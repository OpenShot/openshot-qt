"""A collection of functions which are triggered automatically by finder when
PyQt5 package is included.
"""

from __future__ import annotations

from textwrap import dedent
from typing import TYPE_CHECKING

from cx_Freeze._compat import IS_CONDA, IS_MACOS
from cx_Freeze.common import get_resource_file_path
from cx_Freeze.hooks._qthooks import copy_qt_files
from cx_Freeze.hooks._qthooks import (
    load_qt_qtdesigner as load_pyqt5_qtdesigner,
)
from cx_Freeze.hooks._qthooks import load_qt_qtgui as load_pyqt5_qtgui
from cx_Freeze.hooks._qthooks import (
    load_qt_qtmultimedia as load_pyqt5_qtmultimedia,
)
from cx_Freeze.hooks._qthooks import load_qt_qtnetwork as load_pyqt5_qtnetwork
from cx_Freeze.hooks._qthooks import load_qt_qtopengl as load_pyqt5_qtopengl
from cx_Freeze.hooks._qthooks import (
    load_qt_qtpositioning as load_pyqt5_qtpositioning,
)
from cx_Freeze.hooks._qthooks import (
    load_qt_qtprintsupport as load_pyqt5_qtprintsupport,
)
from cx_Freeze.hooks._qthooks import load_qt_qtqml as load_pyqt5_qtqml
from cx_Freeze.hooks._qthooks import load_qt_qtsql as load_pyqt5_qtsql
from cx_Freeze.hooks._qthooks import load_qt_qtsvg as load_pyqt5_qtsvg
from cx_Freeze.hooks._qthooks import (
    load_qt_qtwebenginecore as _load_qt_qtwebenginecore,
)
from cx_Freeze.hooks._qthooks import (
    load_qt_qtwebenginewidgets as load_pyqt5_qtwebenginewidgets,
)
from cx_Freeze.hooks._qthooks import load_qt_qtwidgets as load_pyqt5_qtwidgets
from cx_Freeze.hooks._qthooks import load_qt_uic as load_pyqt5_uic

if TYPE_CHECKING:
    from cx_Freeze.finder import ModuleFinder
    from cx_Freeze.module import Module


def load_pyqt5(finder: ModuleFinder, module: Module) -> None:
    """Inject code in PyQt5 __init__ to locate and load plugins and
    resources. Also, this fixes issues with conda-forge versions.
    """
    # Activate an optimized mode when PyQt5 is in zip_include_packages
    if module.in_file_system == 0:
        module.in_file_system = 2

    # Include a module that fix an issue
    qt_debug = get_resource_file_path("hooks/pyqt5", "_append_to_init", ".py")
    finder.include_file_as_module(qt_debug, "PyQt5._cx_freeze_append_to_init")

    # Include a module that inject an optional debug code
    qt_debug = get_resource_file_path("hooks/pyqt5", "debug", ".py")
    finder.include_file_as_module(qt_debug, "PyQt5._cx_freeze_debug")

    # Include a resource with qt.conf (Prefix = lib/PyQt5) for conda-forge
    if IS_CONDA:
        resource = get_resource_file_path("hooks/pyqt5", "resource", ".py")
        finder.include_file_as_module(resource, "PyQt5._cx_freeze_resource")

    # Include an optional qt.conf to be used by QtWebEngine (Prefix = ..)
    copy_qt_files(finder, "PyQt5", "LibraryExecutablesPath", "qt.conf")

    # Inject code to the end of init
    code_string = module.file.read_text(encoding="utf_8")
    code_string += dedent(
        f"""
        # cx_Freeze patch start
        import os, sys
        if {IS_CONDA}:  # conda-forge linux, macos and windows
            import PyQt5._cx_freeze_resource
        elif {IS_MACOS}:  # macos using 'pip install pyqt5'
            # Support for QtWebEngine (bdist_mac differs from build_exe)
            helpers = os.path.join(os.path.dirname(sys.frozen_dir), "Helpers")
            if not os.path.isdir(helpers):
                helpers = os.path.join(sys.frozen_dir, "share")
            os.environ["QTWEBENGINEPROCESS_PATH"] = os.path.join(
                helpers,
                "QtWebEngineProcess.app/Contents/MacOS/QtWebEngineProcess"
            )
            os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--single-process"
        else:
            # Support for QtWebEngine (linux and windows using pip)
            os.environ["QTWEBENGINE_DISABLE_SANDBOX"] = "1"
        import PyQt5._cx_freeze_append_to_init
        import PyQt5._cx_freeze_debug
        # cx_Freeze patch end
        """
    )
    module.code = compile(code_string, module.file.as_posix(), "exec")


def load_pyqt5_qtwebenginecore(finder: ModuleFinder, module: Module) -> None:
    """Include module dependency and QtWebEngineProcess files."""
    _load_qt_qtwebenginecore(finder, module)
    if IS_MACOS and not IS_CONDA:
        # duplicate resource files
        for source, target in finder.included_files[:]:
            if any(
                filter(source.match, ("Resources/*.pak", "Resources/*.dat"))
            ):
                finder.include_files(
                    source,
                    target.parent.parent / target.name,
                    copy_dependent_files=False,
                )


__all__ = [
    "load_pyqt5",
    "load_pyqt5_qtdesigner",
    "load_pyqt5_qtgui",
    "load_pyqt5_qtmultimedia",
    "load_pyqt5_qtnetwork",
    "load_pyqt5_qtopengl",
    "load_pyqt5_qtpositioning",
    "load_pyqt5_qtprintsupport",
    "load_pyqt5_qtqml",
    "load_pyqt5_qtsql",
    "load_pyqt5_qtsvg",
    "load_pyqt5_qtwebenginecore",
    "load_pyqt5_qtwebenginewidgets",
    "load_pyqt5_qtwidgets",
    "load_pyqt5_uic",
]
