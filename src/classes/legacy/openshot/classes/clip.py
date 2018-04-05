"""
 @file
 @brief This file is for legacy support of OpenShot 1.x project files
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

import uuid
from classes.legacy.openshot.classes import keyframe


class clip:
    """This class represents a media clip on the timeline."""

    # ----------------------------------------------------------------------
    def __init__(self, clip_name, color, position_on_track, start_time, end_time, parent_track, file_object):
        """Constructor"""

        # init variables for clip object
        self.name = clip_name  # the name of the clip
        self.color = color  # the color of the clip, used to organize clips
        self.start_time = start_time  # the time in seconds where we start playing a clip
        self.end_time = end_time  # the time in seconds where we stop playing a clip
        self.speed = 1.0  # the rate of playback (this will change if you want to slow down or speed up the clip)
        self.max_length = 0.0  # this is the max length of the clip in seconds
        self.position_on_track = float(
            position_on_track)  # the time in seconds to start playing the clip relative to the track
        self.play_video = True
        self.play_audio = True
        self.fill = True
        self.distort = False
        self.composite = True
        self.halign = "centre"
        self.valign = "centre"
        self.reversed = False
        self.volume = 100.0
        self.audio_fade_in = False
        self.audio_fade_out = False
        self.audio_fade_in_amount = 2.0
        self.audio_fade_out_amount = 2.0
        self.video_fade_in = False
        self.video_fade_out = False
        self.video_fade_in_amount = 2.0
        self.video_fade_out_amount = 2.0
        self.parent = parent_track  # the parent track this clip lives on
        self.file_object = file_object  # the file object that this clip is linked to
        self.unique_id = str(uuid.uuid1())
        self.rotation = 0.0
        self.thumb_location = ""

        # init key-frame dictionary
        self.keyframes = {"start": keyframe(0, 100.0, 100.0, 0.0, 0.0, 1.0),
                          "end": keyframe(-1, 100.0, 100.0, 0.0, 0.0, 1.0)}

        # init effects dictionary
        self.effects = []

        # init vars for drag n drop
        self.drag_x = 0.0
        self.drag_y = 0.0
        self.moved = False
        self.is_timeline_scrolling = False
