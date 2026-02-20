"""Base class for Module and ConstantsModule."""

from __future__ import annotations

import ast
import socket
from contextlib import suppress
from datetime import datetime, timezone
from functools import cached_property, partial
from importlib import import_module
from importlib.machinery import EXTENSION_SUFFIXES
from keyword import iskeyword
from pathlib import Path
from typing import TYPE_CHECKING

from cx_Freeze._importlib import metadata
from cx_Freeze.exception import ModuleError, OptionError

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from types import CodeType

__all__ = ["ConstantsModule", "Module", "ModuleHook"]


class DistributionCache(metadata.PathDistribution):
    """Cache the distribution package."""

    def __init__(self, cache_path: Path, name: str) -> None:
        """Construct a distribution.

        :param cache_path: Path indicating where to store the cache.
        :param name: The name of the distribution package to cache.
        :raises ModuleError: When the named package's distribution
            metadata cannot be found.
        """
        try:
            distribution = metadata.PathDistribution.from_name(name)
        except metadata.PackageNotFoundError:
            distribution = None
        if distribution is None:
            raise ModuleError(name)
        # Cache dist-info files in a temporary directory
        normalized_name = getattr(distribution, "_normalized_name", None)
        if normalized_name is None:
            normalized_name = metadata.Prepared.normalize(name)
        source_path = getattr(distribution, "_path", None)
        if source_path is None:
            mask = f"{normalized_name}-{distribution.version}.*-info"
            dist_path = list(distribution.locate_file(".").glob(mask))
            if not dist_path:
                mask = f"{name}-{distribution.version}.*-info"
                dist_path = list(distribution.locate_file(".").glob(mask))
            if dist_path:
                source_path = dist_path[0]
        if source_path is None or not source_path.exists():
            raise ModuleError(name)

        target_name = f"{normalized_name}-{distribution.version}.dist-info"
        target_path = cache_path / target_name
        super().__init__(target_path)
        if target_path.exists():  # cached
            return
        target_path.mkdir(parents=True)

        purelib = None
        if source_path.name.endswith(".dist-info"):
            for source in source_path.rglob("*"):  # type: Path
                target = target_path / source.relative_to(source_path)
                if source.is_dir():
                    target.mkdir(exist_ok=True)
                else:
                    target.write_bytes(source.read_bytes())
        elif source_path.is_file():
            # old egg-info file is converted to dist-info
            target = target_path / "METADATA"
            target.write_bytes(source_path.read_bytes())
            purelib = (source_path.parent / (normalized_name + ".py")).exists()
        else:
            # Copy minimal data from egg-info directory into dist-info
            source = source_path / "PKG-INFO"
            if source.is_file():
                target = target_path / "METADATA"
                target.write_bytes(source.read_bytes())
            source = source_path / "top_level.txt"
            if source.is_file():
                target = target_path / "top_level.txt"
                target.write_bytes(source.read_bytes())
            purelib = not source_path.joinpath("not-zip-safe").is_file()

        self._write_wheel_distinfo(target_path, purelib)
        self._write_record_distinfo(target_path)

    @staticmethod
    def _write_wheel_distinfo(target_path: Path, purelib: bool) -> None:
        """Create a WHEEL file if it doesn't exist."""
        target = target_path / "WHEEL"
        if not target.exists():
            project = Path(__file__).parent.name
            version = metadata.version(project)
            root_is_purelib = "true" if purelib else "false"
            text = [
                "Wheel-Version: 1.0",
                f"Generator: {project} ({version})",
                f"Root-Is-Purelib: {root_is_purelib}",
                "Tag: py3-none-any",
            ]
            with target.open(mode="w", encoding="utf_8", newline="") as file:
                file.write("\n".join(text))

    @staticmethod
    def _write_record_distinfo(target_path: Path) -> None:
        """Recreate a minimal RECORD file."""
        target_name = target_path.name
        record = [
            f"{target_name}/{file.name},," for file in target_path.iterdir()
        ]
        record.append(f"{target_name}/RECORD,,")
        target = target_path / "RECORD"
        with target.open(mode="w", encoding="utf_8", newline="") as file:
            file.write("\n".join(record))

    @property
    def requires(self) -> list[str]:
        return super().requires or []


