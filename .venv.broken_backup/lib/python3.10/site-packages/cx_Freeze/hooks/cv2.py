"""A collection of functions which are triggered automatically by finder when
opencv-python package is included.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

from cx_Freeze._compat import IS_MACOS, IS_MINGW, IS_MINGW64, IS_WINDOWS

if TYPE_CHECKING:
    from cx_Freeze.finder import ModuleFinder
    from cx_Freeze.module import Module


def load_cv2(finder: ModuleFinder, module: Module) -> None:
    """Versions of cv2 (opencv-python) above 4.5.3 require additional
    configuration files.

    Additionally, on Linux the opencv_python.libs directory is not
    copied across for versions above 4.5.3.
    """
    finder.include_package("numpy")
    if module.distribution is None:
        module.update_distribution("opencv-python")

    source_dir = module.file.parent
    target_dir = Path("lib", "cv2")

    # conda-forge and msys2: cv2 4.6.0 is a extension module
    if module.path is None:
        # msys2 files is on 'share' subdirectory
        if IS_MINGW:
            if IS_MINGW64:
                source = Path(sys.base_prefix, "share/qt6/plugins/platforms")
            else:
                source = Path(sys.base_prefix, "share/qt5/plugins/platforms")
        else:
            source = Path(sys.base_prefix, "plugins/platforms")
        if source.is_dir():
            finder.include_files(source, target_dir / "plugins" / "platforms")
        source = Path(sys.base_prefix, "fonts")
        if not source.is_dir():
            source = Path(sys.base_prefix, "share/fonts")
        if source.is_dir():
            finder.include_files(source, target_dir / "fonts")
        qt_conf: Path = finder.cache_path / "qt.conf"
        lines = ["[Paths]", f"Prefix = {target_dir.as_posix()}"]
        with qt_conf.open(mode="w", encoding="utf_8", newline="") as file:
            file.write("\n".join(lines))
        finder.include_files(qt_conf, qt_conf.name)
        if IS_MACOS:
            finder.include_files(qt_conf, "Contents/Resources/qt.conf")
        return

    # Use optmized mode
    module.in_file_system = 2
    finder.include_package("cv2")
    finder.exclude_module("cv2.config-3")
    finder.exclude_module("cv2.load_config_py2")
    module.exclude_names.add("load_config_py2")
    # include files config.py (empty) and config-3.py (original)
    source = finder.cache_path / "cv2-config.py"
    source.touch()
    finder.include_files(source, target_dir / "config.py")
    finder.include_files(
        source_dir / "config-3.py", target_dir / "config-3.py"
    )
    # data files
    data_dir = source_dir / "data"
    if data_dir.exists():
        for path in data_dir.glob("*.xml"):
            finder.include_files(path, target_dir / "data" / path.name)

    # Copy all binary files
    if IS_WINDOWS:
        for path in source_dir.glob("*.dll"):
            finder.include_files(path, target_dir / path.name)
        return

    if IS_MACOS:
        libs_dir = source_dir / ".dylibs"
        if libs_dir.exists():
            finder.include_files(libs_dir, target_dir / ".dylibs")
        return

    # Linux and others
    libs_name = "opencv_python.libs"
    libs_dir = source_dir.parent / libs_name
    if libs_dir.exists():
        finder.include_files(libs_dir, target_dir.parent / libs_name)
    qt_files = source_dir / "qt"
    if qt_files.exists():
        finder.include_files(qt_files, target_dir / "qt")
