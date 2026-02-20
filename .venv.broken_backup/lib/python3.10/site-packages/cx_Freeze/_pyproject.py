"""Internal module."""

from __future__ import annotations

from pathlib import Path

try:
    from tomllib import loads as toml_loads
except ImportError:
    try:
        from setuptools.extern.tomli import loads as toml_loads
    except ImportError:
        from tomli import loads as toml_loads


def get_pyproject_tool_data() -> dict:
    pyproject_toml = Path("pyproject.toml")
    if not pyproject_toml.exists():
        return {}
    data = toml_loads(pyproject_toml.read_bytes().decode())
    tool_data = data.get("tool", {}).get("cxfreeze", {})
    executables = tool_data.pop("executables", [])
    options = {}
    for cmd, data in tool_data.items():
        for option, value in data.items():
            options.setdefault(cmd, {})
            options[cmd].setdefault(option, ("tool.cxfreeze", value))
    options["executables"] = executables
    return options
