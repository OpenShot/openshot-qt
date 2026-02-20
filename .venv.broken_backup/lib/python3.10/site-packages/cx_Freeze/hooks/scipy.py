"""A collection of functions which are triggered automatically by finder when
scipy package is included.
"""

from __future__ import annotations

import os
from importlib.machinery import EXTENSION_SUFFIXES
from typing import TYPE_CHECKING

from cx_Freeze._compat import IS_LINUX, IS_MACOS, IS_MINGW, IS_WINDOWS
from cx_Freeze.hooks._libs import replace_delvewheel_patch

if TYPE_CHECKING:
    from cx_Freeze.finder import ModuleFinder
    from cx_Freeze.module import Module


def load_scipy(finder: ModuleFinder, module: Module) -> None:
    """The scipy package.

    Supported pypi and conda-forge versions (lasted tested version is 1.11.2).
    """
    source_dir = module.file.parent.parent / f"{module.name}.libs"
    if source_dir.exists():  # scipy >= 1.9.2 (windows)
        finder.include_files(source_dir, f"lib/{source_dir.name}")
        replace_delvewheel_patch(module)
    finder.include_package("scipy.integrate")
    finder.include_package("scipy._lib")
    finder.include_package("scipy.misc")
    finder.include_package("scipy.optimize")


def load_scipy__distributor_init(finder: ModuleFinder, module: Module) -> None:
    """Fix the location of dependent files in Windows and macOS."""
    if IS_LINUX or IS_MINGW:
        return  # it is detected correctly.

    # patch the code when necessary
    code_string = module.file.read_text(encoding="utf_8")

    # installed from pypi, scipy < 1.9.2 (windows) or all versions (macOS)
    module_dir = module.file.parent
    libs_dir = module_dir.joinpath(".dylibs" if IS_MACOS else ".libs")
    if libs_dir.is_dir():
        # copy any file at site-packages/scipy/.libs
        finder.include_files(
            libs_dir, f"lib/scipy/{libs_dir.name}", copy_dependent_files=False
        )
        # do not check dependencies already handled
        extension = EXTENSION_SUFFIXES[0]
        for file in module_dir.rglob(f"*{extension}"):
            finder.exclude_dependent_files(file)

    if module.in_file_system == 0:
        code_string = code_string.replace(
            "__file__", "__file__.replace('library.zip/', '')"
        )
    module.code = compile(code_string, os.fspath(module.file), "exec")


def load_scipy_interpolate(
    finder: ModuleFinder,
    module: Module,  # noqa: ARG001
) -> None:
    """The scipy.interpolate must be loaded as a package."""
    finder.exclude_module("scipy.interpolate.tests")
    finder.include_package("scipy.interpolate")


def load_scipy_linalg(finder: ModuleFinder, module: Module) -> None:
    """The scipy.linalg module loads items within itself in a way that causes
    problems without the entire package being present.
    """
    module.global_names.add("norm")
    finder.include_package("scipy.linalg")


def load_scipy_linalg_interface_gen(_, module: Module) -> None:
    """The scipy.linalg.interface_gen module optionally imports the pre module;
    ignore the error if this module cannot be found.
    """
    module.ignore_names.add("pre")


def load_scipy_ndimage(
    finder: ModuleFinder,
    module: Module,  # noqa: ARG001
) -> None:
    """The scipy.ndimage must be loaded as a package."""
    finder.exclude_module("scipy.ndimage.tests")
    finder.include_package("scipy.ndimage")


def load_scipy_sparse(
    finder: ModuleFinder,
    module: Module,  # noqa: ARG001
) -> None:
    """The scipy.sparse must be loaded as a package."""
    finder.exclude_module("scipy.sparse.tests")
    finder.include_package("scipy.sparse")


def load_scipy_sparse_csgraph(
    finder: ModuleFinder,
    module: Module,  # noqa: ARG001
) -> None:
    """The scipy.sparse.csgraph must be loaded as a package."""
    finder.exclude_module("scipy.sparse.csgraph.tests")
    finder.include_package("scipy.sparse.csgraph")


def load_scipy_sparse_linalg__dsolve_linsolve(
    finder: ModuleFinder,  # noqa: ARG001
    module: Module,
) -> None:
    """The scipy.sparse.linalg._dsolve.linsolve optionally loads
    scikits.umfpack.
    """
    module.ignore_names.add("scikits.umfpack")


def load_scipy_spatial(
    finder: ModuleFinder,
    module: Module,  # noqa: ARG001
) -> None:
    """The scipy.spatial must be loaded as a package."""
    finder.include_package("scipy.spatial")
    finder.exclude_module("scipy.spatial.tests")
    if IS_WINDOWS or IS_MINGW:
        finder.exclude_module("scipy.spatial.cKDTree")


def load_scipy_spatial_transform(
    finder: ModuleFinder,
    module: Module,  # noqa: ARG001
) -> None:
    """The scipy.spatial.transform must be loaded as a package."""
    finder.include_package("scipy.spatial.transform")
    finder.exclude_module("scipy.spatial.transform.tests")


def load_scipy_special(
    finder: ModuleFinder,
    module: Module,  # noqa: ARG001
) -> None:
    """The scipy.special must be loaded as a package."""
    finder.exclude_module("scipy.special.tests")
    finder.include_package("scipy.special")
    finder.include_package("scipy.special._precompute")


def load_scipy_special__cephes(
    finder: ModuleFinder,  # noqa: ARG001
    module: Module,
) -> None:
    """The scipy.special._cephes is an extension module and the scipy module
    imports * from it in places; advertise the global names that are used
    in order to avoid spurious errors about missing modules.
    """
    module.global_names.add("gammaln")


def load_scipy_stats(
    finder: ModuleFinder,
    module: Module,  # noqa: ARG001
) -> None:
    """The scipy.stats must be loaded as a package."""
    finder.exclude_module("scipy.stats.tests")
    finder.include_package("scipy.stats")
