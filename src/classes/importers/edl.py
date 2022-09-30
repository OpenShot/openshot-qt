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
from classes.query import Clip, Track, File
from classes.time_parts import timecodeToSeconds
from windows.views.find_file import find_missing_file

# REGEX expressions to parse lines from EDL file
title_regex = re.compile(r"TITLE:[ ]+(.*)")
clips_regex = re.compile(r"(\d{3})[ ]+(.+?)[ ]+(.+?)[ ]+(.+?)[ ]+(.*)[ ]+(.*)[ ]+(.*)[ ]+(.*)")
clip_name_regex = re.compile(r"[*][ ]+FROM CLIP NAME:[ ]+(.*)")
opacity_regex = re.compile(r"[*][ ]+OPACITY LEVEL AT (.*) IS [+-]*(.*)%")
audio_level_regex = re.compile(r"[*][ ]+AUDIO LEVEL AT (.*) IS [+]*(.*)[ ]+DB.*")
fcm_regex = re.compile(r"FCM:[ ]+(.*)")


def create_clip(context, track):
    """Create a new clip based on this context dict"""
    app = get_app()
    _ = app._tr

    # Get FPS info
    fps_num = app.project.get("fps").get("num", 24)
    fps_den = app.project.get("fps").get("den", 1)
    fps_float = float(fps_num / fps_den)

    # Get clip path (and prompt user if path not found)
    clip_path, is_modified, is_skipped = find_missing_file(context.get("clip_path", ""))
    if is_skipped:
        return

    # Get video context
    video_ctx = context.get("AX", {}).get("V", {})
    audio_ctx = context.get("AX", {}).get("A", {})

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
        except:
            log.warning('Error building File object for %s' % clip_path, exc_info=1)

    if (file.data["media_type"] == "video" or file.data["media_type"] == "image"):
        # Determine thumb path
        thumb_path = os.path.join(info.THUMBNAIL_PATH, "%s.png" % file.data["id"])
    else:
        # Audio file
        thumb_path = os.path.join(info.PATH, "images", "AudioThumbnail.png")

    # Create Clip object
    clip = Clip()
    clip.data = json.loads(clip_obj.Json())
    clip.data["file_id"] = file.id
    clip.data["title"] = context.get("clip_path", "")
    clip.data["layer"] = track.data.get("number", 1000000)
    if video_ctx and not audio_ctx:
        # Only video
        clip.data["position"] = timecodeToSeconds(video_ctx.get("timeline_position", "00:00:00:00"), fps_num, fps_den)
        clip.data["start"] = timecodeToSeconds(video_ctx.get("clip_start_time", "00:00:00:00"), fps_num, fps_den)
        clip.data["end"] = timecodeToSeconds(video_ctx.get("clip_end_time", "00:00:00:00"), fps_num, fps_den)
        clip.data["has_audio"] = {
            "Points": [
                {
                    "co": {
                        "X": 1.0,
                        "Y": 0.0 # Disable audio
                    },
                    "interpolation": 2
                }
            ]
        }
    elif audio_ctx and not video_ctx:
        # Only audio
        clip.data["position"] = timecodeToSeconds(audio_ctx.get("timeline_position", "00:00:00:00"), fps_num, fps_den)
        clip.data["start"] = timecodeToSeconds(audio_ctx.get("clip_start_time", "00:00:00:00"), fps_num, fps_den)
        clip.data["end"] = timecodeToSeconds(audio_ctx.get("clip_end_time", "00:00:00:00"), fps_num, fps_den)
        clip.data["has_video"] = {
            "Points": [
                {
                    "co": {
                        "X": 1.0,
                        "Y": 0.0 # Disable video
                    },
                    "interpolation": 2
                }
            ]
        }
    else:
        # Both video and audio
        clip.data["position"] = timecodeToSeconds(video_ctx.get("timeline_position", "00:00:00:00"), fps_num, fps_den)
        clip.data["start"] = timecodeToSeconds(video_ctx.get("clip_start_time", "00:00:00:00"), fps_num, fps_den)
        clip.data["end"] = timecodeToSeconds(video_ctx.get("clip_end_time", "00:00:00:00"), fps_num, fps_den)

    # Add volume keyframes
    if context.get("volume"):
        clip.data["volume"] = {"Points": []}
        for keyframe in context.get("volume", []):
            clip.data["volume"]["Points"].append(
                {
                    "co": {
                        "X": round(timecodeToSeconds(keyframe.get("time", 0.0), fps_num, fps_den) * fps_float),
                        "Y": keyframe.get("value", 0.0)
                    },
                    "interpolation": 1 # linear
                }
            )

    # Add alpha keyframes
    if context.get("opacity"):
        clip.data["alpha"] = {"Points": []}
        for keyframe in context.get("opacity", []):
            clip.data["alpha"]["Points"].append(
                {
                    "co": {
                        "X": round(timecodeToSeconds(keyframe.get("time", 0.0), fps_num, fps_den) * fps_float),
                        "Y": keyframe.get("value", 0.0)
                    },
                    "interpolation": 1 # linear
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
    file_path = QFileDialog.getOpenFileName(app.window, _("Import EDL..."), recommended_path,
                                            _("Edit Decision List (*.edl)"), _("Edit Decision List (*.edl)"))[0]
    if os.path.exists(file_path):
        context = {}
        current_clip_index = ""

        # Get # of tracks
        all_tracks = app.project.get("layers")
        track_number = list(reversed(sorted(all_tracks, key=itemgetter('number'))))[0].get("number") + 1000000

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
                    context["title"] = r   # Project title

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
                            context = {"title": context.get("title"), "fcm": context.get("fcm")}

                        if tape not in context:
                            context[tape] = {}
                        if clip_type not in context[tape]:
                            context[tape][clip_type] = {}

                        # New clip detected
                        context["edit_index"] = edit_index                          # 001
                        context[tape][clip_type]["edit_type"] = r[3]                # C
                        context[tape][clip_type]["clip_start_time"] = r[4]          # 00:00:00:01
                        context[tape][clip_type]["clip_end_time"] = r[5]            # 00:00:03:01
                        context[tape][clip_type]["timeline_position"] = r[6]        # 00:00:30:01
                        context[tape][clip_type]["timeline_position_end"] = r[7]    # 00:00:33:01

                # Detect clip name
                for r in clip_name_regex.findall(line):
                    context["clip_path"] = r   # FileName.mp4

                # Detect opacity
                for r in opacity_regex.findall(line):
                    if len(r) == 2:
                        if "opacity" not in context:
                            context["opacity"] = []
                        keyframe_time = r[0]                    # 00:00:00:01
                        keyframe_value = float(r[1]) / 100.0    # 100.00 (scale 0 to 1)
                        context["opacity"].append({"time": keyframe_time, "value": keyframe_value})

                # Detect audio levels
                for r in audio_level_regex.findall(line):
                    if len(r) == 2:
                        if "volume" not in context:
                            context["volume"] = []
                        keyframe_time = r[0]                            # 00:00:00:01
                        keyframe_value = (float(r[1]) + 99.0) / 99.0    # -99.00 (scale 0 to 1)
                        context["volume"].append({"time": keyframe_time, "value": keyframe_value})

                # Detect FCM attribute
                for r in fcm_regex.findall(line):
                    context["fcm"] = r   # NON-DROP FRAME

            # Final edit needs committing
            create_clip(context, track)

            # Update the preview and reselect current frame in properties
            app.window.refreshFrameSignal.emit()
            app.window.propertyTableView.select_frame(app.window.preview_thread.player.Position())
