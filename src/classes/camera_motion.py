"""
 @file
 @brief Camera motion framing helpers for clip motion presets
 @author OpenShot Studios

 @section LICENSE

 Copyright (c) 2008-2026 OpenShot Studios, LLC
 (http://www.openshotstudios.com). This file is part of
 OpenShot Video Editor (http://www.openshot.org), an open-source project
 dedicated to delivering high quality video editing and animation solutions
 to the world.

 OpenShot Video Editor is free software: you can redistribute it and/or modify
 it under the terms of the GNU General Public License as published by
 the Free Software Foundation, either version 3 of the License, or
 (at your option) any later version.
 """

from typing import Dict, NamedTuple, Optional, Tuple


PAN_AUTO = "auto"
PAN_LEFT_TO_RIGHT = "left_to_right"
PAN_RIGHT_TO_LEFT = "right_to_left"
PAN_TOP_TO_BOTTOM = "top_to_bottom"
PAN_BOTTOM_TO_TOP = "bottom_to_top"
PAN_LEFT = "pan_left"
PAN_RIGHT = "pan_right"
PAN_UP = "pan_up"
PAN_DOWN = "pan_down"

KEN_BURNS_AUTO = "auto"
KEN_BURNS_LEFT_TO_RIGHT = "left_to_right"
KEN_BURNS_RIGHT_TO_LEFT = "right_to_left"
KEN_BURNS_TOP_TO_BOTTOM = "top_to_bottom"
KEN_BURNS_BOTTOM_TO_TOP = "bottom_to_top"


class CameraKeyframes(NamedTuple):
    """Plain keyframe values returned by camera motion helpers."""

    scale_x: Tuple[float, float]
    scale_y: Tuple[float, float]
    location_x: Tuple[float, float] = (0.0, 0.0)
    location_y: Tuple[float, float] = (0.0, 0.0)


def _positive_float(value, fallback: float) -> float:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return fallback
    return value if value > 0.0 else fallback


def _crop_base_size(
    project_width,
    project_height,
    source_width,
    source_height,
) -> Tuple[float, float]:
    """Return source size after SCALE_CROP with scale_x/scale_y at 1.0."""
    pw = _positive_float(project_width, 1920.0)
    ph = _positive_float(project_height, 1080.0)
    sw = _positive_float(source_width, pw)
    sh = _positive_float(source_height, ph)

    project_aspect = pw / ph
    source_aspect = sw / sh
    if source_aspect >= project_aspect:
        return ph * source_aspect, ph
    return pw, pw / source_aspect


def _safe_location(canvas_size: float, base_size: float, scale: float) -> float:
    """Largest normalized location value that keeps SCALE_CROP edges covered."""
    scaled_size = max(0.0001, float(base_size) * max(0.001, float(scale)))
    canvas_size = max(0.0001, float(canvas_size))
    if scaled_size <= canvas_size:
        return 0.0
    return (scaled_size - canvas_size) / (scaled_size + canvas_size)


def _scale_for_safe_location(canvas_size: float, base_size: float, target: float) -> float:
    """Return minimum scale needed for target normalized pan room on one axis."""
    target = max(0.0, min(float(target), 0.9))
    canvas_size = max(0.0001, float(canvas_size))
    base_size = max(0.0001, float(base_size))
    return (canvas_size * (1.0 + target)) / (base_size * (1.0 - target))


def _axis_for_direction(direction: str) -> str:
    if direction in (
            PAN_LEFT, PAN_RIGHT, PAN_LEFT_TO_RIGHT, PAN_RIGHT_TO_LEFT,
            KEN_BURNS_LEFT_TO_RIGHT, KEN_BURNS_RIGHT_TO_LEFT):
        return "x"
    if direction in (
            PAN_UP, PAN_DOWN, PAN_TOP_TO_BOTTOM, PAN_BOTTOM_TO_TOP,
            KEN_BURNS_TOP_TO_BOTTOM, KEN_BURNS_BOTTOM_TO_TOP):
        return "y"
    return "auto"


def _auto_ken_burns_direction(
    project_width,
    project_height,
    source_width,
    source_height,
) -> str:
    """Choose the strongest natural crop axis for a Ken Burns drift."""
    pw = _positive_float(project_width, 1920.0)
    ph = _positive_float(project_height, 1080.0)
    bw, bh = _crop_base_size(pw, ph, source_width, source_height)
    x_room = _safe_location(pw, bw, 1.0)
    y_room = _safe_location(ph, bh, 1.0)

    if x_room > y_room + 0.03:
        return KEN_BURNS_LEFT_TO_RIGHT
    if y_room > x_room + 0.03:
        return KEN_BURNS_BOTTOM_TO_TOP
    return KEN_BURNS_LEFT_TO_RIGHT


