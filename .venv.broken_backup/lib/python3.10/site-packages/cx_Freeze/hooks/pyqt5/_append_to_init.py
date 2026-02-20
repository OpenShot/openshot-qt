"""Module used to inject a code to guessing and set the plugins directory."""

import sys
from pathlib import Path


def _run() -> None:
    qtcore = __import__("PyQt5", fromlist=["QtCore"]).QtCore

    # With PyQt5 5.15.4, if the folder name contains non-ascii characters, the
    # libraryPaths returns empty. Prior to this version, this doesn't happen.
    executable_dir = Path(sys.executable).parent
    qt_root_dir = executable_dir / "lib" / "PyQt5"
    plugins_dir = qt_root_dir / "Qt5" / "plugins"  # PyQt5 5.15.4
    if not plugins_dir.is_dir():
        plugins_dir = qt_root_dir / "Qt" / "plugins"
    if not plugins_dir.is_dir():
        plugins_dir = qt_root_dir / "plugins"
    if plugins_dir.is_dir():
        qtcore.QCoreApplication.addLibraryPath(plugins_dir.as_posix())


_run()
