"""Exercise launcher imports in fresh processes without the source on sys.path."""

import os
from pathlib import Path
import shutil
import subprocess  # nosec B404 - Run the local launcher in an isolated process.
import sys
import tempfile
import unittest


class LaunchTests(unittest.TestCase):
    def check_launch(self, installed):
        source = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = root / ("openshot_qt" if installed else "src")
            (package / "classes").mkdir(parents=True)
            # Stage the real modules needed by --version, using setup.py's layout.
            for name in ("__init__.py", "launch.py", "qt_api.py",
                         "classes/__init__.py", "classes/info.py", "classes/log_config.py"):
                shutil.copy2(str(source / name), str(package / name))

            home = root / "home"
            home.mkdir()
            env = dict(os.environ, HOME=str(home), USERPROFILE=str(home),
                       PYTHONPATH=str(root), QT_QPA_PLATFORM="offscreen")
            if installed:
                # Load the same entry point used by the installed openshot-qt script.
                command = [sys.executable, "-c", (
                    "from importlib.metadata import EntryPoint; "
                    "EntryPoint(name='openshot-qt', "
                    "value='openshot_qt.launch:main', group='gui_scripts').load()()"
                ), "--version"]
            else:
                command = [sys.executable, str(package / "launch.py"), "--version"]

            result = subprocess.run(  # nosec B603 - Fixed local Python command, no shell.
                command, cwd=str(home), env=env, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, universal_newlines=True, timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertRegex(result.stdout.strip().splitlines()[-1], r"^\d+\.\d+\.\d+\S*$")

    def test_installed_entry_point(self):
        self.check_launch(installed=True)

    def test_source_script(self):
        self.check_launch(installed=False)


if __name__ == "__main__":
    unittest.main()
