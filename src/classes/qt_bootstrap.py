"""Shared pre-QApplication display setup for the editor and CLI sessions."""
import json
import logging
import os


def configure_qt():
    """Apply the editor's UI scale and high-DPI attributes before creating Qt widgets."""
    # Load user-configured UI scale before importing the Qt binding
    scale = 1.0
    logger = logging.getLogger(__name__)

    settings_path = os.path.join(os.path.expanduser("~/.openshot_qt"), "openshot.settings")

    try:
        if os.path.exists(settings_path):
            with open(settings_path, "r", encoding="utf-8") as fh:
                for item in json.load(fh):
                    if item.get("setting") == "ui-scale":
                        scale = float(item.get("value", scale))
                        break
    except Exception as exc:
        logger.warning("Failed to read UI scale from %s: %s", settings_path, exc, exc_info=True)
    from qt_api import QtCore, QtWidgets, minimum_ui_scale

    # Qt reads this when QApplication is created. Older Qt painters cannot shrink
    # below a device pixel ratio of one, even though window geometry can do so.
    requested_scale = scale
    scale = max(minimum_ui_scale(), min(3.0, scale))
    if scale != requested_scale:
        logger.warning("UI scale %s is unsupported by Qt %s; using %s",
                       requested_scale, QtCore.qVersion(), scale)
    if scale != 1.0 or scale != requested_scale:
        os.environ["QT_SCALE_FACTOR"] = str(scale)

    Qt = QtCore.Qt
    QApplication = QtWidgets.QApplication

    try:
        # This must be done before creating QApplication
        QApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
        from OpenGL import GL  # noqa
    except (ImportError, AttributeError):
        pass

    try:
        # PassThrough lets Qt use the exact QT_SCALE_FACTOR value (e.g. 1.5) without rounding
        # to the nearest integer (e.g. 2.0).
        os.environ['QT_SCALE_FACTOR_ROUNDING_POLICY'] = "PassThrough"

        # Enable High-DPI resolutions
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)
    except AttributeError:
        pass  # Quietly fail for older Qt5 versions
