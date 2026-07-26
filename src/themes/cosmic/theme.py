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

from qt_api import Qt
from qt_api import QIcon
from qt_api import QTabWidget, QWidget

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

QLabel#lblTutorialText {
    font-size: 14px;
}

QCheckBox#checkboxMetrics {
    font-size: 14px;
}

QWidget#tutorial QPushButton#NextTip {
    background-color: #283241;
    font-size: 12px;
}

QWidget#tutorial QPushButton#HideTutorial {
    font-size: 12px;
}


QDialog {
    background-color: #192332;
    color: #91C3FF;
}

QLabel#lblMissingFileHint,
QLabel#lblMissingFilePath {
    color: #9bb2cc;
}

QFrame#recordingCard {
    background-color: rgba(20, 31, 48, 190);
    border: 1px solid rgba(70, 134, 230, 110);
    border-radius: 8px;
}
QFrame#recordingCard[checked="true"] {
    border: 2px solid #2f8cff;
    background-color: rgba(26, 58, 105, 170);
}
QFrame#recordingCard[available="false"] {
    border: 1px solid rgba(80, 91, 110, 90);
    background-color: rgba(20, 25, 34, 120);
}
QLabel#recordingCardIcon {
    color: #7db7ff;
    font-size: 22px;
}
QLabel#recordingCardTitle {
    color: #f4f7ff;
    font-size: 14px;
    font-weight: 700;
}
QLabel#recordingCardSubtitle {
    color: #9aa8bd;
    font-size: 11px;
}
QFrame#recordingSection {
    background-color: rgba(13, 24, 38, 165);
    border: 1px solid rgba(83, 105, 134, 95);
    border-radius: 8px;
}
QFrame#recordingSection[active="true"] {
    border: 1px solid rgba(70, 141, 255, 125);
}
QFrame#recordingSection[active="false"] {
    color: #6f7b8d;
    background-color: rgba(15, 20, 28, 95);
}
QLabel#recordingSectionIcon {
    color: #8fbfff;
    font-size: 16px;
}
QLabel#recordingSectionTitle {
    color: #f4f7ff;
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
    border: 1px solid rgba(83, 105, 134, 120);
    border-radius: 6px;
    padding: 7px 10px;
    color: #c4cedd;
    background-color: rgba(14, 25, 40, 170);
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
    color: #9dccff;
    border: 1px solid #2f8cff;
    background-color: rgba(40, 94, 170, 135);
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

QMenuBar::item {
    padding: 6px 10px;
    background: transparent;
}

QMenuBar::item:selected {
    background-color: #323C50;
    color: #ffffff;
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
    padding: 6px 18px 6px 22px;
}

QMenu::item:checked {
    padding: 6px 18px 6px 22px;
}

QMenu::indicator {
    width: 12px;
    height: 12px;
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
    padding-left: 8px;
    padding-right: 8px;
    border: none;
}

QToolBar#toolBar QToolButton:hover {
    background-color: #323C50;
}

QToolBar QToolButton:hover {
    background-color: #192332;
}

QToolBar QToolButton:pressed {
    background-color: #192332;
}

QToolBar#filesToolbar,
QToolBar#transitionsToolbar,
QToolBar#effectsToolbar {
    background-color: transparent;
    spacing: 4px;
    padding: 2px;
    border: none;
}

QToolBar#filesToolbar QToolButton,
QToolBar#transitionsToolbar QToolButton,
QToolBar#effectsToolbar QToolButton {
    background-color: #141923;
    color: #91C3FF;
    border-radius: 3px;
    padding: 3px 6px;
}

QToolBar#filesToolbar QToolButton:hover,
QToolBar#transitionsToolbar QToolButton:hover,
QToolBar#effectsToolbar QToolButton:hover {
    background-color: #192332;
}

QToolBar#filesToolbar QToolButton:checked,
QToolBar#transitionsToolbar QToolButton:checked,
QToolBar#effectsToolbar QToolButton:checked {
    background-color: #202b3a;
}

QToolBar#filesToolbar QToolButton:focus,
QToolBar#transitionsToolbar QToolButton:focus,
QToolBar#effectsToolbar QToolButton:focus {
    background-color: #1d2737;
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
    border: none;
}

QToolBar#timelineToolbar QToolButton:hover {
    background-color: #283241;
}


QToolBar#timelineToolbar QToolButton:checked {
    background-color: #283241;
}

