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


class transition:
    """This class represents a media clip on the timeline."""

    # ----------------------------------------------------------------------
    def __init__(self, name, position_on_track, length, resource, parent, type="transition", mask_value=50.0):
        """Constructor"""

        # init variables for clip object
        self.name = name
        self.position_on_track = float(position_on_track)  # the time in seconds where the transition starts on the timeline
        self.length = float(length)  # the length in seconds of this transition
        self.resource = resource  # Any grey-scale image, or leave empty for a dissolve
        self.softness = 0.3  # 0.0 = no softness. 1.0 = too soft.
        self.reverse = False
        self.unique_id = str(uuid.uuid1())
        self.parent = parent  # the sequence

        # mask settings
        self.type = type  # transition or mask
        self.mask_value = mask_value  # 0.0 to 1.0

        # init vars for drag n drop
        self.drag_x = 0.0
        self.drag_y = 0.0
