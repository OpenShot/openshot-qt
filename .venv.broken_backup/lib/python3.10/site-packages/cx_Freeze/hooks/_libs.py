"""Helper functions for hooks."""

from __future__ import annotations

from types import CodeType
from typing import TYPE_CHECKING

from cx_Freeze.common import code_object_replace_function

if TYPE_CHECKING:
    from cx_Freeze.module import Module


def replace_delvewheel_patch(
    module: Module, libs_name: str | None = None
) -> None:
    """Replace delvewheel injections of code to not find for module.libs
    directory.
    """
    code = module.code
    if code is None:
        return

    if libs_name is None:
        libs_name = f"{module.name}.libs"
    delvewheel_func_names = "_delvewheel_init_patch_", "_delvewheel_patch_"
    consts = list(code.co_consts)
    for constant in consts:
        if isinstance(constant, CodeType):
            name = constant.co_name
            if name.startswith(delvewheel_func_names):
                source = f"""\
                def {name}():
                    import os, sys

                    libs_path = os.path.join(
                        sys.frozen_dir, "lib", "{libs_name}"
                    )
                    try:
                        os.add_dll_directory(libs_path)
                    except (OSError, AttributeError):
                        pass
                    env_path = os.environ.get("PATH", "").split(os.pathsep)
                    if libs_path not in env_path:
                        env_path.insert(0, libs_path)
                        os.environ["PATH"] = os.pathsep.join(env_path)
                """
                code = code_object_replace_function(code, name, source)
                break
    module.code = code
