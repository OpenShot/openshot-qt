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

from PyQt5.QtWidgets import QWidget, QHBoxLayout, QPushButton, QLabel


class HiddenTitleBar(QWidget):
    def __init__(self, dock_widget, title_text=""):
        super().__init__()
        self.dock_widget = dock_widget
        self.dragging = False  # Flag for dragging
        self.start_pos = None

        # Set up a horizontal layout
        layout = QHBoxLayout(self)

        # Add a QLabel for the title (optional, based on title_text)
        self.title_label = QLabel(title_text)
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

        # Add close and undock buttons
        close_button = QPushButton()
        undock_button = QPushButton()

        # Set object names for styling via stylesheets
        close_button.setObjectName("dock-close-button")
        undock_button.setObjectName("dock-float-button")

        # Connect the buttons to the appropriate actions
        close_button.clicked.connect(self.dock_widget.close)
        undock_button.clicked.connect(self.toggle_dock_state)

        # Add buttons to the layout
        layout.addWidget(undock_button)
        layout.addWidget(close_button)

        # Set margins and reduce height for the title bar
        layout.setContentsMargins(0, 0, 0, 0)
        self.setFixedHeight(20)  # Reduced height

    def update_title(self, text):
        """Update label text when dock title changes."""
        self.title_label.setText(text)

    def toggle_dock_state(self):
        """Toggle between docked and floating states."""
        if self.dock_widget.isFloating():
            # Restore the default title bar when docking
            self.dock_widget.setFloating(False)
        else:
            # Float the widget and apply custom title bar
            self.dock_widget.setFloating(True)
