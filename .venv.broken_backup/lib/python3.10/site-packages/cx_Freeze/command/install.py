"""Extends setuptools 'install' command."""

from __future__ import annotations

import contextlib
import sys
import warnings
from typing import ClassVar, ContextManager

from setuptools.command.install import install as _install

__all__ = ["Install"]


@contextlib.contextmanager
def suppress_known_deprecation() -> ContextManager:
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", "setup.py install is deprecated")
        yield


class Install(_install):
    """Install everything from build directory."""

    command_name = "install"
    user_options: ClassVar[list[tuple[str, str | None, str]]] = [
        *_install.user_options,
        ("install-exe=", None, "installation directory for executables"),
    ]

    def expand_dirs(self) -> None:
        super().expand_dirs()
        self._expand_attrs(["install_exe"])

    def get_sub_commands(self) -> list[str]:
        sub_commands = super().get_sub_commands()[:]
        if self.distribution.executables:
            sub_commands.remove("install_egg_info")
            sub_commands.remove("install_scripts")
            sub_commands.append("install_exe")
        return sub_commands

    def initialize_options(self) -> None:
        with suppress_known_deprecation():
            super().initialize_options()
        self.install_exe = None

    def finalize_options(self) -> None:
        if self.prefix is None and sys.platform == "win32":
            winreg = __import__("winreg")
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"Software\Microsoft\Windows\CurrentVersion",
            )
            prefix = str(winreg.QueryValueEx(key, "ProgramFilesDir")[0])
            metadata = self.distribution.metadata
            self.prefix = f"{prefix}\\{metadata.get_name()}"
        super().finalize_options()
        self.convert_paths("exe")
        if self.root is not None:
            self.change_roots("exe")

    def select_scheme(self, name) -> None:
        super().select_scheme(name)
        if self.install_exe is None:
            if sys.platform == "win32":
                self.install_exe = "$base"
            else:
                metadata = self.distribution.metadata
                dir_name = f"{metadata.get_name()}-{metadata.get_version()}"
                self.install_exe = f"$base/lib/{dir_name}"

    def run(self) -> None:
        # setuptools used inspect.currentframe(), this method needs to exist.
        super().run()
