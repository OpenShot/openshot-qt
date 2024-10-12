"""
 @file
 @brief This file loads the Choose Profile dialog
 @author Jonathan Thomas <jonathan@openshot.org>

 @section LICENSE

 Copyright (c) 2008-2023 OpenShot Studios, LLC
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
from PyQt5.QtWidgets import QDialog, QSizePolicy, QDialogButtonBox

from classes import info, ui_util
from classes.app import get_app
from classes.logger import log
from classes.metrics import track_metric_screen
from windows.views.profiles_treeview import ProfilesTreeView


class Profile(QDialog):
    """ Choose Profile Dialog """

    # Path to ui file
    ui_path = os.path.join(info.PATH, 'windows', 'ui', 'profile.ui')

    def __init__(self, initial_profile_desc=None):

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

        # Set up the buttons
        self.buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.okButton = self.buttonBox.button(QDialogButtonBox.Ok)
        self.cancelButton = self.buttonBox.button(QDialogButtonBox.Cancel)

        # Set object names (for theme styles)
        self.okButton.setObjectName("acceptButton")
        self.cancelButton.setObjectName("cancelButton")
        self.layout().addWidget(self.buttonBox)

        # Connect the buttons
        self.okButton.clicked.connect(self.accept)
        self.cancelButton.clicked.connect(self.reject)

        # Loop through profiles
        self.profile_list = []
        self.project_profile = None
        self.selected_profile = None
        self.project_index = 0
        for profile_folder in [info.USER_PROFILES_PATH, info.PROFILES_PATH]:
            for file in reversed(sorted(os.listdir(profile_folder))):
                profile_path = os.path.join(profile_folder, file)
                if os.path.isdir(profile_path):
                    continue
                try:
                    # Load Profile
                    profile = openshot.Profile(profile_path)
                    if profile_folder == info.USER_PROFILES_PATH:
                        profile.path = profile_path
                        profile.user_created = True
                    else:
                        profile.user_created = False
                    if profile.info.description == initial_profile_desc or profile.Key() == initial_profile_desc:
                        self.project_profile = profile
                        self.project_index = len(self.profile_list)
                        self.setWindowTitle(f'{_("Choose Profile")} [{profile.info.description}]')

                    # Add description of Profile to list
                    self.profile_list.append(profile)

                except RuntimeError as e:
                    log.warning("Failed to parse file '%s' as a profile: %s" % (profile_path, e))

        # Create treeview
        self.profileListView = ProfilesTreeView(self, self.profile_list)
        self.profileListView.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.verticalLayout.insertWidget(1, self.profileListView)

        # Select project profile (if any)
        if self.project_profile:
            model_index = self.profileListView.profiles_model.proxy_model.index(self.project_index, 1)
            self.profileListView.select_profile(model_index)

        # Connect signals
        self.txtProfileFilter.textChanged.connect(self.profileListView.refresh_view)
        self.txtProfileFilter.textChanged.connect(self.profileListView.refresh_view)
        self.profileListView.FilterCountChanged.connect(self.profileCountChanged)
        self.profileListView.doubleClicked.connect(self.profileDoubleClick)

    def profileCountChanged(self, new_count):
        """Profile filter count changed"""
        self.lblCount.setText(f"{new_count}")

    def profileDoubleClick(self):
        """Profile tree was double clicked"""
        self.accept()

    def accept(self):
        """ Ok button clicked """
        # Get selected profile
        profile = self.profileListView.get_profile()
        if profile:
            # New profile selected
            self.selected_profile = profile
            super(Profile, self).accept()
        else:
            # No profile or same as current project
            self.reject()

    def closeEvent(self, event):
        """Signal for closing Profile window"""
        # Invoke the close button
        self.reject()

    def reject(self):
        """Window closed without choosing a new profile"""
        # Close dialog
        super(Profile, self).reject()
