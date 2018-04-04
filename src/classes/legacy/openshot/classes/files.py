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


class OpenShotFile:
    """The generic file object for OpenShot"""

    # ----------------------------------------------------------------------
    def __init__(self, project=None):
        """Constructor"""
        self.project = project

        # init the variables for the File Object
        self.name = ""  # short / friendly name of the file
        self.length = 0.0  # length in seconds
        self.videorate = (30, 0)  # audio rate or video framerate
        self.file_type = ""  # video, audio, image, image sequence
        self.max_frames = 0.0
        self.fps = 0.0
        self.height = 0
        self.width = 0
        self.label = ""  # user description of the file
        self.thumb_location = ""  # file uri of preview thumbnail
        self.ttl = 1  # time-to-live - only used for image sequence.  Represents the # of frames per image.

        self.unique_id = str(uuid.uuid1())
        self.parent = None
        self.project = project  # reference to project

        self.video_codec = ""
        self.audio_codec = ""
        self.audio_frequency = ""
        self.audio_channels = ""


class OpenShotFolder:
    """The generic folder object for OpenShot"""

    # ----------------------------------------------------------------------
    def __init__(self, project=None):
        """Constructor"""

        # Init the variables for the Folder Object
        self.name = ""  # short / friendly name of the folder
        self.location = ""  # file system location
        self.parent = None
        self.project = project

        self.label = ""  # user description of the folder
        self.unique_id = str(uuid.uuid1())

        # init the list of files & folders
        # this list can contain OpenShotFolder or OpenShotFile objects
        # the order of this list determines the order of the tree items
        self.items = []

        # this queue holds files that are currently being added. this prevents
        # duplicate files to be added at the same time
        self.queue = []
