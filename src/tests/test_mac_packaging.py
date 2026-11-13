"""Mac packaging regression checks using binary fixtures and mocked Apple tools."""

import contextlib
import importlib.util
import io
from pathlib import Path
import struct
import tempfile
import unittest
from unittest import mock

from tests.source_tree import source_path


spec = importlib.util.spec_from_file_location(
    "fix_qt5_rpath", source_path("installer/fix_qt5_rpath.py"))
rpath = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rpath)
X86_64 = 0x01000007


def thin_binary(machine):
    return b"\xcf\xfa\xed\xfe" + struct.pack("<I", machine) + bytes(24)


class MacPackagingTests(unittest.TestCase):
    def test_arm_detection_for_thin_universal_and_invalid_files(self):
        fixtures = [(thin_binary(X86_64), False),
                    (thin_binary(rpath.CPU_TYPE_ARM64), True),
                    (b"not a Mach-O file", False),
                    (b"\xcf\xfa\xed\xfe", False)]
        for magic, arch_size in ((b"\xca\xfe\xba\xbe", 20),
                                 (b"\xca\xfe\xba\xbf", 32)):
            entries = b"".join(struct.pack(">I", machine) + bytes(arch_size - 4)
                               for machine in (X86_64, rpath.CPU_TYPE_ARM64))
            fixtures.append((magic + struct.pack(">I", 2) + entries, True))
            fixtures.append((magic + struct.pack(">I", 2), False))
        with tempfile.TemporaryDirectory() as directory:
            binary = Path(directory) / "example.dylib"
            for data, expected in fixtures:
                with self.subTest(data=data):
                    binary.write_bytes(data)
                    self.assertEqual(rpath.has_arm64_code(binary), expected)

    def test_codesign_failure_stops_packaging(self):
        result = mock.Mock(returncode=1, stdout=b"signature rejected")
        with mock.patch.object(rpath.subprocess, "run", return_value=result):
            with self.assertRaisesRegex(RuntimeError, "signature rejected"):
                rpath.adhoc_sign("example.dylib")

    def test_intel_and_arm_dependency_relocation(self):
        for machine, prefix in ((X86_64, "/usr/local"),
                                (rpath.CPU_TYPE_ARM64, "/opt/homebrew")):
            with self.subTest(machine=machine), tempfile.TemporaryDirectory() as directory:
                binary = Path(directory) / "openshot-qt"
                binary.write_bytes(thin_binary(machine))
                dependency = Path(directory) / "libQt5Core.dylib"
                dependency.write_bytes(thin_binary(X86_64))
                source = prefix + "/lib/libQt5Core.dylib"
                output = ("openshot-qt (architecture arm64):\n"
                          "\t%s (compatibility version 5.0.0, current version 5.15.0)\n" % source)
                process = mock.Mock()
                process.communicate.return_value = (output.encode(), None)
                with mock.patch.object(rpath.subprocess, "Popen", return_value=process), \
                     mock.patch.object(rpath, "call") as install_name_tool, \
                     mock.patch.object(rpath, "adhoc_sign") as sign:
                    rpath.fix_rpath(directory)
                install_name_tool.assert_any_call([
                    "install_name_tool", str(binary), "-change", source,
                    "@executable_path/libQt5Core.dylib"])
                if machine == rpath.CPU_TYPE_ARM64:
                    sign.assert_called_once_with(str(binary))
                else:
                    sign.assert_not_called()

    def test_minimum_versions_ignore_trailing_zero_components(self):
        for arch, version, error in (("arm64", "11.0", False),
                                     ("arm64", "11.0.0", False),
                                     ("arm64", "11.0.1", True),
                                     ("x86_64", "10.15.0", False),
                                     ("x86_64", "11.0", True)):
            with self.subTest(arch=arch, version=version), tempfile.TemporaryDirectory() as directory:
                (Path(directory) / "example.dylib").write_bytes(thin_binary(X86_64))
                process = mock.Mock()
                process.communicate.return_value = (
                    ("cmd LC_BUILD_VERSION\n minos %s\n sdk 15.0\n" % version).encode(), None)
                output = io.StringIO()
                with mock.patch.object(rpath.platform, "machine", return_value=arch), \
                     mock.patch.object(rpath.subprocess, "Popen", return_value=process), \
                     contextlib.redirect_stdout(output):
                    rpath.print_min_versions(directory)
                self.assertEqual("ERROR!!!!" in output.getvalue(), error)
                self.assertIn("min: %s, sdk: 15.0" % version, output.getvalue())


if __name__ == "__main__":
    unittest.main()