QToolBar#toolBar QToolButton:focus {
    background-color: #2f3848;
}

QToolBar#timelineToolbar QToolButton:focus:!checked {
    background-color: #2a3444;
}

QToolBar#timelineToolbar QToolButton:checked:focus {
    background-color: #314055;
}

QToolBar#timelineToolbar QToolButton:pressed {
    background-color: #3a4558;
}

QToolBar#toolBar QToolButton:pressed {
    background-color: #3a4456;
}

QToolBar#filesToolbar QToolButton:pressed,
QToolBar#transitionsToolbar QToolButton:pressed,
QToolBar#effectsToolbar QToolButton:pressed {
    background-color: #2a374a;
}

QToolBar#toolBar QToolButton:hover {
    background-color: #323C50;
}

QToolBar#videoToolbar QToolButton:focus {
    background-color: #1d2737;
}

QToolBar#videoToolbar QToolButton:pressed {
    background-color: #2a374a;
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

QPushButton#acceptButton:focus,
QPushButton#acceptButton:default {
    background-color: #1a86ff;
}

QPushButton {
    padding: 8px 16px 8px 12px;
    border-radius: 4px;
    background-color: #192332;
    color: #91C3FF;
}

QPushButton:hover {
    background-color: #283241;
}

QPushButton:focus {
    background-color: #283241;
}

QWidget#settingsContainer {
    background-color: #141923;
}

QWidget#scrollAreaWidgetContents {
    background-color: #141923;
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
    color: #91C3FF;
    font-weight: 500;
    min-height: 20px;
    padding: 10px 16px 8px 16px;
}

QLabel#dock-title-handle {
    padding-left: 16px;
    qproperty-pixmap: url({PATH}themes/cosmic/images/dock-move.svg);
}

QDockWidget {
    background-color: #141923;
    titlebar-close-icon: url({PATH}themes/cosmic/images/dock-close.svg);
    titlebar-normal-icon: url({PATH}themes/cosmic/images/dock-float.svg);
    color: #91C3FF;
    font-weight: 500;
    padding: 16px;
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
    color: rgba(145, 195, 255, 0.4);
}

QTabWidget#exportTabs QTabBar::tab,
QTabWidget#tabCategories QTabBar::tab,
QTabWidget#tabCredits QTabBar::tab,
QTabWidget#generateTabs QTabBar::tab {
    margin-bottom: 10px;
}

QTabWidget#generateTabs QTabBar::tab:selected {
    border-bottom: 1.2px solid #53a0ed;
}

QTabBar::tab:selected {
    color: rgba(145, 195, 255, 1.0);
}

QTabBar:focus {
    outline: none;
}

QTabBar::tab:focus {
    border-bottom: 1.2px solid #53a0ed;
}

QToolBox::tab:focus {
    border-left: 1.2px solid #53a0ed;
}

QCheckBox:focus {
    background-color: #283241;
}

QLineEdit#filesFilter, QLineEdit#effectsFilter, QLineEdit#transitionsFilter, QLineEdit#emojisFilter, QLineEdit#txtPropertyFilter {
    background-color: #192332;
    border-radius: 4px;
    padding: 6px;
    padding-left: 8px;
    padding-right: 8px;
}

QLineEdit,
QSpinBox,
QDoubleSpinBox {
    background-color: #121212;
    border: 1.2px solid transparent;
    border-radius: 4px;
    padding-top: 1px;
    padding-bottom: 1px;
    padding-left: 6px;
    min-height: 18px;
}

QSpinBox,
QDoubleSpinBox {
    padding-right: 22px;
}

QDoubleSpinBox#colorGradeSpinBox {
    padding-right: 14px;
}

QSpinBox::up-button,
QDoubleSpinBox::up-button,
QSpinBox::down-button,
QDoubleSpinBox::down-button {
    subcontrol-origin: border;
    width: 16px;
    background: transparent;
    border: 1px solid transparent;
    border-radius: 3px;
    margin-right: 2px;
}

QSpinBox::up-button,
QDoubleSpinBox::up-button {
    subcontrol-position: top right;
    margin-top: 1px;
    margin-bottom: 0px;
    min-height: 7px;
}

QSpinBox::down-button,
QDoubleSpinBox::down-button {
    subcontrol-position: bottom right;
    margin-top: 0px;
    margin-bottom: 1px;
    min-height: 7px;
}

