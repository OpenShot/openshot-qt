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
/* Modern dark base */
QMainWindow {
    background-color: #0B0E14;
    color: #E6E6EB;
}

QWidget {
    color: #E6E6EB;
    font-family: Inter, "Segoe UI", Roboto, sans-serif;
    font-size: 11pt;
}

QWidget#tutorial {
    background-color: #151A23;
    border: 1px solid rgba(230, 230, 235, 0.2);
    border-radius: 8px;
    padding: 20px;
}

QLabel#lblTutorialText {
    font-size: 14px;
}

QCheckBox#checkboxMetrics {
    font-size: 14px;
}

QWidget#tutorial QPushButton#NextTip {
    background-color: #151A23;
    border-radius: 10px;
    padding: 8px 14px;
    font-size: 12px;
}

QWidget#tutorial QPushButton#HideTutorial {
    background-color: #151A23;
    border-radius: 10px;
    padding: 8px 14px;
    font-size: 12px;
}

QDialog {
    background-color: #0B0E14;
    color: #E6E6EB;
}

QWidget#Simple, QWidget#Advanced, QWidget#PreferencePanel {
    background-color: #151A23;
    border: none;
}

QScrollArea {
    border: none;
}

QTabWidget {
    border: none;
}

QMenuBar {
    background-color: #151A23;
    color: #E6E6EB;
    padding: 0px;
    border: none;
}

QMenu {
    background-color: #151A23;
    color: #E6E6EB;
    padding: 8px;
    padding-left: 10px;
    padding-right: 10px;
    min-width: 40px;
    border: 1px solid rgba(230, 230, 235, 0.12);
    border-radius: 8px;
}

QMenu::item {
    padding: 8px 16px 8px 12px;
    border-radius: 6px;
}

QMenu::item::checked {
    padding: 8px 12px 8px 20px;
}

QMenu::item:selected {
    background-color: #1E2433;
    color: #ffffff;
}

QMenu::separator {
    height: 8px;
    background-color: transparent;
}

QToolBar#toolBar {
    background-color: #151A23;
    spacing: 0px;
    padding: 0px;
    border: none;
}

QToolBar#toolBar QToolButton {
    background-color: transparent;
    color: #E6E6EB;
    padding: 10px 12px;
    border: none;
    border-radius: 8px;
}

QToolBar#toolBar QToolButton:hover {
    background-color: #1E2433;
}

QToolBar#toolBar QToolButton:pressed {
    background-color: #2A3147;
}

QToolBar QToolButton:hover {
    background-color: #1E2433;
}

QToolBar QToolButton:pressed {
    background-color: #2A3147;
}

QToolBar#timelineToolbar {
    background-color: #151A23;
    spacing: 0px;
    padding: 0px;
    border: none;
}

QToolBar#timelineToolbar QToolButton {
    color: #E6E6EB;
    background-color: #151A23;
    padding: 8px 12px;
    margin-bottom: 4px;
    margin-right: 5px;
    margin-left: 5px;
    border-radius: 8px;
}

QToolBar#timelineToolbar QToolButton:hover {
    background-color: #1E2433;
}

QToolBar#timelineToolbar QToolButton:pressed {
    background-color: #2A3147;
}

QToolBar#timelineToolbar QToolButton:checked {
    background-color: #1E2433;
}

QPushButton#acceptButton {
    padding: 8px 14px;
    border-radius: 10px;
    background-color: #6366F1;
    color: #FFFFFF;
}

QPushButton#acceptButton:hover {
    background-color: #818CF8;
}

QPushButton#acceptButton:pressed {
    background-color: #4F46E5;
}

QPushButton {
    padding: 8px 14px;
    border-radius: 10px;
    background-color: #151A23;
    color: #E6E6EB;
}

QPushButton:hover {
    background-color: #1E2433;
}

QPushButton:pressed {
    background-color: #2A3147;
}

QWidget#settingsContainer {
    background-color: #151A23;
}

QWidget#scrollAreaWidgetContents {
    background-color: #151A23;
}

QPushButton#dock-close-button {
    image: url({PATH}themes/cosmic/images/dock-close.svg);
    padding: 0px;
    padding-top: 2px;
    padding-bottom: 2px;
    margin: 0px;
    margin-right: 16px;
    width: 16px;
    height: 16px;
}
QPushButton#dock-float-button {
    image: url({PATH}themes/cosmic/images/dock-float.svg);
    padding: 0px;
    padding-top: 2px;
    padding-bottom: 2px;
    margin: 0px;
    width: 16px;
    height: 16px;
}

