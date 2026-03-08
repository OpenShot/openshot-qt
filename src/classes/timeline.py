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


class TimelineSync(UpdateInterface):
    """ This class syncs changes from the timeline to libopenshot """

    def __init__(self, window):
        self.app = get_app()
        self.window = window
        project = self.app.project

        # Get some settings from the project
        fps = project.get("fps")
        width = project.get("width")
        height = project.get("height")
        sample_rate = project.get("sample_rate")
        channels = project.get("channels")
        channel_layout = project.get("channel_layout")

        # Create an instance of a libopenshot Timeline object
        self.timeline = openshot.Timeline(width, height, openshot.Fraction(fps["num"], fps["den"]),
                                          sample_rate, channels, channel_layout)
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
        if action and len(action.key) >= 1 and action.key[0].lower() in ["files", "history", "markers", "layers", "scale", "profile", "export_settings", "export_overrides"]:
            return

        # Disable video caching temporarily
        caching_value = openshot.Settings.Instance().ENABLE_PLAYBACK_CACHING
        openshot.Settings.Instance().ENABLE_PLAYBACK_CACHING = False

        try:
            if action.type == "load":
                # Clear any selections in UI (since we are clearing the timeline)
                self.window.clearSelections()

                # Clear any existing clips & effects (free memory)
                self.timeline.Close()
                self.timeline.Clear()

                # This JSON is initially loaded to libopenshot to update the timeline
                self.timeline.SetJson(action.json(only_value=True))
                self.timeline.Open()  # Re-Open the Timeline reader

                # The timeline's profile changed, so update all clips
                self.timeline.ApplyMapperToClips()

                # Always seek back to frame 1
                self.window.SeekSignal.emit(1)

                # Refresh current frame (since the entire timeline was updated)
                self.window.refreshFrameSignal.emit()

            else:
                # This JSON DIFF is passed to libopenshot to update the timeline
                self.timeline.ApplyJsonDiff(action.json(is_array=True))

        except Exception as e:
            log.error("Error applying JSON to timeline object in libopenshot: %s. %s" %
                     (e, action.json(is_array=True)))

        # Resume video caching original value
        openshot.Settings.Instance().ENABLE_PLAYBACK_CACHING = caching_value

    def MaxSizeChangedCB(self, new_size):
        """Callback for max sized change (i.e. max size of video widget)"""
        while not self.window.initialized:
            log.info('Waiting for main window to initialize before calling SetMaxSize')
            time.sleep(0.5)

        # Increase based on DPI
        device_pixel_ratio = self.window.devicePixelRatioF()
        scaled_width = round(new_size.width() * device_pixel_ratio)
        scaled_height = round(new_size.height() * device_pixel_ratio)

        log.info(f"Adjusting max size of preview image: {scaled_width}x{scaled_height}")

        # Set new max video size (Based on preview widget size and display scaling)
        previous_preview_width = self.timeline.preview_width
        previous_preview_height = self.timeline.preview_height

        self.timeline.SetMaxSize(scaled_width, scaled_height)

        if (
            previous_preview_width != self.timeline.preview_width
            or previous_preview_height != self.timeline.preview_height
        ):
            # Clear timeline preview cache (since our video size has changed)
            self.timeline.ClearAllCache(True)

            # Refresh current frame (since the entire timeline was updated)
            self.window.refreshFrameSignal.emit()
