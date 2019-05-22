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

import os
import re
from operator import itemgetter

from PyQt5.QtWidgets import *

from classes import info
from classes.app import get_app
from classes.logger import log
from classes.query import Clip, Track
from classes.time_parts import secondsToTime

# REGEX expressions to parse lines from EDL file
title_regex = re.compile(r"TITLE:[ ]+(.*)")
clips_regex = re.compile(r"(\d{3})[ ]+(.+?)[ ]+(.+?)[ ]+(.+?)[ ]+(.*)[ ]+(.*)[ ]+(.*)[ ]+(.*)")
clip_name_regex = re.compile(r"[*][ ]+FROM CLIP NAME:[ ]+(.*)")
opacity_regex = re.compile(r"[*][ ]+OPACITY LEVEL AT (.*) IS [+-]*(.*)%")
audio_level_regex = re.compile(r"[*][ ]+AUDIO LEVEL AT (.*) IS [+]*(.*)[ ]+DB.*")
fcm_regex = re.compile(r"FCM:[ ]+(.*)")


def import_edl():
    """Import EDL File"""
    app = get_app()
    _ = app._tr

    # Get FPS info
    fps_num = get_app().project.get(["fps"]).get("num", 24)
    fps_den = get_app().project.get(["fps"]).get("den", 1)
    fps_float = float(fps_num / fps_den)

    # Get EDL path
    recommended_path = app.project.current_filepath or ""
    if not recommended_path:
        recommended_path = info.HOME_PATH
    else:
        recommended_path = os.path.split(recommended_path)[0]
    file_path, file_type = QFileDialog.getOpenFileName(get_app().window, _("Import EDL..."), recommended_path,
                                                       _("Edit Decision Lists (*.edl)"), _("Edit Decision Lists (*.edl)"))
    if os.path.exists(file_path):
        context = {}
        current_clip_index = ""

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
                            print("commit context for %s" % context)

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
                for r in clips_regex.findall(line):
                    if len(r) == 2:
                        if "opacity" not in context:
                            context["opacity"] = []

                        keyframe_time = r[0]    # 00:00:00:01
                        keyframe_value = r[1]   # 100.00
                        context["opacity"].append({"time": keyframe_time, "value": keyframe_value})

                # Detect FCM attribute
                for r in fcm_regex.findall(line):
                    context["fcm"] = r   # NON-DROP FRAME

            # Final edit needs committing
            print("commit context for %s" % context)