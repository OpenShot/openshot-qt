"""A collection of functions which are triggered automatically by finder when
numpy package is included.
"""

from __future__ import annotations

import json
import os
import sys
from importlib.machinery import EXTENSION_SUFFIXES
from pathlib import Path
from textwrap import dedent
from typing import TYPE_CHECKING

from cx_Freeze._compat import (
    IS_CONDA,
    IS_LINUX,
    IS_MACOS,
    IS_MINGW,
    IS_WINDOWS,
)
from cx_Freeze.hooks._libs import replace_delvewheel_patch

if TYPE_CHECKING:
    from cx_Freeze.finder import ModuleFinder
    from cx_Freeze.module import Module

# The sample/pandas is used to test.
# Using pip (pip install numpy) in Windows/Linux/macOS from pypi (w/ OpenBLAS)
# And using cgohlke/numpy-mkl.whl, numpy 1.23.5+mkl in windows:
# https://github.com/cgohlke/numpy-mkl.whl/releases/download/v2023.1.4/numpy-1.23.5+mkl-cp311-cp311-win_amd64.whl
#
# Read the numpy documentation, especially if using conda-forge and MKL:
# https://numpy.org/install/#numpy-packages--accelerated-linear-algebra-libraries
#
# For conda-forge we can use the default installation with MKL:
# conda install -c conda-forge numpy
# Or use OpenBLAS:
# conda install -c conda-forge blas=*=openblas numpy


def load_numpy(finder: ModuleFinder, module: Module) -> None:
    """The numpy package.

    Supported pypi and conda-forge versions (tested from 1.21.2 to 1.26.4).
    """
    source_dir = module.file.parent.parent / f"{module.name}.libs"
    if source_dir.exists():  # numpy >= 1.26.0
        finder.include_files(source_dir, f"lib/{source_dir.name}")
        replace_delvewheel_patch(module)

    # Exclude all tests and unnecessary modules.
    for mod in [
        "array_api.tests",
        "conftest",
        "compat.tests",
        "core.tests",
        "distutils",
        "distutils.tests",
        "f2py.tests",
        "fft.tests",
        "lib.tests",
        "linalg.tests",
        "ma.tests",
        "matrixlib.tests",
        "polynomial.tests",
        "_pyinstaller",
        "random._examples",
        "random.tests",
        "testing.tests",
        "tests",
        "typing.tests",
    ]:
        finder.exclude_module(f"numpy.{mod}")
    # Include dynamically loaded module
    finder.include_package("numpy.core")  # numpy.core._dtype_ctypes
    finder.include_module("numpy.lib.format")
    finder.include_module("numpy.polynomial")
    finder.include_module("secrets")


def load_numpy_core__add_newdocs(
    finder: ModuleFinder,
    module: Module,  # noqa: ARG001
) -> None:
    """Include module used by the numpy.core._add_newdocs module."""
    finder.include_module("numpy.core._multiarray_tests")


