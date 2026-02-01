"""First script that is run when cx_Freeze starts up. It determines the name of
the initscript that is to be executed after a basic initialization.
"""

from __future__ import annotations

import os
import string
import sys
from importlib.machinery import (
    EXTENSION_SUFFIXES,
    ExtensionFileLoader,
    ModuleSpec,
    PathFinder,
)

import BUILD_CONSTANTS

STRINGREPLACE = list(
    string.whitespace + string.punctuation.replace(".", "").replace("_", "")
)


class ExtensionFinder(PathFinder):
    """A Finder for extension modules of packages in zip files."""

    @classmethod
    def find_spec(
        cls,
        fullname,
        path=None,
        target=None,  # noqa: ARG003
    ) -> ModuleSpec | None:
        """Finder only for extension modules found within packages that
        are included in the zip file (instead of as files on disk);
        extension modules cannot be found within zip files but are stored in
        the lib subdirectory; if the extension module is found in a package,
        however, its name has been altered so this finder is needed.
        """
        if path is None:
            return None
        suffixes = EXTENSION_SUFFIXES
        for entry in sys.path:
            if ".zip" in entry:
                continue
            for ext in suffixes:
                location = os.path.join(entry, fullname + ext)
                if os.path.isfile(location):
                    loader = ExtensionFileLoader(fullname, location)
                    return ModuleSpec(fullname, loader, origin=location)
        return None


def init() -> None:
    """Basic initialization of the startup script."""
    # to avoid bugs (especially in MSYS2) use normpath after any change
    sys.executable = os.path.normpath(sys.executable)
    sys.frozen_dir = frozen_dir = os.path.dirname(sys.executable)
    sys.meta_path.append(ExtensionFinder)

    sys.path = list(map(os.path.normpath, sys.path))
    if sys.platform.startswith("win"):
        # for python >= 3.8, the search for dlls is sandboxed
        search_path: list[str] = [
            entry for entry in sys.path if os.path.isdir(entry)
        ]
        add_to_path = os.path.join(frozen_dir, "lib")
        if add_to_path not in search_path:
            search_path.insert(0, add_to_path)
        # add to dll search path (or to path)
        env_path = os.environ.get("PATH", "").split(os.pathsep)
        env_path = list(map(os.path.normpath, env_path))
        for directory in search_path:
            try:
                os.add_dll_directory(directory)
            except OSError:
                pass
            except AttributeError:
                # XXX: we need to add to path only when python < 3.8
                if directory not in env_path:
                    env_path.insert(0, directory)
        env_path = [entry.replace(os.sep, "\\") for entry in env_path]
        os.environ["PATH"] = os.pathsep.join(env_path)

    # set environment variables
    for name in (
        "TCL_LIBRARY",
        "TK_LIBRARY",
        "PYTZ_TZDATADIR",
        "PYTHONTZPATH",
    ):
        try:
            value = getattr(BUILD_CONSTANTS, name)
        except AttributeError:
            pass
        else:
            var_path = os.path.join(frozen_dir, os.path.normpath(value))
            if not os.path.exists(var_path) and sys.platform == "darwin":
                # when using bdist_mac
                var_path = os.path.join(
                    os.path.dirname(frozen_dir),
                    "Resources",
                    os.path.normpath(value),
                )
            os.environ[name] = var_path


def run() -> None:
    """Determines the name of the initscript and execute it."""
    # get the real name of __init__ script
    # basically, the basename of executable plus __init__
    # but can be renamed when only one executable exists
    name = os.path.normcase(os.path.basename(sys.executable))
    if sys.platform.startswith("win"):
        name, _ = os.path.splitext(name)
    name = name.partition(".")[0]
    if not name.isidentifier():
        for char in STRINGREPLACE:
            name = name.replace(char, "_")
    try:
        module_init = __import__(name + "__init__")
    except ModuleNotFoundError:
        names = [
            f.rpartition("__init__")[0]
            for f in __spec__.loader._files  # noqa: SLF001
            if f.endswith("__init__.pyc")
            and f.rpartition("__init__")[0].isidentifier()
        ]
        if len(names) != 1:
            msg = (
                "Apparently, the original executable has been renamed to "
                f"{name!r}. When multiple executables are generated, "
                "renaming is not allowed."
            )
            raise RuntimeError(msg) from None
        name = names[0]
        module_init = __import__(name + "__init__")
    module_init.run(name + "__main__")
