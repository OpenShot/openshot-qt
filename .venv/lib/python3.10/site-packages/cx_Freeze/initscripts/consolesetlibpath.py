"""Initialization script for cx_Freeze which manipulates the path so that the
directory in which the executable is found is searched for extensions but
no other directory is searched. The environment variable LD_LIBRARY_PATH is
manipulated first, however, to ensure that shared libraries found in the
target directory are found. This requires a restart of the executable because
the environment variable LD_LIBRARY_PATH is only checked at startup.

"""

from __future__ import annotations

import os
import sys

DIR_NAME = os.path.dirname(sys.executable)

paths = os.environ.get("LD_LIBRARY_PATH", "").split(os.pathsep)

if DIR_NAME not in paths:
    paths.insert(0, DIR_NAME)
    os.environ["LD_LIBRARY_PATH"] = os.pathsep.join(paths)
    os.execv(sys.executable, sys.argv)  # noqa: S606

sys.frozen = True
sys.path = sys.path[:4]


def run(name) -> None:
    """Execute the main script of the frozen application."""
    code = __spec__.loader.get_code(name)
    module_main = __import__("__main__")
    module_main.__dict__["__file__"] = code.co_filename
    exec(code, module_main.__dict__)
