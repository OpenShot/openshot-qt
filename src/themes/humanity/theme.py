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


class HumanityDarkTheme(BaseTheme):
    def __init__(self, app):
        super().__init__(app)
        self.style_sheet = """
QToolTip {
    color: #ffffff;
    background-color: #2a82da;
    border: 0px solid white;
}

QComboBox::item {
    height: 24px;
}

QComboBox {
    combobox-popup: 0;
}

.property_value {
    foreground-color: #217dd4;
    background-color: #565656;
}

.zoom_slider_playhead {
    background-color: #ff0024;
}

QWidget#videoPreview {
    background-color: #191919;
}

QLabel#lblMissingFileHint,
QLabel#lblMissingFilePath {
    color: #b8b8b8;
}

QFrame#recordingCard {
    background-color: #303030;
    border: 1px solid #555b63;
    border-radius: 8px;
}
QFrame#recordingCard[checked="true"] {
    background-color: #3a4655;
    border: 2px solid #2f8cff;
}
QFrame#recordingCard[available="false"] {
    background-color: #292929;
    border: 1px solid #454545;
}
QLabel#recordingCardIcon {
    color: #70adf5;
    font-size: 22px;
}
QLabel#recordingCardTitle {
    color: #f1f1f1;
    font-size: 14px;
    font-weight: 700;
}
QLabel#recordingCardSubtitle {
    color: #b8bec8;
    font-size: 11px;
}
QFrame#recordingSection {
    background-color: #292929;
    border: 1px solid #50555c;
    border-radius: 8px;
}
QFrame#recordingSection[active="true"] {
    border-color: #4779b8;
}
QFrame#recordingSection[active="false"] {
    background-color: #252525;
    color: #858b94;
}
QLabel#recordingSectionIcon {
    color: #78aef0;
    font-size: 16px;
}
QLabel#recordingSectionTitle {
    color: #f1f1f1;
    font-weight: 700;
}
QPushButton#recordingAdvancedLink {
    color: #4f9aff;
    border: none;
    padding: 0;
    text-align: right;
}
QPushButton#recordingAdvancedLink:hover {
    color: #b8d7ff;
    text-decoration: underline;
}
QPushButton#recordingSegment {
    color: #d0d3d8;
    background-color: #303030;
    border: 1px solid #555b63;
    border-radius: 6px;
    padding: 7px 10px;
}
QPushButton#recordingSegment[position="left"] {
    border-top-right-radius: 0;
    border-bottom-right-radius: 0;
}
QPushButton#recordingSegment[position="right"] {
    border-left: none;
    border-top-left-radius: 0;
    border-bottom-left-radius: 0;
}
QPushButton#recordingSegment:checked {
    color: #a9d0ff;
    background-color: #3a526f;
    border: 1px solid #2f8cff;
}
        """

    def apply_theme(self):
        super().apply_theme()

        from classes import ui_util
        from classes.logger import log
        from qt_api import QStyleFactory

        log.info("Setting Fusion dark palette")
        self.app.setStyle(QStyleFactory.create("Fusion"))
        dark_palette = ui_util.make_dark_palette(self.app.palette())
        self.app.setPalette(dark_palette)
        self.app.setStyleSheet(self.compose_stylesheet())

        from .styles import HumanityDarkTimelineTheme
        self.app.window.timeline.apply_theme(HumanityDarkTimelineTheme())

        # Emit signal
        self.app.window.ThemeChangedSignal.emit(self)

class Retro(BaseTheme):
    def __init__(self, app):
        super().__init__(app)
        self.style_sheet = """
QComboBox::item {
    height: 24px;
}

QMainWindow::separator:hover {
    background: #dedede;
}

.property_value {
    foreground-color: #217dd4;
    background-color: #7f7f7f;
}

.zoom_slider_playhead {
    background-color: #ff0024;
}

QWidget#videoPreview {
    background-color: #dedede;
}

QLabel#lblMissingFileHint,
QLabel#lblMissingFilePath {
    color: #5a5a5a;
}

QFrame#recordingCard {
    background-color: #e5e7ea;
    border: 1px solid #a5abb3;
    border-radius: 8px;
}
QFrame#recordingCard[checked="true"] {
    background-color: #d7e8fb;
    border: 2px solid #287dcc;
}
QFrame#recordingCard[available="false"] {
    background-color: #ededed;
    border: 1px solid #c4c4c4;
}
QLabel#recordingCardIcon {
    color: #287dcc;
    font-size: 22px;
}
QLabel#recordingCardTitle {
    color: #25282d;
    font-size: 14px;
    font-weight: 700;
}
QLabel#recordingCardSubtitle {
    color: #586473;
    font-size: 11px;
}
QFrame#recordingSection {
    background-color: #eeeeee;
    border: 1px solid #a9adb3;
    border-radius: 8px;
}
QFrame#recordingSection[active="true"] {
    border-color: #4a8fca;
}
QFrame#recordingSection[active="false"] {
    background-color: #e4e4e4;
    color: #777d84;
}
QLabel#recordingSectionIcon {
    color: #287dcc;
    font-size: 16px;
}
QLabel#recordingSectionTitle {
    color: #25282d;
    font-weight: 700;
}
QPushButton#recordingAdvancedLink {
    color: #176fba;
    border: none;
    padding: 0;
    text-align: right;
}
QPushButton#recordingAdvancedLink:hover {
    color: #0c4f89;
    text-decoration: underline;
}
QPushButton#recordingSegment {
    color: #30343a;
    background-color: #f7f7f7;
    border: 1px solid #a9adb3;
    border-radius: 6px;
    padding: 7px 10px;
}
QPushButton#recordingSegment[position="left"] {
    border-top-right-radius: 0;
    border-bottom-right-radius: 0;
}
QPushButton#recordingSegment[position="right"] {
    border-left: none;
    border-top-left-radius: 0;
    border-bottom-left-radius: 0;
}
QPushButton#recordingSegment:checked {
    color: #155f9e;
    background-color: #d7e8fb;
    border: 1px solid #287dcc;
}

QComboBox {
    combobox-popup: 0;
}
        """

    def apply_theme(self):
        super().apply_theme()

        from .styles import RetroTimelineTheme
        self.app.window.timeline.apply_theme(RetroTimelineTheme())

        # Emit signal
        self.app.window.ThemeChangedSignal.emit(self)
