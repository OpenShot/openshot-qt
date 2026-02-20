# ruff: noqa
from __future__ import annotations
import sysconfig

import os
import shutil
import stat
import subprocess
from tempfile import TemporaryDirectory
from collections.abc import Iterable
from pathlib import Path
from cx_Freeze.exception import PlatformError


# In a MachO file, need to deal specially with links that use @executable_path,
# @loader_path, @rpath
#
# @executable_path - where ultimate calling executable is
# @loader_path - directory of current object
# @rpath - list of paths to check
# (earlier rpaths have higher priority, i believe)
#
# Resolving these variables (particularly @rpath) requires tracing through the
# sequence linked MachO files leading the the current file, to determine which
# directories are included in the current rpath.


def isMachOFile(path: Path) -> bool:
    """Determines whether the file is a Mach-O file."""
    if not path.is_file():
        return False
    if b"Mach-O" in subprocess.check_output(("file", path)):
        return True
    return False


class MachOReference:
    """Represents a linking reference from MachO file to another file."""

    def __init__(
        self,
        source_file: DarwinFile,
        raw_path: str,
        resolved_path: Path | None,
    ):
        """:param source_file: DarwinFile object for file in which the reference
        was found
        :param raw_path: The load path that appears in the file
        (may include @rpath, etc.)
        :param resolved_path: The path resolved to an explicit path to a file
        on system. Or None, if the path could not be resolved at the time the
        DarwinFile was processed.
        """
        self.source_file: DarwinFile = source_file
        self.raw_path: str = raw_path
        self.resolved_path: Path | None = resolved_path

        # True if the referenced file is copied into the frozen package
        # (i.e., not a non-copied system file)
        self.is_copied = False
        # reference to target DarwinFile (but only if file is copied into app)
        self.target_file: DarwinFile | None = None

    def isResolved(self) -> bool:
        return self.resolved_path is not None

    def setTargetFile(self, darwin_file: DarwinFile):
        self.target_file = darwin_file
        self.is_copied = True


