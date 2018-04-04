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


class sequence:
    """A sequence contains tracks and clips that make up a scene (aka sequence).  Currently, Openshot
    only contains a single sequence, but soon it will have the ability to create many sequences."""

    # ----------------------------------------------------------------------
    def __init__(self, seq_name, project):
        """Constructor"""

        # init variables for sequence
        self.name = seq_name
        self.length = 600.0  # length in seconds of sequence.  This controls how wide to render the tracks.
        self.project = project  # reference to current project
        self.scale = 8.0  # this represents how many seconds per tick mark
        self.tick_pixels = 100  # number of pixels between each tick mark
        self.play_head_position = 0.0  # position of the play head in seconds

        # init the tracks on the sequence
        self.tracks = []

        # init markers
        self.markers = []

        # reference to play_head goocanvas group
        self.play_head = None
        self.ruler_time = None
        self.play_head_line = None
        self.enable_animated_playhead = True