QSpinBox::up-button:hover,
QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover,
QDoubleSpinBox::down-button:hover {
    background-color: rgba(145, 195, 255, 0.08);
    border-color: rgba(145, 195, 255, 0.25);
}

QSpinBox::up-button:pressed,
QDoubleSpinBox::up-button:pressed,
QSpinBox::down-button:pressed,
QDoubleSpinBox::down-button:pressed {
    background-color: rgba(145, 195, 255, 0.14);
    border-color: rgba(145, 195, 255, 0.4);
}

QSpinBox::up-arrow,
QDoubleSpinBox::up-arrow {
    image: url({PATH}themes/cosmic/images/spin-up-arrow.svg);
    width: 12px;
    height: 12px;
}

QSpinBox::down-arrow,
QDoubleSpinBox::down-arrow {
    image: url({PATH}themes/cosmic/images/spin-down-arrow.svg);
    width: 12px;
    height: 12px;
}

QLineEdit:focus,
QSpinBox:focus,
QDoubleSpinBox:focus {
    border-width: 1.2px;
    border-style: solid;
    border-color: #53a0ed;
}

QLineEdit#filesFilter:focus, QLineEdit#effectsFilter:focus, QLineEdit#transitionsFilter:focus, QLineEdit#emojisFilter:focus, QLineEdit#txtPropertyFilter:focus {
    border-width: 1.2px;
    border-style: solid;
    border-color: #53a0ed;
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
    border: 1.2px solid transparent;
    border-radius: 4px;
    padding: 6px;
    padding-left: 8px;
    padding-right: 8px;
    combobox-popup: 0;
}

QComboBox:focus {
    border-color: #53a0ed;
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

QTableView#propertyTableView::item:selected {
    background-color: #192332;
    border: 1.2px solid #0078FF;
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
    border-top: 1px solid rgba(145, 195, 255, .2);
}

QTabWidget QWidget#pageAdvancedOptions, QWidget#pageProfile, QWidget#pageImageSequenceSettings, QWidget#pageVideoSettings, QWidget#pageAudioSettings {
    background-color: #141923;
}

QTabWidget QWidget#pageVideoDetails, QWidget#pageVideoFormat, QWidget#pageAudioFormat, QWidget#pageFrameSettings {
    background-color: #141923;
}

QDialog#generateDialog QTabWidget#generateTabs::pane {
    border: none;
    background-color: #141923;
}

QDialog#generateDialog QTabWidget#generateTabs QWidget#pagePrompt,
QDialog#generateDialog QTabWidget#generateTabs QWidget#pagePoints,
QDialog#generateDialog QTabWidget#generateTabs QWidget#pageHighlight {
    background-color: #141923;
    border: none;
}

QDialog#generateDialog QLineEdit,
QDialog#generateDialog QTextEdit,
QDialog#generateDialog QComboBox {
    background-color: #141923;
    color: #91C3FF;
    border: 1.2px solid transparent;
    border-radius: 4px;
    padding: 6px 8px;
}

QDialog#generateDialog QLineEdit:focus,
QDialog#generateDialog QTextEdit:focus,
QDialog#generateDialog QComboBox:focus {
    border: 1.2px solid #53a0ed;
}

QLineEdit:disabled,
QTextEdit:disabled,
QComboBox:disabled,
QSpinBox:disabled,
QDoubleSpinBox:disabled {
    color: #808080;
}

