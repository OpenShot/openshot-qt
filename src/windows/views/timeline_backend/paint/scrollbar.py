"""
 @file
 @brief Painter for the custom scrollbars.
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
from PyQt5.QtGui import QBrush, QColor, QPainter

from .base import BasePainter


class ScrollbarPainter(BasePainter):
    """Draw horizontal and vertical scrollbars."""

    def update_theme(self):
        handle = getattr(self.w.theme, "scrollbar_handle", QColor())
        track = getattr(self.w.theme, "scrollbar_track", QColor())
        if not handle.isValid():
            handle = QColor("#4b92ad")
        if not track.isValid():
            track = QColor("#000")
        self.handle_brush = QBrush(handle)
        self.track_brush = QBrush(track)

    def paint(self, painter: QPainter):
        # Horizontal scrollbar
        sb = self.w.scroll_bar_rect
        if not sb.isNull():
            track = QRectF(
                self.w.track_name_width,
                self.w.height() - self.w.scroll_bar_thickness,
                self.w.width() - self.w.track_name_width - self.w.scroll_bar_thickness,
                self.w.scroll_bar_thickness,
            )
            painter.fillRect(track, self.track_brush)
            painter.fillRect(sb, self.handle_brush)

        # Vertical scrollbar
        sbv = getattr(self.w, "v_scroll_bar_rect", QRectF())
        if not sbv.isNull():
            track = QRectF(
                self.w.width() - self.w.scroll_bar_thickness,
                self.w.ruler_height,
                self.w.scroll_bar_thickness,
                self.w.height() - self.w.ruler_height - self.w.scroll_bar_thickness,
            )
            painter.fillRect(track, self.track_brush)
            painter.fillRect(sbv, self.handle_brush)