class DarwinFile:
    """A DarwinFile object represents a file that will be copied into the
    application, and record where it was ultimately moved to in the application
    bundle. Mostly used to provide special handling for copied files that are
    Mach-O files.
    """

    def __init__(
        self,
        path: str | Path,
        referencing_file: DarwinFile | None = None,
        strict: bool = False,
    ):
        """:param path: The original path of the DarwinFile
        (before copying into app)
        :param referencing_file: DarwinFile object representing the referencing
        source file
        :param strict: Do not make guesses about rpath resolution. If the
        load does not resolve, throw an Exception.
        """
        self.path = Path(path).resolve()
        self.referencing_file: DarwinFile | None = None
        self.strict = strict

        # path to file in build directory (set as part of freeze process)
        self._build_path: Path | None = None

        # commands in a Mach-O file
        self.commands: list[MachOCommand] = []
        self.loadCommands: list[MachOLoadCommand] = []
        self.rpathCommands: list[MachORPathCommand] = []

        # note: if file gets referenced twice (or more), it will only be the
        # first reference that gets recorded.
        # mapping of raw load paths to absolute resolved paths
        # (or None, if no resolution was determined)
        self.libraryPathResolution: dict[str, Path | None] = {}
        # the is of entries in the rpath in effect for this file.
        self._rpath: list[Path] | None = None

        # dictionary of MachOReference objects, by their paths.
        # Path used is the resolved path, if available, and otherwise the
        # unresolved load path.
        self.machOReferenceForTargetPath: dict[Path, MachOReference] = {}

        if not isMachOFile(self.path):
            self.isMachO = False
            return

        # if this is a MachO file, extract linking information from it
        self.isMachO = True
        self.commands = MachOCommand._getMachOCommands(self.path)
        self.loadCommands = [
            c for c in self.commands if isinstance(c, MachOLoadCommand)
        ]
        self.rpathCommands = [
            c for c in self.commands if isinstance(c, MachORPathCommand)
        ]
        self.referencing_file = referencing_file

        self.getRPath()
        self.resolveLibraryPaths()

        # Create MachOReference objects for all the binaries referenced form
        # this file.
        for raw_path, resolved_path in self.libraryPathResolution.items():
            # the path to use for storing in dictionary
            if resolved_path is None:
                dict_path = Path(raw_path)
            else:
                dict_path = resolved_path
            if dict_path in self.machOReferenceForTargetPath:
                if self.strict:
                    raise PlatformError(
                        f"ERROR: Multiple dynamic libraries from {self.path}"
                        f" resolved to the same file ({dict_path})."
                    )
                print(
                    f"WARNING: Multiple dynamic libraries from {self.path}"
                    f" resolved to the same file ({dict_path})."
                )
                continue
            reference = MachOReference(
                source_file=self,
                raw_path=raw_path,
                resolved_path=resolved_path,
            )
            self.machOReferenceForTargetPath[dict_path] = reference

    def __str__(self):
        parts = []
        # parts.append("RPath Commands: {}".format(self.rpathCommands))
        # parts.append("Load commands: {}".format(self.loadCommands))
        parts.append(f"Mach-O File: {self.path}")
        parts.append("Resolved rpath:")
        for rpath in self.getRPath():
            parts.append(f"   {rpath}")
        parts.append("Loaded libraries:")
        for rpath in self.libraryPathResolution:
            parts.append(f"   {rpath} -> {self.libraryPathResolution[rpath]}")
        return "\n".join(parts)

    def fileReferenceDepth(self) -> int:
        """Returns how deep this Mach-O file is in the dynamic load order."""
        if self.referencing_file is not None:
            return self.referencing_file.fileReferenceDepth() + 1
        return 0

    def printFileInformation(self):
        """Prints information about the Mach-O file."""
        print(f"[{self.fileReferenceDepth()}] File: {self.path}")
        print("  Commands:")
        if len(self.commands) > 0:
            for cmd in self.commands:
                print(f"    {cmd}")
        else:
            print("    [None]")

        # This can be included for even more detail on the problem file.
        # print("  Load commands:")
        # if len(self.loadCommands) > 0:
        #     for cmd in self.loadCommands: print(f'    {cmd}')
        # else: print("    [None]")

        print("  RPath commands:")
        if len(self.rpathCommands) > 0:
            for rpc in self.rpathCommands:
                print(f"    {rpc}")
        else:
            print("    [None]")
        print("  Calculated RPath:")
        rpath = self.getRPath()
        if len(rpath) > 0:
            for path in rpath:
                print(f"    {path}")
        else:
            print("    [None]")
        if self.referencing_file is not None:
            print("Referenced from:")
            self.referencing_file.printFileInformation()

    def setBuildPath(self, path: Path):
        self._build_path = path

    def getBuildPath(self) -> Path | None:
        return self._build_path

    @staticmethod
    def isExecutablePath(path: str) -> bool:
        return path.startswith("@executable_path")

    @staticmethod
    def isLoaderPath(path: str) -> bool:
        return path.startswith("@loader_path")

    @staticmethod
    def isRPath(path: str) -> bool:
        return path.startswith("@rpath")

    def resolveLoader(self, path: str) -> Path | None:
        """Resolve a path that includes @loader_path. @loader_path represents
        the directory in which the DarwinFile is located.
        """
        if self.isLoaderPath(path):
            return self.path.parent / Path(path).relative_to("@loader_path")
        raise PlatformError(f"resolveLoader() called on bad path: {path}")

    def resolveExecutable(self, path: str) -> Path:
        """@executable_path should resolve to the directory where the original
        executable was located. By default, we set that to the directory of
        the library, so it would resolve in the same was as if linked from an
        executable in the same directory.
        """
        # consider making this resolve to the directory of the python
        # interpreter? Apparently not a big issue in practice, since the
        # code has been like this forever.
        if self.isExecutablePath(path):
            return self.path.parent / Path(path).relative_to(
                "@executable_path/"
            )
        raise PlatformError(f"resolveExecutable() called on bad path: {path}")

    def resolveRPath(self, path: str) -> Path | None:
        for rpath in self.getRPath():
            test_path = rpath / Path(path).relative_to("@rpath")
            if isMachOFile(test_path):
                return test_path
        if not self.strict:
            # If not strictly enforcing rpath, return None here, and leave any
            # error to .finalizeReferences() instead.
            return None
        print(f"\nERROR: Problem resolving RPath [{path}] in file:")
        self.printFileInformation()
        raise PlatformError(f"resolveRPath() failed to resolve path: {path}")

    def getRPath(self) -> list[Path]:
        """Returns the rpath in effect for this file. Determined by rpath
        commands in this file and (recursively) the chain of files that
        referenced this file.
        """
        if self._rpath is not None:
            return self._rpath
        raw_paths = [c.rpath for c in self.rpathCommands]
        rpath = []
        for raw_path in raw_paths:
            test_rp = Path(raw_path)
            if test_rp.is_absolute():
                rpath.append(test_rp)
            elif self.isLoaderPath(raw_path):
                rpath.append(self.resolveLoader(raw_path).resolve())
            elif self.isExecutablePath(raw_path):
                rpath.append(self.resolveExecutable(raw_path).resolve())
        rpath = [raw_path for raw_path in rpath if raw_path.exists()]

        if self.referencing_file is not None:
            rpath = self.referencing_file.getRPath() + rpath
        self._rpath = rpath
        return rpath

    def resolvePath(self, path: str) -> Path | None:
        """Resolves any @executable_path, @loader_path, and @rpath references
        in a path.
        """
        if self.isLoaderPath(path):  # replace @loader_path
            return self.resolveLoader(path)
        if self.isExecutablePath(path):  # replace @executable_path
            return self.resolveExecutable(path)
        if self.isRPath(path):  # replace @rpath
            return self.resolveRPath(path)
        test_path = Path(path)
        if test_path.is_absolute():  # just use the path, if it is absolute
            return test_path
        test_path = self.path.parent / path
        if isMachOFile(test_path):
            return test_path.resolve()
        if self.strict:
            raise PlatformError(
                f"Could not resolve path: {path} from file {self.path}."
            )
        print(
            f"WARNING: Unable to resolve reference to {path} from "
            f"file {self.path}.  Frozen application may not "
            f"function correctly."
        )
        return None

    def resolveLibraryPaths(self):
        for cmd in self.loadCommands:
            raw_path = cmd.load_path
            resolved_path = self.resolvePath(raw_path)
            self.libraryPathResolution[raw_path] = resolved_path

    def getDependentFilePaths(self) -> set[Path]:
        """Returns a list the available resolved paths to dependencies."""
        dependents: set[Path] = set()
        for ref in self.machOReferenceForTargetPath.values():
            # skip load references that could not be resolved
            if ref.isResolved():
                dependents.add(ref.resolved_path)
        return dependents

    def getMachOReferenceList(self) -> list[MachOReference]:
        return list(self.machOReferenceForTargetPath.values())

    def getMachOReferenceForPath(self, path: Path) -> MachOReference:
        """Returns the reference pointing to the specified path, baed on paths
        stored in self.machOReferenceTargetPath. Raises Exception if not
        available.
        """
        try:
            return self.machOReferenceForTargetPath[path]
        except KeyError:
            raise PlatformError(
                f"Path {path} is not a path referenced from DarwinFile"
            ) from None


