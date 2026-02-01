"""A collection of functions which are triggered automatically by finder when
setuptools package is included.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cx_Freeze.finder import ModuleFinder
    from cx_Freeze.module import Module

_setuptools_extern = [
    "setuptools.extern.jaraco.functools",
    "setuptools.extern.jaraco.text",
    "setuptools.extern.more_itertools",
    "setuptools.extern.ordered_set",
    "setuptools.extern.packaging",
    "setuptools.extern.packaging.markers",
    "setuptools.extern.packaging.requirements",
    "setuptools.extern.packaging.specifiers",
    "setuptools.extern.packaging.tags",
    "setuptools.extern.packaging.utils",
    "setuptools.extern.packaging.version",
    "setuptools.extern.platformdirs",
]


def load_setuptools(finder: ModuleFinder, module: Module) -> None:
    """The setuptools must load the _distutils and _vendor subpackage."""
    with contextlib.suppress(ImportError):
        finder.include_package(f"{module.name}._distutils")
    with contextlib.suppress(ImportError):
        finder.include_package(f"{module.name}._vendor")


def load_setuptools_command_build(_, module: Module) -> None:
    """Ignore optional modules."""
    module.ignore_names.add("typing_extensions")


def load_setuptools_command_build_ext(_, module: Module) -> None:
    """Ignore optional modules."""
    module.ignore_names.update(["Cython.Distutils.build_ext", "dl"])


def load_setuptools_command_easy_install(_, module: Module) -> None:
    """Ignore optional modules."""
    module.ignore_names.add("setuptools.extern.jaraco.text")


def load_setuptools_command_egg_info(_, module: Module) -> None:
    """Ignore optional modules."""
    module.ignore_names.update(
        ["setuptools.extern.jaraco.text", "setuptools.extern.packaging"]
    )


def load_setuptools_config_setupcfg(_, module: Module) -> None:
    """Ignore optional modules."""
    module.ignore_names.update(_setuptools_extern)


def load_setuptools_config__apply_pyprojecttoml(_, module: Module) -> None:
    """Ignore optional modules."""
    module.ignore_names.add("setuptools.extern.packaging.specifiers")


def load_setuptools_config_expand(_, module: Module) -> None:
    """Ignore optional modules."""
    module.ignore_names.add("setuptools.extern.more_itertools")


def load_setuptools_config_pyprojecttoml(_, module: Module) -> None:
    """Ignore optional modules."""
    module.ignore_names.update(
        ["setuptools.extern.more_itertools", "setuptools.extern.tomli"]
    )


def load_setuptools_config__validate_pyproject_formats(
    _, module: Module
) -> None:
    """Ignore optional modules."""
    module.ignore_names.update(
        ["packaging", "trove_classifiers", "typing_extensions"]
    )


def load_setuptools_depends(_, module: Module) -> None:
    """Ignore optional modules."""
    module.ignore_names.add("setuptools.extern.packaging")


def load_setuptools_dist(_, module: Module) -> None:
    """Ignore optional modules."""
    module.ignore_names.update(_setuptools_extern)


def load_setuptools__entry_points(_, module: Module) -> None:
    """Ignore optional modules."""
    module.ignore_names.update(_setuptools_extern)


def load_setuptools_extension(_, module: Module) -> None:
    """The setuptools.extension module optionally loads
    Pyrex.Distutils.build_ext but its absence is not considered an error.
    """
    module.ignore_names.add("Pyrex.Distutils.build_ext")


def load_setuptools__importlib(_, module: Module) -> None:
    """Ignore optional modules."""
    module.ignore_names.update(
        [
            "importlib_metadata",
            "setuptools.extern.importlib_metadata",
            "setuptools.extern.importlib_resources",
        ]
    )


def load_setuptools__itertools(_, module: Module) -> None:
    """Ignore optional modules."""
    module.ignore_names.add("setuptools.extern.more_itertools")


def load_setuptools__normalization(_, module: Module) -> None:
    """Ignore optional modules."""
    module.ignore_names.add("setuptools.extern.packaging")


def load_setuptools_monkey(
    finder: ModuleFinder,
    module: Module,  # noqa: ARG001
) -> None:
    """Add hidden module."""
    finder.include_module("setuptools.msvc")


def load_setuptools_package_index(_, module: Module) -> None:
    """Ignore optional modules."""
    module.ignore_names.add("setuptools.extern.more_itertools")


def load_setuptools__reqs(_, module: Module) -> None:
    """Ignore optional modules."""
    module.ignore_names.update(_setuptools_extern)


def load_setuptools_sandbox(_, module: Module) -> None:
    """Ignore optional modules."""
    module.ignore_names.add("org.python.modules.posix.PosixModule")


def load_setuptools__vendor_ordered_set(_, module: Module) -> None:
    """Ignore optional modules."""
    module.ignore_names.update(
        ["collections.MutableSet", "collections.Sequence"]
    )


def load_setuptools__vendor_jaraco_text(_, module: Module) -> None:
    """Ignore optional modules."""
    module.ignore_names.update(
        [
            "setuptools.extern.importlib_resources",
            "setuptools.extern.jaraco.context",
            "setuptools.extern.jaraco.functools",
        ]
    )


def load_setuptools__vendor_jaraco_functools(_, module: Module) -> None:
    """Ignore optional modules."""
    module.ignore_names.add("setuptools.extern.more_itertools")


def load_setuptools__vendor_packaging_metadata(_, module: Module) -> None:
    """Ignore optional modules."""
    module.ignore_names.add("typing_extensions")


def load_setuptools_wheel(_, module: Module) -> None:
    """Ignore optional modules."""
    module.ignore_names.update(_setuptools_extern)
