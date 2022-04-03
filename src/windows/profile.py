"""
 @file
 @brief This file loads the Choose Profile dialog
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
import functools

import openshot  # Python module for libopenshot (required video editing module installed separately)

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QDialog

from classes import info, ui_util
from classes.app import get_app
from classes.logger import log
from classes.metrics import track_metric_screen


class Profile(QDialog):
    """ Choose Profile Dialog """

    # Path to ui file
    ui_path = os.path.join(info.PATH, 'windows', 'ui', 'profile.ui')

    def __init__(self):

        # Create dialog class
        QDialog.__init__(self)

        # Load UI from designer & init
        ui_util.load_ui(self, self.ui_path)
        ui_util.init_ui(self)

        # get translations
        _ = get_app()._tr

        # Pause playback
        get_app().window.PauseSignal.emit()

        # Track metrics
        track_metric_screen("profile-screen")

        # Keep track of starting selection
        self.initial_index = 0

        # Loop through profiles
        self.profile_names = []
        self.profile_paths = {}
        for profile_folder in [info.USER_PROFILES_PATH, info.PROFILES_PATH]:
            for file in os.listdir(profile_folder):
                profile_path = os.path.join(profile_folder, file)
                try:
                    # Load Profile
                    profile = openshot.Profile(profile_path)

                    # Add description of Profile to list
                    profile_name = "%s (%sx%s)" % (profile.info.description, profile.info.width, profile.info.height)
                    self.profile_names.append(profile_name)
                    self.profile_paths[profile_name] = profile_path

                except RuntimeError as e:
                    # This exception occurs when there's a problem parsing
                    # the Profile file - display a message and continue
                    log.error("Failed to parse file '%s' as a profile: %s" % (profile_path, e))

        # Sort list
        self.profile_names.sort()

        # Loop through sorted profiles
        for box_index, profile_name in enumerate(self.profile_names):
            # Add to dropdown
            self.cboProfile.addItem(profile_name, self.profile_paths[profile_name])

            # Set default (if it matches the project)
            if get_app().project.get(['profile']) in profile_name:
                self.initial_index = box_index

        # Connect signals
        self.cboProfile.currentIndexChanged.connect(self.dropdown_index_changed)
        self.cboProfile.activated.connect(self.dropdown_activated)

        # Set current item (from project)
        self.cboProfile.setCurrentIndex(self.initial_index)

    def dropdown_index_changed(self, index):
        # Get profile path
        value = self.cboProfile.itemData(index)

        # Load profile
        profile = openshot.Profile(value)

        # Set labels
        self.lblSize.setText("%sx%s" % (profile.info.width, profile.info.height))
        self.lblFPS.setText("%0.2f" % (profile.info.fps.ToFloat()))
        # (Note: Takes advantage of openshot.Fraction's __string__ method
        # which outputs the value with the format "{num}:{den}")
        self.lblOther.setText("DAR: %s, SAR: %s, Interlaced: %s" % (
            profile.info.display_ratio,
            profile.info.pixel_ratio,
            profile.info.interlaced_frame))

    def dropdown_activated(self, index):
        # Ignore if the selection wasn't changed
        if index == self.initial_index:
            return

        win = get_app().window
        proj = get_app().project
        updates = get_app().updates

        # Get profile path & load
        value = self.cboProfile.itemData(index)
        profile = openshot.Profile(value)

        # Get current FPS (prior to changing)
        current_fps = proj.get("fps")
        current_fps_float = float(current_fps["num"]) / float(current_fps["den"])
        fps_factor = float(profile.info.fps.ToFloat() / current_fps_float)

        # Update timeline settings
        updates.update(["profile"], profile.info.description)
        updates.update(["width"], profile.info.width)
        updates.update(["height"], profile.info.height)
        updates.update(["fps"], {
            "num": profile.info.fps.num,
            "den": profile.info.fps.den,
            })
        updates.update(["display_ratio"], {
            "num": profile.info.display_ratio.num,
            "den": profile.info.display_ratio.den,
            })
        updates.update(["pixel_ratio"], {
            "num": profile.info.pixel_ratio.num,
            "den": profile.info.pixel_ratio.den,
            })

        # Rescale all keyframes and reload project
        if fps_factor != 1.0:
            # Get a copy of rescaled project data (this does not modify the active project... yet)
            rescaled_app_data = proj.rescale_keyframes(fps_factor)

            # Apply rescaled data to active project
            proj._data = rescaled_app_data

            # Distribute all project data through update manager
            updates.load(rescaled_app_data)

        # Force ApplyMapperToClips to apply these changes
        win.timeline_sync.timeline.ApplyMapperToClips()

        # Update Window Title and stored index
        win.SetWindowTitle(profile.info.description)
        self.initial_index = index

        # Reset the playhead position (visually it moves anyway)
        win.SeekSignal.emit(1)
        # Refresh frame (since size of preview might have changed)
        QTimer.singleShot(500, win.refreshFrameSignal.emit)
