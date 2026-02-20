"""A collection of functions which are triggered automatically by finder when
importlib namespace is included.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from cx_Freeze._compat import IS_WINDOWS

if TYPE_CHECKING:
    from cx_Freeze.finder import ModuleFinder
    from cx_Freeze.module import Module


def load_importlib(_, module: Module) -> None:
    """The module shouldn't import internal names."""
    module.exclude_names.add("_frozen_importlib")
    module.exclude_names.add("_frozen_importlib_external")


def load_importlib_abc(_, module: Module) -> None:
    """The module shouldn't import internal names."""
    module.exclude_names.add("_frozen_importlib")
    module.exclude_names.add("_frozen_importlib_external")


def load_importlib__bootstrap(_, module: Module) -> None:
    """The module shouldn't import internal names."""
    module.exclude_names.add("_frozen_importlib_external")


def load_importlib__bootstrap_external(_, module: Module) -> None:
    """Ignore modules not found in current OS."""
    if IS_WINDOWS:
        module.exclude_names.add("posix")
    else:
        module.exclude_names.update(("nt", "winreg"))


def load_importlib_metadata(finder: ModuleFinder, module: Module) -> None:
    """The importlib.metadata module should filter import names."""
    if module.name == "importlib.metadata":
        module.exclude_names.add("pep517")
        finder.include_module("email")
