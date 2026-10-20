"""
 @file
 @brief This file contains re-time keyframe logic (for Time->Fast/Slow menu, Timing mode on timeline)
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
import json
import openshot
from classes.app import get_app
from classes.clip_utils import is_single_image_media
from classes.keyframe_editing import add_point
from classes.logger import log
from .timeline_backend.enums import MenuTime


def _project_fps_float():
    proj_fps = get_app().project.get("fps") or {"num": 30, "den": 1}
    return float(proj_fps.get("num", 30)) / float(proj_fps.get("den", 1))


def _calculate_retime_metrics(clip, new_end, pfps):
    start_s = float(clip.data["start"])
    old_end_s = float(clip.data["end"])
    req_end_s = float(new_end)
    new_dur_s = req_end_s - start_s
    if new_dur_s <= 0:
        return None

    # Frame snapping and derived X domain
    new_dur_frames = max(1, int(round(new_dur_s * pfps)))
    new_dur_s = new_dur_frames / pfps
    new_end_s = start_s + new_dur_s

    start_x = int(round(start_s * pfps)) + 1
    old_end_x = int(round(old_end_s * pfps))
    new_end_x = start_x + new_dur_frames

    old_len = max(1, old_end_x - start_x)
    scale = float(new_end_x - start_x) / float(old_len)

    return {
        "start_s": start_s,
        "old_end_s": old_end_s,
        "new_dur_s": new_dur_s,
        "new_end_s": new_end_s,
        "start_x": start_x,
        "new_end_x": new_end_x,
        "scale": scale,
    }


def _iterate_keyframe_lists(value):
    """Yield every keyframe Points list nested anywhere inside a clip payload."""
    if isinstance(value, dict):
        points = value.get("Points")
        if isinstance(points, list):
            yield points
            return
        for child in value.values():
            yield from _iterate_keyframe_lists(child)
    elif isinstance(value, list):
        for child in value:
            yield from _iterate_keyframe_lists(child)


def _scale_points(points, start_x, new_end_x, scale):
    if not isinstance(points, list):
        return
    for point in points:
        if not isinstance(point, dict):
            continue
        co = point.get("co", {})
        if not isinstance(co, dict):
            continue
        x = co.get("X")
        if x is None or x < start_x:
            continue
        nx = start_x + (x - start_x) * scale
        nx = int(round(nx))
        if nx < start_x:
            nx = start_x
        elif nx > new_end_x:
            nx = new_end_x
        co["X"] = nx


def _reverse_time_points(points):
    """Mirror points horizontally (X) across their min/max span and swap handles."""
    if not isinstance(points, list) or not points:
        return

    x_values = [p.get("co", {}).get("X") for p in points if isinstance(p.get("co"), dict) and "X" in p.get("co", {})]
    if not x_values:
        return

    pivot = min(x_values) + max(x_values)

    # Preserve original order to keep segment interpolation mapping intact.
    orig_points = sorted(points, key=lambda p: p.get("co", {}).get("X", 0))

    mirrored = []
    for point in orig_points:
        new_point = copy.deepcopy(point)
        co = new_point.get("co")
        if isinstance(co, dict) and "X" in co:
            co["X"] = pivot - point["co"]["X"]
            hl = new_point.pop("handle_left", None)
            hr = new_point.pop("handle_right", None)
            if hr is not None:
                new_point["handle_left"] = hr
            if hl is not None:
                new_point["handle_right"] = hl
        mirrored.append(new_point)

    # Move per-segment interpolation with its segment. In libopenshot the interpolation
    # lives on the destination point, so when reversing we shift each interpolation one
    # point backward to follow the same segment in the new order.
    for idx in range(len(mirrored) - 1):
        mirrored[idx]["interpolation"] = orig_points[idx + 1].get("interpolation", openshot.LINEAR)
    if mirrored:
        mirrored[-1]["interpolation"] = orig_points[-1].get("interpolation", openshot.LINEAR)

    mirrored.sort(key=lambda p: p.get("co", {}).get("X", 0))
    points[:] = mirrored


def _ensure_time_curve(clip, start_x, new_end_x, old_end_s, pfps, _direction):
    time_data = clip.data.get("time")
    time_points = time_data.get("Points") if isinstance(time_data, dict) else None
    if not isinstance(time_points, list) or len(time_points) < 2:
        y0 = start_x
        y1 = int(round(old_end_s * pfps))
        p0 = openshot.Point(start_x, y0, openshot.LINEAR)
        p1 = openshot.Point(new_end_x, y1, openshot.LINEAR)
        clip.data["time"] = {"Points": [json.loads(p0.Json()), json.loads(p1.Json())]}
        return clip.data["time"]["Points"]

    return time_points


def _finalize_time_points(time_points, start_x, new_end_x):
    if not time_points:
        return
    time_points.sort(key=lambda point: float(point.get("co", {}).get("X", 0)))

    domain_start = int(start_x)
    domain_end = int(new_end_x)
    count = len(time_points)

    # Normalize all X values into the clip domain
    normalized = []
    for point in time_points:
        co = point.setdefault("co", {})
        raw_x = co.get("X", domain_start)
        snapped_x = int(round(raw_x))
        if snapped_x < domain_start:
            snapped_x = domain_start
        elif snapped_x > domain_end:
            snapped_x = domain_end
        normalized.append(snapped_x)

    # Clamp endpoints to the domain bounds
    normalized[0] = domain_start
    normalized[-1] = domain_end

    # Ensure the sequence is non-decreasing from start to end
    for index in range(1, count):
        prev = normalized[index - 1]
        if normalized[index] <= prev:
            normalized[index] = min(domain_end, prev + 1)

    # Make sure there is enough room remaining for trailing points
    for index in range(count - 2, -1, -1):
        remaining = count - index - 1
        max_allowed = domain_end - remaining
        if normalized[index] > max_allowed:
            normalized[index] = max_allowed
        if normalized[index] < domain_start:
            normalized[index] = domain_start
        if index > 0 and normalized[index] <= normalized[index - 1]:
            normalized[index] = min(max_allowed, normalized[index - 1] + 1)

    normalized[0] = domain_start
    normalized[-1] = domain_end

    # Final forward pass to clean up any residual overlap
    for index in range(1, count):
        if normalized[index] <= normalized[index - 1]:
            normalized[index] = min(domain_end, normalized[index - 1] + 1)

    normalized[0] = domain_start
    normalized[-1] = domain_end

    for point, x_val in zip(time_points, normalized):
        point["co"]["X"] = int(x_val)


def retime_clip(clip, new_end, new_position=None, direction=1):
    """Retimes a clip and uniformly rescales ALL keyframes' X (including 'time').
       - X and Y are in PROJECT frames.
       - Mirror the time curve's X for reverse.
    """

    pfps = _project_fps_float()
    metrics = _calculate_retime_metrics(clip, new_end, pfps)
    if not metrics:
        return False

    for points in _iterate_keyframe_lists(clip.data):
        _scale_points(points, metrics["start_x"], metrics["new_end_x"], metrics["scale"])

    time_points = _ensure_time_curve(
        clip,
        metrics["start_x"],
        metrics["new_end_x"],
        metrics["old_end_s"],
        pfps,
        direction,
    )
    if direction == -1:
        _reverse_time_points(time_points)
    _finalize_time_points(time_points, metrics["start_x"], metrics["new_end_x"])

    clip.data["duration"] = float(metrics["new_dur_s"])
    clip.data["end"] = float(metrics["new_end_s"])
    if new_position is not None:
        clip.data["position"] = float(int(round(float(new_position) * pfps)) / pfps)

    return True


def apply_time_action(clip, action, fps_float, speed="1X", playhead_position=0.0, base_clip=None):
    """Apply one Speed menu action (MenuTime) to a clip, in place.

    speed is a factor label such as "2X" or "1/4X", or freeze seconds for
    FREEZE/FREEZE_ZOOM, which start at playhead_position (timeline seconds).
    base_clip is a native clip used to read current time/volume values.
    """
    from .repeat import reset_repeat  # repeat.py needs the app at import time.
    if action in [MenuTime.FREEZE, MenuTime.FREEZE_ZOOM]:
        freeze_seconds = float(speed)

        original_duration = clip.data["duration"]
        original_end = float(clip.data["end"])
        log.info('Updating timing for clip ID {}, original duration: {}'.format(clip.id, original_duration))
        log.debug(clip.data)

        # Extend end & duration (freeze). Do NOT touch reader.video_length.
        clip.data["end"] = float(clip.data["end"]) + freeze_seconds
        clip.data["duration"] = float(clip.data["duration"]) + freeze_seconds

        # Determine start frame from position (project frames)
        start_animation_seconds = float(clip.data["start"]) + (playhead_position - float(clip.data["position"]))
        start_animation_frames = round(start_animation_seconds * fps_float) + 1
        start_animation_frames_value = start_animation_frames
        end_animation_seconds = start_animation_seconds + freeze_seconds
        end_animation_frames = round(end_animation_seconds * fps_float) + 1
        end_of_clip_seconds = float(clip.data["end"])
        end_of_clip_frames = round((end_of_clip_seconds) * fps_float) + 1
        end_of_clip_frames_value = round((original_end) * fps_float) + 1

        # Determine volume start and end
        start_volume_value = 1.0

        # If existing time curve, get intersecting Y from libopenshot curve
        if len(clip.data["time"]["Points"]) > 1:
            del clip.data["time"]["Points"][-1]
            if base_clip:
                start_animation_frames_value = base_clip.time.GetLong(start_animation_frames)

        # If existing volume curve, get intersecting value
        if len(clip.data["volume"]["Points"]) > 1:
            if base_clip:
                start_volume_value = base_clip.volume.GetValue(start_animation_frames)

        # Time freeze keyframes
        p = openshot.Point(start_animation_frames, start_animation_frames_value, openshot.LINEAR)
        add_point(clip.data['time'], json.loads(p.Json()))
        p1 = openshot.Point(end_animation_frames, start_animation_frames_value, openshot.LINEAR)
        add_point(clip.data['time'], json.loads(p1.Json()))
        p2 = openshot.Point(end_of_clip_frames, end_of_clip_frames_value, openshot.LINEAR)
        add_point(clip.data['time'], json.loads(p2.Json()))

        # Volume mute keyframes
        p = openshot.Point(start_animation_frames - 1, start_volume_value, openshot.LINEAR)
        add_point(clip.data['volume'], json.loads(p.Json()))
        p = openshot.Point(start_animation_frames, 0.0, openshot.LINEAR)
        add_point(clip.data['volume'], json.loads(p.Json()))
        p2 = openshot.Point(end_animation_frames - 1, 0.0, openshot.LINEAR)
        add_point(clip.data['volume'], json.loads(p2.Json()))
        p3 = openshot.Point(end_animation_frames, start_volume_value, openshot.LINEAR)
        add_point(clip.data['volume'], json.loads(p3.Json()))

        if action == MenuTime.FREEZE_ZOOM:
            p = openshot.Point(start_animation_frames, 1.0, openshot.BEZIER)
            add_point(clip.data['scale_x'], json.loads(p.Json()))
            p = openshot.Point(start_animation_frames, 1.0, openshot.BEZIER)
            add_point(clip.data['scale_y'], json.loads(p.Json()))
            diff_halfed = (end_animation_frames - start_animation_frames) / 2.0
            p1 = openshot.Point(start_animation_frames + diff_halfed, 1.05, openshot.BEZIER)
            add_point(clip.data['scale_x'], json.loads(p1.Json()))
            p1 = openshot.Point(start_animation_frames + diff_halfed, 1.05, openshot.BEZIER)
            add_point(clip.data['scale_y'], json.loads(p1.Json()))
            p1 = openshot.Point(end_animation_frames, 1.0, openshot.BEZIER)
            add_point(clip.data['scale_x'], json.loads(p1.Json()))
            p1 = openshot.Point(end_animation_frames, 1.0, openshot.BEZIER)
            add_point(clip.data['scale_y'], json.loads(p1.Json()))

    else:

        if action == MenuTime.NONE:
            # RESET TIME
            reset_repeat(clip)
            reader = clip.data.get("reader", {}) or {}
            start_sec = float(clip.data.get("start", 0.0))
            duration_sec = 0.0
            try:
                duration_sec = float(reader.get("duration", 0.0) or 0.0)
            except (TypeError, ValueError):
                duration_sec = 0.0

            if duration_sec <= 0.0 and base_clip:
                try:
                    duration_sec = float(getattr(base_clip.Reader().info, "duration", 0.0))
                except Exception:
                    duration_sec = 0.0
            if duration_sec <= 0.0:
                try:
                    duration_sec = float(clip.data.get("duration", 0.0))
                except (TypeError, ValueError):
                    duration_sec = 0.0

            if is_single_image_media(reader):
                duration_sec = float(get_app().get_settings().get("default-image-length") or 10.0)

            if duration_sec <= 0.0:
                duration_sec = 1.0 / fps_float

            target_frames = max(1, int(round(duration_sec * fps_float)))
            snapped_duration = target_frames / fps_float
            target_end_sec = start_sec + snapped_duration

            # Retime the clip to that end (rescales ALL X correctly)
            retime_clip(clip, target_end_sec, clip.data.get("position"), direction=1)

            # Clear the time curve (default identity point)
            clip.data["time"] = {"Points": [{"co": {"X": 1, "Y": 1}, "interpolation": openshot.LINEAR}]}

        elif action == MenuTime.REVERSE:
            start_sec = float(clip.data.get("start", 0.0))
            try:
                target_end_sec = float(clip.data.get("end", start_sec))
            except (TypeError, ValueError):
                target_end_sec = start_sec

            if target_end_sec <= start_sec:
                try:
                    duration_sec = float(clip.data.get("duration", 0.0))
                except (TypeError, ValueError):
                    duration_sec = 0.0
                if duration_sec <= 0.0:
                    duration_sec = 1.0 / fps_float
                target_end_sec = start_sec + duration_sec

            retime_clip(clip, target_end_sec, clip.data.get("position"), direction=-1)

        else:
            speed_label = speed.replace('X', '')
            parts = speed_label.split('/')
            if len(parts) == 2:
                speed_factor = float(parts[0]) / float(parts[1])
            else:
                speed_factor = float(speed_label)

            original_duration = float(clip.data["end"]) - float(clip.data["start"])
            new_duration = original_duration / speed_factor
            new_end_time = float(clip.data["start"]) + new_duration
            direction = 1 if action == MenuTime.FORWARD else -1

            retime_clip(clip, new_end_time, clip.data.get("position"), direction)

