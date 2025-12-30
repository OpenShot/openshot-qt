"""
 @file
 @brief Painter for the timeline ruler and header.
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

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import (
    QBrush,
    QFont,
    QFontMetrics,
    QLinearGradient,
    QPainter,
    QPen,
)
import math

from classes.app import get_app
from classes.time_parts import secondsToTime

from .base import BasePainter


class RulerPainter(BasePainter):
    def update_theme(self):
        self.bg = self.w.theme.ruler.background
        self.bg2 = self.w.theme.ruler.background2
        self.name_bg = (
            self.w.theme.ruler_name_background
            if self.w.theme.ruler_name_background.isValid()
            else self.w.theme.track.name_background
        )
        self.name_bg2 = (
            self.w.theme.ruler_name_background2
            if self.w.theme.ruler_name_background2.isValid()
            else self.name_bg
        )
        self.tick_pen = QPen(self.w.theme.ruler.border_color)
        self.tick_pen.setCosmetic(True)
        self.text_pen = QPen(self.w.theme.ruler.font_color)
        self.tick_font = QFont()
        if self.w.theme.ruler.font_size:
            self.tick_font.setPointSize(self.w.theme.ruler.font_size)
        self.play_font = QFont()
        if self.w.theme.ruler_time_font_size:
            self.play_font.setPointSize(self.w.theme.ruler_time_font_size)
        self.label_top = self.w.theme.ruler_label_top
        self.pad_left = self.w.theme.ruler_time_pad_left
        self.pad_top = self.w.theme.ruler_time_pad_top
        self._last_playhead_label = ""

    def _current_playhead_label(self):
        proj = get_app().project
        fps_info = proj.get("fps")
        fps_float = float(fps_info.get("num", 24)) / float(fps_info.get("den", 1) or 1)
        frame_seconds = 0.0
        if fps_float:
            frame_seconds = max(
                0.0, (max(1, self.w.current_frame) - 1) / fps_float
            )
        tt = secondsToTime(
            frame_seconds,
            fps_info["num"],
            fps_info["den"],
        )
        return f"{tt['hour']}:{tt['min']}:{tt['sec']},{tt['frame']}"

    def _draw_time_panel(self, painter: QPainter, label: str = None):
        left_rect = QRectF(0, 0, self.w.track_name_width, self.w.ruler_height)
        if left_rect.width() <= 0 or left_rect.height() <= 0:
            return left_rect
        if self.name_bg2 != self.name_bg:
            grad = QLinearGradient(left_rect.topLeft(), left_rect.bottomLeft())
            grad.setColorAt(0, self.name_bg)
            grad.setColorAt(1, self.name_bg2)
            painter.fillRect(left_rect, QBrush(grad))
        else:
            painter.fillRect(left_rect, self.name_bg)

        if label is None:
            label = self._current_playhead_label()
        if label:
            painter.setPen(self.text_pen)
            painter.setFont(self.play_font)
            painter.drawText(
                left_rect.adjusted(self.pad_left, self.pad_top, -2, -2),
                Qt.AlignLeft | Qt.AlignTop,
                label,
            )
            painter.setPen(self.tick_pen)
        return left_rect

    def _prime_factors(self, n: int):
        factors = []
        d = 2
        while d * d <= n:
            while n % d == 0:
                factors.append(d)
                n //= d
            d += 1
        if n > 1:
            factors.append(n)
        return factors

    def _frames_per_tick(self, pps, fps):
        frames = 1
        factors = self._prime_factors(round(fps))
        while (frames / fps) * pps < 40:
            frames *= factors.pop(0) if factors else 2
        return frames

    def paint(self, painter: QPainter):
        proj = get_app().project
        duration = proj.get("duration")
        fps_info = proj.get("fps")
        fps_float = float(fps_info.get("num", 24)) / float(fps_info.get("den", 1) or 1)
        pps = self.w.pixels_per_second
        width = max(1, self.w.width() - self.w.track_name_width)

        rect = QRectF(self.w.track_name_width, 0, width, self.w.ruler_height)
        if self.bg2.isValid() and self.bg != self.bg2:
            grad = QLinearGradient(rect.topLeft(), rect.bottomLeft())
            grad.setColorAt(0, self.bg)
            grad.setColorAt(1, self.bg2)
            painter.fillRect(rect, QBrush(grad))
        elif self.bg.isValid():
            painter.fillRect(rect, self.bg)
        play_lbl = self._current_playhead_label()
        self._last_playhead_label = play_lbl
        self._draw_time_panel(painter, play_lbl)
        base_y = self.w.ruler_height
        tick_metrics = QFontMetrics(self.tick_font)
        label_top = max(0, self.label_top - 2)
        long_ht = base_y - (label_top + tick_metrics.height()) - 2
        short_ht = long_ht / 2
        painter.setPen(self.tick_pen)

        offset_px = getattr(self.w, "h_scroll_offset", 0.0)
        if pps <= 0:
            return
        visible_px = width
        start_seconds = offset_px / pps
        end_seconds = (offset_px + visible_px) / pps
        fpt = self._frames_per_tick(pps, fps_float)
        if fpt <= 0:
            return
        total_frames = int(duration * fps_float)
        start_frame = int(math.floor((start_seconds * fps_float) / fpt) * fpt)
        start_frame = max(0, start_frame)
        end_frame = int(math.ceil((end_seconds * fps_float) / fpt) * fpt)
        end_frame = min(total_frames, end_frame + fpt)
        frame = start_frame
        while frame <= end_frame:
            t = frame / fps_float
            x = self.w.track_name_width + t * pps - offset_px
            ht = long_ht if frame % (fpt * 2) == 0 else short_ht

            if x >= self.w.track_name_width - 2 and x <= self.w.track_name_width + visible_px + 2:
                painter.drawLine(QPointF(x, base_y), QPointF(x, base_y - ht))

            if frame % (fpt * 2) == 0 and (
                x + 1.0 >= self.w.track_name_width and x <= self.w.track_name_width + visible_px
            ):
                tt = secondsToTime(t, fps_info["num"], fps_info["den"])
                if frame == 0:
                    lbl = f"{int(tt['min'])}:{tt['sec']}"
                    text_w = tick_metrics.width(lbl)
                    text_rect = QRectF(
                        x + 2,
                        label_top,
                        text_w,
                        tick_metrics.height(),
                    )
                    align = Qt.AlignLeft | Qt.AlignTop
                else:
                    lbl = f"{tt['hour']}:{tt['min']}:{tt['sec']}"
                    if fpt < round(fps_float):
                        lbl += f",{tt['frame']}"
                    text_w = tick_metrics.width(lbl)
                    text_rect = QRectF(
                        x - text_w / 2,
                        label_top,
                        text_w,
                        tick_metrics.height(),
                    )
                    align = Qt.AlignCenter | Qt.AlignTop
                painter.setPen(self.text_pen)
                painter.setFont(self.tick_font)
                painter.drawText(text_rect, align, lbl)
                painter.setPen(self.tick_pen)
            frame += fpt

    def paint_overlay(self, painter: QPainter):
        self._draw_time_panel(painter, getattr(self, "_last_playhead_label", None))
