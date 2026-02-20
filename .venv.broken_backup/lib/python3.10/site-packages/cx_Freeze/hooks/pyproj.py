"""A collection of functions which are triggered automatically by finder when
pyproj package is included.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cx_Freeze.finder import ModuleFinder
    from cx_Freeze.module import Module


def load_pyproj(finder: ModuleFinder, module: Module) -> None:
    """The pyproj package."""
    source_dir = module.file.parent.parent / f"{module.name}.libs"
    if source_dir.exists():
        finder.include_files(source_dir, f"lib/{source_dir.name}")
