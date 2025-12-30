"""
 @file
 @brief Marker geometry helpers for the timeline widget.
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

from classes.query import Marker


class MarkerGeometryMixin:
    """Populate cached marker rectangles."""

    def _populate_marker_rects(self, ctx):
        w = self.widget
        top_margin = ctx.get("top_margin", 0.0)
        height = max(0.0, ctx["content_h"] - top_margin)
        theme = getattr(w, "theme", None)
        pix = getattr(theme, "marker_icon", None) if theme else None
        icon_w = float(getattr(theme, "marker_icon_width", 0) or 0)
        icon_h = float(getattr(theme, "marker_icon_height", 0) or 0)
        if icon_w <= 0.0 and pix:
            icon_w = float(pix.width())
        if icon_h <= 0.0 and pix:
            icon_h = float(pix.height())
        if icon_w <= 0.0:
            icon_w = 8.0
        if icon_h <= 0.0:
            icon_h = 10.0
        offset_x = getattr(theme, "marker_icon_offset_x", None) if theme else None
        if offset_x is None:
            offset_x = -icon_w / 2.0
        offset_y = getattr(theme, "marker_icon_offset_y", None) if theme else None
        if offset_y is None:
            offset_y = -6.0
        hit_pad = getattr(theme, "marker_hit_padding", 0.0) if theme else 0.0
        try:
            hit_pad = float(hit_pad)
        except (TypeError, ValueError):
            hit_pad = 0.0
        hit_pad = max(0.0, hit_pad)
        for marker in Marker.filter():
            mx = (
                w.track_name_width
                + marker.data.get("position", 0.0) * w.pixels_per_second
            )
            line_rect = QRectF(
                mx,
                w.ruler_height + top_margin,
                0.5,
                height,
            )
            icon_rect = None
            if icon_w > 0.0 and icon_h > 0.0:
                icon_rect = QRectF(
                    mx + offset_x,
                    max(0.0, w.ruler_height - icon_h - offset_y),
                    icon_w,
                    icon_h,
                )
            hit_rect = None
            if icon_rect and not icon_rect.isNull() and hit_pad > 0.0:
                hit_rect = QRectF(icon_rect)
                hit_rect.adjust(-hit_pad, -hit_pad, hit_pad, hit_pad)
            seconds = marker.data.get("position", 0.0)
            try:
                seconds = float(seconds)
            except (TypeError, ValueError):
                seconds = 0.0
            entry = {
                "marker": marker,
                "id": str(getattr(marker, "id", "")),
                "seconds": seconds,
                "line_rect": line_rect,
            }
            if icon_rect:
                entry["icon_rect"] = icon_rect
            if hit_rect:
                entry["hit_rect"] = hit_rect
            self.marker_rects.append(entry)
