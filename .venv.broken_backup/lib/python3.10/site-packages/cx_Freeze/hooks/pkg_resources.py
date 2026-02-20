"""A collection of functions which are triggered automatically by finder when
pkg_resources package is included.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cx_Freeze.finder import ModuleFinder
    from cx_Freeze.module import Module


def load_pkg_resources(finder: ModuleFinder, module: Module) -> None:
    """The pkg_resources must load the _vendor subpackage."""
    finder.exclude_module("pkg_resources._vendor.platformdirs.__main__")
    finder.include_package("pkg_resources._vendor")
    module.ignore_names.update(
        [
            "__main__",
            "pkg_resources.extern.jaraco.text",
            "pkg_resources.extern.packaging",
            "pkg_resources.extern.packaging.markers",
            "pkg_resources.extern.packaging.requirements",
            "pkg_resources.extern.packaging.specifiers",
            "pkg_resources.extern.packaging.utils",
            "pkg_resources.extern.packaging.version",
            "pkg_resources.extern.platformdirs",
        ]
    )


def load_pkg_resources__vendor_jaraco_text(_, module: Module) -> None:
    """Ignore optional modules."""
    module.ignore_names.update(
        [
            "pkg_resources.extern.importlib_resources",
            "pkg_resources.extern.jaraco.context",
            "pkg_resources.extern.jaraco.functools",
        ]
    )


def load_pkg_resources__vendor_jaraco_functools(_, module: Module) -> None:
    """Ignore optional modules."""
    module.ignore_names.add("pkg_resources.extern.more_itertools")


def load_pkg_resources__vendor_packaging_metadata(_, module: Module) -> None:
    """Ignore optional modules_."""
    module.ignore_names.add("typing_extensions")