def load_numpy__distributor_init(finder: ModuleFinder, module: Module) -> None:
    """Fix the location of dependent files in Windows and macOS."""
    if IS_LINUX or IS_MINGW:
        return  # it is detected correctly.

    # patch the code when necessary
    code_string = module.file.read_text(encoding="utf_8")

    module_dir = module.file.parent
    exclude_dependent_files = False
    if (IS_MACOS or IS_WINDOWS) and not IS_CONDA:
        version = float(module.parent.distribution.version.rpartition(".")[0])
        if version >= 1.26:
            return  # for numpy >= 1.26.0 is handled in top module
        # numpy < 1.26.0 pypi
        libs_dir = module_dir.joinpath(".dylibs" if IS_MACOS else ".libs")
        if libs_dir.is_dir():
            # copy any file at site-packages/numpy/.libs
            target_dir = f"lib/numpy/{libs_dir.name}"
            finder.include_files(
                libs_dir, target_dir, copy_dependent_files=False
            )
            exclude_dependent_files = True

        # cgohlke/numpy-mkl.whl, numpy 1.23.5+mkl
        libs_dir = module_dir / "DLLs"
        if libs_dir.is_dir():
            finder.exclude_module("numpy.DLLs")
            finder.include_files(
                libs_dir, "lib/numpy/DLLs", copy_dependent_files=False
            )
            exclude_dependent_files = True

    elif IS_CONDA:  # conda-forge
        prefix = Path(sys.prefix)
        conda_meta = prefix / "conda-meta"
        packages = ["libblas", "libcblas", "liblapack"]
        blas_options = ["libopenblas", "mkl"]
        packages += blas_options
        files_to_copy: list[Path] = []
        blas = None
        for package in packages:
            try:
                pkg = next(conda_meta.glob(f"{package}-*.json"))
            except StopIteration:
                continue
            files = json.loads(pkg.read_text(encoding="utf_8"))["files"]
            files_to_copy += [
                prefix / file
                for file in files
                if file.lower().endswith(".dll")
            ]
            blas = package
        for source in files_to_copy:
            finder.include_files(source, f"lib/{blas}/{source.name}")
        numpy_blas = f"""
            def init_numpy_blas():
                import os

                blas_path = os.path.join(
                    os.path.dirname(os.path.dirname(__file__)), "{blas}"
                )
                try:
                    os.add_dll_directory(blas_path)
                except (OSError, AttributeError):
                    pass
                env_path = os.environ.get("PATH", "").split(os.pathsep)
                if blas_path not in env_path:
                    env_path.insert(0, blas_path)
                    os.environ["PATH"] = os.pathsep.join(env_path)

            init_numpy_blas()
            """
        code_string += dedent(numpy_blas)
        exclude_dependent_files = True

    # do not check dependencies already handled
    if exclude_dependent_files:
        extension = EXTENSION_SUFFIXES[0]
        for file in module_dir.rglob(f"*{extension}"):
            finder.exclude_dependent_files(file)

    if module.in_file_system == 0:
        code_string = code_string.replace(
            "__file__", "__file__.replace('library.zip/', '')"
        )
    module.code = compile(code_string, os.fspath(module.file), "exec")


def load_numpy_core_numerictypes(_, module: Module) -> None:
    """The numpy.core.numerictypes module adds a number of items to itself
    dynamically; define these to avoid spurious errors about missing
    modules.
    """
    module.global_names.update(
        [
            "bool_",
            "cdouble",
            "complexfloating",
            "csingle",
            "double",
            "float64",
            "float_",
            "inexact",
            "intc",
            "int32",
            "number",
            "single",
        ]
    )


def load_numpy_distutils_command_scons(_, module: Module) -> None:
    """The numpy.distutils.command.scons module optionally imports the numscons
    module; ignore the error if the module cannot be found.
    """
    module.ignore_names.add("numscons")


def load_numpy_distutils_misc_util(_, module: Module) -> None:
    """The numpy.distutils.misc_util module optionally imports the numscons
    module; ignore the error if the module cannot be found.
    """
    module.ignore_names.add("numscons")


def load_numpy_distutils_system_info(_, module: Module) -> None:
    """The numpy.distutils.system_info module optionally imports the Numeric
    module; ignore the error if the module cannot be found.
    """
    module.ignore_names.add("Numeric")


def load_numpy_f2py___version__(_, module: Module) -> None:
    """The numpy.f2py.__version__ module optionally imports the __svn_version__
    module; ignore the error if the module cannot be found.
    """
    module.ignore_names.add("__svn_version__")


def load_numpy_linalg(
    finder: ModuleFinder,
    module: Module,  # noqa: ARG001
) -> None:
    """The numpy.linalg module implicitly loads the lapack_lite module; make
    sure this happens.
    """
    finder.include_module("numpy.linalg.lapack_lite")


def load_numpy__pytesttester(_, module: Module) -> None:
    """Remove optional modules in the numpy._pytesttester module."""
    module.exclude_names.add("pytest")


def load_numpy_random_mtrand(_, module: Module) -> None:
    """The numpy.random.mtrand module is an extension module and the numpy
    module imports * from this module; define the list of global names
    available to this module in order to avoid spurious errors about missing
    modules.
    """
    module.global_names.update(["rand", "randn"])