class MachOCommand:
    """Represents a load command in a MachO file."""

    def __init__(self, lines: list[str]):
        self.lines = lines

    def displayString(self) -> str:
        parts: list[str] = []
        if len(self.lines) > 0:
            parts.append(self.lines[0].strip())
        if len(self.lines) > 1:
            parts.append(self.lines[1].strip())
        return " / ".join(parts)

    def __repr__(self):
        return f"<MachOCommand ({self.displayString()})>"

    @staticmethod
    def _getMachOCommands(path: Path) -> list[MachOCommand]:
        """Returns a list of load commands in the specified file, using
        otool.
        """
        shell_command = ("otool", "-l", path)
        commands: list[MachOCommand] = []
        current_command_lines = None

        # split the output into separate load commands
        out = subprocess.check_output(shell_command, encoding="utf_8")
        for raw_line in out.splitlines():
            line = raw_line.strip()
            if line[:12] == "Load command":
                if current_command_lines is not None:
                    commands.append(
                        MachOCommand.parseLines(current_command_lines)
                    )
                current_command_lines = []
            if current_command_lines is not None:
                current_command_lines.append(line)
        if current_command_lines is not None:
            commands.append(MachOCommand.parseLines(current_command_lines))
        return commands

    @staticmethod
    def parseLines(lines: list[str]) -> MachOCommand:
        if len(lines) < 2:
            return MachOCommand(lines)
        parts = lines[1].split(" ")
        if parts[0] != "cmd":
            return MachOCommand(lines)
        if parts[1] == "LC_LOAD_DYLIB":
            return MachOLoadCommand(lines)
        if parts[1] == "LC_RPATH":
            return MachORPathCommand(lines)
        return MachOCommand(lines)


