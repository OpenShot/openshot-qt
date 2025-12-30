"""
 @file
 @brief Helper for horizontal snapping.
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

from classes.app import get_app


class SnapHelper:
    """Compute horizontal snap offsets for dragged clips and transitions."""

    def __init__(self, widget, geometry):
        self.widget = widget
        self.geometry = geometry

    # ---- Helpers -----------------------------------------------------
    def _h_offset(self) -> float:
        """Return current horizontal scroll offset in pixels."""
        view_w = self.widget.scrollbar_position[3] or 1.0
        timeline_w = self.widget.scrollbar_position[2] or view_w
        left = self.widget.scrollbar_position[0]
        offset = left * timeline_w
        max_scroll = max(0.0, timeline_w - view_w)
        if offset > max_scroll:
            offset = max_scroll
        return offset

    def _project_duration(self) -> float:
        app = get_app()
        if not app:
            return 0.0
        project = getattr(app, "project", None)
        if not project:
            return 0.0
        try:
            return float(project.get("duration") or 0.0)
        except (TypeError, ValueError):
            return 0.0

    def _snap_tolerance_px(self) -> float:
        value = getattr(self.widget, "snap_tolerance_px", None)
        try:
            tol = float(value)
        except (TypeError, ValueError):
            tol = 12.0
        if tol <= 0.0:
            tol = 12.0
        return tol

    def _active_targets(self) -> dict:
        active = getattr(self.widget, "_snap_active_targets", None)
        if not isinstance(active, dict):
            active = {}
            self.widget._snap_active_targets = active
        return active

    def reset(self, labels=None):
        """Clear cached snap targets.

        If *labels* is provided, only the specified keys are removed.
        """

        active = getattr(self.widget, "_snap_active_targets", None)
        if not isinstance(active, dict):
            return
        if labels is None:
            active.clear()
            return
        for label in labels:
            active.pop(label, None)

    def _target_edges_px(self):
        self.geometry.ensure()
        pps = float(self.widget.pixels_per_second or 0.0)
        if pps <= 0.0:
            return []

        generic_targets = set()
        keyframe_targets = []
        h_offset = self._h_offset()
        left_edge = self.widget.track_name_width - h_offset

        ignore_ids = getattr(self.widget, "_snap_ignore_ids", set())
        for rect, obj, _selected in self.geometry.iter_clips():
            obj_id = getattr(obj, "id", None)
            if obj_id in ignore_ids:
                continue
            generic_targets.add(rect.left())
            generic_targets.add(rect.right())

        for rect, obj, _selected in self.geometry.iter_transitions():
            obj_id = getattr(obj, "id", None)
            if obj_id in ignore_ids:
                continue
            generic_targets.add(rect.left())
            generic_targets.add(rect.right())

        for entry in self.geometry.iter_markers():
            if isinstance(entry, dict):
                rect = entry.get("line_rect") or entry.get("rect")
            else:
                rect = entry
            if rect:
                generic_targets.add(rect.left())

        duration = self._project_duration()
        if duration > 0.0:
            generic_targets.add(left_edge + duration * pps)

        generic_targets.add(left_edge)

        snap_px = self._snap_tolerance_px()
        extra_seconds = getattr(self.widget, "_snap_keyframe_seconds", None)
        if extra_seconds:
            fps = getattr(self.widget, "fps_float", 0.0) or 0.0
            frame_sec = 1.0 / float(fps) if fps else 0.0
            base_sec = max(frame_sec, 0.02)
            default_sec = snap_px / pps if pps > 0.0 else 0.0
            if default_sec > 0.0:
                base_sec = min(base_sec, default_sec)
            keyframe_tol_px = base_sec * pps
            if not math.isfinite(keyframe_tol_px) or keyframe_tol_px <= 0.0:
                keyframe_tol_px = snap_px
            keyframe_tol_px = max(1.0, min(snap_px, keyframe_tol_px))

            for value in extra_seconds:
                tolerance_override = None
                if isinstance(value, dict):
                    sec_value = value.get("seconds")
                    tolerance_override = value.get("tolerance")
                else:
                    sec_value = value
                try:
                    sec = float(sec_value)
                except (TypeError, ValueError):
                    continue
                px = (
                    self.widget.track_name_width
                    + sec * pps
                    - h_offset
                )
                tolerance_px = keyframe_tol_px
                if tolerance_override is not None:
                    try:
                        tol_sec = float(tolerance_override)
                        tolerance_px = tol_sec * pps
                    except (TypeError, ValueError):
                        tolerance_px = keyframe_tol_px
                if not math.isfinite(tolerance_px) or tolerance_px <= 0.0:
                    tolerance_px = keyframe_tol_px
                tolerance_px = max(1.0, min(snap_px, abs(tolerance_px)))
                keyframe_targets.append((px, tolerance_px))

        playhead_x = (
            self.widget.track_name_width
            + (self.widget.current_frame / self.widget.fps_float)
            * pps
            - h_offset
        )
        generic_targets.add(playhead_x)

        valid = []
        for value in generic_targets:
            if value is None:
                continue
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                continue
            if math.isfinite(numeric):
                valid.append(numeric)

        for value, tolerance_px in keyframe_targets:
            try:
                px_value = float(value)
                tol_value = float(tolerance_px)
            except (TypeError, ValueError):
                continue
            if math.isfinite(px_value) and math.isfinite(tol_value):
                valid.append((px_value, max(0.0, tol_value)))
        return valid

    def keyframe_snap_seconds(self, include_playhead=True):
        """Return generic snap targets converted to seconds for keyframe drags."""

        px_targets = self._target_edges_px()
        pps = float(self.widget.pixels_per_second or 0.0)
        if pps <= 0.0:
            return []

        h_offset = self._h_offset()
        track_left = float(getattr(self.widget, "track_name_width", 0.0) or 0.0)

        fps = float(getattr(self.widget, "fps_float", 0.0) or 0.0)
        playhead_px = None
        if fps > 0.0:
            frame = float(getattr(self.widget, "current_frame", 0) or 0.0)
            playhead_px = track_left + (frame / fps) * pps - h_offset

        targets = []
        seen = set()
        for entry in px_targets:
            tolerance_px = None
            if isinstance(entry, tuple):
                if not entry:
                    continue
                px_value = entry[0]
                if len(entry) > 1:
                    tolerance_px = entry[1]
            else:
                px_value = entry

            try:
                px_value = float(px_value)
            except (TypeError, ValueError):
                continue
            if not math.isfinite(px_value):
                continue

            if not include_playhead and playhead_px is not None and math.isfinite(playhead_px):
                if abs(px_value - playhead_px) <= 0.5:
                    continue

            seconds = (px_value + h_offset - track_left) / pps
            if not math.isfinite(seconds):
                continue
            if seconds < 0.0:
                seconds = 0.0

            key = round(seconds, 6)
            if key in seen:
                continue
            seen.add(key)

            tolerance_sec = None
            if tolerance_px is not None:
                try:
                    tolerance_px = float(tolerance_px)
                    tolerance_sec = abs(tolerance_px) / pps
                except (TypeError, ValueError):
                    tolerance_sec = None
            if tolerance_sec and tolerance_sec > 0.0:
                targets.append({"seconds": seconds, "tolerance": tolerance_sec})
            else:
                targets.append(seconds)

        return targets

    def _diff_to_target(self, label: str, current_px: float, snap_px: float, targets, active):
        """Return (diff, target, reused_active, tolerance_px) for a given cursor position."""

        if not math.isfinite(current_px):
            return None, None, False, snap_px

        target_entry = active.get(label)
        target_px = None
        tolerance_px = snap_px
        if isinstance(target_entry, dict):
            target_px = target_entry.get("px")
            tol_val = target_entry.get("tol")
            if isinstance(tol_val, (int, float)) and math.isfinite(tol_val):
                tolerance_px = max(0.0, float(tol_val))
        elif isinstance(target_entry, (tuple, list)) and target_entry:
            target_px = target_entry[0]
            if len(target_entry) > 1:
                try:
                    tolerance_px = max(0.0, float(target_entry[1]))
                except (TypeError, ValueError):
                    tolerance_px = snap_px
        else:
            target_px = target_entry

        if isinstance(target_px, (int, float)) and math.isfinite(target_px):
            diff = float(target_px) - current_px
            if math.isfinite(diff) and abs(diff) <= tolerance_px:
                return diff, float(target_px), True, tolerance_px

        best_target = None
        best_diff = None
        best_tol = tolerance_px
        for entry in targets:
            if isinstance(entry, tuple):
                candidate = entry[0]
                tol_override = entry[1] if len(entry) > 1 else None
            else:
                candidate = entry
                tol_override = None
            try:
                candidate_px = float(candidate)
            except (TypeError, ValueError):
                continue
            if not math.isfinite(candidate_px):
                continue
            tolerance = snap_px
            if tol_override is not None:
                try:
                    tolerance = float(tol_override)
                except (TypeError, ValueError):
                    tolerance = snap_px
            if not math.isfinite(tolerance):
                tolerance = snap_px
            tolerance = abs(tolerance)
            diff = candidate_px - current_px
            if not math.isfinite(diff):
                continue
            if abs(diff) <= tolerance:
                if best_diff is None or abs(diff) < abs(best_diff):
                    best_diff = diff
                    best_target = candidate_px
                    best_tol = tolerance

        if best_target is None:
            return None, None, False, snap_px

        return best_diff, best_target, False, best_tol

    def snap_dx(self, delta_sec: float) -> float:
        """Return adjusted delta in seconds for horizontal snapping."""
        self.geometry.ensure()
        pps = float(self.widget.pixels_per_second or 0.0)
        if pps <= 0.0:
            return delta_sec
        snap_px = self._snap_tolerance_px()
        bbox = self.widget.drag_bbox
        if not hasattr(bbox, "x"):
            return delta_sec

        targets = self._target_edges_px()
        if not targets:
            self.reset(["drag-left", "drag-right"])
            return delta_sec

        active = self._active_targets()
        start_left = bbox.x()
        width = bbox.width()
        current_positions = [
            ("drag-left", start_left + delta_sec * pps),
            ("drag-right", start_left + width + delta_sec * pps),
        ]

        chosen = None
        for label, current_px in current_positions:
            diff, target, reused, tolerance = self._diff_to_target(
                label, current_px, snap_px, targets, active
            )
            if diff is None:
                continue
            priority = 0 if reused else 1
            if (
                chosen is None
                or priority < chosen[0]
                or (priority == chosen[0] and abs(diff) < abs(chosen[1]))
            ):
                chosen = (priority, diff, label, target, tolerance)

        if chosen is None:
            self.reset(["drag-left", "drag-right"])
            return delta_sec

        _, diff_px, label, target_px, tol_px = chosen
        active[label] = {"px": target_px, "tol": tol_px}
        for other in ("drag-left", "drag-right"):
            if other != label:
                active.pop(other, None)

        delta_sec += diff_px / self.widget.pixels_per_second
        return delta_sec

    def snap_edge(self, orig_edge_sec: float, delta_sec: float) -> float:
        """Snap a moving edge (in seconds) to nearby clip edges or playhead."""
        self.geometry.ensure()
        pps = float(self.widget.pixels_per_second or 0.0)
        if pps <= 0.0:
            return delta_sec
        snap_px = self._snap_tolerance_px()
        h_offset = self._h_offset()
        start_px = (
            self.widget.track_name_width
            + orig_edge_sec * self.widget.pixels_per_second
            - h_offset
        )
        edge_px = start_px + (delta_sec * self.widget.pixels_per_second)
        moved_px = edge_px - start_px
        targets = self._target_edges_px()
        label = getattr(self.widget, "_resize_edge", None)
        if label in ("left", "right"):
            label = f"edge-{label}"
        else:
            label = "edge"

        if not targets:
            self.reset([label])
            return delta_sec

        active = self._active_targets()
        diff_px, target_px, _, tolerance_px = self._diff_to_target(
            label, edge_px, snap_px, targets, active
        )
        if diff_px is None:
            self.reset([label])
            return delta_sec

        target_distance = target_px - start_px
        tolerance_used = tolerance_px if math.isfinite(tolerance_px) else snap_px
        if abs(target_distance) > 1e-6:
            if abs(moved_px) < 1e-6:
                self.reset([label])
                return delta_sec
            if moved_px * target_distance < 0:
                self.reset([label])
                return delta_sec
            min_travel = min(abs(target_distance), tolerance_used)
            if abs(moved_px) + 1e-6 < min_travel:
                self.reset([label])
                return delta_sec

        active[label] = {"px": target_px, "tol": tolerance_used}
        delta_sec += diff_px / self.widget.pixels_per_second
        return delta_sec