class Module:
    """The Module class."""

    def __init__(
        self,
        name: str,
        path: Sequence[Path | str] | None = None,
        filename: Path | str | None = None,
        parent: Module | None = None,
    ) -> None:
        self.name: str = name
        self.path: list[Path] | None = list(map(Path, path)) if path else None
        self._file: Path | None = self._file_validate(filename)
        self.parent: Module | None = parent
        self.root: Module = parent.root if parent else self
        self.code: CodeType | None = None
        self.cache_path: Path | None = None
        self.distribution: DistributionCache | None = None
        self.hook: ModuleHook | Callable | None = None
        self.exclude_names: set[str] = set()
        self.global_names: set[str] = set()
        self.ignore_names: set[str] = set()
        self.in_import: bool = True
        self.source_is_string: bool = False
        self.source_is_zip_file: bool = False
        self._in_file_system: int = 1
        # add the load hook
        self.load_hook()

    def __repr__(self) -> str:
        parts = [f"name={self.name!r}"]
        if self.file is not None:
            parts.append(f"file={self.file!r}")
        if self.path is not None:
            parts.append(f"path={self.path!r}")
        join_parts = ", ".join(parts)
        return f"<Module {join_parts}>"

    @property
    def file(self) -> Path | None:
        """Module filename."""
        return self._file

    @file.setter
    def file(self, filename: Path | str | None) -> None:
        self._file = self._file_validate(filename)

    def _file_validate(self, filename: Path | str | None) -> Path | None:
        if "stub_code" in self.__dict__:
            del self.__dict__["stub_code"]  # clear the cache
        if not filename:
            return None
        if isinstance(filename, str):
            filename = Path(filename)
        return filename

    @cached_property
    def stub_code(self) -> CodeType | None:
        cache_path: Path = self.cache_path
        filename = self._file
        if filename is None:
            return None
        ext = "".join(filename.suffixes)
        if ext not in EXTENSION_SUFFIXES:
            return None
        source_dir = self.root.file.parent
        package = filename.parent.relative_to(source_dir.parent)
        stem = filename.name.partition(ext)[0]
        stub_name = f"{stem}.pyi"
        # search for the stub file already parsed in the distribution
        importshed = Path(__file__).resolve().parent / "importshed"
        source_file = importshed / package / stub_name
        if source_file.exists():
            imports_only = source_file.read_text(encoding="utf_8")
            if imports_only:
                return compile(imports_only, stub_name, "exec")
        # search for a stub file along side the python extension module
        source_file = filename.parent / stub_name
        if not source_file.exists():
            return None
        if cache_path:
            target_file = cache_path / package / stub_name
            if target_file.exists():
                # a parsed stub exists in the cache
                imports_only = target_file.read_text(encoding="utf_8")
            else:
                imports_only = self.get_imports_from_file(source_file)
                if imports_only:
                    # cache the parsed stub
                    target_file.parent.mkdir(parents=True, exist_ok=True)
                    target_file.write_text(
                        "# Generated by cx_Freeze\n\n" + imports_only,
                        encoding="utf_8",
                    )
        else:
            imports_only = self.get_imports_from_file(source_file)
        if imports_only:
            return compile(imports_only, stub_name, "exec")
        return None

    def get_imports_from_file(self, source_file: Path) -> str | None:
        """Get the implicit imports in a stub file."""
        if not source_file.is_file():
            return None
        ignore = {"__future__", "builtins", "typing", "_typeshed"}
        source = source_file.read_text(encoding="utf_8")
        try:
            rootnode = ast.parse(source, source_file.name)
        except SyntaxError:
            return None
        lines = []
        for node in ast.walk(rootnode):
            if isinstance(node, ast.Import):
                names = {name.name for name in node.names}
                names.difference_update(ignore)
                if names:
                    lines.append("import " + ", ".join(sorted(names)))
            elif isinstance(node, ast.ImportFrom):
                if node.level == 0 and node.module in ignore:
                    continue
                names = {name.name for name in node.names}
                line = "from "
                if node.level > 0:
                    line += "." * node.level
                if node.module:
                    line += node.module
                line += " import " + ", ".join(sorted(names))
                lines.append(line)
        return "\n".join([*lines, ""]) if lines else None

    @property
    def in_file_system(self) -> int:
        """Returns a value indicating where the module/package will be stored:
        0. in a zip file (not directly in the file system)
        1. in the file system, package with modules and data
        2. in the file system, only detected modules.
        """
        if self.parent is not None:
            return self.parent.in_file_system
        if self.path is None or self.file is None:
            return 0
        return self._in_file_system

    @in_file_system.setter
    def in_file_system(self, value: int) -> None:
        self._in_file_system: int = value

    def load_hook(self) -> None:
        """Load hook for the given module if one is present.

        For instance, a load hook for PyQt5.QtCore:
        - Using ModuleHook class:
            # module and hook methods are lowercased.
            hook = pyqt5.Hook()
            hook.qt_qtcore()
        - For functions present in hooks.__init__:
            # module and load hook functions use the original case.
            load_PyQt5_QtCore()
        - For functions in a separated module:
            # module and load hook functions are lowercased.
            pyqt5.load_pyqt5_qtcore()
        """
        if not isinstance(self.root.hook, ModuleHook):
            try:
                # new style hook using ModuleHook class - top-level call
                root_name = self.root.name.lower()
                hooks = import_module(f"cx_Freeze.hooks.{root_name}")
                hook_cls = getattr(hooks, "Hook", None)
                if hook_cls and issubclass(hook_cls, ModuleHook):
                    self.root.hook = hook_cls(self.root)
                else:
                    # old style hook with lowercased functions
                    name = self.name.replace(".", "_").lower()
                    func = getattr(hooks, f"load_{name}", None)
                    self.hook = partial(func, module=self) if func else None
                    return
            except ImportError:
                # old style hook with functions at hooks.__init__
                hooks = import_module("cx_Freeze.hooks")
                name = self.name.replace(".", "_")
                func = getattr(hooks, f"load_{name}", None)
                self.hook = partial(func, module=self) if func else None
                return
        # new style hook using ModuleHook class - lower level call
        root_hook = self.root.hook
        if isinstance(root_hook, ModuleHook) and self.parent is not None:
            name = "_".join(self.name.lower().split(".")[1:])
            func = getattr(root_hook, f"{root_hook.name}_{name}", None)
            self.hook = partial(func, module=self) if func else None

    def update_distribution(self, name: str | None = None) -> None:
        """Update the distribution cache based on its name.
        This method may be used to link an distribution's name to a module.

        Example: ModuleFinder cannot detects the distribution of _cffi_backend
        but in a hook we can link it to 'cffi'.
        """
        cache_path: Path = self.cache_path
        if cache_path is None:
            return
        if name is None:
            name = self.name
        try:
            distribution = DistributionCache(cache_path, name)
        except ModuleError:
            return
        for req in distribution.requires:
            req_name = req.partition(" ")[0]
            with suppress(ModuleError):
                DistributionCache(cache_path, req_name)
        self.distribution = distribution


