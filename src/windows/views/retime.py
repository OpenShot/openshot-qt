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


def _iterate_keyframe_lists(clip_dict):
    for value in clip_dict.values():
        if isinstance(value, dict) and isinstance(value.get("Points"), list):
            yield value["Points"]
    objects = clip_dict.get("objects") or {}
    for obj in objects.values():
        if not isinstance(obj, dict):
            continue
        for value in obj.values():
            if isinstance(value, dict) and isinstance(value.get("Points"), list):
                yield value["Points"]
    for eff in clip_dict.get("effects", []) or []:
        if not isinstance(eff, dict):
            continue
        for value in eff.values():
            if isinstance(value, dict) and isinstance(value.get("Points"), list):
                yield value["Points"]


def _scale_points(points, start_x, new_end_x, scale):
    if not isinstance(points, list):
        return
    for point in points:
        co = point.get("co", {})
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
