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
import re

from qt_api import Qt, QSize, QEvent, QObject
from qt_api import QColor, QIcon, QPixmap, QPainter
from qt_api import QSvgRenderer
from qt_api import (
    QDialogButtonBox, QLabel, QMessageBox, QPushButton, QTabWidget, QWidget,
    QSizePolicy,
)

from classes import ui_util
from classes.info import PATH


class MessageBoxStyleFilter(QObject):
    """Add semantic styling hooks to QMessageBox instances as they appear."""

    def eventFilter(self, watched, event):
        if isinstance(watched, QMessageBox) and event.type() == QEvent.Show:
            self.style_message_box(watched)
        return False

    @staticmethod
    def style_message_box(message_box):
        """Modernize a message box while retaining Qt's platform behavior."""
        message_box.setProperty("openshotMessageBox", True)
        message_box.setMinimumWidth(400)

        layout = message_box.layout()
        if layout:
            layout.setContentsMargins(20, 16, 20, 16)
            layout.setHorizontalSpacing(12)
            layout.setVerticalSpacing(12)

        button_box = message_box.findChild(
            QDialogButtonBox, "qt_msgbox_buttonbox")
        if button_box and button_box.layout():
            button_box.layout().setSpacing(10)
            button_box.layout().setAlignment(Qt.AlignRight)

        # The glossy stock question-mark icon is visually dated and adds a
        # large empty column. Other message types retain their useful icons.
        if message_box.icon() == QMessageBox.Question:
            icon_label = message_box.findChild(
                QWidget, "qt_msgboxex_icon_label")
            if icon_label:
                icon_label.hide()
                icon_label.setMaximumSize(0, 0)

            # QMessageBox reserves a spacer column between its icon and text.
            # Collapse it along with the hidden question icon, then let the
            # message occupy the full content width.
            if layout:
                spacer_item = layout.itemAtPosition(0, 1)
                if spacer_item and spacer_item.spacerItem():
                    spacer_item.spacerItem().changeSize(
                        0, 0, QSizePolicy.Fixed, QSizePolicy.Fixed)
                layout.setColumnStretch(0, 0)
                layout.setColumnStretch(1, 0)
                layout.setColumnStretch(2, 1)
                layout.invalidate()

        message_label = message_box.findChild(
            QLabel, "qt_msgbox_label")
        if message_label:
            message_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        for button in message_box.buttons():
            if not isinstance(button, QPushButton):
                continue

            # Standard dialog-button icons vary dramatically by platform and
            # icon theme. Text-only actions are calmer and more consistent.
            button.setIcon(QIcon())
            button.setText(
                button.text().replace("&&", "\0").replace("&", "")
                .replace("\0", "&")
            )
            size_policy = button.sizePolicy()
            size_policy.setHorizontalPolicy(QSizePolicy.Maximum)
            button.setSizePolicy(size_policy)

            standard_button = message_box.standardButton(button)
            role = message_box.buttonRole(button)
            if standard_button == QMessageBox.Cancel:
                style_role = "cancel"
            elif role in (
                    QDialogButtonBox.AcceptRole,
                    QDialogButtonBox.YesRole,
                    QDialogButtonBox.ApplyRole):
                style_role = "primary"
            elif role == QDialogButtonBox.DestructiveRole:
                style_role = "destructive"
            else:
                style_role = "secondary"
            button.setProperty("dialogRole", style_role)

            # Dynamic properties added after construction need repolishing
            # before their attribute selectors take effect.
            button.style().unpolish(button)
            button.style().polish(button)


