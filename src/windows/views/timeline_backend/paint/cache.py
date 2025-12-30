"""
 @file
 @brief Painter for cached playback segments.
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
from PyQt5.QtGui import QColor, QPainter

from .base import BasePainter


class PlaybackCachePainter(BasePainter):
    """Render cached playback ranges as a thin bar under the ruler."""

    def update_theme(self):
        color = getattr(self.w.theme, "playback_cache_color", QColor("#4B92AD"))
        if not isinstance(color, QColor) or not color.isValid():
            color = QColor("#4B92AD")
        self.cache_color = color

        height = getattr(self.w.theme, "playback_cache_height", 5.0)
        try:
            height = float(height)
        except (TypeError, ValueError):
            height = 5.0
        if height <= 0.0:
            height = 5.0
        self.cache_height = height

    def paint(self, painter: QPainter):
        ranges = getattr(self.w, "_playback_cache_ranges", None)
        if not ranges:
            return

        pps = float(getattr(self.w, "pixels_per_second", 0.0) or 0.0)
        if pps <= 0.0:
            return

        area = QRectF(
            self.w.track_name_width,
            self.w.ruler_height,
            self.w.width() - self.w.track_name_width - self.w.scroll_bar_thickness,
            self.w.height() - self.w.ruler_height - self.w.scroll_bar_thickness,
        )
        if area.width() <= 0.0 or area.height() <= 0.0:
            return

        bar_height = min(self.cache_height, area.height())
        if bar_height <= 0.0:
            return

        offset_px = float(getattr(self.w, "h_scroll_offset", 0.0) or 0.0)

        painter.save()
        painter.setClipRect(area)
        painter.setPen(Qt.NoPen)
        painter.setBrush(self.cache_color)

        top = area.top()
        for start_seconds, end_seconds in ranges:
            if end_seconds <= start_seconds:
                continue
            start_px = self.w.track_name_width + start_seconds * pps - offset_px
            end_px = self.w.track_name_width + end_seconds * pps - offset_px
            width = end_px - start_px
            if width <= 0.5:
                continue
            rect = QRectF(start_px, top, width, bar_height)
            rect = rect.intersected(area)
            if rect.isNull():
                continue
            painter.fillRect(rect, self.cache_color)

        painter.restore()
