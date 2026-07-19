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

import json
import time
import uuid
from qt_api import Qt, QRectF, QPointF
from qt_api import QApplication
from classes.app import get_app
from classes.clip_utils import is_single_image_media
from classes.query import Clip, Transition
from classes.waveform import waveform_sample_rate
from windows.views.retime import retime_clip


class ClipInteractionMixin:
    def _selected_resize_candidates(self):
        """Return selected clips/transitions from the current geometry."""
        items = []
        geometry = getattr(self, "geometry", None)
        if geometry is None or not hasattr(geometry, "iter_items"):
            return items
        for _rect, item, selected, _type in geometry.iter_items(viewport=False):
            if selected:
                items.append(item)
        return items

    def _resize_edge_value(self, item, edge):
        """Return the timeline position of the requested item's edge."""
        data = getattr(item, "data", None)
        if not isinstance(data, dict):
            return None
        try:
            position = float(data.get("position", 0.0) or 0.0)
            start = float(data.get("start", 0.0) or 0.0)
            end = float(data.get("end", start) or start)
        except (TypeError, ValueError):
            return None
        if edge == "left":
            return position
        if edge == "right":
            return position + max(0.0, end - start)
        return None

    def _resize_edge_tolerance(self):
        fps = self._positive_float(getattr(self, "fps_float", None))
        if fps:
            # Allow one-frame drift so mixed clip/transition selections keep
            # behaving as a shared edge after commit quantization.
            return max(1e-6, (1.0 / fps) + 1e-9)
        return 1e-6

    def _resize_targets_for_item(self, item, edge):
        """
        Resolve which selected items should respond to an edge resize.

        For multi-selection, only shared outer edges are resizable. Interior
        edges fall back to normal drag behavior.
        """
        if edge not in ("left", "right") or item is None:
            return []

        item_id = str(getattr(item, "id", "") or "")
        selected_items = self._selected_resize_candidates()
        selected_ids = {
            str(getattr(candidate, "id", "") or "")
            for candidate in selected_items
        }

        if item_id not in selected_ids or len(selected_items) <= 1:
            return [item]

        candidate_edge = self._resize_edge_value(item, edge)
        if candidate_edge is None:
            return []

        edge_values = []
        for candidate in selected_items:
            value = self._resize_edge_value(candidate, edge)
            if value is not None:
                edge_values.append(value)
        if not edge_values:
            return []

        outer_edge = min(edge_values) if edge == "left" else max(edge_values)
        tolerance = self._resize_edge_tolerance()
        if abs(candidate_edge - outer_edge) > tolerance:
            return []

        return [
            candidate
            for candidate in selected_items
            if abs((self._resize_edge_value(candidate, edge) or 0.0) - outer_edge) <= tolerance
        ]

    def _build_resize_context(self, item):
        """Capture the per-item baseline state used during trim/retime preview."""
        world_rect = self.geometry.calc_item_rect(item)
        rect = self.geometry.calc_item_rect(item, viewport=True)
        initial = {
            "start": float(item.data.get("start", 0.0)),
            "end": float(item.data.get("end", 0.0)),
            "position": float(item.data.get("position", 0.0)),
            "duration": float(item.data.get("duration", item.data.get("end", 0.0) - item.data.get("start", 0.0))),
        }
        context = {
            "item": item,
            "world_rect": QRectF(world_rect),
            "rect": QRectF(rect),
            "initial": initial,
            "max_duration": None,
            "clip_is_single_image": False,
            "allow_left_overflow": False,
            "static_mask": False,
        }
        if isinstance(item, Clip):
            max_duration = self._clip_reader_duration_seconds(item)
            if max_duration is None:
                max_duration = self._positive_float(initial.get("duration"))
            current_end = initial["end"]
            if max_duration is not None and current_end > max_duration:
                max_duration = current_end
            clip_is_single_image = self._clip_is_single_image(item)
            context["max_duration"] = max_duration
            context["clip_is_single_image"] = clip_is_single_image
            context["allow_left_overflow"] = bool(self.enable_timing or clip_is_single_image)
        else:
            context["static_mask"] = self._transition_uses_static_mask(item.data)
        return context

    def _clear_resize_preview_overrides(self, item):
        if isinstance(item, Transition):
            self._pending_transition_overrides.pop(item.id, None)
        else:
            self._pending_clip_overrides.pop(item.id, None)

    def _apply_resize_preview_override(self, item, context, start, end, position):
        if isinstance(item, Clip):
            override = self._pending_clip_overrides.setdefault(
                item.id,
                {
                    "start": start,
                    "end": end,
                    "position": position,
                    "initial_start": context["initial"].get("start", start),
                    "initial_end": context["initial"].get("end", end),
                    "initial_position": context["initial"].get("position", position),
                },
            )
            override["start"] = start
            override["end"] = end
            override["position"] = position
            override["scale"] = bool(self.enable_timing)
        else:
            override = self._pending_transition_overrides.setdefault(
                item.id,
                {
                    "position": position,
                    "start": start,
                    "end": end,
                    "initial_start": context["initial"].get("start", start),
                    "initial_end": context["initial"].get("end", end),
                },
            )
            override["position"] = position
            override["start"] = start
            override["end"] = end
            override["scale"] = bool(context.get("static_mask"))

    def _restore_resize_snap_ignore_ids(self, resized_items):
        if hasattr(self, "_resize_snap_ignore_backup"):
            ignore_ids = set(self._resize_snap_ignore_backup)
            del self._resize_snap_ignore_backup
        else:
            ignore_ids = set(getattr(self, "_snap_ignore_ids", set()))

        resized_ids = {
            getattr(item, "id", None)
            for item in (resized_items or [])
        }
        self._snap_ignore_ids = {
            item_id for item_id in ignore_ids if item_id not in resized_ids
        }

    def _finalize_resize_preview_state(self, resize_items, backend_refresh_requested):
        """
        End a resize gesture's preview state.

        Resize commits are now batched, so once the saves complete we can drop
        all preview overrides immediately and rebuild from committed data.
        """
        for candidate in resize_items:
            self._clear_resize_preview_overrides(candidate)
        self.changed(None)

    def _normalize_resize_commit_bounds(self, start, end, position):
        """
        Quantize resize results while preserving the snapped outer right edge.

        Snapping ``position``, ``start``, and ``end`` independently can move
        the item's timeline right edge by a frame, which breaks later
        multi-selection shared-edge detection. Snap the absolute right edge
        once, then derive ``end`` from the snapped left-side values.
        """
        snapped_position = self._snap_time(position)
        snapped_start = self._snap_time(start)
        snapped_right = self._snap_time(position + max(0.0, end - start))

        fps = float(getattr(self, "fps_float", 0.0) or 0.0)
        min_len = (1.0 / fps) if fps > 0.0 else 0.0
        snapped_span = max(min_len, snapped_right - snapped_position)
        snapped_end = self._snap_time(snapped_start + snapped_span)
        if min_len > 0.0 and snapped_end - snapped_start < min_len:
            snapped_end = snapped_start + min_len
        return snapped_start, snapped_end, snapped_position

    def _commit_resized_clip(self, clip, start, end, position, context, transaction_id, ignore_refresh):
        """Persist a resized clip, batching retime commits the same way as trims."""
        if self.enable_timing:
            initial_start = context.get("initial", {}).get("start")
            if initial_start is None:
                initial_start = start
            original_start = float(initial_start)
            duration = end - start
            target_end = self._snap_time(original_start + duration)
            target_position = self._snap_time(position)
            if not retime_clip(clip, target_end, target_position, direction=1):
                return False
            ui_data = clip.data.get("ui")
            if isinstance(ui_data, dict) and "audio_data" in ui_data:
                ui_data.pop("audio_data", None)
                ui_data.pop("audio_data_rms", None)
                ui_data.pop("audio_data_rate", None)
                ui_data.pop("audio_data_format", None)
            self.update_clip_data(
                clip.data,
                only_basic_props=False,
                ignore_reader=True,
                ignore_refresh=ignore_refresh,
                transaction_id=transaction_id,
            )
            return True

        start, end, position = self._normalize_resize_commit_bounds(start, end, position)
        clip.data["start"] = start
        clip.data["end"] = end
        clip.data["position"] = position
        self.update_clip_data(
            clip.data,
            only_basic_props=True,
            ignore_reader=True,
            ignore_refresh=ignore_refresh,
            transaction_id=transaction_id,
        )
        return True

    def _active_resize_items(self):
        """Return the items currently participating in an edge resize gesture."""
        if getattr(self, "_press_hit", "") != "clip-edge":
            return []
        items = list(getattr(self, "_resize_items", None) or [])
        if items:
            return items
        item = getattr(self, "_resizing_item", None)
        return [item] if item is not None else []

    def _is_active_resize_item(self, item):
        """Return True when *item* is part of the current edge-resize preview."""
        if item is None:
            return False
        for candidate in self._active_resize_items():
            if candidate is item:
                return True
            if getattr(candidate, "id", None) == getattr(item, "id", None):
                return True
        return False

    def _resize_preview_focus_item(self):
        """Choose the primary grabbed item for player preview updates."""
        items = list(self._active_resize_items())
        if not items:
            return None
        primary = getattr(self, "_resizing_item", None)
        if primary is not None:
            primary_id = getattr(primary, "id", None)
            for item in items:
                if item is primary or getattr(item, "id", None) == primary_id:
                    return item
        return items[0]

    def _transition_uses_static_mask(self, transition_data):
        reader = {}
        if isinstance(transition_data, dict):
            for key in ("mask_reader", "reader"):
                candidate = transition_data.get(key)
                if isinstance(candidate, dict):
                    reader = candidate
                    break
        if isinstance(reader, dict) and "has_single_image" in reader:
            return bool(reader.get("has_single_image"))
        return bool(is_single_image_media(reader))

    def _set_trim_thumbnail_suspension(self, enabled, clip_id=None):
        """Pause thumbnail generation while trimming and drop stale queued work."""
        self._suspend_thumbnail_requests = bool(enabled)
        clip_key = str(clip_id or "")
        if enabled:
            if self.thumbnail_manager:
                self.thumbnail_manager.clear_pending()
            if clip_key and hasattr(self, "clip_painter"):
                # Keep existing cached thumbs visible while trimming, but drop in-flight requests.
                self.clip_painter.invalidate_clip_thumbnails(
                    clip_key,
                    drop_cache=False,
                    drop_pending=True,
                    drop_fallback=False,
                    drop_preview=False,
                    invalidate_render_cache=False,
                )
            return

        if self.thumbnail_manager:
            self.thumbnail_manager.clear_pending()
        if clip_key and hasattr(self, "clip_painter"):
            # Preserve existing thumbnails until replacements arrive; only drop stale in-flight requests.
            self.clip_painter.invalidate_clip_thumbnails(
                clip_key,
                drop_cache=False,
                drop_pending=True,
                drop_fallback=False,
                invalidate_render_cache=False,
            )
            self.clip_painter.clear_retime_preview(clip_key)

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

        ui_data = data.get("ui", {}) if isinstance(data, dict) else {}
        samples_per_second = waveform_sample_rate(ui_data)
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
            rms_data = ui_data.get("audio_data_rms")
            return (
                len(audio_data),
                len(rms_data) if isinstance(rms_data, list) else 0,
                ui_data.get("waveform_token"),
                ui_data.get("audio_data_format"),
                ui_data.get("audio_data_rate"),
            )
        return 0

    def _clip_data_dict(self, clip):
        data = getattr(clip, "data", None)
        return data if isinstance(data, dict) else {}

    def _clip_reader_dict(self, clip):
        reader = self._clip_data_dict(clip).get("reader")
        return reader if isinstance(reader, dict) else {}

    def _clip_is_single_image(self, clip):
        data = self._clip_data_dict(clip)
        if is_single_image_media(data):
            return True
        reader = self._clip_reader_dict(clip)
        if is_single_image_media(reader):
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
        start = self._float_or_none(data.get("start"))
        if start is None:
            start = 0.0

        candidate_limits = []

        duration = self._positive_float(reader.get("duration"))
        if duration is not None:
            candidate_limits.append(duration)

        video_length = self._positive_float(reader.get("video_length"))
        fps_meta = reader.get("fps") if isinstance(reader.get("fps"), dict) else {}
        fps_num = self._positive_float(fps_meta.get("num"))
        fps_den = self._positive_float(fps_meta.get("den"))
        if video_length is not None and fps_num is not None and fps_den is not None and fps_den > 0.0:
            fps_value = fps_num / fps_den
            if fps_value > 0.0:
                candidate_limits.append(video_length / fps_value)

        project_fps = self._positive_float(getattr(self, "fps_float", None))
        time_data = data.get("time") if isinstance(data.get("time"), dict) else {}
        time_points = time_data.get("Points") if isinstance(time_data.get("Points"), list) else []
        if project_fps is not None and len(time_points) >= 2:
            x_values = []
            for point in time_points:
                if not isinstance(point, dict):
                    continue
                co = point.get("co")
                if not isinstance(co, dict):
                    continue
                x_val = self._float_or_none(co.get("X"))
                if x_val is not None:
                    x_values.append(x_val)
            if len(x_values) >= 2:
                time_duration = (max(x_values) - min(x_values)) / project_fps
                if time_duration > 0.0:
                    candidate_limits.append(start + time_duration)

        clip_duration = self._positive_float(data.get("duration"))
        if clip_duration is not None:
            candidate_limits.append(start + clip_duration)

        end = self._float_or_none(data.get("end"))
        if end is None:
            end = start
        span = end - start
        if span > 0.0:
            candidate_limits.append(end)

        return max(candidate_limits) if candidate_limits else None

    def _selection_anchor_from_item(self, item, sel_type=None):
        """Build a normalized selection anchor for clips/transitions."""
        data = item.data if isinstance(item.data, dict) else {}
        item_type = sel_type or ("transition" if isinstance(item, Transition) else "clip")
        position = float(data.get("position", 0.0) or 0.0)
        layer = int(data.get("layer", 0) or 0)
        start = float(data.get("start", 0.0) or 0.0)
        end = float(data.get("end", start) or start)
        duration = max(0.0, end - start)
        return {
            "type": item_type,
            "position": position,
            "end_position": position + duration,
            "layer": layer,
        }

    def _normalize_selection_anchor(self, anchor):
        """Convert legacy tuple anchors into the normalized anchor dict format."""
        if isinstance(anchor, dict):
            try:
                position = float(anchor.get("position", 0.0) or 0.0)
                end_position = float(anchor.get("end_position", position) or position)
                layer = int(anchor.get("layer", 0) or 0)
            except (TypeError, ValueError):
                return None
            if end_position < position:
                end_position = position
            return {
                "type": anchor.get("type"),
                "position": position,
                "end_position": end_position,
                "layer": layer,
            }

        if isinstance(anchor, (tuple, list)) and len(anchor) >= 2:
            try:
                position = float(anchor[0] or 0.0)
                layer = int(anchor[1] or 0)
            except (TypeError, ValueError):
                return None
            return {
                "type": None,
                "position": position,
                "end_position": position,
                "layer": layer,
            }

        return None

    def _startClipDrag(self):
        """Begin a drag operation on one or many selected clips/transitions."""
        e = self._last_event

        self.snap.reset()
        self._collapse_selection_on_release = False
        self._collapse_selection_target = None
        self._drag_moved = False
        self._drag_press_pos = e.position() if (e and hasattr(e, "position")) else (QPointF(e.pos()) if e else None)
        self._drag_threshold_met = False

        # Identify the item under the cursor (include clips and transitions)
        clicked_item = None
        for rect, item, _selected, _type in self.geometry.iter_items(reverse=True):
            if rect.contains(self._drag_press_pos):
                clicked_item = item
                break
        if clicked_item is None:
            return

        self._fix_cursor(self.cursors["hand"])

        # Each drag operation is grouped under a single undo transaction
        self._drag_transaction_id = str(uuid.uuid4())

        modifiers = e.modifiers()
        ctrl = bool(modifiers & Qt.ControlModifier)
        alt = bool(modifiers & Qt.AltModifier)
        shift = bool(modifiers & Qt.ShiftModifier)
        sel_type = "transition" if isinstance(clicked_item, Transition) else "clip"
        last_anchor = self._normalize_selection_anchor(getattr(self, "_last_click_pos", None))
        already = (
            clicked_item.id in self.win.selected_clips or
            clicked_item.id in self.win.selected_transitions
        )

        if alt:
            # ALT+Click: select the clicked item plus everything to its right on
            # the same layer.  CTRL+ALT keeps existing selection; plain ALT replaces.
            if not ctrl:
                self.win.clearSelections()
            self.selectRipple(clicked_item.id, sel_type)
            # ALT does not update _last_click_pos; nothing to drag.
            self.dragging_items = []
            self._drag_transaction_id = None
            self.changed(None)
            return

        elif shift and last_anchor:
            # SHIFT+Click: simple rectangular range-select between anchor and
            # click (position + layer), across both clips and transitions.
            current_anchor = self._selection_anchor_from_item(clicked_item, sel_type)
            min_pos = min(last_anchor["position"], current_anchor["position"])
            max_pos = max(last_anchor["position"], current_anchor["position"])
            min_layer = min(last_anchor["layer"], current_anchor["layer"])
            max_layer = max(last_anchor["layer"], current_anchor["layer"])
            eps = 1e-9
            matched_items = []
            for item in Clip.filter() + Transition.filter():
                d = item.data if isinstance(item.data, dict) else {}
                try:
                    item_pos = float(d.get("position", 0.0) or 0.0)
                    item_layer = int(d.get("layer", 0) or 0)
                    if (min_pos - eps <= item_pos <= max_pos + eps and
                            min_layer <= item_layer <= max_layer):
                        item_type = "transition" if isinstance(item, Transition) else "clip"
                        matched_items.append((item.id, item_type))
                except (TypeError, ValueError):
                    pass

            if not matched_items:
                # Fallback: always keep clicked item selected for this SHIFT action.
                matched_items = [(clicked_item.id, sel_type)]

            if not ctrl:
                self.win.selected_items = []

            for item_id, item_type in matched_items:
                self.win.addSelection(str(item_id), item_type, False)

            self.clip_painter.clear_render_cache()
            self.geometry.mark_dirty()
            self._keyframes_dirty = True
            self.update()

            # Keep the original anchor during SHIFT range operations.
            # This prevents repeated SHIFT press events from collapsing the
            # selection to a single clicked item.
            self.changed(None)
            # Fall through to drag setup; SHIFT+drag freezes horizontal movement.

        elif ctrl and already:
            dbl = QApplication.doubleClickInterval() / 1000.0
            just_added = (
                getattr(self, "_ctrl_just_selected_id", None) == clicked_item.id and
                time.monotonic() - getattr(self, "_ctrl_just_selected_time", 0.0) < dbl
            )
            self._ctrl_just_selected_id = None
            self._last_click_pos = self._selection_anchor_from_item(clicked_item, sel_type)
            if just_added:
                # Second press of a double-click: clip was just CTRL-added;
                # don't immediately toggle it back off — preserve selection.
                pass
            else:
                # Deliberate CTRL+Click on selected item: toggle off.
                self._ctrl_just_deselected_id = clicked_item.id
                self._ctrl_just_deselected_time = time.monotonic()
                self._deselect_timeline_item(clicked_item.id, sel_type)
                self.dragging_items = []
                self._drag_transaction_id = None
                self.changed(None)
                return

        elif not already:
            dbl = QApplication.doubleClickInterval() / 1000.0
            just_deselected = (
                ctrl and
                getattr(self, "_ctrl_just_deselected_id", None) == clicked_item.id and
                time.monotonic() - getattr(self, "_ctrl_just_deselected_time", 0.0) < dbl
            )
            self._ctrl_just_deselected_id = None
            if just_deselected:
                # Second press of a double-click: clip was just CTRL-deselected;
                # don't immediately re-add it — preserve deselected state.
                self._last_click_pos = self._selection_anchor_from_item(clicked_item, sel_type)
            else:
                # Regular click clears+selects; CTRL+click adds to selection.
                self.win.addSelection(clicked_item.id, sel_type, not ctrl)
                if ctrl:
                    self._ctrl_just_selected_id = clicked_item.id
                    self._ctrl_just_selected_time = time.monotonic()
                else:
                    self._ctrl_just_selected_id = None
                self._last_click_pos = self._selection_anchor_from_item(clicked_item, sel_type)
                self.changed(None)

        else:
            # Clicking already-selected item (no special modifier):
            # preserve multi-selection for group drag, but collapse to this
            # one item if this ends as a plain click (no drag movement).
            self._ctrl_just_selected_id = None
            self._last_click_pos = self._selection_anchor_from_item(clicked_item, sel_type)
            selected_count = (
                len(getattr(self.win, "selected_clips", []) or [])
                + len(getattr(self.win, "selected_transitions", []) or [])
            )
            if selected_count > 1:
                self._collapse_selection_on_release = True
                self._collapse_selection_target = (clicked_item.id, sel_type)

        # All selected clips and transitions participate in the drag
        self.dragging_items = [
            itm
            for _rect, itm, selected, _type in self.geometry.iter_items(viewport=False)
            if selected
        ]
        if not self.dragging_items:
            self.dragging_items = [clicked_item]
        if self._selection_overlaps_locked_tracks(self.dragging_items):
            self.dragging_items = []
            self._drag_transaction_id = None
            self._release_cursor()
            return

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
        self.drag_clip_offset = e.position().x() if hasattr(e, "position") else e.pos().x()
        self.drag_clip_offset -= self.drag_bbox.x()

        # Starting track index
        start_idx = self._track_index_at_viewport_y(
            e.position().y() if hasattr(e, "position") else e.pos().y(),
            prefer_clip_lane=True,
            snap_to_nearest=True,
        )
        self._drag_layer_idx_start = start_idx if start_idx is not None else 0

    def _dragMove(self):
        """Apply identical horizontal/vertical deltas to every dragged item."""
        if getattr(self, "_drag_commit_in_progress", False):
            return
        if not getattr(self, "dragging_items", None):
            return
        e = self._last_event

        if not getattr(self, "_drag_threshold_met", True):
            anchor = getattr(self, "_drag_press_pos", None)
            if anchor is not None and e is not None:
                delta = (e.position() if hasattr(e, "position") else QPointF(e.pos())) - anchor
                if delta.manhattanLength() < QApplication.startDragDistance():
                    return
            self._drag_threshold_met = True

        # -------- Horizontal delta (seconds) --------
        pps = float(self.pixels_per_second or 0.0)
        if pps <= 0.0:
            return

        # SHIFT+Drag: freeze horizontal movement (track-only drag), matching JS behaviour.
        shift_held = bool(e.modifiers() & Qt.ShiftModifier) if e else False
        if shift_held:
            delta_sec = 0.0
        else:
            new_bbox_x = (e.position().x() if hasattr(e, "position") else e.pos().x()) - self.drag_clip_offset
            delta_sec = (new_bbox_x - self.drag_bbox.x()) / pps

            # Snap horizontally ±1.5 s (pure x-axis)
            if self.enable_snapping:
                delta_sec = self._snap_delta(delta_sec)

        # -------- Vertical delta (track indexes) ----
        new_idx_under_cursor = self._track_index_at_viewport_y(
            e.position().y() if hasattr(e, "position") else e.pos().y(),
            prefer_clip_lane=True,
            snap_to_nearest=True,
        )
        if new_idx_under_cursor is None:
            new_idx_under_cursor = self._drag_layer_idx_start
        delta_idx = new_idx_under_cursor - self._drag_layer_idx_start

        # Clamp delta_idx so *all* items stay within valid index range
        orig_indices = [info["index"] for info in self._drag_initial.values()]
        if orig_indices:
            if min(orig_indices) + delta_idx < 0:
                delta_idx = -min(orig_indices)
            if max(orig_indices) + delta_idx >= len(self.track_list):
                delta_idx = (len(self.track_list) - 1) - max(orig_indices)

        # Clamp horizontal delta so items do not move before t=0.
        start_positions = [info["position"] for info in self._drag_initial.values()]
        if start_positions:
            min_delta_sec = -min(start_positions)
            if delta_sec < min_delta_sec:
                delta_sec = min_delta_sec

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

            delta_sec = frame_offset / fps

        # Reapply left bound to account for frame rounding
        if start_positions:
            min_delta_sec = -min(start_positions)
            if delta_sec < min_delta_sec:
                delta_sec = min_delta_sec

        # -------- Apply identical deltas ------------
        for itm in self.dragging_items:
            info = self._drag_initial[itm.id]
            start_pos_sec = info["position"]
            start_idx = info["index"]

            # New values
            if frame_offset is not None:
                new_pos_sec = start_pos_sec + (frame_offset / fps)
            else:
                new_pos_sec = start_pos_sec + delta_sec
            new_pos_sec = max(0.0, new_pos_sec)
            new_idx = start_idx + delta_idx
            new_idx = max(0, min(new_idx, len(self.track_list) - 1))
            unlocked_idx = self._nearest_unlocked_track_index(new_idx)
            if unlocked_idx is None:
                unlocked_idx = start_idx
            new_idx = unlocked_idx
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
            # Use the actual applied movement (after per-item clamping/snap-to-frame),
            # otherwise panel points can lag at the snap threshold while clip visuals
            # already snapped to the final frame-aligned position.
            applied_delta_sec = new_pos_sec - start_pos_sec
            if fps > 0.0:
                applied_frame_delta = int(round(applied_delta_sec * fps))
            else:
                applied_frame_delta = 0
            # Always apply panel shift, even for 0 delta. When snapping returns to
            # drag origin, skipping this leaves stale panel points until mouse-up.
            self._panel_shift_item(itm, applied_delta_sec, applied_frame_delta)

        # Immediate visual feedback
        self._keyframes_dirty = True
        self.update()

    def _finishClipDrag(self):
        """Persist all moved clips/transitions and refresh geometry."""
        items = list(getattr(self, "dragging_items", None) or [])
        moved = bool(getattr(self, "_drag_moved", False))
        collapse_selection = bool(getattr(self, "_collapse_selection_on_release", False))
        collapse_target = getattr(self, "_collapse_selection_target", None)

        if items and moved:
            # Freeze the drag state before dispatching any updates. Otherwise a
            # late mouse-move can still mutate the remaining selected items
            # while this save loop is running, causing them to commit to
            # different layers/positions within one drag.
            transaction_id = self._drag_transaction_id
            self._drag_commit_in_progress = True
            self.dragging_items = []
            self._drag_transaction_id = None
            self._preserve_overrides_once = True
            total = len(items)
            commit_items = []
            for itm in items:
                commit_items.append({
                    "item": itm,
                    "type": "transition" if isinstance(itm, Transition) else "clip",
                    "data": json.loads(json.dumps(itm.data)),
                })
            # Persist clips before transitions so any transition logic that
            # inspects neighboring clips sees the final clip positions.
            commit_items.sort(key=lambda entry: 1 if entry["type"] == "transition" else 0)
            try:
                for idx, entry in enumerate(commit_items):
                    itm = entry["item"]
                    ignore_refresh = idx < total - 1
                    if entry["type"] == "transition":
                        transition_data = entry["data"]
                        if total == 1 and self._transition_uses_static_mask(transition_data):
                            transition_data["_auto_direction"] = True
                        self.update_transition_data(
                            transition_data,
                            only_basic_props=True,
                            ignore_refresh=ignore_refresh,
                            transaction_id=transaction_id,
                        )
                        itm.data = transition_data
                    else:
                        clip_data = entry["data"]
                        if total == 1:
                            clip_data["_auto_transition"] = True
                        self.update_clip_data(
                            clip_data,
                            only_basic_props=True,
                            ignore_reader=True,
                            ignore_refresh=ignore_refresh,
                            transaction_id=transaction_id,
                        )
                        itm.data = clip_data
            finally:
                self._drag_commit_in_progress = False
        elif items and not moved:
            for itm in items:
                if isinstance(itm, Transition):
                    self._pending_transition_overrides.pop(itm.id, None)
                else:
                    self._pending_clip_overrides.pop(itm.id, None)

        self.dragging_items = []
        self._drag_transaction_id = None
        self.snap.reset()
        self._collapse_selection_on_release = False
        self._collapse_selection_target = None
        if moved:
            self._update_project_duration()
            self.changed(None)
        else:
            if collapse_selection and collapse_target:
                target_id, target_type = collapse_target
                self.win.addSelection(target_id, target_type, True)
                self.changed(None)
            self.geometry.mark_dirty()
        self.update()
        self._release_cursor()
        if self._last_event:
            posf = self._last_event.position() if hasattr(self._last_event, "position") else QPointF(self._last_event.pos())
            self._updateCursor(posf)
        self._drag_moved = False
        self._drag_press_pos = None
        self._drag_threshold_met = False

    def _compute_selected_bounding(self):
        """Return a QRectF encompassing all currently-selected clips and transitions."""
        rects = [
            rect
            for rect, _item, selected, _type in self.geometry.iter_items(viewport=False)
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

    def _snap_trim_delta(self, delta_seconds, edge=None, initial=None):
        """
        Apply directional edge snapping to trim deltas.

        Uses the trim edge's original timeline position (left/right) and lets
        SnapHelper.snap_edge() handle direction-aware target selection.
        """
        if initial is None:
            initial = getattr(self, "_resize_initial", None)
        if not isinstance(initial, dict):
            return delta_seconds

        edge_label = edge or getattr(self, "_resize_edge", None)
        if edge_label not in ("left", "right"):
            return delta_seconds

        if edge_label == "left":
            edge_sec = float(initial.get("position", 0.0) or 0.0)
        else:
            edge_sec = float(initial.get("position", 0.0) or 0.0)
            edge_sec += float(initial.get("end", 0.0) or 0.0) - float(initial.get("start", 0.0) or 0.0)

        return self.snap.snap_edge(edge_sec, delta_seconds)

    def _startResize(self):
        if self._press_hit == "clip-edge" and self._resizing_item:
            self._startItemResize()
        elif self._press_hit == "timeline-handle":
            self._startProjectResize()
        elif self._press_hit == "handle":
            self._resize_start = self.track_name_width

    def _resizeMove(self):
        if self._press_hit == "clip-edge" and self._resizing_item:
            self._itemResizeMove()
        elif self._press_hit == "timeline-handle":
            self._projectResizeMove()
        elif self._press_hit == "handle":
            new_width = max(40, (self._last_event.position().x() if hasattr(self._last_event, "position") else self._last_event.pos().x()))
            if new_width != self.track_name_width:
                self.track_name_width = new_width
                self.changed(None)

    def _finishResize(self):
        if self._press_hit == "clip-edge" and self._resizing_item:
            self._finishItemResize()
            if hasattr(self.win, "TimelinePreviewMode"):
                self.win.TimelinePreviewMode.emit()
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
        new_duration = self._seconds_from_x(event.position().x() if hasattr(event, "position") else event.pos().x())
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
        if self._is_track_locked((item.data if isinstance(item.data, dict) else {}).get("layer")):
            self._resizing_item = None
            self._resize_items = []
            self._resize_initial_map = {}
            self._resize_edge = None
            self._release_cursor()
            return
        if hasattr(self.win, "TrimPreviewMode"):
            self.win.TrimPreviewMode.emit()
        self.snap.reset()
        self._fix_cursor(self.cursors["resize_x"])
        resize_items = list(getattr(self, "_resize_items", None) or [item])
        self._resize_items = resize_items
        self._resize_initial_map = {}
        primary_context = None
        self._resize_clip_max_duration = None
        self._resize_clip_is_single_image = False
        self._resize_allow_left_overflow = False
        self._resize_snap_ignore_backup = set(getattr(self, "_snap_ignore_ids", set()))
        updated_ignore = set(self._resize_snap_ignore_backup)
        for candidate in resize_items:
            candidate_id = getattr(candidate, "id", None)
            if candidate_id is not None:
                updated_ignore.add(candidate_id)
            context = self._build_resize_context(candidate)
            self._resize_initial_map[candidate.id] = context
            self._apply_resize_preview_override(
                candidate,
                context,
                context["initial"]["start"],
                context["initial"]["end"],
                context["initial"]["position"],
            )
            if isinstance(candidate, Clip):
                self._set_trim_thumbnail_suspension(True, candidate.id)
            if candidate is item:
                primary_context = context
        self._snap_ignore_ids = updated_ignore
        if primary_context is None:
            primary_context = self._build_resize_context(item)
            self._resize_initial_map[item.id] = primary_context

        self._resize_initial_world_rect = QRectF(primary_context["world_rect"])
        self._resize_initial_rect = QRectF(primary_context["rect"])
        self._resize_initial = dict(primary_context["initial"])
        self._resize_clip_max_duration = primary_context.get("max_duration")
        self._resize_clip_is_single_image = bool(primary_context.get("clip_is_single_image"))
        self._resize_allow_left_overflow = bool(primary_context.get("allow_left_overflow"))
        if isinstance(item, Clip):
            self._timing_original_start = self._resize_initial["start"]
            sel_type = "clip"
        else:
            sel_type = "transition"
            self._snap_keyframe_seconds = []
        # Ensure item is selected
        self.win.addSelection(item.id, sel_type, False)

        if isinstance(item, Clip) and not self.enable_timing:
            # Rebuild markers before collecting trim snap targets.
            self._keyframes_dirty = True
            self._update_snap_keyframe_targets(item)

    def _itemResizeMove(self):
        resize_items = list(getattr(self, "_resize_items", None) or [])
        if not resize_items:
            return
        self._resize_results = {}
        preview_item = self._resize_preview_focus_item()
        preview_result = None
        primary_item = self._resizing_item if self._resizing_item in resize_items else resize_items[0]
        primary_context = self._resize_initial_map.get(getattr(primary_item, "id", None))
        shared_edge_seconds = None
        primary_result = None
        if primary_context:
            if isinstance(primary_item, Transition):
                primary_result = self._compute_transition_resize(primary_item, primary_context)
            else:
                primary_result = self._compute_clip_resize(primary_item, primary_context)
            _rect, start, end, position = primary_result
            shared_edge_seconds = self._resize_result_edge_seconds(start, end, position)

        for item in resize_items:
            context = self._resize_initial_map.get(item.id)
            if not context:
                continue
            if item is primary_item and primary_result is not None:
                rect, start, end, position = primary_result
            elif isinstance(item, Transition):
                rect, start, end, position = self._compute_transition_resize(
                    item,
                    context,
                    target_edge_seconds=shared_edge_seconds,
                )
            else:
                rect, start, end, position = self._compute_clip_resize(
                    item,
                    context,
                    target_edge_seconds=shared_edge_seconds,
                )

            self._resize_results[item.id] = {
                "start": start,
                "end": end,
                "position": position,
            }
            self.geometry.update_item_rect(item, rect)
            self._apply_resize_preview_override(item, context, start, end, position)
            self._keyframes_dirty = True

            if item is self._resizing_item:
                self._resize_new_start = start
                self._resize_new_end = end
                self._resize_new_position = position
            if item is preview_item:
                preview_result = {
                    "item": item,
                    "start": start,
                    "end": end,
                    "position": position,
                }
            if isinstance(item, Clip) and self.enable_timing:
                self._snap_keyframe_seconds = []

        timeline = getattr(self.win, "timeline", None)
        if preview_result and timeline and self.fps_float:
            item = preview_result["item"]
            start = preview_result["start"]
            end = preview_result["end"]
            if isinstance(item, Clip):
                item_id = getattr(item, "id", None)
                if item_id:
                    if self._resize_edge == "left":
                        frame_seconds = self._snap_time(start)
                    else:
                        frame_seconds = self._snap_time(end)
                    frame = int(round(frame_seconds * self.fps_float)) + 1
                    timeline.PreviewClipFrame(str(item_id), max(1, frame))
            elif isinstance(item, Transition):
                item_id = getattr(item, "id", None)
                if item_id:
                    if self._resize_edge == "left":
                        frame_seconds = self._snap_time(start)
                    else:
                        frame_seconds = self._snap_time(end)
                    frame = int(round(frame_seconds * self.fps_float)) + 1
                    timeline.PreviewTransitionFrame(str(item_id), max(1, frame))
        self.update()

    def _resize_result_edge_seconds(self, start, end, position):
        if getattr(self, "_resize_edge", None) == "left":
            return position
        return position + max(0.0, end - start)

    def _compute_transition_resize(self, item, context=None, target_edge_seconds=None):
        event = self._last_event
        pps = self.pixels_per_second
        min_len = 1.0 / self.fps_float
        if context is None:
            context = {
                "rect": self._resize_initial_rect,
                "world_rect": getattr(self, "_resize_initial_world_rect", self._resize_initial_rect),
                "initial": self._resize_initial,
                "static_mask": self._transition_uses_static_mask(item.data),
            }
        rect = context["rect"]
        world_rect = context.get("world_rect", rect)
        initial = context["initial"]
        start = initial["start"]
        end = initial["end"]
        width = max(end - start, min_len)
        pos = initial["position"]
        static_mask = bool(context.get("static_mask"))

        if self._resize_edge == "left":
            if target_edge_seconds is not None:
                delta_sec = target_edge_seconds - pos
            else:
                delta_sec = ((event.position().x() if hasattr(event, "position") else event.pos().x()) - rect.left()) / pps
            if target_edge_seconds is None and self.enable_snapping:
                delta_sec = self.snap.snap_edge(pos, delta_sec)
            max_delta = width - min_len
            if delta_sec > max_delta:
                delta_sec = max_delta
            new_position = pos + delta_sec
            new_start = 0.0 if static_mask else start + delta_sec
            new_end = (width - delta_sec) if static_mask else end
            if new_position < 0:
                new_position = 0
                if static_mask:
                    new_end = (pos + width) - new_position
                else:
                    new_start = start + (new_position - pos)
            rect_left = self.track_name_width + new_position * pps
        else:
            if target_edge_seconds is not None:
                delta_sec = target_edge_seconds - (pos + width)
            else:
                delta_sec = ((event.position().x() if hasattr(event, "position") else event.pos().x()) - rect.right()) / pps
            if target_edge_seconds is None and self.enable_snapping:
                delta_sec = self.snap.snap_edge(pos + width, delta_sec)
            min_delta = -(width - min_len)
            if delta_sec < min_delta:
                delta_sec = min_delta
            new_start = 0.0 if static_mask else start
            new_end = (width + delta_sec) if static_mask else end + delta_sec
            new_position = pos
            rect_left = self.track_name_width + new_position * pps

        rect_width = max(new_end - new_start, min_len) * pps
        geom_rect = QRectF(rect_left, world_rect.y(), rect_width, world_rect.height())
        return geom_rect, new_start, new_end, new_position

    def _compute_clip_resize(self, item, context=None, target_edge_seconds=None):
        event = self._last_event
        pps = float(self.pixels_per_second or 0.0)
        if context is None:
            context = {
                "rect": self._resize_initial_rect,
                "world_rect": getattr(self, "_resize_initial_world_rect", self._resize_initial_rect),
                "initial": self._resize_initial,
                "max_duration": getattr(self, "_resize_clip_max_duration", None),
                "allow_left_overflow": bool(getattr(self, "_resize_allow_left_overflow", False)),
                "clip_is_single_image": bool(getattr(self, "_resize_clip_is_single_image", False)),
            }
        rect = context["rect"]
        world_rect = context.get("world_rect", rect)
        initial = context["initial"]
        start = initial["start"]
        end = initial["end"]
        pos = initial["position"]
        duration = initial["duration"]
        fps = self.fps_float or 1.0
        min_len = 1.0 / fps
        max_duration = context.get("max_duration")
        allow_left_overflow = bool(context.get("allow_left_overflow", False))
        single_image_resize = bool(context.get("clip_is_single_image", False))
        overflow_enabled = allow_left_overflow and single_image_resize and not self.enable_timing

        if target_edge_seconds is None and (event is None or pps <= 0.0):
            geom_rect = QRectF(world_rect)
            return geom_rect, start, end, pos

        cursor_sec = target_edge_seconds
        if cursor_sec is None:
            cursor_sec = self._seconds_from_x(event.position().x() if hasattr(event, "position") else event.pos().x())
        clip_span = max(end - start, min_len)

        if self._resize_edge == "left":
            delta_sec = cursor_sec - pos
            if target_edge_seconds is None and self.enable_snapping:
                delta_sec = self._snap_trim_delta(delta_sec, edge="left", initial=initial)
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
            if new_start < 0.0 and not self.enable_timing:
                overflow = -new_start
                new_start = 0.0
                if not allow_left_overflow and not self.enable_timing:
                    new_position = pos - start
            if new_start > max_start:
                new_start = max_start
                new_position = pos + (max_start - start)
            if new_position < 0.0 and not self.enable_timing:
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
            if target_edge_seconds is None and self.enable_snapping:
                delta_sec = self._snap_trim_delta(delta_sec, edge="right", initial=initial)
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
        resize_items = list(getattr(self, "_resize_items", None) or ([item] if item else []))
        if not item:
            return
        if not hasattr(self, "_resize_new_start"):
            for candidate in resize_items:
                if isinstance(candidate, Clip):
                    self._set_trim_thumbnail_suspension(False, candidate.id)
                else:
                    # Resize can start/end without a move event; clear any preview
                    # override seeded in _startItemResize().
                    self._pending_transition_overrides.pop(candidate.id, None)
                self._clear_resize_preview_overrides(candidate)
            self._resizing_item = None
            self._resize_items = []
            self._resize_initial_map = {}
            self._snap_keyframe_seconds = []
            self.snap.reset()
            self._restore_resize_snap_ignore_ids(resize_items)
            # Ensure selection visuals are fully refreshed even when resize
            # starts/ends without movement (click on edge).
            self.changed(None)
            self.geometry.mark_dirty()
            self._keyframes_dirty = True
            self.update()
            self._release_cursor()
            if self._last_event:
                self._updateCursor(self._last_event.pos())
            return
        resize_results = getattr(self, "_resize_results", {}) or {}
        resize_initial_map = dict(getattr(self, "_resize_initial_map", {}) or {})
        resize_edge = self._resize_edge
        self._resizing_item = None
        self._resize_items = []
        self._resize_initial_map = {}
        self._resize_results = {}
        self._keyframes_dirty = True
        suspend_keyframe_rebuild = (
            len(resize_items) > 1
            and any(isinstance(candidate, Transition) for candidate in resize_items)
        )
        if suspend_keyframe_rebuild:
            self._suspend_keyframe_rebuild = True
        transaction_id = str(uuid.uuid4())
        total = len(resize_items)
        waveform_clips = []
        requested_backend_refresh = False
        self._suspend_changed_update += 1
        self._preserve_overrides_during_batch = True
        try:
            for idx, candidate in enumerate(resize_items):
                result = resize_results.get(candidate.id)
                if not isinstance(result, dict):
                    continue
                start = result["start"]
                end = result["end"]
                position = result["position"]
                setattr(self.win, "_trim_refresh_pending", True)
                ignore_refresh = idx < total - 1
                if not ignore_refresh:
                    requested_backend_refresh = True
                if isinstance(candidate, Clip):
                    context = resize_initial_map.get(candidate.id, {})
                    audio_data = candidate.data.get("ui", {}).get("audio_data")
                    has_waveform = audio_data not in (None, [])
                    if self._commit_resized_clip(
                        candidate,
                        start,
                        end,
                        position,
                        context,
                        transaction_id,
                        ignore_refresh,
                    ) and has_waveform:
                        waveform_clips.append(candidate.id)
                else:
                    context = resize_initial_map.get(candidate.id, {})
                    static_mask = bool(context.get("static_mask"))
                    transition_data = json.loads(json.dumps(candidate.data))
                    start, end, position = self._normalize_resize_commit_bounds(start, end, position)
                    transition_data["position"] = position
                    transition_data["start"] = start
                    transition_data["end"] = end
                    transition_data["duration"] = self._snap_time(transition_data["end"] - transition_data["start"])
                    transition_data["_auto_direction"] = static_mask
                    self.update_transition_data(
                        transition_data,
                        only_basic_props=True,
                        ignore_refresh=ignore_refresh,
                        transaction_id=transaction_id,
                    )
                    candidate.data = transition_data

                if isinstance(candidate, (Clip, Transition)) and hasattr(self, "RefreshTrimmedTimelineItem"):
                    self.RefreshTrimmedTimelineItem(json.dumps(candidate.data), resize_edge)

                if isinstance(candidate, Clip):
                    self._set_trim_thumbnail_suspension(False, candidate.id)
        finally:
            self._preserve_overrides_during_batch = False
            self._suspend_changed_update = max(0, self._suspend_changed_update - 1)
            self._suspend_keyframe_rebuild = False

        self._snap_keyframe_seconds = []
        self.snap.reset()
        self._restore_resize_snap_ignore_ids(resize_items)
        self._update_project_duration()
        if waveform_clips and hasattr(self, "Show_Waveform_Triggered"):
            self.Show_Waveform_Triggered(waveform_clips, transaction_id=transaction_id)
        self._finalize_resize_preview_state(resize_items, requested_backend_refresh)
        if hasattr(self, "_refresh_keyframe_markers") and not self._dragging_panel_keyframes and not self._dragging_keyframe:
            self._refresh_keyframe_markers()
        else:
            self._keyframes_dirty = True
        self.update()
        self._release_cursor()
        if self._last_event:
            posf = self._last_event.position() if hasattr(self._last_event, "position") else QPointF(self._last_event.pos())
            self._updateCursor(posf)
        if hasattr(self, "_resize_initial_world_rect"):
            del self._resize_initial_world_rect
        self._resize_clip_max_duration = None
        self._resize_allow_left_overflow = False
        self._resize_clip_is_single_image = False

    def _startBoxSelect(self):
        e = self._last_event
        ctrl_down = bool(e.modifiers() & Qt.ControlModifier)
        self.box_start = e.position() if hasattr(e, "position") else QPointF(e.pos())
        panel_lane = self._panel_lane_at(self.box_start)
        panel_track = panel_lane.get("track") if panel_lane else self._panel_track_at_pos(self.box_start)
        if panel_track is not None:
            self._panel_box_track = panel_track
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
        rect = QRectF(
            self.box_start,
            self._last_event.position() if hasattr(self._last_event, "position") else QPointF(self._last_event.pos())
        ).normalized()
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
                    selected_context = None
                    for point in points:
                        seconds = point.get("seconds")
                        if seconds is None:
                            continue
                        marker_rect = self._panel_marker_rect(lane_rect, lane_padding, seconds)
                        if marker_rect.intersects(selection_rect):
                            point_context = None
                            if hasattr(self, "_panel_property_context"):
                                point_context = self._panel_property_context(
                                    {"context": point.get("_panel_context")},
                                    lane.get("context"),
                                )
                            if selected_context is None and point_context:
                                selected_context = self._panel_context_signature(point_context)
                            frame_val = point.get("frame")
                            if frame_val is not None:
                                try:
                                    selected_frames.add(int(frame_val))
                                except (TypeError, ValueError):
                                    continue
                    if selected_frames:
                        selector = self._panel_selection_selector(
                            selected_frames,
                            context_signature=selected_context,
                        )
                        frames_by_prop[prop.get("key")] = selector
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
