"""
 @file
 @brief Clip and transition interaction helpers for the timeline widget.
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

import uuid
from PyQt5.QtCore import Qt, QRectF
from PyQt5.QtWidgets import QApplication
from classes.app import get_app
from classes.query import Clip, Transition
from classes.waveform import SAMPLES_PER_SECOND as WAVEFORM_SAMPLES_PER_SECOND


class ClipInteractionMixin:
    def clip_has_pending_override(self, clip):
        if not isinstance(clip, Clip):
            return False
        return clip.id in self._pending_clip_overrides

    def clip_waveform_window(self, clip):
        data = clip.data if isinstance(clip.data, dict) else {}
        start = float(data.get("start", 0.0) or 0.0)
        end = float(data.get("end", start) or start)
        if end < start:
            end = start
        overrides = None
        if isinstance(clip, Clip):
            overrides = self._pending_clip_overrides.get(clip.id)

        pending_start = start
        pending_end = end
        initial_start = start
        initial_end = end
        scale_waveform = False
        if overrides:
            pending_start = float(overrides.get("start", pending_start) or pending_start)
            pending_end = float(overrides.get("end", pending_end) or pending_end)
            initial_start = float(overrides.get("initial_start", initial_start) or initial_start)
            initial_end = float(overrides.get("initial_end", initial_end) or initial_end)
            if pending_end < pending_start:
                pending_end = pending_start
            if initial_end < initial_start:
                initial_end = initial_start
            scale_waveform = bool(overrides.get("scale"))

        samples_per_second = getattr(self, "_waveform_samples_per_second", None)
        if not samples_per_second:
            try:
                samples_per_second = int(WAVEFORM_SAMPLES_PER_SECOND)
            except Exception:
                samples_per_second = 20
            if samples_per_second <= 0:
                samples_per_second = 20
            self._waveform_samples_per_second = samples_per_second

        ui_data = data.get("ui", {}) if isinstance(data, dict) else {}
        audio_data = ui_data.get("audio_data") if isinstance(ui_data, dict) else None
        sample_count = len(audio_data) if isinstance(audio_data, list) else 0
        media_duration = 0.0
        if sample_count:
            media_duration = float(sample_count) / float(samples_per_second)

        if media_duration <= 0.0:
            media_duration = max(initial_end, pending_end, end, start, 0.0)

        clip_span = max(initial_end - initial_start, 0.0)
        tolerance = 1.0 / float(samples_per_second)
        dataset_matches_clip = (
            media_duration > 0.0
            and clip_span > 0.0
            and abs(media_duration - clip_span) <= max(tolerance, clip_span * 1e-3)
        )
        origin = initial_start if dataset_matches_clip else 0.0

        def _ratio(value, offset):
            if media_duration <= 0.0:
                return 0.0
            relative = float(value) - float(offset)
            if relative < 0.0:
                relative = 0.0
            if relative > media_duration:
                relative = media_duration
            return relative / media_duration

        start_ratio = _ratio(pending_start, origin)
        end_ratio = _ratio(pending_end, origin)
        source_start_ratio = _ratio(initial_start, origin)
        source_end_ratio = _ratio(initial_end, origin)

        if end_ratio < start_ratio:
            end_ratio = start_ratio
        if source_end_ratio < source_start_ratio:
            source_end_ratio = source_start_ratio

        return {
            "start_ratio": start_ratio,
            "end_ratio": end_ratio,
            "scale": scale_waveform,
            "source_start_ratio": source_start_ratio,
            "source_end_ratio": source_end_ratio,
        }

    def clip_waveform_cache_token(self, clip):
        data = clip.data if isinstance(clip.data, dict) else {}
        ui_data = data.get("ui", {}) if isinstance(data, dict) else {}
        audio_data = ui_data.get("audio_data") if isinstance(ui_data, dict) else None
        if isinstance(audio_data, list):
            return len(audio_data)
        return 0

    def _clip_data_dict(self, clip):
        data = getattr(clip, "data", None)
        return data if isinstance(data, dict) else {}

    def _clip_reader_dict(self, clip):
        reader = self._clip_data_dict(clip).get("reader")
        return reader if isinstance(reader, dict) else {}

    @staticmethod
    def _media_type_is_image(value):
        if not isinstance(value, str):
            return False
        return value.strip().lower() == "image"

    def _clip_is_single_image(self, clip):
        data = self._clip_data_dict(clip)
        if data.get("has_single_image"):
            return True
        if self._media_type_is_image(data.get("media_type")):
            return True
        reader = self._clip_reader_dict(clip)
        if reader.get("has_single_image"):
            return True
        if self._media_type_is_image(reader.get("media_type")):
            return True
        return False

    @staticmethod
    def _float_or_none(value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _positive_float(self, value):
        parsed = self._float_or_none(value)
        if parsed is None or parsed <= 0.0:
            return None
        return parsed

    def _clip_reader_duration_seconds(self, clip):
        data = self._clip_data_dict(clip)
        reader = self._clip_reader_dict(clip)

        duration = self._positive_float(reader.get("duration"))
        if duration is not None:
            return duration

        video_length = self._positive_float(reader.get("video_length"))
        fps_meta = reader.get("fps") if isinstance(reader.get("fps"), dict) else {}
        fps_num = self._positive_float(fps_meta.get("num"))
        fps_den = self._positive_float(fps_meta.get("den"))
        if video_length is not None and fps_num is not None and fps_den is not None and fps_den > 0.0:
            fps_value = fps_num / fps_den
            if fps_value > 0.0:
                return video_length / fps_value

        clip_duration = self._positive_float(data.get("duration"))
        if clip_duration is not None:
            return clip_duration

        start = self._float_or_none(data.get("start"))
        end = self._float_or_none(data.get("end"))
        if start is None:
            start = 0.0
        if end is None:
            end = start
        span = end - start
        return span if span > 0.0 else None

    def _startClipDrag(self):
        """Begin a drag operation on one or many selected clips/transitions."""
        e = self._last_event

        self.snap.reset()
        self._drag_moved = False
        self._drag_press_pos = e.pos() if e else None
        self._drag_threshold_met = False

        # Identify the item under the cursor (include clips and transitions)
        clicked_item = None
        for rect, item, _selected, _type in self.geometry.iter_items(reverse=True):
            if rect.contains(e.pos()):
                clicked_item = item
                break
        if clicked_item is None:
            return

        self._fix_cursor(self.cursors["hand"])

        # Each drag operation is grouped under a single undo transaction
        self._drag_transaction_id = str(uuid.uuid4())

        ctrl = bool(e.modifiers() & Qt.ControlModifier)
        already = (
            clicked_item.id in self.win.selected_clips or
            clicked_item.id in self.win.selected_transitions
        )

        if not already:
            sel_type = "transition" if isinstance(clicked_item, Transition) else "clip"
            # Replace existing selections unless the user is multi-selecting
            self.win.addSelection(clicked_item.id, sel_type, not ctrl)
            self.changed(None)

        # All selected clips and transitions participate in the drag
        self.dragging_items = [
            itm
            for _rect, itm, selected, _type in self.geometry.iter_items()
            if selected
        ]
        if not self.dragging_items:
            self.dragging_items = [clicked_item]

        # Map track number → index
        self._track_index_from_num = {
            self.normalize_track_number(t.data["number"]): idx
            for idx, t in enumerate(self.track_list)
        }
        self._track_num_from_index = {
            idx: self.normalize_track_number(t.data["number"])
            for idx, t in enumerate(self.track_list)
        }

        # Record each item’s starting position and layer index
        fps = float(self.fps_float or 0.0)
        use_frames = fps > 0.0
        self._drag_initial = {}
        for itm in self.dragging_items:
            data = itm.data if isinstance(itm.data, dict) else {}
            position = float(data.get("position", 0.0) or 0.0)
            start = float(data.get("start", 0.0) or 0.0)
            end = float(data.get("end", start) or start)
            duration = max(0.0, end - start)
            index = self._track_index_from_num.get(data.get("layer", 0), 0)

            entry = {
                "position": position,
                "index": index,
                "duration": duration,
            }

            if use_frames:
                entry["position_frames"] = int(round(position * fps))
                entry["duration_frames"] = int(round(duration * fps))

            self._drag_initial[itm.id] = entry

        # Seed pending overrides so geometry rebuilds use drag positions
        for itm in self.dragging_items:
            if isinstance(itm, Clip):
                override = self._pending_clip_overrides.setdefault(itm.id, {})
                override["position"] = float(itm.data.get("position", 0.0) or 0.0)
                override.setdefault("start", float(itm.data.get("start", 0.0) or 0.0))
                override.setdefault("end", float(itm.data.get("end", 0.0) or 0.0))
                override["layer"] = itm.data.get("layer", 0)
            elif isinstance(itm, Transition):
                override = self._pending_transition_overrides.setdefault(itm.id, {})
                override["position"] = float(itm.data.get("position", 0.0) or 0.0)
                override["start"] = float(itm.data.get("start", 0.0) or 0.0)
                override["end"] = float(itm.data.get("end", 0.0) or 0.0)
                override["layer"] = itm.data.get("layer", 0)

        # Bounding box for snapping calculations
        self.drag_bbox = self._compute_selected_bounding()

        # Horizontal offset from cursor to bbox-left
        self.drag_clip_offset = e.pos().x() - self.drag_bbox.x()

        # Starting track index
        self._drag_layer_idx_start = int(
            (e.pos().y() - self.ruler_height) / self.vertical_factor
        )

    def _dragMove(self):
        """Apply identical horizontal/vertical deltas to every dragged item."""
        if not getattr(self, "dragging_items", None):
            return
        e = self._last_event

        if not getattr(self, "_drag_threshold_met", True):
            anchor = getattr(self, "_drag_press_pos", None)
            if anchor is not None and e is not None:
                delta = e.pos() - anchor
                if delta.manhattanLength() < QApplication.startDragDistance():
                    return
            self._drag_threshold_met = True

        # -------- Horizontal delta (seconds) --------
        pps = float(self.pixels_per_second or 0.0)
        if pps <= 0.0:
            return

        new_bbox_x = e.pos().x() - self.drag_clip_offset
        delta_sec = (new_bbox_x - self.drag_bbox.x()) / pps

        # Snap horizontally ±1.5 s (pure x-axis)
        if self.enable_snapping:
            delta_sec = self._snap_delta(delta_sec)

        # -------- Vertical delta (track indexes) ----
        new_idx_under_cursor = int(
            (e.pos().y() - self.ruler_height) / self.vertical_factor
        )
        delta_idx = new_idx_under_cursor - self._drag_layer_idx_start

        # Clamp delta_idx so *all* items stay within valid index range
        orig_indices = [info["index"] for info in self._drag_initial.values()]
        if orig_indices:
            if min(orig_indices) + delta_idx < 0:
                delta_idx = -min(orig_indices)
            if max(orig_indices) + delta_idx >= len(self.track_list):
                delta_idx = (len(self.track_list) - 1) - max(orig_indices)

        # Clamp horizontal delta so all clips remain inside the timeline bounds
        start_positions = [info["position"] for info in self._drag_initial.values()]
        if start_positions:
            min_delta_sec = -min(start_positions)
            if delta_sec < min_delta_sec:
                delta_sec = min_delta_sec

        project_duration = 0.0
        project = get_app().project if get_app() else None
        if project:
            try:
                project_duration = float(project.get("duration") or 0.0)
            except Exception:
                project_duration = 0.0

        end_positions = [
            info["position"] + info.get("duration", 0.0)
            for info in self._drag_initial.values()
        ]
        if project_duration > 0.0 and end_positions:
            max_delta_sec = project_duration - max(end_positions)
            if delta_sec > max_delta_sec:
                delta_sec = max_delta_sec

        fps = float(self.fps_float or 0.0)
        frame_offset = None
        if fps > 0.0:
            frame_offset = int(round(delta_sec * fps))

            start_frames = [
                info.get("position_frames")
                for info in self._drag_initial.values()
                if info.get("position_frames") is not None
            ]
            if start_frames:
                min_frame_offset = -min(start_frames)
                if frame_offset < min_frame_offset:
                    frame_offset = min_frame_offset

            if project_duration > 0.0:
                timeline_frames = int(round(project_duration * fps))
            else:
                timeline_frames = None

            end_frames = []
            for info in self._drag_initial.values():
                start_frame = info.get("position_frames")
                if start_frame is None:
                    start_frame = int(round(info["position"] * fps))
                duration_frames = info.get("duration_frames")
                if duration_frames is None:
                    duration_frames = int(round(info.get("duration", 0.0) * fps))
                end_frames.append(start_frame + duration_frames)

            if timeline_frames is not None and end_frames:
                max_frame_offset = timeline_frames - max(end_frames)
                if frame_offset > max_frame_offset:
                    frame_offset = max_frame_offset

            delta_sec = frame_offset / fps

        # Reapply second-based bounds to account for frame rounding
        if start_positions:
            min_delta_sec = -min(start_positions)
            if delta_sec < min_delta_sec:
                delta_sec = min_delta_sec
        if project_duration > 0.0 and end_positions:
            max_delta_sec = project_duration - max(end_positions)
            if delta_sec > max_delta_sec:
                delta_sec = max_delta_sec

        # -------- Apply identical deltas ------------
        for itm in self.dragging_items:
            info = self._drag_initial[itm.id]
            start_pos_sec = info["position"]
            start_idx = info["index"]

            # New values
            if frame_offset is not None:
                start_frame = info.get("position_frames")
                if start_frame is None:
                    start_frame = int(round(start_pos_sec * fps))
                new_frame = max(0, start_frame + frame_offset)
                new_pos_sec = new_frame / fps
            else:
                new_pos_sec = start_pos_sec + delta_sec
            new_pos_sec = max(0.0, new_pos_sec)
            new_pos_sec = self._snap_time(new_pos_sec)
            new_idx = start_idx + delta_idx
            new_idx = max(0, min(new_idx, len(self.track_list) - 1))
            new_layer_num = self._track_num_from_index[new_idx]

            if (
                not getattr(self, "_drag_moved", False)
                and (
                    abs(new_pos_sec - start_pos_sec) > 1e-6
                    or new_idx != start_idx
                )
            ):
                self._drag_moved = True

            itm.data["position"] = new_pos_sec
            itm.data["layer"] = new_layer_num

            if isinstance(itm, Clip):
                override = self._pending_clip_overrides.setdefault(itm.id, {})
            else:
                override = self._pending_transition_overrides.setdefault(itm.id, {})
            override["position"] = new_pos_sec
            override["layer"] = new_layer_num

            # Update cached rect
            rect = self.geometry.calc_item_rect(itm)
            self.geometry.update_item_rect(itm, rect)
            frame_delta = frame_offset if frame_offset is not None else 0
            if delta_sec or frame_delta:
                self._panel_shift_item(itm, delta_sec, frame_delta)

        # Immediate visual feedback
        self._keyframes_dirty = True
        self.update()

    def _finishClipDrag(self):
        """Persist all moved clips/transitions and refresh geometry."""
        items = getattr(self, "dragging_items", None) or []
        moved = bool(getattr(self, "_drag_moved", False))

        if items and moved:
            self._preserve_overrides_once = True
            total = len(items)
            transaction_id = self._drag_transaction_id
            for idx, itm in enumerate(items):
                ignore_refresh = idx < total - 1
                if isinstance(itm, Transition):
                    self.update_transition_data(
                        itm.data,
                        only_basic_props=True,
                        ignore_refresh=ignore_refresh,
                        transaction_id=transaction_id,
                    )
                else:
                    self.update_clip_data(
                        itm.data,
                        only_basic_props=True,
                        ignore_reader=True,
                        ignore_refresh=ignore_refresh,
                        transaction_id=transaction_id,
                    )
        elif items and not moved:
            for itm in items:
                if isinstance(itm, Transition):
                    self._pending_transition_overrides.pop(itm.id, None)
                else:
                    self._pending_clip_overrides.pop(itm.id, None)

        self.dragging_items = []
        self._drag_transaction_id = None
        self.snap.reset()
        if moved:
            self._update_project_duration()
            self.changed(None)
        else:
            self.geometry.mark_dirty()
        self.update()
        self._release_cursor()
        if self._last_event:
            self._updateCursor(self._last_event.pos())
        self._drag_moved = False
        self._drag_press_pos = None
        self._drag_threshold_met = False

    def _compute_selected_bounding(self):
        """Return a QRectF encompassing all currently-selected clips and transitions."""
        rects = [
            rect
            for rect, _item, selected, _type in self.geometry.iter_items()
            if selected
        ]
        if not rects:
            return QRectF()
        bbox = QRectF(rects[0])
        for rect in rects[1:]:
            bbox = bbox.united(rect)
        return bbox

    def _snap_delta(self, delta_seconds):
        """
        Given a proposed horizontal delta (seconds) for the group drag, adjust it
        so the selection’s left or right edge “snaps” to the nearest clip edge
        within ±1.5 seconds.  Snapping is strictly horizontal—layer movement is
        unaffected.
        """
        original_ignore = getattr(self, "_snap_ignore_ids", set())
        try:
            ignore_ids = {
                getattr(item, "id", None)
                for item in getattr(self, "dragging_items", [])
            }
            self._snap_ignore_ids = {obj_id for obj_id in ignore_ids if obj_id is not None}
            return self.snap.snap_dx(delta_seconds)
        finally:
            self._snap_ignore_ids = original_ignore

    def _snap_trim_delta(self, delta_seconds, edge=None):
        """
        Apply drag-style snapping to a trim delta so clip edges snap just like moves.

        _startItemResize() already places the active item id in _snap_ignore_ids,
        so we only need to provide a temporary drag bbox for snap_dx.
        """
        bbox = getattr(self, "_resize_initial_rect", None)
        if not isinstance(bbox, QRectF) or bbox.isNull():
            return delta_seconds

        edge_label = edge or getattr(self, "_resize_edge", None)
        if edge_label not in ("left", "right"):
            return delta_seconds

        # Limit bbox to the moving edge to avoid snapping against the static edge
        if edge_label == "left":
            edge_px = bbox.left()
        else:
            edge_px = bbox.right()
        edge_bbox = QRectF(edge_px, bbox.y(), 0.0, bbox.height())
        if edge_bbox.height() <= 0.0:
            edge_bbox.setHeight(self.vertical_factor or 1.0)

        original_bbox = getattr(self, "drag_bbox", None)
        try:
            self.drag_bbox = edge_bbox
            return self.snap.snap_dx(delta_seconds)
        finally:
            self.drag_bbox = original_bbox

    def _startResize(self):
        if self._press_hit == "clip-edge" and self._resizing_item:
            self._startItemResize()
        elif self._press_hit == "timeline-handle":
            self._startProjectResize()
        else:
            self._resize_start = self.track_name_width

    def _resizeMove(self):
        if self._press_hit == "clip-edge" and self._resizing_item:
            self._itemResizeMove()
        elif self._press_hit == "timeline-handle":
            self._projectResizeMove()
        else:
            new_width = max(40, self._last_event.pos().x())
            if new_width != self.track_name_width:
                self.track_name_width = new_width
                self.changed(None)

    def _finishResize(self):
        if self._press_hit == "clip-edge" and self._resizing_item:
            self._finishItemResize()
        elif self._press_hit == "timeline-handle":
            self._finishProjectResize()
        else:
            pass

    def _startProjectResize(self):
        self._fix_cursor(self.cursors.get("resize_x", Qt.SizeHorCursor))
        self._project_resize_initial_duration = self._current_project_duration()
        min_duration = self._furthest_timeline_edge()
        if self.fps_float > 0:
            min_duration = max(min_duration, 1.0 / self.fps_float)
        self._project_resize_min_duration = max(0.0, min_duration)
        self._project_resize_keep_right = self._is_view_right_aligned()
        self._set_project_duration_override(self._project_resize_initial_duration)

    def _projectResizeMove(self):
        event = self._last_event
        if not event:
            return
        new_duration = self._seconds_from_x(event.pos().x())
        new_duration = max(self._project_resize_min_duration, new_duration)
        snapped = self._snap_time(new_duration)
        if snapped < self._project_resize_min_duration:
            snapped = self._project_resize_min_duration
        current_preview = getattr(self, "_project_duration_override", None)
        if current_preview is None or abs(snapped - current_preview) > 1e-4:
            self._set_project_duration_override(snapped)

    def _finishProjectResize(self):
        final_duration = getattr(self, "_project_duration_override", None)
        if final_duration is None:
            final_duration = self._project_resize_initial_duration
        final_duration = max(self._project_resize_min_duration, float(final_duration or 0.0))
        snapped = self._snap_time(final_duration)
        if snapped < self._project_resize_min_duration:
            snapped = self._project_resize_min_duration
        self._set_project_duration_override(None)
        self._project_resize_keep_right = False
        self._release_cursor()
        if abs(snapped - self._project_resize_initial_duration) <= 1e-3:
            return
        timeline = getattr(self.win, "timeline", None)
        if timeline:
            timeline.resizeTimeline(snapped)

    def _startItemResize(self):
        item = self._resizing_item
        if not item:
            return
        self.snap.reset()
        self._fix_cursor(self.cursors["resize_x"])
        world_rect = self.geometry.calc_item_rect(item)
        self._resize_initial_world_rect = QRectF(world_rect)
        rect = self.geometry.calc_item_rect(item, viewport=True)
        self._resize_initial_rect = rect
        self._resize_initial = {
            "start": float(item.data.get("start", 0.0)),
            "end": float(item.data.get("end", 0.0)),
            "position": float(item.data.get("position", 0.0)),
            "duration": float(item.data.get("duration", item.data.get("end", 0.0) - item.data.get("start", 0.0))),
        }
        self._resize_clip_max_duration = None
        self._resize_clip_is_single_image = False
        self._resize_allow_left_overflow = False
        self._resize_snap_ignore_backup = set(getattr(self, "_snap_ignore_ids", set()))
        item_id = getattr(item, "id", None)
        if item_id is not None:
            updated_ignore = set(self._resize_snap_ignore_backup)
            updated_ignore.add(item_id)
            self._snap_ignore_ids = updated_ignore
        if isinstance(item, Clip):
            max_duration = self._clip_reader_duration_seconds(item)
            if max_duration is None:
                max_duration = self._positive_float(self._resize_initial.get("duration"))
            current_end = self._resize_initial["end"]
            if max_duration is not None and current_end > max_duration:
                max_duration = current_end
            self._resize_clip_max_duration = max_duration
            self._resize_clip_is_single_image = self._clip_is_single_image(item)
            self._resize_allow_left_overflow = bool(self.enable_timing or self._resize_clip_is_single_image)
            self._timing_original_start = self._resize_initial["start"]
            self._pending_clip_overrides[item.id] = {
                "start": self._resize_initial["start"],
                "end": self._resize_initial["end"],
                "position": self._resize_initial["position"],
                "initial_start": self._resize_initial["start"],
                "initial_end": self._resize_initial["end"],
                "scale": bool(self.enable_timing),
            }
            sel_type = "clip"
        else:
            sel_type = "transition"
            self._snap_keyframe_seconds = []
        # Ensure item is selected
        self.win.addSelection(item.id, sel_type, False)

        if isinstance(item, Clip) and not self.enable_timing:
            self._update_snap_keyframe_targets(item)

    def _itemResizeMove(self):
        item = self._resizing_item
        if not item:
            return
        if isinstance(item, Transition):
            rect, start, end, position = self._compute_transition_resize(item)
        else:
            rect, start, end, position = self._compute_clip_resize(item)

        self._resize_new_start = start
        self._resize_new_end = end
        self._resize_new_position = position
        self.geometry.update_item_rect(item, rect)
        if isinstance(item, Clip):
            override = self._pending_clip_overrides.setdefault(
                item.id,
                {
                    "start": start,
                    "end": end,
                    "position": position,
                    "initial_start": self._resize_initial.get("start", start),
                    "initial_end": self._resize_initial.get("end", end),
                },
            )
            override["start"] = start
            override["end"] = end
            override["position"] = position
            override["scale"] = bool(self.enable_timing)
            self._keyframes_dirty = True
            if not self.enable_timing:
                timeline = getattr(self.win, "timeline", None)
                clip_id = getattr(item, "id", None)
                if timeline and self.fps_float and clip_id:
                    if self._resize_edge == "left":
                        frame_seconds = self._snap_time(start)
                    else:
                        frame_seconds = self._snap_time(end)
                    frame = int(round(frame_seconds * self.fps_float)) + 1
                    timeline.PreviewClipFrame(str(clip_id), max(1, frame))
                self._update_snap_keyframe_targets(item)
            else:
                self._snap_keyframe_seconds = []
        self.update()

    def _compute_transition_resize(self, item):
        event = self._last_event
        pps = self.pixels_per_second
        min_len = 1.0 / self.fps_float
        rect = self._resize_initial_rect
        world_rect = getattr(self, "_resize_initial_world_rect", rect)
        width = self._resize_initial["end"]
        pos = self._resize_initial["position"]

        if self._resize_edge == "left":
            delta_sec = (event.pos().x() - rect.left()) / pps
            if self.enable_snapping:
                delta_sec = self.snap.snap_edge(pos, delta_sec)
            max_delta = width - min_len
            if delta_sec > max_delta:
                delta_sec = max_delta
            new_position = pos + delta_sec
            new_end = width - delta_sec
            if new_position < 0:
                new_position = 0
                new_end = (pos + width) - new_position
            rect_left = self.track_name_width + new_position * pps
        else:
            delta_sec = (event.pos().x() - rect.right()) / pps
            if self.enable_snapping:
                delta_sec = self.snap.snap_edge(pos + width, delta_sec)
            min_delta = -(width - min_len)
            if delta_sec < min_delta:
                delta_sec = min_delta
            new_end = width + delta_sec
            new_position = pos
            rect_left = self.track_name_width + new_position * pps

        rect_width = new_end * pps
        geom_rect = QRectF(rect_left, world_rect.y(), rect_width, world_rect.height())
        return geom_rect, 0.0, new_end, new_position

    def _compute_clip_resize(self, item):
        event = self._last_event
        pps = float(self.pixels_per_second or 0.0)
        rect = self._resize_initial_rect
        world_rect = getattr(self, "_resize_initial_world_rect", rect)
        start = self._resize_initial["start"]
        end = self._resize_initial["end"]
        pos = self._resize_initial["position"]
        duration = self._resize_initial["duration"]
        fps = self.fps_float or 1.0
        min_len = 1.0 / fps
        max_duration = getattr(self, "_resize_clip_max_duration", None)
        allow_left_overflow = bool(getattr(self, "_resize_allow_left_overflow", False))
        single_image_resize = bool(getattr(self, "_resize_clip_is_single_image", False))
        overflow_enabled = allow_left_overflow and single_image_resize and not self.enable_timing

        if event is None or pps <= 0.0:
            geom_rect = QRectF(world_rect)
            return geom_rect, start, end, pos

        cursor_sec = self._seconds_from_x(event.pos().x())
        clip_span = max(end - start, min_len)

        if self._resize_edge == "left":
            delta_sec = cursor_sec - pos
            if self.enable_snapping:
                delta_sec = self._snap_trim_delta(delta_sec, edge="left")
            if overflow_enabled and max_duration is not None:
                extra_capacity = max(0.0, max_duration - end)
                min_delta = -start - extra_capacity
                if delta_sec < min_delta:
                    delta_sec = min_delta
            new_position = pos + delta_sec
            new_start = start + delta_sec
            new_end = end

            max_start = end - min_len
            overflow = 0.0
            if new_start < 0.0:
                overflow = -new_start
                new_start = 0.0
                if not allow_left_overflow:
                    new_position = pos - start
            if new_start > max_start:
                new_start = max_start
                new_position = pos + (max_start - start)
            if new_position < 0.0:
                diff = -new_position
                new_position = 0.0
                new_start += diff
            if overflow > 0.0 and overflow_enabled:
                target_end = new_end + overflow
                if max_duration is not None and target_end > max_duration:
                    target_end = max_duration
                new_end = target_end
            rect_left = self.track_name_width + new_position * pps
        else:
            timeline_right = pos + clip_span
            delta_sec = cursor_sec - timeline_right
            if self.enable_snapping:
                delta_sec = self._snap_trim_delta(delta_sec, edge="right")
            new_end = end + delta_sec
            new_start = start
            new_position = pos

            min_end = start + min_len
            if new_end < min_end:
                new_end = min_end
            if not self.enable_timing:
                max_end = max_duration
                if max_end is None:
                    max_end = start + duration
                if new_end > max_end:
                    new_end = max_end
            rect_left = self.track_name_width + new_position * pps

        rect_width = (new_end - new_start) * pps
        geom_rect = QRectF(rect_left, world_rect.y(), rect_width, world_rect.height())
        return geom_rect, new_start, new_end, new_position

    def _finishItemResize(self):
        item = self._resizing_item
        if not item:
            return
        start = self._resize_new_start
        end = self._resize_new_end
        position = self._resize_new_position
        if isinstance(item, Clip):
            if self.enable_timing:
                duration = end - start
                item.data["start"] = self._timing_original_start
                item.data["end"] = self._snap_time(self._timing_original_start + duration)
                item.data["position"] = self._snap_time(position)
                self.RetimeClip(item.id, item.data["end"], item.data["position"])
            else:
                item.data["start"] = self._snap_time(start)
                item.data["end"] = self._snap_time(end)
                item.data["position"] = self._snap_time(position)
                self.update_clip_data(item.data, only_basic_props=True, ignore_reader=True)
        else:
            item.data["position"] = self._snap_time(position)
            item.data["start"] = 0.0
            item.data["end"] = self._snap_time(end)
            item.data["duration"] = self._snap_time(end)
            self.update_transition_data(item.data, only_basic_props=True)

        self._resizing_item = None
        self._snap_keyframe_seconds = []
        self.snap.reset()
        if hasattr(self, "_resize_snap_ignore_backup"):
            ignore_ids = set(self._resize_snap_ignore_backup)
            del self._resize_snap_ignore_backup
        else:
            ignore_ids = set(getattr(self, "_snap_ignore_ids", set()))

        # Ensure the resized item is no longer ignored for future snaps
        item_id = getattr(item, "id", None)
        if item_id is not None and item_id in ignore_ids:
            ignore_ids.discard(item_id)
        self._snap_ignore_ids = ignore_ids
        self._update_project_duration()
        self.changed(None)
        self._release_cursor()
        if self._last_event:
            self._updateCursor(self._last_event.pos())
        if hasattr(self, "_resize_initial_world_rect"):
            del self._resize_initial_world_rect
        self._resize_clip_max_duration = None
        self._resize_allow_left_overflow = False
        self._resize_clip_is_single_image = False

    def _startBoxSelect(self):
        e = self._last_event
        ctrl_down = bool(e.modifiers() & Qt.ControlModifier)
        self.box_start = e.pos()
        panel_lane = self._panel_lane_at(self.box_start)
        if panel_lane:
            self._panel_box_track = panel_lane.get("track")
            self._panel_box_bounds = self._panel_bounds_for_track(self._panel_box_track)
            if not ctrl_down:
                self._clear_panel_selection(self._panel_box_track)
        else:
            self._panel_box_track = None
            self._panel_box_bounds = QRectF()
            if not ctrl_down:
                # Starting a new box selection clears existing selections
                self.win.clearSelections()
        self.selection_rect = QRectF()

    def _boxMove(self):
        rect = QRectF(self.box_start, self._last_event.pos()).normalized()
        if self._panel_box_track is not None:
            bounds = self._panel_box_bounds
            if isinstance(bounds, QRectF) and not bounds.isNull():
                rect = rect.intersected(bounds)
            else:
                rect = QRectF()
        self.selection_rect = rect
        self.update()

    def _finishBoxSelect(self):
        """Finalize box-select: add items intersecting the selection rectangle."""
        self.geometry.ensure()
        if self._panel_box_track is not None:
            ctrl_down = False
            if self._last_event and hasattr(self._last_event, "modifiers"):
                mods = self._last_event.modifiers()
                ctrl_down = bool(mods & Qt.ControlModifier)
            track_num = self._panel_box_track
            selection_rect = QRectF(self.selection_rect)
            frames_by_prop = {}
            if not selection_rect.isNull():
                for lane in self._iter_panel_lanes() or []:
                    if lane.get("track") != track_num:
                        continue
                    combined = lane.get("combined_rect", QRectF())
                    if combined.isNull() or not combined.intersects(selection_rect):
                        continue
                    prop = lane.get("property") or {}
                    points = prop.get("points") or []
                    if not points:
                        continue
                    lane_rect = lane.get("lane_rect", QRectF())
                    lane_padding = lane.get("lane_padding", self._panel_lane_padding())
                    selected_frames = set()
                    for point in points:
                        seconds = point.get("seconds")
                        if seconds is None:
                            continue
                        marker_rect = self._panel_marker_rect(lane_rect, lane_padding, seconds)
                        if marker_rect.intersects(selection_rect):
                            frame_val = point.get("frame")
                            if frame_val is not None:
                                try:
                                    selected_frames.add(int(frame_val))
                                except (TypeError, ValueError):
                                    continue
                    if selected_frames:
                        frames_by_prop[prop.get("key")] = selected_frames
            if ctrl_down:
                if frames_by_prop:
                    self._panel_merge_selection_map(track_num, frames_by_prop)
            else:
                self._panel_set_selection_map(track_num, frames_by_prop)
            self.selection_rect = QRectF()
            self._panel_box_track = None
            self._panel_box_bounds = QRectF()
            self.update()
            return

        # Ensure geometry is up-to-date for clip selections
        self.geometry.mark_dirty()
        self.geometry.ensure()

        # Add any item whose rect intersects selection_rect
        for rect, item, _selected, _type in self.geometry.iter_items():
            if rect.intersects(self.selection_rect):
                sel_type = "transition" if isinstance(item, Transition) else "clip"
                # False = don’t emit SelectionChanged (we’ll handle it ourselves)
                self.win.addSelection(item.id, sel_type, False)

        # Clear the box
        self.selection_rect = QRectF()

        # Recompute all clip/track geometry and repaint immediately
        self.changed(None)
        self.update()
