"""Common utility functions shared between cx_Freeze modules."""

from __future__ import annotations

from contextlib import suppress
from pathlib import Path, PurePath
from textwrap import dedent
from types import CodeType
from typing import TYPE_CHECKING

from cx_Freeze.exception import OptionError

if TYPE_CHECKING:
    from cx_Freeze._typing import IncludesList, InternalIncludesList


def get_resource_file_path(
    dirname: str | Path, name: str | Path, ext: str
) -> Path | None:
    """Return the path to a resource file shipped with cx_Freeze.

    This is used to find our base executables and initscripts when they are
    just specified by name.
    """
    pname = Path(name)
    if pname.is_absolute():
        return pname
    pname = Path(__file__).resolve().parent / dirname / pname.with_suffix(ext)
    if pname.exists():
        return pname
    # Support for name argument in the old Camelcase value
    pname = pname.with_name(pname.name.lower())
    if pname.exists():
        return pname
    return None


def normalize_to_list(
    value: str | list[str] | tuple[str, ...] | None,
) -> list[str]:
    """Takes the different formats of options containing multiple values and
    returns the value as a list object.
    """
    if value is None:
        return []
    if isinstance(value, str):
        return value.split(",")
    return list(value)


def process_path_specs(specs: IncludesList | None) -> InternalIncludesList:
    """Prepare paths specified as config.

    The input is a list of either strings, or 2-tuples (source, target).
    Where single strings are supplied, the basenames are used as targets.
    Where targets are given explicitly, they must not be absolute paths.

    Returns a list of 2-tuples, or throws OptionError if something is wrong
    in the input.
    """
    if specs is None:
        specs = []
    processed_specs: InternalIncludesList = []
    for spec in specs:
        if not isinstance(spec, (list, tuple)):
            source = spec
            target = None
        elif len(spec) != 2:
            msg = "path spec must be a list or tuple of length two"
            raise OptionError(msg)
        else:
            source, target = spec
        source = Path(source)
        if not source.exists():
            msg = f"cannot find file/directory named {source!s}"
            raise OptionError(msg)
        target = PurePath(target or source.name)
        if target.is_absolute():
            msg = f"target path named {target!s} cannot be absolute"
            raise OptionError(msg)
        processed_specs.append((source, target))
    return processed_specs


def code_object_replace(code: CodeType, **kwargs) -> CodeType:
    """Return a copy of the code object with new values for the specified
    fields.
    """
    with suppress(ValueError, KeyError):
        kwargs["co_consts"] = tuple(kwargs["co_consts"])
    return code.replace(**kwargs)


def code_object_replace_function(
    code: CodeType, name: str, source: str
) -> CodeType:
    """Return a copy of the code object with the function 'name' replaced."""
    if code is None:
        return code

    new_code = compile(dedent(source), code.co_filename, "exec")
    new_co_func = None
    for constant in new_code.co_consts:
        if isinstance(constant, CodeType) and constant.co_name == name:
            new_co_func = constant
            break
    if new_co_func is None:
        return code

    consts = list(code.co_consts)
    for i, constant in enumerate(consts):
        if isinstance(constant, CodeType) and constant.co_name == name:
            consts[i] = code_object_replace(
                new_co_func, co_firstlineno=constant.co_firstlineno
            )
            break
    return code_object_replace(code, co_consts=consts)
