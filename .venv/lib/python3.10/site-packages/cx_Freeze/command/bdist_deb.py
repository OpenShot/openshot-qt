"""Implements the 'bdist_deb' command (create DEB binary distributions).

This is a simple wrapper around 'alien' that converts a rpm to deb.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from typing import ClassVar

from setuptools import Command

from cx_Freeze.command.bdist_rpm import bdist_rpm
from cx_Freeze.exception import ExecError, PlatformError

__all__ = ["bdist_deb"]


class bdist_deb(Command):
    """Create an DEB distribution."""

    description = "create an DEB distribution"

    user_options: ClassVar[list[tuple[str, str | None, str]]] = [
        (
            "bdist-base=",
            None,
            "base directory for creating built distributions",
        ),
        (
            "build-dir=",
            "b",
            "directory of built executables and dependent files",
        ),
        ("dist-dir=", "d", "directory to put final built distributions in"),
    ]

    def initialize_options(self) -> None:
        self.bdist_base = None
        self.build_dir = None
        self.dist_dir = None

    def finalize_options(self) -> None:
        if os.name != "posix":
            msg = (
                "don't know how to create DEB "
                f"distributions on platform {os.name}"
            )
            raise PlatformError(msg)
        if not shutil.which("alien"):
            msg = "failed to find 'alien' for this platform."
            raise PlatformError(msg)
        if os.getuid() != 0 and not shutil.which("fakeroot"):
            msg = "failed to find 'fakeroot' for this platform."
            raise PlatformError(msg)

        self.set_undefined_options("bdist", ("bdist_base", "bdist_base"))
        self.set_undefined_options(
            "bdist",
            ("bdist_base", "bdist_base"),
            ("dist_dir", "dist_dir"),
        )

    def run(self) -> None:
        # make a binary RPM to convert
        cmd_rpm = bdist_rpm(
            self.distribution,
            bdist_base=self.bdist_base,
            dist_dir=self.dist_dir,
        )
        cmd_rpm.ensure_finalized()
        if not self.dry_run:
            cmd_rpm.run()
            rpm_filename = None
            for command, _, filename in self.distribution.dist_files:
                if command == "bdist_rpm":
                    rpm_filename = filename
                    break
            if rpm_filename is None:
                msg = "could not build rpm"
                raise ExecError(msg)
        else:
            rpm_filename = "filename.rpm"

        # convert rpm to deb (by default in dist directory)
        logging.info("building DEB")
        cmd = ["alien", "--to-deb", os.path.basename(rpm_filename)]
        if os.getuid() != 0:
            cmd.insert(0, "fakeroot")
        if self.dry_run:
            self.spawn(cmd)
        else:
            logging.info(subprocess.list2cmdline(cmd))
            output = subprocess.check_output(cmd, text=True, cwd=self.dist_dir)
            logging.info(output)
            filename = output.splitlines()[0].split()[0]
            filename = os.path.join(self.dist_dir, filename)
            if not os.path.exists(filename):
                msg = "could not build deb"
                raise ExecError(msg)
            self.distribution.dist_files.append(("bdist_deb", "any", filename))
