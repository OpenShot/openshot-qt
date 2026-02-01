"""A collection of functions which are triggered automatically by finder when
Pillow (PIL) package is included.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from cx_Freeze._compat import IS_MACOS

if TYPE_CHECKING:
    from cx_Freeze.finder import ModuleFinder
    from cx_Freeze.module import Module


def load_pil(finder: ModuleFinder, module: Module) -> None:
    """The Pillow must be loaded as a package."""
    finder.include_package("PIL")

    # [macos] copy dependent files when using zip_include_packages
    if IS_MACOS:
        source_dir = module.file.parent / ".dylibs"
        if source_dir.exists() and module.in_file_system == 0:
            finder.include_files(source_dir, "lib/.dylibs")


def load_pil_fpximageplugin(_, module: Module) -> None:
    """Ignore optional modules."""
    module.ignore_names.add("olefile")


def load_pil_image(_, module: Module) -> None:
    """Ignore optional modules."""
    module.ignore_names.update({"cffi", "defusedxml.ElementTree"})


def load_pil_imageshow(_, module: Module) -> None:
    """Ignore optional modules."""
    module.ignore_names.add("IPython.display")


def load_pil_micimageplugin(_, module: Module) -> None:
    """Ignore optional modules."""
    module.ignore_names.add("olefile")


def load_pil_pyaccess(_, module: Module) -> None:
    """Ignore optional modules."""
    module.ignore_names.add("cffi")
