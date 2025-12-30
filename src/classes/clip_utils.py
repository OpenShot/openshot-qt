"""
 @file
 @brief Clip timing and frame utilities shared by the UI.

 @section LICENSE

 Copyright (c) 2008-2018 OpenShot Studios, LLC
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

import logging
from fractions import Fraction
from typing import Any, Mapping, Optional, Tuple

from classes.app import get_app

logger = logging.getLogger(__name__)


def _as_mapping(candidate: Any) -> Mapping[str, Any]:
    """Return dict-style metadata for clips, readers, or similar."""
    if isinstance(candidate, Mapping):
        return candidate
    data = getattr(candidate, "data", None)
    if isinstance(data, Mapping):
        return data
    return {}


def _rounded_int(value: Any) -> Optional[int]:
    """Round a numeric value to int when possible."""
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


def _to_float(value: Any) -> Optional[float]:
    """Convert a value to float when possible."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_positive_float(value: Any) -> Optional[float]:
    """Convert a value to a positive float."""
    number = _to_float(value)
    if number is None or number <= 0:
        return None
    return number


def _to_positive_int(value: Any) -> Optional[int]:
    """Return a rounded positive int."""
    number = _rounded_int(value)
    if number is None or number <= 0:
        return None
    return number


def _fps_fraction(fps_value: Any) -> Optional[Fraction]:
    """Convert an FPS value to a Fraction."""
    if fps_value is None:
        return None
    if isinstance(fps_value, Fraction):
        return fps_value
    if isinstance(fps_value, (int, float)):
        if fps_value > 0:
            return Fraction(fps_value).limit_denominator(1_000_000)
        return None
    if isinstance(fps_value, Mapping):
        fps_num = fps_value.get("num")
        fps_den = fps_value.get("den")
    else:
        fps_num = getattr(fps_value, "num", None)
        fps_den = getattr(fps_value, "den", None)
    try:
        fps_num = int(fps_num)
        fps_den = int(fps_den)
    except (TypeError, ValueError):
        fps_num = fps_den = None
    if fps_num and fps_den:
        try:
            return Fraction(fps_num, fps_den)
        except ZeroDivisionError:
            return None
    to_float = getattr(fps_value, "ToFloat", None)
    if callable(to_float):
        fps_float = to_float()
        if fps_float and fps_float > 0:
            return Fraction(fps_float).limit_denominator(1_000_000)
    return None


def project_fps_fraction() -> Fraction:
    """Return the current project FPS as a Fraction."""
    app = get_app()
    project = getattr(app, "project", None) if app else None
    fps_meta = None
    if hasattr(project, "get"):
        try:
            fps_meta = project.get("fps")
        except TypeError:
            fps_meta = None
    elif isinstance(project, Mapping):
        fps_meta = project.get("fps")
    fps = _fps_fraction(fps_meta)
    return fps or Fraction(30, 1)


def _project_fps_float() -> float:
    """Return the project FPS as a float."""
    try:
        return float(project_fps_fraction())
    except (TypeError, ValueError):
        return 30.0


def video_length_to_project_frames(
    media: Any = None,
    *,
    video_length: Any = None,
    fps: Any = None,
    duration: Any = None,
    project_fps: Any = None,
) -> Optional[int]:
    """Return project frames needed to play supplied media."""
    metadata = _as_mapping(media)
    if video_length is None:
        video_length = metadata.get("video_length")
    frames = _to_positive_int(video_length)

    if fps is None:
        fps = metadata.get("fps")
    source_fps = _fps_fraction(fps)

    if duration is None:
        duration = metadata.get("duration")
    duration_value = _to_positive_float(duration)

    if frames is None and duration_value is not None and source_fps:
        frames = int(round(duration_value * float(source_fps)))

    if frames is None or frames <= 0:
        return None

    project_fraction = _fps_fraction(project_fps) or project_fps_fraction()

    if not source_fps or not project_fraction:
        return max(frames, 1)

    scaled = Fraction(frames) * project_fraction / source_fps
    try:
        scaled_value = int(round(float(scaled)))
    except (TypeError, ValueError):
        return max(frames, 1)
    return max(scaled_value, 1)


def _clip_reader(clip_data: Any, existing_clip: Any) -> Any:
    """Return reader metadata sourced from clip data or existing clip."""
    reader = _as_mapping(clip_data).get("reader")
    if reader:
        return reader
    return _as_mapping(existing_clip).get("reader")


