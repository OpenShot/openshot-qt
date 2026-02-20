"""A collection of functions which are triggered automatically by finder when
torchvision package is included.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cx_Freeze.finder import ModuleFinder
    from cx_Freeze.module import Module


def load_torchvision(finder: ModuleFinder, module: Module) -> None:
    """Hook for torchvision."""
    module_path = module.file.parent
    site_packages_path = module_path.parent

    # include source of torchvision.models
    source_path = site_packages_path / "torchvision/models"
    for source in source_path.rglob("*.py"):  # type: Path
        target = "lib" / source.relative_to(site_packages_path)
        finder.include_files(source, target)
