"""Exercise launcher imports in fresh processes without the source on sys.path."""

import os
import json
from pathlib import Path
import shutil
import subprocess  # nosec B404 - Run the local launcher in an isolated process.
import sys
import tempfile
import unittest


class LaunchTests(unittest.TestCase):
    def test_saved_scale_is_safe_before_application_creation(self):
        source = Path(__file__).resolve().parents[1]
        script = r'''
import os
from qt_api import QtCore, QtWidgets
QtCore.qVersion = lambda: os.environ["TEST_QT_VERSION"]
import launch
assert float(os.environ["QT_SCALE_FACTOR"]) == float(os.environ["TEST_EXPECTED_SCALE"])
assert QtWidgets.QApplication.instance() is None
'''
        for version, requested, expected in (
                ("5.15.2", 0.75, 1.0),
                ("6.6.3", 0.75, 1.0),
                ("6.7.0", 0.75, 0.75),
                ("6.10.0", 0.75, 0.75),
                ("5.15.2", 1.5, 1.5)):
            with self.subTest(version=version, scale=requested), tempfile.TemporaryDirectory() as directory:
                profile = Path(directory) / ".openshot_qt"
                profile.mkdir()
                (profile / "openshot.settings").write_text(json.dumps([
                    {"setting": "ui-scale", "value": requested}]))
                env = dict(os.environ, HOME=directory, USERPROFILE=directory,
                           PYTHONPATH=str(source), QT_QPA_PLATFORM="offscreen",
                           QT_SCALE_FACTOR="0.75", TEST_QT_VERSION=version,
                           TEST_EXPECTED_SCALE=str(expected))
                result = subprocess.run(
                    [sys.executable, "-c", script], env=env,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    universal_newlines=True, timeout=30)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def check_launch(self, installed):
        source = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = root / ("openshot_qt" if installed else "src")
            (package / "classes").mkdir(parents=True)
            # Stage the real modules needed by --version, using setup.py's layout.
            for name in ("__init__.py", "launch.py", "qt_api.py",
                         "classes/__init__.py", "classes/info.py", "classes/log_config.py",
                         "classes/ui_scale.py"):
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
