"""Local distribution metadata. Build markers describe provenance, not authenticity."""

import ctypes
import json
import os
import platform
import sys
from functools import lru_cache


def windows_package_name():
    """Return this process's package identity, or empty for an unpackaged process."""
    try:
        function = ctypes.WinDLL("kernel32").GetCurrentPackageFullName
        function.argtypes = [ctypes.POINTER(ctypes.c_uint32), ctypes.c_wchar_p]
        function.restype = ctypes.c_long
        length = ctypes.c_uint32()
        if function(ctypes.byref(length), None) != 122:  # ERROR_INSUFFICIENT_BUFFER
            return ""
        if not 0 < length.value <= 32768:
            return ""
        buffer = ctypes.create_unicode_buffer(length.value)
        if function(ctypes.byref(length), buffer) == 0:
            return buffer.value
    except (AttributeError, OSError, ValueError):
        pass
    return ""


def detect_distribution(metadata, system, executable, frozen, environ, package_name="",
                        flatpak=False):
    """Classify the running copy conservatively; downstream packages stay unofficial."""
    kind = "unknown"
    official = False
    marked = metadata.get("official_distribution") is True
    if flatpak or environ.get("FLATPAK_ID"):
        kind = "flatpak"
    elif environ.get("SNAP"):
        kind = "snap"
    elif system == "Windows" and package_name:
        kind = "msix"
        official = marked and frozen and package_name.split("_")[0] == "OpenShotStudios.OpenShotforWindows"
    elif system == "Linux" and environ.get("APPIMAGE"):
        kind = "appimage"
        official = marked and frozen
    elif system == "Windows" and frozen and executable.lower().endswith(".exe"):
        kind = "exe"
        official = marked
    elif system == "Darwin" and frozen and ".app/Contents/MacOS/" in executable:
        kind = "appbundle"
        official = marked
    return {"package_type": kind, "official": official}


@lru_cache(maxsize=1)
def get_distribution_info():
    from classes import info
    try:
        with open(os.path.join(info.PATH, "settings", "version.json"), encoding="utf-8") as stream:
            metadata = json.load(stream)
        if not isinstance(metadata, dict):
            metadata = {}
    except (OSError, ValueError):
        metadata = {}
    system = platform.system()
    package_name = windows_package_name() if system == "Windows" else ""
    result = detect_distribution(
        metadata, system, sys.executable, bool(getattr(sys, "frozen", False)), os.environ,
        package_name,
        os.path.isfile("/.flatpak-info"),
    )
    result.update(app_version=info.VERSION, platform=system.lower(),
                  architecture=platform.machine())
    if metadata.get("build_name"):
        result["build_name"] = str(metadata["build_name"])
    if package_name and len(package_name.split("_")) == 5:
        result["package_version"] = package_name.split("_")[1]
    return result


def distribution_label():
    data = get_distribution_info()
    return "{} | Official distribution: {}".format(
        data["package_type"], "yes" if data["official"] else "no")


def is_snap():
    """Whether this process is running in a Snap package."""
    return bool(os.environ.get("SNAP"))


def blender_unavailable_message(_):
    return _("Not available in Snap")
