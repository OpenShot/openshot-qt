"""A collection of functions which are triggered automatically by finder when
PyQt6 package is included.
"""

from __future__ import annotations

import sys
from textwrap import dedent
from typing import TYPE_CHECKING

from cx_Freeze._compat import IS_CONDA, IS_MACOS, IS_MINGW
from cx_Freeze.common import get_resource_file_path
from cx_Freeze.hooks._qthooks import copy_qt_files
from cx_Freeze.hooks._qthooks import (
    load_qt_qtdesigner as load_pyqt6_qtdesigner,
)
from cx_Freeze.hooks._qthooks import load_qt_qtgui as load_pyqt6_qtgui
from cx_Freeze.hooks._qthooks import (
    load_qt_qtmultimedia as load_pyqt6_qtmultimedia,
)
from cx_Freeze.hooks._qthooks import load_qt_qtnetwork as load_pyqt6_qtnetwork
from cx_Freeze.hooks._qthooks import load_qt_qtopengl as load_pyqt6_qtopengl
from cx_Freeze.hooks._qthooks import (
    load_qt_qtopenglwidgets as load_pyqt6_qtopenglwidgets,
)
from cx_Freeze.hooks._qthooks import (
    load_qt_qtpositioning as load_pyqt6_qtpositioning,
)
from cx_Freeze.hooks._qthooks import (
    load_qt_qtprintsupport as load_pyqt6_qtprintsupport,
)
from cx_Freeze.hooks._qthooks import load_qt_qtqml as load_pyqt6_qtqml
from cx_Freeze.hooks._qthooks import load_qt_qtquick as load_pyqt6_qtquick
from cx_Freeze.hooks._qthooks import load_qt_qtsql as load_pyqt6_qtsql
from cx_Freeze.hooks._qthooks import load_qt_qtsvg as load_pyqt6_qtsvg
from cx_Freeze.hooks._qthooks import (
    load_qt_qtwebenginecore as load_pyqt6_qtwebenginecore,
)
from cx_Freeze.hooks._qthooks import (
    load_qt_qtwebenginewidgets as load_pyqt6_qtwebenginewidgets,
)
from cx_Freeze.hooks._qthooks import (
    load_qt_qtwidgets as load_pyqt6_qtwidgets_base,
)

if TYPE_CHECKING:
    from cx_Freeze.finder import ModuleFinder
    from cx_Freeze.module import Module


def load_pyqt6(finder: ModuleFinder, module: Module) -> None:
    """Inject code in PyQt6 __init__ to locate and load plugins and
    resources.
    """
    # Activate an optimized mode when PyQt6 is in zip_include_packages
    if module.in_file_system == 0:
        module.in_file_system = 2

    # Include modules that inject an optional debug code
    qt_debug = get_resource_file_path("hooks/pyqt6", "debug", ".py")
    finder.include_file_as_module(qt_debug, "PyQt6._cx_freeze_qt_debug")

    # Include a qt.conf in the module path (Prefix = lib/PyQt6/Qt6) for macos
    if IS_MACOS:
        finder.include_files(
            get_resource_file_path("hooks/pyqt6", "qt_macos", ".conf"),
            "qt.conf",
        )
        # bdist_mac (.app) uses a different Prefix in qt.conf
        finder.include_files(
            get_resource_file_path("hooks/pyqt6", "qt_bdist_mac", ".conf"),
            "qt_bdist_mac.conf",
        )
    # Include a qt.conf in the module path (Prefix = lib/PyQt6) for msys2
    if IS_MINGW:
        qt_conf = get_resource_file_path("hooks/pyqt6", "qt_msys2", ".conf")
        finder.include_files(qt_conf, "qt.conf")

    # Include a copy of qt.conf (used by QtWebEngine)
    copy_qt_files(finder, "PyQt6", "LibraryExecutablesPath", "qt.conf")

    # Inject code to init
    code_string = module.file.read_text(encoding="utf_8")
    code_string += dedent(
        f"""
        # cx_Freeze patch start
        if {IS_MACOS} and not {IS_CONDA}:  # conda does not support pyqt6
            import os, sys
            # Support for QtWebEngine (bdist_mac differs from build_exe)
            helpers = os.path.join(os.path.dirname(sys.frozen_dir), "Helpers")
            if not os.path.isdir(helpers):
                helpers = os.path.join(sys.frozen_dir, "share")
            os.environ["QTWEBENGINEPROCESS_PATH"] = os.path.join(
                helpers,
                "QtWebEngineProcess.app/Contents/MacOS/QtWebEngineProcess"
            )
            os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--single-process"
        import PyQt6._cx_freeze_qt_debug
        # cx_Freeze patch end
        """
    )
    module.code = compile(code_string, module.file.as_posix(), "exec")


def load_pyqt6_qtwidgets(finder: ModuleFinder, module: Module) -> None:
    """Include module dependency."""
    load_pyqt6_qtwidgets_base(finder, module)
    if sys.platform == "linux":
        copy_qt_files(finder, "PyQt6", "LibrariesPath", "libQt6Widgets.so.6")


__all__ = [
    "load_pyqt6",
    "load_pyqt6_qtdesigner",
    "load_pyqt6_qtgui",
    "load_pyqt6_qtmultimedia",
    "load_pyqt6_qtnetwork",
    "load_pyqt6_qtopengl",
    "load_pyqt6_qtopenglwidgets",
    "load_pyqt6_qtpositioning",
    "load_pyqt6_qtprintsupport",
    "load_pyqt6_qtquick",
    "load_pyqt6_qtqml",
    "load_pyqt6_qtsql",
    "load_pyqt6_qtsvg",
    "load_pyqt6_qtwebenginecore",
    "load_pyqt6_qtwebenginewidgets",
    "load_pyqt6_qtwidgets",
]
