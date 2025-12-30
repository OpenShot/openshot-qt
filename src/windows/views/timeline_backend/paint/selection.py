"""
 @file
 @brief Painter for drag-selection rectangles.
 @author Jonathan Thomas <jonathan@openshot.org>

 @section LICENSE

 Copyright (c) 2008-2025 OpenShot Studios, LLC
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

from PyQt5.QtCore import QRectF, Qt
from PyQt5.QtGui import QPainter, QPen

from .base import BasePainter


class SelectionPainter(BasePainter):
    def update_theme(self):
        bw = self.w.theme.selection_border_width
        col = (
            self.w.theme.selection_border
            if self.w.theme.selection_border.isValid()
            else self.w.theme.selection
        )
        self.pen = QPen(col, bw, Qt.SolidLine)
        self.pen.setCosmetic(True)

    def paint(self, painter: QPainter):
        if not self.w.selection_rect.isNull():
            area = QRectF(
                0.0,
                self.w.ruler_height,
                self.w.width() - self.w.scroll_bar_thickness,
                self.w.height() - self.w.ruler_height - self.w.scroll_bar_thickness,
            )
            painter.save()
            vis = self.w.selection_rect.intersected(area)
            if not vis.isNull():
                if self.w.theme.selection.isValid():
                    painter.fillRect(vis, self.w.theme.selection)
                if self.pen.color().isValid() and self.pen.widthF() > 0:
                    painter.setPen(self.pen)
                    painter.drawRect(vis)
            painter.restore()