def _inherit_timing(clip_data: Mapping[str, Any], existing_clip: Any) -> None:
    """Fill missing timing fields from an existing clip."""
    existing = _as_mapping(existing_clip)
    if not existing:
        return
    for key in ("start", "end", "duration"):
        if key not in clip_data or clip_data.get(key) is None:
            if key in existing:
                clip_data[key] = existing.get(key)


def _clip_id(clip_data: Any, existing_clip: Any) -> Optional[str]:
    """Return the clip id from data or an existing clip."""
    clip_meta = _as_mapping(clip_data)
    clip_id = clip_meta.get("id")
    if clip_id:
        return clip_id
    existing_meta = _as_mapping(existing_clip)
    clip_id = existing_meta.get("id")
    return clip_id if clip_id else None


def _timeline_clip(clip_data: Any, existing_clip: Any) -> Any:
    """Return the live timeline clip instance when available."""
    clip_id = _clip_id(clip_data, existing_clip)
    if not clip_id:
        return None
    try:
        app = get_app()
        window = getattr(app, "window", None)
        timeline_sync = getattr(window, "timeline_sync", None)
        timeline = getattr(timeline_sync, "timeline", None)
        return timeline.GetClip(clip_id) if timeline else None
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.debug("Unable to locate clip %s on timeline: %s", clip_id, exc, exc_info=True)
        return None


def _time_points(clip_data: Any) -> Optional[list]:
    """Return time curve points from clip metadata."""
    time_data = _as_mapping(clip_data).get("time")
    points = time_data.get("Points") if isinstance(time_data, Mapping) else None
    return points if isinstance(points, list) else None


def _time_curve_length_frames(clip_data: Any, existing_clip: Any) -> Optional[int]:
    """Return the max frame referenced by the time curve."""
    points = _time_points(clip_data)
    if points:
        max_x = 0
        for point in points:
            co = point.get("co") if isinstance(point, Mapping) else None
            if not isinstance(co, Mapping):
                continue
            x_val = _rounded_int(co.get("X"))
            if x_val is not None:
                max_x = max(max_x, x_val)
        if max_x:
            return max_x

    clip_obj = _timeline_clip(clip_data, existing_clip)
    if clip_obj and getattr(clip_obj, "time", None):
        try:
            length = clip_obj.time.GetLength()
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.debug("Unable to query clip time length: %s", exc, exc_info=True)
        else:
            frame_count = _rounded_int(length)
            if frame_count:
                return max(frame_count, 1)

    return None


def _clamp_time_points(points: Any, max_frames: Optional[int]) -> None:
    """Clamp keyframe points to positive axes and available frames."""
    if not isinstance(points, list) or not max_frames:
        return

    limit = int(max_frames)
    for point in points:
        co = point.get("co") if isinstance(point, Mapping) else None
        if not isinstance(co, Mapping):
            continue
        x_val = _rounded_int(co.get("X"))
        if x_val is not None:
            co["X"] = x_val
        y_val = _rounded_int(co.get("Y"))
        if y_val is not None:
            if y_val < 1:
                co["Y"] = 1
            elif y_val > limit:
                co["Y"] = limit
            else:
                co["Y"] = y_val


def _clamp_basic_timing(clip_data: Mapping[str, Any], max_duration: Optional[float]) -> None:
    """Clamp start/end/duration for clips without remapping."""
    start = _to_float(clip_data.get("start"))
    if start is None or start < 0.0:
        start = 0.0
    if max_duration is not None and start > max_duration:
        start = max_duration

    end = _to_float(clip_data.get("end"))
    duration = _to_float(clip_data.get("duration"))

    if end is None:
        if duration is not None:
            end = start + max(duration, 0.0)
        elif max_duration is not None:
            end = max_duration
        else:
            end = start

    if max_duration is not None and end > max_duration:
        end = max_duration
    if end < start:
        start = end

    clip_data["start"] = start
    clip_data["end"] = end
    clip_data["duration"] = max(0.0, end - start)


def _clamp_curve_start(clip_data: Mapping[str, Any], max_duration: Optional[float]) -> None:
    """Clamp the start value for curves to the available range."""
    start = _to_float(clip_data.get("start"))
    if start is None or start < 0.0:
        start = 0.0
    if max_duration is not None and start > max_duration:
        start = max_duration
    clip_data["start"] = start


def _is_single_image(source: Any) -> bool:
    """Return True when metadata flags the media as a single image."""
    metadata = _as_mapping(source)
    if metadata.get("has_single_image"):
        return True
    media_type = metadata.get("media_type")
    return isinstance(media_type, str) and media_type.lower() == "image"


