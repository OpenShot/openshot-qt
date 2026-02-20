"""The internal _packaging module."""

from __future__ import annotations

try:
    from setuptools.extern.packaging.version import Version
except ImportError:
    from packaging.version import Version

__all__ = ["Version"]
