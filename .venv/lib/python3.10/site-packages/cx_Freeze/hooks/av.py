"""A collection of functions which are triggered automatically by finder when
AV/PyAV package is included.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from cx_Freeze._compat import IS_WINDOWS
from cx_Freeze.hooks._libs import replace_delvewheel_patch

if TYPE_CHECKING:
    from cx_Freeze.finder import ModuleFinder
    from cx_Freeze.module import Module


def load_av(finder: ModuleFinder, module: Module) -> None:
    """The AV or PyAV package."""
    if IS_WINDOWS:
        libs_name = "av.libs"
        source_dir = module.file.parent.parent / libs_name
        if not source_dir.exists():
            libs_name = "pyav.libs"
            source_dir = module.file.parent.parent / libs_name
        if source_dir.exists():
            finder.include_files(source_dir, f"lib/{libs_name}")
            replace_delvewheel_patch(module, libs_name)
    finder.include_module("av.deprecation")