QLabel#dock-title-label {
    color: #E6E6EB;
    font-weight: 500;
    padding: 16px;
}

QLabel#dock-title-handle {
    padding-left: 16px;
    qproperty-pixmap: url({PATH}themes/cosmic/images/dock-move.svg);
}

QDockWidget {
    background-color: #151A23;
    titlebar-close-icon: url({PATH}themes/cosmic/images/dock-close.svg);
    titlebar-normal-icon: url({PATH}themes/cosmic/images/dock-float.svg);
    color: #E6E6EB;
    font-weight: 500;
    padding: 16px;
}

QDockWidget QWidget {
    border: none;
}

QDockWidget QWidget#dockFilesContents, QWidget#dockTransitionsContents, QWidget#dockEmojisContents, QWidget#dockEffectsContents, QWidget#dockCaptionContents, QWidget#dockVideoContents, QWidget#dockPropertiesContents {
    background-color: #151A23;
    border-radius: 8px;
    margin-left: 16px;
    margin-right: 16px;
}

QDockWidget QWidget#dockTimelineContents {
    border-radius: 0px;
    margin-left: 0px;
    margin-right: 0px;
    padding: 0px;
}

QTabBar {
    border: none;
    qproperty-drawBase: 0;
    margin: 0px;
    padding: 0px;
}

QTabBar::tab {
    height: 16px;
    border: none;
    margin-left: 16px;
    margin-top: 16px;
    margin-bottom: 0px;
    padding-bottom: 0px;
    color: rgba(230, 230, 235, 0.5);
}

QTabWidget#exportTabs QTabBar::tab,
QTabWidget#tabCategories QTabBar::tab,
QTabWidget#tabCredits QTabBar::tab{
    margin-bottom: 10px;
}

QTabBar::tab:selected {
    color: #E6E6EB;
}

QLineEdit#filesFilter, QLineEdit#effectsFilter, QLineEdit#transitionsFilter, QLineEdit#emojisFilter, QLineEdit#txtPropertyFilter {
    background-color: #151A23;
    color: #E6E6EB;
    border: 1px solid rgba(230, 230, 235, 0.12);
    border-radius: 8px;
    padding: 8px 10px;
    padding-left: 10px;
    padding-right: 10px;
}

QLineEdit#filesFilter:focus, QLineEdit#effectsFilter:focus, QLineEdit#transitionsFilter:focus, QLineEdit#emojisFilter:focus, QLineEdit#txtPropertyFilter:focus {
    border-width: 1px;
    border-style: solid;
    border-color: #6366F1;
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
    background: rgba(230, 230, 235, 0.25);
    border-radius: 6px;
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
    background-color: #151A23;
    color: #E6E6EB;
    border: 1px solid rgba(230, 230, 235, 0.12);
    border-radius: 8px;
    padding: 8px 10px;
    padding-left: 10px;
    padding-right: 10px;
    combobox-popup: 0;
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
    color: #E6E6EB;
    border: 1px solid rgba(230, 230, 235, 0.12);
    border-radius: 8px;
    padding: 8px;
    padding-left: 10px;
    padding-right: 10px;
    background-color: #151A23;
    text-align: left;
}

QComboBox::item {
    height: 28px;
    padding: 4px 8px;
    border-radius: 6px;
}

QComboBox::item:selected {
    border: none;
    text-align: left;
    background-color: #1E2433;
}

QComboBox::item:checked {
    font-weight: bold;
    background-color: #1E2433;
}

QComboBox::indicator::checked {
    image: url({PATH}themes/cosmic/images/dropdown-tick.svg);
}

QHeaderView::section {
    background-color: #151A23;
    color: #E6E6EB;
    padding: 8px 4px;
    border: none;
}

QTableView {
    background-color: #151A23;
    gridline-color: rgba(230, 230, 235, 0.08);
}

QTreeView {
    background-color: #151A23;
}

QListView {
    background-color: #151A23;
}

QWidget#Details, QWidget#Output {
    background-color: #151A23;
}

QWidget#Output QTextEdit {
    color: #E6E6EB;
}

QToolBox::tab {
    color: #E6E6EB;
    border-top: 1px solid rgba(230, 230, 235, 0.12);
}

QTabWidget QWidget#pageAdvancedOptions, QWidget#pageProfile, QWidget#pageImageSequenceSettings, QWidget#pageVideoSettings, QWidget#pageAudioSettings {
    background-color: #151A23;
}

QTabWidget QWidget#pageVideoDetails, QWidget#pageVideoFormat, QWidget#pageAudioFormat, QWidget#pageFrameSettings {
    background-color: #151A23;
}

