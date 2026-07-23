"""
 @file
 @brief This file contains a custom title bar used by dock widgets
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

from qt_api import Qt, QEvent, QWidget, QDockWidget, QHBoxLayout, QPushButton, QLabel

from classes.app import get_app


class HiddenTitleBar(QWidget):
    def _display_text(self, text):
        """Uppercase panel titles for the Modern Dark theme only."""
        try:
            tm = get_app().theme_manager
            theme = tm.get_current_theme() if tm else None
            from themes.manager import ThemeName
            if theme and theme.name == ThemeName.MODERN_DARK.value:
                return text.upper()
        except Exception:
            pass
        return text

    def __init__(self, dock_widget, title_text="", show_buttons=True):
        super().__init__()
        self.dock_widget = dock_widget
        self.show_buttons = show_buttons
        self._tr = None
        self.dragging = False  # Flag for dragging
        self.start_pos = None
        self.setFocusPolicy(Qt.NoFocus)

        # Set up a horizontal layout
        layout = QHBoxLayout(self)

        # Add a QLabel for the title (optional, based on title_text)
        self.title_label = QLabel(self._display_text(title_text))
        self.title_label.setFocusPolicy(Qt.NoFocus)
        self.title_label.installEventFilter(self)
        if title_text:
            self.title_label.setObjectName("dock-title-label")
        else:
            self.title_label.setObjectName("dock-title-handle")

        # Add the QLabel to the layout
        layout.addWidget(self.title_label)

        # Keep title in sync with dock widget
        self.dock_widget.windowTitleChanged.connect(self.update_title)

        # Add a spacer to push buttons to the right
        layout.addStretch()

        self.close_button = None
        self.undock_button = None

        if self.show_buttons:
            # Add close and undock buttons
            self.close_button = QPushButton()
            self.undock_button = QPushButton()
            self.close_button.setFocusPolicy(Qt.NoFocus)
            self.undock_button.setFocusPolicy(Qt.NoFocus)

            # Set object names for styling via stylesheets
            self.close_button.setObjectName("dock-close-button")
            self.undock_button.setObjectName("dock-float-button")

            # Connect the buttons to the appropriate actions
            self.close_button.clicked.connect(self.dock_widget.close)
            self.undock_button.clicked.connect(self.toggle_dock_state)

            # Add buttons to the layout
            layout.addWidget(self.undock_button)
            layout.addWidget(self.close_button)

        # Set margins and height for the title bar
        layout.setContentsMargins(0, 0, 0, 0)
        if title_text:
            # Taller for title with bottom margin
            is_modern = False
            try:
                tm = get_app().theme_manager
                theme = tm.get_current_theme() if tm else None
                from themes.manager import ThemeName
                is_modern = bool(theme and theme.name == ThemeName.MODERN_DARK.value)
            except Exception:
                pass
            self.setFixedHeight(32 if is_modern else 40)
        else:
            # Shorter for just drag handle + buttons (tabbed docks)
            self.setFixedHeight(20)
        self._update_accessible_labels()

    def update_title(self, text):
        """Update label text when dock title changes."""
        self.title_label.setText(self._display_text(text))

    def _update_accessible_labels(self):
        if self._tr is None:
            self._tr = get_app()._tr
        _ = self._tr
        if not self.show_buttons:
            return
        close_label = _("Close")
        self.close_button.setAccessibleName(close_label)

        if self.dock_widget.isFloating():
            float_label = _("Dock")
        else:
            float_label = _("Float")
        self.undock_button.setAccessibleName(float_label)

    def _close_on_middle_click(self, event):
        if event.button() != Qt.MiddleButton:
            return False
        if not (self.dock_widget.features() & QDockWidget.DockWidgetClosable):
            return False
        self.dock_widget.close()
        event.accept()
        return True

    def eventFilter(self, obj, event):
        if obj is self.title_label and event.type() == QEvent.MouseButtonRelease:
            if self._close_on_middle_click(event):
                return True
        return super().eventFilter(obj, event)

    def mouseReleaseEvent(self, event):
        if self._close_on_middle_click(event):
            return
        super().mouseReleaseEvent(event)

    def toggle_dock_state(self):
        """Toggle between docked and floating states."""
        if self.dock_widget.isFloating():
            # Restore the default title bar when docking
            self.dock_widget.setFloating(False)
        else:
            # Float the widget and apply custom title bar
            self.dock_widget.setFloating(True)
        self._update_accessible_labels()
