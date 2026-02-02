"""
 @file
 @brief This file is used to generate an EDL (edit decision list) export
 @author Jonathan Thomas <jonathan@openshot.org>

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

import os
from operator import itemgetter

from PyQt5.QtWidgets import QFileDialog

from classes import info
from classes.app import get_app
from classes.logger import log
from classes.path_utils import relative_export_path, absolute_media_path
from classes.query import Clip, Track, File
from classes.time_parts import secondsToTimecode

def _interp_name(value):
    """Map interpolation value to a stable name."""
    try:
        numeric = int(value)
    except (TypeError, ValueError):
        numeric = None
    # libopenshot: 0=bezier, 1=linear, 2=constant/hold
    if numeric == 0:
        return "bezier"
    if numeric == 1:
        return "linear"
    if numeric == 2:
        return "hold"
    text = str(value).lower() if value is not None else ""
    if text.startswith("bez"):
        return "bezier"
    if text.startswith("hold") or text.startswith("const"):
        return "hold"
    return "linear"

def _is_drop_frame(fps_num, fps_den):
    """Return True if FPS corresponds to a common drop-frame rate."""
    if fps_den == 0:
        return False
    fps = float(fps_num) / float(fps_den)
    return any(abs(fps - rate) < 0.01 for rate in (29.97, 59.94))


def _clip_media_path(clip):
    file_id = clip.data.get("file_id")
    if file_id:
        file_obj = File.get(id=file_id)
        if file_obj:
            path = file_obj.absolute_path()
            if path:
                return path

    reader_path = clip.data.get("reader", {}).get("path")
    if reader_path:
        resolved = absolute_media_path(reader_path)
        if resolved:
            return resolved
        return reader_path
    return ""


def _volume_to_db(linear_value):
    """Convert linear (0-1) volume to dB, clamped to a reasonable floor."""
    try:
        v = float(linear_value)
    except (TypeError, ValueError):
        v = 0.0
    v = max(0.0, v)
    if v == 0.0:
        return -96.0
    import math
    db = 20.0 * math.log10(v)
    return max(db, -96.0)


def _fmt_value(value):
    """Format numeric with up to 2 decimals, stripping trailing zeros."""
    try:
        val = float(value)
    except (TypeError, ValueError):
        return "0"
    s = f"{val:.2f}"
    s = s.rstrip("0").rstrip(".")
    return s or "0"


def _fmt_percent(value):
    """Format percent by rounding to nearest int (no decimals)."""
    try:
        val = float(value)
    except (TypeError, ValueError):
        return "0"
    return str(int(round(val)))


def _db_to_volume(db_value):
    """Convert dB back to linear 0-1."""
    import math
    try:
        db = float(db_value)
    except (TypeError, ValueError):
        return 0.0
    if db <= -96.0:
        return 0.0
    linear = 10 ** (db / 20.0)
    return max(0.0, min(1.0, linear))


def export_edl():
    """Export EDL File"""
    app = get_app()
    _ = app._tr

    # EDL Export format
    edl_string = "%03d  %-9s%-6s%-9s%11s %11s %11s %11s\n"

    # Get FPS info
    fps_num = get_app().project.get("fps").get("num", 24)
    fps_den = get_app().project.get("fps").get("den", 1)
    fps_float = float(fps_num / fps_den)

    # Get EDL path
    recommended_path = app.project.current_filepath or ""
    if not recommended_path:
        recommended_path = os.path.join(info.HOME_PATH, "%s.edl" % _("Untitled Project"))
    else:
        for ext in (info.PROJECT_EXT, info.LEGACY_PROJECT_EXT):
            recommended_path = recommended_path.replace(ext, ".edl")
    file_path = QFileDialog.getSaveFileName(app.window, _("Export EDL..."), recommended_path,
                                            _("Edit Decision List (*.edl)"))[0]
    if not file_path:
        return

    # Append .edl if needed
    if not file_path.endswith(".edl"):
        file_path = "%s.edl" % file_path

    export_root = os.path.dirname(os.path.abspath(file_path))

    # Get filename with no extension
    file_name_with_ext = os.path.basename(file_path)
    file_name = os.path.splitext(file_name_with_ext)[0]

    all_tracks = get_app().project.get("layers")
    track_count = len(all_tracks)
    for track in reversed(sorted(all_tracks, key=itemgetter('number'))):
        existing_track = Track.get(number=track.get("number"))
        if not existing_track:
            # Log error and fail silently, and continue
            log.error('No track object found with number: %s' % track.get("number"))
            continue

        # Track name
        track_name = track.get("label") or "TRACK %s" % track_count
        clips_on_track = sorted(Clip.filter(layer=track.get("number")), key=lambda c: c.data.get('position', 0.0))
        if not clips_on_track:
            continue

        # Generate EDL File (1 per track - limitation of EDL format)
        # TODO: Improve and move this into its own class
        with open("%s-%s.edl" % (file_path.replace(".edl", ""), track_name), 'w', encoding="utf8") as f:
            # Add Header
            f.write("TITLE: %s - %s\n" % (file_name, track_name))
            f.write("FCM: %s\n\n" % ("DROP FRAME" if _is_drop_frame(fps_num, fps_den) else "NON-DROP FRAME"))

            # Loop through each track
            export_position = 0.0
            event_index = 1

            # Loop through clips on this track
            for clip in clips_on_track:
                clip_position = clip.data.get('position', 0.0)
                clip_start = clip.data.get('start', 0.0)
                clip_end = clip.data.get('end', clip_start)
                clip_duration = clip_end - clip_start

                # Do we need a blank clip?
                if clip_position > export_position:
                    clip_start_time = secondsToTimecode(0.0, fps_num, fps_den)
                    clip_end_time = secondsToTimecode(clip_position - export_position, fps_num, fps_den)
                    timeline_start_time = secondsToTimecode(export_position, fps_num, fps_den)
                    timeline_end_time = secondsToTimecode(clip_position, fps_num, fps_den)

                    f.write(edl_string % (
                        event_index, "BL"[:9], "V"[:6], "C",
                        clip_start_time, clip_end_time,
                        timeline_start_time, timeline_end_time))
                    event_index += 1
                    export_position = clip_position

                # Format clip start/end and timeline start/end values (i.e. 00:00:00:00)
                clip_start_time = secondsToTimecode(clip_start, fps_num, fps_den)
                clip_end_time = secondsToTimecode(clip_end, fps_num, fps_den)
                timeline_start_time = secondsToTimecode(clip_position, fps_num, fps_den)
                timeline_end_time = secondsToTimecode(clip_position + clip_duration, fps_num, fps_den)

                has_video = clip.data.get("reader", {}).get("has_video", False)
                has_audio = clip.data.get("reader", {}).get("has_audio", False)
                if not has_video and not has_audio:
                    continue
                reel_name = clip.data.get("reel") or "AX"
                reel_video_tag = f"{reel_name} V"
                reel_audio_tag = f"{reel_name} A1"
                if has_video:
                    # Video Track
                    f.write(edl_string % (
                            event_index, reel_name[:9], "V"[:6], "C",
                            clip_start_time, clip_end_time,
                            timeline_start_time, timeline_end_time))
                if has_audio:
                    # Audio Track
                    f.write(edl_string % (
                            event_index, reel_name[:9], "A"[:6], "C",
                        clip_start_time, clip_end_time,
                        timeline_start_time, timeline_end_time))
                f.write("* FROM CLIP NAME: %s\n" % clip.data.get('title'))
                media_path = _clip_media_path(clip)
                relative_media = relative_export_path(media_path, export_root)
                if relative_media:
                    f.write("* SOURCE FILE: %s\n" % relative_media)

                # Add opacity data (if any)
                alpha_points = clip.data.get('alpha', {}).get('Points', [])
                if len(alpha_points) >= 1:
                    # Loop through Points (remove duplicates)
                    keyframes = {}
                    for point in alpha_points:
                        keyframeTime = (point.get('co', {}).get('X', 1.0) - 1) / fps_float
                        keyframeValue = point.get('co', {}).get('Y', 0.0) * 100.0
                        interp_name = _interp_name(point.get("interpolation"))
                        keyframes[keyframeTime] = (keyframeValue, interp_name)
                    # Write keyframe values to EDL
                    for opacity_time in sorted(keyframes.keys()):
                        opacity_value, interp_name = keyframes.get(opacity_time)
                        tc = secondsToTimecode(opacity_time, fps_num, fps_den)
                        f.write("* VIDEO LEVEL AT %s IS %s%% %s (REEL %s)\n" % (tc, _fmt_percent(opacity_value), interp_name.upper(), reel_video_tag))

                # Add volume data (if any)
                volume_points = clip.data.get('volume', {}).get('Points', [])
                if len(volume_points) >= 1:
                    # Loop through Points (remove duplicates)
                    keyframes = {}
                    for point in volume_points:
                        keyframeTime = (point.get('co', {}).get('X', 1.0) - 1) / fps_float
                        keyframeValue = _volume_to_db(point.get('co', {}).get('Y', 0.0))
                        interp_name = _interp_name(point.get("interpolation"))
                        keyframes[keyframeTime] = (keyframeValue, interp_name)
                    # Write keyframe values to EDL
                    for volume_time in sorted(keyframes.keys()):
                        volume_value, interp_name = keyframes.get(volume_time)
                        f.write("* AUDIO LEVEL AT %s IS %.2f DB %s (REEL %s)\n" % (secondsToTimecode(volume_time, fps_num, fps_den), volume_value, interp_name.upper(), reel_audio_tag))

                # Export transform keyframes (skip defaults)
                transform_defs = [
                    ("scale_x", "SCALE X", 100.0, 1.0, True),
                    ("scale_y", "SCALE Y", 100.0, 1.0, True),
                    ("location_x", "LOCATION X", 100.0, 0.0, True),
                    ("location_y", "LOCATION Y", 100.0, 0.0, True),
                    ("rotation", "ROTATION", 1.0, 0.0, False),
                    ("shear_x", "SHEAR X", 100.0, 0.0, True),
                    ("shear_y", "SHEAR Y", 100.0, 0.0, True),
                ]

                for key_name, label, multiplier, default_val, is_percent in transform_defs:
                    points = clip.data.get(key_name, {}).get("Points", [])
                    if not points:
                        continue
                    include_all = len(points) > 1
                    keyframes = {}
                    for point in points:
                        keyframeTime = (point.get('co', {}).get('X', 1.0) - 1) / fps_float
                        raw_value = point.get('co', {}).get('Y', default_val)
                        if not include_all and len(points) == 1 and abs(raw_value - default_val) < 1e-6:
                            continue  # single default point: skip
                        if not include_all and keyframes and abs(raw_value - default_val) < 1e-6:
                            continue  # avoid duplicate defaults when not including all
                        display_value = raw_value * multiplier if is_percent else raw_value
                        interp_name = _interp_name(point.get("interpolation"))
                        keyframes[keyframeTime] = (display_value, interp_name)
                    for t in sorted(keyframes.keys()):
                        val, interp_name = keyframes[t]
                        unit = "%" if is_percent else "DEG"
                        display_val = _fmt_percent(val) if is_percent else _fmt_value(val)
                        if unit == "%":
                            value_unit = "%s%%" % display_val
                        else:
                            value_unit = "%s %s" % (display_val, unit.strip())
                        f.write("* %s AT %s IS %s %s (REEL %s)\n" % (label, secondsToTimecode(t, fps_num, fps_den), value_unit, interp_name.upper(), reel_video_tag))

                # Update export position
                export_position = max(export_position, clip_position + clip_duration)
                event_index += 1
                f.write("\n")

            # Update counters
            track_count -= 1
