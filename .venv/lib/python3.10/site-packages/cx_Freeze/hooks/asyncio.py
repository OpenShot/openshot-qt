"""A collection of functions which are triggered automatically by finder when
asyncio package is included.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from cx_Freeze._compat import IS_WINDOWS

if TYPE_CHECKING:
    from cx_Freeze.finder import ModuleFinder
    from cx_Freeze.module import Module


def load_asyncio(finder: ModuleFinder, module: Module) -> None:  # noqa: ARG001
    """The asyncio must be loaded as a package."""
    finder.include_package("asyncio")


def load_asyncio_windows_events(_, module: Module) -> None:
    """Ignore modules not found in current OS."""
    if not IS_WINDOWS:
        module.exclude_names.update({"_overlapped", "_winapi", "msvcrt"})


def load_asyncio_windows_utils(_, module: Module) -> None:
    """Ignore modules not found in current OS."""
    if not IS_WINDOWS:
        module.exclude_names.update({"_winapi", "msvcrt"})
