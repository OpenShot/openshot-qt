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

from PyQt5.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton


class HiddenTitleBar(QWidget):
    def __init__(self, dock_widget, title_text="", show_buttons=False):
        super().__init__()
        self.dock_widget = dock_widget
        self.dragging = False  # Flag for dragging
        self.start_pos = None

        # Set up a horizontal layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Add a QLabel for the title (optional, based on title_text)
        self.title_label = QLabel(title_text)
        if title_text:
            self.title_label.setObjectName("dock-title-label")
        else:
            self.title_label.setObjectName("dock-title-handle")
        layout.addWidget(self.title_label)

        if show_buttons:
            layout.addStretch()

            # Float / undock button
            float_btn = QPushButton("⧉")
            float_btn.setObjectName("dock-float-button")
            float_btn.setFixedSize(18, 18)
            float_btn.setFlat(True)
            float_btn.setToolTip("Float")
            float_btn.clicked.connect(lambda: dock_widget.setFloating(not dock_widget.isFloating()))
            layout.addWidget(float_btn)

            # Close button
            close_btn = QPushButton("✕")
            close_btn.setObjectName("dock-close-button")
            close_btn.setFixedSize(18, 18)
            close_btn.setFlat(True)
            close_btn.setToolTip("Close")
            close_btn.clicked.connect(dock_widget.hide)
            layout.addWidget(close_btn)

        # Keep title in sync with dock widget
        self.dock_widget.windowTitleChanged.connect(self.update_title)

        # Collapse to zero height when no title text — avoids blank whitespace above content
        self.setFixedHeight(0 if (not title_text and not show_buttons) else 20)

    def update_title(self, text):
        """Update label text when dock title changes."""
        self.title_label.setText(text)

