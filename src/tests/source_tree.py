"""Locate build-time fixtures from source and pybuild's copied package tree."""

from pathlib import Path


def source_path(relative_path):
    for root in Path(__file__).resolve().parents:
        candidate = root / relative_path
        if (root / "setup.py").is_file() and candidate.exists():
            return candidate
    raise FileNotFoundError("Source fixture not found: %s" % relative_path)
