"""
 @file
 @brief Keyframe panel layout and interaction helpers.
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

import json
import math
import uuid
from qt_api import QPointF, QRectF, Qt, QTimer
from classes.app import get_app
from classes.logger import log
from classes.query import Clip, Transition, Effect
from .keyframe import keyframe_hit_at


class KeyframePanelMixin:
    def _panel_track_for_item(self, item):
        for track_key, info in (self._panel_properties or {}).items():
            if not isinstance(info, dict):
                continue
            context = info.get("context")
            if isinstance(context, dict) and context.get("placeholder"):
                continue
            properties = info.get("properties") or []
            if not properties:
                continue
            for prop in properties:
                prop_ctx = self._panel_property_context(prop, context)
                if self._panel_context_matches_item(prop_ctx, item):
                    return self.normalize_track_number(track_key)
        return None

    def _panel_drag_item_key(self, item):
        if isinstance(item, Clip):
            return ("clip", str(getattr(item, "id", "")))
        if isinstance(item, Transition):
            return ("transition", str(getattr(item, "id", "")))
        return None

    def _panel_float(self, value, default=0.0):
        try:
            result = float(value)
        except (TypeError, ValueError):
            return default
        if math.isnan(result) or math.isinf(result):
            return default
        return result

    def get_track_panel_height(self, track_num):
        key = self.normalize_track_number(track_num)
        if not self._track_panel_enabled.get(key):
            return 0.0
        return float(self._panel_heights.get(key, 0.0) or 0.0)

    def get_track_panel_properties(self, track_num):
        key = self.normalize_track_number(track_num)
        info = self._panel_properties.get(key)
        if not isinstance(info, dict):
            return []
        return info.get("properties", [])

    def get_track_panel_context(self, track_num):
        key = self.normalize_track_number(track_num)
        info = self._panel_properties.get(key)
        if not isinstance(info, dict):
            return {}
        ctx = info.get("context")
        return ctx if isinstance(ctx, dict) else {}

    def _panel_placeholder_info(self, reason="no-selection"):
        translate = get_app()._tr
        label = translate("No Selection") if reason == "no-selection" else translate("No Keyframes")
        props = [{"display_name": label, "points": [], "placeholder": True}]
        info = {
            "item_id": "",
            "item_type": None,
            "properties": props,
            "context": {"placeholder": reason},
            "base_properties": {},
            "base_context": {},
        }
        height = self._panel_height_for_properties(len(props))
        return info, height

    def _panel_multi_available_map(self, entries):
        available_map = {}
        for entry in entries or []:
            for available_entry in entry.get("available") or []:
                if not isinstance(available_entry, dict):
                    continue
                available_key = available_entry.get("key")
                if available_key is None:
                    continue
                available_map[str(available_key)] = dict(available_entry)
        return available_map

    def _panel_multi_manual_entry(self, track_key, available_map):
        manual_entry = self._panel_manual_properties.get(track_key)
        if not manual_entry or manual_entry.get("item_type") != "multi":
            manual_entry = {"item_id": "", "item_type": "multi", "properties": set()}
        else:
            manual_entry = {
                "item_id": "",
                "item_type": "multi",
                "properties": set(manual_entry.get("properties") or []),
            }
        manual_entry["properties"] = {
            prop_id for prop_id in manual_entry.get("properties", set()) if prop_id in available_map
        }
        self._panel_manual_properties[track_key] = manual_entry
        return manual_entry

    @staticmethod
    def _panel_multi_row_from_available(track_key, prop_id, entry_obj):
        return {
            "key": prop_id,
            "panel_key": prop_id,
            "display_name": entry_obj.get("display_name") or prop_id,
            "points": [],
            "min_value": entry_obj.get("min_value"),
            "max_value": entry_obj.get("max_value"),
            "owner_type": entry_obj.get("owner_type"),
            "source_meta": entry_obj.get("source_meta"),
            "value": entry_obj.get("value"),
            "value_type": entry_obj.get("value_type"),
            "point_paths": [],
            "context": {"item_type": "multi", "track": track_key},
        }

    def _panel_multi_manual_rows(self, track_key, available_map):
        manual_entry = self._panel_multi_manual_entry(track_key, available_map)
        rows = []
        for prop_id in sorted(manual_entry["properties"], key=lambda value: str(value).lower()):
            entry_obj = available_map.get(prop_id)
            if not isinstance(entry_obj, dict):
                continue
            rows.append(self._panel_multi_row_from_available(track_key, prop_id, entry_obj))
        return manual_entry, rows

    def is_keyframe_panel_visible(self, track_num):
        key = self.normalize_track_number(track_num)
        if not self._track_panel_enabled.get(key):
            return False
        if self._panel_heights.get(key, 0.0) <= 0.0:
            return False
        return bool(self.get_track_panel_properties(key))

    def _panel_height_for_properties(self, count):
        try:
            total = int(count)
        except (TypeError, ValueError):
            total = 0
        if total <= 0:
            return 0.0
        padding = float(self.keyframe_panel_padding or 0.0)
        row_height = float(self.keyframe_panel_row_height or 0.0)
        spacing = float(self.keyframe_panel_row_spacing or 0.0)
        height = padding * 2.0 + row_height * total
        if total > 1:
            height += spacing * (total - 1)
        return height

    def _panel_property_key(self, prop):
        if not isinstance(prop, dict):
            return None
        panel_key = prop.get("panel_key")
        if panel_key:
            return panel_key
        key = prop.get("key")
        if key:
            return key
        name = prop.get("display_name")
        if name:
            return name
        return str(id(prop))

    def _panel_context_signature(self, context):
        if not isinstance(context, dict):
            return ("", "", "", "")
        item_type = str(context.get("item_type") or "")
        item_id = str(
            context.get("item_id")
            or context.get("clip_id")
            or context.get("transition_id")
            or context.get("effect_id")
            or ""
        )
        clip_id = str(context.get("clip_id") or "")
        effect_id = str(context.get("effect_id") or "")
        return (item_type, item_id, clip_id, effect_id)

    def _panel_property_context(self, prop, fallback=None):
        if isinstance(prop, dict):
            ctx = prop.get("context")
            if isinstance(ctx, dict):
                return ctx
        return fallback if isinstance(fallback, dict) else {}

    def _panel_point_context_signature(self, point, fallback_context=None):
        point_ctx = point.get("_panel_context") if isinstance(point, dict) else None
        if isinstance(point_ctx, dict):
            return self._panel_context_signature(point_ctx)
        return self._panel_context_signature(fallback_context if isinstance(fallback_context, dict) else {})

    def _panel_selection_frames(self, selector):
        if isinstance(selector, dict):
            source = selector.get("frames", [])
        else:
            source = selector or []
        frames = set()
        for value in source:
            if value is None:
                continue
            try:
                frames.add(int(value))
            except (TypeError, ValueError):
                continue
        return frames

    def _panel_selection_context(self, selector):
        if not isinstance(selector, dict):
            return None
        context = selector.get("context")
        if not context:
            return None
        if isinstance(context, (tuple, list)):
            return tuple(str(part) for part in context)
        return None

    def _panel_selection_selector(self, frames, context_signature=None):
        frame_set = self._panel_selection_frames(frames)
        if not frame_set:
            return None
        if context_signature:
            if isinstance(context_signature, (tuple, list)):
                context_signature = tuple(str(part) for part in context_signature)
            else:
                context_signature = None
        if context_signature:
            return {"frames": frame_set, "context": context_signature}
        return frame_set

    def _panel_selection_contains(self, selector, frame, point=None, fallback_context=None):
        if frame is None:
            return False
        frames = self._panel_selection_frames(selector)
        if frame not in frames:
            return False
        selector_ctx = self._panel_selection_context(selector)
        if selector_ctx is None:
            return True
        point_ctx = self._panel_point_context_signature(point, fallback_context)
        return point_ctx == selector_ctx

    def _panel_context_matches_item(self, context, item):
        if not isinstance(context, dict):
            return False
        item_type = context.get("item_type")
        target_id = str(
            context.get("item_id")
            or context.get("clip_id")
            or context.get("transition_id")
            or ""
        )
        if isinstance(item, Clip):
            item_id = str(getattr(item, "id", ""))
            clip_match = str(context.get("clip_id") or "")
            if item_type == "clip":
                return not target_id or target_id == item_id
            if item_type == "effect":
                return not clip_match or clip_match == item_id
            return False
        if isinstance(item, Transition):
            item_id = str(getattr(item, "id", ""))
            return item_type == "transition" and (not target_id or target_id == item_id)
        return False

    def _panel_context_matches_marker(self, context, context_type, context_id, effect_id=None):
        if not isinstance(context, dict):
            return False
        item_type = context.get("item_type")
        target_id = str(
            context.get("item_id")
            or context.get("clip_id")
            or context.get("transition_id")
            or ""
        )
        if context_type == "transition":
            return item_type == "transition" and (not target_id or target_id == context_id)
        if context_type == "effect":
            effect_ctx = str(context.get("item_id") or context.get("effect_id") or "")
            return item_type == "effect" and (not effect_id or not effect_ctx or effect_ctx == effect_id)
        if item_type not in ("clip", "effect"):
            return False
        return not target_id or target_id == context_id or context.get("clip_id") in (None, context_id)

    def _panel_property_points_parent_path(self, prop):
        if not isinstance(prop, dict):
            return None
        paths = prop.get("point_paths") or []
        for path in paths:
            try:
                tuple_path = tuple(path)
            except TypeError:
                tuple_path = path
            if tuple_path:
                return tuple_path[:-1]
        for point in prop.get("points") or []:
            path = point.get("path")
            if not path:
                continue
            try:
                tuple_path = tuple(path)
            except TypeError:
                tuple_path = path
            if tuple_path:
                return tuple_path[:-1]
        return None

    def _panel_find_points_parent_path(self, data, prop_key, path=()):
        if not prop_key:
            return None
        if isinstance(data, dict):
            if prop_key in data and isinstance(data.get(prop_key), dict):
                prop_dict = data.get(prop_key) or {}
                points = prop_dict.get("Points")
                if isinstance(points, list):
                    return path + (("dict", prop_key), ("dict", "Points"))
                for channel in ("red", "green", "blue", "alpha"):
                    channel_dict = prop_dict.get(channel)
                    if isinstance(channel_dict, dict) and isinstance(channel_dict.get("Points"), list):
                        return path + (
                            ("dict", prop_key),
                            ("dict", channel),
                            ("dict", "Points"),
                        )
            for key_name, value in data.items():
                if isinstance(value, (dict, list)):
                    found = self._panel_find_points_parent_path(
                        value,
                        prop_key,
                        path + (("dict", key_name),),
                    )
                    if found:
                        return found
        elif isinstance(data, list):
            for index, item in enumerate(data):
                if not isinstance(item, (dict, list)):
                    continue
                found = self._panel_find_points_parent_path(
                    item,
                    prop_key,
                    path + (("list", index),),
                )
                if found:
                    return found
        return None

    def _panel_context_under_playhead(self, track_num, prop, fallback_context):
        context = fallback_context if isinstance(fallback_context, dict) else {}
        context_signatures = set()
        if isinstance(prop, dict):
            for point in prop.get("points") or []:
                point_ctx = point.get("_panel_context") if isinstance(point, dict) else None
                if not isinstance(point_ctx, dict):
                    continue
                context_signatures.add(self._panel_context_signature(point_ctx))
        force_multi = len(context_signatures) > 1
        if context.get("item_type") != "multi" and not force_multi:
            return context
        fps = self.fps_float or 1.0
        if fps <= 0.0:
            fps = 1.0
        frame = int(getattr(self, "current_frame", 1) or 1)
        if frame < 1:
            frame = 1
        playhead_seconds = (frame - 1.0) / fps
        epsilon = 1.0 / fps if fps > 0.0 else 1e-6
        selected_items = list(getattr(self.win, "selected_items", []) or [])
        candidates = []
        for selected in selected_items:
            item_id = selected.get("id") if isinstance(selected, dict) else None
            item_type = selected.get("type") if isinstance(selected, dict) else None
            if not item_id or item_type not in ("clip", "effect", "transition"):
                continue
            item_context = self._panel_item_context(item_id, item_type)
            track_value = item_context.get("track") if isinstance(item_context, dict) else None
            track_key = self.normalize_track_number(track_value) if track_value is not None else None
            if track_key != self.normalize_track_number(track_num):
                continue
            range_start = self._panel_float(item_context.get("range_start_seconds"), None)
            range_end = self._panel_float(item_context.get("range_end_seconds"), None)
            if range_start is None or range_end is None:
                continue
            if range_end < range_start:
                range_start, range_end = range_end, range_start
            contains = False
            if abs(range_end - range_start) <= epsilon:
                contains = abs(playhead_seconds - range_start) <= epsilon
            else:
                contains = (playhead_seconds + 1e-9) >= range_start and (playhead_seconds + 1e-9) < (range_end - 1e-9)
            if contains:
                candidates.append((range_start, range_end, item_context))
        if candidates:
            # Prefer the most specific containing item (shortest span), then latest start.
            candidates.sort(key=lambda row: ((row[1] - row[0]), -row[0]))
            return candidates[0][2]
        return {}

    def _panel_parent_path_for_context(self, prop, context):
        parent_path = self._panel_property_points_parent_path(prop)
        if parent_path and context.get("item_type") != "multi":
            return parent_path
        source_key = prop.get("source_key") if isinstance(prop, dict) else None
        if not source_key and isinstance(prop, dict):
            source_key = prop.get("key")
        if not source_key:
            return parent_path
        data = None
        item_type = context.get("item_type") if isinstance(context, dict) else None
        if item_type == "clip":
            clip_id = context.get("clip_id") or context.get("item_id")
            clip_obj = Clip.get(id=clip_id) if clip_id else None
            if clip_obj and isinstance(getattr(clip_obj, "data", None), (dict, list)):
                data = clip_obj.data
        elif item_type == "transition":
            tran_id = context.get("transition_id") or context.get("item_id")
            tran_obj = Transition.get(id=tran_id) if tran_id else None
            if tran_obj and isinstance(getattr(tran_obj, "data", None), (dict, list)):
                data = tran_obj.data
        elif item_type == "effect":
            effect_id = context.get("effect_id") or context.get("item_id")
            effect_obj = Effect.get(id=effect_id) if effect_id else None
            if effect_obj and isinstance(getattr(effect_obj, "data", None), (dict, list)):
                data = effect_obj.data
            if data is None:
                clip_id = context.get("clip_id")
                clip_obj = Clip.get(id=clip_id) if clip_id else None
                if clip_obj and isinstance(getattr(clip_obj, "data", None), (dict, list)):
                    data = clip_obj.data
        found = self._panel_find_points_parent_path(data, source_key) if data is not None else None
        return found or parent_path

    def _panel_capture_base_properties(self, properties):
        base = {}
        for prop in properties or []:
            if not isinstance(prop, dict):
                continue
            if prop.get("placeholder"):
                continue
            key = self._panel_property_key(prop)
            if not key:
                continue
            points = []
            for point in prop.get("points") or []:
                if isinstance(point, dict):
                    points.append(dict(point))
            base[key] = points
        return base

    def _panel_capture_base_context(self, context):
        result = {}
        if not isinstance(context, dict):
            return result
        for key in ("position", "range_start_seconds", "range_end_seconds"):
            if key not in context:
                continue
            value = context.get(key)
            if value is None:
                continue
            try:
                result[key] = float(value)
            except (TypeError, ValueError):
                result[key] = value
        return result

    def _panel_current_signature(self):
        enabled = [
            self.normalize_track_number(track)
            for track, state in self._track_panel_enabled.items()
            if state
        ]
        try:
            enabled_sorted = tuple(sorted(enabled))
        except TypeError:
            enabled_sorted = tuple(enabled)

        selection_signature = []
        win = getattr(self, "win", None)
        if win is not None:
            try:
                selection = list(getattr(win, "selected_items", []) or [])
            except Exception:
                selection = []
            for entry in selection:
                sel_type = None
                sel_id = None
                if isinstance(entry, dict):
                    sel_type = entry.get("type")
                    sel_id = entry.get("id")
                else:
                    sel_type = getattr(entry, "type", None)
                    sel_id = getattr(entry, "id", None)
                    if sel_id is None and hasattr(entry, "get"):
                        try:
                            sel_id = entry.get("id")
                        except Exception:
                            sel_id = None
                selection_signature.append(
                    (
                        str(sel_type) if sel_type is not None else "",
                        str(sel_id) if sel_id is not None else str(entry),
                    )
                )

        return (tuple(selection_signature), enabled_sorted)

    def _panel_lane_padding(self):
        row_height = float(self.keyframe_panel_row_height or 0.0)
        if row_height <= 0.0:
            return 6.0
        return min(6.0, row_height * 0.25)

    def _panel_layout_constants(self):
        padding = float(self.keyframe_panel_padding or 0.0)
        row_height = float(self.keyframe_panel_row_height or 0.0)
        spacing = float(self.keyframe_panel_row_spacing or 0.0)
        lane_padding = self._panel_lane_padding()
        return padding, row_height, spacing, lane_padding

    def _panel_seconds_to_x(self, seconds):
        try:
            seconds_val = float(seconds)
        except (TypeError, ValueError):
            seconds_val = 0.0
        state = self.geometry._current_view_state()
        origin = self.track_name_width - state.get("h_offset", 0.0)
        return origin + seconds_val * float(self.pixels_per_second or 0.0)

    def _panel_x_to_seconds(self, x_value):
        try:
            x_float = float(x_value)
        except (TypeError, ValueError):
            x_float = float(self.track_name_width or 0.0)
        state = self.geometry._current_view_state()
        origin = self.track_name_width - state.get("h_offset", 0.0)
        pixels = float(self.pixels_per_second or 0.0)
        if pixels <= 0.0:
            return 0.0
        return (x_float - origin) / pixels

    def _panel_bounds_for_track(self, track_num):
        key = self.normalize_track_number(track_num)
        self.geometry.ensure()
        for _track_rect, track, name_rect in self.geometry.iter_tracks():
            current = self.normalize_track_number(track.data.get("number"))
            if current != key:
                continue
            panel_rect = self.geometry.panel_rect(current)
            if not panel_rect or panel_rect.height() <= 0.0:
                return QRectF()
            return QRectF(
                name_rect.x(),
                panel_rect.y(),
                name_rect.width() + panel_rect.width(),
                panel_rect.height(),
            )
        return QRectF()

    def _iter_panel_lanes(self):
        padding, row_height, spacing, lane_padding = self._panel_layout_constants()
        if row_height <= 0.0:
            return
        self.geometry.ensure()
        for _track_rect, track, name_rect in self.geometry.iter_tracks():
            track_num = self.normalize_track_number(track.data.get("number"))
            panel_rect = self.geometry.panel_rect(track_num)
            if not panel_rect or panel_rect.height() <= 0.0:
                continue
            properties = self.get_track_panel_properties(track_num)
            if not properties:
                continue
            track_context = self.get_track_panel_context(track_num)
            toggle_rect = self._track_toggle_rect(track, name_rect)
            indent = 0.0
            if not toggle_rect.isNull():
                indent = max(0.0, toggle_rect.x() - name_rect.x())
            y = panel_rect.y() + padding
            for prop in properties:
                context = self._panel_property_context(prop, track_context)
                if y + row_height > panel_rect.bottom() - padding + 1.0:
                    break
                full_lane = QRectF(panel_rect.x(), y, panel_rect.width(), row_height)
                lane_left = max(full_lane.left(), float(self.track_name_width or 0.0))
                right_limit = float(self.width() - self.scroll_bar_thickness)
                lane_right = min(full_lane.right(), right_limit)
                if lane_right < lane_left:
                    lane_right = lane_left
                lane_rect = QRectF(lane_left, y, lane_right - lane_left, row_height)
                label_rect = QRectF(name_rect.x(), y, name_rect.width(), row_height)
                combined_width = label_rect.width() + max(0.0, lane_rect.width())
                combined = QRectF(label_rect.x(), y, combined_width, row_height)
                add_rect = QRectF()
                if isinstance(prop, dict) and not prop.get("placeholder"):
                    add_rect = self._panel_add_icon_rect(label_rect)
                    prop["_panel_add_rect"] = add_rect
                elif isinstance(prop, dict):
                    prop["_panel_add_rect"] = QRectF()
                yield {
                    "track": track_num,
                    "property": prop,
                    "lane_rect": lane_rect,
                    "full_lane_rect": full_lane,
                    "label_rect": label_rect,
                    "combined_rect": combined,
                    "context": context,
                    "lane_padding": lane_padding,
                    "indent": indent,
                    "render_rect": lane_rect,
                    "add_rect": add_rect,
                }
                y += row_height + spacing

    def _panel_lane_at(self, pos, include_label=True):
        for lane in self._iter_panel_lanes() or []:
            rect = lane["combined_rect"] if include_label else lane["lane_rect"]
            if rect.contains(pos):
                return lane
        return None

    def _panel_marker_rect(self, lane_rect, lane_padding, seconds):
        size = max(2.0, float(getattr(self.keyframe_panel_painter, "marker_size", 8.0) or 8.0))
        baseline = lane_rect.center().y()
        if lane_rect.height() > 0.0:
            baseline = max(
                lane_rect.top() + lane_padding,
                min(lane_rect.bottom() - lane_padding, baseline),
            )
        x_pos = self._panel_seconds_to_x(seconds)
        x_pos = max(lane_rect.left(), min(lane_rect.right(), x_pos))
        half = size / 2.0
        return QRectF(x_pos - half, baseline - half, size, size)

    def _panel_add_icon_rect(self, label_rect):
        painter = getattr(self, "keyframe_panel_painter", None)
        if not painter or not getattr(painter, "add_pix", None) or label_rect.isNull():
            return QRectF()
        pix = painter.add_pix
        pix_w, pix_h = painter.logical_size(pix)
        if pix_w <= 0.0 or pix_h <= 0.0:
            return QRectF()
        try:
            margin = float(getattr(painter, "add_margin", painter.label_margin))
        except (TypeError, ValueError):
            margin = float(painter.label_margin)
        if not math.isfinite(margin):
            margin = 0.0
        margin = max(0.0, margin)
        width = float(pix_w)
        height = float(pix_h)
        x = label_rect.right() - margin - width
        if x < label_rect.left():
            x = label_rect.left()
        y = label_rect.center().y() - height / 2.0
        if y < label_rect.top():
            y = label_rect.top()
        if y + height > label_rect.bottom():
            y = label_rect.bottom() - height
        return QRectF(x, y, width, height)

    def _panel_marker_at(self, pos):
        lane = self._panel_lane_at(pos, include_label=False)
        if not lane:
            return None
        prop = lane.get("property")
        lane_rect = lane.get("render_rect", lane.get("lane_rect", QRectF()))
        lane_padding = lane.get("lane_padding", self._panel_lane_padding())
        candidates = []
        for point in prop.get("points") or []:
            seconds = point.get("seconds")
            if seconds is None:
                continue
            marker_rect = self._panel_marker_rect(lane_rect, lane_padding, seconds)
            info = dict(lane)
            info["point"] = point
            info["marker_rect"] = marker_rect
            point_context = point.get("_panel_context") if isinstance(point, dict) else None
            if isinstance(point_context, dict):
                info["context"] = point_context
            candidates.append((marker_rect, info))
        return keyframe_hit_at(pos, candidates)

    def _panel_add_button_at(self, pos):
        for lane in self._iter_panel_lanes() or []:
            add_rect = lane.get("add_rect")
            if isinstance(add_rect, QRectF) and not add_rect.isNull() and add_rect.contains(pos):
                info = dict(lane)
                info["add_rect"] = add_rect
                return info
        return None

    def _panel_compute_snap_targets(self, track_num, property_entry, entries, context):
        targets = []
        seen = set()
        current_context = self._panel_property_context(property_entry, context)
        current_signature = self._panel_context_signature(current_context)
        entry_signatures = {
            self._panel_context_signature(entry.get("context"))
            for entry in (entries or [])
            if isinstance(entry, dict)
        }
        if entry_signatures:
            current_signature = next(iter(entry_signatures))

        def _same_owner(prop):
            prop_context = self._panel_property_context(prop, context)
            return self._panel_context_signature(prop_context) == current_signature

        def _point_same_owner(prop, point):
            point_ctx = point.get("_panel_context") if isinstance(point, dict) else None
            if isinstance(point_ctx, dict):
                return self._panel_context_signature(point_ctx) == current_signature
            return _same_owner(prop)

        # Collect dragged entries' original positions (seconds) to exclude
        # from non-keyframe snap sources (markers, snap_helper) that would
        # otherwise create a dead zone at the drag origin.
        dragged_positions = set()
        for entry in entries or []:
            orig = entry.get("original_seconds")
            if orig is not None:
                dragged_positions.add(round(float(orig), 6))

        # Collect dragged frames by property key so selected points across
        # multiple properties are excluded from snap targets.
        selected_frames_by_prop = {}
        dragged_paths = set()
        for entry in entries or []:
            prop_key = entry.get("prop_key")
            frame_val = entry.get("original_frame")
            if not prop_key or frame_val is None:
                continue
            try:
                frame_int = int(frame_val)
            except (TypeError, ValueError):
                continue
            selected_frames_by_prop.setdefault(prop_key, set()).add(frame_int)
            path = entry.get("path")
            if path:
                try:
                    dragged_paths.add(tuple(path))
                except TypeError:
                    pass

        property_key = property_entry.get("key") if isinstance(property_entry, dict) else None
        selected_frames = selected_frames_by_prop.get(property_key, set())

        # Keep origin-position snapping only when an unselected point exists at
        # that same time.
        unselected_positions = set()
        # Track panel property points first.
        for prop in self.get_track_panel_properties(track_num) or []:
            prop_key = prop.get("key") if isinstance(prop, dict) else None
            selected_prop_frames = selected_frames_by_prop.get(prop_key, set())
            for point in prop.get("points") or []:
                if not _point_same_owner(prop, point):
                    continue
                frame_val = point.get("frame")
                try:
                    frame_int = int(frame_val) if frame_val is not None else None
                except (TypeError, ValueError):
                    frame_int = None
                if frame_int is not None and frame_int in selected_prop_frames:
                    continue
                seconds_val = point.get("seconds")
                try:
                    unselected_positions.add(round(float(seconds_val), 6))
                except (TypeError, ValueError):
                    continue

        # Also include unselected keyframe markers for the same owner. Because
        # clip markers are merged by frame, inspect marker paths to detect mixed
        # selected/unselected keyframes at a dragged origin frame.
        anchor_point = None
        if entries and isinstance(entries[0], dict):
            anchor_point = entries[0].get("point")
        owner = self._panel_resolve_owner(property_entry, current_context, point=anchor_point)
        drag_scope = {
            "owner_type": owner.get("owner_type", "clip"),
            "object_id": owner.get("object_id", ""),
            "clip": owner.get("clip"),
            "transition": owner.get("transition"),
            "entries": entries,
        }
        self._ensure_keyframe_markers()
        markers = list(getattr(self, "_keyframe_markers", []) or [])
        selected_marker_ids = set()
        for entry in entries or []:
            marker = self._find_panel_drag_marker(markers, drag_scope, entry)
            if marker is not None:
                selected_marker_ids.add(id(marker))
        for marker in markers:
            if not self._panel_drag_owner_matches_marker(drag_scope, marker):
                continue
            if id(marker) in selected_marker_ids:
                marker_paths = self._marker_paths_tuples(marker)
                if marker_paths and any(path not in dragged_paths for path in marker_paths):
                    absolute = self._marker_absolute_seconds(marker)
                    if absolute is not None:
                        unselected_positions.add(round(float(absolute), 6))
                continue
            absolute = self._marker_absolute_seconds(marker)
            if absolute is not None:
                unselected_positions.add(round(float(absolute), 6))

        def add_target(value, tolerance=None):
            try:
                seconds_val = float(value)
            except (TypeError, ValueError):
                return
            if seconds_val < 0.0:
                seconds_val = 0.0
            key = round(seconds_val, 6)
            tol_val = None
            if tolerance is not None:
                try:
                    tol_val = float(tolerance)
                except (TypeError, ValueError):
                    tol_val = None
            seen_key = (key, tol_val if tol_val is not None else 0.0)
            if seen_key in seen:
                return
            seen.add(seen_key)
            if tol_val is not None and tol_val > 0.0:
                targets.append({"seconds": seconds_val, "tolerance": tol_val})
            else:
                targets.append(seconds_val)

        def _is_excluded_dragged_position(value):
            try:
                key = round(float(value), 6)
            except (TypeError, ValueError):
                return False
            if key not in dragged_positions:
                return False
            # Allow snapping back to drag origin when there is at least one
            # unselected keyframe at this position.
            return key not in unselected_positions

        # Same-property points: exclude dragged frames
        for point in property_entry.get("points") or []:
            frame_val = point.get("frame")
            try:
                frame_int = int(frame_val)
            except (TypeError, ValueError):
                frame_int = None
            if frame_int is not None and frame_int in selected_frames:
                continue
            seconds = point.get("seconds")
            if seconds is None:
                continue
            add_target(seconds)

        for other_prop in self.get_track_panel_properties(track_num) or []:
            if other_prop is property_entry:
                continue
            other_key = other_prop.get("key") if isinstance(other_prop, dict) else None
            selected_other_frames = selected_frames_by_prop.get(other_key, set())
            for point in other_prop.get("points") or []:
                if not _point_same_owner(other_prop, point):
                    continue
                frame_val = point.get("frame")
                try:
                    frame_int = int(frame_val) if frame_val is not None else None
                except (TypeError, ValueError):
                    frame_int = None
                if frame_int is not None and frame_int in selected_other_frames:
                    continue
                seconds = point.get("seconds")
                if seconds is None:
                    continue
                add_target(seconds)

        # Context range boundaries: always valid
        if isinstance(context, dict):
            range_start = context.get("range_start_seconds")
            range_end = context.get("range_end_seconds")
            if range_start is not None:
                add_target(range_start)
            if range_end is not None:
                add_target(range_end)

        # Markers: exclude those at the drag origin
        for marker in markers:
            absolute = self._marker_absolute_seconds(marker)
            if absolute is None:
                continue
            if _is_excluded_dragged_position(absolute):
                continue
            add_target(absolute)

        # Snap helper: exclude those at the drag origin
        snap_helper = getattr(self, "snap", None)
        if snap_helper and hasattr(snap_helper, "keyframe_snap_seconds"):
            for entry in snap_helper.keyframe_snap_seconds(include_playhead=False):
                if isinstance(entry, dict):
                    sec = entry.get("seconds")
                    if _is_excluded_dragged_position(sec):
                        continue
                    add_target(sec, entry.get("tolerance"))
                else:
                    if _is_excluded_dragged_position(entry):
                        continue
                    add_target(entry)

        return targets

    def _panel_snap_seconds(self, drag, seconds):
        targets = drag.get("snap_targets") or []
        return self._snap_absolute_seconds_to_targets(seconds, targets)

    def _panel_write_point_value(
        self,
        data,
        *,
        parent_path,
        frame,
        value,
        existing_path=None,
        interpolation=1,
    ):
        if existing_path:
            target = self._resolve_data_path(data, existing_path)
            if not isinstance(target, dict):
                return False
            co = target.get("co")
            if not isinstance(co, dict):
                return False
            co["Y"] = value
            if frame is not None:
                co["X"] = frame
            if interpolation is not None:
                target["interpolation"] = interpolation
            return True
        target_list = self._resolve_data_path(data, parent_path)
        if not isinstance(target_list, list):
            return False
        new_point = {"co": {"X": frame, "Y": value}}
        if interpolation is not None:
            new_point["interpolation"] = interpolation
        target_list.append(new_point)
        try:
            target_list.sort(key=lambda entry: entry.get("co", {}).get("X", frame))
        except Exception:
            pass
        return True

    def _panel_update_property_points(self, drag, *, resort=True):
        entries = drag.get("entries") or []
        if not entries:
            return
        context = drag.get("context") or {}
        grouped = {}
        for entry in entries:
            prop = entry.get("property")
            prop_key = entry.get("prop_key")
            if not isinstance(prop, dict) or not prop_key:
                continue
            grouped.setdefault(prop_key, {"property": prop, "entries": []})["entries"].append(entry)
        if not grouped:
            return

        track = drag.get("track")
        track_map = {}
        if track is not None:
            track_map = dict(self._panel_selected_keyframes.get(track, {}) or {})

        for prop_key, bundle in grouped.items():
            prop = bundle.get("property")
            if not isinstance(prop, dict):
                continue
            for entry in bundle.get("entries", []):
                point = entry.get("point")
                if not isinstance(point, dict):
                    continue
                pending_frame = entry.get("pending_frame", entry.get("original_frame"))
                pending_seconds = entry.get("pending_seconds", entry.get("original_seconds"))
                if pending_frame is not None:
                    try:
                        point["frame"] = int(pending_frame)
                    except (TypeError, ValueError):
                        point["frame"] = pending_frame
                if pending_seconds is not None:
                    point["seconds"] = pending_seconds
                    entry_context = entry.get("context")
                    if not isinstance(entry_context, dict):
                        entry_context = context
                    try:
                        position = float(entry_context.get("position", 0.0) or 0.0)
                    except (TypeError, ValueError):
                        position = 0.0
                    try:
                        point["local_seconds"] = float(pending_seconds) - position
                    except (TypeError, ValueError):
                        pass
            if resort:
                try:
                    prop_points = prop.get("points") or []
                    prop_points.sort(key=lambda pt: pt.get("seconds", 0.0))
                except Exception:
                    pass
            if track is not None:
                new_frames = {
                    int(entry.get("pending_frame"))
                    for entry in bundle.get("entries", [])
                    if entry.get("pending_frame") is not None
                }
                if new_frames:
                    context_signature = None
                    for entry in bundle.get("entries", []):
                        entry_context = entry.get("context")
                        if isinstance(entry_context, dict):
                            context_signature = self._panel_context_signature(entry_context)
                            break
                    selector = self._panel_selection_selector(
                        new_frames,
                        context_signature=context_signature,
                    )
                    if selector:
                        track_map[prop_key] = selector
                elif prop_key in track_map:
                    track_map.pop(prop_key, None)

        if track is not None:
            self._panel_selected_keyframes[track] = track_map
            self._apply_panel_selection_flags(track)

    def _panel_begin_transaction(self, drag):
        if drag.get("transaction_started"):
            return
        timeline = getattr(self.win, "timeline", None)
        if not timeline:
            return
        tid = str(uuid.uuid4())
        drag["transaction_started"] = True
        drag["transaction_id"] = tid
        object_type = drag.get("owner_type", "clip") or "clip"
        object_id = drag.get("object_id", "") or ""
        timeline.StartKeyframeDrag(object_type, object_id, tid)

    def _move_colorgrade_frames_in_data(self, data, prop_key, old_frame, new_frame, prop_type):
        """Move all sub-keyframes at old_frame → new_frame inside a colorgrade property.

        Recursively searches data for any dict containing prop_key and moves every
        nested Points entry whose co.X == old_frame to new_frame.  Returns True if
        anything changed.
        """
        moved = False

        def _move_in_kf(kf_data):
            nonlocal moved
            if not isinstance(kf_data, dict):
                return
            for pt in kf_data.get("Points", []):
                try:
                    if int(round(float(pt["co"]["X"]))) == old_frame:
                        pt["co"]["X"] = float(new_frame)
                        moved = True
                except (KeyError, TypeError, ValueError):
                    pass

        def _move_in_colorgrade(cg_data):
            if not isinstance(cg_data, dict):
                return
            if prop_type == "colorgrade_curve":
                _move_in_kf(cg_data.get("enabled"))
                for node in cg_data.get("nodes", []):
                    for k in ("x", "y", "left_handle_x", "left_handle_y", "right_handle_x", "right_handle_y"):
                        _move_in_kf(node.get(k))
            elif prop_type == "colorgrade_wheels":
                _move_in_kf(cg_data.get("enabled_keyframes"))
                for section in ("global", "shadows", "midtones", "highlights"):
                    wheel = cg_data.get(section, {})
                    color_kf = wheel.get("color_keyframes") or {}
                    for channel in ("red", "green", "blue", "alpha"):
                        _move_in_kf(color_kf.get(channel))
                    _move_in_kf(wheel.get("amount_keyframes"))
                    _move_in_kf(wheel.get("luma_keyframes"))

        def _search(obj):
            if isinstance(obj, dict):
                candidate = obj.get(prop_key)
                if isinstance(candidate, dict):
                    _move_in_colorgrade(candidate)
                for value in obj.values():
                    _search(value)
            elif isinstance(obj, list):
                for item in obj:
                    _search(item)

        _search(data)
        return moved

    def _apply_panel_keyframe_delta(self, drag, *, ignore_refresh=False, force=False):
        entries = drag.get("entries") or []
        if not entries:
            return
        timeline = getattr(self.win, "timeline", None)
        if not timeline:
            return
        owner_type = drag.get("owner_type", "clip") or "clip"
        clip_obj = drag.get("clip")
        transition_obj = drag.get("transition")
        transaction_id = drag.get("transaction_id")
        moved = False
        context = drag.get("context") or {}
        base_position = drag.get("base_position")
        if base_position is None and isinstance(context, dict):
            base_position = context.get("position")
        try:
            base_position = float(base_position)
        except (TypeError, ValueError):
            base_position = 0.0
        clip_start = 0.0
        if isinstance(context, dict):
            clip_start = context.get("clip_start")
        try:
            clip_start = float(clip_start)
        except (TypeError, ValueError):
            clip_start = 0.0
        if owner_type == "transition" and transition_obj:
            data_copy = json.loads(json.dumps(transition_obj.data))
            fps = drag.get("fps") or self.fps_float or 1.0
            for entry in entries:
                new_seconds = entry.get("pending_seconds")
                if fps and fps > 0.0 and new_seconds is not None:
                    try:
                        new_seconds = float(new_seconds)
                    except (TypeError, ValueError):
                        new_seconds = None
                if fps and fps > 0.0 and new_seconds is not None:
                    new_local = new_seconds - base_position
                    frame_seconds = new_local + clip_start
                    new_frame = int(round(frame_seconds * fps)) + 1
                else:
                    new_frame = entry.get("pending_frame")
                old_frame = entry.get("original_frame")
                path = entry.get("path")
                if new_frame is None or old_frame is None or not path:
                    continue
                if self._set_keyframe_frame_at_path(data_copy, path, new_frame):
                    moved = moved or (new_frame != old_frame or force)
                    if isinstance(transition_obj.data, (dict, list)) and (new_frame != old_frame or force):
                        self._set_keyframe_frame_at_path(transition_obj.data, path, new_frame)
            if moved or force:
                timeline.update_transition_data(
                    data_copy,
                    only_basic_props=False,
                    ignore_refresh=ignore_refresh,
                    transaction_id=transaction_id,
                )
        elif clip_obj:
            data_copy = json.loads(json.dumps(clip_obj.data))
            fps = drag.get("fps") or self.fps_float or 1.0
            for entry in entries:
                new_seconds = entry.get("pending_seconds")
                if fps and fps > 0.0 and new_seconds is not None:
                    try:
                        new_seconds = float(new_seconds)
                    except (TypeError, ValueError):
                        new_seconds = None
                if fps and fps > 0.0 and new_seconds is not None:
                    new_local = new_seconds - base_position
                    frame_seconds = new_local + clip_start
                    new_frame = int(round(frame_seconds * fps)) + 1
                else:
                    new_frame = entry.get("pending_frame")
                old_frame = entry.get("original_frame")
                path = entry.get("path")

                # Colorgrade types store nested keyframe structures with no single
                # path; move all sub-keyframes at old_frame to new_frame instead.
                value_type = (entry.get("property") or {}).get("value_type") or ""
                prop_key_entry = entry.get("prop_key") or ""
                if value_type in ("colorgrade_curve", "colorgrade_wheels") and prop_key_entry:
                    if new_frame is None or old_frame is None:
                        continue
                    if self._move_colorgrade_frames_in_data(data_copy, prop_key_entry, old_frame, new_frame, value_type):
                        moved = moved or (new_frame != old_frame or force)
                        if isinstance(clip_obj.data, (dict, list)):
                            self._move_colorgrade_frames_in_data(clip_obj.data, prop_key_entry, old_frame, new_frame, value_type)
                    continue

                if new_frame is None or old_frame is None or not path:
                    continue
                if self._set_keyframe_frame_at_path(data_copy, path, new_frame):
                    moved = moved or (new_frame != old_frame or force)
                    if isinstance(clip_obj.data, (dict, list)) and (new_frame != old_frame or force):
                        self._set_keyframe_frame_at_path(clip_obj.data, path, new_frame)
            if moved or force:
                timeline.update_clip_data(
                    data_copy,
                    only_basic_props=False,
                    ignore_reader=True,
                    ignore_refresh=ignore_refresh,
                    transaction_id=transaction_id,
                )

    def _panel_resolve_owner(self, prop, context, point=None):
        if isinstance(point, dict):
            point_context = point.get("_panel_context")
            if isinstance(point_context, dict):
                context = point_context
        context = self._panel_property_context(prop, context)
        source_meta = {}
        if isinstance(point, dict):
            point_meta = point.get("_panel_source_meta")
            if isinstance(point_meta, dict):
                source_meta = dict(point_meta)
        if not source_meta:
            source_meta = prop.get("source_meta") if isinstance(prop, dict) else {}
        if not isinstance(source_meta, dict):
            source_meta = {}
        owner_hint = source_meta.get("owner")
        clip_obj = source_meta.get("clip")
        transition_obj = source_meta.get("transition")
        effect_obj = source_meta.get("effect")
        if isinstance(context, dict):
            ctx_item_type = context.get("item_type")
            ctx_clip_id = str(context.get("clip_id") or "")
            ctx_item_id = str(context.get("item_id") or "")
            ctx_transition_id = str(context.get("transition_id") or "")
            ctx_effect_id = str(context.get("effect_id") or "")

            if ctx_item_type == "clip":
                ctx_target = ctx_clip_id or ctx_item_id
                if ctx_target:
                    if clip_obj is not None and str(getattr(clip_obj, "id", "")) != ctx_target:
                        clip_obj = None
                    transition_obj = None
                    effect_obj = None
            elif ctx_item_type == "transition":
                ctx_target = ctx_transition_id or ctx_item_id
                if ctx_target:
                    if transition_obj is not None and str(getattr(transition_obj, "id", "")) != ctx_target:
                        transition_obj = None
                    clip_obj = None
                    effect_obj = None
            elif ctx_item_type == "effect":
                ctx_target = ctx_effect_id or ctx_item_id
                if ctx_target:
                    if effect_obj is not None and str(getattr(effect_obj, "id", "")) != ctx_target:
                        effect_obj = None
                if ctx_clip_id and clip_obj is not None and str(getattr(clip_obj, "id", "")) != ctx_clip_id:
                    clip_obj = None
        if not clip_obj and isinstance(context, dict):
            clip_id_ctx = context.get("clip_id")
            if clip_id_ctx:
                try:
                    clip_obj = Clip.get(id=clip_id_ctx)
                except Exception:
                    pass
        if not transition_obj and isinstance(context, dict) and context.get("item_type") == "transition":
            tran_id_ctx = context.get("transition_id") or context.get("item_id")
            if tran_id_ctx:
                try:
                    transition_obj = Transition.get(id=tran_id_ctx)
                except Exception:
                    pass
        if not effect_obj and isinstance(context, dict) and context.get("item_type") == "effect":
            effect_id_ctx = context.get("effect_id") or context.get("item_id")
            if effect_id_ctx:
                try:
                    effect_obj = Effect.get(id=effect_id_ctx)
                except Exception:
                    pass
        owner_type = "transition" if transition_obj else "clip"
        if owner_hint == "transition" and transition_obj is None and clip_obj is None:
            owner_type = "transition"
        object_id = ""
        if owner_type == "transition" and transition_obj:
            object_id = str(getattr(transition_obj, "id", context.get("item_id") or ""))
        elif clip_obj:
            object_id = str(getattr(clip_obj, "id", context.get("clip_id") or context.get("item_id") or ""))
        elif isinstance(context, dict):
            object_id = str(context.get("item_id") or context.get("clip_id") or "")
        return {
            "source_meta": source_meta,
            "clip": clip_obj,
            "transition": transition_obj,
            "effect": effect_obj,
            "owner_type": owner_type,
            "object_id": object_id,
        }

    def _start_panel_keyframe_drag(self, info):
        if not isinstance(info, dict):
            self._panel_press_info = None
            self._dragging_panel_keyframes = None
            return
        point = info.get("point")
        prop = info.get("property")
        track_num = info.get("track")
        if not isinstance(prop, dict) or track_num is None or not isinstance(point, dict):
            self._panel_press_info = None
            self._dragging_panel_keyframes = None
            return
        frame_val = point.get("frame")
        try:
            frame_int = int(frame_val)
        except (TypeError, ValueError):
            frame_int = None
        if frame_int is None:
            self._panel_press_info = None
            self._dragging_panel_keyframes = None
            return
        track_key = self.normalize_track_number(track_num)
        prop_key = prop.get("key")
        if not prop_key:
            self._panel_press_info = None
            self._dragging_panel_keyframes = None
            return
        lane_rect = info.get("render_rect", info.get("lane_rect", QRectF()))
        if not isinstance(lane_rect, QRectF):
            lane_rect = QRectF(lane_rect)
        if lane_rect.isNull():
            lane_rect = QRectF(info.get("lane_rect", QRectF()))
        lane_padding = info.get("lane_padding", self._panel_lane_padding())
        context = info.get("context") or self.get_track_panel_context(track_key)
        anchor_context = point.get("_panel_context") if isinstance(point, dict) else None
        if not isinstance(anchor_context, dict):
            anchor_context = self._panel_property_context(prop, context)
        context = anchor_context
        anchor_signature = self._panel_context_signature(anchor_context)

        selection_map = self._panel_selected_keyframes.get(track_key, {}) or {}
        selector = selection_map.get(prop_key, set())
        selected_frames = self._panel_selection_frames(selector)
        selector_context = self._panel_selection_context(selector)
        if selector_context and selector_context != anchor_signature:
            selected_frames = set()
        modifiers = info.get("modifiers", Qt.NoModifier)
        ctrl_down = bool(modifiers & Qt.ControlModifier)
        if frame_int not in selected_frames:
            if ctrl_down:
                self._panel_merge_selection_map(
                    track_key,
                    {
                        prop_key: self._panel_selection_selector(
                            {frame_int},
                            context_signature=anchor_signature,
                        )
                    },
                )
                selected_frames.add(frame_int)
            else:
                selected_frames = {frame_int}
                self._panel_set_selection_map(
                    track_key,
                    {
                        prop_key: self._panel_selection_selector(
                            {frame_int},
                            context_signature=anchor_signature,
                        )
                    },
                )

        lane_lookup = {}
        for lane in self._iter_panel_lanes() or []:
            if lane.get("track") != track_key:
                continue
            lane_prop = lane.get("property")
            key = lane_prop.get("key") if isinstance(lane_prop, dict) else None
            if key:
                lane_lookup[key] = lane

        track_map = self._panel_selected_keyframes.get(track_key, {}) or {}
        move_sets = {}
        for key, selector in (track_map.items() if track_map else []):
            selector_context = self._panel_selection_context(selector)
            if selector_context and selector_context != anchor_signature:
                continue
            frames_set = self._panel_selection_frames(selector)
            if frames_set:
                move_sets[key] = frames_set
        if not move_sets:
            move_sets[prop_key] = selected_frames or {frame_int}

        properties = {}
        entries = []
        anchor_entry = None
        for key, frames in move_sets.items():
            lane = lane_lookup.get(key)
            prop_obj = None
            if lane:
                prop_obj = lane.get("property")
            if prop_obj is None and key == prop_key:
                prop_obj = prop
            if not isinstance(prop_obj, dict):
                continue
            properties[key] = prop_obj
            for candidate in prop_obj.get("points") or []:
                frame_val = candidate.get("frame")
                try:
                    candidate_frame = int(frame_val) if frame_val is not None else None
                except (TypeError, ValueError):
                    candidate_frame = None
                if candidate_frame is None or candidate_frame not in frames:
                    continue
                seconds_val = candidate.get("seconds")
                try:
                    seconds_float = float(seconds_val) if seconds_val is not None else None
                except (TypeError, ValueError):
                    seconds_float = None
                entry = {
                    "point": candidate,
                    "original_frame": candidate_frame,
                    "pending_frame": candidate_frame,
                    "original_seconds": seconds_float,
                    "pending_seconds": seconds_float,
                    "path": tuple(candidate.get("path")) if candidate.get("path") else None,
                    "property": prop_obj,
                    "prop_key": key,
                    "context": candidate.get("_panel_context") if isinstance(candidate, dict) else None,
                    "source_meta": candidate.get("_panel_source_meta") if isinstance(candidate, dict) else None,
                }
                entry_signature = self._panel_context_signature(entry.get("context") or anchor_context)
                if entry_signature != anchor_signature:
                    continue
                entries.append(entry)
                if key == prop_key and candidate_frame == frame_int and anchor_entry is None:
                    anchor_entry = entry
        if not entries:
            self._panel_press_info = None
            self._dragging_panel_keyframes = None
            return

        if anchor_entry is None:
            anchor_entry = entries[0]

        owner_info = self._panel_resolve_owner(prop, context, point=anchor_entry.get("point") if anchor_entry else point)
        source_meta = owner_info.get("source_meta") or {}
        clip_obj = owner_info.get("clip")
        transition_obj = owner_info.get("transition")
        effect_obj = owner_info.get("effect")
        owner_type = owner_info.get("owner_type", "clip")
        object_id = owner_info.get("object_id", "")

        range_start = context.get("range_start_seconds") if isinstance(context, dict) else None
        range_end = context.get("range_end_seconds") if isinstance(context, dict) else None
        base_position = context.get("position") if isinstance(context, dict) else 0.0
        try:
            base_position = float(base_position or 0.0)
        except (TypeError, ValueError):
            base_position = 0.0

        drag_info = {
            "track": track_key,
            "prop_key": prop_key,
            "property": prop,
            "entries": entries,
            "properties": properties,
            "context": context,
            "lane_rect": lane_rect,
            "lane_padding": lane_padding,
            "fps": self.fps_float or 1.0,
            "source_meta": source_meta,
            "clip": clip_obj,
            "transition": transition_obj,
            "effect": effect_obj,
            "owner_type": owner_type,
            "object_id": object_id,
            "transaction_started": False,
            "transaction_id": None,
            "moved": False,
            "range_start": range_start,
            "range_end": range_end,
            "base_position": base_position,
            "snap_targets": tuple(self._panel_compute_snap_targets(track_key, prop, entries, context)),
            "anchor": anchor_entry,
        }

        self._dragging_panel_keyframes = drag_info
        info_copy = dict(info)
        info_copy["dragged"] = False
        info_copy["lane_rect"] = lane_rect
        info_copy["lane_padding"] = lane_padding
        info_copy["context"] = context
        info_copy["modifiers"] = modifiers
        self._panel_press_info = info_copy
        self.mouse_dragging = True
        self._fix_cursor(self.cursors.get("resize_x", Qt.SizeHorCursor))

    def _panel_keyframe_move(self, event):
        drag = self._dragging_panel_keyframes
        if not drag:
            return
        lane_rect = drag.get("lane_rect", QRectF())
        if lane_rect.isNull():
            lane_rect = drag.get("render_rect", QRectF())
        if lane_rect.isNull():
            return
        x_pos = event.pos().x()
        x_pos = max(lane_rect.left(), min(lane_rect.right(), x_pos))
        seconds = self._panel_x_to_seconds(x_pos)
        range_start = drag.get("range_start")
        range_end = drag.get("range_end")
        if range_start is not None and seconds < range_start:
            seconds = range_start
        if range_end is not None and seconds > range_end:
            seconds = range_end
        seconds = self._panel_snap_seconds(drag, seconds)

        entries = drag.get("entries") or []
        if not entries:
            return
        anchor = drag.get("anchor") or entries[0]
        anchor_seconds = anchor.get("original_seconds")
        if anchor_seconds is None:
            anchor_seconds = seconds
        delta = seconds - anchor_seconds

        valid_seconds = [
            entry.get("original_seconds")
            for entry in entries
            if entry.get("original_seconds") is not None
        ]
        if range_start is not None and valid_seconds:
            min_initial = min(valid_seconds)
            min_delta = range_start - min_initial
            if delta < min_delta:
                delta = min_delta
        if range_end is not None and valid_seconds:
            max_initial = max(valid_seconds)
            max_delta = range_end - max_initial
            if delta > max_delta:
                delta = max_delta

        fps = drag.get("fps") or self.fps_float or 1.0
        context = drag.get("context") or {}
        base_position = drag.get("base_position")
        if base_position is None and isinstance(context, dict):
            base_position = context.get("position")
        try:
            base_position = float(base_position)
        except (TypeError, ValueError):
            base_position = 0.0
        clip_start = 0.0
        if isinstance(context, dict):
            clip_start = context.get("clip_start")
        try:
            clip_start = float(clip_start)
        except (TypeError, ValueError):
            clip_start = 0.0
        changed = False
        for entry in entries:
            orig_seconds = entry.get("original_seconds")
            if orig_seconds is None:
                continue
            new_abs = orig_seconds + delta
            prev_seconds = entry.get("pending_seconds")
            prev_frame = entry.get("pending_frame")
            if fps > 0.0:
                new_local = new_abs - base_position
                frame_seconds = new_local + clip_start
                new_frame = int(round(frame_seconds * fps)) + 1
                # Keep panel drag positions locked to exact frame boundaries,
                # matching clip keyframe-icon dragging behavior.
                new_abs = ((new_frame - 1.0) / fps) - clip_start + base_position
            else:
                new_frame = entry.get("original_frame")
            if new_frame != prev_frame or prev_seconds is None or not math.isclose(new_abs, prev_seconds, rel_tol=1e-6, abs_tol=1e-9):
                changed = True
            entry["pending_seconds"] = new_abs
            entry["pending_frame"] = new_frame
        if not changed and drag.get("moved"):
            return
        if not changed and not drag.get("moved"):
            return

        drag["moved"] = True
        info = dict(self._panel_press_info or {})
        info["dragged"] = True
        self._panel_press_info = info

        anchor_pending = anchor.get("pending_seconds")
        if anchor_pending is None:
            anchor_pending = anchor.get("original_seconds")

        self._panel_update_property_points(drag)
        # Rebuild clip keyframe markers every drag tick so old pre-snap
        # marker frames are not left in the cached marker list.
        self._keyframes_dirty = True

        fps_seek = drag.get("fps") or self.fps_float or 1.0
        if anchor_pending is not None and fps_seek and fps_seek > 0.0 and hasattr(self, "win"):
            frame_seek = int(round(anchor_pending * fps_seek)) + 1
            frame_seek = max(1, frame_seek)
            if hasattr(self.win, "SeekSignal"):
                self.win.SeekSignal.emit(frame_seek, False)
        self.update()

    def _panel_seek_to_point(self, info, point):
        if not isinstance(point, dict) or not hasattr(self, "win"):
            return

        context = info.get("context") if isinstance(info, dict) else None
        if not isinstance(context, dict):
            context = {}
        point_context = point.get("_panel_context") if isinstance(point, dict) else None
        if isinstance(point_context, dict):
            context = point_context

        fps = self._panel_float(context.get("fps"), None)
        if fps is None or fps <= 0.0:
            fps = self._panel_float(getattr(self, "fps_float", None), 0.0)
        if fps <= 0.0:
            return

        seconds = self._panel_float(point.get("seconds"), None)
        if seconds is None:
            local_seconds = self._panel_float(point.get("local_seconds"), None)
            if local_seconds is not None:
                seconds = self._panel_float(context.get("position"), 0.0) + local_seconds

        if seconds is None:
            frame_val = self._panel_float(point.get("frame"), None)
            if frame_val is not None:
                clip_start = self._panel_float(context.get("clip_start"), 0.0)
                position = self._panel_float(context.get("position"), 0.0)
                seconds = ((frame_val - 1.0) / fps) - clip_start + position

        if seconds is None or not math.isfinite(seconds):
            return

        frame_seek = int(round(seconds * fps)) + 1
        if frame_seek < 1:
            frame_seek = 1

        timeline = getattr(self.win, "timeline", None)
        if timeline and hasattr(timeline, "SeekToKeyframe"):
            timeline.SeekToKeyframe(frame_seek)
            return

        if hasattr(self.win, "SeekSignal"):
            self.win.SeekSignal.emit(frame_seek, True)

    def _finish_panel_keyframe_drag(self):
        drag = self._dragging_panel_keyframes
        if not drag:
            return
        timeline = getattr(self.win, "timeline", None)
        started = drag.get("transaction_started")
        moved = drag.get("moved")
        if moved:
            self._panel_begin_transaction(drag)
            started = drag.get("transaction_started")
        if started:
            self._apply_panel_keyframe_delta(drag, ignore_refresh=False, force=True)
            if timeline:
                timeline.FinalizeKeyframeDrag(
                    drag.get("owner_type", "clip") or "clip",
                    drag.get("object_id", "") or "",
                )
            if hasattr(self.win, "show_property_timeout"):
                QTimer.singleShot(0, self.win.show_property_timeout)
            anchor = (drag.get("anchor") or ((drag.get("entries") or [None])[0])) or {}
            # pending_frame is source-relative; pending_seconds is the absolute
            # timeline position used while dragging, including trim and offset.
            seconds = anchor.get("pending_seconds")
            fps = drag.get("fps") or self.fps_float or 1.0
            if seconds is not None and hasattr(self, "win") and hasattr(self.win, "SeekSignal"):
                frame_seek = int(round(seconds * fps)) + 1
                self.win.SeekSignal.emit(max(1, frame_seek), True)
        self._dragging_panel_keyframes = None
        self.mouse_dragging = False
        info = dict(self._panel_press_info or {})
        if moved:
            info["dragged"] = True
        self._panel_press_info = info
        self._release_cursor()
        self._update_track_panel_properties()
        self.geometry.mark_dirty()
        self._keyframes_dirty = True
        self.update()

    def _handle_panel_add_click(self, info):
        if not isinstance(info, dict):
            return False
        modifiers = info.get("modifiers", Qt.NoModifier)
        force_interpolation = None
        if modifiers & Qt.AltModifier:
            # ALT: Bezier
            force_interpolation = 0
        elif modifiers & Qt.ControlModifier:
            # CTRL: Constant
            force_interpolation = 2
        elif modifiers & Qt.ShiftModifier:
            # SHIFT: Linear
            force_interpolation = 1
        prop = info.get("property")
        track_num = info.get("track")
        if not isinstance(prop, dict) or prop.get("placeholder"):
            return False
        context = info.get("context") or self.get_track_panel_context(track_num)
        context = self._panel_context_under_playhead(track_num, prop, context)
        if not isinstance(context, dict) or not context:
            log.info("Keyframe panel add skipped: no selected item under playhead")
            return False
        prop_key = prop.get("key")
        if not prop_key:
            return False
        timeline = getattr(self.win, "timeline", None)
        if not timeline:
            log.info("Keyframe panel add skipped: no timeline backend")
            return False
        item_type = context.get("item_type") if isinstance(context, dict) else None
        clip_obj = None
        transition_obj = None
        effect_obj = None
        if item_type == "clip":
            clip_id = context.get("clip_id") or context.get("item_id")
            clip_obj = Clip.get(id=clip_id) if clip_id else None
        elif item_type == "transition":
            tran_id = context.get("transition_id") or context.get("item_id")
            transition_obj = Transition.get(id=tran_id) if tran_id else None
        elif item_type == "effect":
            effect_id = context.get("effect_id") or context.get("item_id")
            effect_obj = Effect.get(id=effect_id) if effect_id else None
            clip_id = context.get("clip_id")
            clip_obj = Clip.get(id=clip_id) if clip_id else None

        parent_path = self._panel_parent_path_for_context(prop, context)
        if parent_path is None:
            log.info("Keyframe panel add skipped: property %s missing points path", prop_key)
            return False
        try:
            parent_path = tuple(parent_path)
        except TypeError:
            parent_path = parent_path
        data_obj = None
        data_label = None
        if isinstance(getattr(clip_obj, "data", None), (dict, list)):
            data_obj = clip_obj
            data_label = "clip"
        elif isinstance(getattr(transition_obj, "data", None), (dict, list)):
            data_obj = transition_obj
            data_label = "transition"
        elif isinstance(getattr(effect_obj, "data", None), (dict, list)):
            data_obj = effect_obj
            data_label = "effect"

        if not data_obj:
            log.info(
                "Keyframe panel add skipped: property %s has no writable source for context",
                prop_key,
            )
            return False

        data = getattr(data_obj, "data", None)
        target = self._resolve_data_path(data, parent_path) if isinstance(data, (dict, list)) else None
        if not isinstance(target, list):
            source_key = prop.get("source_key") if isinstance(prop, dict) else None
            if not source_key:
                source_key = prop_key
            strict_path = self._panel_find_points_parent_path(data, source_key)
            if strict_path is not None:
                parent_path = strict_path
                target = self._resolve_data_path(data, parent_path)
        if not isinstance(target, list):
            log.info(
                "Keyframe panel add skipped: property %s has no points list in target context",
                prop_key,
            )
            return False
        fps_val = context.get("fps") if isinstance(context, dict) else None
        try:
            fps_prop = float(fps_val)
        except (TypeError, ValueError):
            fps_prop = self.fps_float or 1.0
        if not math.isfinite(fps_prop) or fps_prop <= 0.0:
            fps_prop = self.fps_float or 1.0
        if not math.isfinite(fps_prop) or fps_prop <= 0.0:
            fps_prop = 1.0
        timeline_fps = self.fps_float or fps_prop
        if not math.isfinite(timeline_fps) or timeline_fps <= 0.0:
            timeline_fps = fps_prop if math.isfinite(fps_prop) and fps_prop > 0.0 else 1.0
        current_frame = getattr(self, "current_frame", 1)
        try:
            current_frame = int(current_frame)
        except (TypeError, ValueError):
            current_frame = 1
        if current_frame < 1:
            current_frame = 1
        playhead_seconds = (current_frame - 1) / timeline_fps
        position = self._panel_float(context.get("position"), 0.0)
        clip_start = self._panel_float(context.get("clip_start"), 0.0)
        clip_end = self._panel_float(context.get("clip_end"), clip_start)
        if clip_end < clip_start:
            clip_end = clip_start
        local_seconds = playhead_seconds - position
        frame_seconds = local_seconds + clip_start
        if frame_seconds < clip_start:
            frame_seconds = clip_start
        if frame_seconds > clip_end:
            frame_seconds = clip_end
        new_frame = int(round(frame_seconds * fps_prop)) + 1
        if new_frame < 1:
            new_frame = 1
        raw_value = prop.get("value")
        if raw_value is None:
            log.info("Keyframe panel add skipped: property %s missing value", prop_key)
            return False
        prop_type = (prop.get("value_type") or prop.get("type") or "").lower()
        try:
            if prop_key == "time":
                value_num = int(round(float(raw_value)))
            elif prop_type == "int":
                value_num = int(round(float(raw_value)))
            else:
                value_num = float(raw_value)
        except (TypeError, ValueError):
            log.info(
                "Keyframe panel add skipped: invalid value %s for property %s",
                raw_value,
                prop_key,
            )
            return False
        existing_path = None
        interpolation = None
        target_signature = self._panel_context_signature(context) if isinstance(context, dict) else None
        for point in prop.get("points") or []:
            point_context = point.get("_panel_context") if isinstance(point, dict) else None
            if (
                target_signature
                and isinstance(point_context, dict)
                and self._panel_context_signature(point_context) != target_signature
            ):
                continue
            frame_val = point.get("frame")
            try:
                frame_int = int(frame_val) if frame_val is not None else None
            except (TypeError, ValueError):
                frame_int = None
            if frame_int is None:
                continue
            if interpolation is None:
                interpolation = point.get("interpolation")
            if frame_int == new_frame:
                existing_path = point.get("path")
                interp_val = point.get("interpolation")
                if interp_val is not None:
                    interpolation = interp_val
                break
        if force_interpolation is not None:
            interpolation = force_interpolation
        elif interpolation is None:
            # Default interpolation when no nearby keyframe provides one.
            interpolation = 1
        try:
            interpolation_val = int(interpolation)
        except (TypeError, ValueError):
            interpolation_val = interpolation
        if existing_path:
            try:
                existing_path = tuple(existing_path)
            except TypeError:
                existing_path = existing_path
        data_copy = json.loads(json.dumps(data_obj.data))
        if not self._panel_write_point_value(
            data_copy,
            parent_path=parent_path,
            frame=new_frame,
            value=value_num,
            existing_path=existing_path,
            interpolation=interpolation_val,
        ):
            log.info("Keyframe panel add failed: unable to write property %s", prop_key)
            return False
        original_data = getattr(data_obj, "data", None)
        if isinstance(original_data, (dict, list)):
            self._panel_write_point_value(
                original_data,
                parent_path=parent_path,
                frame=new_frame,
                value=value_num,
                existing_path=existing_path,
                interpolation=interpolation_val,
            )
        try:
            if data_label == "transition":
                timeline.update_transition_data(
                    data_copy,
                    only_basic_props=False,
                    ignore_refresh=False,
                )
            else:
                timeline.update_clip_data(
                    data_copy,
                    only_basic_props=False,
                    ignore_reader=True,
                    ignore_refresh=False,
                )
        except Exception:
            log.info(
                "Keyframe panel add failed: timeline update error for property %s",
                prop_key,
            )
            return False
        if track_num is not None:
            context_signature = self._panel_context_signature(context) if isinstance(context, dict) else None
            selector = self._panel_selection_selector(
                {new_frame},
                context_signature=context_signature,
            )
            self._panel_merge_selection_map(track_num, {prop_key: selector or {new_frame}})
        self._update_track_panel_properties()
        self.geometry.mark_dirty()
        self.update()
        log.info(
            "Keyframe panel add: property %s frame=%s source=%s",
            prop_key,
            new_frame,
            data_label,
        )
        return True

    def _panel_preview_marker(
        self,
        marker,
        old_frame,
        new_frame,
        absolute_seconds,
        *,
        refresh=True,
        drag_paths=None,
    ):
        if not isinstance(marker, dict):
            return
        def _normalize_path(value):
            if isinstance(value, (tuple, list)):
                normalized = []
                for item in value:
                    norm = _normalize_path(item)
                    if isinstance(norm, list):
                        norm = tuple(norm)
                    normalized.append(norm)
                return tuple(normalized)
            return value

        marker_paths = set()
        marker_raw_paths = drag_paths if drag_paths else marker.get("data_paths")
        for raw_path in marker_raw_paths or ():
            try:
                marker_paths.add(_normalize_path(raw_path))
            except TypeError:
                continue
        if not marker_paths:
            single_path = marker.get("data_path")
            if single_path:
                try:
                    marker_paths.add(_normalize_path(single_path))
                except TypeError:
                    pass

        marker_type = marker.get("type")
        track_num = None
        context_type = None
        context_id = ""
        effect_id = marker.get("owner_id") if marker_type == "effect" else None
        clip = marker.get("clip")
        transition = marker.get("transition")
        if marker_type == "transition" and transition and isinstance(transition.data, dict):
            track_val = transition.data.get("layer")
            track_num = self.normalize_track_number(track_val)
            context_type = "transition"
            context_id = str(getattr(transition, "id", marker.get("object_id") or ""))
        elif clip and isinstance(clip.data, dict):
            track_val = clip.data.get("layer")
            track_num = self.normalize_track_number(track_val)
            context_type = "clip" if marker_type != "effect" else "effect"
            context_id = str(getattr(clip, "id", marker.get("object_id") or ""))
        if track_num is None:
            return
        info = self._panel_properties.get(track_num)
        if not info:
            return
        track_context = info.get("context", {})
        properties = info.get("properties", [])
        changed = False
        new_frame_int = None
        try:
            new_frame_int = int(new_frame) if new_frame is not None else None
        except (TypeError, ValueError):
            new_frame_int = new_frame
        for prop in properties:
            prop_context = self._panel_property_context(prop, track_context)
            prop_key = prop.get("key")
            selection_frames = set()
            selection_selector = None
            if track_num in self._panel_selected_keyframes and prop_key in self._panel_selected_keyframes[track_num]:
                selection_selector = self._panel_selected_keyframes[track_num][prop_key]
                selection_frames = self._panel_selection_frames(selection_selector)
            strict_matches = 0
            for point in prop.get("points") or []:
                context = self._panel_property_context({"context": point.get("_panel_context")}, prop_context)
                if not self._panel_context_matches_marker(context, context_type, context_id, effect_id):
                    continue
                point_path = point.get("path")
                path_match = False
                if marker_paths and point_path:
                    try:
                        path_match = _normalize_path(point_path) in marker_paths
                    except TypeError:
                        path_match = False
                frame_val = point.get("frame")
                try:
                    frame_int = int(frame_val) if frame_val is not None else None
                except (TypeError, ValueError):
                    frame_int = None
                # When drag paths are known (clip-keyframe drag), only move exact
                # path matches. Falling back to frame-only matching here causes
                # unrelated points at crossed frames to "ride along" visually.
                # Exception: colorgrade synthetic points have no individual path;
                # they represent all sub-keyframes at a frame and must use frame-match.
                is_colorgrade_point = prop.get("value_type") in ("colorgrade_curve", "colorgrade_wheels")
                frame_match = (
                    (not marker_paths or is_colorgrade_point)
                    and frame_int is not None
                    and frame_int == old_frame
                )
                if not path_match and not frame_match:
                    continue
                strict_matches += 1
                source_frame = frame_int if frame_int is not None else old_frame
                point["frame"] = new_frame_int
                if absolute_seconds is not None:
                    point["seconds"] = absolute_seconds
                    try:
                        position_val = float(context.get("position", 0.0) or 0.0)
                        point["local_seconds"] = absolute_seconds - position_val
                    except (TypeError, ValueError):
                        pass
                changed = True
                if track_num in self._panel_selected_keyframes and prop_key in self._panel_selected_keyframes[track_num]:
                    selection = self._panel_selected_keyframes[track_num][prop_key]
                    sel_context = self._panel_selection_context(selection)
                    point_context = self._panel_point_context_signature(point, context)
                    if sel_context is None or sel_context == point_context:
                        selection_frames_local = self._panel_selection_frames(selection)
                        if source_frame in selection_frames_local:
                            selection_frames_local.discard(source_frame)
                            if new_frame_int is not None:
                                selection_frames_local.add(int(new_frame_int))
                            self._panel_selected_keyframes[track_num][prop_key] = self._panel_selection_selector(
                                selection_frames_local,
                                context_signature=sel_context,
                            ) or set()
            if strict_matches == 0 and selection_frames:
                for point in prop.get("points") or []:
                    context = self._panel_property_context({"context": point.get("_panel_context")}, prop_context)
                    if not self._panel_context_matches_marker(context, context_type, context_id, effect_id):
                        continue
                    frame_val = point.get("frame")
                    try:
                        frame_int = int(frame_val) if frame_val is not None else None
                    except (TypeError, ValueError):
                        frame_int = None
                    if frame_int is None or frame_int not in selection_frames:
                        continue
                    point["frame"] = new_frame_int
                    if absolute_seconds is not None:
                        point["seconds"] = absolute_seconds
                        try:
                            position_val = float(context.get("position", 0.0) or 0.0)
                            point["local_seconds"] = absolute_seconds - position_val
                        except (TypeError, ValueError):
                            pass
                    changed = True
                if track_num in self._panel_selected_keyframes and prop_key in self._panel_selected_keyframes[track_num]:
                    if new_frame_int is not None:
                        sel_context = self._panel_selection_context(selection_selector)
                        self._panel_selected_keyframes[track_num][prop_key] = (
                            self._panel_selection_selector(
                                {int(new_frame_int)},
                                context_signature=sel_context,
                            )
                            or set()
                        )
        if changed:
            self._apply_panel_selection_flags(track_num)
            if refresh:
                self.update()

    def _apply_keyframe_drag_panel_override(self):
        """Keep panel points aligned with the active clip/effect/transition keyframe drag."""
        if self._dragging_panel_keyframes:
            return
        drag = self._dragging_keyframe
        if not isinstance(drag, dict):
            return
        marker = drag.get("marker")
        if not isinstance(marker, dict):
            return
        old_frame = drag.get("current_frame")
        new_frame = drag.get("pending_frame", old_frame)
        pending_seconds = drag.get("pending_seconds")
        if pending_seconds is None:
            fps = self.fps_float or 0.0
            try:
                frame_val = int(new_frame) if new_frame is not None else None
            except (TypeError, ValueError):
                frame_val = None
            if fps > 0.0 and frame_val is not None:
                clip_start = self._panel_float(drag.get("clip_start"), 0.0)
                pending_seconds = max(0.0, ((frame_val - 1.0) / fps) - clip_start)
        if pending_seconds is None:
            return
        pending_seconds = self._panel_float(pending_seconds, None)
        if pending_seconds is None:
            return
        base_position = self._keyframe_base_position(marker)
        absolute_seconds = base_position + pending_seconds
        self._panel_preview_marker(
            marker,
            old_frame,
            new_frame,
            absolute_seconds,
            refresh=False,
            drag_paths=drag.get("data_paths"),
        )

    def _panel_shift_item(self, item, delta_seconds, frame_offset):
        if not isinstance(delta_seconds, (int, float)):
            delta_seconds = 0.0
        try:
            frame_offset = int(frame_offset)
        except (TypeError, ValueError):
            frame_offset = 0
        try:
            layer = item.data.get("layer")
        except Exception:
            layer = None
        target_track_num = self.normalize_track_number(layer) if layer is not None else None
        if target_track_num is None:
            return

        source_track_num = self._panel_track_for_item(item)
        if source_track_num is None:
            source_track_num = target_track_num

        item_key = self._panel_drag_item_key(item)
        hidden_map = getattr(self, "_panel_hidden_drag_info", None)
        if not isinstance(hidden_map, dict):
            hidden_map = {}
            self._panel_hidden_drag_info = hidden_map

        target_enabled = bool(self._track_panel_enabled.get(target_track_num))
        if item_key and target_enabled:
            hidden_entry = hidden_map.get(item_key)
            target_info = self._panel_properties.get(target_track_num)
            target_placeholder = bool(
                isinstance(target_info, dict)
                and isinstance(target_info.get("context"), dict)
                and target_info.get("context", {}).get("placeholder")
            )
            if isinstance(hidden_entry, dict) and (not target_info or target_placeholder):
                restored_info = hidden_entry.get("info")
                if restored_info:
                    self._panel_properties[target_track_num] = restored_info
                    restored_height = hidden_entry.get("height")
                    if restored_height is None:
                        restored_height = self._panel_height_for_properties(
                            len(restored_info.get("properties") or [])
                        )
                    self._panel_heights[target_track_num] = restored_height
                    restored_selection = hidden_entry.get("selection")
                    if restored_selection is not None:
                        self._panel_selected_keyframes[target_track_num] = restored_selection
                    restored_manual = hidden_entry.get("manual")
                    if restored_manual is not None:
                        self._panel_manual_properties[target_track_num] = restored_manual
                    context = restored_info.get("context")
                    if isinstance(context, dict):
                        context["track"] = target_track_num
                    hidden_map.pop(item_key, None)
                    self.geometry.mark_dirty()
                    source_track_num = target_track_num

        # Keep panel aligned with dragged item's track. If target track panel is
        # hidden, clear the moving panel preview to avoid stale old-track display.
        if source_track_num != target_track_num:
            source_info = self._panel_properties.get(source_track_num)
            if isinstance(source_info, dict) and source_info.get("item_type") == "multi":
                # Multi-item panel rows are track-local; let the next refresh rebuild
                # them after drop instead of moving the entire combined panel.
                return
            if target_enabled and source_info:
                source_height = self._panel_heights.get(source_track_num)
                self._panel_properties[target_track_num] = source_info
                self._panel_properties.pop(source_track_num, None)
                if source_height is None:
                    source_height = self._panel_height_for_properties(
                        len(source_info.get("properties") or [])
                    )
                self._panel_heights[target_track_num] = source_height
                if source_track_num in self._panel_selected_keyframes:
                    self._panel_selected_keyframes[target_track_num] = self._panel_selected_keyframes.pop(
                        source_track_num
                    )
                if source_track_num in self._panel_manual_properties:
                    self._panel_manual_properties[target_track_num] = self._panel_manual_properties.pop(
                        source_track_num
                    )
                context = source_info.get("context")
                if isinstance(context, dict):
                    context["track"] = target_track_num
                if self._track_panel_enabled.get(source_track_num):
                    placeholder, placeholder_height = self._panel_placeholder_info("no-selection")
                    self._panel_properties[source_track_num] = placeholder
                    self._panel_heights[source_track_num] = placeholder_height
                else:
                    self._panel_heights.pop(source_track_num, None)
                source_track_num = target_track_num
                self.geometry.mark_dirty()
            elif not target_enabled:
                if item_key and source_info:
                    hidden_map[item_key] = {
                        "info": source_info,
                        "height": self._panel_heights.get(source_track_num),
                        "selection": self._panel_selected_keyframes.get(source_track_num),
                        "manual": self._panel_manual_properties.get(source_track_num),
                    }
                if self._track_panel_enabled.get(source_track_num):
                    placeholder, placeholder_height = self._panel_placeholder_info("no-selection")
                    self._panel_properties[source_track_num] = placeholder
                    self._panel_heights[source_track_num] = placeholder_height
                else:
                    self._panel_properties.pop(source_track_num, None)
                    self._panel_heights.pop(source_track_num, None)
                self._panel_selected_keyframes.pop(source_track_num, None)
                self._panel_manual_properties.pop(source_track_num, None)
                self.geometry.mark_dirty()
                self.update()
                return

        track_num = source_track_num
        info = self._panel_properties.get(track_num)
        if not info:
            return
        track_context = info.get("context")
        if isinstance(track_context, dict) and track_context.get("placeholder"):
            return
        drag_base_token = getattr(self, "_drag_transaction_id", None)
        base_token = info.get("_panel_shift_base_token")
        base_props = info.get("base_properties")
        if base_props is None or base_token != drag_base_token:
            base_props = self._panel_capture_base_properties(info.get("properties"))
            info["base_properties"] = base_props
        info["_panel_shift_base_token"] = drag_base_token

        properties = info.get("properties", [])
        changed = False
        for prop in properties:
            context = self._panel_property_context(prop, track_context)
            prop_matches_item = self._panel_context_matches_item(context, item)
            base_context = prop.get("_panel_base_context")
            if prop_matches_item:
                if not isinstance(base_context, dict) or base_token != drag_base_token:
                    base_context = self._panel_capture_base_context(context)
                    prop["_panel_base_context"] = base_context
                for key_name in ("position", "range_start_seconds", "range_end_seconds"):
                    base_value = base_context.get(key_name, context.get(key_name))
                    if base_value is None:
                        continue
                    try:
                        context[key_name] = float(base_value) + delta_seconds
                    except (TypeError, ValueError):
                        context[key_name] = base_value

            key_name = self._panel_property_key(prop)
            base_points = base_props.get(key_name, []) if key_name else []
            points = prop.get("points") or []
            for index, point in enumerate(points):
                point_context = self._panel_property_context({"context": point.get("_panel_context")}, context)
                if not self._panel_context_matches_item(point_context, item):
                    continue
                base_point = base_points[index] if index < len(base_points) else {}
                base_frame = base_point.get("frame")
                if base_frame is not None:
                    try:
                        point["frame"] = int(base_frame) + frame_offset
                    except (TypeError, ValueError):
                        point["frame"] = base_frame
                    changed = True
                base_seconds = base_point.get("seconds")
                if base_seconds is not None:
                    try:
                        new_seconds = float(base_seconds) + delta_seconds
                    except (TypeError, ValueError):
                        new_seconds = base_seconds
                    point["seconds"] = new_seconds
                    try:
                        position_val = float(point_context.get("position", 0.0) or 0.0)
                        point["local_seconds"] = float(new_seconds) - position_val
                    except (TypeError, ValueError):
                        pass
                    changed = True

        if track_num in self._panel_selected_keyframes:
            existing_selection = dict(self._panel_selected_keyframes.get(track_num, {}) or {})
            updated = {}
            for prop in properties:
                prop_key = prop.get("key")
                if not prop_key:
                    continue
                selected_frames = set()
                selected_context = None
                for point in prop.get("points") or []:
                    context = self._panel_property_context({"context": point.get("_panel_context")}, track_context)
                    if not self._panel_context_matches_item(context, item):
                        continue
                    if not point.get("selected"):
                        continue
                    if selected_context is None:
                        selected_context = self._panel_context_signature(context)
                    frame_val = point.get("frame")
                    if frame_val is None:
                        continue
                    try:
                        selected_frames.add(int(frame_val))
                    except (TypeError, ValueError):
                        continue
                if selected_frames:
                    updated[prop_key] = self._panel_selection_selector(
                        selected_frames,
                        context_signature=selected_context,
                    ) or selected_frames
            if updated:
                self._panel_selected_keyframes[track_num] = updated
            else:
                self._panel_selected_keyframes.pop(track_num, None)
            self._apply_panel_selection_flags(track_num)

        if changed:
            self.update()

    def _panel_select_points_for_clip_marker(self, marker):
        """Select all panel points at the marker frame for the marker's clip."""
        if not isinstance(marker, dict) or marker.get("type") != "clip":
            return
        clip = marker.get("clip")
        if not clip or not isinstance(getattr(clip, "data", None), dict):
            return
        track_num = self.normalize_track_number(clip.data.get("layer"))
        if track_num is None or not self.is_keyframe_panel_visible(track_num):
            return
        info = self._panel_properties.get(track_num)
        if not isinstance(info, dict):
            return
        context = info.get("context")
        if isinstance(context, dict) and context.get("placeholder"):
            return
        clip_id = str(getattr(clip, "id", ""))
        frame_val = marker.get("display_frame", marker.get("frame"))
        try:
            target_frame = int(frame_val) if frame_val is not None else None
        except (TypeError, ValueError):
            target_frame = None
        if target_frame is None:
            return
        mapping = {}
        for prop in info.get("properties", []):
            if not isinstance(prop, dict) or prop.get("placeholder"):
                continue
            prop_key = prop.get("key")
            if not prop_key:
                continue
            frames = set()
            context_signature = None
            for point in prop.get("points") or []:
                point_context = self._panel_property_context({"context": point.get("_panel_context")}, context)
                context_clip_id = str(point_context.get("clip_id") or point_context.get("item_id") or "")
                if context_clip_id and context_clip_id != clip_id:
                    continue
                if context_signature is None:
                    context_signature = self._panel_context_signature(point_context)
                frame = point.get("frame")
                try:
                    frame = int(frame) if frame is not None else None
                except (TypeError, ValueError):
                    frame = None
                if frame == target_frame:
                    frames.add(frame)
            if frames:
                mapping[prop_key] = self._panel_selection_selector(
                    frames,
                    context_signature=context_signature,
                )
        self._panel_set_selection_map(track_num, mapping)

    def _clear_panel_selection(self, track_num=None):
        targets = []
        if track_num is None:
            targets = list(self._panel_selected_keyframes.keys())
        else:
            key = self.normalize_track_number(track_num)
            if key in self._panel_selected_keyframes:
                targets = [key]
        if not targets:
            return
        changed = False
        for key in targets:
            if key in self._panel_selected_keyframes:
                self._panel_selected_keyframes.pop(key, None)
                changed = True
            info = self._panel_properties.get(key)
            if not info:
                continue
            for prop in info.get("properties", []):
                for point in prop.get("points") or []:
                    if point.get("selected"):
                        point["selected"] = False
                        changed = True
        if changed:
            self.update()

    def _apply_panel_selection_flags(self, track_num):
        key = self.normalize_track_number(track_num)
        info = self._panel_properties.get(key)
        if not info:
            return
        selection = self._panel_selected_keyframes.get(key, {}) or {}
        for prop in info.get("properties", []):
            prop_context = self._panel_property_context(prop, info.get("context"))
            selector = selection.get(prop.get("key"), set())
            for point in prop.get("points") or []:
                frame = point.get("frame")
                point["selected"] = self._panel_selection_contains(
                    selector,
                    frame,
                    point=point,
                    fallback_context=prop_context,
                )

    def _sync_panel_selection(self, track_num, properties):
        key = self.normalize_track_number(track_num)
        if key not in self._panel_selected_keyframes:
            return
        current = self._panel_selected_keyframes.get(key) or {}
        if not current:
            self._panel_selected_keyframes.pop(key, None)
            return
        valid = {}
        for prop in properties or []:
            prop_key = prop.get("key")
            frames = {
                int(point.get("frame"))
                for point in prop.get("points") or []
                if point.get("frame") is not None
            }
            if not frames or prop_key not in current:
                continue
            selector = current.get(prop_key, set())
            selector_frames = self._panel_selection_frames(selector)
            selected = {frame for frame in selector_frames if frame in frames}
            if selected:
                valid[prop_key] = self._panel_selection_selector(
                    selected,
                    context_signature=self._panel_selection_context(selector),
                )
        if valid:
            self._panel_selected_keyframes[key] = valid
        else:
            self._panel_selected_keyframes.pop(key, None)

    def _panel_set_selection_map(self, track_num, mapping):
        key = self.normalize_track_number(track_num)
        if key is None:
            return
        cleaned = {}
        for prop_key, selector in (mapping or {}).items():
            if not prop_key or not selector:
                continue
            context_signature = self._panel_selection_context(selector)
            normalized = self._panel_selection_selector(
                selector,
                context_signature=context_signature,
            )
            if normalized:
                cleaned[prop_key] = normalized
        if cleaned:
            self._panel_selected_keyframes[key] = cleaned
        else:
            self._panel_selected_keyframes.pop(key, None)
        self._apply_panel_selection_flags(key)
        self.update()

    def _panel_merge_selection_map(self, track_num, mapping):
        key = self.normalize_track_number(track_num)
        if key is None:
            return
        if key not in self._panel_selected_keyframes:
            self._panel_selected_keyframes[key] = {}
        track_map = self._panel_selected_keyframes[key]
        changed = False
        for prop_key, selector in (mapping or {}).items():
            if not prop_key or not selector:
                continue
            source_frames = self._panel_selection_frames(selector)
            if not source_frames:
                continue
            source_context = self._panel_selection_context(selector)
            current_selector = track_map.get(prop_key)
            current_context = self._panel_selection_context(current_selector)
            current_frames = self._panel_selection_frames(current_selector)
            if current_context is not None and source_context is not None and current_context != source_context:
                merged_frames = set(source_frames)
                merged_context = source_context
            else:
                merged_frames = set(current_frames)
                before = set(merged_frames)
                merged_frames.update(source_frames)
                if merged_frames == before:
                    continue
                merged_context = source_context if source_context is not None else current_context
            normalized = self._panel_selection_selector(
                merged_frames,
                context_signature=merged_context,
            )
            if normalized != current_selector:
                track_map[prop_key] = normalized
                changed = True
        if not track_map:
            self._panel_selected_keyframes.pop(key, None)
        if changed:
            self._apply_panel_selection_flags(key)
            self.update()

    def _panel_toggle_frames(self, track_num, prop_key, frames, context_signature=None):
        key = self.normalize_track_number(track_num)
        if key is None or not prop_key:
            return
        if key not in self._panel_selected_keyframes:
            self._panel_selected_keyframes[key] = {}
        track_map = self._panel_selected_keyframes[key]
        current_selector = track_map.get(prop_key, set())
        current_context = self._panel_selection_context(current_selector)
        if context_signature:
            if isinstance(context_signature, (tuple, list)):
                context_signature = tuple(str(part) for part in context_signature)
            else:
                context_signature = None
        if (
            context_signature is not None
            and current_context is not None
            and current_context != context_signature
        ):
            current = set()
        else:
            current = self._panel_selection_frames(current_selector)
            if context_signature is None:
                context_signature = current_context
        changed = False
        for frame in frames or []:
            if frame is None:
                continue
            frame_int = int(frame)
            if frame_int in current:
                current.remove(frame_int)
            else:
                current.add(frame_int)
            changed = True
        if current:
            track_map[prop_key] = self._panel_selection_selector(
                current,
                context_signature=context_signature,
            )
        else:
            track_map.pop(prop_key, None)
        if not track_map:
            self._panel_selected_keyframes.pop(key, None)
        if changed:
            self._apply_panel_selection_flags(key)
            self.update()

    def _refresh_panel_selection_state(self, new_props):
        active_tracks = set(new_props.keys())
        for track_num in list(self._panel_selected_keyframes.keys()):
            if track_num not in active_tracks:
                self._panel_selected_keyframes.pop(track_num, None)
                continue
            info = new_props.get(track_num, {})
            properties = info.get("properties", [])
            self._sync_panel_selection(track_num, properties)
            self._apply_panel_selection_flags(track_num)

    def _panel_item_context(self, item_id, item_type):
        context = {
            "item_id": str(item_id),
            "item_type": item_type,
            "fps": self.fps_float or 1.0,
        }

        if item_type == "clip":
            clip = Clip.get(id=item_id)
            data = clip.data if clip and isinstance(clip.data, dict) else {}
            position = self._panel_float(data.get("position"), 0.0)
            clip_start = self._panel_float(data.get("start"), 0.0)
            clip_end = self._panel_float(data.get("end"), clip_start)
            if clip_end < clip_start:
                clip_end = clip_start
            duration = max(0.0, clip_end - clip_start)
            context.update(
                {
                    "position": position,
                    "clip_start": clip_start,
                    "clip_end": clip_end,
                    "range_start_seconds": position,
                    "range_end_seconds": position + duration,
                    "clip_id": str(getattr(clip, "id", "") or data.get("id") or item_id),
                    "track": data.get("layer"),
                    "duration": duration,
                }
            )
            return context

        if item_type == "effect":
            effect = Effect.get(id=item_id)
            data = effect.data if effect and isinstance(effect.data, dict) else {}
            parent = effect.parent if effect and isinstance(effect.parent, dict) else {}
            position = self._panel_float(parent.get("position"), None)
            if position is None:
                position = self._panel_float(data.get("position"), 0.0)
            clip_start = self._panel_float(parent.get("start"), 0.0)
            clip_end = self._panel_float(parent.get("end"), clip_start)
            if clip_end < clip_start:
                clip_end = clip_start
            duration = max(0.0, clip_end - clip_start)
            clip_id = parent.get("id") or data.get("parent_id") or parent.get("clip_id")
            context.update(
                {
                    "position": position,
                    "clip_start": clip_start,
                    "clip_end": clip_end,
                    "range_start_seconds": position,
                    "range_end_seconds": position + duration,
                    "clip_id": str(clip_id) if clip_id is not None else "",
                    "parent": parent,
                    "effect_id": str(getattr(effect, "id", "") or data.get("id") or item_id),
                    "track": parent.get("layer")
                    if isinstance(parent, dict) and parent.get("layer") is not None
                    else data.get("layer"),
                    "duration": duration,
                }
            )
            return context

        if item_type == "transition":
            transition = Transition.get(id=item_id)
            data = transition.data if transition and isinstance(transition.data, dict) else {}
            position = self._panel_float(data.get("position"), 0.0)
            clip_start = self._panel_float(data.get("start"), 0.0)
            clip_end = self._panel_float(data.get("end"), clip_start)
            if clip_end < clip_start:
                clip_end = clip_start
            duration = max(0.0, clip_end - clip_start)
            context.update(
                {
                    "position": position,
                    "clip_start": clip_start,
                    "clip_end": clip_end,
                    "range_start_seconds": position,
                    "range_end_seconds": position + duration,
                    "track": data.get("layer"),
                    "transition_id": str(getattr(transition, "id", "") or data.get("id") or item_id),
                    "duration": duration,
                }
            )
            return context

        position = self._panel_float(context.get("position"), 0.0)
        context.update(
            {
                "position": position,
                "clip_start": 0.0,
                "clip_end": 0.0,
                "range_start_seconds": position,
                "range_end_seconds": position,
                "duration": 0.0,
            }
        )
        return context

    def _track_number_for_selection(self, item_id, item_type):
        try:
            if item_type == "clip":
                clip = Clip.get(id=item_id)
                if clip and isinstance(clip.data, dict):
                    return clip.data.get("layer")
            elif item_type == "transition":
                tran = Transition.get(id=item_id)
                if tran and isinstance(tran.data, dict):
                    return tran.data.get("layer")
            elif item_type == "effect":
                effect = Effect.get(id=item_id)
                if effect:
                    parent = getattr(effect, "parent", None)
                    if isinstance(parent, dict):
                        return parent.get("layer")
                    if isinstance(effect.data, dict):
                        return effect.data.get("layer")
        except Exception:
            return None
        return None

    def _properties_for_item(self, timeline, item_id, item_type, frame, context=None):
        obj = None
        item_id_str = str(item_id)
        try:
            if item_type == "clip":
                obj = timeline.GetClip(item_id_str)
            elif item_type == "transition":
                obj = timeline.GetEffect(item_id_str)
            elif item_type == "effect":
                obj = timeline.GetClipEffect(item_id_str)
        except Exception:
            obj = None
        if not obj:
            return [], {}

        try:
            props = json.loads(obj.PropertiesJSON(int(frame)))
        except Exception:
            return [], {}

        tracked = props.pop("objects", None)
        if isinstance(tracked, dict):
            for track_props in tracked.values():
                if isinstance(track_props, dict):
                    props.update(track_props)
                    break

        context = context or self._panel_item_context(item_id, item_type)
        if not context:
            context = {"item_id": item_id_str, "item_type": item_type}
        fps = context.get("fps") or self.fps_float or 1.0
        if fps <= 0.0:
            fps = 1.0

        clip_start = context.get("clip_start", 0.0)
        position = context.get("position", 0.0)

        _ = get_app()._tr

        track_selection = {}
        if isinstance(context, dict) and context.get("track") is not None:
            track_key = self.normalize_track_number(context.get("track"))
            track_selection = self._panel_selected_keyframes.get(track_key, {}) or {}

        raw_sources = []

        def _add_source(data, owner, **meta):
            if not isinstance(data, (dict, list)):
                return
            entry = {"data": data, "owner": owner}
            for key_name, value in meta.items():
                if value is not None:
                    entry[key_name] = value
            raw_sources.append(entry)

        try:
            if item_type == "clip":
                clip_obj = Clip.get(id=item_id)
                if clip_obj and isinstance(getattr(clip_obj, "data", None), dict):
                    _add_source(
                        clip_obj.data,
                        "clip",
                        clip=clip_obj,
                        clip_id=str(getattr(clip_obj, "id", item_id)),
                    )
            elif item_type == "transition":
                tran_obj = Transition.get(id=item_id)
                if tran_obj and isinstance(getattr(tran_obj, "data", None), dict):
                    _add_source(
                        tran_obj.data,
                        "transition",
                        transition=tran_obj,
                        transition_id=str(getattr(tran_obj, "id", item_id)),
                    )
            elif item_type == "effect":
                eff_obj = Effect.get(id=item_id)
                clip_id = context.get("clip_id") if isinstance(context, dict) else None
                clip_obj = Clip.get(id=clip_id) if clip_id else None
                if clip_obj and isinstance(getattr(clip_obj, "data", None), dict):
                    _add_source(
                        clip_obj.data,
                        "clip",
                        clip=clip_obj,
                        effect=eff_obj,
                        clip_id=str(getattr(clip_obj, "id", clip_id)),
                    )
                parent_ctx = context.get("parent") if isinstance(context, dict) else None
                if isinstance(parent_ctx, (dict, list)):
                    _add_source(
                        parent_ctx,
                        "parent",
                        clip=clip_obj,
                        effect=eff_obj,
                        clip_id=str(clip_id) if clip_id is not None else None,
                    )
                if eff_obj and isinstance(getattr(eff_obj, "data", None), dict):
                    _add_source(
                        eff_obj.data,
                        "effect",
                        effect=eff_obj,
                        clip=clip_obj,
                        clip_id=str(clip_id) if clip_id is not None else None,
                        effect_id=str(getattr(eff_obj, "id", item_id)),
                    )
        except Exception:
            log.info("Keyframe panel refresh: failed to fetch raw data for %s %s", item_type, item_id)

        def _iter_sources():
            visited = set()

            def _visit(source, path, meta):
                if not isinstance(source, (dict, list)):
                    return
                key = (id(source), meta.get("owner"))
                if key in visited:
                    return
                visited.add(key)
                if isinstance(source, dict):
                    yield source, path, meta
                    for key_name, value in source.items():
                        if isinstance(value, dict):
                            yield from _visit(value, path + (("dict", key_name),), meta)
                        elif isinstance(value, list):
                            yield from _visit(value, path + (("dict", key_name),), meta)
                else:
                    for index, item in enumerate(source):
                        yield from _visit(item, path + (("list", index),), meta)

            for entry in raw_sources:
                data = entry.get("data")
                if not isinstance(data, (dict, list)):
                    continue
                meta = dict(entry)
                meta.pop("data", None)
                yield from _visit(data, (), meta)

        def _property_points(prop_key, prop_dict):
            for source, path, meta in _iter_sources():
                if not isinstance(source, dict):
                    continue
                candidate = source.get(prop_key)
                if not isinstance(candidate, dict):
                    continue
                base_path = path + (("dict", prop_key),)
                points = candidate.get("Points")
                if isinstance(points, list):
                    point_paths = [
                        base_path + (("dict", "Points"), ("list", index))
                        for index, _point in enumerate(points)
                    ]
                    return {"points": points, "paths": point_paths, "meta": meta}
                if prop_dict.get("type") == "color":
                    for channel in ("red", "green", "blue", "alpha"):
                        channel_data = candidate.get(channel)
                        if not isinstance(channel_data, dict):
                            continue
                        channel_points = channel_data.get("Points")
                        if isinstance(channel_points, list):
                            channel_path = base_path + (("dict", channel), ("dict", "Points"))
                            point_paths = [
                                channel_path + (("list", index),)
                                for index, _point in enumerate(channel_points)
                            ]
                            return {"points": channel_points, "paths": point_paths, "meta": meta}
            return None

        def convert_points(prop_key, prop_dict):
            points_info = _property_points(prop_key, prop_dict)
            if not isinstance(points_info, dict):
                return [], None, None, {}, []

            points = points_info.get("points") or []
            point_paths = points_info.get("paths") or []
            normalized_paths = []
            for path in point_paths:
                try:
                    normalized_paths.append(tuple(path))
                except TypeError:
                    normalized_paths.append(path)
            metadata = points_info.get("meta") or {}

            converted = []
            min_val = None
            max_val = None
            for index, point in enumerate(points):
                if not isinstance(point, dict):
                    continue
                co = point.get("co") if isinstance(point.get("co"), dict) else {}
                frame_val = co.get("X")
                try:
                    frame_float = float(frame_val)
                except (TypeError, ValueError):
                    continue
                seconds_abs = (frame_float - 1.0) / fps
                local_seconds = seconds_abs - clip_start
                absolute_seconds = position + local_seconds
                value = co.get("Y")
                try:
                    value_float = float(value)
                    if math.isnan(value_float) or math.isinf(value_float):
                        value_float = None
                except (TypeError, ValueError):
                    value_float = None
                if value_float is not None:
                    if min_val is None or value_float < min_val:
                        min_val = value_float
                    if max_val is None or value_float > max_val:
                        max_val = value_float
                entry = {
                    "frame": int(round(frame_float)),
                    "seconds": absolute_seconds,
                    "local_seconds": local_seconds,
                    "value": value_float,
                    "interpolation": point.get("interpolation"),
                }
                if index < len(point_paths):
                    try:
                        entry["path"] = tuple(point_paths[index])
                    except TypeError:
                        entry["path"] = point_paths[index]
                converted.append(entry)
            converted.sort(key=lambda entry: entry.get("seconds", 0.0))
            return converted, min_val, max_val, metadata, normalized_paths

        result = []
        available = []
        sparse_logged = getattr(self, "_panel_sparse_properties", None)

        def _colorgrade_synthetic_points(raw_data, prop_type):
            """Return sorted list of unique (frame, seconds) pairs from nested colorgrade data."""
            from windows.color_grade_editor import colorgrade_keyframe_frames
            frame_set = colorgrade_keyframe_frames(raw_data, prop_type)
            pts = []
            for frame_num in sorted(frame_set):
                seconds_abs = (frame_num - 1.0) / fps
                local_secs = seconds_abs - clip_start
                absolute_secs = position + local_secs
                pts.append({
                    "frame": frame_num,
                    "seconds": absolute_secs,
                    "local_seconds": local_secs,
                    "value": None,
                    "interpolation": None,
                    "selected": False,
                })
            return pts

        for key, prop in props.items():
            if not isinstance(prop, dict):
                continue

            # Colorgrade types have nested keyframe structures; handle them separately.
            prop_type = prop.get("type")
            if prop_type in ("colorgrade_curve", "colorgrade_wheels"):
                name = prop.get("name") or str(key)
                raw_data = None
                source_meta = {}
                for source, _path, meta in _iter_sources():
                    if isinstance(source, dict):
                        candidate = source.get(key)
                        if isinstance(candidate, dict):
                            raw_data = candidate
                            source_meta = meta
                            break
                synth_points = _colorgrade_synthetic_points(raw_data, prop_type)
                selected_selector = track_selection.get(key, set())
                for pt in synth_points:
                    pt["selected"] = self._panel_selection_contains(
                        selected_selector, pt.get("frame"), fallback_context=context)
                entry = {
                    "key": key,
                    "display_name": _(name),
                    "points": synth_points,
                    "min_value": None,
                    "max_value": None,
                    "source_meta": source_meta,
                    "owner_type": source_meta.get("owner") if isinstance(source_meta, dict) else None,
                    "value": prop.get("value"),
                    "value_type": prop_type,
                    "point_paths": [],
                }
                available.append(entry)
                if len(synth_points) > 1:
                    result.append(entry)
                continue

            point_count_value = prop.get("points")
            declared_points = None
            if point_count_value is not None:
                try:
                    declared_points = int(point_count_value)
                except (TypeError, ValueError):
                    declared_points = None
            points, min_val, max_val, source_meta, normalized_paths = convert_points(key, prop)
            has_curve_container = bool(source_meta)
            metadata_keyframe = bool(prop.get("keyframe")) or has_curve_container
            if not points and not normalized_paths and not metadata_keyframe:
                continue
            name = prop.get("name") or str(key)
            if len(points) <= 1:
                if sparse_logged is not None and (
                    metadata_keyframe or (declared_points is not None and declared_points > 0)
                ):
                    owner_hint = (
                        prop.get("owner")
                        or prop.get("owner_id")
                        or prop.get("clip_id")
                        or prop.get("effect_id")
                        or prop.get("transition_id")
                        or prop.get("id")
                        or ""
                    )
                    identifier = (str(key), str(owner_hint))
                    if identifier not in sparse_logged:
                        sparse_logged.add(identifier)
                        log.debug(
                            "Keyframe panel refresh: property %s has insufficient curve data (flag=%s points=%s)",
                            key,
                            metadata_keyframe,
                            point_count_value,
                        )
                entry = {
                    "key": key,
                    "display_name": _(name),
                    "points": points,
                    "min_value": min_val,
                    "max_value": max_val,
                    "source_meta": source_meta,
                    "owner_type": source_meta.get("owner") if isinstance(source_meta, dict) else None,
                    "value": prop.get("value"),
                    "value_type": prop.get("type"),
                    "point_paths": normalized_paths,
                }
                available.append(entry)
                continue
            if sparse_logged is not None and declared_points is not None and declared_points <= 1:
                owner_hint = (
                    prop.get("owner")
                    or prop.get("owner_id")
                    or prop.get("clip_id")
                    or prop.get("effect_id")
                    or prop.get("transition_id")
                    or prop.get("id")
                    or ""
                )
                identifier = ("promote", str(key), str(owner_hint))
                if identifier not in sparse_logged:
                    sparse_logged.add(identifier)
                    log.debug(
                        "Keyframe panel refresh: promoting property %s with reported point count %s (actual=%s)",
                        key,
                        declared_points,
                        len(points),
                    )
            if sparse_logged is not None and not metadata_keyframe:
                owner_hint = (
                    prop.get("owner")
                    or prop.get("owner_id")
                    or prop.get("clip_id")
                    or prop.get("effect_id")
                    or prop.get("transition_id")
                    or prop.get("id")
                    or ""
                )
                identifier = ("promote-flag", str(key), str(owner_hint))
                if identifier not in sparse_logged:
                    sparse_logged.add(identifier)
                    log.debug(
                        "Keyframe panel refresh: treating property %s as keyframe despite flag False",
                        key,
                    )
            selected_selector = track_selection.get(key, set())
            selected_frames = self._panel_selection_frames(selected_selector)
            for point in points:
                frame_val = point.get("frame")
                try:
                    frame_int = int(frame_val) if frame_val is not None else None
                except (TypeError, ValueError):
                    frame_int = None
                point["frame"] = frame_int
                point["selected"] = self._panel_selection_contains(
                    selected_selector,
                    frame_int,
                    point=point,
                    fallback_context=context,
                )
            entry = {
                "key": key,
                "display_name": _(name),
                "points": points,
                "min_value": min_val,
                "max_value": max_val,
                "source_meta": source_meta,
                "owner_type": source_meta.get("owner") if isinstance(source_meta, dict) else None,
                "value": prop.get("value"),
                "value_type": prop.get("type"),
                "point_paths": normalized_paths,
            }
            available.append(entry)
            result.append(entry)

        result.sort(key=lambda item: item.get("display_name", "").lower())
        available.sort(key=lambda item: item.get("display_name", "").lower())
        return result, context, available

    def _update_track_panel_properties(self):
        if not getattr(self, "win", None):
            log.info("Keyframe panel refresh skipped: no window reference")
            return False
        timeline_sync = getattr(self.win, "timeline_sync", None)
        timeline = getattr(timeline_sync, "timeline", None) if timeline_sync else None
        if not timeline:
            self._panel_properties = {}
            self._panel_heights = {}
            self._panel_manual_properties = {}
            log.info("Keyframe panel refresh skipped: no timeline model")
            return False
        enabled_tracks = {
            self.normalize_track_number(track)
            for track, state in self._track_panel_enabled.items()
            if state
        }
        if not enabled_tracks:
            had_data = bool(self._panel_properties or self._panel_heights)
            if had_data:
                log.info("Keyframe panel refresh cleared: no panels enabled")
            self._panel_properties = {}
            self._panel_heights = {}
            self._panel_manual_properties = {}
            return had_data
        selection = list(getattr(self.win, "selected_items", []) or [])
        frame = int(getattr(self, "current_frame", 1) or 1)
        if frame <= 0:
            frame = 1
        new_props = {}
        new_heights = {}
        translate = get_app()._tr

        def _placeholder_info(label_text, reason):
            props = [{"display_name": label_text, "points": [], "placeholder": True}]
            info = {
                "item_id": "",
                "item_type": None,
                "properties": props,
                "context": {"placeholder": reason},
                "base_properties": {},
                "base_context": {},
            }
            return info, self._panel_height_for_properties(len(props))

        grouped_entries = {}
        for sel in selection:
            item_id = sel.get("id")
            item_type = sel.get("type")
            if not item_id or item_type not in ("clip", "effect", "transition"):
                continue
            context = self._panel_item_context(item_id, item_type)
            track_value = context.get("track") if isinstance(context, dict) else None
            track_num = self.normalize_track_number(track_value) if track_value is not None else None
            if track_num is None:
                track_num = self._track_number_for_selection(item_id, item_type)
            if track_num is None:
                log.info(
                    "Keyframe panel refresh: unable to determine track for %s %s",
                    item_type,
                    item_id,
                )
                continue
            key = self.normalize_track_number(track_num)
            if key not in enabled_tracks:
                log.info(
                    "Keyframe panel refresh: selection %s %s on track %s not enabled",
                    item_type,
                    item_id,
                    key,
                )
                continue
            properties, context, available = self._properties_for_item(
                timeline,
                item_id,
                item_type,
                frame,
                context=context,
            )
            grouped_entries.setdefault(key, []).append(
                {
                    "item_id": str(item_id),
                    "item_type": item_type,
                    "properties": list(properties or []),
                    "context": dict(context or {}),
                    "available": list(available or []),
                }
            )

        for key in sorted(enabled_tracks):
            entries = grouped_entries.get(key, [])
            if not entries:
                continue
            if len(entries) == 1:
                entry = entries[0]
                item_id = entry["item_id"]
                item_type = entry["item_type"]
                properties = list(entry["properties"] or [])
                context = dict(entry.get("context") or {})
                available = list(entry.get("available") or [])

                available_map = {
                    str(entry_obj.get("key")): entry_obj
                    for entry_obj in available
                    if isinstance(entry_obj, dict) and entry_obj.get("key") is not None
                }
                manual_entry = self._panel_manual_properties.get(key)
                if (
                    not manual_entry
                    or manual_entry.get("item_id") != item_id
                    or manual_entry.get("item_type") != item_type
                ):
                    manual_entry = {
                        "item_id": item_id,
                        "item_type": item_type,
                        "properties": set(),
                    }
                else:
                    manual_entry = {
                        "item_id": manual_entry.get("item_id", item_id),
                        "item_type": manual_entry.get("item_type"),
                        "properties": set(manual_entry.get("properties") or []),
                    }
                manual_entry["properties"] = {
                    prop_id for prop_id in manual_entry.get("properties", set()) if prop_id in available_map
                }
                existing_keys = {
                    str(prop.get("key"))
                    for prop in properties
                    if isinstance(prop, dict) and prop.get("key") is not None
                }

                def _manual_sort_key(prop_id):
                    entry_obj = available_map.get(prop_id)
                    if not isinstance(entry_obj, dict):
                        return prop_id.lower()
                    label = entry_obj.get("display_name") or entry_obj.get("key") or prop_id
                    return str(label).lower()

                for prop_id in sorted(manual_entry["properties"], key=_manual_sort_key):
                    if prop_id in existing_keys:
                        continue
                    candidate = available_map.get(prop_id)
                    if candidate:
                        properties.append(candidate)
                        existing_keys.add(prop_id)
                if properties:
                    properties.sort(key=lambda item: str(item.get("display_name", "")).lower())
                self._panel_manual_properties[key] = manual_entry

                if not properties:
                    if available:
                        placeholder_context = dict(context or {})
                        placeholder_context["placeholder"] = "no-keyframes"
                        placeholder_label = translate("No Keyframes")
                        placeholder_prop = {
                            "display_name": placeholder_label,
                            "points": [],
                            "placeholder": True,
                        }
                        info = {
                            "item_id": item_id,
                            "item_type": item_type,
                            "properties": [placeholder_prop],
                            "context": placeholder_context,
                            "available_properties": available,
                            "base_properties": {},
                            "base_context": self._panel_capture_base_context(placeholder_context),
                        }
                        new_props[key] = info
                        new_heights[key] = self._panel_height_for_properties(1)
                        continue
                    continue

                info = {
                    "item_id": item_id,
                    "item_type": item_type,
                    "properties": properties,
                    "context": context,
                    "available_properties": available,
                    "base_properties": self._panel_capture_base_properties(properties),
                    "base_context": self._panel_capture_base_context(context),
                }
                new_props[key] = info
                new_heights[key] = self._panel_height_for_properties(len(properties))
                continue

            grouped_props = {}
            combined_available = self._panel_multi_available_map(entries)
            for entry in entries:
                item_id = entry["item_id"]
                item_type = entry["item_type"]
                context = dict(entry.get("context") or {})
                context["track"] = key
                for prop in entry.get("properties") or []:
                    if not isinstance(prop, dict):
                        continue
                    base_key = str(prop.get("key") or uuid.uuid4())
                    row = grouped_props.get(base_key)
                    if row is None:
                        row = {
                            "key": base_key,
                            "panel_key": base_key,
                            "display_name": prop.get("display_name") or base_key,
                            "points": [],
                            "min_value": prop.get("min_value"),
                            "max_value": prop.get("max_value"),
                            "owner_type": prop.get("owner_type"),
                            "source_meta": prop.get("source_meta"),
                            "value": prop.get("value"),
                            "value_type": prop.get("value_type"),
                            "point_paths": [],
                            "context": {"item_type": "multi", "track": key},
                        }
                        grouped_props[base_key] = row

                    row_point_paths = row.get("point_paths") or []
                    row_paths_seen = {tuple(path) for path in row_point_paths if isinstance(path, (tuple, list))}
                    for path in prop.get("point_paths") or []:
                        try:
                            tuple_path = tuple(path)
                        except TypeError:
                            continue
                        if tuple_path in row_paths_seen:
                            continue
                        row_paths_seen.add(tuple_path)
                        row_point_paths.append(tuple_path)
                    row["point_paths"] = row_point_paths

                    source_meta = prop.get("source_meta")
                    for point in prop.get("points") or []:
                        if not isinstance(point, dict):
                            continue
                        merged_point = dict(point)
                        merged_point["_panel_context"] = dict(context)
                        merged_point["_panel_source_meta"] = (
                            dict(source_meta) if isinstance(source_meta, dict) else source_meta
                        )
                        row["points"].append(merged_point)

            combined_props = list(grouped_props.values())
            if combined_props:
                manual_entry = self._panel_multi_manual_entry(key, combined_available)
                existing_multi_keys = {
                    str(row.get("key"))
                    for row in combined_props
                    if isinstance(row, dict) and row.get("key") is not None
                }
                for prop_id in sorted(manual_entry["properties"], key=lambda v: str(v).lower()):
                    if prop_id in existing_multi_keys:
                        continue
                    entry_obj = combined_available.get(prop_id)
                    if not isinstance(entry_obj, dict):
                        continue
                    combined_props.append(self._panel_multi_row_from_available(key, prop_id, entry_obj))

                for row in combined_props:
                    row["points"].sort(
                        key=lambda point: (
                            self._panel_float(point.get("seconds"), 0.0),
                            self._panel_float(point.get("frame"), 0.0),
                        )
                    )
                combined_props.sort(key=lambda item: str(item.get("display_name", "")).lower())
                multi_context = {"item_type": "multi", "track": key}
                info = {
                    "item_id": "",
                    "item_type": "multi",
                    "properties": combined_props,
                    "context": multi_context,
                    "available_properties": sorted(
                        combined_available.values(),
                        key=lambda entry: str(entry.get("display_name") or entry.get("key") or "").lower(),
                    ),
                    "base_properties": self._panel_capture_base_properties(combined_props),
                    "base_context": {},
                }
                new_props[key] = info
                new_heights[key] = self._panel_height_for_properties(len(combined_props))
            else:
                # Multi-selection with no grouped rows at this frame still
                # needs available properties for the context menu.
                available_multi = sorted(
                    combined_available.values(),
                    key=lambda entry: str(entry.get("display_name") or entry.get("key") or "").lower(),
                )
                _, manual_rows = self._panel_multi_manual_rows(key, combined_available)

                if manual_rows:
                    manual_rows.sort(key=lambda row: str(row.get("display_name") or "").lower())
                    info = {
                        "item_id": "",
                        "item_type": "multi",
                        "properties": manual_rows,
                        "context": {"item_type": "multi", "track": key},
                        "available_properties": available_multi,
                        "base_properties": self._panel_capture_base_properties(manual_rows),
                        "base_context": {},
                    }
                    height = self._panel_height_for_properties(len(manual_rows))
                else:
                    placeholder_label = translate("No Keyframes")
                    placeholder_prop = {"display_name": placeholder_label, "points": [], "placeholder": True}
                    info = {
                        "item_id": "",
                        "item_type": "multi",
                        "properties": [placeholder_prop],
                        "context": {"item_type": "multi", "track": key, "placeholder": "no-keyframes"},
                        "available_properties": available_multi,
                        "base_properties": {},
                        "base_context": {},
                    }
                    height = self._panel_height_for_properties(1)
                new_props[key] = info
                new_heights[key] = height
        missing_tracks = enabled_tracks - set(new_props.keys())
        if missing_tracks:
            for track_num in sorted(missing_tracks):
                track_entries = grouped_entries.get(track_num, [])
                has_track_selection = bool(track_entries)
                reason = "no-keyframes" if has_track_selection else "no-selection"
                label = translate("No Keyframes") if has_track_selection else translate("No Selection")
                info, height = _placeholder_info(label, reason)
                new_props[track_num] = info
                new_heights[track_num] = height

        changed = new_props != self._panel_properties or new_heights != self._panel_heights
        if changed:
            enabled_tracks = [
                self.normalize_track_number(track)
                for track, state in self._track_panel_enabled.items()
                if state
            ]
            log.info(
                "Keyframe panel refresh: frame=%s selection=%s enabled_tracks=%s",
                frame,
                len(selection),
                enabled_tracks,
            )
            for track_num in sorted(new_props.keys()):
                info = new_props[track_num]
                context = info.get("context") or {}
                props = info.get("properties", [])
                if context.get("placeholder"):
                    log.info(
                        "  track %s placeholder (%s): message=%s",
                        track_num,
                        context.get("placeholder"),
                        props[0].get("display_name") if props else "",
                    )
                    continue
                prop_names = [prop.get("display_name") for prop in props]
                log.info(
                    "  track %s item %s (%s): properties=%s",
                    track_num,
                    info.get("item_id"),
                    info.get("item_type"),
                    prop_names,
                )
        elif not selection and any(self._track_panel_enabled.values()):
            log.info("Keyframe panel refresh: no selection while panels enabled")
        self._panel_properties = new_props
        self._panel_heights = new_heights
        self._panel_refresh_signature = self._panel_current_signature()
        self._refresh_panel_selection_state(new_props)
        if hasattr(self, "_panel_manual_properties"):
            filtered_manual = {}
            for track_key, entry in self._panel_manual_properties.items():
                info = new_props.get(track_key)
                context = info.get("context") if isinstance(info, dict) else None
                if not info:
                    continue
                if isinstance(info, dict) and info.get("item_type") == "multi":
                    filtered_manual[track_key] = entry
                    continue
                if isinstance(context, dict) and context.get("placeholder"):
                    continue
                filtered_manual[track_key] = entry
            self._panel_manual_properties = filtered_manual
        return changed
