"""
 @file
 @brief This file contains the base theme. Each theme starts with these settings and overrides certain things.
 @author Jonathan Thomas <jonathan@openshot.org>

 @section LICENSE

 Copyright (c) 2008-2024 OpenShot Studios, LLC
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
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QTabWidget
from themes.manager import ThemeManager


class BaseTheme:
    def __init__(self, app):
        self.style_sheet = ""
        self.app = app

    def set_dock_content_margins(self, margins=None):
        # Set content margins on dock widgets
        if margins is None:
            margins = [0, 0, 0, 0]

        from PyQt5.QtWidgets import QWidget
        for dock in self.app.window.getDocks():
            for child in dock.children():
                if isinstance(child, QWidget):
                    if child.objectName().startswith("dock") and child.objectName().endswith("Contents"):
                        child.setContentsMargins(*margins)

    def apply_theme(self):
        # Get initial style and palette
        manager = ThemeManager()

        # Apply the stylesheet to the entire application
        self.app.setStyle(manager.original_style)
        self.app.setPalette(manager.original_palette)
        self.app.setStyleSheet(self.style_sheet)

        # Hide main window status bar
        self.app.window.statusBar.hide()

        from classes import info, ui_util
        from classes.logger import log
        from PyQt5.QtGui import QFont, QFontDatabase

        # Load embedded font
        font_path = os.path.join(info.IMAGES_PATH, "fonts", "Ubuntu-R.ttf")
        if os.path.exists(font_path):
            log.info("Setting font to %s", font_path)
            try:
                font_id = QFontDatabase.addApplicationFont(font_path)
                font_family = QFontDatabase.applicationFontFamilies(font_id)[0]
                font = QFont(font_family)
                font.setPointSizeF(10.5)
                self.app.setFont(font)
            except Exception:
                log.warning("Error setting Ubuntu-R.ttf QFont", exc_info=1)

        # Load Icon theme if not set by OS
        ui_util.load_icon_theme()

        # Set dock widget content margins to 0
        self.set_dock_content_margins()

        # Move tabs to bottom
        self.app.window.setTabPosition(Qt.TopDockWidgetArea, QTabWidget.South)

        # Apply timeline theme
        self.app.window.timeline.apply_theme("")