class BaseTheme:
    def __init__(self, app):
        self.style_sheet = """
.property_value {
    foreground-color: #b3b3b3;
    background-color: #343434;
}
QTreeView::item, QListView::item {
    padding-top: 2px;
}
        """
        self.app = app

    def _debug_focus_styles(self):
        if not os.environ.get("OPENSHOT_DEBUG_FOCUS"):
            return ""
        return """
QToolButton:focus, QToolBar QToolButton:focus, QToolBar#toolBar QToolButton:focus,
QToolBar#timelineToolbar QToolButton:focus, QPushButton:focus,
QLineEdit:focus, QTextEdit:focus, QComboBox:focus,
QSpinBox:focus, QDoubleSpinBox:focus, QSlider:focus,
QMenuBar::item:selected,
QTabBar:focus, QTabBar::tab:focus, QMenu::item:selected,
QCheckBox:focus, QRadioButton:focus,
QToolBox::tab:focus {
    border: 2px solid #ff00ff;
}
QToolButton:focus, QToolBar QToolButton:focus {
    border-style: solid;
    border-width: 2px;
}
QListView::item:focus, QListWidget::item:focus,
QTreeView::item:focus, QTableView::item:focus {
    border: 2px solid #ff00ff;
}
QListView::item:selected:focus, QListWidget::item:selected:focus,
QTreeView::item:selected:focus, QTableView::item:selected:focus {
    border: 2px solid #ff00ff;
    background: palette(highlight);
    color: palette(highlighted-text);
}
QLineEdit#filesFilter:focus, QLineEdit#effectsFilter:focus,
QLineEdit#transitionsFilter:focus, QLineEdit#emojisFilter:focus,
QLineEdit#txtPropertyFilter:focus, QLineEdit#txtProfileFilter:focus,
QLineEdit#txtDeveloperFilter:focus, QLineEdit#txtTranslatorFilter:focus,
QLineEdit#txtSupporterFilter:focus, QLineEdit#txtChangeLogFilter_openshot_qt:focus,
QLineEdit#txtChangeLogFilter_libopenshot:focus, QLineEdit#txtChangeLogFilter_libopenshot_audio:focus {
    border: 2px solid #ff00ff;
}
        """

    def _debug_focus_toolbutton_rule(self):
        if not os.environ.get("OPENSHOT_DEBUG_FOCUS"):
            return ""
        return " QToolButton:focus { border: 2px solid #ff00ff; }"

    def compose_stylesheet(self):
        return (
            self._message_box_styles()
            + self.style_sheet
            + self._debug_focus_styles()
        )

    @staticmethod
    def _message_box_styles():
        """Shared message-box geometry; themes supply their own colors."""
        return """
QMessageBox QLabel#qt_msgbox_label {
    font-size: 14px;
    padding: 0;
}
QMessageBox QDialogButtonBox#qt_msgbox_buttonbox QPushButton {
    min-width: 72px;
    padding: 7px 14px;
    border-radius: 6px;
}
QMessageBox QDialogButtonBox#qt_msgbox_buttonbox QPushButton[dialogRole="cancel"] {
    min-width: 48px;
    padding: 7px 10px;
    border: none;
    background-color: transparent;
}
        """

    def create_svg_icon(self, svg_path, size):
        """Create Dynamic High DPI icons"""
        renderer = QSvgRenderer(svg_path)
        image = QPixmap(size * self.app.devicePixelRatio())
        image.fill(Qt.transparent)
        painter = QPainter(image)
        renderer.render(painter)
        painter.end()
        image.setDevicePixelRatio(self.app.devicePixelRatio())
        return QIcon(image)

    def get_color(self, class_name, property_name):
        """Return a QColor from a stylesheet class and property."""
        pattern = rf"{re.escape(class_name)}\s*{{([^}}]*)}}"
        match = re.search(pattern, self.style_sheet, re.IGNORECASE | re.MULTILINE)
        if not match:
            return None

        block = match.group(1)
        m = re.search(rf"(?:^|;)\s*{re.escape(property_name)}\s*:\s*([^;]+)", block)
        if not m:
            return None

        value = m.group(1).strip()

        # Attempt to extract a color from the property value using
        # a few different patterns. This allows parsing of complex
        # properties such as "1px solid #FF0000" or "0 0 4px rgba(...)".
        m_color = re.search(r"#([0-9a-fA-F]{3,8})", value)
        if m_color:
            return QColor("#" + m_color.group(1))

        m_color = re.search(r"rgba?\([^\)]+\)", value)
        if m_color:
            return QColor(m_color.group(0))

        parts = value.split()
        if parts and QColor(parts[-1]).isValid():
            return QColor(parts[-1])

        return None

    def get_int(self, class_name, property_name):
        """Return an int from a stylesheet class and property."""
        pattern = rf"{re.escape(class_name)}\s*{{([^}}]*)}}"
        match = re.search(pattern, self.style_sheet, re.IGNORECASE | re.MULTILINE)
        if not match:
            return None

        block = match.group(1)
        m = re.search(rf"(?:^|;)\s*{re.escape(property_name)}\s*:\s*([^;]+)", block)
        if not m:
            return None

        value = m.group(1).strip()
        m_int = re.search(r"(-?[0-9]+)", value)
        if m_int:
            try:
                return int(m_int.group(1))
            except ValueError:
                pass
        return None

    def set_dock_margins(self, content_margins=None, layout_margins=None, object_name=None):
        """ Set content margins on dock widgets with an optional objectName filter. """
        if content_margins is None:
            content_margins = [0, 0, 0, 0]
        if layout_margins is None:
            layout_margins = [9, 9, 9, 9]

        for dock in self.app.window.getDocks():
            for child in dock.children():
                if isinstance(child, QWidget):
                    # Check filter or use all children
                    if object_name is None or child.objectName() == object_name:
                        if child.objectName().startswith("dock") and child.objectName().endswith("Contents"):
                            # Set content margins on QDock* widget
                            child.setContentsMargins(*content_margins)
                            if child.layout() and layout_margins:
                                # Set content margins on the QDock Layout (which has additional margins)
                                child.layout().setContentsMargins(*layout_margins)

    def set_toolbar_buttons(self, toolbar, icon_size=24, settings=None):
        """Iterate through toolbar button settings, and apply them to each button.
        [{"text": "", "icon": ""},...]
        """
        from qt_api import QT_API, isdeleted

        # Clear toolbar without deleting actions on PySide6
        if QT_API == "pyside6":
            for action in list(toolbar.actions()):
                toolbar.removeAction(action)
        else:
            toolbar.clear()

        # Set icon size
        qsize_icon = QSize(icon_size, icon_size)
        toolbar.setIconSize(qsize_icon)

        for setting in settings:
            # Button settings
            button_action = setting.get("action", None)
            button_icon = setting.get("icon", None)
            button_style = setting.get("style", None)
            button_stylesheet = setting.get("stylesheet", None)
            button_visible = setting.get("visible", True)
            widget = setting.get("widget", None)
            expand = setting.get("expand", False)
            divide = setting.get("divide", False)

            # Update button_icon to abs path (if not found)
            # This is needed for AppImage, where the relative path is wrong
            if button_icon and not button_icon.startswith(":") and not os.path.exists(button_icon):
                new_abs_path = os.path.join(PATH, button_icon)
                if os.path.exists(new_abs_path):
                    button_icon = new_abs_path

            if expand:
                # Add spacer and 'New Version Available' toolbar button (default hidden)
                spacer = QWidget(toolbar)
                spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
                spacer.setFocusPolicy(Qt.NoFocus)
                toolbar.addWidget(spacer)
                continue

            if divide:
                # Create a divider
                toolbar.addSeparator()
                continue

            if widget:
                widget.setVisible(True)
                if button_stylesheet:
                    widget.setStyleSheet(button_stylesheet)
                toolbar.addWidget(widget)
                continue

            # Create button from action
            if button_action:
                if QT_API == "pyside6" and isdeleted(button_action):
                    continue
                toolbar.addAction(button_action)
                button_action.setVisible(button_visible)
                button = toolbar.widgetForAction(button_action)
                button.setObjectName(f"tool-{button_action.objectName()}")
                if button_icon:
                    qicon_instance = self.create_svg_icon(button_icon, qsize_icon)
                    button_action.setIcon(qicon_instance)
                if button_style:
                    button.setToolButtonStyle(button_style)
                if button_stylesheet:
                    button.setStyleSheet(
                        button_stylesheet + self._debug_focus_toolbutton_rule()
                    )

    def apply_theme(self):
        # Apply the stylesheet to the entire application
        from classes import info
        from classes.logger import log
        from qt_api import QFont, QFontDatabase

        if not self.app.theme_manager:
            log.warning("ThemeManager not initialized yet. Skip applying a theme.")

        if self.app.theme_manager.original_style:
            self.app.setStyle(self.app.theme_manager.original_style)
        if self.app.theme_manager.original_palette:
            self.app.setPalette(self.app.theme_manager.original_palette)
        self.app.setStyleSheet(self.compose_stylesheet())
        self.install_message_box_styling()

        # Hide main window status bar
        if hasattr(self.app, "window") and hasattr(self.app.window, "statusBar"):
            self.app.window.statusBar.hide()

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
        self.set_dock_margins()

        # Move tabs to bottom (all dock areas, since restoreState() does not persist tab positions)
        for area in (Qt.TopDockWidgetArea, Qt.BottomDockWidgetArea,
                     Qt.LeftDockWidgetArea, Qt.RightDockWidgetArea):
            self.app.window.setTabPosition(area, QTabWidget.South)

        # Main toolbar buttons
        toolbar_buttons = [
            {"action": self.app.window.actionNew, "style": Qt.ToolButtonIconOnly},
            {"action": self.app.window.actionOpen, "style": Qt.ToolButtonIconOnly},
            {"action": self.app.window.actionSave, "style": Qt.ToolButtonIconOnly},
            {"divide": True},
            {"action": self.app.window.actionUndo, "style": Qt.ToolButtonIconOnly},
            {"action": self.app.window.actionRedo, "style": Qt.ToolButtonIconOnly},
            {"divide": True},
            {"action": self.app.window.actionImportFiles, "style": Qt.ToolButtonIconOnly},
            {"action": self.app.window.actionProfile, "style": Qt.ToolButtonIconOnly},
            {"action": self.app.window.actionFullscreen, "style": Qt.ToolButtonIconOnly},
            {"divide": True},
            {"action": self.app.window.actionExportVideo, "style": Qt.ToolButtonIconOnly},
        ]
        self.set_toolbar_buttons(self.app.window.toolBar, icon_size=24, settings=toolbar_buttons)

        # Timeline toolbar buttons
        timeline_buttons = [
            {"action": self.app.window.actionAddTrack, "style": Qt.ToolButtonIconOnly},
            {"divide": True},
            {"action": self.app.window.actionSnappingTool, "style": Qt.ToolButtonIconOnly, "icon": ":/icons/Humanity/actions/custom/snap.svg"},
            {"action": self.app.window.actionTimingTool, "style": Qt.ToolButtonIconOnly, "icon": ":/icons/Humanity/actions/custom/timing.svg"},
            {"action": self.app.window.actionRazorTool, "style": Qt.ToolButtonIconOnly, "icon": ":/icons/Humanity/actions/16/edit-cut.svg"},
            {"divide": True},
            {"action": self.app.window.actionAddMarker, "style": Qt.ToolButtonIconOnly, "icon": ":/icons/actions/add_marker.svg"},
            {"action": self.app.window.actionPreviousMarker, "style": Qt.ToolButtonIconOnly},
            {"action": self.app.window.actionNextMarker, "style": Qt.ToolButtonIconOnly},
            {"action": self.app.window.actionCenterOnPlayhead, "style": Qt.ToolButtonIconOnly, "icon": ":/icons/Humanity/actions/custom/center-on-playhead.svg"},
            {"divide": True},
            {"widget": self.app.window.sliderZoomWidget}
        ]
        self.set_toolbar_buttons(self.app.window.timelineToolbar, icon_size=24, settings=timeline_buttons)

        # Video toolbar
        toolbar_buttons = [
            {"expand": True},
            {"action": self.app.window.actionJumpStart, "style": Qt.ToolButtonIconOnly},
            {"action": self.app.window.actionRewind, "style": Qt.ToolButtonIconOnly},
            {"action": self.app.window.actionPlay, "style": Qt.ToolButtonIconOnly},
            {"action": self.app.window.actionFastForward, "style": Qt.ToolButtonIconOnly},
            {"action": self.app.window.actionJumpEnd, "style": Qt.ToolButtonIconOnly},
            {"expand": True}
        ]
        self.set_toolbar_buttons(self.app.window.videoToolbar, icon_size=24, settings=toolbar_buttons)

        # Init icons from theme name
        ui_util.init_ui(self.app.window)

        # Emit signal
        self.app.window.ThemeChangedSignal.emit(self)

    def install_message_box_styling(self):
        """Install one application-wide message-box styling filter."""
        previous_filter = getattr(
            self.app, "_openshot_message_box_style_filter", None)
        if previous_filter:
            self.app.removeEventFilter(previous_filter)

        message_box_filter = MessageBoxStyleFilter(self.app)
        self.app.installEventFilter(message_box_filter)
        self.app._openshot_message_box_style_filter = message_box_filter

    def togglePlayIcon(self, isPlay):
        """ Toggle the play icon from play to pause and back """
        if not isPlay:
            ui_util.setup_icon(self.app.window, self.app.window.actionPlay, "actionPlay")
        else:
            ui_util.setup_icon(self.app.window, self.app.window.actionPlay, "actionPlay", "media-playback-pause")
