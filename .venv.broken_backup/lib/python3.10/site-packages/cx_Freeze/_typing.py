"""The internal _typing module."""

from __future__ import annotations

from pathlib import Path, PurePath

try:
    from typing import TypeAlias  # 3.10+
except ImportError:
    from typing_extensions import TypeAlias

from cx_Freeze.module import Module

DeferredList: TypeAlias = list[tuple[Module, Module, list[str]]]

IncludesList: TypeAlias = list[
    str | Path | tuple[str | Path, str | Path | None]
]

InternalIncludesList: TypeAlias = list[tuple[Path, PurePath]]

__all__ = ["TypeAlias", "DeferredList", "IncludesList", "InternalIncludesList"]
