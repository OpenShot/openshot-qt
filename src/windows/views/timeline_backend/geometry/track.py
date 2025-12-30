"""
 @file
 @brief Track-related geometry helpers for the timeline widget.
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

from classes.query import Track


class TrackGeometryMixin:
    """Populate cached track rectangles and layer lookups."""

    def _build_layer_index(self):
        self.track_list = list(reversed(sorted(Track.filter())))
        layers = {}
        for idx, layer in enumerate(self.track_list):
            layers[layer.data.get("number")] = idx
        return layers

    def _populate_track_rects(self, layers, ctx):
        w = self.widget
        offsets = ctx.get("track_offsets", {})
        heights = ctx.get("track_heights", {})
        self.panel_rects = {}
        track_entries = []
        track_offsets = []
        for track in self.track_list:
            track_num = w.normalize_track_number(track.data.get("number"))
            layer_index = layers.get(track.data.get("number"), 0)
            y = (
                w.ruler_height
                + ctx.get("top_margin", 0.0)
                + offsets.get(track_num, layer_index * ctx["spacing"])
            )
            track_height = heights.get(track_num, w.vertical_factor)
            track_rect = QRectF(
                w.track_name_width,
                y,
                ctx["timeline_w"],
                track_height,
            )
            name_rect = QRectF(0, y, w.track_name_width, track_height)
            track_entries.append((track_rect, track, name_rect))

            panel_height = max(0.0, track_height - w.vertical_factor)
            if panel_height > 0.0:
                panel_rect = QRectF(
                    track_rect.x(),
                    y + w.vertical_factor,
                    track_rect.width(),
                    panel_height,
                )
                self.panel_rects[track_num] = panel_rect
            else:
                self.panel_rects.pop(track_num, None)

            track_offsets.append(y)

        self.track_rects = track_entries
        self._track_offsets = track_offsets

        w.resize_handle_rect = QRectF(
            w.track_name_width - w._resize_handle_width / 2,
            w.ruler_height + ctx.get("top_margin", 0.0),
            w._resize_handle_width,
            max(0.0, ctx["content_h"] - ctx.get("top_margin", 0.0)),
        )
        w.timeline_resize_handle_rect = QRectF()
