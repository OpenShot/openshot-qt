"""
 @file
 @brief Clip geometry helpers for the timeline widget.
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

from classes.query import Clip

from .base import _GeometryEntry


class ClipGeometryMixin:
    """Populate cached clip rectangles."""

    def _populate_clip_rects(self, layers, ctx, win):
        w = self.widget
        overrides_map = getattr(w, "_pending_clip_overrides", {})
        entries = []
        selected_ids = set(getattr(win, "selected_clips", []) or [])
        for clip in Clip.filter():
            clip_data = clip.data if isinstance(clip.data, dict) else {}
            override = overrides_map.get(clip.id, {})

            position = override.get("position", clip_data.get("position", 0.0))
            start = override.get("start", clip_data.get("start", 0.0))
            end = override.get("end", clip_data.get("end", start))
            layer_val = override.get("layer", clip_data.get("layer", 0))

            try:
                position = float(position)
            except (TypeError, ValueError):
                position = 0.0
            try:
                start = float(start)
            except (TypeError, ValueError):
                start = 0.0
            try:
                end = float(end)
            except (TypeError, ValueError):
                end = start
            if end < start:
                end = start
            try:
                layer_key = int(layer_val)
            except (TypeError, ValueError):
                layer_key = layer_val

            cx = (
                w.track_name_width
                + position * w.pixels_per_second
            )
            layer_idx = layers.get(layer_key, 0)
            offset = ctx.get("track_offsets", {}).get(
                w.normalize_track_number(layer_key),
                layer_idx * ctx["spacing"],
            )
            cy = (
                w.ruler_height
                + ctx.get("top_margin", 0.0)
                + offset
            )
            cw = (end - start) * w.pixels_per_second
            rect = QRectF(cx, cy, cw, w.vertical_factor)
            entries.append((rect.left(), rect, clip))

        def _clip_sort_key(entry):
            left, rect, clip = entry
            return left, rect.x(), getattr(clip, "id", "")

        entries.sort(key=_clip_sort_key)
        clip_entries = []
        clip_starts = []
        max_right = float("-inf")
        max_rights = []
        for left, rect, clip in entries:
            is_selected = clip.id in selected_ids
            clip_entries.append(_GeometryEntry(rect=rect, obj=clip, selected=is_selected))
            clip_starts.append(left)
            max_right = max(max_right, rect.right())
            max_rights.append(max_right)
        self.clip_entries = clip_entries
        self._clip_starts = clip_starts
        self._clip_max_rights = max_rights
