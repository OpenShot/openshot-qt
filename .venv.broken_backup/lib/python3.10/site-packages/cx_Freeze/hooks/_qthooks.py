"""A collection of functions which are the base to hooks for PyQt5, PyQt6,
PySide2 and PySide6.
"""

from __future__ import annotations

import json
import os
import sys
from contextlib import suppress
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

from cx_Freeze._compat import IS_CONDA, IS_MACOS, IS_MINGW, IS_WINDOWS

if TYPE_CHECKING:
    from cx_Freeze.finder import ModuleFinder
    from cx_Freeze.module import Module


def _qt_implementation(module: Module) -> str:
    """Helper function to get the name of the Qt implementation."""
    return module.name.split(".")[0]


@lru_cache(maxsize=None)
def _qt_libraryinfo_paths(name: str) -> dict[str, tuple[Path, Path]]:
    """Cache the QtCore library paths."""
    try:
        qtcore = __import__(name, fromlist=["QtCore"]).QtCore
    except RuntimeError:
        print("WARNING: Tried to load multiple incompatible Qt ", end="")
        print("wrappers. Some incorrect files may be copied.")
        return {}

    # get paths from QLibraryInfo
    source_paths: dict[str, Path] = {}
    lib = qtcore.QLibraryInfo
    major_version = lib.version().majorVersion()
    if major_version == 6:
        if hasattr(lib.LibraryPath, "__members__"):
            for key, value in lib.LibraryPath.__members__.items():
                source_paths[key] = Path(lib.path(value))
        else:
            for key, value in lib.__dict__.items():
                if isinstance(value, lib.LibraryPath):
                    source_paths[key] = Path(lib.path(value))
    else:
        for key, value in lib.__dict__.items():
            if isinstance(value, (lib.LibraryLocation, int)):
                source_paths[key] = Path(lib.location(value))
    qt_root_dir = Path(qtcore.__file__).parent

    # if QLibraryInfo has incomplete information
    if not source_paths.get("PluginsPath"):
        # Qt Plugins can be in a plugins directory next to the Qt libraries
        plugins_path = qt_root_dir / "plugins"
        if not plugins_path.exists():
            plugins_path = qt_root_dir / "Qt5" / "plugins"  # PyQt5 5.15.4
        # or in a special location in conda-forge
        if not plugins_path.exists():
            plugins_path = Path(sys.base_prefix, "Library", "plugins")
        # default location
        if not plugins_path.exists():
            plugins_path = qt_root_dir / "Qt" / "plugins"
        source_paths["PluginsPath"] = plugins_path
    source_paths.setdefault("PrefixPath", source_paths["PluginsPath"].parent)
    prefix_path = source_paths["PrefixPath"]
    source_paths.setdefault("DataPath", prefix_path)
    source_paths.setdefault("LibrariesPath", prefix_path / "lib")
    source_paths.setdefault("SettingsPath", ".")
    if name in ("PySide2", "PySide6") and IS_WINDOWS and not IS_CONDA:
        source_paths["BinariesPath"] = prefix_path
        source_paths["LibraryExecutablesPath"] = prefix_path

    # set the target paths
    data: dict[str, tuple[Path, Path]] = {}
    target_base = Path("lib", name)
    with suppress(ValueError):
        target_base = target_base / prefix_path.relative_to(qt_root_dir)
    if name == "PyQt5" and prefix_path.name != "Qt5":
        # conda pyqt
        target_base = target_base / "Qt5"

    # set some defaults or use relative path
    for key, source in source_paths.items():
        if key == "SettingsPath":  # Check for SettingsPath first
            target = Path("Contents/Resources" if IS_MACOS else ".")
        elif name in ("PySide2", "PySide6") and IS_WINDOWS and not IS_CONDA:
            target = target_base / source.relative_to(prefix_path)
        elif key in ("ArchDataPath", "DataPath", "PrefixPath"):
            target = target_base
        elif key == "BinariesPath":
            target = target_base / "bin"
        elif key == "LibrariesPath":
            target = target_base / "lib"
        elif key == "LibraryExecutablesPath":
            target = target_base / (
                "bin" if IS_WINDOWS or IS_MINGW else "libexec"
            )
        elif key == "PluginsPath":
            target = target_base / "plugins"
        elif key == "TranslationsPath":
            target = target_base / "translations"
        elif source == Path("."):
            target = target_base
        else:
            target = target_base / source.relative_to(prefix_path)
        data[key] = source, target

    # debug
    if os.environ.get("QT_DEBUG"):
        print("QLibraryInfo:")
        for key, (source, target) in sorted(data.items()):
            print(" ", key, source, "->", target)
    return data


def get_qt_paths(name: str, variable: str) -> tuple[Path, Path]:
    """Helper function to get the source and target path of Qt variable."""
    libraryinfo_paths = _qt_libraryinfo_paths(name)
    source_path, target_path = libraryinfo_paths[variable]
    return (source_path, target_path)


