"""A collection of functions which are triggered automatically by finder when
tensorflow package is included.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from cx_Freeze._compat import IS_MINGW, IS_WINDOWS

if TYPE_CHECKING:
    from cx_Freeze.finder import ModuleFinder
    from cx_Freeze.module import Module


def load_tensorflow(finder: ModuleFinder, module: Module) -> None:
    """Hook for tensorflow. Tested in Windows and Linux."""
    module_path = module.file.parent
    site_packages_path = module_path.parent

    # implicitly loaded packages
    finder.include_package("tensorboard")
    finder.include_package("tensorflow.compiler")
    finder.include_package("tensorflow.python")

    # support for plugins
    source_path = site_packages_path / "tensorflow-plugins"
    if source_path.is_dir():
        pattern = "*.dll" if (IS_WINDOWS or IS_MINGW) else "*.so"
        for source in source_path.rglob(pattern):  # type: Path
            target = "lib" / source.relative_to(site_packages_path)
            finder.include_files(source, target)

    # patch the code to search the correct directory
    code_string = module.file.read_text(encoding="utf_8")
    code_string = code_string.replace(
        "_site_packages_dirs = []",
        "_site_packages_dirs = [_os.path.join(_sys.frozen_dir,'lib')]",
    )
    code_string = code_string.replace(
        "_current_file_location = ",
        "_current_file_location = __file__.replace('library.zip/', '')  #",
    )
    module.code = compile(code_string, os.fspath(module.file), "exec")

    # installed version of tensorflow is a variant?
    if module.distribution is None:
        for name in (
            "tensorflow-aarch64",
            "tensorflow-cpu",
            "tensorflow-cpu-aws",
            "tensorflow-gpu",
            "tensorflow-intel",
            "tensorflow-macos",
            "tensorflow-rocm",
        ):
            module.update_distribution(name)
            if module.distribution is not None:
                break

    # remove run-time warning
    # WARNING:tensorflow:AutoGraph is not available in this environment: ...
    source_path = site_packages_path / "tensorflow/python/autograph"
    for source in source_path.rglob("*.py"):  # type: Path
        target = "lib" / source.relative_to(site_packages_path)
        finder.include_files(source, target)
    finder.exclude_module("tensorflow.python.autograph")
