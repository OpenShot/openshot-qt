"""Initialization script for cx_Freeze which imports the site module (as per
normal processing of a Python script) and then searches for a file with the
same name as the shared library but with the extension .pth. The entries in
this file are used to modify the path to use for subsequent imports.
"""

from __future__ import annotations

import os
import sys

# the site module must be imported for normal behavior to take place; it is
# done dynamically so that cx_Freeze will not add all modules referenced by
# the site module to the frozen executable
__import__("site")

# now locate the pth file to modify the path appropriately
name, ext = os.path.splitext(sys.executable)
filename = name + ".pth"
with open(filename, encoding="utf-8") as in_file:
    sys.path = [s.strip() for s in in_file.read().splitlines()] + sys.path


def run() -> None:  # noqa: D103
    pass
