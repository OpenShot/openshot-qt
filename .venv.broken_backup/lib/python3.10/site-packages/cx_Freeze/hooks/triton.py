"""A collection of functions which are triggered automatically by finder when
triton package is included.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cx_Freeze.finder import ModuleFinder
    from cx_Freeze.module import Module


def load_triton(finder: ModuleFinder, module: Module) -> None:
    """Hook for triton."""
    # exclude _C module that causes RecursionError
    finder.exclude_module("triton._C")
    # but, include the module libtriton as library
    source_lib = module.file.parent / "_C"
    if source_lib.exists():
        finder.include_files(source_lib, f"lib/{module.name}/_C")
