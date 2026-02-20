"""Implements the 'install_exe' command."""

from __future__ import annotations

import os
import shutil
import sys
from typing import ClassVar

from setuptools import Command

__all__ = ["install_exe"]


class install_exe(Command):
    """Install executables built from Python scripts."""

    command_name = "install_exe"
    description = "install executables built from Python scripts"
    user_options: ClassVar[list[tuple[str, str | None, str]]] = [
        ("install-dir=", "d", "directory to install executables to"),
        ("build-dir=", "b", "build directory (where to install from)"),
        ("force", "f", "force installation (overwrite existing files)"),
        ("skip-build", None, "skip the build steps"),
    ]

    def initialize_options(self) -> None:
        self.install_dir: str | None = None
        self.force = 0
        self.build_dir = None
        self.skip_build = None
        self.outfiles = None

    def finalize_options(self) -> None:
        self.set_undefined_options("build_exe", ("build_exe", "build_dir"))
        self.set_undefined_options(
            "install",
            ("install_exe", "install_dir"),
            ("force", "force"),
            ("skip_build", "skip_build"),
        )

    def run(self) -> None:
        if not self.skip_build:
            self.run_command("build_exe")

        self.mkpath(self.install_dir)
        self.outfiles = self.copy_tree(self.build_dir, self.install_dir)

        if sys.platform == "win32":
            return

        # in posix, make symlinks to the executables
        install_dir = self.install_dir
        bin_dir = os.path.join(
            os.path.dirname(os.path.dirname(install_dir)), "bin"
        )
        self.execute(shutil.rmtree, (bin_dir, True), msg=f"removing {bin_dir}")
        self.mkpath(bin_dir)
        for executable in self.get_inputs():
            name = executable.target_name
            target = os.path.join(install_dir, name)
            origin = os.path.join(bin_dir, name)
            relative_reference = os.path.relpath(target, bin_dir)
            self.execute(
                os.symlink,
                (relative_reference, origin, True),
                msg=f"linking {origin} -> {relative_reference}",
            )
            self.outfiles.append(origin)

    def get_inputs(self) -> list[str]:
        return self.distribution.executables or []

    def get_outputs(self) -> list[str]:
        return self.outfiles or []