class MachOLoadCommand(MachOCommand):
    def __init__(self, lines: list[str]):
        super().__init__(lines)
        self.load_path = None
        if len(self.lines) < 4:
            return
        pathline = self.lines[3]
        pathline = pathline.strip()
        if not pathline.startswith("name "):
            return
        pathline = pathline[4:].strip()
        pathline = pathline.split("(offset")[0].strip()
        self.load_path = pathline

    def getPath(self):
        return self.load_path

    def __repr__(self):
        return f"<LoadCommand path={self.load_path!r}>"


class MachORPathCommand(MachOCommand):
    def __init__(self, lines: list[str]):
        super().__init__(lines)
        self.rpath = None
        if len(self.lines) < 4:
            return
        pathline = self.lines[3]
        pathline = pathline.strip()
        if not pathline.startswith("path "):
            return
        pathline = pathline[4:].strip()
        pathline = pathline.split("(offset")[0].strip()
        self.rpath = pathline

    def __repr__(self):
        return f"<RPath path={self.rpath!r}>"


def _printFile(
    darwinFile: DarwinFile,
    seenFiles: set[DarwinFile],
    level: int,
    noRecurse=False,
):
    """Utility function to prints details about a DarwinFile and (optionally)
    recursively any other DarwinFiles that it references.
    """
    print("{}{}".format(level * "|  ", os.fspath(darwinFile.path)), end="")
    print(" (already seen)" if noRecurse else "")
    if noRecurse:
        return
    for ref in darwinFile.machOReferenceForTargetPath.values():
        if not ref.is_copied:
            continue
        file = ref.target_file
        _printFile(
            file,
            seenFiles=seenFiles,
            level=level + 1,
            noRecurse=(file in seenFiles),
        )
        seenFiles.add(file)
    return


def printMachOFiles(fileList: list[DarwinFile]):
    seenFiles = set()
    for file in fileList:
        if file not in seenFiles:
            seenFiles.add(file)
            _printFile(file, seenFiles=seenFiles, level=0)


def change_load_reference(
    filename: str, old_reference: str, new_reference: str, verbose: bool = True
):
    """Utility function that uses install_name_tool to change old_reference to
    new_reference in the machO file specified by filename.
    """
    if verbose:
        print("Redirecting load reference for ", end="")
        print(f"<{filename}> {old_reference} -> {new_reference}")
    original = os.stat(filename).st_mode
    new_mode = original | stat.S_IWUSR
    if new_mode != original:
        os.chmod(filename, new_mode)
    subprocess.call(
        (
            "install_name_tool",
            "-change",
            old_reference,
            new_reference,
            filename,
        )
    )
    if new_mode != original:
        os.chmod(filename, original)


