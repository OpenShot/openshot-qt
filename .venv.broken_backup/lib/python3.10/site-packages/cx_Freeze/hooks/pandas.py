"""A collection of functions which are triggered automatically by finder when
pandas package is included.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from cx_Freeze.hooks._libs import replace_delvewheel_patch

if TYPE_CHECKING:
    from cx_Freeze.finder import ModuleFinder
    from cx_Freeze.module import Module


def load_pandas(finder: ModuleFinder, module: Module) -> None:
    """The pandas package loads items within itself in a way that causes
    problems without libs and a number of subpackages being present.
    """
    source_dir = module.file.parent.parent / f"{module.name}.libs"
    if source_dir.exists():  # pandas >= 2.1.0
        finder.include_files(source_dir, f"lib/{source_dir.name}")
    replace_delvewheel_patch(module)
    finder.include_package("pandas._libs")
    finder.exclude_module("pandas.conftest")
    finder.exclude_module("pandas.tests")


def load_pandas_io_formats_style(_, module: Module) -> None:
    """Ignore optional modules in the pandas.io.formats.style module."""
    module.ignore_names.update(
        ["matplotlib", "matplotlib.colors", "matplotlib.pyplot"]
    )


def load_pandas__libs_testing(
    finder: ModuleFinder,
    module: Module,  # noqa: ARG001
) -> None:
    """Include module used by the pandas._libs.testing module."""
    finder.include_module("cmath")


def load_pandas_plotting__core(_, module: Module) -> None:
    """Ignore optional modules in the pandas.plotting._core module."""
    module.ignore_names.add("matplotlib.axes")


def load_pandas_plotting__misc(_, module: Module) -> None:
    """Ignore optional modules in the pandas.plotting._misc module."""
    module.ignore_names.update(
        [
            "matplotlib.axes",
            "matplotlib.colors",
            "matplotlib.figure",
            "matplotlib.table",
        ]
    )


def load_pandas__testing(_, module: Module) -> None:
    """Ignore optional modules in the pandas._testing module."""
    module.exclude_names.add("pytest")


def load_pandas__testing_asserters(_, module: Module) -> None:
    """Ignore optional modules in the pandas._testing.asserters module."""
    module.ignore_names.add("matplotlib.pyplot")


def load_pandas__testing__io(_, module: Module) -> None:
    """Ignore optional modules in the pandas._testing._io module."""
    module.exclude_names.add("pytest")