def _clip_has_single_image(reader: Any, clip_data: Any, existing_clip: Any) -> bool:
    """Return True if any metadata indicates a single-image clip."""
    if _is_single_image(reader):
        return True
    clip_meta = _as_mapping(clip_data)
    if _is_single_image(clip_meta):
        return True
    if _is_single_image(clip_meta.get("reader")):
        return True
    existing_meta = _as_mapping(existing_clip)
    if _is_single_image(existing_meta):
        return True
    return _is_single_image(existing_meta.get("reader"))


def _normalize_single_image(clip_data: Mapping[str, Any]) -> None:
    """Set consistent timing for single-image clips."""
    start = _to_float(clip_data.get("start"))
    if start is None or start < 0.0:
        start = 0.0

    end = _to_float(clip_data.get("end"))
    duration = _to_float(clip_data.get("duration"))

    if duration is None and end is not None:
        duration = end - start
    if end is None and duration is not None:
        end = start + duration
    if end is None:
        end = start
    if duration is None:
        duration = end - start

    if end < start:
        end = start
    duration = max(0.0, end - start)

    clip_data["start"] = start
    clip_data["end"] = end
    clip_data["duration"] = duration


def _reader_bounds(reader: Any) -> Tuple[Optional[float], Optional[int]]:
    """Return reader duration and total frames in project units."""
    metadata = _as_mapping(reader)
    duration = _to_float(metadata.get("duration"))
    if duration is not None and duration < 0.0:
        duration = None

    project_fps = project_fps_fraction()
    project_fps_float = float(project_fps) if project_fps else None

    frames = video_length_to_project_frames(metadata, project_fps=project_fps)

    if duration is None and frames and project_fps_float:
        duration = frames / project_fps_float
    if frames is None and duration is not None and project_fps_float:
        frames = _to_positive_int(duration * project_fps_float)

    return duration, frames


def clamp_timing_to_media(clip_data: Mapping[str, Any], existing_clip: Any = None) -> Mapping[str, Any]:
    """Clamp clip timing to the available source media or time-curve bounds."""
    reader = _clip_reader(clip_data, existing_clip)

    _inherit_timing(clip_data, existing_clip)

    if _clip_has_single_image(reader, clip_data, existing_clip):
        _normalize_single_image(clip_data)
        return clip_data

    points = _time_points(clip_data)
    multi_point_time = isinstance(points, list) and len(points) > 1

    reader_duration, reader_frames = _reader_bounds(reader)

    if multi_point_time:
        max_frames = _time_curve_length_frames(clip_data, existing_clip) or reader_frames
        if reader_frames:
            _clamp_time_points(points, reader_frames)

        proj_fps_f = _project_fps_float()
        max_duration = None
        if max_frames and proj_fps_f:
            max_duration = max_frames / proj_fps_f
        elif reader_duration is not None:
            max_duration = reader_duration

        _clamp_curve_start(clip_data, max_duration)
        return clip_data

    _clamp_basic_timing(clip_data, reader_duration)
    if reader_frames:
        _clamp_time_points(points, reader_frames)

    return clip_data


def clip_time_bounds(clip_data: Any, existing_clip: Any = None) -> Tuple[float, int]:
    """Return the max duration (seconds) and frame count allowed for the clip."""
    reader = _clip_reader(clip_data, existing_clip) or {}

    if _clip_has_single_image(reader, clip_data, existing_clip):
        clip_meta = _as_mapping(clip_data)
        duration = _to_float(clip_meta.get("duration"))
        if duration is None:
            duration = _to_float(_as_mapping(reader).get("duration"))
        duration = duration if duration is not None else 0.0
        proj_fps_f = _project_fps_float()
        if duration and proj_fps_f:
            max_frames = max(1, int(round(duration * proj_fps_f)))
        else:
            max_frames = 1
        return duration, max_frames

    points = _time_points(clip_data)
    multi_point_time = isinstance(points, list) and len(points) > 1

    proj_fps_f = _project_fps_float()
    reader_duration, reader_frames = _reader_bounds(reader)

    if multi_point_time:
        max_frames = _time_curve_length_frames(clip_data, existing_clip) or reader_frames or 1
        if proj_fps_f:
            max_duration = max_frames / proj_fps_f
        elif reader_duration is not None:
            max_duration = reader_duration
        else:
            max_duration = 0.0
        return max_duration, max_frames

    max_frames = reader_frames or 1
    if reader_duration is not None:
        max_duration = reader_duration
    elif proj_fps_f and max_frames:
        max_duration = max_frames / proj_fps_f
    else:
        max_duration = 0.0

    return max_duration, max_frames
