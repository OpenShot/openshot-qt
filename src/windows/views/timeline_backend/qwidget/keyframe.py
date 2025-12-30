"""
 @file
 @brief Keyframe building, dragging, and selection helpers.
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
from PyQt5.QtCore import QPointF, QRectF, QTimer, Qt
from PyQt5.QtGui import QColor
from classes.app import get_app
from classes.query import Clip, Transition, Effect
from classes.query import Marker
from ..colors import effect_color_qcolor


class KeyframeMixin:
    def _lookup_interpolation(self, value):
        try:
            idx = int(value)
        except (TypeError, ValueError):
            idx = 2
        if idx == 0:
            return "bezier"
        if idx == 1:
            return "linear"
        return "constant"

    def _normalize_color(self, value):
        if isinstance(value, QColor):
            col = QColor()
            col.setRgba(value.rgba())
            return col
        if isinstance(value, str):
            col = QColor(value)
            if col.isValid():
                return col
        if isinstance(value, (tuple, list)):
            try:
                r, g, b = value[:3]
                a = value[3] if len(value) > 3 else 255
                col = QColor()
                col.setRgb(int(r), int(g), int(b), int(a))
                return col
            except (TypeError, ValueError):
                return QColor()
        if isinstance(value, (int, float)):
            try:
                col = QColor()
                col.setRgba(int(value))
                return col
            except (TypeError, ValueError):
                return QColor()
        return QColor()

    def _effect_color(self, effect):
        color = self._normalize_color(effect_color_qcolor(effect))
        if not color.isValid():
            color = self._normalize_color(self.keyframe_painter.fill)
        return color

    def _keyframe_rect(self, clip_rect, seconds):
        """Return the timeline-space rectangle for a keyframe icon."""

        size = max(2, self.keyframe_painter.size)
        pixels = max(self.pixels_per_second, 0.0001)
        x = clip_rect.left() + seconds * pixels
        baseline = clip_rect.bottom() - 0.5
        top = baseline - size / 2.0
        return QRectF(x - size / 2.0, top, size, size)

    def _viewport_rect(self, rect, state):
        if not isinstance(rect, QRectF):
            rect = QRectF(rect)
        result = QRectF(rect)
        if state:
            result.translate(-state.get("h_offset", 0.0), -state.get("v_offset", 0.0))
        return result

    def _collect_keyframes_from_data(
        self,
        data,
        *,
        clip_rect,
        clip,
        transition,
        clip_start,
        clip_end,
        owner_id,
        object_type,
        selected,
        color,
        effect=None,
        object_id=None,
        override=None,
        base_path=(),
        view_state=None,
    ):
        if not isinstance(data, (dict, list)):
            return []

        if not isinstance(clip_rect, QRectF):
            clip_rect = QRectF(clip_rect)

        clip_rect_timeline = QRectF(clip_rect)
        view_state = view_state or self.geometry._current_view_state()
        clip_rect_view = self._viewport_rect(clip_rect_timeline, view_state)

        fps = self.fps_float or 1.0
        duration = max(0.0, clip_end - clip_start)
        override = override or {}
        initial_start = float(override.get("initial_start", clip_start) or clip_start)
        initial_end = float(override.get("initial_end", clip_end) or clip_end)
        initial_duration = max(0.0, initial_end - initial_start)
        scale_override = bool(override.get("scale")) and initial_duration > 0 and duration > 0
        show_outside = bool(override.get("show_outside"))
        markers = {}

        skip_keys = {"effects", "ui", "reader", "cache"}

        def store(frame_value, interpolation_value, point_obj=None, point_path=None):
            if frame_value is None:
                return
            try:
                frame_float = float(frame_value)
            except (TypeError, ValueError):
                return
            seconds_abs = frame_float - 1.0
            seconds_abs /= fps
            dimmed = False
            if scale_override:
                normalized = (seconds_abs - initial_start) / initial_duration
                if normalized < 0.0:
                    normalized = 0.0
                if normalized > 1.0:
                    normalized = 1.0
                local_seconds = normalized * duration
            else:
                local_seconds = seconds_abs - clip_start
                if not show_outside:
                    if local_seconds < -1e-6 or local_seconds > duration + 1e-6:
                        return
                elif local_seconds < -1e-6 or local_seconds > duration + 1e-6:
                    dimmed = True
            frame_int = int(round(frame_float))
            previous = markers.get(frame_int)
            path_value = None
            if point_path is not None:
                try:
                    path_value = tuple(point_path)
                except TypeError:
                    path_value = None

            previous_paths = []
            if previous:
                stored_paths = previous.get("paths")
                if isinstance(stored_paths, (list, tuple)):
                    previous_paths.extend(stored_paths)
                prev_single = previous.get("path")
                if prev_single is not None and prev_single not in previous_paths:
                    previous_paths.append(prev_single)
                if path_value is not None and path_value not in previous_paths:
                    previous_paths.append(path_value)
                if previous_paths:
                    previous["paths"] = tuple(previous_paths)
                    if len(previous_paths) == 1:
                        previous["path"] = previous_paths[0]
                    else:
                        previous["path"] = None
                elif "paths" in previous:
                    previous.pop("paths", None)
                if previous["selected"] and not selected:
                    return
            entry_paths = list(previous_paths)
            if not previous and path_value is not None:
                entry_paths.append(path_value)
            color_value = None
            if isinstance(point_obj, dict):
                for key in ("color", "colour", "icon_color"):
                    val = point_obj.get(key)
                    if val:
                        color_value = val
                        break
                if not color_value:
                    ui_data = point_obj.get("ui") if isinstance(point_obj.get("ui"), dict) else None
                    if ui_data:
                        for key in ("color", "colour", "icon_color"):
                            val = ui_data.get(key)
                            if val:
                                color_value = val
                                break
            entry = {
                "frame": frame_int,
                "seconds": local_seconds,
                "display_seconds": max(0.0, min(local_seconds, duration)) if duration > 0 else 0.0,
                "interpolation": self._lookup_interpolation(interpolation_value),
                "selected": bool(selected),
                "dimmed": dimmed,
            }
            if not color_value and previous:
                color_value = previous.get("color")
            if color_value:
                entry["color"] = color_value
            if entry_paths:
                entry["paths"] = tuple(entry_paths)
                if len(entry_paths) == 1:
                    entry["path"] = entry_paths[0]
            markers[frame_int] = entry

        def walk(obj, path):
            if isinstance(obj, dict):
                points = obj.get("Points")
                if isinstance(points, list) and len(points) > 1:
                    base_path = path + (("dict", "Points"),)
                    for index, point in enumerate(points):
                        co = point.get("co", {}) if isinstance(point, dict) else {}
                        store(
                            co.get("X"),
                            point.get("interpolation"),
                            point,
                            base_path + (("list", index),),
                        )
                red = obj.get("red")
                if isinstance(red, dict):
                    red_points = red.get("Points")
                    if isinstance(red_points, list) and len(red_points) > 1:
                        base_path = path + (("dict", "red"), ("dict", "Points"))
                        for index, point in enumerate(red_points):
                            co = point.get("co", {}) if isinstance(point, dict) else {}
                            store(
                                co.get("X"),
                                point.get("interpolation"),
                                point,
                                base_path + (("list", index),),
                            )
                for key, value in obj.items():
                    if key in skip_keys:
                        continue
                    if isinstance(value, (dict, list)):
                        walk(value, path + (("dict", key),))
            elif isinstance(obj, list):
                for index, item in enumerate(obj):
                    if isinstance(item, (dict, list)):
                        walk(item, path + (("list", index),))

        try:
            initial_path = tuple(base_path)
        except TypeError:
            initial_path = ()
        walk(data, initial_path)

        if not markers:
            return []

        object_id = object_id or (
            str(getattr(clip, "id", ""))
            if clip
            else str(getattr(transition, "id", owner_id))
        )
        base_color = self._normalize_color(color)
        if not base_color.isValid():
            base_color = self._normalize_color(self.keyframe_painter.fill)

        result = []
        for frame, info in markers.items():
            rect_timeline = self._keyframe_rect(clip_rect_timeline, info["seconds"])
            rect_view = self._viewport_rect(rect_timeline, view_state)
            if object_type == "clip":
                color_obj = self._normalize_color(self.keyframe_painter.fill)
            else:
                color_obj = self._normalize_color(base_color)
                info_color = info.get("color")
                override = self._normalize_color(info_color)
                if override.isValid():
                    color_obj = override
                if not color_obj.isValid():
                    color_obj = self._normalize_color(self.keyframe_painter.fill)
            marker = {
                "type": object_type,
                "owner_id": str(owner_id),
                "clip": clip,
                "transition": transition,
                "effect": effect,
                "frame": info["frame"],
                "display_frame": info["frame"],
                "seconds": info["seconds"],
                "display_seconds": info.get("display_seconds", info["seconds"]),
                "interpolation": info["interpolation"],
                "selected": info["selected"],
                "color": color_obj,
                "clip_rect": QRectF(clip_rect_view),
                "clip_rect_timeline": QRectF(clip_rect_timeline),
                "clip_start": clip_start,
                "clip_end": clip_end,
                "rect": QRectF(rect_view),
                "rect_timeline": QRectF(rect_timeline),
                "object_id": str(object_id),
                "object_type": "clip" if object_type in ("clip", "effect") else "transition",
                "key": (object_type, str(owner_id), info["frame"]),
                "dimmed": info.get("dimmed", False),
            }
            if object_type == "effect":
                marker["effect_id"] = str(owner_id)
            paths = info.get("paths")
            if paths:
                try:
                    marker["data_paths"] = tuple(paths)
                except TypeError:
                    pass
                if len(paths) == 1:
                    marker["data_path"] = paths[0]
            else:
                path_value = info.get("path")
                if path_value:
                    marker["data_path"] = path_value
            result.append(marker)
        return result

    def _build_clip_keyframes(self, rect, clip, view_state):
        data = clip.data if isinstance(clip.data, dict) else {}
        base_start = float(data.get("start", 0.0) or 0.0)
        base_end = float(data.get("end", base_start) or base_start)
        if base_end < base_start:
            base_end = base_start
        clip_start = base_start
        clip_end = base_end
        override_ctx = None
        overrides = self._pending_clip_overrides.get(clip.id)
        if overrides:
            clip_start = overrides.get("start", clip_start)
            clip_end = overrides.get("end", clip_end)
            if clip_end < clip_start:
                clip_end = clip_start
            initial_start = overrides.get("initial_start", base_start)
            initial_end = overrides.get("initial_end", base_end)
            override_ctx = {
                "initial_start": initial_start,
                "initial_end": initial_end,
                "scale": bool(overrides.get("scale")),
                "show_outside": not bool(overrides.get("scale")),
            }

        clip_selected = clip.id in getattr(self.win, "selected_clips", [])
        effects = data.get("effects", []) if isinstance(data, dict) else []
        selected_effect_ids_global = self._selected_effect_ids()
        effect_selected_ids = set()
        for eff in effects:
            if not isinstance(eff, dict):
                continue
            eff_id = eff.get("id")
            eff_id_str = str(eff_id) if eff_id is not None else ""
            if not eff_id_str:
                continue
            if eff.get("selected") or eff_id_str in selected_effect_ids_global:
                effect_selected_ids.add(eff_id_str)
        if not clip_selected and not effect_selected_ids:
            return []

        markers = []
        base_selected = clip_selected and not bool(effect_selected_ids)
        markers.extend(
            self._collect_keyframes_from_data(
                data,
                clip_rect=rect,
                clip=clip,
                transition=None,
                clip_start=clip_start,
                clip_end=clip_end,
                owner_id=str(clip.id),
                object_type="clip",
                selected=base_selected,
                color=self.keyframe_painter.fill,
                object_id=str(clip.id),
                override=override_ctx,
                view_state=view_state,
            )
        )

        for eff_index, eff in enumerate(effects):
            if not isinstance(eff, dict):
                continue
            effect_id = eff.get("id")
            if effect_id is None:
                continue
            effect_id_str = str(effect_id)
            color = self._effect_color(eff)
            eff_selected = effect_id_str in effect_selected_ids
            markers.extend(
                self._collect_keyframes_from_data(
                    eff,
                    clip_rect=rect,
                    clip=clip,
                    transition=None,
                    clip_start=clip_start,
                    clip_end=clip_end,
                    owner_id=effect_id_str,
                    object_type="effect",
                    selected=eff_selected,
                    color=color,
                    effect=eff,
                    object_id=str(clip.id),
                    override=override_ctx,
                    base_path=(("dict", "effects"), ("list", eff_index)),
                    view_state=view_state,
                )
            )

        return markers

    def _build_transition_keyframes(self, rect, transition, view_state):
        if transition.id not in getattr(self.win, "selected_transitions", []):
            return []
        data = transition.data if isinstance(transition.data, dict) else {}
        clip_start = float(data.get("start", 0.0) or 0.0)
        clip_end = float(data.get("end", clip_start) or clip_start)
        if clip_end < clip_start:
            clip_end = clip_start
        return self._collect_keyframes_from_data(
            data,
            clip_rect=rect,
            clip=None,
            transition=transition,
            clip_start=clip_start,
            clip_end=clip_end,
            owner_id=str(transition.id),
            object_type="transition",
            selected=True,
            color=self.keyframe_painter.fill,
            object_id=str(transition.id),
            view_state=view_state,
        )

    def _refresh_keyframe_markers(self):
        self.geometry.ensure()
        state = self.geometry._current_view_state()

        markers = []
        for rect, clip, _selected in self.geometry.iter_clips(viewport=False):
            markers.extend(self._build_clip_keyframes(rect, clip, state))
        for rect, tran, _selected in self.geometry.iter_transitions(viewport=False):
            markers.extend(self._build_transition_keyframes(rect, tran, state))

        drag = self._dragging_keyframe
        if drag and drag.get("key") and markers:
            pending_seconds = drag.get("pending_seconds")
            pending_frame = drag.get("pending_frame")
            for marker in markers:
                if marker.get("key") == drag.get("key"):
                    if pending_seconds is not None:
                        marker["seconds"] = pending_seconds
                        marker["display_seconds"] = pending_seconds
                        clip_timeline = marker.get(
                            "clip_rect_timeline", marker.get("clip_rect")
                        )
                        if isinstance(clip_timeline, QRectF) and not clip_timeline.isNull():
                            rect_timeline = self._keyframe_rect(
                                clip_timeline, pending_seconds
                            )
                            marker["rect_timeline"] = QRectF(rect_timeline)
                            marker["rect"] = self._viewport_rect(rect_timeline, state)
                            marker["clip_rect"] = self._viewport_rect(
                                clip_timeline, state
                            )
                        else:
                            marker["rect"] = self._keyframe_rect(
                                marker.get("clip_rect", QRectF()), pending_seconds
                            )
                        marker["dimmed"] = False
                    if pending_frame is not None:
                        marker["display_frame"] = pending_frame
                    break

        self._keyframe_markers = markers
        self._keyframes_dirty = False
        self._update_keyframe_marker_viewports(state)

    def _ensure_keyframe_markers(self):
        if self._keyframes_dirty:
            self._refresh_keyframe_markers()
        else:
            self._update_keyframe_marker_viewports()

    def _update_keyframe_marker_viewports(self, state=None):
        markers = getattr(self, "_keyframe_markers", [])
        state = state or self.geometry._current_view_state()
        offsets = (
            state.get("h_offset", 0.0),
            state.get("v_offset", 0.0),
        )
        if offsets == getattr(self, "_keyframe_marker_offsets", (None, None)):
            return

        for marker in markers or []:
            clip_rect_tl = marker.get("clip_rect_timeline")
            if isinstance(clip_rect_tl, QRectF) and not clip_rect_tl.isNull():
                marker["clip_rect"] = self._viewport_rect(clip_rect_tl, state)
            else:
                clip_rect = marker.get("clip_rect")
                if isinstance(clip_rect, QRectF) and not clip_rect.isNull():
                    marker["clip_rect"] = self._viewport_rect(clip_rect, state)

            rect_tl = marker.get("rect_timeline")
            if isinstance(rect_tl, QRectF) and not rect_tl.isNull():
                marker["rect"] = self._viewport_rect(rect_tl, state)
            else:
                clip_rect_tl = marker.get("clip_rect_timeline")
                if isinstance(clip_rect_tl, QRectF) and not clip_rect_tl.isNull():
                    rect_tl = self._keyframe_rect(
                        clip_rect_tl, marker.get("seconds", 0.0)
                    )
                    marker["rect_timeline"] = QRectF(rect_tl)
                    marker["rect"] = self._viewport_rect(rect_tl, state)

        self._keyframe_marker_offsets = offsets

    def _update_snap_keyframe_targets(self, clip):
        if not isinstance(clip, Clip) or self.enable_timing:
            self._snap_keyframe_seconds = []
            return

        clip_id = getattr(clip, "id", None)
        if clip_id is None:
            self._snap_keyframe_seconds = []
            return

        overrides = self._pending_clip_overrides.get(clip.id)
        position = None
        if overrides:
            position = overrides.get("position")
        if position is None:
            position = clip.data.get("position", 0.0)
        try:
            position = float(position)
        except (TypeError, ValueError):
            position = 0.0

        self._ensure_keyframe_markers()
        clip_id_str = str(clip_id)
        seconds = []
        active_edge = getattr(self, "_resize_edge", None)
        frame_epsilon = 0.0
        if self.fps_float:
            frame_epsilon = 1.0 / float(self.fps_float)

        for marker in getattr(self, "_keyframe_markers", []):
            if marker.get("object_id") != clip_id_str:
                continue
            marker_seconds = marker.get("display_seconds", marker.get("seconds"))
            if marker_seconds is None:
                continue
            try:
                local_seconds = float(marker_seconds)
            except (TypeError, ValueError):
                continue
            if active_edge == "left":
                epsilon = frame_epsilon if frame_epsilon > 0.0 else 1e-6
                if local_seconds <= epsilon + 1e-9:
                    # Skip the keyframe that sits at the clip's first frame when
                    # trimming from the left edge so we don't continually snap back
                    # to the original in-point before the user has moved away from
                    # it. Other keyframes (including ones very near the start) are
                    # still considered.
                    continue

            seconds.append(position + local_seconds)

        seconds.sort()
        self._snap_keyframe_seconds = seconds

    def _get_keyframe_at(self, pos):
        self._ensure_keyframe_markers()
        for marker in reversed(self._keyframe_markers):
            rect = marker.get("rect")
            if isinstance(rect, QRectF) and rect.contains(pos):
                return marker
        return None

    def _clamp_keyframe_seconds(self, seconds, clip_start, clip_end):
        max_sec = clip_end
        if self.fps_float:
            max_sec = max(clip_start, clip_end - (1.0 / self.fps_float))
        if seconds < clip_start:
            seconds = clip_start
        if seconds > max_sec:
            seconds = max_sec
        return seconds

    def _move_keyframes_in_object(self, obj, old_frame, new_frame):
        if isinstance(obj, dict):
            points = obj.get("Points")
            if isinstance(points, list):
                for point in points:
                    if not isinstance(point, dict):
                        continue
                    co = point.get("co")
                    if isinstance(co, dict):
                        x_val = co.get("X")
                        try:
                            frame = int(round(float(x_val)))
                        except (TypeError, ValueError):
                            continue
                        if frame == old_frame:
                            co["X"] = new_frame
            for channel in ("red", "green", "blue"):
                chan = obj.get(channel)
                if isinstance(chan, dict):
                    self._move_keyframes_in_object(chan, old_frame, new_frame)
            for key, value in obj.items():
                if key in ("ui",):
                    continue
                if isinstance(value, (dict, list)):
                    self._move_keyframes_in_object(value, old_frame, new_frame)
        elif isinstance(obj, list):
            for item in obj:
                if isinstance(item, (dict, list)):
                    self._move_keyframes_in_object(item, old_frame, new_frame)

    def _keyframe_base_position(self, info):
        clip = None
        transition = None
        if isinstance(info, dict):
            clip = info.get("clip")
            transition = info.get("transition")
        else:
            clip = getattr(info, "clip", None)
            transition = getattr(info, "transition", None)

        base_position = 0.0
        if clip:
            data = clip.data if isinstance(clip.data, dict) else {}
            try:
                base_position = float(data.get("position", 0.0) or 0.0)
            except (TypeError, ValueError):
                base_position = 0.0
        elif transition:
            data = transition.data if isinstance(transition.data, dict) else {}
            try:
                base_position = float(data.get("position", 0.0) or 0.0)
            except (TypeError, ValueError):
                base_position = 0.0
        return base_position

    def _marker_absolute_seconds(self, marker):
        if not isinstance(marker, dict):
            return None
        seconds = marker.get("seconds")
        if seconds is None:
            seconds = marker.get("display_seconds")
        try:
            local = float(seconds)
        except (TypeError, ValueError):
            return None
        base_position = self._keyframe_base_position(marker)
        return base_position + local

    def _compute_keyframe_snap_targets(self, marker):
        if marker is None:
            return []
        self._ensure_keyframe_markers()
        targets = []
        seen = set()

        def add_target(seconds, tolerance=None):
            try:
                value = float(seconds)
            except (TypeError, ValueError):
                return
            if value < 0.0:
                value = 0.0
            key = round(value, 6)
            if key in seen:
                return
            seen.add(key)
            if tolerance is not None:
                try:
                    tol = float(tolerance)
                except (TypeError, ValueError):
                    tol = None
                if tol and tol > 0.0:
                    targets.append({"seconds": value, "tolerance": tol})
                    return
            targets.append(value)

        current_key = marker.get("key")
        for other in getattr(self, "_keyframe_markers", []):
            if other is marker:
                continue
            if current_key is not None and other.get("key") == current_key:
                continue
            absolute = self._marker_absolute_seconds(other)
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

        clip_obj = marker.get("clip") if isinstance(marker, dict) else None
        if isinstance(clip_obj, Clip):
            clip_data = clip_obj.data if isinstance(clip_obj.data, dict) else {}
            try:
                clip_position = float(clip_data.get("position", 0.0) or 0.0)
            except (TypeError, ValueError):
                clip_position = 0.0
            try:
                clip_start = float(clip_data.get("start", 0.0) or 0.0)
            except (TypeError, ValueError):
                clip_start = 0.0
            try:
                clip_end = float(clip_data.get("end", clip_start) or clip_start)
            except (TypeError, ValueError):
                clip_end = clip_start
            if clip_end < clip_start:
                clip_end = clip_start
            duration = clip_end - clip_start
            add_target(clip_position)
            if duration > 0.0:
                add_target(clip_position + duration)

        transition_obj = marker.get("transition") if isinstance(marker, dict) else None
        if isinstance(transition_obj, Transition):
            tran_data = transition_obj.data if isinstance(transition_obj.data, dict) else {}
            try:
                tran_position = float(tran_data.get("position", 0.0) or 0.0)
            except (TypeError, ValueError):
                tran_position = 0.0
            try:
                tran_start = float(tran_data.get("start", 0.0) or 0.0)
            except (TypeError, ValueError):
                tran_start = 0.0
            try:
                tran_end = float(tran_data.get("end", tran_start) or tran_start)
            except (TypeError, ValueError):
                tran_end = tran_start
            if tran_end < tran_start:
                tran_end = tran_start
            duration = tran_end - tran_start
            add_target(tran_position)
            if duration > 0.0:
                add_target(tran_position + duration)

        for cached_seconds in getattr(self, "_snap_keyframe_seconds", []) or []:
            add_target(cached_seconds)

        return targets

    def _apply_keyframe_snapping(self, drag, local_seconds):
        if not drag or not self.enable_snapping:
            return local_seconds
        targets = drag.get("snap_targets")
        if not targets:
            return local_seconds
        pps = float(self.pixels_per_second or 0.0)
        if pps <= 0.0:
            return local_seconds
        tolerance_px = 0.0
        snap_helper = getattr(self, "snap", None)
        if snap_helper and hasattr(snap_helper, "_snap_tolerance_px"):
            try:
                tolerance_px = float(snap_helper._snap_tolerance_px())
            except (TypeError, ValueError):
                tolerance_px = 0.0
        if tolerance_px <= 0.0:
            return local_seconds
        tolerance_sec = tolerance_px / pps
        try:
            current = float(local_seconds)
        except (TypeError, ValueError):
            return local_seconds
        base_position = self._keyframe_base_position(drag)
        absolute = base_position + current
        best = None
        min_diff = None
        for target in targets:
            tolerance_override = None
            if isinstance(target, dict):
                value = target.get("seconds")
                tolerance_override = target.get("tolerance")
            else:
                value = target
            try:
                value = float(value)
            except (TypeError, ValueError):
                continue
            local_tol = tolerance_sec
            if tolerance_override is not None:
                try:
                    override = float(tolerance_override)
                except (TypeError, ValueError):
                    override = None
                if override is not None and override > 0.0:
                    local_tol = override
            diff = abs(value - absolute)
            if diff > local_tol + 1e-9:
                continue
            if min_diff is None or diff < min_diff:
                min_diff = diff
                best = value
        if best is None:
            return local_seconds
        snapped = best - base_position
        if snapped < 0.0:
            snapped = 0.0
        return snapped

    def _resolve_data_path(self, data, path):
        current = data
        if not path:
            return current
        for entry in path:
            if not isinstance(entry, tuple) or len(entry) != 2:
                return None
            kind, key = entry
            if kind == "dict":
                if isinstance(current, dict):
                    current = current.get(key)
                else:
                    return None
            elif kind == "list":
                if not isinstance(current, list):
                    return None
                try:
                    index = int(key)
                except (TypeError, ValueError):
                    return None
                if index < 0 or index >= len(current):
                    return None
                current = current[index]
            else:
                return None
            if current is None:
                return None
        return current

    def _set_keyframe_frame_at_path(self, data, path, new_frame):
        target = self._resolve_data_path(data, path)
        if not isinstance(target, dict):
            return False
        co = target.get("co")
        if not isinstance(co, dict):
            return False
        co["X"] = new_frame
        return True

    def _begin_keyframe_transaction(self):
        if not self._dragging_keyframe or self._dragging_keyframe.get("transaction_started"):
            return
        tid = str(uuid.uuid4())
        self._dragging_keyframe["transaction_started"] = True
        self._dragging_keyframe["transaction_id"] = tid
        timeline = getattr(self.win, "timeline", None)
        if timeline:
            timeline.StartKeyframeDrag(
                self._dragging_keyframe.get("object_type", "clip"),
                self._dragging_keyframe.get("object_id", ""),
                tid,
            )

    def _startKeyframeDrag(self):
        if self._press_hit == "panel-keyframe":
            info = self._panel_press_info or {}
            self._start_panel_keyframe_drag(info)
            return
        marker = self._press_keyframe
        self._press_keyframe = None
        if not marker:
            return
        self.mouse_dragging = True
        self._dragging_keyframe = {
            "marker": marker,
            "key": marker.get("key"),
            "current_frame": marker.get("frame"),
            "pending_frame": marker.get("frame"),
            "pending_seconds": marker.get("display_seconds"),
            "transaction_started": False,
            "object_type": marker.get("object_type", "clip"),
            "object_id": marker.get("object_id", ""),
            "clip": marker.get("clip"),
            "transition": marker.get("transition"),
            "effect_id": marker.get("effect_id"),
            "clip_start": marker.get("clip_start", 0.0),
            "clip_end": marker.get("clip_end", 0.0),
            "moved": False,
            "data_path": marker.get("data_path"),
            "data_paths": tuple(marker.get("data_paths", ()) or ()),
            "clear_existing": bool(getattr(self, "_press_keyframe_clear", True)),
        }
        if not self._dragging_keyframe["data_paths"] and marker.get("data_path"):
            self._dragging_keyframe["data_paths"] = (marker.get("data_path"),)
        self._dragging_keyframe["snap_targets"] = tuple(self._compute_keyframe_snap_targets(marker))
        self._fix_cursor(self.cursors.get("resize_x", Qt.SizeHorCursor))
        self._keyframes_dirty = True

    def _keyframeMove(self, event):
        if self._dragging_panel_keyframes:
            self._panel_keyframe_move(event)
            return
        drag = self._dragging_keyframe
        if not drag:
            return
        marker = drag.get("marker", {})
        clip_rect = marker.get("clip_rect", QRectF())
        clip_start = drag.get("clip_start", 0.0)
        clip_end = drag.get("clip_end", clip_start)
        if clip_rect.isNull() or clip_end <= clip_start or self.pixels_per_second <= 0:
            return

        x = event.pos().x()
        x = max(clip_rect.left(), min(x, clip_rect.right()))
        local_px = x - clip_rect.left()
        seconds = clip_start + local_px / self.pixels_per_second
        seconds = self._clamp_keyframe_seconds(seconds, clip_start, clip_end)
        relative_seconds = max(0.0, seconds - clip_start)
        relative_seconds = self._apply_keyframe_snapping(drag, relative_seconds)
        seconds = clip_start + relative_seconds
        seconds = self._clamp_keyframe_seconds(seconds, clip_start, clip_end)
        seconds = self._snap_time(seconds)
        relative_seconds = max(0.0, seconds - clip_start)
        drag["pending_seconds"] = relative_seconds
        if self.fps_float:
            new_frame = int(round(seconds * self.fps_float)) + 1
        else:
            new_frame = drag.get("current_frame")
        drag["pending_frame"] = new_frame
        absolute_seconds = self._keyframe_base_position(marker) + relative_seconds
        self._panel_preview_marker(marker, drag.get("current_frame"), new_frame, absolute_seconds)
        if new_frame != drag.get("current_frame"):
            self._begin_keyframe_transaction()
            if drag.get("transaction_started") and new_frame is not None:
                self._apply_keyframe_delta(drag, ignore_refresh=True)
        self._seek_to_marker_frame(marker, new_frame)
        self._keyframes_dirty = True
        self.update()

    def _apply_keyframe_delta(self, drag, ignore_refresh=False, force=False):
        marker = drag.get("marker")
        if not marker:
            return
        new_frame = drag.get("pending_frame")
        old_frame = drag.get("current_frame")
        if new_frame is None or old_frame is None:
            return
        do_move = new_frame != old_frame
        if not do_move and not force:
            return
        timeline = getattr(self.win, "timeline", None)
        if not timeline:
            return
        transaction_id = drag.get("transaction_id")
        data_paths = tuple(drag.get("data_paths") or ())
        data_path = drag.get("data_path") if drag.get("data_path") else None
        if marker.get("type") == "transition":
            transition = marker.get("transition")
            if not transition:
                return
            data_copy = json.loads(json.dumps(transition.data))
            moved_specific = False
            target_paths = data_paths if data_paths else (() if data_path is None else (data_path,))
            if target_paths:
                for path in target_paths:
                    if path and self._set_keyframe_frame_at_path(data_copy, path, new_frame):
                        moved_specific = True
                if (do_move or force) and isinstance(transition.data, (dict, list)) and moved_specific:
                    for path in target_paths:
                        if path:
                            self._set_keyframe_frame_at_path(transition.data, path, new_frame)
            if (do_move or force) and not moved_specific:
                self._move_keyframes_in_object(data_copy, old_frame, new_frame)
                if isinstance(transition.data, (dict, list)):
                    self._move_keyframes_in_object(transition.data, old_frame, new_frame)
            timeline.update_transition_data(
                data_copy,
                only_basic_props=False,
                ignore_refresh=ignore_refresh,
                transaction_id=transaction_id,
            )
        else:
            clip = marker.get("clip")
            if not clip:
                return
            data_copy = json.loads(json.dumps(clip.data))
            moved_specific = False
            target_paths = data_paths if data_paths else (() if data_path is None else (data_path,))
            if target_paths:
                for path in target_paths:
                    if path and self._set_keyframe_frame_at_path(data_copy, path, new_frame):
                        moved_specific = True
                if (do_move or force) and isinstance(clip.data, (dict, list)) and moved_specific:
                    for path in target_paths:
                        if path:
                            self._set_keyframe_frame_at_path(clip.data, path, new_frame)
            if (do_move or force) and not moved_specific:
                if marker.get("type") == "effect":
                    effect_id = marker.get("owner_id")
                    for eff in data_copy.get("effects", []):
                        if str(eff.get("id")) == str(effect_id):
                            self._move_keyframes_in_object(eff, old_frame, new_frame)
                            break
                    if isinstance(clip.data, dict):
                        for eff in clip.data.get("effects", []):
                            if str(eff.get("id")) == str(effect_id):
                                self._move_keyframes_in_object(eff, old_frame, new_frame)
                                break
                else:
                    self._move_keyframes_in_object(data_copy, old_frame, new_frame)
                    if isinstance(clip.data, (dict, list)):
                        self._move_keyframes_in_object(clip.data, old_frame, new_frame)
            timeline.update_clip_data(
                data_copy,
                only_basic_props=False,
                ignore_reader=True,
                ignore_refresh=ignore_refresh,
                transaction_id=transaction_id,
            )

        base_position = self._keyframe_base_position(marker)
        pending_seconds = drag.get("pending_seconds")
        if pending_seconds is None and self.fps_float:
            pending_seconds = max(0.0, ((new_frame - 1.0) / self.fps_float) - drag.get("clip_start", 0.0))
        absolute_seconds = base_position + (pending_seconds or 0.0)
        self._panel_preview_marker(marker, old_frame, new_frame, absolute_seconds)

        drag["current_frame"] = new_frame
        marker["frame"] = new_frame
        marker["display_frame"] = new_frame
        if self.fps_float:
            seconds_abs = (new_frame - 1.0) / self.fps_float
            clip_start = drag.get("clip_start", 0.0)
            marker["seconds"] = max(0.0, seconds_abs - clip_start)
            marker["display_seconds"] = marker["seconds"]
        if do_move or force:
            drag["moved"] = True

    def _select_marker_owner(self, marker, *, seek=False, clear_existing=True):
        if not marker:
            return

        marker_type = marker.get("type")
        target_id = None
        target_type = None

        if marker_type == "effect":
            target_id = marker.get("owner_id") or marker.get("effect_id")
            target_type = "effect"
        elif marker_type == "transition":
            transition = marker.get("transition")
            if transition:
                target_id = getattr(transition, "id", None)
                target_type = "transition"
        else:
            clip = marker.get("clip")
            if clip:
                target_id = getattr(clip, "id", None)
                target_type = "clip"

        if target_id is not None and target_type:
            self._select_timeline_item(target_id, target_type, clear_existing)

        if not seek:
            return

        timeline = getattr(self.win, "timeline", None)
        if not timeline:
            return

        clip = marker.get("clip")
        transition = marker.get("transition")
        clip_start = marker.get("clip_start", 0.0)
        frame = marker.get("frame", 1)
        fps = self.fps_float or 1.0
        base_position = 0.0
        if clip:
            data = clip.data if isinstance(clip.data, dict) else {}
            base_position = float(data.get("position", 0.0) or 0.0)
        elif transition:
            data = transition.data if isinstance(transition.data, dict) else {}
            base_position = float(data.get("position", 0.0) or 0.0)
        absolute = round(base_position * fps) + frame - round(clip_start * fps)
        absolute = max(1, int(absolute))
        timeline.SeekToKeyframe(absolute)

    def _handle_keyframe_click(self, marker, clear_existing=True):
        if not marker:
            return
        self._select_marker_owner(marker, seek=True, clear_existing=clear_existing)

    def _seek_to_marker_frame(self, marker, frame):
        if marker is None or frame is None:
            return
        fps = self.fps_float or 1.0
        clip = marker.get("clip")
        transition = marker.get("transition")
        clip_start = marker.get("clip_start", 0.0)
        base_position = 0.0
        if clip:
            data = clip.data if isinstance(clip.data, dict) else {}
            base_position = float(data.get("position", 0.0) or 0.0)
        elif transition:
            data = transition.data if isinstance(transition.data, dict) else {}
            base_position = float(data.get("position", 0.0) or 0.0)
        absolute = round(base_position * fps) + frame - round(clip_start * fps)
        absolute = max(1, int(absolute))
        self.win.SeekSignal.emit(absolute)

    def _finishKeyframeDrag(self):
        if self._dragging_panel_keyframes:
            self._finish_panel_keyframe_drag()
            return
        drag = self._dragging_keyframe
        if not drag:
            return
        started = drag.get("transaction_started")
        changed = drag.get("pending_frame") != drag.get("current_frame")
        moved = drag.get("moved")
        marker = drag.get("marker")
        timeline = getattr(self.win, "timeline", None)
        if started:
            if moved:
                if changed:
                    self._apply_keyframe_delta(drag)
                else:
                    self._apply_keyframe_delta(drag, force=True)
            if timeline:
                timeline.FinalizeKeyframeDrag(
                    drag.get("object_type", "clip"),
                    drag.get("object_id", ""),
                )
            if moved and hasattr(self.win, "show_property_timeout"):
                QTimer.singleShot(0, self.win.show_property_timeout)
        else:
            clear_existing = drag.get("clear_existing", True)
            self._handle_keyframe_click(marker, clear_existing=clear_existing)

        self._dragging_keyframe = None
        self.mouse_dragging = False
        self._keyframes_dirty = True
        self._release_cursor()
        self.update()
