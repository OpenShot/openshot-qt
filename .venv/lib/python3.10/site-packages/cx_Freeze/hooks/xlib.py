"""A collection of functions which are triggered automatically by finder when
Xlib package is included.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cx_Freeze.finder import ModuleFinder
    from cx_Freeze.module import Module


def load_xlib_display(
    finder: ModuleFinder,
    module: Module,  # noqa: ARG001
) -> None:
    """The Xlib.display module implicitly loads a number of extension modules;
    make sure this happens.
    """
    finder.include_module("Xlib.ext.xtest")
    finder.include_module("Xlib.ext.shape")
    finder.include_module("Xlib.ext.xinerama")
    finder.include_module("Xlib.ext.record")
    finder.include_module("Xlib.ext.composite")
    finder.include_module("Xlib.ext.randr")


def load_xlib_support_connect(
    finder: ModuleFinder,
    module: Module,  # noqa: ARG001
) -> None:
    """The Xlib.support.connect module implicitly loads a platform specific
    module; make sure this happens.
    """
    if sys.platform.split("-", maxsplit=1)[0] == "OpenVMS":
        module_name = "vms_connect"
    else:
        module_name = "unix_connect"
    finder.include_module(f"Xlib.support.{module_name}")


def load_xlib_xk(finder: ModuleFinder, module: Module) -> None:  # noqa: ARG001
    """The Xlib.XK module implicitly loads some keysymdef modules; make sure
    this happens.
    """
    finder.include_module("Xlib.keysymdef.miscellany")
    finder.include_module("Xlib.keysymdef.latin1")
