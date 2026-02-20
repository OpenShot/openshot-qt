"""A collection of functions which are triggered automatically by finder when
easyocr package is included.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cx_Freeze.finder import ModuleFinder
    from cx_Freeze.module import Module


def load_easyocr(finder: ModuleFinder, module: Module) -> None:  # noqa: ARG001
    """The easyocr package."""
    finder.include_module("easyocr.easyocr")
    finder.include_module("easyocr.model.vgg_model")
    finder.include_module("imageio.plugins.pillow")


def load_easyocr_easyocr(_, module: Module) -> None:
    """Ignore optional modules."""
    module.ignore_names.update(["six", "pathlib2"])
