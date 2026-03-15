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

from PyQt5.QtCore import Qt, QSize, QTimer
from PyQt5.QtGui import QIcon, QPainter, QPixmap, QTransform
from PyQt5.QtWidgets import QDockWidget, QMenu, QTabBar, QTabWidget, QWidget

from classes.info import PATH
from ..base import BaseTheme


# ── Design tokens (Cursor-IDE inspired dark palette) ──────────────────────
#
#   BG_DEEP    #0d0d0d   main window / dialog floor  ← the "absolute black"
#   BG_MAIN    #0d0d0d   primary panel surface       ← same as deep black (2-tone palette)
#   BG_RAISED  #252525   raised surfaces, hover
#   BG_PRESS   #2e2e2e   pressed / active toggle
#   BG_INPUT   #0d0d0d   text inputs (same as deep black)
#
#   TEXT       #d4d4d4   primary text
#   TEXT_DIM   #8a8a8a   secondary / muted text
#   TEXT_OFF   #555555   disabled text
#
#   BORDER     rgba(255,255,255,0.07)   subtle border
#   BORDER_HI  rgba(255,255,255,0.13)  hover border
#   ACCENT     #4d9cf6   blue accent
#   ACCENT_HVR #3b8fe8   accent hover
#   PLAYHEAD   #f59e0b   amber playhead
#   DANGER     #ef4444   destructive red
#   SEL_BG     rgba(77,156,246,0.18)   selection highlight
# ──────────────────────────────────────────────────────────────────────────


