"""List of modules for automatic exclusions on various platforms."""

from __future__ import annotations

import collections.abc
import os
import sys

__all__ = ("MODULES",)

MODULES = [
    # py2 modules that have been removed or renamed in py3
    "__builtin__",
    "__main__",
    "audiodev",
    "anydbm",
    "BaseHTTPServer",
    "Bastion",
    "bsddb",
    "cPickle",
    "commands",
    "ConfigParser",
    "Cookie",
    "copy_reg",
    "cStringIO",
    "dbhash",
    "dircache",
    "dumbdbm",
    "dummy_thread",
    "email.Charset",
    "email.Encoders",
    "email.Errors",
    "email.FeedParser",
    "email.Generator",
    "email.Header",
    "email.Iterators",
    "email.Message",
    "email.Parser",
    "email.Utils",
    "email.base64MIME",
    "email.quopriMIME",
    "FCNTL",
    "fl",
    "fm",
    "fpformat",
    "gl",
    "gdbm",
    "htmllib",
    "HTMLParser",
    "httplib",
    "hotshot",
    "ihooks",
    "imputil",
    "linuxaudiodev",
    "md5",
    "Nav",
    "new",
    "mutex",
    "Pickle",
    "Queue",
    "rexec",
    "robotparser",
    "sgmllib",
    "sha",
    "SocketServer",
    "statvfs",
    "StringIO",
    "sunaudiodev",
    "thread",
    "Tkinter",
    "toaiff",
    "urllib.quote",
    "urllib.quote_plus",
    "urllib.unquote",
    "urllib.unquote_plus",
    "urllib.urlencode",
    "urllib.urlopen",
    "urllib.urlretrieve",
    "urllib2",
    "urlparse",
    "user",
    "UserDict",
    "UserList",
    "UserString",
    "whichdb",
    # macos specfic removed in py3
    # https://docs.python.org/2.7/library/mac.html?highlight=removed
    "autoGIL",
    "Carbon",
    "ColorPicker",
    "EasyDialogs",
    "findertools",
    "FrameWork",
    "ic",
    "MacOS",
    "macostools",
    # macpython removed
    "aetools",
    "aepack",
    "aetypes",
    "applesingle",
    "buildtools",
    "cfmfile",
    "icopen",
    "macerros",
    "macresource",
    "PixMapWrapper",
    "videoreader",
    "W",
    # sgi removed
    "al",
    "imgfile",
    "jpeg",
    "cd",
    "sv",
    # confused names in Windows
    "multiprocessing.Pool",
    "multiprocessing.Process",
]
# old collections modules
MODULES.extend([f"collections.{name}" for name in collections.abc.__all__])
# exclusion by platform/os
if os.name != "nt":
    MODULES += (
        "msilib",
        "nturl2path",
        "pyHook",
        "pythoncom",
        "pywintypes",
        "winerror",
        "winsound",
        "win32api",
        "win32con",
        "win32com.shell",
        "win32gui",
        "win32event",
        "win32evtlog",
        "win32evtlogutil",
        "win32file",
        "win32pdh",
        "win32pipe",
        "win32process",
        "win32security",
        "win32service",
        "win32stat",
        "win32wnet",
        "wx.activex",
    )
if sys.platform != "darwin":
    MODULES += (
        "mac",
        "macpath",
        "macurl2path",
        "_scproxy",
    )
if os.name != "os2":
    MODULES += ("os2", "os2emxpath", "_emx_link")
if os.name != "ce":
    MODULES.append("ce")
if os.name != "riscos":
    MODULES += ("riscos", "riscosenviron", "riscospath", "rourl2path")
if "__pypy__" not in sys.builtin_module_names:
    MODULES.append("__pypy__")

MODULES.append("test")
