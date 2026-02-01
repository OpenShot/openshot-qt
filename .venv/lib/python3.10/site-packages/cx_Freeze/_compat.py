"""Internal compatible module."""

from __future__ import annotations

import sys
import sysconfig
from pathlib import Path

__all__ = ["PLATFORM", "IS_LINUX", "IS_MACOS", "IS_MINGW", "IS_WINDOWS"]
__all__ += ["IS_CONDA"]

PLATFORM = sysconfig.get_platform()
IS_LINUX = PLATFORM.startswith("linux")
IS_MACOS = PLATFORM.startswith("macos")
IS_MINGW = PLATFORM.startswith("mingw")
IS_MINGW64 = PLATFORM.startswith("mingw_x86_64")
IS_WINDOWS = PLATFORM.startswith("win")

IS_CONDA = Path(sys.prefix, "conda-meta").is_dir()
