""" 
 @file
 @brief This file contains a timeline object, which listens for updates and syncs a libopenshot timeline object
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

import time
import openshot  # Python module for libopenshot (required video editing module installed separately)

from classes.updates import UpdateInterface
from classes.logger import log
from classes.app import get_app
from classes import settings


class TimelineSync(UpdateInterface):
    """ This class syncs changes from the timeline to libopenshot """

    def __init__(self, window):
        self.app = get_app()
        self.window = window
        project = self.app.project
        s = settings.get_settings()

        # Get some settings from the project
        fps = project.get(["fps"])
        width = project.get(["width"])
        height = project.get(["height"])
        sample_rate = project.get(["sample_rate"])
        channels = project.get(["channels"])
        channel_layout = project.get(["channel_layout"])

        # Create an instance of a libopenshot Timeline object
        self.timeline = openshot.Timeline(width, height, openshot.Fraction(fps["num"], fps["den"]), sample_rate, channels,
                                          channel_layout)
        self.timeline.info.channel_layout = channel_layout
        self.timeline.info.has_audio = True
        self.timeline.info.has_video = True
        self.timeline.info.video_length = 99999
        self.timeline.info.duration = 999.99
        self.timeline.info.sample_rate = sample_rate
        self.timeline.info.channels = channels

        # Open the timeline reader
        self.timeline.Open()

        # Add self as listener to project data updates (at the beginning of the list)
        # This listener will receive events before others.
        self.app.updates.add_listener(self, 0)

        # Connect to signal
        self.window.MaxSizeChanged.connect(self.MaxSizeChangedCB)

    def changed(self, action):
        """ This method is invoked by the UpdateManager each time a change happens (i.e UpdateInterface) """

        # Ignore changes that don't affect libopenshot
        if len(action.key) >= 1 and action.key[0].lower() in ["files", "history", "markers", "layers", "export_path", "import_path", "scale"]:
            return

        elif len(action.key) >= 1 and action.key[0].lower() in ["profile"]:

            # The timeline's profile changed, so update all clips
            self.timeline.ApplyMapperToClips()
            return

        # Pass the change to the libopenshot timeline
        try:
            if action.type == "load":
                # This JSON is initially loaded to libopenshot to update the timeline
                self.timeline.SetJson(action.json(only_value=True))
                self.timeline.Open()  # Re-Open the Timeline reader

                # The timeline's profile changed, so update all clips
                self.timeline.ApplyMapperToClips()

                # Refresh current frame (since the entire timeline was updated)
                self.window.refreshFrameSignal.emit()

            else:
                # This JSON DIFF is passed to libopenshot to update the timeline
                self.timeline.ApplyJsonDiff(action.json(is_array=True))

        except Exception as e:
            log.info("Error applying JSON to timeline object in libopenshot: %s. %s" % (e, action.json(is_array=True)))

    def MaxSizeChangedCB(self, new_size):
        """Callback for max sized change (i.e. max size of video widget)"""
        while not self.window.initialized:
            log.info('Waiting for main window to initialize before calling SetMaxSize')
            time.sleep(0.5)

        log.info("Adjusting max size of preview image: %s" % new_size)

        # Clear timeline preview cache (since our video size has changed)
        self.timeline.ClearAllCache()

        # Set new max video size (Based on preview widget size)
        self.timeline.SetMaxSize(new_size.width(), new_size.height())
