#!/usr/bin/env python3
"""Make a generated Qt resource module use OpenShot's binding-neutral Qt API."""

import argparse
from pathlib import Path


BINDING_IMPORTS = (
    "from PyQt5 import QtCore",
    "from PyQt6 import QtCore",
    "from PySide6 import QtCore",
)
NEUTRAL_IMPORT = "from qt_api import QtCore"


def neutralize_import(source):
    """Replace exactly one supported binding import with qt_api."""
    matches = [
        binding_import
        for binding_import in BINDING_IMPORTS
        if binding_import in source
    ]
    if not matches:
        if NEUTRAL_IMPORT in source:
            return source
        raise ValueError("No supported QtCore import found")
    if len(matches) != 1:
        raise ValueError("Multiple QtCore binding imports found")
    return source.replace(matches[0], NEUTRAL_IMPORT, 1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("resource_module", type=Path)
    args = parser.parse_args()

    source = args.resource_module.read_text(encoding="utf-8")
    updated = neutralize_import(source)
    args.resource_module.write_text(updated, encoding="utf-8")


if __name__ == "__main__":
    main()