def get_qt_plugins_paths(name: str, plugins: str) -> list[tuple[Path, Path]]:
    """Helper function to get a list of source and target paths of Qt plugins,
    indicated to be used in include_files.
    """
    source_path, target_path = get_qt_paths(name, "PluginsPath")
    source_path = source_path / plugins
    if not source_path.exists():
        return []
    return [(source_path, target_path / plugins)]


def copy_qt_files(finder: ModuleFinder, name: str, *args) -> None:
    """Helper function to find and copy Qt plugins, resources, translations,
    etc.
    """
    source_path, target_path = get_qt_paths(name, variable=args[0])
    for arg in args[1:]:
        if "*" in arg:
            # XXX: this code needs improvement
            for source in source_path.glob(arg):
                if source.is_file():
                    finder.include_files(source, target_path / source.name)
            return
        source_path = source_path / arg
        target_path = target_path / arg
    if not source_path.exists():
        return
    finder.include_files(source_path, target_path)


def load_qt_phonon(finder: ModuleFinder, module: Module) -> None:
    """In Windows, phonon5.dll requires an additional dll phonon_ds94.dll to
    be present in the build directory inside a folder phonon_backend.
    """
    if IS_WINDOWS or IS_MINGW:
        name = _qt_implementation(module)
        copy_qt_files(finder, name, "PluginsPath", "phonon_backend")


def load_qt_qtdesigner(finder: ModuleFinder, module: Module) -> None:
    """Include plugins for the module."""
    name = _qt_implementation(module)
    copy_qt_files(finder, name, "PluginsPath", "designer")


def load_qt_qtgui(finder: ModuleFinder, module: Module) -> None:
    """There is a chance that QtGui will use some image formats, then, add the
    image format plugins.
    """
    name = _qt_implementation(module)
    copy_qt_files(finder, name, "PluginsPath", "accessiblebridge")
    copy_qt_files(finder, name, "PluginsPath", "generic")
    copy_qt_files(finder, name, "PluginsPath", "imageformats")
    copy_qt_files(finder, name, "PluginsPath", "pictureformats")  # obsolete
    # For simplicity, we just copy the platform plugins that are installed.
    copy_qt_files(finder, name, "PluginsPath", "platforminputcontexts")
    copy_qt_files(finder, name, "PluginsPath", "platforms")
    copy_qt_files(finder, name, "PluginsPath", "platformthemes")


def load_qt_qtmultimedia(finder: ModuleFinder, module: Module) -> None:
    """Include plugins for the module."""
    name = _qt_implementation(module)
    copy_qt_files(finder, name, "PluginsPath", "audio")
    copy_qt_files(finder, name, "PluginsPath", "mediaservice")
    copy_qt_files(finder, name, "PluginsPath", "multimedia")
    copy_qt_files(finder, name, "PluginsPath", "playlistformats")
    copy_qt_files(finder, name, "PluginsPath", "resourcepolicy")
    copy_qt_files(finder, name, "PluginsPath", "video")


def load_qt_qtnetwork(finder: ModuleFinder, module: Module) -> None:
    """Include plugins for the module."""
    name = _qt_implementation(module)
    copy_qt_files(finder, name, "PluginsPath", "bearer")
    copy_qt_files(finder, name, "PluginsPath", "networkinformation")
    copy_qt_files(finder, name, "PluginsPath", "tls")


def load_qt_qtopengl(finder: ModuleFinder, module: Module) -> None:
    """Include plugins for the module."""
    name = _qt_implementation(module)
    copy_qt_files(finder, name, "PluginsPath", "renderers")


def load_qt_qtopenglwidgets(finder: ModuleFinder, module: Module) -> None:
    """Include plugins for the module."""
    name = _qt_implementation(module)
    copy_qt_files(finder, name, "PluginsPath", "renderers")


def load_qt_qtpositioning(finder: ModuleFinder, module: Module) -> None:
    """Include plugins for the module."""
    name = _qt_implementation(module)
    copy_qt_files(finder, name, "PluginsPath", "position")


def load_qt_qtprintsupport(finder: ModuleFinder, module: Module) -> None:
    """Include plugins for the module."""
    name = _qt_implementation(module)
    copy_qt_files(finder, name, "PluginsPath", "printsupport")
    copy_qt_files(finder, name, "BinariesPath", "Qt?Pdf*.dll")


def load_qt_qtqml(finder: ModuleFinder, module: Module) -> None:
    """Include plugins for the module."""
    name = _qt_implementation(module)
    copy_qt_files(finder, name, "PluginsPath", "qmltooling")


def load_qt_qtquick(finder: ModuleFinder, module: Module) -> None:
    """Include plugins for the module."""
    name = _qt_implementation(module)
    copy_qt_files(finder, name, "PluginsPath", "scenegraph")


