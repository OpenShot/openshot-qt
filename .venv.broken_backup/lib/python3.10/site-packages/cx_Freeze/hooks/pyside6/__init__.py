"""A collection of functions which are triggered automatically by finder when
PySide6 package is included.
"""

from __future__ import annotations

from textwrap import dedent
from typing import TYPE_CHECKING

from cx_Freeze._compat import IS_CONDA, IS_MACOS, IS_MINGW
from cx_Freeze.common import (
    code_object_replace_function,
    get_resource_file_path,
)
from cx_Freeze.hooks._qthooks import (
    load_qt_qtdesigner as load_pyside6_qtdesigner,
)
from cx_Freeze.hooks._qthooks import load_qt_qtgui as load_pyside6_qtgui
from cx_Freeze.hooks._qthooks import (
    load_qt_qtmultimedia as load_pyside6_qtmultimedia,
)
from cx_Freeze.hooks._qthooks import (
    load_qt_qtnetwork as load_pyside6_qtnetwork,
)
from cx_Freeze.hooks._qthooks import load_qt_qtopengl as load_pyside6_qtopengl
from cx_Freeze.hooks._qthooks import (
    load_qt_qtopenglwidgets as load_pyside6_qtopenglwidgets,
)
from cx_Freeze.hooks._qthooks import (
    load_qt_qtpositioning as load_pyside6_qtpositioning,
)
from cx_Freeze.hooks._qthooks import (
    load_qt_qtprintsupport as load_pyside6_qtprintsupport,
)
from cx_Freeze.hooks._qthooks import load_qt_qtqml as load_pyside6_qtqml
from cx_Freeze.hooks._qthooks import load_qt_qtquick as load_pyside6_qtquick
from cx_Freeze.hooks._qthooks import load_qt_qtsql as load_pyside6_qtsql
from cx_Freeze.hooks._qthooks import load_qt_qtsvg as load_pyside6_qtsvg
from cx_Freeze.hooks._qthooks import (
    load_qt_qtwebenginecore as load_pyside6_qtwebenginecore,
)
from cx_Freeze.hooks._qthooks import (
    load_qt_qtwebenginewidgets as load_pyside6_qtwebenginewidgets,
)
from cx_Freeze.hooks._qthooks import (
    load_qt_qtwidgets as load_pyside6_qtwidgets,
)

if TYPE_CHECKING:
    from cx_Freeze.finder import ModuleFinder
    from cx_Freeze.module import Module


def load_pyside6(finder: ModuleFinder, module: Module) -> None:
    """Inject code in PySide6 __init__ to locate and load plugins and
    resources.
    """
    # Activate an optimized mode when PySide6 is in zip_include_packages
    if module.in_file_system == 0:
        module.in_file_system = 2

    # Include modules that inject an optional debug code
    qt_debug = get_resource_file_path("hooks/pyside6", "debug", ".py")
    finder.include_file_as_module(qt_debug, "PySide6._cx_freeze_qt_debug")

    # Include a resource for conda-forge
    if IS_CONDA:
        # The resource include a qt.conf (Prefix = lib/PySide6)
        resource = get_resource_file_path("hooks/pyside6", "resource", ".py")
        finder.include_file_as_module(resource, "PySide6._cx_freeze_resource")

    if IS_MINGW:
        # Include a qt.conf in the module path (Prefix = lib/PySide6)
        qt_conf = get_resource_file_path("hooks/pyside6", "qt", ".conf")
        finder.include_files(qt_conf, qt_conf.name)

    # Inject code to init
    code_string = module.file.read_text(encoding="utf_8")
    code_string += dedent(
        f"""
        # cx_Freeze patch start
        if {IS_CONDA}:
            import PySide6._cx_freeze_resource
        else:
            # Support for QtWebEngine
            import os, sys
            if {IS_MACOS}:
                # is a bdist_mac ou build_exe directory?
                helpers = os.path.join(
                    os.path.dirname(sys.frozen_dir), "Helpers"
                )
                if not os.path.isdir(helpers):
                    helpers = os.path.join(sys.frozen_dir, "share")
                os.environ["QTWEBENGINEPROCESS_PATH"] = os.path.join(
                    helpers,
                    "QtWebEngineProcess.app/Contents/MacOS/QtWebEngineProcess"
                )
                os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--single-process"
        import PySide6._cx_freeze_qt_debug
        # cx_Freeze patch end
        """
    )
    code = compile(code_string, module.file.as_posix(), "exec")

    # shiboken6 in zip_include_packages
    shiboken6 = finder.include_package("shiboken6")
    if shiboken6.in_file_system == 0:
        name = "_additional_dll_directories"
        source = f"""\
        def {name}(package_dir):
            return []
        """
        code = code_object_replace_function(code, name, source)
    finder.include_module("inspect")  # for shiboken6

    module.code = code


__all__ = [
    "load_pyside6",
    "load_pyside6_qtdesigner",
    "load_pyside6_qtgui",
    "load_pyside6_qtmultimedia",
    "load_pyside6_qtnetwork",
    "load_pyside6_qtopengl",
    "load_pyside6_qtopenglwidgets",
    "load_pyside6_qtpositioning",
    "load_pyside6_qtprintsupport",
    "load_pyside6_qtquick",
    "load_pyside6_qtqml",
    "load_pyside6_qtsql",
    "load_pyside6_qtsvg",
    "load_pyside6_qtwebenginecore",
    "load_pyside6_qtwebenginewidgets",
    "load_pyside6_qtwidgets",
]
