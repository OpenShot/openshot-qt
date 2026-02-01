"""A collection of functions which are triggered automatically by finder when
ssl module is included.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

from cx_Freeze._compat import IS_WINDOWS

if TYPE_CHECKING:
    from cx_Freeze.finder import ModuleFinder
    from cx_Freeze.module import Module


def load_ssl(finder: ModuleFinder, module: Module) -> None:  # noqa: ARG001
    """In Windows, the SSL module requires additional dlls to be present in the
    build directory. In other OS certificates are required.
    """
    if IS_WINDOWS:
        for dll_search in ["libcrypto-*.dll", "libssl-*.dll"]:
            libs_dir = Path(sys.base_prefix, "DLLs")
            for dll_path in libs_dir.glob(dll_search):
                finder.include_files(dll_path, Path("lib", dll_path.name))
