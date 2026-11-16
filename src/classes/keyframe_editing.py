"""Keyframe initialization and editing rules shared by the UI."""

from copy import deepcopy


def initialize_split_clip_keyframes(data, fps):
    """Anchor fresh constant properties at a Split File range's left edge.

    Call only when creating a timeline clip from project media, never when
    trimming or slicing an existing clip. Time maps retain their source origin.
    """
    start_frame = round(float(data.get("start", 0.0)) * fps) + 1
    if start_frame <= 1:
        return

    def anchor(value):
        if isinstance(value, dict):
            points = value.get("Points")
            if isinstance(points, list):
                if len(points) == 1 and points[0]["co"]["X"] == 1:
                    # Keep the source's base value if the range is extended left.
                    point = deepcopy(points[0])
                    point["co"]["X"] = start_frame
                    points.append(point)
                return
            for key, child in value.items():
                if key not in ("time", "reader"):
                    anchor(child)
        elif isinstance(value, list):
            for child in value:
                anchor(child)

    anchor(data)


def auto_keyframes_enabled(window):
    action = getattr(window, "actionAutoKeyframes", None)
    return action is None or action.isChecked()


def edit_frame(points, frame, auto_keyframes=True):
    """Use the preceding point (or the first point before the curve starts)."""
    frame = max(1, int(round(frame)))
    if auto_keyframes:
        return frame
    frames = [point["co"]["X"] for point in points]
    if not frames:
        # A missing property still needs a constant value.
        return 1
    return max((x for x in frames if x <= frame), default=min(frames))


def retarget_keyframe_changes(original, updated, frame):
    """Retarget nested color-grade edits without changing unrelated channels."""
    if not isinstance(original, dict) or not isinstance(updated, dict):
        return
    if "Points" in original and "Points" in updated:
        points = original["Points"]
        old = next((p for p in points if p["co"]["X"] == frame), None)
        new = next((p for p in updated["Points"] if p["co"]["X"] == frame), None)
        target = edit_frame(points, frame, False)
        if new is not None and new != old and target != frame:
            updated["Points"].remove(new)
            previous = next((p for p in updated["Points"] if p["co"]["X"] == target), None)
            if previous is not None:
                previous["co"]["Y"] = new["co"]["Y"]
            else:
                new["co"]["X"] = target
                updated["Points"].append(new)
        return
    for key, value in updated.items():
        old = original.get(key)
        if isinstance(value, list) and isinstance(old, list):
            for old_item, new_item in zip(old, value):
                retarget_keyframe_changes(old_item, new_item, frame)
        else:
            retarget_keyframe_changes(old, value, frame)


def add_point(keyframe, new_point):
    """Add a point to a keyframe dict, replacing any point on the same frame."""
    keyframe["Points"] = [
        point for point in keyframe["Points"]
        if point.get("co", {}).get("X") != new_point.get("co", {}).get("X")
    ] + [new_point]


def remove_points_in_range(keyframe, frame_start, frame_end):
    """Remove all keyframe points with X in [frame_start, frame_end]."""
    keyframe["Points"] = [
        p for p in keyframe["Points"]
        if not (frame_start <= p.get("co", {}).get("X", -1) <= frame_end)
    ]


def is_keyframe_patch(values):
    """Transient single-point edits; project files always retain full Points arrays."""
    return isinstance(values, dict) and bool(values) and all(
        isinstance(curve, dict) and set(curve) == {"Point"}
        and isinstance(curve["Point"], dict)
        and isinstance(curve["Point"].get("co"), dict)
        and isinstance(curve["Point"]["co"].get("X"), (int, float))
        and isinstance(curve["Point"]["co"].get("Y"), (int, float))
        for curve in values.values())


def apply_keyframe_patch(data, values, indexes):
    """Apply drag samples without copying or scanning the preceding animation.

    Indexes belong to one live edit and are discarded on a normal update.
    Keep every matching point for compatibility with imported duplicate frames.
    """
    for name, patch in values.items():
        points = data.setdefault(name, {"Points": []}).setdefault("Points", [])
        key = (id(data), name)
        cached = indexes.get(key)
        if cached is None or cached[0] is not points or cached[1] != len(points):
            by_frame = {}
            for point in points:
                by_frame.setdefault(point["co"]["X"], []).append(point)
        else:
            by_frame = cached[2]
        point = deepcopy(patch["Point"])
        frame = point["co"]["X"]
        if frame in by_frame:
            for previous in by_frame[frame]:
                previous.update(deepcopy(point))
        else:
            points.append(point)
            by_frame[frame] = [point]
        indexes[key] = (points, len(points), by_frame)
