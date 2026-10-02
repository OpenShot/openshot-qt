"""
 @file
 @brief Painter for the playhead indicator.
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

from qt_api import QPointF, QRectF, Qt
from qt_api import QBrush, QColor, QPainter, QPen
import math

from .base import BasePainter


class PlayheadPainter(BasePainter):
    def update_theme(self):
        col = QColor(self.w.theme.playhead_color)
        self.line_brush = QBrush(col)
        self.line_width = float(self.w.theme.playhead_width)
        self.pen = QPen(self.line_brush, self.line_width)
        self.pen.setCosmetic(True)
        self.icon_pix = None
        if self.w.theme.playhead_icon:
            w = self.w.theme.playhead_icon_width or self.w.theme.playhead_icon.width()
            h = self.w.theme.playhead_icon_height or self.w.theme.playhead_icon.height()
            self.icon_pix = self.w.theme.playhead_icon.scaled(
                w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
        self.icon_offset_x = self.w.theme.playhead_icon_offset_x
        self.icon_offset_y = self.w.theme.playhead_icon_offset_y

    def paint(self, painter: QPainter):
        offset_px = getattr(self.w, "h_scroll_offset", 0.0)
        frame_seconds = 0.0
        if self.w.fps_float:
            frame_seconds = max(
                0.0, (max(1, self.w.current_frame) - 1) / self.w.fps_float
            )
        x = (
            self.w.track_name_width
            + frame_seconds * self.w.pixels_per_second
            - offset_px
        )
        painter.setRenderHint(QPainter.Antialiasing, False)
        ix = int(round(x))

        if self.icon_pix:
            icon_top = math.floor(self.icon_offset_y)
            icon_w = float(self.icon_pix.width())
            icon_h = float(self.icon_pix.height())
            icon_bottom = icon_top + icon_h
        else:
            icon_top = self.icon_offset_y
            icon_bottom = self.w.ruler_height

        margin_top = float(getattr(self.w, "track_margin_top", 0.0) or 0.0)
        line_top = float(self.w.ruler_height + margin_top)
        top = float(icon_bottom if self.icon_pix else self.w.ruler_height)
        if line_top > top:
            top = line_top

        # The playhead belongs to the viewport, including empty space below
        # short tracks. Stop above the horizontal scrollbar in every layout.
        viewport_bottom = max(0.0, self.w.height() - self.w.scroll_bar_thickness)
        bottom = max(top, viewport_bottom)

        timeline_left = self.w.track_name_width
        timeline_width = (
            self.w.width() - self.w.track_name_width - self.w.scroll_bar_thickness
        )
        visible = QRectF(
            timeline_left,
            top,
            max(0.0, timeline_width),
            bottom - top,
        )
        line_rect = QRectF(ix - self.line_width / 2, top, self.line_width, bottom - top)
        intersected = line_rect.intersected(visible)
        if not intersected.isNull():
            painter.fillRect(intersected, self.line_brush)

        if self.icon_pix:
            icon_pos = QPointF(ix + self.icon_offset_x, icon_top)
            icon_w = float(self.icon_pix.width())
            icon_h = float(self.icon_pix.height())
            icon_rect = QRectF(icon_pos.x(), icon_pos.y(), icon_w, icon_h)
            icon_visible = icon_rect.intersected(
                QRectF(
                    timeline_left,
                    0.0,
                    max(0.0, timeline_width),
                    viewport_bottom,
                )
            )
            if not icon_visible.isNull():
                # The icon includes a shaft; clip it at viewport edges too.
                dx = icon_visible.x() - icon_rect.x()
                dy = icon_visible.y() - icon_rect.y()
                source_rect = QRectF(
                    max(0.0, dx),
                    max(0.0, dy),
                    icon_visible.width(),
                    icon_visible.height(),
                )
                painter.drawPixmap(icon_visible.topLeft(), self.icon_pix, source_rect)
