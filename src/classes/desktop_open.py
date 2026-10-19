"""Open a file in its default application, or reveal it in the file manager.

Linux prefers the xdg-desktop-portal (host installs, AppImage, Snap and
Flatpak alike), then a sanitized ``xdg-open``. Windows and macOS use their
native file managers. Every path ends with Qt's generic ``openUrl`` fallback.
"""

import os
import shutil
# Known desktop executables with argument arrays; no shell.
import subprocess  # nosec B404
import sys

from qt_api import QDesktopServices, QUrl

from classes.logger import log

# Bundled libraries must never leak into the user's own applications.
_LOADER_VARIABLES = ("LD_LIBRARY_PATH", "LD_PRELOAD", "LD_AUDIT", "PYTHONPATH", "PYTHONHOME",
                     "QT_PLUGIN_PATH", "QML2_IMPORT_PATH", "GST_PLUGIN_PATH")


def _sandboxed():
    return bool(os.environ.get("SNAP") or os.environ.get("FLATPAK_ID")
                or os.path.isfile("/.flatpak-info"))


def _host_environment():
    environment = dict(os.environ)
    for variable in _LOADER_VARIABLES:
        environment.pop(variable, None)
    return environment


def _launch(command):
    try:
        # Fixed executables from PATH with argument arrays. No shell.
        subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,  # nosec B603
                         stderr=subprocess.DEVNULL, env=_host_environment(), close_fds=True)
        return True
    except OSError as exc:
        log.warning("Unable to launch %s: %s", command[0], exc)
        return False


def _open_url(path):
    try:
        return bool(QDesktopServices.openUrl(QUrl.fromLocalFile(path)))
    except Exception:
        log.warning("Unable to open %s", path, exc_info=True)
        return False


def _xdg_open(path):
    executable = shutil.which("xdg-open")
    return bool(executable) and not _sandboxed() and _launch([executable, path])


def open_file(parent, path):
    """Open path with the user's default application. Returns True when launched."""
    if sys.platform.startswith("linux"):
        from classes.portal_file_dialog import open_file_with_default_application
        result = open_file_with_default_application(parent, path)
        if result is not None:
            return result
        if _xdg_open(path):
            return True
    return _open_url(path)


def reveal_file(parent, path):
    """Show path selected in the file manager, or open its folder when it can't be selected."""
    folder = os.path.dirname(path) or "."
    if not os.path.exists(path):
        # e.g. an image sequence pattern: the folder is the useful result.
        return open_file(parent, folder) if os.path.isdir(folder) else False
    if sys.platform == "win32":
        return _launch(["explorer", "/select,", os.path.normpath(path)]) or _open_url(folder)
    if sys.platform == "darwin":
        return _launch(["open", "-R", path]) or _open_url(folder)
    from classes.portal_file_dialog import open_containing_directory
    if open_containing_directory(parent, path):
        return True
    return _xdg_open(folder) or _open_url(folder)
