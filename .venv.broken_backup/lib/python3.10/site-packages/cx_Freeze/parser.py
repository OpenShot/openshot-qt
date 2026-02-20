"""Implements `Parser` interface to create an abstraction to parse binary
files.
"""

from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess
from abc import ABC, abstractmethod
from contextlib import suppress
from pathlib import Path
from tempfile import TemporaryDirectory

from cx_Freeze._compat import IS_MINGW, IS_WINDOWS
from cx_Freeze.exception import PlatformError

# In Windows, to get dependencies, the default is to use lief package,
# but LIEF can be disabled with:
# set CX_FREEZE_BIND=imagehlp
if IS_WINDOWS or IS_MINGW:
    import lief

    with suppress(ImportError):
        from .util import BindError, GetDependentFiles

    lief.logging.set_level(lief.logging.LOGGING_LEVEL.ERROR)

LIEF_DISABLED = os.environ.get("CX_FREEZE_BIND", "") == "imagehlp"
PE_EXT = (".exe", ".dll", ".pyd")
MAGIC_ELF = b"\x7fELF"
NON_ELF_EXT = ".a:.c:.h:.py:.pyc:.pyi:.pyx:.pxd:.txt:.html:.xml".split(":")
NON_ELF_EXT += ".png:.jpg:.gif:.jar:.json".split(":")


class Parser(ABC):
    """`Parser` interface."""

    def __init__(
        self, path: list[str], bin_path_includes: list[str], silent: int = 0
    ) -> None:
        self._path: list[str] = path
        self._bin_path_includes: list[str] = bin_path_includes
        self._silent: int = silent

        self.dependent_files: dict[Path, set[Path]] = {}
        self.linker_warnings: set = set()

    @property
    def search_path(self) -> list[str]:
        """The default search path."""
        # This cannot be cached because os.environ["PATH"] can be changed in
        # freeze module before the call to get_dependent_files.
        env_path = os.environ["PATH"].split(os.pathsep)
        new_path = []
        for path in self._path + self._bin_path_includes + env_path:
            if path not in new_path and os.path.isdir(path):
                new_path.append(path)
        return new_path

    def find_library(
        self, name: str, search_path: list[str | Path] | None = None
    ) -> Path | None:
        if search_path is None:
            search_path = self.search_path
        for directory in map(Path, search_path):
            library = directory / name
            if library.is_file():
                return library.resolve()
        return None

    def get_dependent_files(self, filename: str | Path) -> set[Path]:
        """Return the file's dependencies using platform-specific tools."""
        if isinstance(filename, str):
            filename = Path(filename)

        with suppress(KeyError):
            return self.dependent_files[filename]

        if not self._is_binary(filename):
            return set()

        dependent_files: set[Path] = self._get_dependent_files(filename)
        self.dependent_files[filename] = dependent_files
        return dependent_files

    @abstractmethod
    def _get_dependent_files(self, filename: Path) -> set[Path]:
        """Return the file's dependencies using platform-specific tools
        (lief package or the imagehlp library on Windows, otool on Mac OS X or
        ldd on Linux); limit this list by the exclusion lists as needed.
        (Implemented separately for each platform).
        """

    @staticmethod
    def _is_binary(filename: Path) -> bool:
        """Determines whether the file is a binary (executable, shared library)
        file. (Overridden in each platform).
        """
        return filename.is_file()


