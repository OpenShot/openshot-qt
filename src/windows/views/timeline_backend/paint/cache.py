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

from qt_api import QRectF, Qt
from qt_api import QColor, QPainter

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

    def _ruler_bottom_color(self):
        """Return the ruler color that touches the playback cache lane."""
        theme = getattr(self.w, "theme", None)
        ruler_theme = getattr(theme, "ruler", None)
        bg = QColor(getattr(ruler_theme, "background", QColor()))
        bg2 = QColor(getattr(ruler_theme, "background2", QColor()))
        if not bg.isValid():
            track_theme = getattr(theme, "track", None)
            bg = QColor(getattr(track_theme, "background", QColor()))
            bg2 = QColor(getattr(track_theme, "background2", QColor()))
        if bg2.isValid():
            return bg2
        return bg

    def _time_panel_bottom_color(self):
        """Return the current-time panel color beside the cache lane."""
        theme = getattr(self.w, "theme", None)
        bg = QColor(getattr(theme, "ruler_name_background", QColor()))
        bg2 = QColor(getattr(theme, "ruler_name_background2", QColor()))
        if not bg.isValid():
            track_theme = getattr(theme, "track", None)
            bg = QColor(getattr(track_theme, "name_background", QColor()))
        if bg2.isValid():
            return bg2
        return bg

    def paint(self, painter: QPainter):
        ranges = getattr(self.w, "_playback_cache_ranges", None) or []

        ruler_height = float(getattr(self.w, "ruler_height", 0.0) or 0.0)
        timeline_height = (
            self.w.height()
            - ruler_height
            - self.w.scroll_bar_thickness
        )
        available_width = (
            self.w.width()
            - self.w.track_name_width
            - self.w.scroll_bar_thickness
        )
        if available_width <= 0.0 or timeline_height <= 0.0:
            return

        bar_height = min(self.cache_height, timeline_height)
        if bar_height <= 0.0:
            return
        lane_height = min(
            timeline_height,
            max(bar_height, float(getattr(self.w, "track_margin_top", 0.0) or 0.0)),
        )
        if lane_height <= 0.0:
            lane_height = bar_height
        lane_rect = QRectF(
            self.w.track_name_width,
            ruler_height,
            available_width,
            lane_height,
        )
        time_lane_rect = QRectF(0.0, ruler_height, self.w.track_name_width, lane_height)

        offset_px = float(getattr(self.w, "h_scroll_offset", 0.0) or 0.0)

        painter.save()
        # Adjacent ruler/cache fills must meet on device pixels. Antialiasing
        # exposes the light timeline background at fractional UI scales.
        painter.setRenderHint(QPainter.Antialiasing, False)
        painter.setPen(Qt.NoPen)
        time_bg = self._time_panel_bottom_color()
        if time_bg.isValid():
            painter.fillRect(time_lane_rect, time_bg)
        bg = self._ruler_bottom_color()
        if bg.isValid():
            painter.fillRect(lane_rect, bg)

        painter.setClipRect(lane_rect)
        pps = float(getattr(self.w, "pixels_per_second", 0.0) or 0.0)
        if pps <= 0.0:
            painter.restore()
            return
        top = lane_rect.top()
        for start_seconds, end_seconds in ranges:
            if end_seconds <= start_seconds:
                continue
            start_px = self.w.track_name_width + start_seconds * pps - offset_px
            end_px = self.w.track_name_width + end_seconds * pps - offset_px
            width = end_px - start_px
            if width <= 0.5:
                continue
            rect = QRectF(start_px, top, width, bar_height)
            rect = rect.intersected(lane_rect)
            if rect.isNull():
                continue
            painter.fillRect(rect, self.cache_color)

        painter.restore()
