"""UI scale limits shared by startup and preferences."""


def minimum_ui_scale(qt_version):
    """Avoid Qt's pre-6.7 QPainter clamp of device pixel ratios below one.

    A global scale below one can work on a high-DPI display, then break
    painting when the window moves to a display using 100% system scaling.
    Use a display-independent limit so moving windows remains safe.
    """
    version = tuple(int(part) for part in qt_version.split(".")[:2])
    return 0.5 if version >= (6, 7) else 1.0