class PEParser(Parser):
    """`PEParser` is based on the `lief` package. If it is disabled,
    use the old friend `cx_Freeze.util` extension module.
    """

    def __init__(
        self, path: list[str], bin_path_includes: list[str], silent: int = 0
    ) -> None:
        super().__init__(path, bin_path_includes, silent)
        if hasattr(lief.PE, "ParserConfig"):
            # LIEF 0.14+
            imports_only = lief.PE.ParserConfig()
            imports_only.parse_exports = False
            imports_only.parse_imports = True
            imports_only.parse_reloc = False
            imports_only.parse_rsrc = False
            imports_only.parse_signature = False
            self.imports_only = imports_only
            resource_only = lief.PE.ParserConfig()
            resource_only.parse_exports = False
            resource_only.parse_imports = False
            resource_only.parse_reloc = False
            resource_only.parse_rsrc = True
            resource_only.parse_signature = False
            self.resource_only = resource_only
        else:
            self.imports_only = None
            self.resource_only = None

    @staticmethod
    def is_pe(filename: str | Path) -> bool:
        """Determines whether the file is a PE file."""
        if isinstance(filename, str):
            filename = Path(filename)
        return filename.suffix.lower().endswith(PE_EXT) and filename.is_file()

    _is_binary = is_pe

    def _get_dependent_files_lief(self, filename: Path) -> set[Path]:
        with filename.open("rb", buffering=0) as raw:
            binary = lief.PE.parse(raw, self.imports_only or filename.name)
        if not binary:
            return set()

        libraries: list[str] = []
        if binary.has_imports:
            libraries += binary.libraries
        for delay_import in binary.delay_imports:
            libraries.append(delay_import.name)

        dependent_files: set[Path] = set()
        search_path = [filename.parent, *self.search_path]
        for name in libraries:
            library = self.find_library(name, search_path)
            if library:
                dependent_files.add(library)
            else:
                if self._silent < 3 and name not in self.linker_warnings:
                    print(f"WARNING: cannot find '{name}'")
                self.linker_warnings.add(name)
        return dependent_files

    def _get_dependent_files_imagehlp(self, filename: Path) -> set[Path]:
        env_path = os.environ["PATH"]
        os.environ["PATH"] = os.pathsep.join(self.search_path)
        try:
            return {Path(dep) for dep in GetDependentFiles(filename)}
        except BindError as exc:
            # Sometimes this gets called when filename is not actually
            # a library (See issue 88).
            if self._silent < 3:
                print("WARNING: ignoring error during ", end="")
                print(f"GetDependentFiles({filename}):", exc)
        finally:
            os.environ["PATH"] = env_path
        return set()

    if LIEF_DISABLED:
        _get_dependent_files = _get_dependent_files_imagehlp
    else:
        _get_dependent_files = _get_dependent_files_lief

    def read_manifest(self, filename: str | Path) -> str:
        """:return: the XML schema of the manifest included in the executable
        :rtype: str

        """
        if isinstance(filename, str):
            filename = Path(filename)
        with filename.open("rb", buffering=0) as raw:
            binary = lief.PE.parse(raw, self.resource_only or filename.name)
        resources_manager = binary.resources_manager
        return (
            resources_manager.manifest
            if resources_manager.has_manifest
            else None
        )

    def write_manifest(self, filename: str | Path, manifest: str) -> None:
        """:return: write the XML schema of the manifest into the executable
        :rtype: str

        """
        if isinstance(filename, str):
            filename = Path(filename)
        with filename.open("rb", buffering=0) as raw:
            binary = lief.PE.parse(raw, self.resource_only or filename.name)
        resources_manager = binary.resources_manager
        resources_manager.manifest = manifest
        builder = lief.PE.Builder(binary)
        builder.build_resources(True)
        builder.build()
        with TemporaryDirectory(prefix="cxfreeze-") as tmp_dir:
            tmp_path = Path(tmp_dir, filename.name)
            builder.write(os.fspath(tmp_path))
            shutil.move(tmp_path, filename)


