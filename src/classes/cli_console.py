"""
 @file
 @brief Restore Windows standard streams for --cli invoked through the GUI executable.

 @section LICENSE

 Copyright (c) 2008-2026 OpenShot Studios, LLC
 (http://www.openshotstudios.com). This file is part of
 OpenShot Video Editor (http://www.openshot.org), an open-source project
 dedicated to delivering high quality video editing and animation solutions
 to the world.

 OpenShot Video Editor is free software: you can redistribute it and/or modify
 it under the terms of the GNU General Public License as published by
 the Free Software Foundation, either version 3 of the License, or
 (at your option) any later version.

 OpenShot Video Editor is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 GNU General Public License for more details.

 You should have received a copy of the GNU General Public License
 along with OpenShot Library.  If not, see <http://www.gnu.org/licenses/>.
 """
import os
import sys


def ensure_standard_streams():
    """Preserve redirected handles; attach to a calling terminal when available.

    Windows GUI executables can start with sys.stdout/stderr set to None. The
    console companion already has streams, so it needs no special handling.
    """
    names = ('stdin', 'stdout', 'stderr')
    if os.name != 'nt' or all(getattr(sys, name) is not None for name in names):
        return
    import ctypes
    from ctypes import wintypes
    import msvcrt

    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetStdHandle.argtypes = [wintypes.DWORD]
    kernel.GetStdHandle.restype = wintypes.HANDLE
    kernel.AttachConsole.argtypes = [wintypes.DWORD]
    kernel.AttachConsole.restype = wintypes.BOOL
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.DuplicateHandle.argtypes = [wintypes.HANDLE, wintypes.HANDLE, wintypes.HANDLE,
                                      ctypes.POINTER(wintypes.HANDLE), wintypes.DWORD,
                                      wintypes.BOOL, wintypes.DWORD]
    kernel.DuplicateHandle.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    ids = dict(zip(names, (-10, -11, -12)))
    saved = {name: kernel.GetStdHandle(identifier) for name, identifier in ids.items()}
    invalid = (None, 0, ctypes.c_void_p(-1).value)
    # Save pipe/file handles before attaching: AttachConsole can replace them.
    kernel.AttachConsole(wintypes.DWORD(-1))
    process = kernel.GetCurrentProcess()
    for name in names:
        if getattr(sys, name) is not None:
            continue
        handle = saved[name]
        if handle in invalid:
            handle = kernel.GetStdHandle(ids[name])
        mode = 'r' if name == 'stdin' else 'w'
        stream = None
        if handle not in invalid:
            duplicate = wintypes.HANDLE()
            if kernel.DuplicateHandle(process, handle, process, ctypes.byref(duplicate), 0, False, 2):
                try:
                    flags = (os.O_RDONLY if mode == 'r' else os.O_WRONLY) | os.O_BINARY
                    descriptor = msvcrt.open_osfhandle(duplicate.value, flags)
                except OSError:
                    kernel.CloseHandle(duplicate)
                    raise
                stream = os.fdopen(descriptor, mode, buffering=1, encoding='utf-8', errors='replace')
        if stream is None:
            # No terminal or redirected handle (e.g. launched from Explorer).
            stream = open(os.devnull, mode, encoding='utf-8')
        setattr(sys, name, stream)
