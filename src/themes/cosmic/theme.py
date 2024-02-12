"""
 @file
 @brief This file contains a theme's colors and UI dimensions
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

from ..base import BaseTheme
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QTabWidget


class CosmicTheme(BaseTheme):
    def __init__(self, app):
        super().__init__(app)
        self.style_sheet = """
QMainWindow {
    background-color: #192332;
    color: #91C3FF;
}

QWidget {
    font-family: Ubuntu;
    font-size: 10px;
    font-style: normal;
    font-weight: 500;
}

QMenuBar {
    background-color: #283241;
    color: #91C3FF;
    padding: 6px;
    border: none;
}

QMenu {
    background-color: #141923;
    color: #91C3FF;
    padding: 6px;
    min-width: 160px;
}

QMenu::item {
    padding: 6px;
}

QMenu::item:selected {
    background-color: #192332;
    color: #ffffff;
}

QMenu::separator {
    height: 8px;
    background-color: #141923;
}

QToolBar#toolBar {
    background-color: #283241;
    spacing: 0px;
    padding: 0px;
    border: none;
}

QToolBar#toolBar QToolButton {
    background-color: #283241;
    margin: 2px;
    padding: 4px;
}

QToolBar#toolBar QToolButton:hover {
    background-color: #323C50;
}

QToolBar#toolBar QToolButton:pressed {
    background-color: #323C50;
}

QToolBar QToolButton {
    color: #91C3FF;
    padding: 6px;
    padding-left: 8px;
    padding-right: 10px;
}

QToolBar QToolButton:hover {
    background-color: #192332;
}

QToolBar QToolButton:pressed {
    background-color: #192332;
}

QDockWidget {
    background-color: #141923;
    titlebar-close-icon: url(themes/cosmic/images/dock-close.svg);
    titlebar-normal-icon: url(themes/cosmic/images/dock-float.svg);
    color: #91C3FF;
    font-weight: 500;
    padding: 16px;
}

QDockWidget::title {
    text-align: left;
    margin-top: 18px;
    margin-bottom: 18px;
    margin-left: 16px;
}

QDockWidget QWidget {
    border: none;
}

QDockWidget QWidget#dockFilesContents, QWidget#dockTransitionsContents, QWidget#dockEmojisContents, QWidget#dockEffectsContents, QWidget#dockCaptionContents, QWidget#dockVideoContents, QWidget#dockPropertiesContents, QWidget#dockTimelineContents {
    background-color: #141923;
    border-radius: 4px;
    margin-left: 16px;
    margin-right: 16px;
}

QDockWidget::close-button, QDockWidget::float-button {
    icon-size: 32px;
}

QDockWidget::close-button:hover, QDockWidget::float-button:hover {
}

QDockWidget::close-button:pressed, QDockWidget::float-button:pressed {
}

QTabBar {
    background-color: transparent;
    border: none;
}

QTabBar::tab {
    margin-left: 16px;
    height: 32px;
    color: rgba(145, 195, 255, 0.4);
    background-color: transparent;
}

QTabBar::tab:selected {
    color: rgba(145, 195, 255, 1.0);
}

QLineEdit#filesFilter, QLineEdit#effectsFilter, QLineEdit#transitionsFilter, QLineEdit#emojisFilter {
    background-color: #192332;
    border-radius: 4px;
    padding: 6px;
    padding-left: 8px;
    padding-right: 8px;
}

QLineEdit#filesFilter:focus, QLineEdit#effectsFilter:focus, QLineEdit#transitionsFilter:focus, QLineEdit#emojisFilter:focus {
    border-width: 1.2px;
    border-style: solid;
    border-color: #0078FF;
}
        """

    def apply_theme(self):
        super().apply_theme()

        from classes import ui_util
        from classes.logger import log
        from PyQt5.QtWidgets import QStyleFactory

        log.info("Setting Fusion dark palette")
        self.app.setStyle(QStyleFactory.create("Fusion"))
        dark_palette = ui_util.make_dark_palette(self.app.palette())
        self.app.setPalette(dark_palette)

        # Move tabs to top
        self.app.window.setTabPosition(Qt.TopDockWidgetArea, QTabWidget.North)

        # Set dock widget content margins to 0
        self.set_dock_content_margins([16, 0, 16, 0])

        # Apply new stylesheet
        self.app.setStyleSheet(self.style_sheet)

