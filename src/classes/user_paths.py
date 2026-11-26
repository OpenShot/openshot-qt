"""Resolve application and user folders without importing Qt or libopenshot."""

import os
import sys


def application_path():
    """Return the installed resources root, or src when running from source."""
    if getattr(sys, "frozen", False) and sys.platform != "darwin":
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.realpath(__file__)))


def is_portable():
    """Only Windows installations opt in using a file beside the application."""
    return sys.platform == "win32" and os.path.isfile(
        os.path.join(application_path(), "portable"))


def user_path():
    """Keep portable state with the application, retaining normal home behavior."""
    root = application_path() if is_portable() else os.path.expanduser("~")
    return os.path.join(root, ".openshot_qt")
