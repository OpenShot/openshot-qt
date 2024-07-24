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

import os

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QTabWidget, QWidget

from classes.info import PATH
from ..base import BaseTheme


class CosmicTheme(BaseTheme):
    def __init__(self, app):
        super().__init__(app)

        from classes.app import get_app
        _ = get_app()._tr

        self.style_sheet = """
QMainWindow {
    background-color: #192332;
    color: #91C3FF;
}

QWidget#tutorial {
    background-color: #192332;
    border: 1.2px solid #0078FF;
    border-radius: 4px;
    padding: 20px;
}


QDialog {
    background-color: #192332;
    color: #91C3FF;
}

QWidget#Simple, QWidget#Advanced, QWidget#PreferencePanel {
    background-color: #141923;
    border: none;
}

QScrollArea {
    border: none;
}

QTabWidget {
    border: none;
}

QMenuBar {
    background-color: #283241;
    color: #91C3FF;
    padding: 0px;
    border: none;
}

QMenu {
    background-color: #141923;
    color: #91C3FF;
    padding: 6px;
    padding-left: 8px;
    padding-right: 8px;
    min-width: 40px;
    border: 1.2px solid #0078FF;
    border-radius: 3px 3px;
}

QMenu::item {
    padding: 6px 14px 6px 10px;
}

QMenu::item::checked {
    padding: 6px 12px 6px 20px;
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
    color: #91C3FF;
    padding-top: 10px;
    padding-bottom: 10px;
}

QToolBar#toolBar QToolButton:hover {
    background-color: #323C50;
}

QToolBar#toolBar QToolButton:pressed {
    background-color: #323C50;
}

QToolBar QToolButton:hover {
    background-color: #192332;
}

QToolBar QToolButton:pressed {
    background-color: #192332;
}

QToolBar#timelineToolbar {
    background-color: #192332;
    spacing: 0px;
    padding: 0px;
    border: none;
}

QToolBar#timelineToolbar QToolButton {
    color: #91C3FF;
    background-color: #141923;
    padding: 8px;
    margin-bottom: 4px;
    margin-right: 5px;
    margin-left: 5px;
    border-radius: 4px;
}

QToolBar#timelineToolbar QToolButton:hover {
    background-color: #283241;
}

QToolBar#timelineToolbar QToolButton:pressed {
    background-color: #353f4e;
}

QToolBar#timelineToolbar QToolButton:checked {
    background-color: #283241;
}

QPushButton#acceptButton {
    padding: 8px 16px 8px 12px;
    border-radius: 4px;
    background-color: #0078FF;
    color: #FFFFFF;
}

QPushButton#acceptButton:hover {
    background-color: #006EE6;
}

QPushButton {
    padding: 8px 16px 8px 12px;
    border-radius: 4px;
    background-color: #192332;
    color: #91C3FF;
}

QPushButton:hover {
    background-color: #283241 
}

QWidget#settingsContainer {
    background-color: #141923;
}

QWidget#scrollAreaWidgetContents {
    background-color: #141923;
}

QDockWidget {
    background-color: #141923;
    titlebar-close-icon: url({PATH}themes/cosmic/images/dock-close.svg);
    titlebar-normal-icon: url({PATH}themes/cosmic/images/dock-float.svg);
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

QDockWidget QWidget#dockFilesContents, QWidget#dockTransitionsContents, QWidget#dockEmojisContents, QWidget#dockEffectsContents, QWidget#dockCaptionContents, QWidget#dockVideoContents, QWidget#dockPropertiesContents {
    background-color: #141923;
    border-radius: 4px;
    margin-left: 16px;
    margin-right: 16px;
}

QDockWidget QWidget#dockTimelineContents {
    border-radius: 0px;
    margin-left: 0px;
    margin-right: 0px;
    padding: 0px;
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

QLineEdit#filesFilter, QLineEdit#effectsFilter, QLineEdit#transitionsFilter, QLineEdit#emojisFilter, QLineEdit#txtPropertyFilter {
    background-color: #192332;
    border-radius: 4px;
    padding: 6px;
    padding-left: 8px;
    padding-right: 8px;
}

QLineEdit#filesFilter:focus, QLineEdit#effectsFilter:focus, QLineEdit#transitionsFilter:focus, QLineEdit#emojisFilter:focus, QLineEdit#txtPropertyFilter:focus {
    border-width: 1.2px;
    border-style: solid;
    border-color: #0078FF;
}

QScrollBar:vertical {
    border: none;
    background: transparent;
    width: 8px;
}

QScrollBar::handle:vertical {
    background: rgba(145, 195, 255, 51);
    border-radius: 4px;
    min-height: 20px;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
    border: none;
    background: transparent;
}

QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: transparent;
}

QScrollBar:horizontal {
    border: none;
    background: transparent;
    height: 8px;
}

QScrollBar::handle:horizontal {
    background: rgba(145, 195, 255, 51);
    border-radius: 4px;
    min-width: 20px;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
    border: none;
    background: transparent;
}

QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background: transparent;
}

QComboBox {
    background-color: #121212;
    color: #FFFFFF;
    border-radius: 4px;
    padding: 6px;
    padding-left: 8px;
    padding-right: 8px;
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 40px;
    border: none;
}

QComboBox::down-arrow {
    image: url({PATH}themes/cosmic/images/dropdown-arrow.svg);
}

QComboBox QAbstractItemView {
    color: #FFFFFF;
    border: 1.2px solid #0078FF;
    border-radius: 3px 3px 0px 0px;
    padding: 6px;
    padding-left: 8px;
    padding-right: 8px;
    background-color: #141923;
    text-align: left;
}

QComboBox::item {
    height: 24px;
}

QComboBox::item:selected {
    border: none;
    text-align: left;
    background-color: #192332;
}

QComboBox::item:checked {
    font-weight: bold;
    background-color: #192332;
}

QComboBox::indicator::checked {
    image: url({PATH}themes/cosmic/images/dropdown-tick.svg);
}

QHeaderView::section {
    background-color: #141923;
    color: #91C3FF;
    padding: 4px;
    border: none;
}

QTableView {
    background-color: #141923;
    gridline-color: #141923;
}

QTreeView {
    background-color: #141923;
}

QListView {
    background-color: #141923;
}

QWidget#Details, QWidget#Output {
    background-color: #141923;
}

QWidget#Output QTextEdit {
    color: #91C3FF;
}

QToolBox::tab {
    color: #91C3FF;
}

QTabWidget QWidget#pageAdvancedOptions, QWidget#pageProfile, QWidget#pageImageSequenceSettings, QWidget#pageVideoSettings, QWidget#pageAudioSettings {
    background-color: #141923;
}

QTabWidget QWidget#pageVideoDetails, QWidget#pageVideoFormat, QWidget#pageAudioFormat, QWidget#pageFrameSettings {
    background-color: #141923;
}

QWidget#cutting QPushButton#btnStart,QPushButton#btnEnd  {
    border: 1px solid #006EE6;
}

QWidget#cutting QPushButton#btnStart:disabled,QPushButton#btnEnd:disabled {
    color: #666666;
    border: 1px solid #666666;
}

QWidget#cutting QPushButton#btnAddClip {
    background-color: #006EE6;
    color: #FFFFFF;
}

QWidget#cutting QPushButton#btnAddClip:disabled {
    background-color: #283241;
    color: #666666;
}

QWidget#aboutDialog QWidget#txtversion {
    background-color: #141923;
    padding-top: 10px;
    padding-bottom: 10px;
    border-radius: 4px;
}

.property_value {
    foreground-color: #0078FF;
    background-color: #283241;
}

.zoom_slider_playhead {
    background-color: #FABE0A;
}

QWidget#videoPreview {
    background-color: #141923;
}
        """
        path_unix_slashes = PATH.replace("\\", "/")
        self.style_sheet = f"""
QMessageBox QPushButton[text="&{_('Yes')}"] {{
    padding: 8px 16px 8px 12px;
    border-radius: 4px;
    background-color: #0078FF;
    color: #FFFFFF;
}}
        """ + self.style_sheet.replace("{PATH}", f"{path_unix_slashes}/")

    def apply_theme(self):
        super().apply_theme()

        from classes.app import get_app
        from classes import ui_util
        from classes.logger import log
        from PyQt5.QtWidgets import QStyleFactory
        from PyQt5.QtGui import QFont

        _ = get_app()._tr

        log.info("Setting Fusion dark palette")
        self.app.setStyle(QStyleFactory.create("Fusion"))
        dark_palette = ui_util.make_dark_palette(self.app.palette())
        self.app.setPalette(dark_palette)

        # Set font for all widgets
        font = QFont("Ubuntu")
        font.setPointSizeF(8)
        self.app.setFont(font)

        # Move tabs to top
        self.app.window.setTabPosition(Qt.DockWidgetArea.TopDockWidgetArea, QTabWidget.North)

        # Set dock widget content margins to 0
        self.set_dock_margins([16, 0, 16, 0])
        self.set_dock_margins([0, 0, 0, 0], [0, 10, 0, 0], "dockTimelineContents")

        # Apply new stylesheet
        self.app.setStyleSheet(self.style_sheet)

        # Create a transparent spacer widget
        spacer = QWidget(self.app.window)
        spacer.setFixedSize(15, 1)
        spacer.setStyleSheet("background: transparent;")

        # Main toolbar buttons
        toolbar_buttons = [
            {"action": self.app.window.actionNew, "icon": "themes/cosmic/images/tool-new-project.svg", "style": Qt.ToolButtonTextBesideIcon},
            {"action": self.app.window.actionOpen, "icon": "themes/cosmic/images/tool-open-project.svg", "style": Qt.ToolButtonTextBesideIcon},
            {"action": self.app.window.actionImportFiles, "icon": "themes/cosmic/images/tool-import-files.svg", "style": Qt.ToolButtonTextBesideIcon},
            {"action": self.app.window.actionProfile, "icon": "themes/cosmic/images/tool-profile.svg", "style": Qt.ToolButtonTextBesideIcon},
            {"expand": True},
            {"action": self.app.window.actionSave, "icon": "themes/cosmic/images/tool-save-project.svg", "style": Qt.ToolButtonTextBesideIcon},
            {"action": self.app.window.actionExportVideo, "icon": "themes/cosmic/images/tool-export.svg", "style": Qt.ToolButtonTextBesideIcon, "stylesheet": "QToolButton {  background-color: #0078FF; color: #FFFFFF; }"},
            {"action": self.app.window.actionUpdate, "icon": "themes/cosmic/images/warning.svg", "visible": False, "style": Qt.ToolButtonTextBesideIcon, "stylesheet": "QToolButton {  background-color: #141923; color: #FABE0A; }"}
        ]
        self.set_toolbar_buttons(self.app.window.toolBar, icon_size=20, settings=toolbar_buttons)

        # Timeline toolbar buttons
        timeline_buttons = [
            {"action": self.app.window.actionAddTrack, "icon": "themes/cosmic/images/tool-add-track.svg", "style": Qt.ToolButtonTextBesideIcon, "stylesheet": "QToolButton { margin-left: 15px; }"},
            {"action": self.app.window.actionUndo, "icon": "themes/cosmic/images/tool-undo.svg", "style": Qt.ToolButtonIconOnly, "stylesheet": "QToolButton { margin-right: 0px; border-bottom-right-radius: 0px; border-top-right-radius: 0px; }"},
            {"action": self.app.window.actionRedo, "icon": "themes/cosmic/images/tool-redo.svg", "style": Qt.ToolButtonIconOnly, "stylesheet": "QToolButton { margin-left: 0px; border-bottom-left-radius: 0px; border-top-left-radius: 0px; }"},
            {"action": self.app.window.actionSnappingTool, "icon": "themes/cosmic/images/tool-snapping.svg", "style": Qt.ToolButtonIconOnly, "stylesheet": "QToolButton { margin-right: 0px; border-bottom-right-radius: 0px; border-top-right-radius: 0px; }"},
            {"action": self.app.window.actionRazorTool, "icon": "themes/cosmic/images/tool-razor.svg", "style": Qt.ToolButtonIconOnly, "stylesheet": "QToolButton { margin-left: 0px; border-bottom-left-radius: 0px; border-top-left-radius: 0px; }"},
            {"action": self.app.window.actionAddMarker, "icon": "themes/cosmic/images/tool-add-marker.svg", "style": Qt.ToolButtonTextBesideIcon, "stylesheet": "QToolButton { margin-right: 0px; border-bottom-right-radius: 0px; border-top-right-radius: 0px; }"},
            {"action": self.app.window.actionPreviousMarker, "icon": "themes/cosmic/images/tool-prev-marker.svg", "style": Qt.ToolButtonIconOnly, "stylesheet": "QToolButton { margin-left: 0px; border-bottom-left-radius: 0px; border-top-left-radius: 0px; margin-right: 0px; border-bottom-right-radius: 0px; border-top-right-radius: 0px; }"},
            {"action": self.app.window.actionNextMarker, "icon": "themes/cosmic/images/tool-next-marker.svg", "style": Qt.ToolButtonIconOnly, "stylesheet": "QToolButton { margin-left: 0px; border-bottom-left-radius: 0px; border-top-left-radius: 0px; }"},
            {"action": self.app.window.actionCenterOnPlayhead, "icon": "themes/cosmic/images/tool-center-playhead.svg", "style": Qt.ToolButtonIconOnly, "stylesheet": "QWidget { margin-right: 10px; }"},
            {"widget": self.app.window.sliderZoomWidget},
            {"widget": spacer}
        ]
        self.set_toolbar_buttons(self.app.window.timelineToolbar, icon_size=12, settings=timeline_buttons)

        # Video toolbar
        toolbar_buttons = [
            {"expand": True},
            {"action": self.app.window.actionJumpStart, "icon": "themes/cosmic/images/tool-media-skip-back.svg", "style": Qt.ToolButtonIconOnly},
            {"action": self.app.window.actionRewind, "icon": "themes/cosmic/images/tool-media-rewind.svg", "style": Qt.ToolButtonIconOnly},
            {"action": self.app.window.actionPlay, "icon": "themes/cosmic/images/tool-media-play.svg", "style": Qt.ToolButtonIconOnly},
            {"action": self.app.window.actionFastForward, "icon": "themes/cosmic/images/tool-media-forward.svg", "style": Qt.ToolButtonIconOnly},
            {"action": self.app.window.actionJumpEnd, "icon": "themes/cosmic/images/tool-media-skip-forward.svg", "style": Qt.ToolButtonIconOnly},
            {"expand": True}
        ]
        self.set_toolbar_buttons(self.app.window.videoToolbar, icon_size=32, settings=toolbar_buttons)

        # Apply timeline theme
        self.app.window.timeline.apply_theme("""
            body {
              background: #141923;
            }
            ::-webkit-scrollbar {
              width: 8px;
              height: 8px;
            }
            ::-webkit-scrollbar-thumb {
                background: rgba(145, 195, 255, .2);
                border-radius: 4px;
            }
            ::-webkit-scrollbar-track {
              background: #141923;
              box-shadow: none;
            }
            .track_name {
              background: #192332;
              border-top-left-radius: 0px;
              border-bottom-left-radius: 0px;
              border: 1px solid #192332;
              border-left: 4px solid #0078FF;
              box-shadow: none;
              margin-left: 0px;
              height: 48px;
            }
            .track_top {
              padding-top: 4px;
              padding-left: 10px;
              background: none;
            }
            .track_label {
              text-shadow: none;
            }
            .track {
              background: #283241;
              border: 1px solid #283241;
              border-radius: 0px;
              height: 48px;
            }
            .transition {
              height: 48px;
              min-height: 48px;
            }
            .transition_top {
              background: none;
            }
            .clip {
              background: #192332;
              border: 1px solid #0078FF;
              box-sizing: border-box;
              height: 48px;
              min-height: 48px;
              display: flex;
            }
            .clip_label {
              text-shadow: 1px 1px 1px black;
            }
            .clip_top {
              background: none;
              position: absolute;
              top: 0;
              width: 100%;
              display: flex;
              justify-content: flex-start;
              align-items: center;
              z-index: 2;
            }
            .thumb-container {
              margin-top: 0px;
            }
            .audio-container {
              margin-top: 0px;
              object-fit: cover;
              align-self: flex-start;
              z-index: 0;
            }
            .thumb-container, .audio-container {
              position: absolute;
              top: 0;
              left: 0;
              right: 0;
              bottom: 0;
              overflow: hidden;
            }
            .audio {
              border-radius: 8px;
            }
            .thumb {
              border-radius: 8px;
              margin: 0px;
              height: 100%;
              object-fit: cover;
              align-self: flex-start;
              z-index: 1;
            }
            .ui-selecting {
              border: 1px solid yellow !important;
            }
            .ui-selected {
              border: 1px solid red !important;
            }
            .playhead-top {
              margin-left: -6px;
              margin-top: 20px;
              width: 12px;
              height: 188px;
              background-image: url(../themes/cosmic/images/playhead.svg);
            }
            .playhead-line {
              z-index: 9999;
              position: absolute;
              height: 316px;
              top: 0;
              width: 2px;
              background-color: #FABE0A;
              margin: -1px;
            }
            .point_bezier {
              background-image: url(../themes/cosmic/images/keyframe-bezier.svg);
            }
            .point_linear {
              background-image: url(../themes/cosmic/images/keyframe-linear.svg);
            }
            .point_constant {
              background-image: url(../themes/cosmic/images/keyframe-constant.svg);
            }
            .marker_icon {
              background-image: url(../themes/cosmic/images/marker.svg);
            }
        """)

    def togglePlayIcon(self, isPlay):
        """ Toggle the play icon from play to pause and back """
        button = self.app.window.videoToolbar.widgetForAction(self.app.window.actionPlay)
        if button:
            if not isPlay:
                play_icon_path = os.path.join(PATH, "themes/cosmic/images/tool-media-play.svg")
                button.setIcon(QIcon(play_icon_path))
            else:
                pause_icon_path = os.path.join(PATH, "themes/cosmic/images/tool-media-pause.svg")
                button.setIcon(QIcon(pause_icon_path))