def load_qt_qtscript(finder: ModuleFinder, module: Module) -> None:
    """Include plugins for the module."""
    name = _qt_implementation(module)
    copy_qt_files(finder, name, "PluginsPath", "script")


def load_qt_qtsensors(finder: ModuleFinder, module: Module) -> None:
    """Include plugins for the module."""
    name = _qt_implementation(module)
    copy_qt_files(finder, name, "PluginsPath", "sensorgestures")
    copy_qt_files(finder, name, "PluginsPath", "sensors")


def load_qt_qtsql(finder: ModuleFinder, module: Module) -> None:
    """Include plugins for the module."""
    name = _qt_implementation(module)
    copy_qt_files(finder, name, "PluginsPath", "sqldrivers")


def load_qt_qtsvg(finder: ModuleFinder, module: Module) -> None:
    """Include plugins for the module."""
    name = _qt_implementation(module)
    copy_qt_files(finder, name, "PluginsPath", "iconengines")


def load_qt_qtwebenginecore(finder: ModuleFinder, module: Module) -> None:
    """Include module dependency and QtWebEngineProcess files."""
    name = _qt_implementation(module)

    if IS_WINDOWS:
        for filename in (
            "QtWebEngineProcess.exe",
            "d3dcompiler_47.dll",
            "libEGL.dll",
            "libGLESv2.dll",
            "opengl32sw.dll",
        ):
            # pyside2 - only QtWebEngineProcess is in LibraryExecutablesPath
            # pyside6 - like pyside2, but the two lib*.dll are missing
            copy_qt_files(finder, name, "ArchDataPath", filename)
            # pyqt5 - all files listed in LibraryExecutablesPath
            copy_qt_files(finder, name, "LibraryExecutablesPath", filename)
    elif IS_MACOS and not IS_CONDA:
        # wheels for macOS
        source_path, _ = get_qt_paths(name, "LibrariesPath")
        source_framework = source_path / "QtWebEngineCore.framework"
        # QtWebEngineProcess
        finder.include_files(source_framework / "Helpers", "share")
        # QtWebEngineCore resources
        source_resources = source_framework / "Resources"
        if source_resources.exists():
            target_datapath = get_qt_paths(name, "DataPath")[1]
            for resource in source_resources.iterdir():
                if resource.name == "Info.plist":
                    continue
                if resource.name == "qtwebengine_locales":
                    target = get_qt_paths(name, "TranslationsPath")[1]
                else:
                    target = target_datapath / "resources"
                finder.include_files(
                    resource,
                    target / resource.name,
                    copy_dependent_files=False,
                )
    else:
        # wheels for Linux or conda-forge Linux and macOS
        copy_qt_files(
            finder, name, "LibraryExecutablesPath", "QtWebEngineProcess"
        )
        if IS_CONDA:  # conda-forge Linux and macOS
            prefix = Path(sys.prefix)
            conda_meta = prefix / "conda-meta"
            pkg = next(conda_meta.glob("nss-*.json"))
            files = json.loads(pkg.read_text(encoding="utf_8"))["files"]
            for file in files:
                source = prefix / file
                if source.match("lib*.so") or source.match("lib*.dylib"):
                    finder.include_files(source, f"lib/{source.name}")
        else:
            copy_qt_files(finder, name, "LibraryExecutablesPath", "libnss*.*")

    copy_qt_files(finder, name, "DataPath", "resources")
    copy_qt_files(finder, name, "TranslationsPath", "qtwebengine_*")


def load_qt_qtwebenginewidgets(finder: ModuleFinder, module: Module) -> None:
    """Include data and plugins for the module."""
    name = _qt_implementation(module)
    copy_qt_files(finder, name, "LibrariesPath", "*WebEngineWidgets.*")
    copy_qt_files(finder, name, "PluginsPath", "designer")
    copy_qt_files(finder, name, "PluginsPath", "imageformats")
    copy_qt_files(finder, name, "PluginsPath", "webview")
    copy_qt_files(finder, name, "PluginsPath", "xcbglintegrations")


def load_qt_qtwidgets(finder: ModuleFinder, module: Module) -> None:
    """Include plugins for the module."""
    name = _qt_implementation(module)
    copy_qt_files(finder, name, "PluginsPath", "accessible")
    copy_qt_files(finder, name, "PluginsPath", "styles")


def load_qt_uic(finder: ModuleFinder, module: Module) -> None:
    """The uic module makes use of "plugins" that need to be read directly and
    cannot be frozen; the PyQt5.QtWebKit and PyQt5.QtNetwork modules are
    also implicity loaded.
    """
    name = _qt_implementation(module)
    source_dir = module.path[0] / "widget-plugins"
    if source_dir.exists():
        finder.include_files(source_dir, f"{name}.uic.widget-plugins")
