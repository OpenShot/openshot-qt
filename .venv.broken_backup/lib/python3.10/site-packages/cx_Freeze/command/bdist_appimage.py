"""Implements the 'bdist_appimage' command (create Linux AppImage format).

https://appimage.org/
https://docs.appimage.org/
https://docs.appimage.org/packaging-guide/manual.html#ref-manual
"""

from __future__ import annotations

import os
import platform
import shutil
import stat
from textwrap import dedent
from typing import ClassVar
from urllib.request import urlretrieve

from filelock import FileLock
from setuptools import Command

import cx_Freeze.icons
from cx_Freeze.exception import ExecError, PlatformError

__all__ = ["bdist_appimage"]

APPIMAGEKIT_URL = (
    "https://github.com/AppImage/AppImageKit/releases/download/continuous"
)
APPIMAGEKIT_TOOL = os.path.expanduser("~/.local/bin/appimagetool")


class bdist_appimage(Command):
    """Create a Linux AppImage."""

    description = "create a Linux AppImage"
    user_options: ClassVar[list[tuple[str, str | None, str]]] = [
        (
            "appimagekit=",
            None,
            f"path to AppImageKit [default: {APPIMAGEKIT_TOOL}]",
        ),
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
        (
            "skip-build",
            None,
            "skip rebuilding everything (for testing/debugging)",
        ),
        ("target-name=", None, "name of the file to create"),
        ("target-version=", None, "version of the file to create"),
        ("silent", "s", "suppress all output except warnings"),
    ]
    boolean_options: ClassVar[list[str]] = [
        "skip-build",
        "silent",
    ]

    def initialize_options(self) -> None:
        self.appimagekit = None
        self._appimage_extract_and_run = False

        self.bdist_base = None
        self.build_dir = None
        self.dist_dir = None
        self.skip_build = None

        self.target_name = None
        self.target_version = None
        self.fullname = None
        self.silent = None

    def finalize_options(self) -> None:
        if os.name != "posix":
            msg = (
                "don't know how to create AppImage "
                f"distributions on platform {os.name}"
            )
            raise PlatformError(msg)

        self.set_undefined_options("build_exe", ("build_exe", "build_dir"))
        self.set_undefined_options(
            "bdist",
            ("bdist_base", "bdist_base"),
            ("dist_dir", "dist_dir"),
            ("skip_build", "skip_build"),
        )

        if self.target_name is None:
            self.target_name = self.distribution.get_name()
        if self.target_version is None and self.distribution.metadata.version:
            self.target_version = self.distribution.metadata.version
        arch = platform.machine()
        name = self.target_name
        version = self.target_version or self.distribution.get_version()
        name, ext = os.path.splitext(name)
        if ext == ".AppImage":
            self.app_name = self.target_name
            self.fullname = name
        elif self.target_version:
            self.app_name = f"{name}-{version}-{arch}.AppImage"
            self.fullname = f"{name}-{version}"
        else:
            self.app_name = f"{name}-{arch}.AppImage"
            self.fullname = name

        if self.silent is not None:
            self.verbose = 0 if self.silent else 2

        # validate or download appimagekit
        self._get_appimagekit()

    def _get_appimagekit(self) -> None:
        """Fetch AppImageKit from the web if not available locally."""
        if self.appimagekit is None:
            self.appimagekit = APPIMAGEKIT_TOOL
        appimagekit = self.appimagekit
        appimagekit_dir = os.path.dirname(appimagekit)
        self.mkpath(appimagekit_dir)
        with FileLock(appimagekit + ".lock"):
            if not os.path.exists(appimagekit):
                self.announce(
                    f"download and install AppImageKit from {APPIMAGEKIT_URL}"
                )
                arch = platform.machine()
                name = f"appimagetool-{arch}.AppImage"
                filename = os.path.join(appimagekit_dir, name)
                if not os.path.exists(filename):
                    urlretrieve(  # noqa: S310
                        os.path.join(APPIMAGEKIT_URL, name), filename
                    )
                    os.chmod(filename, stat.S_IRWXU)
                if not os.path.exists(appimagekit):
                    self.execute(
                        os.symlink,
                        (filename, appimagekit),
                        msg=f"linking {appimagekit} -> {filename}",
                    )

            try:
                self.spawn([appimagekit, "--version"])
            except Exception:  # noqa: BLE001
                self._appimage_extract_and_run = True

    def run(self) -> None:
        # Create the application bundle
        if not self.skip_build:
            self.run_command("build_exe")

        # Make appimage (by default in dist directory)
        # Set the full path of appimage to be built
        self.mkpath(self.dist_dir)
        output = os.path.abspath(os.path.join(self.dist_dir, self.app_name))
        if os.path.exists(output):
            os.unlink(output)

        # Make AppDir folder
        appdir = os.path.join(self.bdist_base, "AppDir")
        if os.path.exists(appdir):
            self.execute(shutil.rmtree, (appdir,), msg=f"removing {appdir}")

        self.mkpath(appdir)
        share_icons = os.path.join("share", "icons")
        icons_dir = os.path.join(appdir, share_icons)
        self.mkpath(icons_dir)

        # Copy from build_exe
        self.copy_tree(self.build_dir, appdir, preserve_symlinks=True)

        # Add icon, desktop file, entrypoint
        executables = self.distribution.executables
        executable = executables[0]
        if len(executables) > 1:
            self.warn(
                "using the first executable as entrypoint: "
                f"{executable.target_name}"
            )
        if executable.icon is None:
            icon_name = "logox128.png"
            icon_source_dir = os.path.dirname(cx_Freeze.icons.__file__)
            self.copy_file(os.path.join(icon_source_dir, icon_name), icons_dir)
        else:
            icon_name = executable.icon.name
            self.move_file(os.path.join(appdir, icon_name), icons_dir)
        relative_reference = os.path.join(share_icons, icon_name)
        origin = os.path.join(appdir, ".DirIcon")
        self.execute(
            os.symlink,
            (relative_reference, origin),
            msg=f"linking {origin} -> {relative_reference}",
        )

        desktop_entry = f"""\
            [Desktop Entry]
            Type=Application
            Name={self.target_name}
            Exec={executable.target_name}
            Comment={self.distribution.get_description()}
            Icon=/{share_icons}/{os.path.splitext(icon_name)[0]}
            Categories=Development;
            Terminal=true
            X-AppImage-Arch={platform.machine()}
            X-AppImage-Name={self.target_name}
            X-AppImage-Version={self.target_version or ''}
        """
        self.save_as_file(
            dedent(desktop_entry),
            os.path.join(appdir, f"{self.target_name}.desktop"),
        )
        entrypoint = f"""\
            #! /bin/bash
            # If running from an extracted image, fix APPDIR
            if [ -z "$APPIMAGE" ]; then
                self="$(readlink -f -- $0)"
                export APPDIR="${{self%/*}}"
            fi
            # Call the application entry point
            "$APPDIR/{executable.target_name}" "$@"
        """
        self.save_as_file(
            dedent(entrypoint), os.path.join(appdir, "AppRun"), mode="x"
        )

        # Build an AppImage from an AppDir
        os.environ["ARCH"] = platform.machine()
        cmd = [self.appimagekit, "--no-appstream", appdir, output]
        if self._appimage_extract_and_run:
            cmd.insert(1, "--appimage-extract-and-run")
        with FileLock(self.appimagekit + ".lock"):
            self.spawn(cmd)
        if not os.path.exists(output):
            msg = "Could not build AppImage"
            raise ExecError(msg)

    def save_as_file(self, data, outfile, mode="r") -> tuple[str, int]:
        """Save an input data to a file respecting verbose, dry-run and force
        flags.
        """
        if not self.force and os.path.exists(outfile):
            if self.verbose >= 1:
                self.warn(f"not creating {outfile} (output exists)")
            return (outfile, 0)
        if self.verbose >= 1:
            self.announce(f"creating {outfile}")

        if self.dry_run:
            return (outfile, 1)

        if isinstance(data, str):
            data = data.encode()
        with open(outfile, "wb") as out:
            out.write(data)
        st_mode = stat.S_IRUSR
        if "w" in mode:
            st_mode = st_mode | stat.S_IWUSR
        if "x" in mode:
            st_mode = st_mode | stat.S_IXUSR
        os.chmod(outfile, st_mode)
        return (outfile, 1)
