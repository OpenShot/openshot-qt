"""
 @file
 @brief Geometry caching helpers for the experimental timeline widget.
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

from bisect import bisect_left

from PyQt5.QtCore import QPointF, QRectF

from classes.app import get_app
from classes.logger import log


class _GeometryEntry:
    def __init__(self, rect: QRectF, obj: object, selected: bool):
        self.rect = rect
        self.obj = obj
        self.selected = selected

    @property
    def left(self):
        return self.rect.left()

    @property
    def right(self):
        return self.rect.right()

    @property
    def top(self):
        return self.rect.top()

    @property
    def bottom(self):
        return self.rect.bottom()


class GeometryBase:
    """Shared cache and hit-testing helpers for timeline geometry."""

    def __init__(self, widget):
        self.widget = widget
        self.dirty = True
        self.track_rects = []
        self.clip_entries = []
        self.transition_entries = []
        self.marker_rects = []
        self.track_list = []
        self.panel_rects = {}
        self._clip_starts = []
        self._clip_max_rights = []
        self._transition_starts = []
        self._transition_max_rights = []
        self._track_offsets = []
        self._view_context = {}

    # ------------------------------------------------------------------
    # Cache management
    # ------------------------------------------------------------------
    def mark_dirty(self):
        """Invalidate all cached geometry."""
        self.dirty = True
        if hasattr(self.widget, "_keyframes_dirty"):
            self.widget._keyframes_dirty = True

    def ensure(self):
        """Rebuild cached geometry if marked dirty."""
        if self.dirty:
            self._rebuild()

    # ------------------------------------------------------------------
    # Geometry building
    # ------------------------------------------------------------------
    def _reset_cache(self):
        self.track_rects.clear()
        self.clip_entries.clear()
        self.transition_entries.clear()
        self.marker_rects.clear()
        self.panel_rects.clear()
        self._clip_starts.clear()
        self._clip_max_rights.clear()
        self._transition_starts.clear()
        self._transition_max_rights.clear()
        self._track_offsets.clear()

    @staticmethod
    def _entry_sort_key(entry):
        obj = getattr(entry, "obj", None)
        obj_id = getattr(obj, "id", "") if obj is not None else ""
        return (round(entry.rect.left(), 6), round(entry.rect.top(), 6), obj_id)

    def _resort_clip_entries(self):
        if not self.clip_entries:
            self._clip_starts = []
            return
        self.clip_entries.sort(key=self._entry_sort_key)
        starts = []
        max_rights = []
        max_right = float("-inf")
        for entry in self.clip_entries:
            rect = entry.rect
            starts.append(rect.left())
            max_right = max(max_right, rect.right())
            max_rights.append(max_right)
        self._clip_starts = starts
        self._clip_max_rights = max_rights

    def _resort_transition_entries(self):
        if not self.transition_entries:
            self._transition_starts = []
            return
        self.transition_entries.sort(key=self._entry_sort_key)
        starts = []
        max_rights = []
        max_right = float("-inf")
        for entry in self.transition_entries:
            rect = entry.rect
            starts.append(rect.left())
            max_right = max(max_right, rect.right())
            max_rights.append(max_right)
        self._transition_starts = starts
        self._transition_max_rights = max_rights

    def _update_vertical_factor(self, layers, view_h):
        if self.widget.track_height:
            self.widget.vertical_factor = self.widget.track_height
            return
        tracks = len(layers) if layers else 1
        self.widget.vertical_factor = max(1, view_h / tracks)

    def _update_horizontal_scrollbar(self, timeline_w, view_w):
        w = self.widget
        w.scrollbar_position[2] = timeline_w
        w.scrollbar_position[3] = view_w
        view_ratio = view_w / timeline_w if timeline_w else 1.0
        max_left = max(0.0, 1.0 - view_ratio)
        left = max(0.0, min(w.scrollbar_position[0], max_left))
        scroll_px = left * timeline_w
        max_scroll = max(0.0, timeline_w - view_w)
        if max_scroll:
            scroll_px = min(scroll_px, max_scroll)
            left = scroll_px / timeline_w
        right = left + view_ratio
        w.scrollbar_position[0] = left
        w.scrollbar_position[1] = right
        if view_ratio < 1.0:
            handle_w = max(20.0, view_ratio * view_w)
            avail = view_w - handle_w
            handle_x = w.track_name_width
            if max_scroll:
                handle_x += (scroll_px / max_scroll) * avail
            w.scroll_bar_rect = QRectF(
                handle_x,
                w.height() - w.scroll_bar_thickness,
                handle_w,
                w.scroll_bar_thickness,
            )
            return scroll_px
        w.scroll_bar_rect = QRectF()
        return 0.0

    def _update_vertical_scrollbar(self, content_h, view_h):
        w = self.widget
        w.v_scrollbar_position[2] = content_h
        w.v_scrollbar_position[3] = view_h
        v_ratio = view_h / content_h if content_h else 1.0
        max_top = max(0.0, 1.0 - v_ratio)
        top = max(0.0, min(w.v_scrollbar_position[0], max_top))
        scroll_py = top * content_h
        max_vscroll = max(0.0, content_h - view_h)
        if max_vscroll:
            scroll_py = min(scroll_py, max_vscroll)
            top = scroll_py / content_h
        bottom = top + v_ratio
        w.v_scrollbar_position[0] = top
        w.v_scrollbar_position[1] = bottom
        if v_ratio < 1.0:
            handle_h = max(20.0, v_ratio * view_h)
            avail = view_h - handle_h
            handle_y = w.ruler_height
            if max_vscroll:
                handle_y += (scroll_py / max_vscroll) * avail
            w.v_scroll_bar_rect = QRectF(
                w.width() - w.scroll_bar_thickness,
                handle_y,
                w.scroll_bar_thickness,
                handle_h,
            )
            return scroll_py
        w.v_scroll_bar_rect = QRectF()
        return 0.0

    def _calculate_view_context(self, layers):
        w = self.widget
        proj = get_app().project
        duration = self.widget._current_project_duration()
        tick_px = proj.get("tick_pixels") or 100
        w.pixels_per_second = tick_px / float(w.zoom_factor or 1)
        view_w = w.width() - w.track_name_width - w.scroll_bar_thickness
        view_h = w.height() - w.ruler_height - w.scroll_bar_thickness
        timeline_w = max(view_w, duration * w.pixels_per_second)
        self._update_vertical_factor(layers, view_h)
        track_gap = float(getattr(w, "track_gap", 0.0) or 0.0)
        top_margin = float(getattr(w, "track_margin_top", 0.0) or 0.0)
        track_offsets = {}
        track_heights = {}
        cumulative = 0.0
        base_height = float(self.widget.vertical_factor or 0.0)
        for idx, track in enumerate(self.track_list):
            if idx > 0:
                cumulative += track_gap
            track_num = w.normalize_track_number(track.data.get("number"))
            extra = float(w.get_track_panel_height(track_num))
            extra = max(0.0, extra)
            track_offsets[track_num] = cumulative
            track_height = base_height + extra
            track_heights[track_num] = track_height
            cumulative += track_height
            if extra > 0.0:
                log.debug(
                    "Geometry: track %s base=%.2f extra=%.2f total=%.2f",
                    track_num,
                    base_height,
                    extra,
                    track_height,
                )
        content_h = max(cumulative, 0.0)
        spacing = base_height + track_gap
        content_h = max(content_h, 0.0) + top_margin
        h_offset = self._update_horizontal_scrollbar(timeline_w, view_w)
        if getattr(w, "_project_resize_keep_right", False):
            view_ratio = view_w / timeline_w if timeline_w else 1.0
            view_ratio = min(1.0, max(0.0, view_ratio))
            left = 0.0
            if view_ratio < 1.0:
                left = max(0.0, 1.0 - view_ratio)
            right = min(1.0, left + view_ratio)
            w.scrollbar_position[0] = left
            w.scrollbar_position[1] = right
            w.h_scroll_offset = left * timeline_w
            if view_ratio < 1.0:
                handle_w = max(20.0, view_ratio * view_w)
                avail = view_w - handle_w
                handle_x = w.track_name_width
                max_scroll = max(0.0, timeline_w - view_w)
                scroll_px = w.h_scroll_offset
                if max_scroll > 0.0 and avail > 0.0:
                    handle_x += (scroll_px / max_scroll) * avail
                w.scroll_bar_rect = QRectF(
                    handle_x,
                    w.height() - w.scroll_bar_thickness,
                    handle_w,
                    w.scroll_bar_thickness,
                )
            else:
                w.scroll_bar_rect = QRectF()
        v_offset = self._update_vertical_scrollbar(content_h, view_h)
        ctx = {
            "view_w": view_w,
            "view_h": view_h,
            "timeline_w": timeline_w,
            "spacing": spacing,
            "top_margin": top_margin,
            "content_h": content_h,
            "h_offset": h_offset,
            "v_offset": v_offset,
            "track_offsets": track_offsets,
            "track_heights": track_heights,
        }
        self._view_context = ctx
        return ctx

    def refresh_viewport(self, *, view_w=None, view_h=None, timeline_w=None):
        """Update viewport-dependent values without rebuilding cached geometry."""

        w = self.widget

        if view_w is None:
            view_w = w.width() - w.track_name_width - w.scroll_bar_thickness
        if view_h is None:
            view_h = w.height() - w.ruler_height - w.scroll_bar_thickness

        view_w = max(0.0, float(view_w or 0.0))
        view_h = max(0.0, float(view_h or 0.0))

        ctx = self._view_context or {}
        self._view_context = ctx

        if timeline_w is None:
            baseline = float(ctx.get("timeline_w", 0.0) or 0.0)
            timeline_w = max(baseline, view_w)
        else:
            timeline_w = max(float(timeline_w or 0.0), view_w)

        ctx["view_w"] = view_w
        ctx["view_h"] = view_h
        ctx["timeline_w"] = timeline_w

        top_margin = float(ctx.get("top_margin", 0.0) or 0.0)
        content_h = max(0.0, float(ctx.get("content_h", view_h + top_margin) or 0.0))
        ctx["content_h"] = content_h

        h_offset = self._update_horizontal_scrollbar(timeline_w, view_w)
        if getattr(w, "_project_resize_keep_right", False):
            view_ratio = view_w / timeline_w if timeline_w else 1.0
            view_ratio = min(1.0, max(0.0, view_ratio))
            left = 0.0
            if view_ratio < 1.0:
                left = max(0.0, 1.0 - view_ratio)
            right = min(1.0, left + view_ratio)
            w.scrollbar_position[0] = left
            w.scrollbar_position[1] = right
            w.h_scroll_offset = left * timeline_w
            if view_ratio < 1.0:
                handle_w = max(20.0, view_ratio * view_w)
                avail = view_w - handle_w
                handle_x = w.track_name_width
                max_scroll = max(0.0, timeline_w - view_w)
                scroll_px = w.h_scroll_offset
                if max_scroll > 0.0 and avail > 0.0:
                    handle_x += (scroll_px / max_scroll) * avail
                w.scroll_bar_rect = QRectF(
                    handle_x,
                    w.height() - w.scroll_bar_thickness,
                    handle_w,
                    w.scroll_bar_thickness,
                )
            else:
                w.scroll_bar_rect = QRectF()

        self._update_vertical_scrollbar(content_h, view_h)

        if self.track_rects:
            for rect, _track, _name_rect in self.track_rects:
                if rect.width() != timeline_w:
                    rect.setWidth(timeline_w)

        if self.panel_rects:
            for rect in self.panel_rects.values():
                if rect.width() != timeline_w:
                    rect.setWidth(timeline_w)

        w.resize_handle_rect = QRectF(
            w.track_name_width - w._resize_handle_width / 2,
            w.ruler_height + top_margin,
            w._resize_handle_width,
            max(0.0, content_h - top_margin),
        )
        w.timeline_resize_handle_rect = QRectF()

        self._current_view_state()

    def _rebuild(self):
        win = get_app().window

        self._reset_cache()
        layers = self._build_layer_index()

        if not hasattr(win, "timeline"):
            self.dirty = False
            return

        ctx = self._calculate_view_context(layers)
        self._populate_track_rects(layers, ctx)
        self._populate_clip_rects(layers, ctx, win)
        self._populate_transition_rects(layers, ctx, win)
        self._populate_marker_rects(ctx)
        self.dirty = False

    def _current_view_state(self):
        """Return dictionary describing the current viewport offsets and sizes."""

        w = self.widget
        view_w = w.scrollbar_position[3] or (
            w.width() - w.track_name_width - w.scroll_bar_thickness
        )
        timeline_w = max(
            view_w,
            w.scrollbar_position[2] or self._view_context.get("timeline_w", view_w),
        )
        left = max(0.0, min(w.scrollbar_position[0], 1.0))
        h_offset = left * timeline_w
        max_scroll = max(0.0, timeline_w - view_w)
        if h_offset > max_scroll:
            h_offset = max_scroll

        view_h = w.v_scrollbar_position[3] or (
            w.height() - w.ruler_height - w.scroll_bar_thickness
        )
        content_h = max(
            view_h,
            w.v_scrollbar_position[2],
            self._view_context.get("content_h", view_h),
        )
        top = max(0.0, min(w.v_scrollbar_position[0], 1.0))
        v_offset = top * content_h
        max_vscroll = max(0.0, content_h - view_h)
        if v_offset > max_vscroll:
            v_offset = max_vscroll

        w.h_scroll_offset = h_offset
        if self._view_context is not None:
            self._view_context["h_offset"] = h_offset
            self._view_context["v_offset"] = v_offset
        return {
            "view_w": view_w,
            "view_h": view_h,
            "timeline_w": timeline_w,
            "content_h": content_h,
            "h_offset": h_offset,
            "v_offset": v_offset,
        }

    # ------------------------------------------------------------------
    # Hit testing
    # ------------------------------------------------------------------
    def hit(self, pos: QPointF):
        """Return a string describing what lies under *pos*."""
        self.ensure()
        if (
            pos.x() >= self.widget.track_name_width
            and pos.y() >= self.widget.ruler_height
        ):
            for rect, _obj, _sel, _type in self.iter_items(reverse=True):
                if rect.contains(pos):
                    return "clip"
        for _track_rect, track, name_rect in self.iter_tracks():
            track_num = self.widget.normalize_track_number(track.data.get("number"))
            panel_rect = self.panel_rect(track_num)
            if not panel_rect or panel_rect.height() <= 0.0:
                continue
            if panel_rect.contains(pos):
                return "panel"
            combined = QRectF(
                name_rect.x(),
                panel_rect.y(),
                name_rect.width() + panel_rect.width(),
                panel_rect.height(),
            )
            if combined.contains(pos):
                return "panel"
        if self.widget.scroll_bar_rect.contains(pos):
            return "h-scroll"
        if getattr(self.widget, "v_scroll_bar_rect", QRectF()).contains(pos):
            return "v-scroll"
        timeline_handle = self.timeline_handle_rect()
        if timeline_handle.contains(pos):
            return "timeline-handle"
        if self.widget.resize_handle_rect.contains(pos):
            return "handle"
        if pos.y() <= self.widget.ruler_height:
            return "ruler"
        return "background"

    def calc_item_rect(self, item, *, viewport=False):
        """Return QRectF for *item* (Clip or Transition).

        When *viewport* is ``True`` the coordinates are adjusted for the current
        scroll offsets so the rectangle can be compared directly against widget
        positions. Otherwise, geometry is returned in timeline space so the
        cache can be updated without double counting scroll offsets.
        """

        layers = {t.data.get("number"): idx for idx, t in enumerate(self.track_list)}
        spacing = self.widget.vertical_factor + getattr(self.widget, "track_gap", 0)
        offsets = getattr(self, "_view_context", {}).get("track_offsets", {})
        position = float(item.data.get("position", 0.0) or 0.0)
        start = float(item.data.get("start", 0.0) or 0.0)
        end = float(item.data.get("end", start) or start)
        if end < start:
            end = start
        x = self.widget.track_name_width + position * self.widget.pixels_per_second
        layer_val = item.data.get("layer", 0)
        offset = offsets.get(
            self.widget.normalize_track_number(layer_val),
            layers.get(layer_val, 0) * spacing,
        )
        y = (
            self.widget.ruler_height
            + getattr(self.widget, "track_margin_top", 0.0)
            + offset
        )
        width = (end - start) * self.widget.pixels_per_second
        rect = QRectF(x, y, width, self.widget.vertical_factor)
        if viewport:
            state = self._current_view_state()
            rect.translate(-state["h_offset"], -state["v_offset"])
        return rect

    def update_item_rect(self, item, rect):
        """Replace cached rect for *item* if present."""
        for entry in self.clip_entries:
            if entry.obj.id == item.id:
                entry.rect = QRectF(rect)
                self._resort_clip_entries()
                return
        for entry in self.transition_entries:
            if entry.obj.id == item.id:
                entry.rect = QRectF(rect)
                self._resort_transition_entries()
                return

    # ------------------------------------------------------------------
    # Iteration helpers
    # ------------------------------------------------------------------
    def iter_clips(self, reverse=False, *, viewport=True):
        """Yield (rect, clip, selected) tuples for cached clips."""
        yield from self._iter_entries(
            self.clip_entries,
            self._clip_starts,
            self._clip_max_rights,
            reverse,
            viewport=viewport,
        )

    def iter_transitions(self, reverse=False, *, viewport=True):
        """Yield (rect, transition, selected) tuples for cached transitions."""
        yield from self._iter_entries(
            self.transition_entries,
            self._transition_starts,
            self._transition_max_rights,
            reverse,
            viewport=viewport,
        )

    def iter_items(self, reverse=False, *, viewport=True):
        """Yield (rect, obj, selected, type) for transitions then clips."""
        for rect, tran, selected in self.iter_transitions(
            reverse=reverse, viewport=viewport
        ):
            yield rect, tran, selected, "transition"
        for rect, clip, selected in self.iter_clips(
            reverse=reverse, viewport=viewport
        ):
            yield rect, clip, selected, "clip"

    def iter_tracks(self):
        """Yield track and name rectangles adjusted for the current viewport."""

        state = self._current_view_state()
        h_offset = state["h_offset"]
        v_offset = state["v_offset"]

        for rect, track, name_rect in self.track_rects:
            adj_rect = QRectF(rect)
            adj_rect.translate(-h_offset, -v_offset)
            name_adj = QRectF(name_rect)
            name_adj.translate(0.0, -v_offset)
            yield adj_rect, track, name_adj

    def iter_markers(self):
        """Yield marker rectangles adjusted for the current viewport."""

        if not self.marker_rects:
            return
        state = self._current_view_state()
        h_offset = state["h_offset"]
        v_offset = state["v_offset"]
        for rect in self.marker_rects:
            if isinstance(rect, dict):
                entry = dict(rect)
                base_rect = entry.get("line_rect") or entry.get("rect")
                if base_rect:
                    adj = QRectF(base_rect)
                    adj.translate(-h_offset, -v_offset)
                    entry["line_rect"] = adj
                    entry["rect"] = adj
                icon_rect = entry.get("icon_rect")
                if icon_rect:
                    adj_icon = QRectF(icon_rect)
                    adj_icon.translate(-h_offset, -v_offset)
                    entry["icon_rect"] = adj_icon
                hit_rect = entry.get("hit_rect")
                if hit_rect:
                    adj_hit = QRectF(hit_rect)
                    adj_hit.translate(-h_offset, -v_offset)
                    entry["hit_rect"] = adj_hit
                yield entry
                continue
            adj = QRectF(rect)
            adj.translate(-h_offset, -v_offset)
            yield adj

    def panel_rect(self, track_num):
        base_rect = self.panel_rects.get(track_num)
        if not base_rect:
            return None
        state = self._current_view_state()
        rect = QRectF(base_rect)
        rect.translate(-state["h_offset"], -state["v_offset"])
        return rect

    def timeline_handle_rect(self):
        ctx = self._view_context
        state = self._current_view_state()
        timeline_w = ctx.get("timeline_w", state["timeline_w"])
        view_w = state["view_w"]
        h_offset = state["h_offset"]
        handle_width = float(getattr(self.widget, "_project_handle_width", 10.0) or 0.0)
        handle_height = max(
            0.0, ctx.get("content_h", state["content_h"]) - ctx.get("top_margin", 0.0)
        )
        if handle_width <= 0.0 or handle_height <= 0.0:
            return QRectF()
        if timeline_w <= 0.0 or view_w <= 0.0:
            return QRectF()
        right_aligned = h_offset + view_w >= timeline_w - 0.5
        if not right_aligned:
            return QRectF()
        timeline_right = self.widget.track_name_width + timeline_w - h_offset
        visible_limit = self.widget.track_name_width + view_w
        handle_x = timeline_right - handle_width
        handle_x = max(self.widget.track_name_width, handle_x)
        handle_x = min(handle_x, visible_limit - handle_width)
        handle_x = max(self.widget.track_name_width, handle_x)
        return QRectF(
            handle_x,
            self.widget.ruler_height + ctx.get("top_margin", 0.0) - state["v_offset"],
            handle_width,
            handle_height,
        )

    def _iter_entries(
        self,
        entries,
        starts,
        max_rights,
        reverse=False,
        *,
        viewport=True,
    ):
        """Yield visible entries grouped by selection state while preserving stacking order."""

        if not entries:
            return

        state = self._current_view_state()
        h_offset = state["h_offset"]
        v_offset = state["v_offset"]
        view_left = self.widget.track_name_width + h_offset
        view_right = view_left + state["view_w"]
        view_top = self.widget.ruler_height + v_offset
        view_bottom = view_top + state["view_h"]

        margin = max(64.0, state["view_w"] * 0.25)
        search_left = view_left - margin
        search_right = view_right + margin

        def _visible_sequence():
            if not entries:
                return []

            total = len(entries)
            start_idx = bisect_left(starts, search_left)
            forward = []
            idx = start_idx
            while idx < total:
                entry = entries[idx]
                rect = entry.rect
                if rect.left() > search_right:
                    break
                if (
                    rect.right() >= search_left
                    and rect.bottom() >= view_top
                    and rect.top() <= view_bottom
                ):
                    forward.append(idx)
                idx += 1

            backward = []
            idx = start_idx - 1
            while idx >= 0 and max_rights[idx] >= search_left:
                entry = entries[idx]
                rect = entry.rect
                if (
                    rect.right() >= search_left
                    and rect.bottom() >= view_top
                    and rect.top() <= view_bottom
                ):
                    backward.append(idx)
                idx -= 1

            indices = list(reversed(backward)) + forward
            return [entries[i] for i in indices]

        seq = _visible_sequence()

        if reverse:
            seq = list(reversed(seq))
            order = (True, False)
        else:
            order = (False, True)

        for selected_flag in order:
            for entry in seq:
                if entry.selected != selected_flag:
                    continue
                rect = QRectF(entry.rect)
                if viewport:
                    rect.translate(-h_offset, -v_offset)
                yield rect, entry.obj, entry.selected
