"""A collection of functions which are triggered automatically by finder when
tiktoken package is included.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cx_Freeze.finder import ModuleFinder
    from cx_Freeze.module import Module


def load_tiktoken(
    finder: ModuleFinder,
    module: Module,  # noqa: ARG001
) -> None:
    """The tiktoken must include extension."""
    finder.include_module("tiktoken_ext.openai_public")