QComboBox:disabled::drop-down {
    opacity: 0.75;
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

QMessageBox QPushButton[text="&{_('Cancel')}"] {{
    qproperty-icon: none;
}}
        """ + self.style_sheet.replace("{PATH}", f"{path_unix_slashes}/")

    def apply_theme(self):
        super().apply_theme()

        from classes.app import get_app
        from classes import ui_util
        from classes.logger import log
        from qt_api import QStyleFactory
        from qt_api import QFont

        _ = get_app()._tr

        log.info("Setting Fusion dark palette")
        self.app.setStyle(QStyleFactory.create("Fusion"))
        dark_palette = ui_util.make_dark_palette(self.app.palette())
        self.app.setPalette(dark_palette)

        # Set font for all widgets
        font = QFont("Ubuntu")
        font.setPointSizeF(8)
        self.app.setFont(font)

        # Move tabs to top (all dock areas, since restoreState() does not persist tab positions)
        for area in (Qt.TopDockWidgetArea, Qt.BottomDockWidgetArea,
                     Qt.LeftDockWidgetArea, Qt.RightDockWidgetArea):
            self.app.window.setTabPosition(area, QTabWidget.North)

        # Set dock widget content margins to 0
        self.set_dock_margins([16, 0, 16, 0])
        self.set_dock_margins([0, 0, 0, 0], [0, 10, 0, 0], "dockTimelineContents")

        # Apply new stylesheet
        self.app.setStyleSheet(self.compose_stylesheet())

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
             "style": Qt.ToolButtonTextBesideIcon, "stylesheet": "QToolButton { background-color: #0078FF; color: #FFFFFF; border: none; } QToolButton:hover { background-color: #0a82ff; } QToolButton:focus { background-color: #0a82ff; } QToolButton:pressed { background-color: #3d9bff; }"},
            {"action": self.app.window.actionUpdate, "icon": "themes/cosmic/images/warning.svg", "visible": False, "style": Qt.ToolButtonTextBesideIcon, "stylesheet": "QToolButton {  background-color: #141923; color: #FABE0A; }"}
        ]
        self.set_toolbar_buttons(self.app.window.toolBar, icon_size=20, settings=toolbar_buttons)

        self.app.window.actionColor_Grade_View.setIcon(
            QIcon(os.path.join(PATH, "themes/cosmic/images/view-color.svg"))
        )

        # Timeline toolbar buttons
        timeline_buttons = [
            {"action": self.app.window.actionAddTrack, "icon": "themes/cosmic/images/tool-add-track.svg", "style": Qt.ToolButtonTextBesideIcon, "stylesheet": "QToolButton { margin-left: 15px; }"},
            {"action": self.app.window.actionUndo, "icon": "themes/cosmic/images/tool-undo.svg", "style": Qt.ToolButtonIconOnly, "stylesheet": "QToolButton { margin-right: 0px; border-bottom-right-radius: 0px; border-top-right-radius: 0px; }"},
            {"action": self.app.window.actionRedo, "icon": "themes/cosmic/images/tool-redo.svg", "style": Qt.ToolButtonIconOnly, "stylesheet": "QToolButton { margin-left: 0px; border-bottom-left-radius: 0px; border-top-left-radius: 0px; }"},
            {"action": self.app.window.actionSnappingTool, "icon": "themes/cosmic/images/tool-snapping.svg", "style": Qt.ToolButtonIconOnly, "stylesheet": "QToolButton { margin-right: 0px; border-bottom-right-radius: 0px; border-top-right-radius: 0px; } QToolButton:focus { border: 1px solid #5aa2e6; background-color: #141923; } QToolButton:checked:focus { border: 1px solid #5aa2e6; background-color: #283241; }"},
            {"action": self.app.window.actionTimingTool, "icon": "themes/cosmic/images/tool-timing.svg", "style": Qt.ToolButtonIconOnly, "stylesheet": "QToolButton { margin-left: 0px; margin-right: 0px; border-bottom-left-radius: 0px; border-top-left-radius: 0px; border-bottom-right-radius: 0px; border-top-right-radius: 0px; } QToolButton:focus { border: 1px solid #5aa2e6; background-color: #141923; } QToolButton:checked:focus { border: 1px solid #5aa2e6; background-color: #283241; }"},
            {"action": self.app.window.actionRazorTool, "icon": "themes/cosmic/images/tool-razor.svg", "style": Qt.ToolButtonIconOnly, "stylesheet": "QToolButton { margin-left: 0px; border-bottom-left-radius: 0px; border-top-left-radius: 0px; } QToolButton:focus { border: 1px solid #5aa2e6; background-color: #141923; } QToolButton:checked:focus { border: 1px solid #5aa2e6; background-color: #283241; }"},
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

        from .styles import CosmicDuskTimelineTheme
        self.app.window.timeline.apply_theme(CosmicDuskTimelineTheme())

        # Emit signal
        self.app.window.ThemeChangedSignal.emit(self)

    def togglePlayIcon(self, isPlay):
        """ Toggle the play icon from play to pause and back """
        button = self.app.window.videoToolbar.widgetForAction(self.app.window.actionPlay)
        if button:
            icon_name = "tool-media-pause.svg" if isPlay else "tool-media-play.svg"
            icon_path = os.path.join(PATH, "themes/cosmic/images", icon_name)
            icon = self.create_svg_icon(icon_path, self.app.window.videoToolbar.iconSize())
            button.setIcon(icon)