QWidget#cutting QPushButton#btnStart,QPushButton#btnEnd  {
    border: 1px solid rgba(99, 102, 241, 0.5);
    border-radius: 10px;
}

QWidget#cutting QPushButton#btnStart:disabled,QPushButton#btnEnd:disabled {
    color: #6B7280;
    border: 1px solid rgba(230, 230, 235, 0.2);
}

QWidget#cutting QPushButton#btnAddClip {
    background-color: #6366F1;
    color: #FFFFFF;
    border-radius: 10px;
}

QWidget#cutting QPushButton#btnAddClip:disabled {
    background-color: #1E2433;
    color: #6B7280;
}

.property_value {
    foreground-color: #6366F1;
    background-color: #1E2433;
}

.zoom_slider_playhead {
    background-color: #6366F1;
}

QWidget#videoPreview {
    background-color: #151A23;
}

/* Zenvi Assistant chat: modern dark */
QDockWidget#AIChatWindow QWidget#AIChatWindowContents {
    background-color: #151A23;
}
QDockWidget#AIChatWindow QFrame#chatPreamble {
    background-color: #1E2433;
    border: 1px solid rgba(230, 230, 235, 0.12);
    border-radius: 8px;
}
QDockWidget#AIChatWindow QLabel#chatPreambleLabel {
    color: #E6E6EB;
    font-size: 12px;
}
QDockWidget#AIChatWindow QTextEdit#chatBox {
    background-color: #151A23;
    color: #E6E6EB;
    border: 1px solid rgba(230, 230, 235, 0.12);
    border-radius: 8px;
    padding: 8px;
}
QDockWidget#AIChatWindow QTextEdit#msgInput {
    background-color: #151A23;
    color: #E6E6EB;
    border: 1px solid rgba(230, 230, 235, 0.12);
    border-radius: 8px;
    padding: 8px;
}
QDockWidget#AIChatWindow QPushButton#sendBtn,
QDockWidget#AIChatWindow QPushButton#clearBtn {
    background-color: #151A23;
    color: #E6E6EB;
    border: 1px solid rgba(230, 230, 235, 0.12);
    border-radius: 10px;
    padding: 8px 14px;
}
QDockWidget#AIChatWindow QPushButton#sendBtn:hover,
QDockWidget#AIChatWindow QPushButton#clearBtn:hover {
    background-color: #1E2433;
    color: #ffffff;
}
QDockWidget#AIChatWindow QPushButton#sendBtn:pressed,
QDockWidget#AIChatWindow QPushButton#clearBtn:pressed {
    background-color: #2A3147;
}
QDockWidget#AIChatWindow QComboBox#modelCombo {
    background-color: #151A23;
    color: #E6E6EB;
    border: 1px solid rgba(230, 230, 235, 0.12);
    border-radius: 8px;
}
        """
        path_unix_slashes = PATH.replace("\\", "/")
        self.style_sheet = f"""
QMessageBox QPushButton[text="&{_('Yes')}"] {{
    padding: 8px 14px;
    border-radius: 10px;
    background-color: #6366F1;
    color: #FFFFFF;
}}

