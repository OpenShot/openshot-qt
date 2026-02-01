"""A collection of functions which are triggered automatically by finder when
yt_dlp package is included.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cx_Freeze.finder import ModuleFinder
    from cx_Freeze.module import Module


def load_yt_dlp(finder: ModuleFinder, module: Module) -> None:  # noqa: ARG001
    """The yt_dlp must include backends."""
    finder.include_module("yt_dlp.compat._deprecated")
    finder.include_module("yt_dlp.compat._legacy")
    finder.include_module("yt_dlp.utils._deprecated")
    finder.include_module("yt_dlp.utils._legacy")