class ModuleHook:
    """The Module Hook class."""

    def __init__(self, module: Module) -> None:
        self.module = module
        self.name = module.name.replace(".", "_").lower()

    def __call__(self, finder) -> None:
        # redirect to the top level hook
        method = getattr(self, self.name, None)
        if method:
            method(finder, self.module)


class ConstantsModule:
    """Base ConstantsModule class."""

    def __init__(
        self,
        release_string: str | None = None,
        copyright_string: str | None = None,
        module_name: str = "BUILD_CONSTANTS",
        time_format: str = "%B %d, %Y %H:%M:%S",
        constants: list[str] | None = None,
    ) -> None:
        self.module_name: str = module_name
        self.time_format: str = time_format
        self.values: dict[str, str] = {}
        self.values["BUILD_RELEASE_STRING"] = release_string
        self.values["BUILD_COPYRIGHT"] = copyright_string
        if constants:
            for constant in constants:
                parts = constant.split("=", maxsplit=1)
                if len(parts) == 1:
                    name = constant
                    value = None
                else:
                    name, string_value = parts
                    value = ast.literal_eval(string_value)
                if (not name.isidentifier()) or iskeyword(name):
                    msg = (
                        f"Invalid constant name in ConstantsModule ({name!r})"
                    )
                    raise OptionError(msg)
                self.values[name] = value

    def create(self, tmp_path: Path, modules: list[Module]) -> Path:
        """Create the module which consists of declaration statements for each
        of the values.
        """
        today = datetime.now(tz=timezone.utc)
        source_timestamp = 0
        for module in modules:
            if module.file is None or module.source_is_string:
                continue
            if module.source_is_zip_file:
                continue
            if not module.file.exists():
                msg = (
                    f"No file named {module.file!s} (for module {module.name})"
                )
                raise OptionError(msg)
            timestamp = module.file.stat().st_mtime
            source_timestamp = max(source_timestamp, timestamp)
        stamp = datetime.fromtimestamp(source_timestamp, tz=timezone.utc)
        self.values["BUILD_TIMESTAMP"] = today.strftime(self.time_format)
        self.values["BUILD_HOST"] = socket.gethostname().split(".")[0]
        self.values["SOURCE_TIMESTAMP"] = stamp.strftime(self.time_format)
        parts = []
        names = list(self.values.keys())
        names.sort()
        for name in names:
            value = self.values[name]
            parts.append(f"{name} = {value!r}")
        module_path = tmp_path.joinpath(self.module_name).with_suffix(".py")
        with module_path.open(mode="w", encoding="utf_8", newline="") as file:
            file.write("\n".join(parts))
        return module_path
