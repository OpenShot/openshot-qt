"""
 @file
 @brief This file creates a styled QMenu (which supports border radius and border color)
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

from PyQt5.QtWidgets import QMenu
from PyQt5.QtGui import QPainter, QPen, QColor
from PyQt5.QtCore import Qt, QRectF
from classes.app import get_app
import re


class StyledContextMenu(QMenu):
    def __init__(self, title=None, parent=None):
        super().__init__(title, parent)
        self.app = get_app()
        self.border = self.get_border()
        self.border_radius = self.get_border_radius()

    def get_border(self):
        """Parses border width and color from app.styleSheet()"""
        pattern = r'QMenu\s*{\s*[^}]*border:\s*([^;]+);'
        match = re.search(pattern, self.app.styleSheet(), re.IGNORECASE)
        if match:
            border_parts = match.group(1).split()
            # Typically, border is defined as width style color
            if len(border_parts) >= 3:
                width = float(border_parts[0].replace('px', ''))  # Remove 'px' and convert to float
                style = border_parts[1]
                color = QColor(border_parts[2])
                return {'width': width, 'style': style, 'color': color}
        return None

    def get_border_radius(self):
        """Parses border radius from app.styleSheet()"""
        pattern = r'QMenu\s*{\s*[^}]*border-radius:\s*([^;]+);'
        match = re.search(pattern, self.app.styleSheet(), re.IGNORECASE)
        if match:
            # Split the radius values by whitespace and remove 'px' unit
            radius_values = match.group(1).replace('px', '').split()
            if len(radius_values) == 1:
                radius = float(radius_values[0])
                return {'x': radius, 'y': radius}
            if len(radius_values) == 2:
                return {'x': float(radius_values[0]), 'y': float(radius_values[1])}
        return None

    def paintEvent(self, event):
        """Paint optional borders and corner radius on QMenu"""
        super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        if self.border:
            pen = QPen(self.border.get('color'), self.border.get('width'))
            painter.setPen(pen)

        if self.border_radius:
            rect = QRectF(0, 0, self.width(), self.height())
            painter.drawRoundedRect(rect, self.border_radius.get('x'), self.border_radius.get('y'), Qt.AbsoluteSize)

        painter.end()
