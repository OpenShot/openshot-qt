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
from PyQt5.QtCore import QPointF, QRectF, Qt, QTimer
from classes.app import get_app
from classes.logger import log
from classes.query import Clip, Transition, Effect


class KeyframePanelMixin:
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
        key = prop.get("key")
        if key:
            return key
        name = prop.get("display_name")
        if name:
            return name
        return str(id(prop))

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
            context = self.get_track_panel_context(track_num)
            toggle_rect = self._track_toggle_rect(track, name_rect)
            indent = 0.0
            if not toggle_rect.isNull():
                indent = max(0.0, toggle_rect.x() - name_rect.x())
            y = panel_rect.y() + padding
            for prop in properties:
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
        for point in prop.get("points") or []:
            seconds = point.get("seconds")
            if seconds is None:
                continue
            marker_rect = self._panel_marker_rect(lane_rect, lane_padding, seconds)
            if marker_rect.contains(pos):
                info = dict(lane)
                info["point"] = point
                info["marker_rect"] = marker_rect
                return info
        return None

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

        for entry in entries or []:
            add_target(entry.get("original_seconds"))

        selected_frames = {
            entry.get("original_frame")
            for entry in entries
            if entry.get("original_frame") is not None
        }
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
            for point in other_prop.get("points") or []:
                seconds = point.get("seconds")
                if seconds is None:
                    continue
                add_target(seconds)

        if isinstance(context, dict):
            range_start = context.get("range_start_seconds")
            range_end = context.get("range_end_seconds")
            if range_start is not None:
                add_target(range_start)
            if range_end is not None:
                add_target(range_end)

        self._ensure_keyframe_markers()
        for marker in getattr(self, "_keyframe_markers", []):
            absolute = self._marker_absolute_seconds(marker)
            if absolute is None:
                continue
            add_target(absolute)

        snap_helper = getattr(self, "snap", None)
        if snap_helper and hasattr(snap_helper, "keyframe_snap_seconds"):
            for entry in snap_helper.keyframe_snap_seconds(include_playhead=False):
                if isinstance(entry, dict):
                    add_target(entry.get("seconds"), entry.get("tolerance"))
                else:
                    add_target(entry)

        return targets

    def _panel_snap_seconds(self, drag, seconds):
        if not self.enable_snapping:
            return seconds
        targets = drag.get("snap_targets") or []
        if not targets:
            return seconds
        pps = float(self.pixels_per_second or 0.0)
        if pps <= 0.0:
            return seconds
        tolerance_px = 0.0
        snap_helper = getattr(self, "snap", None)
        if snap_helper and hasattr(snap_helper, "_snap_tolerance_px"):
            try:
                tolerance_px = float(snap_helper._snap_tolerance_px())
            except (TypeError, ValueError):
                tolerance_px = 0.0
        if tolerance_px <= 0.0:
            return seconds
        tolerance_sec = tolerance_px / pps
        best = None
        min_diff = None
        for target in targets:
            tolerance_override = None
            if isinstance(target, dict):
                target_seconds = target.get("seconds")
                tolerance_override = target.get("tolerance")
            else:
                target_seconds = target
            try:
                value = float(target_seconds)
            except (TypeError, ValueError):
                continue
            local_tol = tolerance_sec
            if tolerance_override is not None:
                try:
                    override = float(tolerance_override)
                except (TypeError, ValueError):
                    override = None
                if override and override > 0.0:
                    local_tol = override
            diff = abs(value - seconds)
            if diff > local_tol + 1e-9:
                continue
            if min_diff is None or diff < min_diff:
                min_diff = diff
                best = value
        if best is None:
            return seconds
        return best

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
        try:
            position = float(context.get("position", 0.0) or 0.0)
        except (TypeError, ValueError):
            position = 0.0
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
                    track_map[prop_key] = set(new_frames)
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

    def _panel_resolve_owner(self, prop, context):
        source_meta = prop.get("source_meta") if isinstance(prop, dict) else {}
        if not isinstance(source_meta, dict):
            source_meta = {}
        owner_hint = source_meta.get("owner")
        clip_obj = source_meta.get("clip")
        transition_obj = source_meta.get("transition")
        effect_obj = source_meta.get("effect")
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

        selection_map = self._panel_selected_keyframes.get(track_key, {}) or {}
        selected_frames = set(selection_map.get(prop_key, set()) or set())
        normalized_frames = set()
        for val in selected_frames:
            if val is None:
                continue
            try:
                normalized_frames.add(int(val))
            except (TypeError, ValueError):
                continue
        if normalized_frames:
            selected_frames = normalized_frames
        modifiers = info.get("modifiers", Qt.NoModifier)
        ctrl_down = bool(modifiers & Qt.ControlModifier)
        if frame_int not in selected_frames:
            if ctrl_down:
                self._panel_merge_selection_map(track_key, {prop_key: {frame_int}})
                selected_frames.add(frame_int)
            else:
                selected_frames = {frame_int}
                self._panel_set_selection_map(track_key, {prop_key: {frame_int}})

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
        for key, frames in (track_map.items() if track_map else []):
            frames_set = set()
            for val in frames or []:
                if val is None:
                    continue
                try:
                    frames_set.add(int(val))
                except (TypeError, ValueError):
                    continue
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
                }
                entries.append(entry)
                if key == prop_key and candidate_frame == frame_int and anchor_entry is None:
                    anchor_entry = entry
        if not entries:
            self._panel_press_info = None
            self._dragging_panel_keyframes = None
            return

        if anchor_entry is None:
            anchor_entry = entries[0]

        owner_info = self._panel_resolve_owner(prop, context)
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
        self._panel_begin_transaction(drag)
        self._apply_panel_keyframe_delta(drag, ignore_refresh=True)

        fps_seek = drag.get("fps") or self.fps_float or 1.0
        if anchor_pending is not None and fps_seek and fps_seek > 0.0 and hasattr(self, "win"):
            frame_seek = int(round(anchor_pending * fps_seek)) + 1
            frame_seek = max(1, frame_seek)
            if hasattr(self.win, "SeekSignal"):
                self.win.SeekSignal.emit(frame_seek)
        self.update()

    def _panel_seek_to_point(self, info, point):
        if not isinstance(point, dict) or not hasattr(self, "win"):
            return

        context = info.get("context") if isinstance(info, dict) else None
        if not isinstance(context, dict):
            context = {}

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
            self.win.SeekSignal.emit(frame_seek)

    def _finish_panel_keyframe_drag(self):
        drag = self._dragging_panel_keyframes
        if not drag:
            return
        timeline = getattr(self.win, "timeline", None)
        started = drag.get("transaction_started")
        moved = drag.get("moved")
        if started:
            self._apply_panel_keyframe_delta(drag, ignore_refresh=False, force=True)
            if timeline:
                timeline.FinalizeKeyframeDrag(
                    drag.get("owner_type", "clip") or "clip",
                    drag.get("object_id", "") or "",
                )
            if moved and hasattr(self.win, "show_property_timeout"):
                QTimer.singleShot(0, self.win.show_property_timeout)
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
        prop = info.get("property")
        track_num = info.get("track")
        if not isinstance(prop, dict) or prop.get("placeholder"):
            return False
        context = info.get("context") or self.get_track_panel_context(track_num)
        prop_key = prop.get("key")
        if not prop_key:
            return False
        timeline = getattr(self.win, "timeline", None)
        if not timeline:
            log.info("Keyframe panel add skipped: no timeline backend")
            return False
        owner = self._panel_resolve_owner(prop, context)
        clip_obj = owner.get("clip")
        transition_obj = owner.get("transition")
        parent_path = self._panel_property_points_parent_path(prop)
        if parent_path is None:
            log.info("Keyframe panel add skipped: property %s missing points path", prop_key)
            return False
        try:
            parent_path = tuple(parent_path)
        except TypeError:
            parent_path = parent_path
        data_obj = None
        data_label = None
        for label, candidate in (("clip", clip_obj), ("transition", transition_obj)):
            data = getattr(candidate, "data", None)
            if isinstance(data, (dict, list)):
                target = self._resolve_data_path(data, parent_path)
                if isinstance(target, list):
                    data_obj = candidate
                    data_label = label
                    break
        if not data_obj or not isinstance(getattr(data_obj, "data", None), (dict, list)):
            log.info(
                "Keyframe panel add skipped: property %s has no writable source",
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
        for point in prop.get("points") or []:
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
        if interpolation is None:
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
            self._panel_merge_selection_map(track_num, {prop_key: {new_frame}})
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

    def _panel_preview_marker(self, marker, old_frame, new_frame, absolute_seconds):
        if not isinstance(marker, dict):
            return
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
        context = info.get("context", {})
        item_type = context.get("item_type")
        target_id = str(context.get("item_id") or context.get("clip_id") or context.get("transition_id") or "")
        if context_type == "transition":
            if item_type != "transition" or (target_id and target_id != context_id):
                return
        elif context_type == "effect":
            effect_ctx = str(context.get("item_id") or context.get("effect_id") or "")
            if item_type != "effect" or (effect_id and effect_ctx and effect_ctx != effect_id):
                return
        else:
            if item_type not in ("clip", "effect"):
                return
            if target_id and target_id != context_id and context.get("clip_id") not in (None, context_id):
                return

        properties = info.get("properties", [])
        changed = False
        new_frame_int = None
        try:
            new_frame_int = int(new_frame) if new_frame is not None else None
        except (TypeError, ValueError):
            new_frame_int = new_frame
        for prop in properties:
            prop_key = prop.get("key")
            for point in prop.get("points") or []:
                frame_val = point.get("frame")
                try:
                    frame_int = int(frame_val) if frame_val is not None else None
                except (TypeError, ValueError):
                    frame_int = None
                if frame_int is None or frame_int != old_frame:
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
                    selection = self._panel_selected_keyframes[track_num][prop_key]
                    if old_frame in selection:
                        selection.discard(old_frame)
                        if new_frame_int is not None:
                            selection.add(int(new_frame_int))
        if changed:
            self._apply_panel_selection_flags(track_num)
            self.update()

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
        track_num = self.normalize_track_number(layer) if layer is not None else None
        if track_num is None:
            return
        info = self._panel_properties.get(track_num)
        if not info:
            return
        context = info.get("context")
        if not isinstance(context, dict) or context.get("placeholder"):
            return
        item_type = context.get("item_type")
        target_id = str(context.get("item_id") or context.get("clip_id") or context.get("transition_id") or "")
        if isinstance(item, Clip):
            item_id = str(getattr(item, "id", ""))
            clip_match = str(context.get("clip_id") or "")
            if item_type == "clip":
                if target_id and target_id != item_id:
                    return
            elif item_type == "effect":
                if clip_match and clip_match != item_id:
                    return
            else:
                return
        elif isinstance(item, Transition):
            item_id = str(getattr(item, "id", ""))
            if item_type != "transition" or (target_id and target_id != item_id):
                return
        else:
            return

        base_props = info.get("base_properties")
        if base_props is None:
            base_props = self._panel_capture_base_properties(info.get("properties"))
            info["base_properties"] = base_props
        base_context = info.get("base_context")
        if base_context is None:
            base_context = self._panel_capture_base_context(context)
            info["base_context"] = base_context

        if delta_seconds:
            for key_name in ("position", "range_start_seconds", "range_end_seconds"):
                base_value = base_context.get(key_name, context.get(key_name))
                if base_value is None:
                    continue
                try:
                    context[key_name] = float(base_value) + delta_seconds
                except (TypeError, ValueError):
                    context[key_name] = base_value

        properties = info.get("properties", [])
        for prop in properties:
            key_name = self._panel_property_key(prop)
            base_points = base_props.get(key_name, []) if key_name else []
            points = prop.get("points") or []
            for index, point in enumerate(points):
                base_point = base_points[index] if index < len(base_points) else {}
                if frame_offset:
                    base_frame = base_point.get("frame")
                    if base_frame is not None:
                        try:
                            point["frame"] = int(base_frame) + frame_offset
                        except (TypeError, ValueError):
                            point["frame"] = base_frame
                if delta_seconds:
                    base_seconds = base_point.get("seconds")
                    if base_seconds is not None:
                        try:
                            new_seconds = float(base_seconds) + delta_seconds
                        except (TypeError, ValueError):
                            new_seconds = base_seconds
                        point["seconds"] = new_seconds
                        try:
                            position_val = float(context.get("position", 0.0) or 0.0)
                            point["local_seconds"] = float(new_seconds) - position_val
                        except (TypeError, ValueError):
                            pass

        if track_num in self._panel_selected_keyframes:
            updated = {}
            for prop in properties:
                prop_key = prop.get("key")
                if not prop_key:
                    continue
                selected_frames = set()
                for point in prop.get("points") or []:
                    if not point.get("selected"):
                        continue
                    frame_val = point.get("frame")
                    if frame_val is None:
                        continue
                    try:
                        selected_frames.add(int(frame_val))
                    except (TypeError, ValueError):
                        continue
                if selected_frames:
                    updated[prop_key] = selected_frames
            if updated:
                self._panel_selected_keyframes[track_num] = updated
            else:
                self._panel_selected_keyframes.pop(track_num, None)
            self._apply_panel_selection_flags(track_num)
        self.update()

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
            frames = selection.get(prop.get("key"), set()) or set()
            for point in prop.get("points") or []:
                frame = point.get("frame")
                point["selected"] = frame in frames if frame is not None else False

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
            selected = {frame for frame in current.get(prop_key, set()) if frame in frames}
            if selected:
                valid[prop_key] = selected
        if valid:
            self._panel_selected_keyframes[key] = valid
        else:
            self._panel_selected_keyframes.pop(key, None)

    def _panel_set_selection_map(self, track_num, mapping):
        key = self.normalize_track_number(track_num)
        if key is None:
            return
        cleaned = {}
        for prop_key, frames in (mapping or {}).items():
            if not prop_key or not frames:
                continue
            cleaned[prop_key] = {int(frame) for frame in frames if frame is not None}
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
        for prop_key, frames in (mapping or {}).items():
            if not prop_key or not frames:
                continue
            if prop_key not in track_map:
                track_map[prop_key] = set()
            dest = set(track_map[prop_key])
            before = set(dest)
            for frame in frames:
                if frame is None:
                    continue
                dest.add(int(frame))
            if dest != before:
                track_map[prop_key] = dest
                changed = True
        if not track_map:
            self._panel_selected_keyframes.pop(key, None)
        if changed:
            self._apply_panel_selection_flags(key)
            self.update()

    def _panel_toggle_frames(self, track_num, prop_key, frames):
        key = self.normalize_track_number(track_num)
        if key is None or not prop_key:
            return
        if key not in self._panel_selected_keyframes:
            self._panel_selected_keyframes[key] = {}
        track_map = self._panel_selected_keyframes[key]
        current = set(track_map.get(prop_key, set()))
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
            track_map[prop_key] = current
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
                if isinstance(points, list) and points:
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
                        if isinstance(channel_points, list) and channel_points:
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

        for key, prop in props.items():
            if not isinstance(prop, dict):
                continue
            metadata_keyframe = bool(prop.get("keyframe"))
            point_count_value = prop.get("points")
            declared_points = None
            if point_count_value is not None:
                try:
                    declared_points = int(point_count_value)
                except (TypeError, ValueError):
                    declared_points = None
            points, min_val, max_val, source_meta, normalized_paths = convert_points(key, prop)
            if not points and not normalized_paths:
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
            selected_frames = track_selection.get(key, set())
            if selected_frames:
                selected_frames = {int(frame) for frame in selected_frames}
            for point in points:
                frame_val = point.get("frame")
                try:
                    frame_int = int(frame_val) if frame_val is not None else None
                except (TypeError, ValueError):
                    frame_int = None
                point["frame"] = frame_int
                if selected_frames and frame_int is not None:
                    point["selected"] = frame_int in selected_frames
                else:
                    point["selected"] = False
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
        priority = {"effect": 0, "clip": 1, "transition": 2}
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

        for sel in selection:
            item_id = sel.get("id")
            item_type = sel.get("type")
            if not item_id or item_type not in priority:
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
            existing = new_props.get(key)
            if existing and priority[existing.get("item_type")] <= priority[item_type]:
                continue
            properties, context, available = self._properties_for_item(
                timeline,
                item_id,
                item_type,
                frame,
                context=context,
            )
            properties = list(properties or [])
            available = list(available or [])
            available_map = {
                str(entry.get("key")): entry
                for entry in available
                if isinstance(entry, dict) and entry.get("key") is not None
            }
            current_item_id = str(item_id)
            manual_entry = self._panel_manual_properties.get(key)
            if (
                not manual_entry
                or manual_entry.get("item_id") != current_item_id
                or manual_entry.get("item_type") != item_type
            ):
                manual_entry = {
                    "item_id": current_item_id,
                    "item_type": item_type,
                    "properties": set(),
                }
            else:
                manual_entry = {
                    "item_id": manual_entry.get("item_id", current_item_id),
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
            manual_added = []
            def _manual_sort_key(prop_id):
                entry = available_map.get(prop_id)
                if not isinstance(entry, dict):
                    return prop_id.lower()
                label = entry.get("display_name") or entry.get("key") or prop_id
                return str(label).lower()

            for prop_id in sorted(manual_entry["properties"], key=_manual_sort_key):
                if prop_id in existing_keys:
                    continue
                candidate = available_map.get(prop_id)
                if candidate:
                    manual_added.append(candidate)
                    existing_keys.add(prop_id)
            if manual_added:
                properties.extend(manual_added)
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
                        "item_id": str(item_id),
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

                cached = self._panel_properties.get(key)
                cached_props = cached.get("properties") if isinstance(cached, dict) else None
                if (
                    cached
                    and cached_props
                    and cached.get("item_id") == str(item_id)
                    and cached.get("item_type") == item_type
                ):
                    if "base_properties" not in cached:
                        cached["base_properties"] = self._panel_capture_base_properties(cached_props)
                    if "base_context" not in cached:
                        cached["base_context"] = self._panel_capture_base_context(cached.get("context"))
                    if "available_properties" not in cached:
                        cached["available_properties"] = available
                    log.info(
                        "Keyframe panel refresh: reusing cached properties for %s %s on track %s",
                        item_type,
                        item_id,
                        key,
                    )
                    new_props[key] = cached
                    cached_height = self._panel_heights.get(key)
                    if cached_height is None:
                        cached_height = self._panel_height_for_properties(len(cached_props))
                    new_heights[key] = cached_height
                    continue
                log.info(
                    "Keyframe panel refresh: no properties found for %s %s on track %s",
                    item_type,
                    item_id,
                    key,
                )
                continue
            info = {
                "item_id": str(item_id),
                "item_type": item_type,
                "properties": properties,
                "context": context,
                "available_properties": available,
                "base_properties": self._panel_capture_base_properties(properties),
                "base_context": self._panel_capture_base_context(context),
            }
            new_props[key] = info
            new_heights[key] = self._panel_height_for_properties(len(properties))
        missing_tracks = enabled_tracks - set(new_props.keys())
        if missing_tracks:
            reason = "no-selection" if not selection else "no-keyframes"
            label = translate("No Selection") if not selection else translate("No Keyframes")
            for track_num in sorted(missing_tracks):
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
                if not info or (isinstance(context, dict) and context.get("placeholder")):
                    continue
                filtered_manual[track_key] = entry
            self._panel_manual_properties = filtered_manual
        return changed
