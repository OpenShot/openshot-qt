"""
 @file
 @brief This file contains repeat time keyframe logic (for Time->Repeat menu)
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

import copy
import openshot
from PyQt5.QtWidgets import (
    QDialog, QFormLayout, QComboBox, QSpinBox, QDoubleSpinBox,
    QDialogButtonBox, QHBoxLayout
)
from classes.app import get_app

_ = get_app()._tr


class RepeatDialog(QDialog):
    """Simple dialog to collect custom repeat options."""

    def __init__(self, parent=None, pattern="loop", direction=1):
        super().__init__(parent)
        self.setWindowTitle(_("Custom Repeat"))
        layout = QFormLayout(self)

        self.pattern_combo = QComboBox(self)
        self.pattern_combo.addItems([_("Loop"), _("Ping-Pong")])
        self.pattern_combo.setCurrentIndex(0 if pattern == "loop" else 1)
        layout.addRow(_("Pattern"), self.pattern_combo)

        self.direction_combo = QComboBox(self)
        self.direction_combo.addItems([_("Forward"), _("Reverse")])
        self.direction_combo.setCurrentIndex(0 if direction > 0 else 1)
        layout.addRow(_("Direction"), self.direction_combo)

        self.passes_spin = QSpinBox(self)
        self.passes_spin.setRange(2, 500)
        self.passes_spin.setValue(2)
        layout.addRow(_("Passes"), self.passes_spin)

        delay_layout = QHBoxLayout()
        self.delay_spin = QDoubleSpinBox(self)
        self.delay_spin.setRange(0.0, 100000.0)
        self.delay_spin.setDecimals(3)
        self.delay_unit = QComboBox(self)
        self.delay_unit.addItems([_("frames"), _("ms"), _("sec")])
        delay_layout.addWidget(self.delay_spin)
        delay_layout.addWidget(self.delay_unit)
        layout.addRow(_("Delay"), delay_layout)

        self.ramp_spin = QDoubleSpinBox(self)
        self.ramp_spin.setRange(-1000.0, 1000.0)
        self.ramp_spin.setDecimals(3)
        layout.addRow(_("Speed Ramp (%)"), self.ramp_spin)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=self
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_values(self, fps_float):
        pattern = "loop" if self.pattern_combo.currentIndex() == 0 else "pingpong"
        direction = 1 if self.direction_combo.currentIndex() == 0 else -1
        passes = self.passes_spin.value()
        delay_val = self.delay_spin.value()
        unit = self.delay_unit.currentText()
        if unit == _("frames"):
            delay_frames = int(round(delay_val))
        elif unit == _("ms"):
            delay_frames = int(round((delay_val / 1000.0) * fps_float))
        else:
            delay_frames = int(round(delay_val * fps_float))
        ramp = self.ramp_spin.value() / 100.0
        return pattern, direction, passes, delay_frames, ramp


# Repeat logic


def _normalize_points(points):
    """Normalize points so X starts at 1 while preserving Y values."""
    if not points:
        return []
    pts = sorted(points, key=lambda p: int(round(p.get("co", {}).get("X", 0))))
    x0 = int(round(pts[0]["co"]["X"]))
    out = []
    for p in pts:
        x = int(round(p["co"].get("X", 0))) - x0 + 1
        y = p["co"].get("Y")
        out.append({"co": {"X": x, "Y": y}, "interpolation": p.get("interpolation", openshot.LINEAR)})
    return out


def _normalize_points_to_trim(points, trim_start_frames, trim_span_frames):
    """Normalize points to the trimmed span (1..trim_span), tolerating clip-relative or absolute."""
    if not points or trim_span_frames <= 0:
        return []

    pts = sorted(points, key=lambda p: int(round(p.get("co", {}).get("X", 0))))
    xs = [int(round(p.get("co", {}).get("X", 0))) for p in pts]
    min_x = min(xs)
    max_x = max(xs)

    normalized = []
    for p, x_abs in zip(pts, xs):
        co = p.get("co", {}) if isinstance(p, dict) else {}

        # If the data already looks clip-relative (within trimmed span), keep as-is
        if 1 <= min_x and max_x <= trim_span_frames:
            x_rel = x_abs
        else:
            # Convert absolute project frame to trimmed-relative frame (1-based)
            x_rel = x_abs - trim_start_frames

        x_rel = int(round(x_rel))

        # Drop any keyframes that fall outside the trimmed clip range once shifted.
        if x_rel < 1 or x_rel > trim_span_frames:
            continue

        new_point = copy.deepcopy(p)
        new_point.setdefault("co", {})
        new_point["co"]["X"] = x_rel
        normalized.append(new_point)
    return normalized


def _repeat_curve(points, span_x, dir_sign, passes, delay_frames, ramp, pattern):
    """Repeat normalized points applying ramp, delay, and direction."""
    new_points = []
    base = 0
    dir_local = dir_sign
    for k in range(passes):
        speed = (1 + ramp) ** k
        scale = 1 / abs(speed)
        dur = max(1, int(round(span_x * scale)))
        pts_iter = points if dir_local > 0 else reversed(points)
        for idx, p in enumerate(pts_iter):
            x = int(round(p["co"].get("X", 0))) - 1
            y = p["co"].get("Y")
            nx_off = min(int(round(x * scale)), dur - 1)
            if dir_local > 0:
                nx = base + nx_off + 1
            else:
                nx = base + (dur - nx_off)
            interp = p.get("interpolation", openshot.LINEAR)
            if pattern == "loop" and k > 0 and idx == 0:
                interp = openshot.CONSTANT
            new_points.append({"co": {"X": nx, "Y": y}, "interpolation": interp})
        base += dur
        if k < passes - 1 and delay_frames:
            last_y = new_points[-1]["co"].get("Y")
            new_points.append({"co": {"X": base, "Y": last_y}, "interpolation": openshot.LINEAR})
            new_points.append({"co": {"X": base + delay_frames, "Y": last_y}, "interpolation": openshot.LINEAR})
            base += delay_frames
        if pattern == "pingpong":
            dir_local *= -1
    return new_points, base

def apply_repeat(clip, pattern, start_dir, passes, delay_frames, ramp, fps_float):
    """Apply repeat stamping to a clip."""
    if passes < 2:
        return

    # Convert trim (seconds) to frames (zero-based repeat: always use 1..trim_span).
    # Use duration to avoid off-by-one loss when end is rounded down/up differently.
    trim_start_frames = int(round(float(clip.data.get("start", 0.0)) * fps_float))
    trim_span_frames = max(
        1,
        int(round((float(clip.data.get("end", 0.0)) - float(clip.data.get("start", 0.0))) * fps_float)),
    )
    target_start_y = trim_start_frames + 1
    target_end_y = target_start_y + trim_span_frames
    target_range = max(1, target_end_y - target_start_y)

    # Normalize existing time curve or build linear default
    orig_time = clip.data.get("time", {}).get("Points", [])
    if isinstance(orig_time, list) and len(orig_time) >= 2:
        base_time = _normalize_points(orig_time)
        y_start = int(round(base_time[0]["co"].get("Y", 0)))
        y_end = int(round(base_time[-1]["co"].get("Y", 0)))
        y_range = max(1, y_end - y_start)
        # Rescale Y values so they align with the trimmed region (in frames)
        for p in base_time:
            y_val = p["co"].get("Y", 0)
            p["co"]["Y"] = target_start_y + ((y_val - y_start) * target_range / y_range)
    else:
        base_frames = trim_span_frames
        base_time = [
            {"co": {"X": 1, "Y": target_start_y}, "interpolation": openshot.LINEAR},
            {"co": {"X": base_frames, "Y": target_end_y}, "interpolation": openshot.LINEAR},
        ]
    time_span_x = max(1, int(round(base_time[-1]["co"]["X"])))

    # Rescale any existing time curve X to the trimmed span so repeat stays zero-based
    if time_span_x != trim_span_frames:
        scale = float(trim_span_frames) / float(time_span_x)
        for p in base_time:
            x_val = int(round(p["co"].get("X", 1) * scale))
            p["co"]["X"] = max(1, x_val)
        time_span_x = trim_span_frames

    # Store original data if not already
    if "repeat_cache" not in clip.data:
        cache = {
            "start": clip.data.get("start", 0.0),
            "end": clip.data["end"],
            "duration": clip.data["duration"],
            "properties": {},
        }
        for k, v in clip.data.items():
            if isinstance(v, dict) and isinstance(v.get("Points"), list) and len(v["Points"]) > 1:
                cache["properties"][k] = copy.deepcopy(v)
        clip.data["repeat_cache"] = cache

    dir_sign = 1 if start_dir >= 0 else -1

    # Build time curve based on existing keyframes
    time_points, total_frames = _repeat_curve(
        base_time, time_span_x, dir_sign, passes, delay_frames, ramp, pattern
    )
    clip.data["time"] = {"Points": time_points}

    # Repeat animated properties
    cache = clip.data.get("repeat_cache", {})
    for prop, original in cache.get("properties", {}).items():
        if prop == "time":
            continue
        norm = _normalize_points_to_trim(
            original.get("Points", []),
            trim_start_frames,
            trim_span_frames,
        )
        span = int(round(norm[-1]["co"]["X"])) if norm else 0
        if span:
            # Rescale keyframe X into the trimmed span to keep repeats aligned
            if span != time_span_x:
                scale = float(time_span_x) / float(span)
                first_x = float(norm[0]["co"].get("X", 1))
                for p in norm:
                    orig_x = float(p["co"].get("X", 1))
                    x_val = 1 + (orig_x - first_x) * scale
                    x_val = int(round(x_val))
                    p["co"]["X"] = min(max(1, x_val), time_span_x)
                span = time_span_x

            # Deduplicate any points that collapsed onto the same frame (esp. at start)
            latest_by_x = {}
            for p in norm:
                x_val = int(round(p["co"].get("X", 1)))
                p["co"]["X"] = x_val
                # Prefer the last occurrence (most recently edited) when duplicates collapse
                latest_by_x[x_val] = p
            norm = [latest_by_x[x] for x in sorted(latest_by_x.keys())]

            new_points, used = _repeat_curve(norm, span, dir_sign, passes, delay_frames, ramp, pattern)
            clip.data[prop] = {"Points": new_points}
            total_frames = max(total_frames, used)

    # Update trims to cover the repeated span starting at 0
    new_duration = total_frames / fps_float
    clip.data["start"] = 0.0
    clip.data["end"] = new_duration
    clip.data["duration"] = new_duration


def reset_repeat(clip):
    cache = clip.data.pop("repeat_cache", None)
    if not cache:
        return
    clip.data["start"] = cache.get("start", clip.data.get("start"))
    clip.data["end"] = cache.get("end", clip.data.get("end"))
    clip.data["duration"] = cache.get("duration", clip.data.get("duration"))
    for prop, data in cache.get("properties", {}).items():
        clip.data[prop] = data
    if "time" not in cache.get("properties", {}):
        clip.data["time"] = {"Points": [{"co": {"X": 1, "Y": 1}, "interpolation": openshot.LINEAR}]}
