"""A collection of functions which are triggered automatically by finder when
scipy package is included.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cx_Freeze.finder import ModuleFinder
    from cx_Freeze.module import Module


def load_sklearn__distributor_init(
    finder: ModuleFinder, module: Module
) -> None:
    """Fix the location of dependent files in Windows."""
    source_dir = module.parent.path[0] / ".libs"
    if source_dir.exists():
        # msvcp140 and vcomp140 dlls should be copied
        finder.include_files(source_dir, "lib")
        # patch the code to search the correct directory
        code_string = module.file.read_text(encoding="utf_8")
        code_string = code_string.replace(
            "libs_path =", "libs_path = __import__('sys').frozen_dir  #"
        )
        module.code = compile(code_string, os.fspath(module.file), "exec")
