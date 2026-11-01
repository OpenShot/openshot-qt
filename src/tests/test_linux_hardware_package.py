"""Exercise the Linux package checker's isolated child process without a GPU."""
import subprocess  # nosec B404 - Runs the local package checker without a shell.
import sys
import tempfile
import unittest

from tests.source_tree import source_path


@unittest.skipUnless(sys.platform.startswith('linux'), 'Linux AppImage runtime check')
class LinuxHardwarePackageTests(unittest.TestCase):
    def test_child_runs_runtime_check_and_rejects_missing_bundled_ffmpeg(self):
        checker = source_path('installer/check-linux-hardware.py')
        with tempfile.TemporaryDirectory() as bundle:
            result = subprocess.run(  # nosec B603 - Fixed interpreter and repository checker; no shell.
                [sys.executable, str(checker), bundle], capture_output=True,
                text=True, timeout=20)
        self.assertNotEqual(result.returncode, 0)
        # The child must reach CDLL loading, rather than treat its code as a filename.
        self.assertIn('libavcodec.so.61', result.stderr)
        self.assertNotIn("can't open file", result.stderr)
