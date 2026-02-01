"""Initialization script for cx_Freeze which behaves similarly to the one for
console based applications but must handle the case where Python has already
been initialized and another DLL of this kind has been loaded. As such it
does not block the path unless sys.frozen is not already set.
"""

from __future__ import annotations

import sys

if not hasattr(sys, "frozen"):
    sys.frozen = True
    sys.path = sys.path[:4]


def run() -> None:  # noqa: D103
    pass
