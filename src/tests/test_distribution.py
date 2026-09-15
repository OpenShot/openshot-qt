"""Distribution detection must not promote downstream or source builds."""

import os
import sys
import ctypes
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import unittest

PATH = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if PATH not in sys.path:
    sys.path.append(PATH)

from classes import distribution, info
from classes.distribution import detect_distribution
from tests.source_tree import source_path


class DistributionTests(unittest.TestCase):
    def detect(self, system="Linux", executable="/usr/bin/openshot-qt", frozen=True,
               environ=None, package_name="", marked=True, flatpak=False):
        return detect_distribution({"official_distribution": marked}, system, executable,
                                   frozen, environ or {}, package_name, flatpak)

    def test_official_packages(self):
        cases = [
            ({"environ": {"APPIMAGE": "/tmp/OpenShot.AppImage"}}, "appimage"),
            ({"system": "Windows", "executable": "C:/OpenShot/openshot-qt.exe"}, "exe"),
            ({"system": "Darwin", "executable": "/Applications/OpenShot.app/Contents/MacOS/openshot-qt"}, "appbundle"),
            ({"system": "Windows", "package_name": "OpenShotStudios.OpenShotforWindows_4.0.0.0_x64__publisher"}, "msix"),
        ]
        for args, kind in cases:
            with self.subTest(kind=kind):
                self.assertEqual(self.detect(**args), {"package_type": kind, "official": True})
                self.assertFalse(self.detect(marked=False, **args)["official"])

    def test_downstream_wrappers_override_official_marker(self):
        for env, flatpak in [({"SNAP": "/snap/openshot/1", "APPIMAGE": "app"}, False),
                             ({"FLATPAK_ID": "org.openshot.OpenShot"}, False), ({}, True)]:
            with self.subTest(env=env, flatpak=flatpak):
                self.assertFalse(self.detect(environ=env, flatpak=flatpak)["official"])

    def test_ppa_source_and_foreign_msix_are_not_official(self):
        self.assertFalse(self.detect()["official"])
        self.assertFalse(self.detect(frozen=False, environ={"APPIMAGE": "app"})["official"])
        self.assertFalse(self.detect(system="Windows", package_name="Other.OpenShot_1_x64__id")["official"])

    def test_source_copy_of_official_metadata_is_not_official(self):
        for args in [dict(system="Windows", executable="C:/python.exe"),
                     dict(system="Darwin", executable="/App.app/Contents/MacOS/python"),
                     dict(system="Windows", package_name="OpenShotStudios.OpenShotforWindows_4.0.0.0_x64__publisher")]:
            self.assertFalse(self.detect(frozen=False, **args)["official"])

    def test_windows_api_uses_two_calls_and_returns_full_identity(self):
        name = "OpenShotStudios.OpenShotforWindows_4.0.0.0_x64__publisher"
        calls = []

        def api(length, buffer):
            calls.append(buffer is None)
            if buffer is None:
                length._obj.value = len(name) + 1
                return 122
            buffer.value = name
            return 0

        with patch.object(ctypes, "WinDLL", return_value=SimpleNamespace(GetCurrentPackageFullName=api), create=True):
            self.assertEqual(distribution.windows_package_name(), name)
        self.assertEqual(calls, [True, False])

    def test_windows_api_fails_safely_without_identity_or_api(self):
        for code, size in [(15700, 0), (5, 0), (122, 0), (122, 1000000)]:
            def api(length, buffer):
                length._obj.value = size
                return code
            with patch.object(ctypes, "WinDLL", return_value=SimpleNamespace(GetCurrentPackageFullName=api), create=True):
                self.assertEqual(distribution.windows_package_name(), "")
        for error in (OSError("unavailable"), AttributeError("unsupported")):
            with patch.object(ctypes, "WinDLL", side_effect=error, create=True):
                self.assertEqual(distribution.windows_package_name(), "")

    def test_windows_api_second_call_failure_is_not_a_package(self):
        def api(length, buffer):
            length._obj.value = 100
            return 122 if buffer is None else 5
        with patch.object(ctypes, "WinDLL", return_value=SimpleNamespace(GetCurrentPackageFullName=api), create=True):
            self.assertEqual(distribution.windows_package_name(), "")

    def test_metadata_loading_and_runtime_version_payload(self):
        with tempfile.TemporaryDirectory() as folder:
            metadata = Path(folder, "settings", "version.json")
            metadata.parent.mkdir()
            with patch.object(info, "PATH", folder), \
                    patch.object(distribution.platform, "system", return_value="Windows"), \
                    patch.object(distribution.platform, "machine", return_value="AMD64"), \
                    patch.object(distribution, "windows_package_name", return_value="OpenShotStudios.OpenShotforWindows_4.0.0.123_x64__publisher"), \
                    patch.object(sys, "frozen", True, create=True), patch.dict(os.environ, {}, clear=True):
                for content in [None, "{bad json", "[]", '{"official_distribution":"true"}']:
                    if content is not None:
                        metadata.write_text(content)
                    distribution.get_distribution_info.cache_clear()
                    self.assertFalse(distribution.get_distribution_info()["official"])
                metadata.write_text(json.dumps({"official_distribution": True, "build_name": "OpenShot-v4.0.0-daily-123"}))
                distribution.get_distribution_info.cache_clear()
                data = distribution.get_distribution_info()
                self.assertTrue(data["official"])
                self.assertEqual(data["package_type"], "msix")
                self.assertEqual(data["package_version"], "4.0.0.123")
                self.assertEqual(data["app_version"], info.VERSION)
                self.assertEqual(data["build_name"], "OpenShot-v4.0.0-daily-123")
                self.assertEqual(data["architecture"], "AMD64")
            distribution.get_distribution_info.cache_clear()


class BuildProvenanceTests(unittest.TestCase):
    def test_only_our_ci_project_marks_official_and_local_rebuild_clears_marker(self):
        sys.path.insert(0, str(source_path("installer").parent))
        self.addCleanup(sys.path.pop, 0)
        from installer.version_parser import write_build_metadata
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder, "version.json")
            official_env = {"CI_SERVER_HOST": "gitlab.openshot.org", "CI_PROJECT_PATH": "OpenShot/openshot-qt"}
            source = {"build_name": "OpenShot-v4.0.0", "official_distribution": True}
            write_build_metadata(target, source, official_env)
            self.assertTrue(json.loads(target.read_text())["official_distribution"])
            for env in [{}, dict(official_env, CI_SERVER_HOST="gitlab.com"),
                        dict(official_env, CI_PROJECT_PATH="someone/openshot-qt")]:
                write_build_metadata(target, source, env)
                self.assertFalse(json.loads(target.read_text())["official_distribution"])
            write_build_metadata(target, {}, {})
            self.assertEqual(json.loads(target.read_text()), {"official_distribution": False})
            self.assertTrue(source["official_distribution"])
