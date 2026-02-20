"""A collection of functions which are triggered automatically by finder when
pytz package is included.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cx_Freeze.finder import ModuleFinder
    from cx_Freeze.module import Module


def load_pytz(finder: ModuleFinder, module: Module) -> None:
    """The pytz module requires timezone data to be found in a known directory
    or in the zip file where the package is written.
    """
    source_path = module.file.parent / "zoneinfo"
    if not source_path.is_dir():
        # Fedora (and possibly other systems) use a separate location to
        # store timezone data so look for that here as well
        pytz = __import__("pytz")
        source_path = Path(
            getattr(pytz, "_tzinfo_dir", None)
            or os.getenv("PYTZ_TZDATADIR")
            or "/usr/share/zoneinfo"
        )
    if source_path.is_dir():
        if module.in_file_system >= 1:
            target_path = "share/zoneinfo"
            finder.add_constant("PYTZ_TZDATADIR", target_path)
            finder.include_files(
                source_path, target_path, copy_dependent_files=False
            )
        else:
            finder.zip_include_files(source_path, "pytz/zoneinfo")
    module.exclude_names.add("doctest")


def load_pytz_lazy(_, module: Module) -> None:
    """Ignore module not used in Python 3.x."""
    module.ignore_names.update({"UserDict", "collections.Mapping"})


def load_pytz_tzinfo(_, module: Module) -> None:
    """Ignore module not used in Python 3.x."""
    module.ignore_names.add("sets")


__all__ = ["load_pytz", "load_pytz_lazy", "load_pytz_tzinfo"]
