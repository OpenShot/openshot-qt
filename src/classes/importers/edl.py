"""
@file
@brief This file is used to import an EDL (edit decision list) file
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

import json
import os
import re
from operator import itemgetter

import openshot
from PyQt5.QtWidgets import QFileDialog

from classes import info
from classes.app import get_app
from classes.logger import log
from classes.image_types import get_media_type
from classes.path_utils import absolute_path_from_export
from classes.query import Clip, Track, File
from classes.time_parts import timecodeToSeconds
from windows.views.find_file import find_missing_file

# REGEX expressions to parse lines from EDL file
title_regex = re.compile(r"TITLE:[ ]+(.*)")
clips_regex = re.compile(r"(\d{3})[ ]+(.+?)[ ]+(.+?)[ ]+(.+?)[ ]+(.*)[ ]+(.*)[ ]+(.*)[ ]+(.*)")
clip_name_regex = re.compile(r"[*][ ]+FROM CLIP NAME:[ ]+(.*)")
source_regex = re.compile(r"[*][ ]+SOURCE FILE:[ ]+(.*)")
_PERMISSIVE = r"[ ]*;?[ ]*(?:interp[:=])?[ ]*([A-Za-z0-9]+)?(?:.*)?$"
param_regexes = [
    ("opacity", re.compile(r"\* (?:OPACITY|VIDEO) LEVEL AT\s+([0-9:;]+)\s+IS\s+([+-]?[0-9.]+)\s*%?\s*" + _PERMISSIVE, re.IGNORECASE)),
    ("volume", re.compile(r"\* AUDIO LEVEL AT\s+([0-9:;]+)\s+IS\s+([+-]?[0-9.]+)\s*d[bB]?\s*" + _PERMISSIVE, re.IGNORECASE)),
    ("scale_x", re.compile(r"\* SCALE X AT\s+([0-9:;]+)\s+IS\s+([+-]?[0-9.]+)\s*%?\s*" + _PERMISSIVE, re.IGNORECASE)),
    ("scale_y", re.compile(r"\* SCALE Y AT\s+([0-9:;]+)\s+IS\s+([+-]?[0-9.]+)\s*%?\s*" + _PERMISSIVE, re.IGNORECASE)),
    ("location_x", re.compile(r"\* LOCATION X AT\s+([0-9:;]+)\s+IS\s+([+-]?[0-9.]+)\s*%?\s*" + _PERMISSIVE, re.IGNORECASE)),
    ("location_y", re.compile(r"\* LOCATION Y AT\s+([0-9:;]+)\s+IS\s+([+-]?[0-9.]+)\s*%?\s*" + _PERMISSIVE, re.IGNORECASE)),
    ("rotation", re.compile(r"\* ROTATION AT\s+([0-9:;]+)\s+IS\s+([+-]?[0-9.]+)\s*(?:deg)?\s*" + _PERMISSIVE, re.IGNORECASE)),
    ("shear_x", re.compile(r"\* SHEAR X AT\s+([0-9:;]+)\s+IS\s+([+-]?[0-9.]+)\s*%?\s*" + _PERMISSIVE, re.IGNORECASE)),
    ("shear_y", re.compile(r"\* SHEAR Y AT\s+([0-9:;]+)\s+IS\s+([+-]?[0-9.]+)\s*%?\s*" + _PERMISSIVE, re.IGNORECASE)),
]
fcm_regex = re.compile(r"FCM:[ ]+(.*)")


def _interp_from_name(name):
    n = (str(name) if name is not None else "").strip().lower()
    # libopenshot: 0=bezier, 1=linear, 2=constant
    if n.isdigit():
        try:
            numeric = int(n)
        except ValueError:
            numeric = None
    else:
        numeric = None
    if numeric == 0:
        return openshot.BEZIER
    if numeric == 1:
        return openshot.LINEAR
    if numeric == 2:
        return openshot.CONSTANT
    if n.startswith("bez"):
        return openshot.BEZIER
    if n.startswith("hold") or n.startswith("const"):
        return openshot.CONSTANT
    return openshot.LINEAR


def _db_to_volume(db_value):
    """Convert dB to linear 0-1, with floor at -96 dB."""
    try:
        db = float(db_value)
    except (TypeError, ValueError):
        return 0.0
    if db <= -96.0:
        return 0.0
    linear = 10 ** (db / 20.0)
    return max(0.0, min(1.0, linear))


def create_clip(context, track):
    """Create a new clip based on this context dict"""
    app = get_app()
    _ = app._tr

    # Get FPS info
    fps_num = app.project.get("fps").get("num", 24)
    fps_den = app.project.get("fps").get("den", 1)
    fps_float = float(fps_num / fps_den)

    clip_path_value = context.get("clip_path") or context.get("clip_title") or ""
    clip_path_value = clip_path_value or ""

    # Get clip path (and prompt user if path not found)
    clip_path, is_modified, is_skipped = find_missing_file(clip_path_value)
    if is_skipped:
        return

    # Get component contexts
    video_ctx = context.get("video_ctx", {})
    audio_ctx_list = context.get("audio_ctx", [])
    audio_ctx = audio_ctx_list[0] if audio_ctx_list else {}

    if not (video_ctx or audio_ctx):
        # Nothing to import (likely filler)
        return

    # Check for this path in our existing project data
    file = File.get(path=clip_path)

    # Load filepath in libopenshot clip object (which will try multiple readers to open it)
    clip_obj = openshot.Clip(clip_path)

    if not file:
        # Get the JSON for the clip's internal reader
        try:
            reader = clip_obj.Reader()
            file_data = json.loads(reader.Json())

            # Determine media type
            file_data["media_type"] = get_media_type(file_data)

            # Save new file to the project data
            file = File()
            file.data = file_data

            # Save file
            file.save()
        except Exception:
            log.warning("Error building File object for %s" % clip_path, exc_info=1)

    if file.data["media_type"] == "video" or file.data["media_type"] == "image":
        # Determine thumb path
        thumb_path = os.path.join(info.THUMBNAIL_PATH, "%s.png" % file.data["id"])
    else:
        # Audio file
        thumb_path = os.path.join(info.PATH, "images", "AudioThumbnail.png")

    # Create Clip object
    clip = Clip()
    clip.data = json.loads(clip_obj.Json())
    clip.data["file_id"] = file.id
    clip_title = context.get("clip_title") or os.path.basename(clip_path_value) or clip_path_value
    clip.data["title"] = clip_title
    clip.data["layer"] = track.data.get("number", 1000000)
    reel_name = (video_ctx or audio_ctx).get("reel") if (video_ctx or audio_ctx) else None
    if not reel_name and audio_ctx_list:
        reel_name = audio_ctx_list[0].get("reel")
    if reel_name:
        clip.data["reel"] = reel_name

    if video_ctx and not audio_ctx:
        # Only video
        clip.data["position"] = timecodeToSeconds(
            video_ctx.get("timeline_position", "00:00:00:00"), fps_num, fps_den
        )
        clip.data["start"] = timecodeToSeconds(
            video_ctx.get("clip_start_time", "00:00:00:00"), fps_num, fps_den
        )
        clip.data["end"] = timecodeToSeconds(
            video_ctx.get("clip_end_time", "00:00:00:00"), fps_num, fps_den
        )
        clip.data["has_audio"] = {
            "Points": [
                {
                    "co": {
                        "X": 1.0,
                        "Y": 0.0,  # Disable audio
                    },
                    "interpolation": 2,
                }
            ]
        }
    elif audio_ctx and not video_ctx:
        # Only audio
        clip.data["position"] = timecodeToSeconds(
            audio_ctx.get("timeline_position", "00:00:00:00"), fps_num, fps_den
        )
        clip.data["start"] = timecodeToSeconds(
            audio_ctx.get("clip_start_time", "00:00:00:00"), fps_num, fps_den
        )
        clip.data["end"] = timecodeToSeconds(
            audio_ctx.get("clip_end_time", "00:00:00:00"), fps_num, fps_den
        )
        clip.data["has_video"] = {
            "Points": [
                {
                    "co": {
                        "X": 1.0,
                        "Y": 0.0,  # Disable video
                    },
                    "interpolation": 2,
                }
            ]
        }
    else:
        # Both video and audio
        clip.data["position"] = timecodeToSeconds(
            video_ctx.get("timeline_position", "00:00:00:00"), fps_num, fps_den
        )
        clip.data["start"] = timecodeToSeconds(
            video_ctx.get("clip_start_time", "00:00:00:00"), fps_num, fps_den
        )
        clip.data["end"] = timecodeToSeconds(
            video_ctx.get("clip_end_time", "00:00:00:00"), fps_num, fps_den
        )

    # Add volume keyframes
    if context.get("volume"):
        clip.data["volume"] = {"Points": []}
        for keyframe in context.get("volume", []):
            clip.data["volume"]["Points"].append(
                {
                    "co": {
                        "X": round(
                            timecodeToSeconds(
                                keyframe.get("time", 0.0), fps_num, fps_den
                            ) * fps_float
                        ),
                        "Y": keyframe.get("value", 0.0),
                    },
                    "interpolation": _interp_from_name(keyframe.get("interp")),
                }
            )

    # Add alpha keyframes (from opacity)
    if context.get("opacity"):
        clip.data["alpha"] = {"Points": []}
        for keyframe in context.get("opacity", []):
            clip.data["alpha"]["Points"].append(
                {
                    "co": {
                        "X": round(
                            timecodeToSeconds(
                                keyframe.get("time", 0.0), fps_num, fps_den
                            ) * fps_float
                        ),
                        "Y": keyframe.get("value", 0.0),
                    },
                    "interpolation": _interp_from_name(keyframe.get("interp")),
                }
            )

    # Add transform keyframes
    for field in ("scale_x", "scale_y", "location_x", "location_y", "rotation", "shear_x", "shear_y"):
        if context.get(field):
            clip.data[field] = {"Points": []}
            for keyframe in context.get(field, []):
                clip.data[field]["Points"].append(
                    {
                        "co": {
                            "X": round(
                                timecodeToSeconds(
                                    keyframe.get("time", 0.0), fps_num, fps_den
                                ) * fps_float
                            ),
                            "Y": keyframe.get("value", 0.0),
                        },
                        "interpolation": _interp_from_name(keyframe.get("interp")),
                    }
                )

    # Save clip
    clip.save()


def import_edl():
    """Import EDL File"""
    app = get_app()
    _ = app._tr

    # Get EDL path
    recommended_path = app.project.current_filepath or ""
    if not recommended_path:
        recommended_path = info.HOME_PATH
    else:
        recommended_path = os.path.dirname(recommended_path)
    file_path = QFileDialog.getOpenFileName(
        app.window,
        _("Import EDL..."),
        recommended_path,
        _("Edit Decision List (*.edl)"),
        _("Edit Decision List (*.edl)"),
    )[0]
    if os.path.exists(file_path):
        context = {"audio_ctx": []}
        current_clip_index = ""
        edl_folder = os.path.dirname(os.path.abspath(file_path))

        # Get # of tracks
        all_tracks = app.project.get("layers")
        track_number = list(
            reversed(sorted(all_tracks, key=itemgetter("number")))
        )[0].get("number") + 1000000

        # Create new track above existing layer(s)
        track = Track()
        track.data = {"number": track_number, "y": 0, "label": "EDL Import", "lock": False}
        track.save()

        # Open EDL file
        with open(file_path, "r") as f:
            # Loop through each line, and compare against regex expressions
            for line in f:
                # Detect title
                for r in title_regex.findall(line):
                    context["title"] = r  # Project title

                # Detect clips
                for r in clips_regex.findall(line):
                    if len(r) == 8:
                        edit_index = r[0]   # 001
                        tape = r[1]         # BL, AX
                        clip_type = r[2]    # V, A
                        if tape == "BL":
                            # Ignore
                            continue
                        if current_clip_index == "":
                            # first clip, ignore for now
                            current_clip_index = edit_index
                        if current_clip_index != edit_index:
                            # clip changed, time to commit previous context
                            create_clip(context, track)

                            # reset context
                            current_clip_index = edit_index
                            context = {
                                "title": context.get("title"),
                                "fcm": context.get("fcm"),
                                "audio_ctx": [],
                            }

                        # New clip detected
                        context["edit_index"] = edit_index  # 001

                        component_ctx = {
                            "reel": tape,
                            "edit_type": r[3],
                            "clip_start_time": r[4],
                            "clip_end_time": r[5],
                            "timeline_position": r[6],
                            "timeline_position_end": r[7],
                        }

                        clip_type_key = clip_type.strip().upper()
                        if clip_type_key.startswith("V"):
                            context["video_ctx"] = component_ctx
                        elif clip_type_key.startswith("A"):
                            context.setdefault("audio_ctx", [])
                            context["audio_ctx"].append(component_ctx)

                # Detect clip name
                for r in clip_name_regex.findall(line):
                    context["clip_title"] = r
                    if "clip_path" not in context or not context.get("clip_path"):
                        context["clip_path"] = absolute_path_from_export(r, edl_folder)

                for r in source_regex.findall(line):
                    resolved_path = absolute_path_from_export(r, edl_folder)
                    context["clip_path"] = resolved_path

                # Detect keyframe comments
                for field, regex in param_regexes:
                    for r in regex.findall(line):
                        if len(r) >= 2:
                            context.setdefault(field, [])
                            keyframe_time = r[0]
                            raw_val = r[1]
                            interp_name = r[2].strip() if len(r) > 2 and r[2] else None
                            if not interp_name:
                                m = re.search(r"interp[:=]\s*([^\s)]+)", line, re.IGNORECASE)
                                if m:
                                    interp_name = m.group(1)

                            # NOTE: opacity is stored as 0–1, volume via dB→linear,
                            # and most % based params are normalized 0–1.
                            if field == "opacity":
                                keyframe_value = float(raw_val) / 100.0
                            elif field == "volume":
                                keyframe_value = _db_to_volume(raw_val)
                            elif field in ("scale_x", "scale_y", "location_x", "location_y", "shear_x", "shear_y"):
                                keyframe_value = float(raw_val) / 100.0
                            else:
                                keyframe_value = float(raw_val)

                            context[field].append(
                                {"time": keyframe_time, "value": keyframe_value, "interp": interp_name}
                            )

                # Detect FCM attribute
                for r in fcm_regex.findall(line):
                    context["fcm"] = r   # NON-DROP FRAME

            # Final edit needs committing
            create_clip(context, track)

            # Update the preview and reselect current frame in properties
            app.window.refreshFrameSignal.emit()
            app.window.propertyTableView.select_frame(
                app.window.preview_thread.player.Position()
            )
