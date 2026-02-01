"""A collection of functions which are triggered automatically by finder when
pycryptodomex package is included.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from cx_Freeze.common import code_object_replace_function
from cx_Freeze.module import Module, ModuleHook

if TYPE_CHECKING:
    from cx_Freeze.finder import ModuleFinder


class Hook(ModuleHook):
    """The Module Hook class."""

    def cryptodome_cipher(self, finder: ModuleFinder, module: Module) -> None:
        """The Crypto.Cipher subpackage of pycryptodome package."""
        if module.in_file_system == 0:
            finder.include_package(module.name)

    def cryptodome_hash(self, finder: ModuleFinder, module: Module) -> None:
        """The Crypto.Hash subpackage of pycryptodome package."""
        if module.in_file_system == 0:
            finder.include_package(module.name)

    def cryptodome_math(self, finder: ModuleFinder, module: Module) -> None:
        """The Crypto.Math subpackage of pycryptodome package."""
        if module.in_file_system == 0:
            finder.include_package(module.name)

    def cryptodome_protocol(
        self, finder: ModuleFinder, module: Module
    ) -> None:
        """The Crypto.Protocol subpackage of pycryptodome package."""
        if module.in_file_system == 0:
            finder.include_package(module.name)

    def cryptodome_publickey(
        self, finder: ModuleFinder, module: Module
    ) -> None:
        """The Crypto.PublicKey subpackage of pycryptodome package."""
        if module.in_file_system == 0:
            finder.include_package(module.name)

    def cryptodome_util(self, finder: ModuleFinder, module: Module) -> None:
        """The Crypto.Util subpackage of pycryptodome package."""
        if module.in_file_system == 0:
            finder.include_package(module.name)

    def cryptodome_util__file_system(self, _, module: Module) -> None:
        """The patch for pycryptodome package."""
        code = module.code
        if module.in_file_system == 0 and code is not None:
            name = "pycryptodome_filename"
            source = f"""\
            def {name}(dir_comps, filename):
                import os, sys
                modulename = "{self.module.name}"
                if dir_comps[0] != modulename:
                    raise ValueError(
                        "Only available for modules under '" + modulename + "'"
                    )
                dir_comps = list(dir_comps) + [filename]
                root_lib = os.path.join(sys.frozen_dir, "lib")
                return os.path.join(root_lib, ".".join(dir_comps))
            """
            module.code = code_object_replace_function(code, name, source)


__all__ = ["Hook"]
