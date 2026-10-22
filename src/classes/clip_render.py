"""
 @file
 @brief Render a single timeline Clip's own trimmed content to a flat video file,
        without an Export dialog or a full-project Timeline -- just that clip's own
        reader. Used by the two-clip AI bridge timeline action to produce clean,
        single-source inputs for a ComfyUI template, independent of whatever else
        is composited on other tracks during that time range.
 @author Jonathan Thomas <jonathan@openshot.org>

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

 OpenShot Video Editor is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 GNU General Public License for more details.

 You should have received a copy of the GNU General Public License
 along with OpenShot Library.  If not, see <http://www.gnu.org/licenses/>.
 """

import os

import openshot

from classes.logger import log
from classes.query import File


def _reader_properties(clip):
    """A timeline Clip's own media properties (width/height/fps/etc.) live nested
    under clip.data["reader"] -- unlike a File object, where they're flattened at
    the top level of .data. Confirmed against classes/query.py's own Clip.title()
    (`self.data.get("reader", {}).get("path")`)."""
    reader = clip.data.get("reader") if isinstance(clip.data, dict) else None
    return reader if isinstance(reader, dict) else {}


def clip_source_path(clip):
    """Resolve the real, absolute source file path for `clip` (a timeline Clip).
    Prefers looking up the live File record via clip.data["file_id"] (reusing
    File.absolute_path()'s portability-aware resolution, e.g. a moved project),
    falling back to the clip's own nested reader path if the File can't be found.
    """
    file_id = clip.data.get("file_id") if isinstance(clip.data, dict) else None
    if file_id:
        file_obj = File.get(id=file_id)
        if file_obj:
            return file_obj.absolute_path()
    return _reader_properties(clip).get("path", "")


def clip_frame_range(clip):
    """Return (start_frame, end_frame), 1-based and inclusive, for the trim range
    already on `clip`. Always present and exactly right for a timeline clip --
    unlike a File, which may have no start/end at all, a timeline Clip's own
    start/end are precisely its visible in/out points."""
    reader = _reader_properties(clip)
    fps = reader.get("fps") or {"num": 30, "den": 1}
    fps_float = float(fps.get("num", 30)) / float(fps.get("den", 1) or 1)
    start_time = float(clip.data.get("start", 0.0))
    end_time = float(clip.data.get("end", start_time))
    start_frame = max(1, int(round(start_time * fps_float)) + 1)
    end_frame = max(start_frame - 1, int(round(end_time * fps_float)))
    return start_frame, end_frame


def _positive_int(value, default):
    try:
        value = int(value)
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def setup_clip_writer(clip, writer):
    """Configure `writer` (an openshot.FFmpegWriter) to match `clip`'s own media
    properties. Mirrors windows/export_clips.py's setupWriter(), adapted to read
    from a timeline Clip's nested reader properties instead of a File's flattened
    top-level ones."""
    reader = _reader_properties(clip)
    pr = reader.get("pixel_ratio") or {"num": 1, "den": 1}
    pixel_ratio = openshot.Fraction(pr.get("num", 1), pr.get("den", 1))
    fps = reader.get("fps") or {"num": 30, "den": 1}
    frames_per_second = openshot.Fraction(fps.get("num", 1), fps.get("den", 1))
    has_audio = bool(reader.get("has_audio", False))

    writer.SetVideoOptions(
        True,
        "libx264",
        frames_per_second,
        reader.get("width", 1280),
        reader.get("height", 720),
        pixel_ratio,
        False,
        False,
        22,
    )
    writer.PrepareStreams()
    writer.SetAudioOptions(
        has_audio,
        "aac",
        _positive_int(reader.get("sample_rate"), 48000),
        _positive_int(reader.get("channels"), 2),
        _positive_int(reader.get("channel_layout"), 3),
        _positive_int(reader.get("audio_bit_rate"), 192000),
    )
    writer.PrepareStreams()
    writer.Open()


def render_clip_to_file(clip, export_path):
    """Render just `clip`'s own trimmed content -- not whatever else is composited
    on other timeline tracks during that time range -- to `export_path`, reading
    directly from its own source file via its own reader. No Export dialog, no
    full-project openshot.Timeline. Mirrors windows/export_clips.py's
    _exportClip(), adapted for a timeline Clip's data shape.

    Returns True on success. On any error, removes a partial output file (if any)
    and returns False -- never raises.
    """
    source_path = clip_source_path(clip)
    if not source_path:
        log.error("render_clip_to_file: no source path for clip %s", getattr(clip, "id", None))
        return False

    start_frame, end_frame = clip_frame_range(clip)
    if end_frame < start_frame:
        log.error("render_clip_to_file: empty frame range for clip %s", getattr(clip, "id", None))
        return False

    writer = openshot.FFmpegWriter(export_path)
    try:
        setup_clip_writer(clip, writer)
    except Exception:
        log.error("render_clip_to_file: failed to set up writer for %s", export_path, exc_info=True)
        if os.path.exists(export_path):
            os.remove(export_path)
        return False

    clip_reader = None
    success = False
    try:
        clip_reader = openshot.Clip(source_path)
        clip_reader.Open()
        for frame in range(start_frame, end_frame + 1):
            writer.WriteFrame(clip_reader.GetFrame(frame))
        success = True
    except Exception:
        log.error("render_clip_to_file: failed to render %s", export_path, exc_info=True)
    finally:
        if clip_reader:
            clip_reader.Close()
        writer.Close()

    if not success and os.path.exists(export_path):
        os.remove(export_path)
    return success