class CosmicTheme(BaseTheme):
    def __init__(self, app):
        super().__init__(app)

        from classes.app import get_app
        _ = get_app()._tr

        # ── Base stylesheet ────────────────────────────────────────────────
        # Assigned first so get_color() / get_int() can parse it.
        # The f-string replacement (PATH, translated strings) happens below.
        self.style_sheet = """

/* ── Window & dialog ─────────────────────────────────────── */
QMainWindow {
    background-color: #0d0d0d;
    color: #d4d4d4;
}

QMainWindow::separator {
    background: rgba(255,255,255,0.06);
    width: 1px;
    height: 1px;
}

QMainWindow::separator:hover {
    background: rgba(77, 156, 246, 0.5);
}

QDialog {
    background-color: #0d0d0d;
    color: #d4d4d4;
}

QWidget {
    color: #d4d4d4;
}

/* ── Tooltips ─────────────────────────────────────────────── */
QToolTip {
    background-color: #252525;
    color: #d4d4d4;
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 6px;
    padding: 4px 10px;
    font-size: 11px;
}

/* ── Tutorial widget ──────────────────────────────────────── */
QWidget#tutorial {
    background-color: #0d0d0d;
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 6px;
    padding: 20px;
}

QLabel#lblTutorialText  { font-size: 14px; }
QCheckBox#checkboxMetrics { font-size: 14px; }

QWidget#tutorial QPushButton#NextTip,
QWidget#tutorial QPushButton#HideTutorial {
    font-size: 12px;
}

/* ── Preference / settings panels ────────────────────────── */
QWidget#Simple, QWidget#Advanced, QWidget#PreferencePanel,
QWidget#settingsContainer, QWidget#scrollAreaWidgetContents {
    background-color: #0d0d0d;
    border: none;
}

QScrollArea { border: none; background: transparent; }
QTabWidget   { border: none; }

/* ── Menu bar ─────────────────────────────────────────────── */
QMenuBar {
    background-color: #0d0d0d;
    color: #d4d4d4;
    padding: 0;
    border: none;
    border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

QMenuBar::item {
    padding: 5px 10px;
    background: transparent;
}

QMenuBar::item:selected,
QMenuBar::item:pressed {
    background-color: #252525;
    border-radius: 3px;
}

/* ── Dropdown menus ───────────────────────────────────────── */
QMenu {
    background-color: #252525;
    color: #d4d4d4;
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 8px;
    padding: 4px;
}

QMenu::item {
    padding: 5px 16px 5px 10px;
    border-radius: 4px;
}

QMenu::item:selected {
    background-color: rgba(77, 156, 246, 0.15);
    color: #d4d4d4;
}

QMenu::item:disabled { color: #555555; }

QMenu::separator {
    height: 1px;
    background: rgba(255, 255, 255, 0.08);
    margin: 3px 6px;
}

QMenu::indicator:checked {
    image: url({PATH}themes/cosmic/images/dropdown-tick.svg);
}

/* ── Main toolbar ─────────────────────────────────────────── */
QToolBar#toolBar {
    background-color: #0d0d0d;
    border-bottom: 1px solid rgba(255, 255, 255, 0.06);
    spacing: 0;
    padding: 0 4px;
}

QToolBar#toolBar QToolButton {
    background-color: transparent;
    color: #d4d4d4;
    padding: 8px 10px;
    border: none;
    border-radius: 6px;
}

QToolBar#toolBar QToolButton:hover   { background-color: #252525; }
QToolBar#toolBar QToolButton:pressed { background-color: #2e2e2e; }

/* ── Timeline toolbar ─────────────────────────────────────── */
QToolBar#timelineToolbar {
    background-color: #0d0d0d;
    border-top: 1px solid rgba(255, 255, 255, 0.06);
    spacing: 0;
    padding: 0 2px;
}

QToolBar#timelineToolbar QToolButton {
    color: #d4d4d4;
    background-color: transparent;
    padding: 6px 7px;
    margin: 3px 2px;
    border-radius: 6px;
    border: none;
}

QToolBar#timelineToolbar QToolButton:hover   { background-color: #252525; }
QToolBar#timelineToolbar QToolButton:pressed { background-color: #2e2e2e; }
QToolBar#timelineToolbar QToolButton:checked { background-color: rgba(77, 156, 246, 0.18); }

/* General toolbar button defaults (video toolbar etc.) */
QToolBar QToolButton:hover   { background-color: #252525; }
QToolBar QToolButton:pressed { background-color: #2e2e2e; }

QToolBar::separator {
    background: rgba(255, 255, 255, 0.08);
    width: 1px;
    margin: 4px 3px;
}

/* ── Push buttons ─────────────────────────────────────────── */
QPushButton {
    background-color: #252525;
    color: #d4d4d4;
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 6px;
    padding: 6px 14px;
    min-height: 22px;
}

QPushButton:hover {
    background-color: #2e2e2e;
    border-color: rgba(255, 255, 255, 0.2);
}

QPushButton:pressed { background-color: #333333; }
QPushButton:disabled { color: #555555; border-color: rgba(255,255,255,0.05); }

QPushButton#acceptButton {
    background-color: #4d9cf6;
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 6px 16px;
    font-weight: 500;
}

QPushButton#acceptButton:hover   { background-color: #3b8fe8; }
QPushButton#acceptButton:pressed { background-color: #2f7fd6; }


/* ── Labels ───────────────────────────────────────────────── */
QLabel { color: #d4d4d4; }

QLabel#dock-title-label {
    color: #d4d4d4;
    font-weight: 500;
    padding: 0 14px;
    font-size: 11px;
    letter-spacing: 0.02em;
}

QLabel#dock-title-handle {
    padding-left: 14px;
    qproperty-pixmap: url({PATH}themes/cosmic/images/dock-move.svg);
}

/* ── Dock widgets ─────────────────────────────────────────── */
QDockWidget {
    background-color: #0d0d0d;
    titlebar-close-icon:  url({PATH}themes/cosmic/images/dock-close.svg);
    titlebar-normal-icon: url({PATH}themes/cosmic/images/dock-float.svg);
    color: #d4d4d4;
    font-weight: 500;
}

QDockWidget::title {
    background-color: #0d0d0d;
    border-bottom: 1px solid rgba(255, 255, 255, 0.06);
    padding: 9px 14px;
    text-align: left;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
}

/* Hide close & float buttons – accessible via right-click on title bar */
QDockWidget::close-button,
QDockWidget::float-button {
    max-width: 0px;
    max-height: 0px;
    padding: 0px;
    margin: 0px;
    border: none;
    background: transparent;
    image: none;
}

/* Nav dock title bar: compact float + close icon buttons */
QPushButton#dock-float-button,
QPushButton#dock-close-button {
    background: transparent;
    border: none;
    border-radius: 4px;
    color: #6b7280;
    font-size: 11px;
    padding: 0px;
}
QPushButton#dock-float-button:hover {
    background: rgba(255,255,255,0.07);
    color: #d4d4d4;
}
QPushButton#dock-close-button:hover {
    background: rgba(239,68,68,0.15);
    color: #ef4444;
}

QDockWidget QWidget { border: none; }

/* Dock content areas */
QDockWidget QWidget#dockFilesContents,
QWidget#dockTransitionsContents,
QWidget#dockEmojisContents,
QWidget#dockEffectsContents,
QWidget#dockCaptionContents,
QWidget#dockPropertiesContents {
    background-color: #0d0d0d;
    border-radius: 0;
    margin: 0 12px;
}

/* Video preview dock – no side margins, glow border on the actual preview */
QWidget#dockVideoContents {
    background-color: #0d0d0d;
    border-radius: 0;
    margin: 0;
}

/* Subtle white glow to visually separate the video canvas */
QWidget#videoPreview {
    background-color: #000000;
    border: 1px solid rgba(255, 255, 255, 0.18);
    border-radius: 4px;
}

QDockWidget QWidget#dockTimelineContents {
    border-radius: 0;
    margin: 0;
    padding: 0;
}

/* ── Tab bar ──────────────────────────────────────────────── */
QTabBar {
    border: none;
    qproperty-drawBase: 0;
    qproperty-expanding: 0;
    background: #0d0d0d;
}

/* Vertical dock-panel nav tabs (West position) – icon only, no text */
QTabBar::tab {
    background: transparent;
    color: transparent;
    font-size: 1px;
    border: none;
    padding: 0px;
    margin: 2px 0;
    border-right: 2px solid transparent;
    min-width: 36px;
    max-width: 36px;
    min-height: 36px;
    text-align: center;
}

QTabBar::tab:selected {
    background: rgba(77, 156, 246, 0.12);
    border-right: 2px solid #4d9cf6;
}

QTabBar::tab:hover:!selected {
    background: rgba(255, 255, 255, 0.05);
}

/* Override for export / preferences dialogs that use horizontal (North) tabs */
QTabWidget#exportTabs QTabBar::tab,
QTabWidget#tabCategories QTabBar::tab,
QTabWidget#tabCredits QTabBar::tab {
    padding: 6px 14px;
    border-right: none;
    border-bottom: 2px solid transparent;
    margin-bottom: 8px;
    max-width: 400px;
    text-align: center;
}

QTabWidget#exportTabs QTabBar::tab:selected,
QTabWidget#tabCategories QTabBar::tab:selected,
QTabWidget#tabCredits QTabBar::tab:selected {
    border-right: none;
    border-bottom: 2px solid #4d9cf6;
    background: transparent;
}

/* ── Line edit (general) ──────────────────────────────────── */
QLineEdit {
    background-color: #0d0d0d;
    color: #d4d4d4;
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 6px;
    padding: 5px 8px;
    selection-background-color: rgba(77, 156, 246, 0.3);
}

QLineEdit:hover  { border-color: rgba(255, 255, 255, 0.18); }
QLineEdit:focus  { border-color: #4d9cf6; }
QLineEdit:disabled { color: #555555; border-color: rgba(255, 255, 255, 0.05); }

/* Filter boxes in dock panels */
QLineEdit#filesFilter,
QLineEdit#effectsFilter,
QLineEdit#transitionsFilter,
QLineEdit#emojisFilter,
QLineEdit#txtPropertyFilter {
    background-color: #0d0d0d;
    border-radius: 6px;
    padding: 5px 10px;
}

/* ── Text edit ────────────────────────────────────────────── */
QTextEdit, QPlainTextEdit {
    background-color: #0d0d0d;
    color: #d4d4d4;
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 6px;
    padding: 4px;
    selection-background-color: rgba(77, 156, 246, 0.3);
}

QTextEdit:focus, QPlainTextEdit:focus { border-color: #4d9cf6; }

/* ── Spin box ─────────────────────────────────────────────── */
QSpinBox, QDoubleSpinBox {
    background-color: #0d0d0d;
    color: #d4d4d4;
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 6px;
    padding: 4px 8px;
    selection-background-color: rgba(77, 156, 246, 0.3);
}

QSpinBox:focus,
QDoubleSpinBox:focus { border-color: #4d9cf6; }

QSpinBox::up-button,
QDoubleSpinBox::up-button,
QSpinBox::down-button,
QDoubleSpinBox::down-button {
    background: transparent;
    border: none;
    width: 16px;
}

/* ── Scroll bars ──────────────────────────────────────────── */
QScrollBar:vertical {
    border: none;
    background: transparent;
    width: 6px;
}

QScrollBar::handle:vertical {
    background: rgba(255, 255, 255, 0.16);
    border-radius: 3px;
    min-height: 24px;
}

QScrollBar::handle:vertical:hover { background: rgba(255, 255, 255, 0.28); }

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    height: 0;
    border: none;
    background: transparent;
}

QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical { background: transparent; }

QScrollBar:horizontal {
    border: none;
    background: transparent;
    height: 6px;
}

QScrollBar::handle:horizontal {
    background: rgba(255, 255, 255, 0.16);
    border-radius: 3px;
    min-width: 24px;
}

QScrollBar::handle:horizontal:hover { background: rgba(255, 255, 255, 0.28); }

QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal {
    width: 0;
    border: none;
    background: transparent;
}

QScrollBar::add-page:horizontal,
QScrollBar::sub-page:horizontal { background: transparent; }

/* ── Combo box ────────────────────────────────────────────── */
QComboBox {
    background-color: #252525;
    color: #d4d4d4;
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 6px;
    padding: 5px 8px;
    combobox-popup: 0;
}

QComboBox:hover  { border-color: rgba(255, 255, 255, 0.2); }
QComboBox:focus  { border-color: #4d9cf6; }

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 32px;
    border: none;
}

QComboBox::down-arrow {
    image: url({PATH}themes/cosmic/images/dropdown-arrow.svg);
}

QComboBox QAbstractItemView {
    background-color: #252525;
    color: #d4d4d4;
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 8px;
    padding: 4px;
    selection-background-color: rgba(77, 156, 246, 0.2);
}

QComboBox::item        { height: 24px; }
QComboBox::item:selected  { background-color: rgba(77, 156, 246, 0.2); }
QComboBox::item:checked   { font-weight: 600; }
QComboBox::indicator::checked {
    image: url({PATH}themes/cosmic/images/dropdown-tick.svg);
}

/* ── Tree / List / Table views ────────────────────────────── */
QTreeView, QListView, QTableView {
    background-color: #0d0d0d;
    border: none;
    color: #d4d4d4;
    gridline-color: rgba(255, 255, 255, 0.05);
    alternate-background-color: rgba(255, 255, 255, 0.02);
    show-decoration-selected: 1;
}

QTreeView::item:hover,
QListView::item:hover,
QTableView::item:hover {
    background: rgba(255, 255, 255, 0.05);
}

QTreeView::item:selected,
QListView::item:selected,
QTableView::item:selected {
    background: rgba(77, 156, 246, 0.18);
    color: #d4d4d4;
}

QHeaderView::section {
    background-color: #0d0d0d;
    color: #8a8a8a;
    padding: 5px 8px;
    border: none;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    font-size: 11px;
}

QHeaderView::section:hover {
    background-color: #252525;
    color: #d4d4d4;
}

/* ── Splitter handles ─────────────────────────────────────── */
QSplitter::handle {
    background: rgba(255, 255, 255, 0.04);
}

QSplitter::handle:horizontal { width: 1px; }
QSplitter::handle:vertical   { height: 1px; }

QSplitter::handle:hover {
    background: rgba(77, 156, 246, 0.35);
}

/* ── Slider ───────────────────────────────────────────────── */
QSlider::groove:horizontal {
    background: rgba(255, 255, 255, 0.1);
    height: 3px;
    border-radius: 2px;
}

QSlider::handle:horizontal {
    background: #4d9cf6;
    border: none;
    width: 12px;
    height: 12px;
    margin: -5px 0;
    border-radius: 6px;
}

QSlider::handle:horizontal:hover { background: #3b8fe8; }

QSlider::sub-page:horizontal {
    background: rgba(77, 156, 246, 0.45);
    border-radius: 2px;
}

QSlider::groove:vertical {
    background: rgba(255, 255, 255, 0.1);
    width: 3px;
    border-radius: 2px;
}

QSlider::handle:vertical {
    background: #4d9cf6;
    border: none;
    width: 12px;
    height: 12px;
    margin: 0 -5px;
    border-radius: 6px;
}

QSlider::sub-page:vertical {
    background: rgba(77, 156, 246, 0.45);
    border-radius: 2px;
}

/* ── Checkbox ─────────────────────────────────────────────── */
QCheckBox {
    color: #d4d4d4;
    spacing: 6px;
}

QCheckBox::indicator {
    width: 14px;
    height: 14px;
    border: 1px solid rgba(255, 255, 255, 0.2);
    border-radius: 3px;
    background: #0d0d0d;
}

QCheckBox::indicator:hover          { border-color: #4d9cf6; }
QCheckBox::indicator:checked        { background: #4d9cf6; border-color: #4d9cf6; }
QCheckBox::indicator:indeterminate  { background: rgba(77, 156, 246, 0.5); border-color: #4d9cf6; }

/* ── Radio button ─────────────────────────────────────────── */
QRadioButton {
    color: #d4d4d4;
    spacing: 6px;
}

QRadioButton::indicator {
    width: 14px;
    height: 14px;
    border: 1px solid rgba(255, 255, 255, 0.2);
    border-radius: 7px;
    background: #0d0d0d;
}

QRadioButton::indicator:hover   { border-color: #4d9cf6; }
QRadioButton::indicator:checked { background: #4d9cf6; border-color: #4d9cf6; }

/* ── Group box ────────────────────────────────────────────── */
QGroupBox {
    color: #8a8a8a;
    font-size: 11px;
    border: 1px solid rgba(255, 255, 255, 0.07);
    border-radius: 6px;
    margin-top: 20px;
    padding-top: 10px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    /* No left offset — avoids clipping on narrow docks */
    left: 8px;
    top: -6px;
    padding: 1px 6px;
    background: #0d0d0d;
    border-radius: 3px;
    /* Prevent the title text from wrapping or being cut */
    min-width: 0;
}

/* ── Tool box ─────────────────────────────────────────────── */
QToolBox::tab {
    background: #252525;
    color: #d4d4d4;
    border: none;
    border-top: 1px solid rgba(255, 255, 255, 0.08);
    padding: 5px 10px;
}

QToolBox::tab:selected { color: #4d9cf6; }

/* ── Progress bar ─────────────────────────────────────────── */
QProgressBar {
    background: rgba(255, 255, 255, 0.08);
    border: none;
    border-radius: 3px;
    height: 4px;
    text-align: center;
    color: transparent;
}

QProgressBar::chunk {
    background: #4d9cf6;
    border-radius: 3px;
}

/* ── Frame dividers ───────────────────────────────────────── */
QFrame[frameShape="4"] {
    /* HLine */
    background: rgba(255, 255, 255, 0.07);
    max-height: 1px;
    border: none;
    margin: 2px 0;
}

QFrame[frameShape="5"] {
    /* VLine */
    background: rgba(255, 255, 255, 0.07);
    max-width: 1px;
    border: none;
    margin: 0 2px;
}

/* ── Output / details panels ──────────────────────────────── */
QWidget#Details, QWidget#Output { background-color: #0d0d0d; }
QWidget#Output QTextEdit         { color: #d4d4d4; }

/* ── Export / cutting dialog specifics ───────────────────── */
QTabWidget QWidget#pageAdvancedOptions,
QWidget#pageProfile,
QWidget#pageImageSequenceSettings,
QWidget#pageVideoSettings,
QWidget#pageAudioSettings,
QTabWidget QWidget#pageVideoDetails,
QWidget#pageVideoFormat,
QWidget#pageAudioFormat,
QWidget#pageFrameSettings {
    background-color: #0d0d0d;
}

QWidget#cutting QPushButton#btnStart,
QPushButton#btnEnd {
    border: 1px solid rgba(255, 255, 255, 0.18);
}

QWidget#cutting QPushButton#btnStart:disabled,
QPushButton#btnEnd:disabled {
    color: #555555;
    border-color: rgba(255, 255, 255, 0.08);
}

QWidget#cutting QPushButton#btnAddClip {
    background-color: #4d9cf6;
    color: #ffffff;
    border: none;
}

QWidget#cutting QPushButton#btnAddClip:disabled {
    background-color: #252525;
    color: #555555;
}

/* ── Property panel token colors ─────────────────────────── */
.property_value {
    foreground-color: #4d9cf6;
    background-color: #1e2a3a;
}

/* ── Zoom slider playhead ─────────────────────────────────── */
.zoom_slider_playhead { background-color: #f59e0b; }

/* ── Video preview ────────────────────────────────────────── */
QWidget#videoPreview { background-color: #0d0d0d; }

/* ── AI Media Manager dock ────────────────────────────────── */
QDockWidget#AIMediaPanel QWidget,
QDockWidget#AIMediaPanel QTabWidget,
QDockWidget#AIMediaPanel QTabWidget::pane {
    background-color: #0d0d0d;
    border: none;
}

QDockWidget#AIMediaPanel QListWidget,
QDockWidget#AIMediaPanel QTreeWidget {
    background-color: #0d0d0d;
    border: none;
}

QDockWidget#AIMediaPanel QTabBar::tab {
    padding: 5px 12px;
    font-size: 11px;
    max-width: 400px;
}

/* Make the tag search feel like a real search field */
QDockWidget#AIMediaPanel QLineEdit {
    background: #0d0d0d;
    border-radius: 5px;
    padding: 5px 10px;
}

/* Compact list rows in the Tags list */
QDockWidget#AIMediaPanel QListWidget,
QDockWidget#AIMediaPanel QTreeWidget {
    font-size: 11px;
}

QDockWidget#AIMediaPanel QListWidget::item,
QDockWidget#AIMediaPanel QTreeWidget::item {
    padding: 3px 4px;
    border-radius: 3px;
}

QDockWidget#AIMediaPanel QListWidget::item:selected,
QDockWidget#AIMediaPanel QTreeWidget::item:selected {
    background: rgba(77, 156, 246, 0.18);
}

/* ── Tree/List view item height ───────────────────────────── */
QTreeView::item,
QListView::item {
    min-height: 22px;
    padding: 2px 4px;
    border-radius: 3px;
}

/* ── Status bar (hidden in theme but styled if shown) ─────── */
QStatusBar {
    background: #0d0d0d;
    color: #8a8a8a;
    font-size: 11px;
    border-top: 1px solid rgba(255, 255, 255, 0.06);
}

/* ── AI Chat dock (Qt wrapper) ────────────────────────────── */
QDockWidget#AIChatWindow QWidget#AIChatWindowContents {
    background-color: #0d0d0d;
}

QDockWidget#AIChatWindow QFrame#chatPreamble {
    background-color: #0d0d0d;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 0;
}

QDockWidget#AIChatWindow QLabel#chatPreambleLabel {
    color: #d4d4d4;
    font-size: 12px;
}

QDockWidget#AIChatWindow QTextEdit#chatBox {
    background-color: #0d0d0d;
    color: #d4d4d4;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 0;
    padding: 8px;
}

QDockWidget#AIChatWindow QTextEdit#msgInput {
    background-color: #0d0d0d;
    color: #d4d4d4;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 0;
    padding: 6px;
}

QDockWidget#AIChatWindow QPushButton#sendBtn,
QDockWidget#AIChatWindow QPushButton#clearBtn {
    background-color: #252525;
    color: #d4d4d4;
    border: 1px solid rgba(255, 255, 255, 0.1);
}

QDockWidget#AIChatWindow QPushButton#sendBtn:hover,
QDockWidget#AIChatWindow QPushButton#clearBtn:hover {
    background-color: #2e2e2e;
}

QDockWidget#AIChatWindow QComboBox#modelCombo {
    background-color: #252525;
    color: #d4d4d4;
    border: 1px solid rgba(255, 255, 255, 0.1);
}
        """

        # Prepend translated message-box buttons, and expand {PATH}
        path_unix_slashes = PATH.replace("\\", "/")
        self.style_sheet = f"""
QMessageBox QPushButton[text="&{_('Yes')}"] {{
    background-color: #4d9cf6;
    color: #ffffff;
    border: none;
    padding: 6px 16px;
    border-radius: 4px;
}}

QMessageBox QPushButton[text="&{_('Cancel')}"] {{
    qproperty-icon: none;
}}
        """ + self.style_sheet.replace("{PATH}", f"{path_unix_slashes}/")

    # ── apply_theme ────────────────────────────────────────────────────────
    def apply_theme(self):
        super().apply_theme()

        from classes.app import get_app
        from classes import ui_util
        from classes.logger import log
        from PyQt5.QtWidgets import QStyleFactory
        from PyQt5.QtGui import QFont

        _ = get_app()._tr

        log.info("Setting Fusion dark palette (Cursor theme)")
        self.app.setStyle(QStyleFactory.create("Fusion"))
        dark_palette = ui_util.make_dark_palette(self.app.palette())

        # Override palette to absolute black so all unstyled QWidget backgrounds
        # default to #0d0d0d instead of the default medium-gray (53,53,53)
        from PyQt5.QtGui import QColor as _QColor
        _black = _QColor(13, 13, 13)
        _gray  = _QColor(37, 37, 37)
        from PyQt5.QtGui import QPalette as _QPalette
        dark_palette.setColor(_QPalette.Window,        _black)
        dark_palette.setColor(_QPalette.Base,          _black)
        dark_palette.setColor(_QPalette.AlternateBase, _black)
        dark_palette.setColor(_QPalette.Button,        _gray)
        dark_palette.setColor(_QPalette.Mid,           _black)
        dark_palette.setColor(_QPalette.Dark,          _black)

        self.app.setPalette(dark_palette)

        # Compact font
        font = QFont("Ubuntu")
        font.setPointSizeF(8)
        self.app.setFont(font)

        # Tabs on the left side (vertical menu style)
        self.app.window.setTabPosition(Qt.TopDockWidgetArea, QTabWidget.West)

        # Dock content margins
        self.set_dock_margins([14, 0, 14, 0])
        self.set_dock_margins([0, 0, 0, 0], [0, 8, 0, 0], "dockTimelineContents")

        # Re-apply the full stylesheet
        self.app.setStyleSheet(self.style_sheet)

        # ── Dock nav tab icons (icon-only, text hidden via QSS) ───────
        win = self.app.window

        _img_dir = os.path.join(PATH, "themes/cosmic/images")
        _tab_size = 36   # must match the min/max-width/height in the instance stylesheet
        _icon_size = QSize(20, 20)
        _icon_offset = (_tab_size - _icon_size.width()) // 2  # 8px — centers 20px icon in 36px tab

        def _nav_icon(filename):
            """Load SVG, center it in a _tab_size × _tab_size canvas, then pre-rotate 90° CW
            to cancel Qt's CCW rotation for West tabs. Centering is baked into the pixmap so
            that Qt's icon placement doesn't matter."""
            raw_icon = QIcon(os.path.join(_img_dir, filename))
            src_pix = raw_icon.pixmap(_icon_size)
            # Paint the 20×20 icon onto a transparent _tab_size×_tab_size canvas
            canvas = QPixmap(_tab_size, _tab_size)
            canvas.fill(Qt.transparent)
            painter = QPainter(canvas)
            painter.drawPixmap(_icon_offset, _icon_offset, src_pix)
            painter.end()
            # Pre-rotate 90° CW to cancel Qt's built-in CCW rotation for West tabs
            return QIcon(canvas.transformed(QTransform().rotate(90)))

        _nav_icon_map = {
            win.dockFiles.windowTitle():       _nav_icon("nav-files.svg"),
            win.dockTransitions.windowTitle(): _nav_icon("nav-transitions.svg"),
            win.dockEffects.windowTitle():     _nav_icon("nav-effects.svg"),
            win.dockEmojis.windowTitle():      _nav_icon("nav-emojis.svg"),
        }

        # Also set windowIcon so Qt uses it as fallback
        for dock, icon in zip(
            [win.dockFiles, win.dockTransitions, win.dockEffects, win.dockEmojis],
            _nav_icon_map.values(),
        ):
            dock.setWindowIcon(icon)

        def _apply_tab_icons():
            """Write icons onto every QTabBar that hosts nav docks.
            Matches by windowTitle (text) or by tooltip (already-processed tabs)."""
            for tabbar in win.findChildren(QTabBar):
                tabbar.setIconSize(QSize(_tab_size, _tab_size))
                has_nav = False
                for i in range(tabbar.count()):
                    text = tabbar.tabText(i)
                    tooltip = tabbar.tabToolTip(i)
                    # Match by original title (fresh tab) or preserved tooltip (re-opened tab)
                    key = text if text in _nav_icon_map else (tooltip if tooltip in _nav_icon_map else None)
                    if key is None:
                        continue
                    has_nav = True
                    tabbar.setTabIcon(i, _nav_icon_map[key])
                    tabbar.setTabToolTip(i, key)    # dock name for hover display
                    tabbar.setTabText(i, "")        # remove text — eliminates reserved height
                if has_nav:
                    # Only disable expanding on the nav sidebar tabbar — not dialog tabbars
                    tabbar.setExpanding(False)
                    # Force fixed tab height via instance-level stylesheet (highest priority).
                    # Global QSS max-width/max-height are ignored after text-based size is cached,
                    # but instance stylesheet overrides the cached sizeHint.
                    tabbar.setStyleSheet("""
                        QTabBar::tab {
                            min-width:  36px;
                            max-width:  36px;
                            min-height: 36px;
                            max-height: 36px;
                            padding:    0px;
                            margin:     2px 0px;
                            border-right: 2px solid transparent;
                        }
                        QTabBar::tab:selected {
                            background: rgba(77,156,246,0.12);
                            border-right: 2px solid #4d9cf6;
                        }
                        QTabBar::tab:hover:!selected {
                            background: rgba(255,255,255,0.05);
                        }
                    """)

        def _schedule_tab_icons():
            QTimer.singleShot(150, _apply_tab_icons)

        # Run immediately and after event-loop settle
        _apply_tab_icons()
        QTimer.singleShot(200, _apply_tab_icons)

        # Re-apply when a nav dock is shown/hidden (close→reopen from Views menu)
        # and when dock location changes (dock moved, tabified, detached)
        for _dock in [win.dockFiles, win.dockTransitions, win.dockEffects, win.dockEmojis]:
            _dock.visibilityChanged.connect(_schedule_tab_icons)
            _dock.dockLocationChanged.connect(lambda _area: _schedule_tab_icons())

        # ── Dock close/float via right-click only ─────────────────────

        def _dock_context_menu(dock, global_pos):
            menu = QMenu(dock)
            if dock.isFloating():
                action = menu.addAction("Dock")
                action.triggered.connect(lambda: dock.setFloating(False))
            else:
                action = menu.addAction("Undock / Float")
                action.triggered.connect(lambda: dock.setFloating(True))
            menu.addSeparator()
            close_action = menu.addAction("Close Panel")
            close_action.triggered.connect(dock.close)
            menu.exec_(global_pos)

        for dock in win.findChildren(QDockWidget):
            dock.setContextMenuPolicy(Qt.CustomContextMenu)
            dock.customContextMenuRequested.connect(
                lambda pos, d=dock: _dock_context_menu(d, d.mapToGlobal(pos))
            )

        # Transparent spacer for toolbar end padding
        spacer = QWidget(self.app.window)
        spacer.setFixedSize(12, 1)
        spacer.setStyleSheet("background: transparent;")

        # ── Main toolbar (icon-only; action text shown as tooltip on hover) ──
        toolbar_buttons = [
            {"action": self.app.window.actionNew,         "icon": "themes/cosmic/images/tool-new-project.svg",  "style": Qt.ToolButtonIconOnly},
            {"action": self.app.window.actionOpen,        "icon": "themes/cosmic/images/tool-open-project.svg", "style": Qt.ToolButtonIconOnly},
            {"action": self.app.window.actionImportFiles, "icon": "themes/cosmic/images/tool-import-files.svg", "style": Qt.ToolButtonIconOnly},
            {"action": self.app.window.actionProfile,     "icon": "themes/cosmic/images/tool-profile.svg",      "style": Qt.ToolButtonIconOnly},
            {"expand": True},
            {"action": self.app.window.actionSave,        "icon": "themes/cosmic/images/tool-save-project.svg", "style": Qt.ToolButtonIconOnly},
            {
                "action": self.app.window.actionExportVideo,
                "icon": "themes/cosmic/images/tool-export.svg",
                "style": Qt.ToolButtonIconOnly,
                "stylesheet": (
                    "QToolButton { background-color: #4d9cf6; color: #ffffff; border: none; border-radius: 6px; padding: 8px 12px; } "
                    "QToolButton:hover, QToolButton:pressed { background-color: #3b8fe8; }"
                ),
            },
            {
                "action": self.app.window.actionUpdate,
                "icon": "themes/cosmic/images/warning.svg",
                "visible": False,
                "style": Qt.ToolButtonIconOnly,
                "stylesheet": "QToolButton { background-color: #252525; color: #f59e0b; }",
            },
        ]
        self.set_toolbar_buttons(self.app.window.toolBar, icon_size=20, settings=toolbar_buttons)

        # ── Timeline toolbar (all icon-only) ─────────────────────────
        timeline_buttons = [
            {"action": self.app.window.actionAddTrack,        "icon": "themes/cosmic/images/tool-add-track.svg",       "style": Qt.ToolButtonIconOnly, "stylesheet": "QToolButton { margin-left: 12px; }"},
            {"action": self.app.window.actionUndo,            "icon": "themes/cosmic/images/tool-undo.svg",            "style": Qt.ToolButtonIconOnly, "stylesheet": "QToolButton { margin-right: 0; border-top-right-radius: 0; border-bottom-right-radius: 0; }"},
            {"action": self.app.window.actionRedo,            "icon": "themes/cosmic/images/tool-redo.svg",            "style": Qt.ToolButtonIconOnly, "stylesheet": "QToolButton { margin-left: 0; border-top-left-radius: 0; border-bottom-left-radius: 0; }"},
            {"action": self.app.window.actionSnappingTool,    "icon": "themes/cosmic/images/tool-snapping.svg",        "style": Qt.ToolButtonIconOnly, "stylesheet": "QToolButton { margin-right: 0; border-top-right-radius: 0; border-bottom-right-radius: 0; }"},
            {"action": self.app.window.actionTimingTool,      "icon": "themes/cosmic/images/tool-timing.svg",          "style": Qt.ToolButtonIconOnly, "stylesheet": "QToolButton { margin: 0; border-radius: 0; }"},
            {"action": self.app.window.actionRazorTool,       "icon": "themes/cosmic/images/tool-razor.svg",           "style": Qt.ToolButtonIconOnly, "stylesheet": "QToolButton { margin-left: 0; border-top-left-radius: 0; border-bottom-left-radius: 0; }"},
            {"action": self.app.window.actionAddMarker,       "icon": "themes/cosmic/images/tool-add-marker.svg",      "style": Qt.ToolButtonIconOnly, "stylesheet": "QToolButton { margin-right: 0; border-top-right-radius: 0; border-bottom-right-radius: 0; }"},
            {"action": self.app.window.actionPreviousMarker,  "icon": "themes/cosmic/images/tool-prev-marker.svg",     "style": Qt.ToolButtonIconOnly, "stylesheet": "QToolButton { margin: 0; border-radius: 0; }"},
            {"action": self.app.window.actionNextMarker,      "icon": "themes/cosmic/images/tool-next-marker.svg",     "style": Qt.ToolButtonIconOnly, "stylesheet": "QToolButton { margin-left: 0; border-top-left-radius: 0; border-bottom-left-radius: 0; }"},
            {"action": self.app.window.actionCenterOnPlayhead,"icon": "themes/cosmic/images/tool-center-playhead.svg", "style": Qt.ToolButtonIconOnly, "stylesheet": "QToolButton { margin-right: 8px; }"},
            {"widget": self.app.window.sliderZoomWidget},
            {"widget": spacer},
        ]
        self.set_toolbar_buttons(self.app.window.timelineToolbar, icon_size=12, settings=timeline_buttons)

        # ── Video toolbar ─────────────────────────────────────────────
        toolbar_buttons = [
            {"expand": True},
            {"action": self.app.window.actionJumpStart,   "icon": "themes/cosmic/images/tool-media-skip-back.svg",    "style": Qt.ToolButtonIconOnly},
            {"action": self.app.window.actionRewind,      "icon": "themes/cosmic/images/tool-media-rewind.svg",       "style": Qt.ToolButtonIconOnly},
            {"action": self.app.window.actionPlay,        "icon": "themes/cosmic/images/tool-media-play.svg",         "style": Qt.ToolButtonIconOnly},
            {"action": self.app.window.actionFastForward, "icon": "themes/cosmic/images/tool-media-forward.svg",      "style": Qt.ToolButtonIconOnly},
            {"action": self.app.window.actionJumpEnd,     "icon": "themes/cosmic/images/tool-media-skip-forward.svg", "style": Qt.ToolButtonIconOnly},
            {"expand": True},
        ]
        self.set_toolbar_buttons(self.app.window.videoToolbar, icon_size=32, settings=toolbar_buttons)

        # ── Timeline CSS overrides ─────────────────────────────────────
        self.app.window.timeline.apply_theme("""
            /* ── Timeline body ──────────────────────────────── */
            body {
                background: #0d0d0d;
            }

            /* ── Scrollbars ─────────────────────────────────── */
            ::-webkit-scrollbar {
                width: 6px;
                height: 6px;
            }
            ::-webkit-scrollbar-thumb {
                background: rgba(255, 255, 255, 0.14);
                border-radius: 3px;
            }
            ::-webkit-scrollbar-thumb:hover {
                background: rgba(255, 255, 255, 0.26);
            }
            ::-webkit-scrollbar-track {
                background: #0d0d0d;
                box-shadow: none;
            }
            ::-webkit-scrollbar-corner { background: #0d0d0d; }

            /* ── Ruler ──────────────────────────────────────── */
            #ruler_label {
                background: #0d0d0d;
            }
            #scrolling_ruler {
                background: #0d0d0d;
                border-bottom: 1px solid rgba(255, 255, 255, 0.06);
            }
            #ruler_time {
                color: #8a8a8a;
            }
            .ruler_time {
                color: #8a8a8a;
            }
            .tick_mark {
                background-color: rgba(255, 255, 255, 0.2);
            }

            /* ── Track control panel ─────────────────────────── */
            .track_name {
                background: #0d0d0d;
                border: 1px solid rgba(255, 255, 255, 0.06);
                border-left: 3px solid #4d9cf6;
                border-radius: 0;
                box-shadow: none;
                margin-left: 0;
                height: 48px;
                color: #d4d4d4;
            }
            .track_top {
                padding-top: 4px;
                padding-left: 10px;
                background: none;
            }
            .track_label { text-shadow: none; }

            /* ── Track lanes ─────────────────────────────────── */
            .track {
                background: #0d0d0d;
                border: none;
                border-top: 1px solid rgba(255, 255, 255, 0.04);
                border-bottom: 1px solid rgba(255, 255, 255, 0.04);
                border-radius: 0;
                height: 48px;
                box-shadow: none;
                transition: background 0.15s ease;
            }
            .track:hover {
                background: #1a1a1a;
            }
            .track_disabled {
                background: #0e0e0e !important;
            }
            .track-resize-handle {
                background-color: #0d0d0d;
                border: 1px solid rgba(255, 255, 255, 0.04);
                border-left: none;
                border-radius: 0;
                transition: background-color 0.15s ease;
            }
            .track-resize-handle:hover { background-color: #252525; }

            /* ── Clips ───────────────────────────────────────── */
            .clip {
                background: #1e3050;
                border: 1px solid #4d9cf6;
                border-radius: 6px;
                box-sizing: border-box;
                height: 48px;
                min-height: 48px;
                box-shadow: none;
                display: flex;
                opacity: 0.95;
                transition: filter 0.12s ease, opacity 0.12s ease, border-color 0.12s ease;
                cursor: grab;
            }
            .clip:hover {
                filter: brightness(1.08);
                opacity: 1;
                border-color: #6db0fa;
            }
            .clip.ui-draggable-dragging {
                cursor: grabbing;
                opacity: 0.85;
                box-shadow: 0 4px 16px rgba(0,0,0,0.5);
                transform-origin: center center;
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
            .clip_label {
                color: #d4d4d4;
                text-shadow: none;
                font-size: 9pt;
            }
            .thumb-container,
            .audio-container {
                position: absolute;
                top: 0; left: 0; right: 0; bottom: 0;
                overflow: hidden;
                margin-top: 0;
                border-radius: 5px;
            }
            .thumb {
                border-radius: 5px;
                margin: 0;
                height: 100%;
                object-fit: cover;
                z-index: 1;
            }
            .audio { border-radius: 5px; }

            /* Selection states */
            .ui-selecting {
                border: 1px solid #f59e0b !important;
            }
            .ui-selected {
                border: 1px solid #4d9cf6 !important;
                filter: brightness(1.15);
            }

            /* Edge stop indicators */
            .left_edge_stop  { border-left: 2px solid #4d9cf6; }
            .right_edge_stop { border-right: 2px solid #4d9cf6; }

            /* ── Transitions ─────────────────────────────────── */
            .transition {
                background: linear-gradient(to bottom, #0e4e78, #1a6494);
                border: 1px solid rgba(77, 156, 246, 0.5);
                border-radius: 6px;
                height: 48px;
                min-height: 48px;
                opacity: 0.8;
                box-shadow: none;
                transition: opacity 0.12s ease;
            }
            .transition:hover { opacity: 0.95; }
            .transition_top { background: none; }
            .transition.ui-selected { opacity: 1; }
            .highlight_transition { border-color: #4d9cf6 !important; }

            /* ── Playhead ────────────────────────────────────── */
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
                background-color: #f59e0b;
                margin: -1px;
                pointer-events: none;
            }

            /* ── Snap line ───────────────────────────────────── */
            .snapping-line {
                background-color: rgba(77, 156, 246, 0.7);
            }

            /* ── Selection box ───────────────────────────────── */
            .ui-selectable-helper {
                border: 1px solid #4d9cf6;
                background-color: rgba(77, 156, 246, 0.12);
            }

            /* ── Keyframe icons ──────────────────────────────── */
            .point_bezier   { background-image: url(../themes/cosmic/images/keyframe-bezier.svg); }
            .point_linear   { background-image: url(../themes/cosmic/images/keyframe-linear.svg); }
            .point_constant { background-image: url(../themes/cosmic/images/keyframe-constant.svg); }

            /* ── Track control icons ─────────────────────────── */
            .track-keyframe-panel-disabled { background-image: url(../themes/cosmic/images/track-keyframe-panel-show-disabled.svg); }
            .track-keyframe-panel-enabled  { background-image: url(../themes/cosmic/images/track-keyframe-panel-show-enabled.svg); }
            .track-add-above-disabled      { background-image: url(../themes/cosmic/images/track-add-above-disabled.svg); }
            .track-add-above-enabled       { background-image: url(../themes/cosmic/images/track-add-above-enabled.svg); }
            .track-add-below-disabled      { background-image: url(../themes/cosmic/images/track-add-below-disabled.svg); }
            .track-add-below-enabled       { background-image: url(../themes/cosmic/images/track-add-below-enabled.svg); }
            .track-delete-disabled         { background-image: url(../themes/cosmic/images/track-delete-disabled.svg); }
            .track-delete-enabled          { background-image: url(../themes/cosmic/images/track-delete-enabled.svg); }
            .track-locked-disabled         { background-image: url(../themes/cosmic/images/track-locked-disabled.svg); }
            .track-locked-enabled          { background-image: url(../themes/cosmic/images/track-locked-enabled.svg); }
            .track-unlocked-disabled       { background-image: url(../themes/cosmic/images/track-unlocked-disabled.svg); }
            .track-unlocked-enabled        { background-image: url(../themes/cosmic/images/track-unlocked-enabled.svg); }
            .keyframe-panel-add            { background-image: url(../themes/cosmic/images/keyframe-panel-add.svg); }
            .marker_icon                   { background-image: url(../themes/cosmic/images/marker.svg); }
        """)

        # Emit signal
        self.app.window.ThemeChangedSignal.emit(self)

    def togglePlayIcon(self, isPlay):
        """Toggle the play icon between play and pause."""
        button = self.app.window.videoToolbar.widgetForAction(self.app.window.actionPlay)
        if button:
            icon_name = "tool-media-pause.svg" if isPlay else "tool-media-play.svg"
            button.setIcon(QIcon(os.path.join(PATH, "themes/cosmic/images", icon_name)))