QMessageBox QPushButton[text="&{_('Cancel')}"] {{
    qproperty-icon: none;
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
        self.app.window.setTabPosition(Qt.TopDockWidgetArea, QTabWidget.North)

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
            {"action": self.app.window.actionExportVideo, "icon": "themes/cosmic/images/tool-export.svg",
             "style": Qt.ToolButtonTextBesideIcon, "stylesheet": "QToolButton { background-color: #6366F1; color: #FFFFFF; border: none; border-radius: 8px; } QToolButton:hover, QToolButton:pressed { background-color: #818CF8; }"},
            {"action": self.app.window.actionUpdate, "icon": "themes/cosmic/images/warning.svg", "visible": False, "style": Qt.ToolButtonTextBesideIcon, "stylesheet": "QToolButton { background-color: #151A23; color: #FABE0A; border-radius: 8px; }"}
        ]
        self.set_toolbar_buttons(self.app.window.toolBar, icon_size=20, settings=toolbar_buttons)

        # Timeline toolbar buttons
        timeline_buttons = [
            {"action": self.app.window.actionAddTrack, "icon": "themes/cosmic/images/tool-add-track.svg", "style": Qt.ToolButtonTextBesideIcon, "stylesheet": "QToolButton { margin-left: 15px; }"},
            {"action": self.app.window.actionUndo, "icon": "themes/cosmic/images/tool-undo.svg", "style": Qt.ToolButtonIconOnly, "stylesheet": "QToolButton { margin-right: 0px; border-bottom-right-radius: 0px; border-top-right-radius: 0px; }"},
            {"action": self.app.window.actionRedo, "icon": "themes/cosmic/images/tool-redo.svg", "style": Qt.ToolButtonIconOnly, "stylesheet": "QToolButton { margin-left: 0px; border-bottom-left-radius: 0px; border-top-left-radius: 0px; }"},
            {"action": self.app.window.actionSnappingTool, "icon": "themes/cosmic/images/tool-snapping.svg", "style": Qt.ToolButtonIconOnly, "stylesheet": "QToolButton { margin-right: 0px; border-bottom-right-radius: 0px; border-top-right-radius: 0px; }"},
            {"action": self.app.window.actionTimingTool, "icon": "themes/cosmic/images/tool-timing.svg", "style": Qt.ToolButtonIconOnly, "stylesheet": "QToolButton { margin-left: 0px; margin-right: 0px; border-bottom-left-radius: 0px; border-top-left-radius: 0px; border-bottom-right-radius: 0px; border-top-right-radius: 0px; }"},
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

        # Apply timeline theme (modern dark)
        self.app.window.timeline.apply_theme("""
            body {
              background: #151A23;
            }
            ::-webkit-scrollbar {
              width: 8px;
              height: 8px;
            }
            ::-webkit-scrollbar-thumb {
                background: rgba(230, 230, 235, 0.2);
                border-radius: 6px;
            }
            ::-webkit-scrollbar-track {
              background: #151A23;
              box-shadow: none;
            }
            .track_name {
              background: #1E2433;
              border-top-left-radius: 0px;
              border-bottom-left-radius: 0px;
              border: 1px solid #1E2433;
              border-left: 4px solid #6366F1;
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
              background: #1E2433;
              border: 1px solid #1E2433;
              border-radius: 0px;
              height: 48px;
            }
            .track-resize-handle {
              background-color: #151A23;
              border-top: 1px solid #151A23;
              border-bottom: 1px solid #151A23;
              border-right: 1px solid #151A23;
              border-top-right-radius: 0px;
              border-bottom-right-radius: 0px;
            }
            .track-resize-handle:hover {
              background-color: #2A3147;
            }
            .transition {
              height: 48px;
              min-height: 48px;
            }
            .transition_top {
              background: none;
            }
            .clip {
              background: #1E2433;
              border: 1px solid #6366F1;
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
              top: 0;
              width: 2px;
              background-color: #FABE0A;
              margin: -1px;
              pointer-events: none;
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
            .track-keyframe-panel-disabled {
              background-image: url(../themes/cosmic/images/track-keyframe-panel-show-disabled.svg);
            }
            .track-keyframe-panel-enabled {
              background-image: url(../themes/cosmic/images/track-keyframe-panel-show-enabled.svg);
            }
            .track-add-above-disabled {
              background-image: url(../themes/cosmic/images/track-add-above-disabled.svg);
            }
            .track-add-above-enabled {
              background-image: url(../themes/cosmic/images/track-add-above-enabled.svg);
            }
            .track-add-below-disabled {
              background-image: url(../themes/cosmic/images/track-add-below-disabled.svg);
            }
            .track-add-below-enabled {
              background-image: url(../themes/cosmic/images/track-add-below-enabled.svg);
            }
            .track-delete-disabled {
              background-image: url(../themes/cosmic/images/track-delete-disabled.svg);
            }
            .track-delete-enabled {
              background-image: url(../themes/cosmic/images/track-delete-enabled.svg);
            }
            .track-locked-disabled {
              background-image: url(../themes/cosmic/images/track-locked-disabled.svg);
            }
            .track-locked-enabled {
              background-image: url(../themes/cosmic/images/track-locked-enabled.svg);
            }
            .track-unlocked-disabled {
              background-image: url(../themes/cosmic/images/track-unlocked-disabled.svg);
            }
            .track-unlocked-enabled {
              background-image: url(../themes/cosmic/images/track-unlocked-enabled.svg);
            }
            .keyframe-panel-add {
              background-image: url(../themes/cosmic/images/keyframe-panel-add.svg);
            }
            .marker_icon {
              background-image: url(../themes/cosmic/images/marker.svg);
            }
            #ruler_label {
              background: #151A23;
            }
            #scrolling_ruler {
              background: #151A23;
            }
        """)

        # Emit signal
        self.app.window.ThemeChangedSignal.emit(self)

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
