"""Register bundled native libraries before importing Qt or libopenshot on Windows."""
import os
import sys

_DLL_HANDLES = {}


def configure_windows_dll_paths():
    if os.name != 'nt':
        return
    root = os.path.dirname(os.path.abspath(sys.executable))
    candidates = [root, os.path.join(root, 'lib')]
    candidates.extend(os.path.join(root, 'lib', binding) for binding in ('PyQt6', 'PySide6', 'PyQt5'))
    paths = [path for path in candidates if os.path.isdir(path)]
    os.environ['PATH'] = os.pathsep.join(paths + [os.environ.get('PATH', '')])
    add_directory = getattr(os, 'add_dll_directory', None)
    if add_directory:
        for path in paths:
            if path not in _DLL_HANDLES:
                # Retain the handles: closing them unregisters these directories.
                _DLL_HANDLES[path] = add_directory(path)
