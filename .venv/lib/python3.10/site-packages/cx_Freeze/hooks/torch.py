"""A collection of functions which are triggered automatically by finder when
PyTorch package is included.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cx_Freeze.finder import ModuleFinder
    from cx_Freeze.module import Module

# 1) Test in Windows from pypi
# pip install torch
#
# 2) Test in Windows from pytorch
# # https://pytorch.org/get-started/locally/
#
# 3) Test in Linux from pypi includes nvidia packages
# pip install torch


def load_torch(finder: ModuleFinder, module: Module) -> None:
    """Hook for PyTorch. Tested in Windows and Linux."""
    module_path = module.file.parent
    site_packages_path = module_path.parent

    # Activate an optimized mode when torch is in zip_include_packages
    if module.in_file_system == 0:
        module.in_file_system = 2
    # patch the code to ignore CUDA_PATH_Vxx_x installation directory
    code_string = module.file.read_text(encoding="utf_8")
    code_string = code_string.replace("CUDA_PATH", "NO_CUDA_PATH")
    module.code = compile(code_string, module.file.as_posix(), "exec")
    # include the binaries (torch 2.1+)
    source_bin = module.file.parent / "bin"
    if source_bin.exists():
        finder.include_files(source_bin, f"lib/{module.name}/bin")
    # include the shared libraries in 'lib' to avoid searching through the
    # system.
    source_lib = module.file.parent / "lib"
    if source_lib.exists():
        finder.include_files(source_lib, f"lib/{module.name}/lib")
    # hidden modules
    finder.include_module("torch._C")
    finder.include_module("torch._VF")
    finder.include_package("torch.distributions")
    finder.include_package("torch.testing")
    # exclude C files
    finder.exclude_module("torch.include")
    finder.exclude_module("torch.share")
    finder.exclude_module("torchgen.packaged.ATen.templates")
    # torch 2.2
    finder.include_module("torch.return_types")
    for config_file in (
        "_dynamo/config.py",
        "_functorch/config.py",
        "_inductor/config.py",
        "_lazy/config.py",
        "distributed/_spmd/config.py",
        "fx/config.py",
        "fx/experimental/_config.py",
    ):
        config = module.file.parent / config_file
        if config.exists():
            finder.include_files(config, f"lib/{module.name}/{config_file}")
    # include source files for torch.jit._overload
    source_path = site_packages_path / "torch/ao"
    for source in source_path.rglob("*.py"):  # type: Path
        target = "lib" / source.relative_to(site_packages_path)
        finder.include_files(source, target)
    source_path = site_packages_path / "torch/nn"
    for source in source_path.rglob("*.py"):  # type: Path
        target = "lib" / source.relative_to(site_packages_path)
        finder.include_files(source, target)
    source = site_packages_path / "torch/functional.py"
    target = "lib" / source.relative_to(site_packages_path)
    finder.include_files(source, target)


def load_torch__dynamo_skipfiles(_, module: Module) -> None:
    """Patch to work with Python 3.11+."""
    code_string = module.file.read_text(encoding="utf_8")
    code_string = code_string.replace(
        "return _strip_init_py(m.__file__)",
        'return _strip_init_py(getattr(m, "__file__", ""))',
    )
    module.code = compile(code_string, os.fspath(module.file), "exec")
