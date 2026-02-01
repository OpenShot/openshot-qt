"""A collection of functions which are triggered automatically by finder when
TKinter package is included.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

from cx_Freeze._compat import IS_WINDOWS
from cx_Freeze.common import get_resource_file_path

if TYPE_CHECKING:
    from cx_Freeze.finder import ModuleFinder
    from cx_Freeze.module import Module


def load_tkinter(finder: ModuleFinder, module: Module) -> None:
    """The tkinter module has data files (also called tcl/tk libraries) that
    are required to be loaded at runtime.
    """
    folders = {}
    share = get_resource_file_path("bases", "share", "")
    if share and share.is_dir():
        # manylinux wheels and macpython wheels store tcl/tk libraries
        folders["TCL_LIBRARY"] = next(share.glob("tcl*.*"))
        folders["TK_LIBRARY"] = next(share.glob("tk*.*"))
    else:
        # Windows, MSYS2, Miniconda: collect the tcl/tk libraries
        try:
            tkinter = __import__(module.name)
        except (ImportError, AttributeError):
            return
        root = tkinter.Tk(useTk=False)
        source_path = Path(root.tk.exprstring("$tcl_library"))
        folders["TCL_LIBRARY"] = source_path
        source_name = source_path.name.replace("tcl", "tk")
        source_path = source_path.parent / source_name
        folders["TK_LIBRARY"] = source_path
    for env_name, source_path in folders.items():
        target_path = f"share/{source_path.name}"
        finder.add_constant(env_name, target_path)
        finder.include_files(source_path, target_path)
        if env_name == "TCL_LIBRARY":
            tcl8_path = source_path.parent / source_path.stem
            if tcl8_path.is_dir():
                finder.include_files(tcl8_path, f"share/{tcl8_path.name}")
        if IS_WINDOWS:
            dll_name = source_path.name.replace(".", "") + "t.dll"
            dll_path = Path(sys.base_prefix, "DLLs", dll_name)
            if not dll_path.exists():
                continue
            finder.include_files(dll_path, f"lib/{dll_name}")
