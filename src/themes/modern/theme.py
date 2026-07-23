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


from themes.modern import tokens

class ModernTheme(BaseTheme):
    def __init__(self, app):
        super().__init__(app)

        from classes.app import get_app
        _ = get_app()._tr

        self.style_sheet = f"""
QMainWindow {{
    background-color: {tokens.palette["window_bg"]};
    color: {tokens.palette["text_primary"]};
}}

QMainWindow::separator {{
    background: {tokens.palette["window_bg"]};
    width: 2px;
    height: 2px;
}}

QWidget#tutorial {{
    background-color: {tokens.palette["window_bg"]};
    border: 1.2px solid {tokens.palette["accent"]};
    border-radius: 4px;
    padding: 20px;
}}

QLabel#lblTutorialText {{
    font-size: 14px;
}}

QCheckBox#checkboxMetrics {{
    font-size: 14px;
}}

QWidget#tutorial QPushButton#NextTip {{
    background-color: {tokens.palette["hover_bg"]};
    font-size: 12px;
}}

QWidget#tutorial QPushButton#HideTutorial {{
    font-size: 12px;
}}


QDialog {{
    background-color: {tokens.palette["window_bg"]};
    color: {tokens.palette["text_primary"]};
}}

QLabel#lblMissingFileHint,
QLabel#lblMissingFilePath {{
    color: {tokens.palette["text_secondary"]};
}}

QWidget#Simple, QWidget#Advanced, QWidget#PreferencePanel {{
    background-color: {tokens.palette["surface_bg"]};
    border: none;
}}

QScrollArea {{
    border: none;
}}

QTabWidget {{
    border: none;
}}

QMenuBar {{
    background-color: {tokens.palette["hover_bg"]};
    color: {tokens.palette["text_primary"]};
    padding: 0px;
    border: none;
}}

QMenuBar::item {{
    padding: 6px 10px;
    background: transparent;
}}

QMenuBar::item:selected {{
    background-color: {tokens.palette["selected_bg"]};
    color: {tokens.palette["text_primary"]};
}}

QMenu {{
    background-color: {tokens.palette["surface_bg"]};
    color: {tokens.palette["text_primary"]};
    padding: 6px;
    padding-left: 8px;
    padding-right: 8px;
    min-width: 40px;
    border: 1.2px solid {tokens.palette["accent"]};
    border-radius: 3px 3px;
}}

QMenu::item {{
    padding: 6px 18px 6px 22px;
}}

QMenu::item:checked {{
    padding: 6px 18px 6px 22px;
}}

QMenu::indicator {{
    width: 12px;
    height: 12px;
}}

QMenu::item:selected {{
    background-color: {tokens.palette["window_bg"]};
    color: {tokens.palette["text_primary"]};
}}

QMenu::separator {{
    height: 8px;
    background-color: {tokens.palette["surface_bg"]};
}}

QToolBar#toolBar {{
    background-color: {tokens.palette["hover_bg"]};
    spacing: 0px;
    padding: 0px;
    border: none;
}}

QToolBar#toolBar QToolButton {{
    background-color: {tokens.palette["hover_bg"]};
    color: {tokens.palette["text_primary"]};
    padding-top: 10px;
    padding-bottom: 10px;
    padding-left: 8px;
    padding-right: 8px;
    border: none;
}}

QToolBar#toolBar QToolButton:hover {{
    background-color: {tokens.palette["selected_bg"]};
}}

QToolBar QToolButton:hover {{
    background-color: {tokens.palette["window_bg"]};
}}

QToolBar QToolButton:pressed {{
    background-color: {tokens.palette["window_bg"]};
}}

QToolBar#filesToolbar,
QToolBar#transitionsToolbar,
QToolBar#effectsToolbar {{
    background-color: transparent;
    spacing: 4px;
    padding: 2px;
    border: none;
}}

QToolBar#filesToolbar QToolButton,
QToolBar#transitionsToolbar QToolButton,
QToolBar#effectsToolbar QToolButton {{
    background-color: {tokens.palette["surface_bg"]};
    color: {tokens.palette["text_primary"]};
    border-radius: 3px;
    padding: 3px 6px;
}}

QToolBar#filesToolbar QToolButton:hover,
QToolBar#transitionsToolbar QToolButton:hover,
QToolBar#effectsToolbar QToolButton:hover {{
    background-color: {tokens.palette["window_bg"]};
}}

QToolBar#filesToolbar QToolButton:checked,
QToolBar#transitionsToolbar QToolButton:checked,
QToolBar#effectsToolbar QToolButton:checked {{
    background-color: #202b3a;
}}

QToolBar#filesToolbar QToolButton:focus,
QToolBar#transitionsToolbar QToolButton:focus,
QToolBar#effectsToolbar QToolButton:focus {{
    background-color: #1d2737;
}}


QToolBar#timelineToolbar {{
    background-color: {tokens.palette["window_bg"]};
    spacing: 0px;
    padding: 0px;
    border: none;
}}

QToolBar#timelineToolbar QToolButton {{
    color: {tokens.palette["text_primary"]};
    background-color: {tokens.palette["surface_bg"]};
    padding: 8px;
    margin-bottom: 4px;
    margin-right: 5px;
    margin-left: 5px;
    border-radius: 4px;
    border: none;
}}

QToolBar#timelineToolbar QToolButton:hover {{
    background-color: {tokens.palette["hover_bg"]};
}}


QToolBar#timelineToolbar QToolButton:checked {{
    background-color: {tokens.palette["hover_bg"]};
}}

QToolBar#toolBar QToolButton:focus {{
    background-color: #2f3848;
}}

QToolBar#timelineToolbar QToolButton:focus:!checked {{
    background-color: #2a3444;
}}

QToolBar#timelineToolbar QToolButton:checked:focus {{
    background-color: #314055;
}}

QToolBar#timelineToolbar QToolButton:pressed {{
    background-color: #3a4558;
}}

QToolBar#toolBar QToolButton:pressed {{
    background-color: #3a4456;
}}

QToolBar#filesToolbar QToolButton:pressed,
QToolBar#transitionsToolbar QToolButton:pressed,
QToolBar#effectsToolbar QToolButton:pressed {{
    background-color: #2a374a;
}}

QToolBar#toolBar QToolButton:hover {{
    background-color: {tokens.palette["selected_bg"]};
}}

QToolBar#videoToolbar {{
    background-color: {tokens.palette["surface_bg"]};
    border-radius: 4px;
    border: 1px solid {tokens.palette["border_subtle"]};
    margin: 6px 220px 10px 220px;
}}

QToolBar#videoToolbar QToolButton {{
    border-radius: 4px;
    padding: 6px;
}}

QToolBar#videoToolbar QToolButton:focus {{
    background-color: #1d2737;
}}

QToolBar#videoToolbar QToolButton:pressed {{
    background-color: #2a374a;
}}

QPushButton#acceptButton,
QToolButton#tool-actionExportVideo {{
    padding: 8px 16px 8px 12px;
    border-radius: {tokens.spacing["button_radius"]};
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {tokens.palette["cta_gradient_start"]}, stop:1 {tokens.palette["cta_gradient_end"]});
    color: #FFFFFF;
    border: 1px solid transparent;
    font-weight: bold;
}}

QPushButton#acceptButton:hover,
QToolButton#tool-actionExportVideo:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1A85FF, stop:1 #1ACDFF);
}}

QPushButton#acceptButton:pressed,
QToolButton#tool-actionExportVideo:pressed {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0066D6, stop:1 #00B3E6);
}}

QPushButton#acceptButton:focus,
QPushButton#acceptButton:default,
QToolButton#tool-actionExportVideo:focus {{
    border: 1px solid {tokens.palette["accent"]};
    outline: 1px solid {tokens.palette["accent"]};
}}

QPushButton {{
    padding: 8px 16px 8px 12px;
    border-radius: {tokens.spacing["button_radius"]};
    background-color: {tokens.palette["window_bg"]};
    color: {tokens.palette["text_primary"]};
    border: 1px solid transparent;
}}

QPushButton:hover {{
    background-color: {tokens.palette["hover_bg"]};
}}

QPushButton:pressed {{
    background-color: #151922;
}}

QPushButton:focus {{
    border: 1px solid {tokens.palette["accent"]};
}}

QToolButton {{
    background-color: {tokens.palette["surface_bg"]};
    color: {tokens.palette["text_primary"]};
    border-radius: 4px;
    border: 1px solid transparent;
}}

QToolButton:hover {{
    background-color: {tokens.palette["hover_bg"]};
}}

QToolButton:pressed {{
    background-color: #151922;
}}

QToolButton:focus {{
    border: 1px solid {tokens.palette["accent"]};
}}

QWidget#settingsContainer {{
    background-color: {tokens.palette["surface_bg"]};
}}

QWidget#scrollAreaWidgetContents {{
    background-color: {tokens.palette["surface_bg"]};
}}

QPushButton#dock-close-button {{
    image: url({PATH}/themes/modern/images/dock-close.svg);
    padding: 0px;
    padding-top: 2px;
    padding-bottom: 2px;
    margin: 0px;
    margin-right: 16px;
    width: 16px;
    height: 16px;
}}
QPushButton#dock-float-button {{
    image: url({PATH}/themes/modern/images/dock-float.svg);
    padding: 0px;
    padding-top: 2px;
    padding-bottom: 2px;
    margin: 0px;
    width: 16px;
    height: 16px;
}}

QLabel#dock-title-label {{
    font-size: 12px;
    font-weight: 600;
    color: {tokens.palette["text_secondary"]};
    letter-spacing: 0.3px;
    padding: 16px;
}}

HiddenTitleBar {{
    background-color: {tokens.palette["window_bg"]};
    min-height: 24px;
    max-height: 24px;
}}

QLabel#dock-title-label {{
    color: {tokens.palette["text_secondary"]};
    font-size: {tokens.typography["title_size"]};
    font-weight: normal;
    padding-left: 8px;
}}


QLabel#dock-title-handle {
    padding-left: 8px;
    qproperty-pixmap: url({PATH}/themes/modern/images/dock-move.svg);
}

QDockWidget {
    background-color: {tokens.palette["surface_bg"]};
    titlebar-close-icon: url({PATH}/themes/modern/images/dock-close.svg);
    titlebar-normal-icon: url({PATH}/themes/modern/images/dock-float.svg);
    color: {tokens.palette["text_primary"]};
    font-weight: normal;
}

QDockWidget QWidget {{
    border: none;
}}

QDockWidget QWidget#dockFilesContents, QWidget#dockTransitionsContents, QWidget#dockEmojisContents, QWidget#dockEffectsContents, QWidget#dockCaptionContents, QWidget#dockVideoContents, QWidget#dockPropertiesContents {{
    background-color: {tokens.palette["surface_bg"]};
    border-radius: 4px;
    border: 1px solid {tokens.palette["border_subtle"]};
    margin-top: 5px;
    margin-left: 2px;
    margin-right: 2px;
}}

QDockWidget QWidget#dockTimelineContents {{
    border-radius: 4px;
    margin-left: 0px;
    margin-right: 0px;
    padding: 0px;
}}

QTabBar {{
    border: none;
    qproperty-drawBase: 0;
    margin: 0px;
    padding: 0px;
}}

/* Hide dock widget tabs (Project Files, Transitions, etc.) */
QMainWindow > QTabBar,
QMainWindow > QTabBar::tab {{
    height: 0px;
    width: 0px;
    margin: 0px;
    padding: 0px;
    border: none;
    color: transparent;
    background: transparent;
}}

QTabBar::tab {{
    height: 16px;
    border: none;
    border-radius: 4px;
    margin-left: 16px;
    margin-top: 16px;
    margin-bottom: 0px;
    padding: 6px 14px;
    color: {tokens.palette["text_secondary"]};
}}

QTabWidget#exportTabs QTabBar::tab,
QTabWidget#tabCategories QTabBar::tab,
QTabWidget#tabCredits QTabBar::tab,
QTabWidget#generateTabs QTabBar::tab {{
    margin-bottom: 10px;
}}

QTabWidget#generateTabs QTabBar::tab:selected {{
    border-bottom: 1.2px solid {tokens.palette["accent"]};
}}

QTabBar::tab:selected {{
    background-color: {tokens.palette["selected_bg"]};
    color: {tokens.palette["accent"]};
    border-bottom: 1.2px solid {tokens.palette["accent"]};
    font-weight: 600;
}}

QTabBar:focus {{
    outline: none;
}}

QTabBar::tab:focus {{
    border-bottom: 1.2px solid {tokens.palette["accent"]};
}}

QToolBox::tab:focus {{
    border-left: 1.2px solid {tokens.palette["accent"]};
}}

QCheckBox:focus {{
    background-color: {tokens.palette["hover_bg"]};
}}

QLineEdit#filesFilter, QLineEdit#effectsFilter, QLineEdit#transitionsFilter, QLineEdit#emojisFilter, QLineEdit#txtPropertyFilter {{
    background-color: {tokens.palette["window_bg"]};
    border-radius: 4px;
    padding: 6px;
    padding-left: 8px;
    padding-right: 8px;
}}

QLineEdit,
QSpinBox,
QDoubleSpinBox {{
    background-color: {tokens.palette["surface_bg"]};
    border: 1.2px solid transparent;
    border-radius: 4px;
    padding-top: 1px;
    padding-bottom: 1px;
    padding-left: 6px;
    min-height: 18px;
}}

QSpinBox,
QDoubleSpinBox {{
    padding-right: 22px;
}}

QDoubleSpinBox#colorGradeSpinBox {{
    padding-right: 14px;
}}

QSpinBox::up-button,
QDoubleSpinBox::up-button,
QSpinBox::down-button,
QDoubleSpinBox::down-button {{
    subcontrol-origin: border;
    width: 16px;
    background: transparent;
    border: 1px solid transparent;
    border-radius: 3px;
    margin-right: 2px;
}}

QSpinBox::up-button,
QDoubleSpinBox::up-button {{
    subcontrol-position: top right;
    margin-top: 1px;
    margin-bottom: 0px;
    min-height: 7px;
}}

QSpinBox::down-button,
QDoubleSpinBox::down-button {{
    subcontrol-position: bottom right;
    margin-top: 0px;
    margin-bottom: 1px;
    min-height: 7px;
}}

QSpinBox::up-button:hover,
QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover,
QDoubleSpinBox::down-button:hover {{
    background-color: rgba(145, 195, 255, 0.08);
    border-color: rgba(145, 195, 255, 0.25);
}}

QSpinBox::up-button:pressed,
QDoubleSpinBox::up-button:pressed,
QSpinBox::down-button:pressed,
QDoubleSpinBox::down-button:pressed {{
    background-color: rgba(145, 195, 255, 0.14);
    border-color: rgba(145, 195, 255, 0.4);
}}

QSpinBox::up-arrow,
QDoubleSpinBox::up-arrow {{
    image: url({PATH}/themes/modern/images/spin-up-arrow.svg);
    width: 12px;
    height: 12px;
}}

QSpinBox::down-arrow,
QDoubleSpinBox::down-arrow {{
    image: url({PATH}/themes/modern/images/spin-down-arrow.svg);
    width: 12px;
    height: 12px;
}}

QLineEdit:focus,
QTextEdit:focus,
QSpinBox:focus,
QDoubleSpinBox:focus {{
    border-width: 1.2px;
    border-style: solid;
    border-color: {tokens.palette["accent"]};
}}

QLineEdit#filesFilter:focus, QLineEdit#effectsFilter:focus, QLineEdit#transitionsFilter:focus, QLineEdit#emojisFilter:focus, QLineEdit#txtPropertyFilter:focus {{
    border-width: 1.2px;
    border-style: solid;
    border-color: {tokens.palette["accent"]};
}}

QScrollBar:vertical {{
    border: none;
    background: transparent;
    width: 6px;
}}

QScrollBar::handle:vertical {{
    background-color: {tokens.palette["border_subtle"]};
    border-radius: 3px;
    min-height: 20px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: {tokens.palette["text_secondary"]};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
    border: none;
    background: transparent;
}}

QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: transparent;
}}

QScrollBar:horizontal {{
    border: none;
    background: transparent;
    height: 6px;
}}

QScrollBar::handle:horizontal {{
    background-color: {tokens.palette["border_subtle"]};
    border-radius: 3px;
    min-width: 20px;
}}

QScrollBar::handle:horizontal:hover {{
    background-color: {tokens.palette["text_secondary"]};
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0px;
    border: none;
    background: transparent;
}}

QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
    background: transparent;
}}

QComboBox {{
    background-color: {tokens.palette["surface_bg"]};
    color: {tokens.palette["text_primary"]};
    border: 1.2px solid transparent;
    border-radius: 4px;
    padding: 6px;
    padding-left: 8px;
    padding-right: 8px;
    combobox-popup: 0;
}}

QComboBox:focus {{
    border-color: {tokens.palette["accent"]};
}}

QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 40px;
    border: none;
}}

QComboBox::down-arrow {{
    image: url({PATH}/themes/modern/images/dropdown-arrow.svg);
}}

QComboBox QAbstractItemView {{
    color: {tokens.palette["text_primary"]};
    border: 1.2px solid {tokens.palette["accent"]};
    border-radius: 3px 3px 0px 0px;
    padding: 6px;
    padding-left: 8px;
    padding-right: 8px;
    background-color: {tokens.palette["surface_bg"]};
    text-align: left;
}}

QComboBox::item {{
    height: 24px;
}}

QComboBox::item:selected {{
    border: none;
    text-align: left;
    background-color: {tokens.palette["selected_bg"]};
    color: {tokens.palette["accent"]};
}}

QComboBox::item:checked {{
    font-weight: bold;
    background-color: {tokens.palette["window_bg"]};
}}

QComboBox::indicator::checked {{
    image: url({PATH}/themes/modern/images/dropdown-tick.svg);
}}

QHeaderView::section {{
    background-color: {tokens.palette["surface_bg"]};
    color: {tokens.palette["text_primary"]};
    padding: 4px;
    border: none;
}}

QTableView {{
    background-color: {tokens.palette["surface_bg"]};
    gridline-color: {tokens.palette["surface_bg"]};
}}

QTableView#propertyTableView::item:selected {{
    background-color: {tokens.palette["selected_bg"]};
    color: {tokens.palette["accent"]};
    border: 1.2px solid {tokens.palette["accent"]};
}}

QTreeView {{
    background-color: {tokens.palette["surface_bg"]};
}}

QListView::item,
QTreeView::item {{
    padding: 4px;
    border-radius: 6px;
}}

QTreeView::item:selected,
QListView::item:selected,
QTableView::item:selected,
QListWidget::item:selected {{
    background-color: {tokens.palette["selected_bg"]};
    color: {tokens.palette["accent"]};
}}

QListView {{
    background-color: {tokens.palette["surface_bg"]};
}}

QWidget#Details, QWidget#Output {{
    background-color: {tokens.palette["surface_bg"]};
}}

QWidget#Output QTextEdit {{
    color: {tokens.palette["text_primary"]};
}}

QToolBox::tab {{
    color: {tokens.palette["text_primary"]};
    border-top: 1px solid rgba(145, 195, 255, .2);
}}

QTabWidget QWidget#pageAdvancedOptions, QWidget#pageProfile, QWidget#pageImageSequenceSettings, QWidget#pageVideoSettings, QWidget#pageAudioSettings {{
    background-color: {tokens.palette["surface_bg"]};
}}

QTabWidget QWidget#pageVideoDetails, QWidget#pageVideoFormat, QWidget#pageAudioFormat, QWidget#pageFrameSettings {{
    background-color: {tokens.palette["surface_bg"]};
}}

QDialog#generateDialog QTabWidget#generateTabs::pane {{
    border: none;
    background-color: {tokens.palette["surface_bg"]};
}}

QDialog#generateDialog QTabWidget#generateTabs QWidget#pagePrompt,
QDialog#generateDialog QTabWidget#generateTabs QWidget#pagePoints,
QDialog#generateDialog QTabWidget#generateTabs QWidget#pageHighlight {{
    background-color: {tokens.palette["surface_bg"]};
    border: none;
}}

QDialog#generateDialog QLineEdit,
QDialog#generateDialog QTextEdit,
QDialog#generateDialog QComboBox {{
    background-color: {tokens.palette["surface_bg"]};
    color: {tokens.palette["text_primary"]};
    border: 1.2px solid transparent;
    border-radius: 4px;
    padding: 6px 8px;
}}

QDialog#generateDialog QLineEdit:focus,
QDialog#generateDialog QTextEdit:focus,
QDialog#generateDialog QComboBox:focus {{
    border: 1.2px solid {tokens.palette["accent"]};
}}

QLineEdit:disabled,
QTextEdit:disabled,
QComboBox:disabled,
QSpinBox:disabled,
QDoubleSpinBox:disabled {{
    color: #808080;
}}

QComboBox:disabled::drop-down {{
    opacity: 0.75;
}}

QWidget#cutting QPushButton#btnStart,QPushButton#btnEnd  {{
    border: 1px solid {tokens.palette["cta_gradient_start"]};
}}

QWidget#cutting QPushButton#btnStart:disabled,QPushButton#btnEnd:disabled {{
    color: #666666;
    border: 1px solid #666666;
}}

QWidget#cutting QPushButton#btnAddClip {{
    background-color: {tokens.palette["cta_gradient_start"]};
    color: {tokens.palette["text_primary"]};
}}

QWidget#cutting QPushButton#btnAddClip:disabled {{
    background-color: {tokens.palette["hover_bg"]};
    color: #666666;
}}

.property_value {{
    foreground-color: {tokens.palette["accent"]};
    background-color: {tokens.palette["hover_bg"]};
}}

.zoom_slider_playhead {{
    background-color: #FABE0A;
}}

QWidget#videoPreview {{
    background-color: {tokens.palette["surface_bg"]};
}}
        
/* Typography Scales */
QWidget {{ font-family: {tokens.typography["font_family"]}; font-size: {tokens.typography["base_size"]}; }}
QLabel#lblMissingFileHint {{ font-size: {tokens.typography["caption_size"]}; }}

/* Phase 5: Interaction-State Polish & CTA */
QDockWidget QWidget {{
    border-radius: {tokens.spacing["panel_radius"]};
}}

QPushButton {{
    border-radius: {tokens.spacing["button_radius"]};
}}

QPushButton#acceptButton,
QToolButton#tool-actionExportVideo {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {tokens.palette["cta_gradient_start"]}, stop:1 {tokens.palette["cta_gradient_end"]});
    border-radius: {tokens.spacing["button_radius"]};
    color: #FFFFFF;
    font-weight: bold;
}}

QPushButton#acceptButton:hover,
QToolButton#tool-actionExportVideo:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1A85FF, stop:1 #1ACDFF);
}}

QPushButton#acceptButton:pressed,
QToolButton#tool-actionExportVideo:pressed {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0066D6, stop:1 #00B3E6);
}}

QPushButton#acceptButton:focus,
QToolButton#tool-actionExportVideo:focus {{
    border: 1px solid {tokens.palette["accent"]};
}}

QTabWidget::pane {{
    border-radius: {tokens.spacing["panel_radius"]};
}}



QScrollBar:vertical {{
    width: 6px;
}}
QScrollBar::handle:vertical {{
    background-color: {tokens.palette["border_subtle"]};
    border-radius: 3px;
}}
QScrollBar::handle:vertical:hover {{
    background-color: {tokens.palette["text_secondary"]};
}}
QScrollBar:horizontal {{
    height: 6px;
}}
QScrollBar::handle:horizontal {{
    background-color: {tokens.palette["border_subtle"]};
    border-radius: 3px;
}}
QScrollBar::handle:horizontal:hover {{
    background-color: {tokens.palette["text_secondary"]};
}}
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

        log.info("Setting Fusion modern palette")
        self.app.setStyle(QStyleFactory.create("Fusion"))
        modern_palette = ui_util.make_modern_palette(self.app.palette())
        self.app.setPalette(modern_palette)

        # Set font for all widgets
        font = QFont("Ubuntu")
        font.setPointSizeF(10)
        self.app.setFont(font)

        # Move tabs to top (all dock areas, since restoreState() does not persist tab positions)
        for area in (Qt.TopDockWidgetArea, Qt.BottomDockWidgetArea,
                     Qt.LeftDockWidgetArea, Qt.RightDockWidgetArea):
            self.app.window.setTabPosition(area, QTabWidget.North)

        # Set dock widget content margins to 0
        self.set_dock_margins([2, 0, 2, 0])
        self.set_dock_margins([0, 0, 0, 0], [0, 10, 0, 0], "dockTimelineContents")

        # Apply new stylesheet
        self.app.setStyleSheet(self.compose_stylesheet())

        # Create a transparent spacer widget
        spacer = QWidget(self.app.window)
        spacer.setFixedSize(15, 1)
        spacer.setStyleSheet("background: transparent;")

        # Main toolbar buttons
        toolbar_buttons = [
            {"action": self.app.window.actionNew, "icon": "themes/modern/images/tool-new-project.svg", "style": Qt.ToolButtonTextBesideIcon},
            {"action": self.app.window.actionOpen, "icon": "themes/modern/images/tool-open-project.svg", "style": Qt.ToolButtonTextBesideIcon},
            {"action": self.app.window.actionImportFiles, "icon": "themes/modern/images/tool-import-files.svg", "style": Qt.ToolButtonTextBesideIcon},
            {"action": self.app.window.actionProfile, "icon": "themes/modern/images/tool-profile.svg", "style": Qt.ToolButtonTextBesideIcon},
            {"expand": True},
            {"action": self.app.window.actionSave, "icon": "themes/modern/images/tool-save-project.svg", "style": Qt.ToolButtonTextBesideIcon},
            {"action": self.app.window.actionExportVideo, "icon": "themes/modern/images/tool-export.svg",
             "style": Qt.ToolButtonTextBesideIcon, "stylesheet": "QToolButton { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0078FF, stop:1 #00C6FF); color: #FFFFFF; border: 1px solid transparent; border-radius: 4px; padding: 4px 14px; margin: 5px; margin-right: 10px; font-weight: bold; } QToolButton:hover { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1A85FF, stop:1 #1ACDFF); } QToolButton:pressed { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0066D6, stop:1 #00B3E6); } QToolButton:focus { border: 1px solid #7FB8FF; }"},
            {"action": self.app.window.actionUpdate, "icon": "themes/modern/images/warning.svg", "visible": False, "style": Qt.ToolButtonTextBesideIcon, "stylesheet": "QToolButton {  background-color: #141923; color: #FABE0A; }"}
        ]
        
        # Add a couple of spaces to the action text to create a gap between icon and text
        for btn in toolbar_buttons:
            if "action" in btn:
                action = btn["action"]
                text = action.text()
                if not text.startswith("  "):
                    action.setText("  " + text.strip())

        self.set_toolbar_buttons(self.app.window.toolBar, icon_size=20, settings=toolbar_buttons)

        self.app.window.actionColor_Grade_View.setIcon(
            QIcon(os.path.join(PATH, "themes/modern/images/view-color.svg"))
        )

        # Timeline toolbar buttons
        timeline_buttons = [
            {"action": self.app.window.actionAddTrack, "icon": "themes/modern/images/tool-add-track.svg", "style": Qt.ToolButtonTextBesideIcon, "stylesheet": "QToolButton { margin-left: 15px; }"},
            {"action": self.app.window.actionUndo, "icon": "themes/modern/images/tool-undo.svg", "style": Qt.ToolButtonIconOnly, "stylesheet": "QToolButton { margin-right: 0px; border-bottom-right-radius: 0px; border-top-right-radius: 0px; }"},
            {"action": self.app.window.actionRedo, "icon": "themes/modern/images/tool-redo.svg", "style": Qt.ToolButtonIconOnly, "stylesheet": "QToolButton { margin-left: 0px; border-bottom-left-radius: 0px; border-top-left-radius: 0px; }"},
            {"action": self.app.window.actionSnappingTool, "icon": "themes/modern/images/tool-snapping.svg", "style": Qt.ToolButtonIconOnly, "stylesheet": "QToolButton { margin-right: 0px; border-bottom-right-radius: 0px; border-top-right-radius: 0px; } QToolButton:focus { border: 1px solid #7FB8FF; background-color: #141923; } QToolButton:checked:focus { border: 1px solid #7FB8FF; background-color: #283241; }"},
            {"action": self.app.window.actionTimingTool, "icon": "themes/modern/images/tool-timing.svg", "style": Qt.ToolButtonIconOnly, "stylesheet": "QToolButton { margin-left: 0px; margin-right: 0px; border-bottom-left-radius: 0px; border-top-left-radius: 0px; border-bottom-right-radius: 0px; border-top-right-radius: 0px; } QToolButton:focus { border: 1px solid #7FB8FF; background-color: #141923; } QToolButton:checked:focus { border: 1px solid #7FB8FF; background-color: #283241; }"},
            {"action": self.app.window.actionRazorTool, "icon": "themes/modern/images/tool-razor.svg", "style": Qt.ToolButtonIconOnly, "stylesheet": "QToolButton { margin-left: 0px; border-bottom-left-radius: 0px; border-top-left-radius: 0px; } QToolButton:focus { border: 1px solid #7FB8FF; background-color: #141923; } QToolButton:checked:focus { border: 1px solid #7FB8FF; background-color: #283241; }"},
            {"action": self.app.window.actionAddMarker, "icon": "themes/modern/images/tool-add-marker.svg", "style": Qt.ToolButtonTextBesideIcon, "stylesheet": "QToolButton { margin-right: 0px; border-bottom-right-radius: 0px; border-top-right-radius: 0px; }"},
            {"action": self.app.window.actionPreviousMarker, "icon": "themes/modern/images/tool-prev-marker.svg", "style": Qt.ToolButtonIconOnly, "stylesheet": "QToolButton { margin-left: 0px; border-bottom-left-radius: 0px; border-top-left-radius: 0px; margin-right: 0px; border-bottom-right-radius: 0px; border-top-right-radius: 0px; }"},
            {"action": self.app.window.actionNextMarker, "icon": "themes/modern/images/tool-next-marker.svg", "style": Qt.ToolButtonIconOnly, "stylesheet": "QToolButton { margin-left: 0px; border-bottom-left-radius: 0px; border-top-left-radius: 0px; }"},
            {"action": self.app.window.actionCenterOnPlayhead, "icon": "themes/modern/images/tool-center-playhead.svg", "style": Qt.ToolButtonIconOnly, "stylesheet": "QWidget { margin-right: 10px; }"},
            {"widget": self.app.window.sliderZoomWidget},
            {"widget": spacer}
        ]
        self.set_toolbar_buttons(self.app.window.timelineToolbar, icon_size=12, settings=timeline_buttons)

        # Video toolbar
        toolbar_buttons = [
            {"expand": True},
            {"action": self.app.window.actionJumpStart, "icon": "themes/modern/images/tool-media-skip-back.svg", "style": Qt.ToolButtonIconOnly},
            {"action": self.app.window.actionRewind, "icon": "themes/modern/images/tool-media-rewind.svg", "style": Qt.ToolButtonIconOnly},
            {"action": self.app.window.actionPlay, "icon": "themes/modern/images/tool-media-play.svg", "style": Qt.ToolButtonIconOnly},
            {"action": self.app.window.actionFastForward, "icon": "themes/modern/images/tool-media-forward.svg", "style": Qt.ToolButtonIconOnly},
            {"action": self.app.window.actionJumpEnd, "icon": "themes/modern/images/tool-media-skip-forward.svg", "style": Qt.ToolButtonIconOnly},
            {"expand": True}
        ]
        self.set_toolbar_buttons(self.app.window.videoToolbar, icon_size=32, settings=toolbar_buttons)

        # Nav rail
        from qt_api import QToolBar, QSize, QActionGroup, QByteArray, QPixmap, QPainter
        win = self.app.window
        rail = win.findChild(QToolBar, "modernNavRail")
        if rail is None:
            rail = QToolBar("Navigation", win)
            rail.setObjectName("modernNavRail")
            rail.setMovable(False)
            rail.setOrientation(Qt.Orientation.Vertical)
            rail.setIconSize(QSize(22, 22))
            win.addToolBar(Qt.ToolBarArea.LeftToolBarArea, rail)

            nav_group = QActionGroup(rail)
            nav_group.setExclusive(True)

            nav_items = [
                (win.dockFiles, "themes/modern/images/tool-import-files.svg", "Project Files"),
                (win.dockTransitions, "themes/modern/images/view-waveform.svg", "Transitions"),
                (win.dockEffects, "themes/modern/images/tool-generate-sparkle.svg", "Effects"),
                (win.dockEmojis, "themes/modern/images/ai-category-create.svg", "Emojis"),
                (win.dockProperties, "themes/modern/images/tool-profile.svg", "Properties"),
            ]
            for dock, icon_path, tooltip in nav_items:
                icon = QIcon()
                try:
                    with open(os.path.join(PATH, icon_path), "r") as f:
                        svg_data = f.read()
                    
                    # Convert any blues to neutral gray
                    svg_gray = re.sub(r'#0078FF|#2A82DA|#53A0ED', '#8B95A5', svg_data, flags=re.IGNORECASE)
                    # Active gets the accent blue
                    svg_active = re.sub(r'#8B95A5|#0078FF|#2A82DA|#53A0ED', '#0078FF', svg_data, flags=re.IGNORECASE)
                    
                    pm_gray = QPixmap()
                    pm_gray.loadFromData(QByteArray(svg_gray.encode("utf-8")))
                    
                    pm_active = QPixmap()
                    pm_active.loadFromData(QByteArray(svg_active.encode("utf-8")))

                    # Normal (Off) -> 55% opacity gray
                    pm_off = QPixmap(pm_gray.size())
                    pm_off.fill(Qt.transparent)
                    painter = QPainter(pm_off)
                    painter.setOpacity(0.55)
                    painter.drawPixmap(0, 0, pm_gray)
                    painter.end()

                    # Hover (Active, Off) -> 80% opacity gray
                    pm_hover = QPixmap(pm_gray.size())
                    pm_hover.fill(Qt.transparent)
                    painter = QPainter(pm_hover)
                    painter.setOpacity(0.80)
                    painter.drawPixmap(0, 0, pm_gray)
                    painter.end()

                    icon.addPixmap(pm_off, QIcon.Normal, QIcon.Off)
                    icon.addPixmap(pm_hover, QIcon.Active, QIcon.Off)
                    icon.addPixmap(pm_active, QIcon.Normal, QIcon.On)
                    icon.addPixmap(pm_active, QIcon.Active, QIcon.On)
                except Exception:
                    icon = QIcon(os.path.join(PATH, icon_path))
                
                action = rail.addAction(icon, "")
                action.setToolTip(tooltip)
                action.setCheckable(True)
                nav_group.addAction(action)
                
                # Make the first one checked by default
                if tooltip == "Project Files":
                    action.setChecked(True)
                
                action.triggered.connect(lambda checked, d=dock, a=action: (d.show(), d.raise_(), a.setChecked(True)))

            rail.setStyleSheet(
                "QToolBar { background-color: #141820; border: none; padding-top: 8px; } "
                "QToolButton { padding: 8px 10px; border-radius: 0px; border: none; margin: 4px 0px; border-left: 2px solid transparent; } "
                "QToolButton:hover { background-color: #1A1F29; border-left: 2px solid #232A36; } "
                "QToolButton:checked { border-left: 2px solid #0078FF; background-color: #1A1F29; }"
            )

        from .styles import ModernTimelineTheme
        self.app.window.timeline.apply_theme(ModernTimelineTheme())

        # Emit signal
        self.app.window.ThemeChangedSignal.emit(self)

    def togglePlayIcon(self, isPlay):
        """ Toggle the play icon from play to pause and back """
        button = self.app.window.videoToolbar.widgetForAction(self.app.window.actionPlay)
        if button:
            if not isPlay:
                play_icon_path = os.path.join(PATH, "themes/modern/images/tool-media-play.svg")
                button.setIcon(QIcon(play_icon_path))
            else:
                pause_icon_path = os.path.join(PATH, "themes/modern/images/tool-media-pause.svg")
                button.setIcon(QIcon(pause_icon_path))
