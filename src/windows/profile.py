"""
 @file
 @brief This file loads the Choose Profile dialog
 @author Jonathan Thomas <jonathan@openshot.org>

 @section LICENSE

 Copyright (c) 2008-2016 OpenShot Studios, LLC
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
import sys
import functools

from PyQt5.QtCore import *
from PyQt5.QtGui import QIcon, QStandardItemModel, QStandardItem
from PyQt5.QtWidgets import *
from PyQt5 import uic
import openshot  # Python module for libopenshot (required video editing module installed separately)

from classes import info, ui_util, settings, qt_types, updates
from classes.app import get_app
from classes.logger import log
from classes.metrics import *


class Profile(QDialog):
    """ Choose Profile Dialog """

    # Path to ui file
    ui_path = os.path.join(info.PATH, 'windows', 'ui', 'profile.ui')

    def __init__(self):

        # Create dialog class
        QDialog.__init__(self)

        # Load UI from designer
        ui_util.load_ui(self, self.ui_path)

        # Init UI
        ui_util.init_ui(self)

        # get translations
        app = get_app()
        _ = app._tr

        # Get settings
        self.s = settings.get_settings()

        # Pause playback (to prevent crash since we are fixing to change the timeline's max size)
        get_app().window.actionPlay_trigger(None, force="pause")

        # Track metrics
        track_metric_screen("profile-screen")

        # Loop through profiles
        self.profile_names = []
        self.profile_paths = {}
        for profile_folder in [info.USER_PROFILES_PATH, info.PROFILES_PATH]:
            for file in os.listdir(profile_folder):
                # Load Profile
                profile_path = os.path.join(profile_folder, file)
                profile = openshot.Profile(profile_path)

                # Add description of Profile to list
                profile_name = "%s (%sx%s)" % (profile.info.description, profile.info.width, profile.info.height)
                self.profile_names.append(profile_name)
                self.profile_paths[profile_name] = profile_path

        # Sort list
        self.profile_names.sort()

        # Loop through sorted profiles
        box_index = 0
        selected_index = 0
        for profile_name in self.profile_names:

            # Add to dropdown
            self.cboProfile.addItem(profile_name, self.profile_paths[profile_name])

            # Set default (if it matches the project)
            if app.project.get(['profile']) in profile_name:
                selected_index = box_index

            # increment item counter
            box_index += 1


        # Connect signal
        self.cboProfile.currentIndexChanged.connect(functools.partial(self.dropdown_index_changed, self.cboProfile))

        # Set current item (from project)
        self.cboProfile.setCurrentIndex(selected_index)

    def dropdown_index_changed(self, widget, index):
        # Get profile path
        value = self.cboProfile.itemData(index)
        log.info(value)

        # Load profile
        profile = openshot.Profile(value)

        # Set labels
        self.lblSize.setText("%sx%s" % (profile.info.width, profile.info.height))
        self.lblFPS.setText("%0.2f" % (profile.info.fps.num / profile.info.fps.den))
        self.lblOther.setText("DAR: %s/%s, SAR: %s/%s, Interlaced: %s" % (profile.info.display_ratio.num, profile.info.display_ratio.den, profile.info.pixel_ratio.num, profile.info.pixel_ratio.den, profile.info.interlaced_frame))

        # Update timeline settings
        get_app().updates.update(["profile"], profile.info.description)
        get_app().updates.update(["width"], profile.info.width)
        get_app().updates.update(["height"], profile.info.height)
        get_app().updates.update(["fps"], {"num" : profile.info.fps.num, "den" : profile.info.fps.den})

        # Force ApplyMapperToClips to apply these changes
        get_app().window.timeline_sync.timeline.ApplyMapperToClips()

        # Update Window Title
        get_app().window.SetWindowTitle(profile.info.description)
