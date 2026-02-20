"""A collection of functions which are triggered automatically by finder when
backports namespace is included.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from cx_Freeze.hooks.zoneinfo import load_zoneinfo

if TYPE_CHECKING:
    from cx_Freeze.finder import ModuleFinder
    from cx_Freeze.module import Module


def load_backports_zoneinfo(finder: ModuleFinder, module: Module) -> None:
    """The backports.zoneinfo module should be a drop-in replacement for the
    Python 3.9 standard library module zoneinfo.
    """
    load_zoneinfo(finder, module)


def load_backports_zoneinfo__common(_, module: Module) -> None:
    """Ignore module not used in Python 3.8."""
    module.ignore_names.add("importlib_resources")


def load_backports_zoneinfo__tzpath(_, module: Module) -> None:
    """Ignore module not used in Python 3.8."""
    module.ignore_names.add("importlib_resources")


__all__ = [
    "load_backports_zoneinfo",
    "load_backports_zoneinfo__common",
    "load_backports_zoneinfo__tzpath",
]
