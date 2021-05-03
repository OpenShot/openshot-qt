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


class track:
    """The track class contains a simple grouping of clips on the same layer (aka track)."""

    # ----------------------------------------------------------------------
    def __init__(self, track_name, parent_sequence):
        """Constructor"""

        # init variables for sequence
        self.name = track_name
        self.x = 10  # left x coordinate to start the track
        self.y_top = 0  # top y coordinate of this track
        self.y_bottom = 0  # bottom y coordinate of this track
        self.parent = parent_sequence  # reference to parent sequence object
        self.play_video = True
        self.play_audio = True
        self.unique_id = str(uuid.uuid1())

        # init the tracks on the sequence
        self.clips = []

        # init transitions
        self.transitions = []
