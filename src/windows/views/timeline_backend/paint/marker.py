"""
 @file
 @brief Painter for clip marker overlays.
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

from PyQt5.QtCore import QRectF
from PyQt5.QtGui import QPainter

from .base import BasePainter


class MarkerPainter(BasePainter):
    def update_theme(self):
        pix = getattr(self.w.theme, "marker_icon", None)
        width = getattr(self.w.theme, "marker_icon_width", 0) or 0
        height = getattr(self.w.theme, "marker_icon_height", 0) or 0
        self.icon_pix = None
        if pix and not pix.isNull():
            self.icon_pix = self.scaled_pixmap(pix, width, height)
        self.icon_width, self.icon_height = self.logical_size(self.icon_pix)

    def paint(self, painter: QPainter):
        self.w.geometry.ensure()
        ruler_area = QRectF(
            self.w.track_name_width,
            0.0,
            self.w.width() - self.w.track_name_width - self.w.scroll_bar_thickness,
            self.w.ruler_height,
        )
        if not self.icon_pix or self.icon_pix.isNull():
            return

        markers = list(self.w.geometry.iter_markers())
        if not markers:
            return

        painter.save()
        painter.setClipRect(ruler_area)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        for mr in markers:
            if not isinstance(mr, dict):
                continue
            icon_rect = mr.get("icon_rect")
            if not icon_rect or icon_rect.isNull():
                continue
            painter.drawPixmap(icon_rect.topLeft(), self.icon_pix)
        painter.restore()