class ELFParser(Parser):
    """`ELFParser` is based on the logic around invoking `patchelf` and
    `ldd`.
    """

    def __init__(
        self, path: list[str], bin_path_includes: list[str], silent: int = 0
    ) -> None:
        super().__init__(path, bin_path_includes, silent)
        self._patchelf = shutil.which("patchelf")
        self._verify_patchelf()

    @staticmethod
    def is_elf(filename: str | Path) -> bool:
        """Check if the executable is an ELF."""
        if isinstance(filename, str):
            filename = Path(filename)
        if (
            filename.suffix in NON_ELF_EXT
            or filename.is_symlink()
            or not filename.is_file()
        ):
            return False
        with open(filename, "rb") as binary:
            four_bytes = binary.read(4)
        return bool(four_bytes == MAGIC_ELF)

    _is_binary = is_elf

    def _get_dependent_files(self, filename: Path) -> set[Path]:
        dependent_files: set[Path] = set()
        split_string = " => "
        dependent_file_index = 1
        args = ("ldd", filename)
        env = os.environ.copy()
        env.pop("LD_PRELOAD", None)
        process = subprocess.run(
            args, check=False, capture_output=True, encoding="utf_8", env=env
        )
        for line in process.stdout.splitlines():
            parts = line.expandtabs().strip().split(split_string)
            if len(parts) != 2:
                continue
            partname = parts[dependent_file_index].strip()
            if partname == filename.name:
                continue
            if partname in ("not found", "(file not found)"):
                partname = Path(parts[0])
                for bin_path in self.bin_path_includes:
                    partname = Path(bin_path, partname)
                    if partname.is_file():
                        dependent_files.add(partname)
                        break
                if not partname.is_file():
                    name = partname.name
                    if self._silent < 3 and name not in self.linker_warnings:
                        print(f"WARNING: cannot find '{name}'")
                    self.linker_warnings.add(name)
                continue
            if partname.startswith("("):
                continue
            pos = partname.find(" (")
            if pos >= 0:
                partname = partname[:pos].strip()
            if partname:
                dependent_files.add(Path(partname))
        if process.returncode and self._silent < 3:
            print("WARNING:", *args, "returns:")
            print(process.stderr, end="")
        return dependent_files

    def get_rpath(self, filename: str | Path) -> str:
        """Gets the rpath of the executable."""
        with suppress(subprocess.CalledProcessError):
            return self.run_patchelf(["--print-rpath", filename]).strip()
        return ""

    def replace_needed(
        self, filename: str | Path, so_name: str, new_so_name: str
    ) -> None:
        """Replace DT_NEEDED entry in the dynamic table."""
        self._set_write_mode(filename)
        self.run_patchelf(["--replace-needed", so_name, new_so_name, filename])

    def set_rpath(self, filename: str | Path, rpath: str) -> None:
        """Sets the rpath of the executable."""
        self._set_write_mode(filename)
        self.run_patchelf(["--remove-rpath", filename])
        self.run_patchelf(["--force-rpath", "--set-rpath", rpath, filename])

    def set_soname(self, filename: str | Path, new_so_name: str) -> None:
        """Sets DT_SONAME entry in the dynamic table."""
        self._set_write_mode(filename)
        self.run_patchelf(["--set-soname", new_so_name, filename])

    def run_patchelf(self, args: list[str]) -> str:
        process = subprocess.run(
            [self._patchelf, *args], check=True, capture_output=True, text=True
        )
        if self._silent < 1:
            print("patchelf", *args, "returns:", repr(process.stdout))
            if process.stderr:
                print("patchelf errors:", repr(process.stderr))
        return process.stdout

    @staticmethod
    def _set_write_mode(filename: str | Path) -> None:
        if isinstance(filename, str):
            filename = Path(filename)
        mode = filename.stat().st_mode
        if mode & stat.S_IWUSR == 0:
            filename.chmod(mode | stat.S_IWUSR)

    def _verify_patchelf(self) -> None:
        """Looks for the ``patchelf`` external binary in the PATH, checks for
        the required version, and throws an exception if a proper version
        can't be found. Otherwise, silence is golden.
        """
        if not self._patchelf:
            msg = "Cannot find required utility `patchelf` in PATH"
            raise PlatformError(msg)
        try:
            version = self.run_patchelf(["--version"])
        except subprocess.CalledProcessError:
            msg = "Could not call `patchelf` binary"
            raise PlatformError(msg) from None

        mobj = re.match(r"patchelf\s+(\d+(.\d+)?)", version)
        if mobj and tuple(map(int, mobj.group(1).split("."))) >= (0, 14):
            return
        msg = f"patchelf {version} found. cx_Freeze requires patchelf >= 0.14."
        raise ValueError(msg)
