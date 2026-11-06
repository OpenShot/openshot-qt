"""Test package bootstrap for headless Qt environments."""

import os

from qt_api import QCoreApplication, Qt


# Package builders run without an X server, so use the minimal backend and
# software OpenGL for compatibility with older Qt stacks. Without enable_fonts
# the minimal backend has no font database and renders all text blank.
os.environ.setdefault("QT_QPA_PLATFORM", "minimal:enable_fonts")
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("LIBGL_ALWAYS_SOFTWARE", "1")

# Qt requires this attribute before any Qt application is created.
QCoreApplication.setAttribute(Qt.AA_ShareOpenGLContexts, True)
