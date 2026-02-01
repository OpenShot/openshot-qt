"""Initialization script for cx_Freeze. Sets the attribute sys.frozen so that
modules that expect it behave as they should.
"""

from __future__ import annotations

import sys

sys.frozen = True


def run(name) -> None:
    """Execute the main script of the frozen application."""
    code = __spec__.loader.get_code(name)
    module_main = __import__("__main__")
    module_main.__dict__["__file__"] = code.co_filename
    exec(code, module_main.__dict__)