def apply_adhoc_signature(filename: str):
    if sysconfig.get_platform().endswith("x86_64"):
        return
    # Apply for universal2 and arm64 machines
    print("Applying AdHocSignature")
    args = (
        "codesign",
        "--sign",
        "-",
        "--force",
        "--preserve-metadata=entitlements,requirements,flags,runtime",
        filename,
    )
    if subprocess.call(args):
        # It may be a bug in Apple's codesign utility
        # The workaround is to copy the file to another inode, then move it
        # back erasing the previous file. The sign again.
        with TemporaryDirectory(prefix="cxfreeze-") as tmp_dir:
            tempname = os.path.join(tmp_dir, os.path.basename(filename))
            shutil.copy(filename, tempname)
            shutil.move(tempname, filename)
        subprocess.call(args)


class DarwinFileTracker:
    """Object to track the DarwinFiles that have been added during a freeze."""

    def __init__(self, strict: bool = False):
        self.strict = strict
        # list of DarwinFile objects for files being copied into project
        self._copied_file_list: list[DarwinFile] = []

        # mapping of (build directory) target paths to DarwinFile objects
        self._darwin_file_for_build_path: dict[Path, DarwinFile] = {}

        # mapping of (source location) paths to DarwinFile objects
        self._darwin_file_for_source_path: dict[Path, DarwinFile] = {}

        # a cache of MachOReference objects pointing to a given source path
        self._reference_cache: dict[Path, MachOReference] = {}

    def __iter__(self) -> Iterable[DarwinFile]:
        return iter(self._copied_file_list)

    def pathIsAlreadyCopiedTo(self, target_path: Path) -> bool:
        """Check if the given target_path has already has a file copied to
        it.
        """
        if target_path in self._darwin_file_for_build_path:
            return True
        return False

    def getDarwinFile(
        self, source_path: Path, target_path: Path
    ) -> DarwinFile:
        """Gets the DarwinFile for file copied from source_path to target_path.
        If either (i) nothing, or (ii) a different file has been copied to
        targetPath, raises a PlatformError.
        """
        # check that the target file came from the specified source
        targetDarwinFile: DarwinFile
        try:
            targetDarwinFile = self._darwin_file_for_build_path[target_path]
        except KeyError:
            raise PlatformError(
                f"File {target_path} already copied to, "
                "but no DarwinFile object found for it."
            ) from None
        real_source = source_path.resolve()
        target_real_source = targetDarwinFile.path.resolve()
        if real_source != target_real_source:
            # raise PlatformError(
            print(
                "*** WARNING ***\n"
                f"Attempting to copy two files to {target_path}\n"
                f"source 1: {targetDarwinFile.path} "
                f"(real: {target_real_source})\n"
                f"source 2: {source_path} (real: {real_source})\n"
                "(This may be caused by including modules in the zip file "
                "that rely on binary libraries with the same name.)"
                "\nUsing only source 1."
            )
        return targetDarwinFile

    def recordCopiedFile(self, target_path: Path, darwin_file: DarwinFile):
        """Record that a DarwinFile is being copied to a given path. If a
        file has been copied to that path, raise a PlatformError.
        """
        if self.pathIsAlreadyCopiedTo(target_path):
            raise PlatformError(
                "addFile() called with target_path already copied to "
                f"(target_path={target_path})"
            )

        self._copied_file_list.append(darwin_file)
        self._darwin_file_for_build_path[target_path] = darwin_file
        self._darwin_file_for_source_path[darwin_file.path] = darwin_file

    def cacheReferenceTo(self, source_path: Path, reference: MachOReference):
        self._reference_cache[source_path] = reference

    def getCachedReferenceTo(self, source_path: Path) -> MachOReference | None:
        return self._reference_cache.get(source_path)

    def findDarwinFileForFilename(self, filename: str) -> DarwinFile | None:
        """Attempts to locate a copied DarwinFile with the specified filename
        and returns that. Otherwise returns None.
        """
        basename = Path(filename).name
        for file in self._copied_file_list:
            if file.path.name == basename:
                return file
        return None

    def finalizeReferences(self):
        """This function does a final pass through the references for all the
        copied DarwinFiles and attempts to clean up any remaining references
        that are not already marked as copied. It covers two cases where the
        reference might not be marked as copied:
        1) Files where _CopyFile was called without copyDependentFiles=True
           (in which the information would not have been added to the
            references at that time).
        2) Files with broken @rpath references. We try to fix that up here by
           seeing if the relevant file was located *anywhere* as part of the
        freeze process.
        """
        copied_file: DarwinFile
        reference: MachOReference
        for copied_file in self._copied_file_list:
            for reference in copied_file.getMachOReferenceList():
                if not reference.is_copied:
                    if reference.isResolved():
                        # if reference is resolve, simply check if the resolved
                        # path was otherwise copied and lookup the DarwinFile
                        # object.
                        target_path = reference.resolved_path.resolve()
                        if target_path in self._darwin_file_for_source_path:
                            reference.setTargetFile(
                                self._darwin_file_for_source_path[target_path]
                            )
                    else:
                        # if reference is not resolved, look through the copied
                        # files and try to find a candidate, and use it if
                        # found.
                        potential_target = self.findDarwinFileForFilename(
                            reference.raw_path
                        )
                        if potential_target is None:
                            # If we cannot find any likely candidate, fail.
                            if self.strict:
                                copied_file.printFileInformation()
                                raise PlatformError(
                                    f"finalizeReferences() failed to resolve"
                                    f" path [{reference.raw_path}] in file "
                                    f"[{copied_file.path}]."
                                )
                            print(
                                "\nWARNING: Could not resolve dynamic link to "
                                f"[{reference.raw_path}] in file "
                                f"[{copied_file.path}], and could "
                                "not find any likely intended target."
                            )
                            continue
                        print(
                            f"WARNING: In file [{copied_file.path}]"
                            f" guessing that {reference.raw_path} "
                            f"resolved to {potential_target.path}."
                        )
                        reference.resolved_path = potential_target.path
                        reference.setTargetFile(potential_target)

    def set_relative_reference_paths(self, build_dir: str, bin_dir: str):
        """Make all the references from included Mach-O files to other included
        Mach-O files relative.
        """
        darwin_file: DarwinFile

        for darwin_file in self._copied_file_list:
            # Skip text files
            if darwin_file.path.suffix == ".txt":
                continue

            # get the relative path to darwin_file in build directory
            print(f"Setting relative_reference_path for: {darwin_file}")
            relative_copy_dest = os.path.relpath(
                darwin_file.getBuildPath(), build_dir
            )
            # figure out directory where it will go in binary directory for
            # .app bundle, this would be the Content/MacOS subdirectory in
            # bundle.  This is the file that needs to have its dynamic load
            # references updated.
            file_path_in_bin_dir = os.path.join(bin_dir, relative_copy_dest)
            # for each file that this darwin_file references, update the
            # reference as necessary; if the file is copied into the binary
            # package, change the reference to be relative to @executable_path
            # (so an .app bundle will work wherever it is moved)
            for reference in darwin_file.getMachOReferenceList():
                if not reference.is_copied:
                    # referenced file not copied -- assume this is a system
                    # file that will also be present on the user's machine,
                    # and do not change reference
                    continue
                # this is the reference in the machO file that needs to be
                # updated
                raw_path = reference.raw_path
                ref_target_file: DarwinFile = reference.target_file
                # this is where file copied in build dir
                abs_build_dest = ref_target_file.getBuildPath()
                rel_build_dest = os.path.relpath(abs_build_dest, build_dir)
                exe_path = f"@executable_path/{rel_build_dest}"
                change_load_reference(
                    file_path_in_bin_dir, raw_path, exe_path, verbose=False
                )

            apply_adhoc_signature(file_path_in_bin_dir)