def _pan_endpoints(direction: str, magnitude: float) -> Tuple[float, float]:
    magnitude = round(max(0.0, float(magnitude)), 6)
    if direction in (PAN_LEFT, PAN_RIGHT_TO_LEFT, KEN_BURNS_RIGHT_TO_LEFT):
        return -magnitude, magnitude
    if direction in (PAN_RIGHT, PAN_LEFT_TO_RIGHT, KEN_BURNS_LEFT_TO_RIGHT):
        return magnitude, -magnitude
    if direction in (PAN_UP, PAN_BOTTOM_TO_TOP, KEN_BURNS_BOTTOM_TO_TOP):
        return -magnitude, magnitude
    if direction in (PAN_DOWN, PAN_TOP_TO_BOTTOM, KEN_BURNS_TOP_TO_BOTTOM):
        return magnitude, -magnitude
    return 0.0, 0.0


def camera_pan_keyframes(
    direction: str,
    project_width,
    project_height,
    source_width,
    source_height,
    *,
    target_pan: float = 0.18,
    edge_margin: float = 0.995,
) -> CameraKeyframes:
    """Return smart SCALE_CROP pan values for a requested camera pan direction."""
    pw = _positive_float(project_width, 1920.0)
    ph = _positive_float(project_height, 1080.0)
    if direction == PAN_AUTO:
        direction = _auto_ken_burns_direction(pw, ph, source_width, source_height)
    bw, bh = _crop_base_size(pw, ph, source_width, source_height)
    axis = _axis_for_direction(direction)
    canvas = pw if axis == "x" else ph
    base = bw if axis == "x" else bh

    natural_room = _safe_location(canvas, base, 1.0)
    if natural_room >= target_pan:
        scale = 1.0
        magnitude = natural_room * edge_margin
    else:
        scale = max(1.0, _scale_for_safe_location(canvas, base, target_pan))
        magnitude = _safe_location(canvas, base, scale) * edge_margin

    start, end = _pan_endpoints(direction, magnitude)
    if axis == "x":
        return CameraKeyframes((scale, scale), (scale, scale), (start, end), (0.0, 0.0))
    return CameraKeyframes((scale, scale), (scale, scale), (0.0, 0.0), (start, end))


def push_pull_keyframes(zoom_in: bool, *, zoom: float = 1.2) -> CameraKeyframes:
    """Return centered push-in or pull-out camera zoom keyframes."""
    start, end = (1.0, zoom) if zoom_in else (zoom, 1.0)
    return CameraKeyframes((start, end), (start, end))


def ken_burns_keyframes(
    zoom_in: bool,
    direction: str,
    project_width,
    project_height,
    source_width,
    source_height,
    *,
    zoom: float = 1.22,
    target_pan: float = 0.10,
    max_pan: float = 0.24,
) -> CameraKeyframes:
    """Return smart Ken Burns zoom and drift values."""
    pw = _positive_float(project_width, 1920.0)
    ph = _positive_float(project_height, 1080.0)
    bw, bh = _crop_base_size(pw, ph, source_width, source_height)

    if direction == KEN_BURNS_AUTO:
        direction = _auto_ken_burns_direction(pw, ph, source_width, source_height)

    axis = _axis_for_direction(direction)
    canvas = pw if axis == "x" else ph
    base = bw if axis == "x" else bh
    zoom = max(float(zoom), _scale_for_safe_location(canvas, base, target_pan))

    start_scale, end_scale = (1.0, zoom) if zoom_in else (zoom, 1.0)
    start_safe = min(_safe_location(canvas, base, start_scale) * 0.82, max_pan)
    end_safe = min(_safe_location(canvas, base, end_scale) * 0.82, max_pan)
    start_magnitude = max(start_safe, target_pan if start_safe else 0.0)
    end_magnitude = max(end_safe, target_pan if end_safe else 0.0)
    start_mag = _pan_endpoints(direction, min(start_magnitude, max_pan))[0]
    end_mag = _pan_endpoints(direction, min(end_magnitude, max_pan))[1]

    if axis == "x":
        return CameraKeyframes((start_scale, end_scale), (start_scale, end_scale), (start_mag, end_mag), (0.0, 0.0))
    return CameraKeyframes((start_scale, end_scale), (start_scale, end_scale), (0.0, 0.0), (start_mag, end_mag))


def source_dimensions_from_reader(reader: Optional[Dict]) -> Tuple[Optional[float], Optional[float]]:
    """Extract media dimensions from reader metadata."""
    if not isinstance(reader, dict):
        return None, None
    width = reader.get("width") or reader.get("display_width")
    height = reader.get("height") or reader.get("display_height")
    try:
        return float(width), float(height)
    except (TypeError, ValueError):
        return None, None
