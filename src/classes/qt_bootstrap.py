"""
 @file
 @brief Shared pre-QApplication display setup for the editor and CLI sessions.

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
        from OpenGL import GL  # pylint: disable=unused-import  # noqa: F401 - Initialize OpenGL before Qt.
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
