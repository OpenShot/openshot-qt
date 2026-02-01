"""A collection of functions which are triggered automatically by finder when
zoneinfo package is included.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cx_Freeze.finder import ModuleFinder
    from cx_Freeze.module import Module


def load_zoneinfo(finder: ModuleFinder, module: Module) -> None:
    """The zoneinfo package requires timezone data,
    that can be the in tzdata package, if installed.
    """
    try:
        finder.include_package("tzdata")
    except ImportError:
        pass
    else:
        return

    # without tzdata, copy only zoneinfo directory
    source_path = None
    zoneinfo = __import__(module.name, fromlist=["TZPATH"])
    if zoneinfo.TZPATH:
        for path in zoneinfo.TZPATH:
            if path.endswith("zoneinfo"):
                source_path = Path(path)
                break
    if source_path is None or not source_path.is_dir():
        return
    if module.in_file_system == 0:
        finder.zip_include_files(source_path, "tzdata/zoneinfo")
    else:
        target_path = "share/zoneinfo"
        finder.add_constant("PYTHONTZPATH", target_path)
        finder.include_files(
            source_path, target_path, copy_dependent_files=False
        )


__all__ = ["load_zoneinfo"]
