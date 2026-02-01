"""Implements the 'bdist_rpm' command (create RPM binary distributions).

Borrowed from distutils.command.bdist_rpm of Python 3.10 and merged with
bdist_rpm subclass of cx_Freeze 6.10.
"""

from __future__ import annotations

import logging
import os
import platform
import shutil
import sys
import tarfile
from subprocess import CalledProcessError, check_output
from sysconfig import get_python_version
from typing import ClassVar

from setuptools import Command

from cx_Freeze.exception import (
    ExecError,
    FileError,
    OptionError,
    PlatformError,
)

__all__ = ["bdist_rpm"]


class bdist_rpm(Command):
    """Create an RPM distribution."""

    description = "create an RPM distribution"

    user_options: ClassVar[list[tuple[str, str | None, str]]] = [
        (
            "bdist-base=",
            None,
            "base directory for creating built distributions",
        ),
        (
            "rpm-base=",
            None,
            'base directory for creating RPMs (defaults to "rpm" under '
            "--bdist-base; must be specified for RPM 2)",
        ),
        (
            "dist-dir=",
            "d",
            "directory to put final RPM files in "
            "(and .spec files if --spec-only)",
        ),
        ("spec-only", None, "only regenerate spec file"),
        # More meta-data: too RPM-specific to put in the setup script,
        # but needs to go in the .spec file -- so we make these options
        # to "bdist_rpm".  The idea is that packagers would put this
        # info in setup.cfg, although they are of course free to
        # supply it on the command line.
        (
            "distribution-name=",
            None,
            "name of the (Linux) distribution to which this "
            "RPM applies (*not* the name of the module distribution!)",
        ),
        (
            "group=",
            None,
            'package classification [default: "Development/Libraries"]',
        ),
        ("release=", None, "RPM release number"),
        ("serial=", None, "RPM serial number"),
        (
            "vendor=",
            None,
            'RPM "vendor" (eg. "Joe Blow <joe@example.com>") '
            "[default: maintainer or author from setup script]",
        ),
        (
            "packager=",
            None,
            'RPM packager (eg. "Jane Doe <jane@example.net>") '
            "[default: vendor]",
        ),
        (
            "doc-files=",
            None,
            "list of documentation files (space or comma-separated)",
        ),
        ("changelog=", None, "RPM changelog"),
        ("icon=", None, "name of icon file"),
        ("provides=", None, "capabilities provided by this package"),
        ("requires=", None, "capabilities required by this package"),
        ("conflicts=", None, "capabilities which conflict with this package"),
        (
            "build-requires=",
            None,
            "capabilities required to build this package",
        ),
        ("obsoletes=", None, "capabilities made obsolete by this package"),
        ("no-autoreq", None, "do not automatically calculate dependencies"),
        # Actions to take when building RPM
        ("keep-temp", "k", "don't clean up RPM build directory"),
        ("no-keep-temp", None, "clean up RPM build directory [default]"),
        ("rpm3-mode", None, "RPM 3 compatibility mode (default)"),
        ("rpm2-mode", None, "RPM 2 compatibility mode"),
        # Add the hooks necessary for specifying custom scripts
        (
            "prep-script=",
            None,
            "Specify a script for the PREP phase of RPM building",
        ),
        (
            "build-script=",
            None,
            "Specify a script for the BUILD phase of RPM building",
        ),
        (
            "pre-install=",
            None,
            "Specify a script for the pre-INSTALL phase of RPM building",
        ),
        (
            "install-script=",
            None,
            "Specify a script for the INSTALL phase of RPM building",
        ),
        (
            "post-install=",
            None,
            "Specify a script for the post-INSTALL phase of RPM building",
        ),
        (
            "pre-uninstall=",
            None,
            "Specify a script for the pre-UNINSTALL phase of RPM building",
        ),
        (
            "post-uninstall=",
            None,
            "Specify a script for the post-UNINSTALL phase of RPM building",
        ),
        (
            "clean-script=",
            None,
            "Specify a script for the CLEAN phase of RPM building",
        ),
        (
            "verify-script=",
            None,
            "Specify a script for the VERIFY phase of the RPM build",
        ),
        ("quiet", "q", "Run the INSTALL phase of RPM building in quiet mode"),
        ("debug", "g", "Run in debug mode"),
    ]

    boolean_options: ClassVar[list[str]] = [
        "keep-temp",
        "rpm3-mode",
        "no-autoreq",
        "quiet",
        "debug",
    ]

    negative_opt: ClassVar[dict[str, str]] = {
        "no-keep-temp": "keep-temp",
        "rpm2-mode": "rpm3-mode",
    }

    def initialize_options(self) -> None:
        self.bdist_base = None
        self.dist_dir = None

        self.rpm_base = None
        self.spec_only = None

        self.distribution_name = None
        self.group = None
        self.release = None
        self.serial = None
        self.vendor = None
        self.packager = None
        self.doc_files = None
        self.changelog = None
        self.icon = None

        self.prep_script = None
        self.build_script = None
        self.install_script = None
        self.clean_script = None
        self.verify_script = None
        self.pre_install = None
        self.post_install = None
        self.pre_uninstall = None
        self.post_uninstall = None
        self.prep = None
        self.provides = None
        self.requires = None
        self.conflicts = None
        self.build_requires = None
        self.obsoletes = None

        self.keep_temp = 0
        self.rpm3_mode = 1
        self.no_autoreq = 0

        self.quiet = 0
        self.debug = 0

    def finalize_options(self) -> None:
        if os.name != "posix":
            msg = (
                "don't know how to create RPM "
                f"distributions on platform {os.name}"
            )
            raise PlatformError(msg)

        self._rpm = shutil.which("rpm")
        self._rpmbuild = shutil.which("rpmbuild")
        if not self._rpmbuild:
            msg = "failed to find rpmbuild for this platform."
            raise PlatformError(msg)

        self.set_undefined_options(
            "bdist",
            ("bdist_base", "bdist_base"),
            ("dist_dir", "dist_dir"),
        )
        if self.rpm_base is None:
            if not self.rpm3_mode:
                msg = "you must specify --rpm-base in RPM 2 mode"
                raise OptionError(msg)
            self.rpm_base = os.path.join(self.bdist_base, "rpm")

        self.finalize_package_data()

    def finalize_package_data(self) -> None:
        self.ensure_string("group", "Development/Libraries")
        contact = self.distribution.get_contact() or "UNKNOWN"
        contact_email = self.distribution.get_contact_email() or "UNKNOWN"
        self.ensure_string("vendor", f"{contact} <{contact_email}>")
        self.ensure_string("packager")
        self.ensure_string_list("doc_files")
        if isinstance(self.doc_files, list):
            doc_files = set(self.doc_files)
            for readme in ("README", "README.txt"):
                if os.path.exists(readme) and readme not in doc_files:
                    self.doc_files.append(readme)

        self.ensure_string("release", "1")
        self.ensure_string("serial")  # should it be an int?

        self.ensure_string("distribution_name")

        self.ensure_string("changelog")
        # Format changelog correctly
        self.changelog = self._format_changelog(self.changelog)

        self.ensure_filename("icon")

        self.ensure_filename("prep_script")
        self.ensure_filename("build_script")
        self.ensure_filename("install_script")
        self.ensure_filename("clean_script")
        self.ensure_filename("verify_script")
        self.ensure_filename("pre_install")
        self.ensure_filename("post_install")
        self.ensure_filename("pre_uninstall")
        self.ensure_filename("post_uninstall")

        # Now *this* is some meta-data that belongs in the setup script...
        self.ensure_string_list("provides")
        self.ensure_string_list("requires")
        self.ensure_string_list("conflicts")
        self.ensure_string_list("build_requires")
        self.ensure_string_list("obsoletes")

    def run(self) -> None:
        if self.debug:
            print("before _get_package_data():")
            print("vendor =", self.vendor)
            print("packager =", self.packager)
            print("doc_files =", self.doc_files)
            print("changelog =", self.changelog)

        # make directories
        if self.spec_only:
            spec_dir = self.dist_dir
        else:
            rpm_dir = {}
            for data in ("SOURCES", "SPECS", "BUILD", "RPMS", "SRPMS"):
                rpm_dir[data] = os.path.join(self.rpm_base, data)
                self.mkpath(rpm_dir[data])
            spec_dir = rpm_dir["SPECS"]
        self.mkpath(self.dist_dir)

        # Spec file goes into 'dist_dir' if '--spec-only specified',
        # build/rpm.<plat> otherwise.
        distribution_name = self.distribution.get_name()
        spec_path = os.path.join(spec_dir, f"{distribution_name}.spec")
        self.execute(
            write_file,
            (spec_path, self._make_spec_file()),
            f"writing '{spec_path}'",
        )

        if self.spec_only:  # stop if requested
            return

        # Make a source distribution and copy to SOURCES directory with
        # optional icon.
        def exclude_filter(info: tarfile.TarInfo) -> tarfile.TarInfo | None:
            if (
                os.path.basename(info.name) in ("build", "dist")
                and info.isdir()
            ):
                return None
            return info

        name = self.distribution.get_name()
        version = self.distribution.get_version()
        source = f"{name}-{version}"
        source_dir = rpm_dir["SOURCES"]
        source_fullname = os.path.join(source_dir, source + ".tar.gz")
        with tarfile.open(source_fullname, "w:gz") as tar:
            tar.add(".", source, filter=exclude_filter)
        if self.icon:
            if os.path.exists(self.icon):
                self.copy_file(self.icon, source_dir)
            else:
                msg = f"icon file {self.icon!r} does not exist"
                raise FileError(msg)

        # build package
        logging.info("building RPMs")
        rpm_cmd = [self._rpmbuild]
        # binary only
        rpm_cmd.append("-bb")
        if self.rpm3_mode:
            topdir = os.path.abspath(self.rpm_base)
            rpm_cmd.extend(["--define", f"_topdir {topdir}"])
        if not self.keep_temp:
            rpm_cmd.append("--clean")

        if self.quiet:
            rpm_cmd.append("--quiet")

        rpm_cmd.append(spec_path)
        # Determine the binary rpm names that should be built out of this spec
        # file
        # Note that some of these may not be really built (if the file
        # list is empty)
        nvr_string = "%{name}-%{version}-%{release}"
        src_rpm = nvr_string + ".src.rpm"
        non_src_rpm = "%{arch}/" + nvr_string + ".%{arch}.rpm"
        q_cmd = [
            self._rpm,
            "-q",
            "--qf",
            rf"{src_rpm} {non_src_rpm}\n",
            "--specfile",
            spec_path,
        ]
        try:
            out = check_output(q_cmd, text=True)
        except CalledProcessError as exc:
            msg = f"Failed to execute: {' '.join(q_cmd)!r}"
            raise ExecError(msg) from exc

        binary_rpms = []
        for line in out.splitlines():
            rows = line.split()
            assert len(rows) == 2  # noqa: S101
            binary_rpms.append(rows[1])

        self.spawn(rpm_cmd)

        if not self.dry_run:
            pyversion = get_python_version()

            for binary_rpm in binary_rpms:
                rpm = os.path.join(rpm_dir["RPMS"], binary_rpm)
                if os.path.exists(rpm):
                    self.move_file(rpm, self.dist_dir)
                    filename = os.path.join(
                        self.dist_dir, os.path.basename(rpm)
                    )
                    self.distribution.dist_files.append(
                        ("bdist_rpm", pyversion, filename)
                    )

    def _make_spec_file(self) -> list[str]:
        """Generate the text of an RPM spec file and return it as a
        list of strings (one per line).
        """
        # definitions and headers
        spec_file = [
            "%define name " + self.distribution.get_name(),
            "%define version "
            + self.distribution.get_version().replace("-", "_"),
            "%define unmangled_version " + self.distribution.get_version(),
            "%define release " + self.release.replace("-", "_"),
            "",
            "Summary: " + self.distribution.get_description() or "UNKNOWN",
            "Name: %{name}",
            "Version: %{version}",
            "Release: %{release}",
            f"License: {self.distribution.get_license() or 'UNKNOWN'}",
            f"Group: {self.group}",
            "BuildRoot: %{buildroot}",
            "Prefix: %{_prefix}",
            f"BuildArch: {platform.machine()}",
        ]

        # Workaround for #14443 which affects some RPM based systems such as
        # RHEL6 (and probably derivatives)
        vendor_hook = check_output(
            [self._rpm, "--eval", "%{__os_install_post}"], text=True
        )
        # Generate a potential replacement value for __os_install_post (whilst
        # normalizing the whitespace to simplify the test for whether the
        # invocation of brp-python-bytecompile passes in __python):
        vendor_hook = "\n".join(
            [f"  {line.strip()} \\" for line in vendor_hook.splitlines()]
        )
        problem = "brp-python-bytecompile \\\n"
        fixed = "brp-python-bytecompile %{__python} \\\n"
        fixed_hook = vendor_hook.replace(problem, fixed)
        if fixed_hook != vendor_hook:
            spec_file += [
                "# Workaround for http://bugs.python.org/issue14443",
                f"%define __python {sys.executable}",
                "%define __os_install_post " + fixed_hook + "\n",
            ]

        # we create the spec file before running 'tar' in case of --spec-only.
        spec_file.append("Source0: %{name}-%{unmangled_version}.tar.gz")

        for field in (
            "Vendor",
            "Packager",
            "Provides",
            "Requires",
            "Conflicts",
            "Obsoletes",
        ):
            val = getattr(self, field.lower())
            if isinstance(val, list):
                join_val = " ".join(val)
                spec_file.append(f"{field}: {join_val}")
            elif val is not None:
                spec_file.append(f"{field}: {val}")

        if self.distribution.get_url() not in (None, "UNKNOWN"):
            spec_file.append("Url: " + self.distribution.get_url())

        if self.distribution_name:
            spec_file.append("Distribution: " + self.distribution_name)

        if self.build_requires:
            spec_file.append("BuildRequires: " + " ".join(self.build_requires))

        if self.icon:
            spec_file.append("Icon: " + os.path.basename(self.icon))

        if self.no_autoreq:
            spec_file.append("AutoReq: 0")

        spec_file.extend(
            [
                "",
                "%description",
                self.distribution.get_long_description()
                or self.distribution.get_description()
                or "UNKNOWN",
            ]
        )

        # rpm scripts - figure out default build script
        def_setup_call = f"{sys.executable} {self.distribution.script_name}"
        def_build = f"{def_setup_call} build_exe -O1 --silent"
        def_build = 'env CFLAGS="$RPM_OPT_FLAGS" ' + def_build

        # insert contents of files

        # this is kind of misleading: user-supplied options are files
        # that we open and interpolate into the spec file, but the defaults
        # are just text that we drop in as-is.

        install_cmd = (
            f"{def_setup_call} install --skip-build"
            " --prefix=%{_prefix} --root=%{buildroot}"
        )

        script_options = [
            ("prep", "prep_script", "%setup -n %{name}-%{unmangled_version}"),
            ("build", "build_script", def_build),
            ("install", "install_script", install_cmd),
            ("clean", "clean_script", "rm -rf %{buildroot}"),
            ("verifyscript", "verify_script", None),
            ("pre", "pre_install", None),
            ("post", "post_install", None),
            ("preun", "pre_uninstall", None),
            ("postun", "post_uninstall", None),
        ]

        for rpm_opt, attr, default in script_options:
            # Insert contents of file referred to, if no file is referred to
            # use 'default' as contents of script
            val = getattr(self, attr)
            if val or default:
                spec_file.extend(["", "%" + rpm_opt])
                if val:
                    with open(val, encoding="utf_8") as file:
                        spec_file.extend(file.read().split("\n"))
                else:
                    spec_file.append(default)

        # files section
        spec_file.extend(
            [
                "",
                "%files",
                "%dir %{_prefix}/lib/%{name}-%{unmangled_version}",
                "%{_prefix}/lib/%{name}-%{unmangled_version}/*",
                "%{_bindir}/%{name}",
                "%defattr(-,root,root)",
            ]
        )

        if self.doc_files:
            spec_file.append("%doc " + " ".join(self.doc_files))

        if self.changelog:
            spec_file.extend(["", "%changelog"])
            spec_file.extend(self.changelog)

        # cx_Freeze specific
        spec_file.append("%define __prelink_undo_cmd %{nil}")
        spec_file.append("%define __strip /bin/true")
        return spec_file

    @staticmethod
    def _format_changelog(changelog) -> list[str]:
        """Format the changelog correctly and convert it to a string list."""
        if not changelog:
            return changelog
        new_changelog = []
        for raw_line in changelog.strip().split("\n"):
            line = raw_line.strip()
            if line[0] == "*":
                new_changelog.extend(["", line])
            elif line[0] == "-":
                new_changelog.append(line)
            else:
                new_changelog.append("  " + line)

        # strip trailing newline inserted by first changelog entry
        if not new_changelog[0]:
            del new_changelog[0]

        return new_changelog


def write_file(filename, contents) -> None:
    """Create a file with the specified name and write 'contents'
    (a sequence of strings without line terminators) to it.
    """
    with open(filename, "w", encoding="utf_8") as file:
        for line in contents:
            file.write(line + "\n")
