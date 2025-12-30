"""
 @file
 @brief Painter for the keyframe panel overlay.
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

import math

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen

from classes.logger import log

from .base import BasePainter


class KeyframePanelPainter(BasePainter):
    def __init__(self, widget):
        self._last_visible_tracks = None
        self._last_enabled_tracks = None
        super().__init__(widget)

    def update_theme(self):
        name_bg = self.w.theme.track.name_background
        if not name_bg.isValid():
            name_bg = self.w.theme.track.background
        self.panel_brush = QBrush(name_bg) if name_bg.isValid() else QBrush()
        self.property_brush = QBrush(self.w.theme.keyframe_panel_property_bg)
        if not self.w.theme.keyframe_panel_property_bg.isValid():
            base = self.w.theme.track.background
            if base.isValid():
                lighter = QColor(base)
                lighter = lighter.lighter(120)
                self.property_brush = QBrush(lighter)
            else:
                self.property_brush = QBrush(QColor("#2f2f2f"))
        self.text_pen = QPen(self.w.theme.track.font_color)
        track_border = self.w.theme.track.border_color
        if not track_border.isValid():
            track_border = self.w.theme.track.font_color
        curve_color = QColor(self.w.keyframe_painter.fill)
        if not curve_color.isValid():
            curve_color = QColor(track_border)
        marker_border = QColor(self.w.keyframe_painter.border)
        if not marker_border.isValid():
            marker_border = QColor(curve_color)

        self.range_pen = QPen(track_border)
        self.range_pen.setCosmetic(True)
        self.range_pen.setWidthF(1.0)

        self.curve_pen = QPen(curve_color)
        self.curve_pen.setCosmetic(True)
        self.curve_pen.setWidthF(1.3)

        self.marker_pen = QPen(marker_border)
        self.marker_pen.setCosmetic(True)
        self.marker_brush = QBrush(curve_color)
        base_size = float(getattr(self.w.keyframe_painter, "size", 10) or 10)
        self.marker_size = max(6.0, base_size * 0.75)
        self.label_margin = max(6.0, float(self.w.theme.menu_margin or 0.0))
        self.add_pix = None
        self.add_margin = float(self.w.theme.menu_margin or 0.0) or self.label_margin
        add_icon = getattr(self.w.theme, "keyframe_panel_add_icon", None)
        if add_icon:
            row_height = float(getattr(self.w, "keyframe_panel_row_height", 24.0) or 0.0)
            lane_padding = min(6.0, row_height * 0.25 if row_height else 6.0)
            target = max(8.0, row_height - lane_padding * 2.0)
            if target > 0.0:
                self.add_pix = self.scaled_pixmap(add_icon, target, target)
            else:
                self.add_pix = add_icon
        if self.add_margin <= 0.0:
            self.add_margin = self.label_margin

    def _seconds_to_x(self, seconds):
        try:
            seconds_val = float(seconds)
        except (TypeError, ValueError):
            seconds_val = 0.0
        state = self.w.geometry._current_view_state()
        offset_px = getattr(self.w, "h_scroll_offset", state.get("h_offset", 0.0))
        origin = self.w.track_name_width - offset_px
        return origin + seconds_val * float(self.w.pixels_per_second or 0.0)

    def _value_to_y(self, value, lane_rect, min_val, max_val):
        top = lane_rect.top()
        bottom = lane_rect.bottom()
        height = lane_rect.height()
        if height <= 0.0:
            return lane_rect.center().y()
        try:
            value_float = float(value)
        except (TypeError, ValueError):
            value_float = None
        if value_float is None or min_val is None or max_val is None:
            return lane_rect.center().y()
        if not math.isfinite(value_float):
            return lane_rect.center().y()
        if max_val is None or not math.isfinite(max_val):
            return lane_rect.center().y()
        if min_val is None or not math.isfinite(min_val):
            return lane_rect.center().y()
        span = max_val - min_val
        if span == 0.0:
            return lane_rect.center().y()
        ratio = (value_float - min_val) / span
        if ratio < 0.0:
            ratio = 0.0
        if ratio > 1.0:
            ratio = 1.0
        return bottom - ratio * height

    def _normalize_interpolation(self, value):
        if isinstance(value, str):
            value_lower = value.lower()
            if value_lower in {"bezier", "linear", "constant"}:
                return value_lower
        try:
            idx = int(value)
        except (TypeError, ValueError):
            idx = 0
        if idx == 0:
            return "bezier"
        if idx == 1:
            return "linear"
        return "constant"

    def _draw_marker(self, painter, x, y, interpolation=None):
        size = self.marker_size
        half = size / 2.0
        rect = QRectF(x - half, y - half, size, size)
        painter.setBrush(self.marker_brush)
        painter.setPen(self.marker_pen)
        mode = self._normalize_interpolation(interpolation)
        if mode == "linear":
            painter.drawRect(rect)
            return
        if mode == "constant":
            path = QPainterPath()
            path.moveTo(x, y - half)
            path.lineTo(x + half, y)
            path.lineTo(x, y + half)
            path.lineTo(x - half, y)
            path.closeSubpath()
            painter.drawPath(path)
            return
        painter.drawEllipse(rect)

    def _paint_property_row(
        self,
        painter: QPainter,
        label_rect: QRectF,
        lane_rect: QRectF,
        prop,
        context,
        lane_padding,
        text_offset,
        timeline_area: QRectF,
        *,
        draw_labels: bool = True,
        draw_timeline: bool = True,
    ):
        lane_clip = lane_rect.intersected(timeline_area)

        if draw_timeline and lane_clip.width() > 0.0 and lane_clip.height() > 0.0:
            painter.save()
            painter.setClipRect(lane_clip)
            painter.fillRect(lane_clip, self.property_brush)
            if self.range_pen.color().isValid() and self.range_pen.widthF() > 0.0:
                painter.setPen(self.range_pen)
                painter.drawRect(lane_clip.adjusted(0.5, 0.5, -0.5, -0.5))
            painter.restore()

        add_rect = QRectF()
        can_add = isinstance(prop, dict) and not prop.get("placeholder")
        if can_add:
            cached = prop.get("_panel_add_rect") if isinstance(prop, dict) else None
            if isinstance(cached, QRectF) and not cached.isNull():
                add_rect = cached
            else:
                add_rect = self.w._panel_add_icon_rect(label_rect)
                if isinstance(prop, dict):
                    prop["_panel_add_rect"] = add_rect

        if draw_labels:
            painter.setPen(self.text_pen)
            offset = max(self.label_margin, float(text_offset or 0.0))
            text_rect = label_rect.adjusted(offset, 0.0, -self.label_margin, 0.0)
            if not add_rect.isNull():
                right_edge = add_rect.x() - max(self.label_margin, 2.0)
                if right_edge < text_rect.left():
                    right_edge = text_rect.left()
                text_rect.setRight(right_edge)
            text = prop.get("display_name", "")
            painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, text)

        if draw_labels and self.add_pix and not add_rect.isNull():
            painter.drawPixmap(add_rect.topLeft(), self.add_pix)

        if prop.get("placeholder") or not draw_timeline:
            return

        if lane_clip.width() <= 0.0 or lane_clip.height() <= 0.0:
            return

        baseline = lane_rect.center().y()
        if lane_rect.height() > 0.0:
            baseline = max(
                lane_rect.top() + lane_padding,
                min(lane_rect.bottom() - lane_padding, baseline),
            )

        range_start = context.get("range_start_seconds") if isinstance(context, dict) else None
        range_end = context.get("range_end_seconds") if isinstance(context, dict) else None
        start_x = lane_rect.left() + lane_padding
        end_x = lane_rect.right() - lane_padding
        if range_start is not None and range_end is not None:
            start_x = self._seconds_to_x(range_start)
            end_x = self._seconds_to_x(range_end)
        if end_x < start_x:
            start_x, end_x = end_x, start_x
        start_x = max(start_x, lane_clip.left())
        end_x = min(end_x, lane_clip.right())

        painter.save()
        painter.setClipRect(lane_clip)
        painter.setPen(self.curve_pen)
        painter.drawLine(QPointF(start_x, baseline), QPointF(end_x, baseline))

        inactive = getattr(self.w.keyframe_painter, "inactive_opacity", 0.5)
        for point in prop.get("points") or []:
            seconds = point.get("seconds")
            if seconds is None:
                continue
            x = self._seconds_to_x(seconds)
            if x < lane_clip.left() - 1.0 or x > lane_clip.right() + 1.0:
                continue
            x = max(lane_clip.left(), min(lane_clip.right(), x))
            selected = bool(point.get("selected"))
            painter.setOpacity(1.0 if selected else inactive)
            self._draw_marker(painter, x, baseline, point.get("interpolation"))
        painter.setOpacity(1.0)
        painter.restore()

    def paint(self, painter: QPainter, mode: str = "full"):
        area = QRectF(
            0.0,
            self.w.ruler_height,
            self.w.width() - self.w.scroll_bar_thickness,
            self.w.height() - self.w.ruler_height - self.w.scroll_bar_thickness,
        )
        draw_timeline = mode in ("full", "underlay")
        draw_labels = mode in ("full", "overlay")
        if not draw_timeline and not draw_labels:
            return

        painter.save()
        painter.setClipRect(area)

        timeline_area = QRectF(
            self.w.track_name_width,
            self.w.ruler_height,
            max(0.0, self.w.width() - self.w.track_name_width - self.w.scroll_bar_thickness),
            self.w.height() - self.w.ruler_height - self.w.scroll_bar_thickness,
        )

        padding = float(getattr(self.w, "keyframe_panel_padding", 6.0) or 0.0)
        row_height = float(getattr(self.w, "keyframe_panel_row_height", 24.0) or 0.0)
        spacing = float(getattr(self.w, "keyframe_panel_row_spacing", 4.0) or 0.0)
        lane_padding = min(6.0, row_height * 0.25 if row_height else 6.0)

        visible_tracks = []
        for _track_rect, track, name_rect in self.w.geometry.iter_tracks():
            track_num = self.w.normalize_track_number(track.data.get("number"))
            if not self.w.is_keyframe_panel_visible(track_num):
                continue
            panel_rect = self.w.geometry.panel_rect(track_num)
            if not panel_rect or panel_rect.height() <= 0.0:
                log.info(
                    "Keyframe panel paint skipped: track %s has no panel rect",
                    track_num,
                )
                continue
            properties = self.w.get_track_panel_properties(track_num)
            if not properties:
                log.info("Keyframe panel paint skipped: track %s has no properties", track_num)
                continue
            visible_tracks.append(track_num)
            context = self.w.get_track_panel_context(track_num)
            y = panel_rect.y() + padding
            label_panel = QRectF(name_rect.x(), panel_rect.y(), name_rect.width(), panel_rect.height())
            if draw_labels and self.panel_brush.style() != Qt.NoBrush and self.panel_brush.color().isValid():
                painter.fillRect(label_panel, self.panel_brush)
            if draw_timeline and self.panel_brush.style() != Qt.NoBrush and self.panel_brush.color().isValid():
                panel_fill = panel_rect.intersected(timeline_area)
                if not panel_fill.isNull():
                    painter.save()
                    painter.setClipRect(timeline_area)
                    painter.fillRect(panel_fill, self.panel_brush)
                    painter.restore()
            toggle_rect = self.w._track_toggle_rect(track, name_rect)
            indent = 0.0
            if not toggle_rect.isNull():
                indent = max(0.0, toggle_rect.x() - label_panel.x())
            for prop in properties:
                if row_height <= 0.0:
                    break
                if y + row_height > panel_rect.bottom() - padding + 1.0:
                    break
                label_rect = QRectF(label_panel.x(), y, label_panel.width(), row_height)
                lane_rect = QRectF(panel_rect.x(), y, panel_rect.width(), row_height)
                self._paint_property_row(
                    painter,
                    label_rect,
                    lane_rect,
                    prop,
                    context,
                    lane_padding,
                    indent,
                    timeline_area,
                    draw_labels=draw_labels,
                    draw_timeline=draw_timeline,
                )
                y += row_height + spacing

        painter.restore()

        if draw_timeline:
            if visible_tracks:
                try:
                    current = tuple(visible_tracks)
                except TypeError:
                    current = tuple(list(visible_tracks))
                if current != self._last_visible_tracks:
                    log.debug("Keyframe panel paint tracks=%s", visible_tracks)
                    self._last_visible_tracks = current
                    self._last_enabled_tracks = None
            elif any(self.w._track_panel_enabled.values()):
                enabled = [
                    self.w.normalize_track_number(track)
                    for track, enabled in self.w._track_panel_enabled.items()
                    if enabled
                ]
                try:
                    enabled_signature = tuple(sorted(enabled))
                except TypeError:
                    enabled_signature = tuple(enabled)
                if enabled_signature != self._last_enabled_tracks:
                    log.debug(
                        "Keyframe panel paint: no visible tracks (enabled=%s)",
                        enabled,
                    )
                    self._last_enabled_tracks = enabled_signature
                    self._last_visible_tracks = None
