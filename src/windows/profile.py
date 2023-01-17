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
from PyQt5.QtWidgets import QDialog, QSizePolicy

from classes import info, ui_util
from classes.app import get_app
from classes.logger import log
from classes.metrics import track_metric_screen
from windows.views.profiles_treeview import ProfilesTreeView


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

        # Disable video caching
        openshot.Settings.Instance().ENABLE_PLAYBACK_CACHING = False

        # Keep track of starting selection
        self.initial_index = 0

        # Loop through profiles
        self.profile_list = []
        self.project_profile = None
        self.project_index = 0
        for profile_folder in [info.USER_PROFILES_PATH, info.PROFILES_PATH]:
            for file in reversed(sorted(os.listdir(profile_folder))):
                profile_path = os.path.join(profile_folder, file)
                if os.path.isdir(profile_path):
                    continue
                try:
                    # Load Profile
                    profile = openshot.Profile(profile_path)
                    if profile.info.description == get_app().project.get(['profile']):
                        self.project_profile = profile
                        self.project_index = len(self.profile_list)
                        self.setWindowTitle(f'{_("Choose Profile")} [{profile.info.description}]')

                    # Add description of Profile to list
                    self.profile_list.append(profile)

                except RuntimeError as e:
                    # This exception occurs when there's a problem parsing
                    # the Profile file - display a message and continue
                    log.error("Failed to parse file '%s' as a profile: %s" % (profile_path, e))

        # Create treeview
        self.profileListView = ProfilesTreeView(self.profile_list)
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

    def profileCountChanged(self, new_count):
        """Profile filter count changed"""
        self.lblCount.setText(f"{new_count}")

    def accept(self):
        """ Ok button clicked """
        super(Profile, self).accept()

        # Get selected profile (if any, and if different than current project)
        profile = self.profileListView.get_profile()
        if profile and profile.info.description != get_app().project.get(['profile']):

            win = get_app().window
            proj = get_app().project
            updates = get_app().updates

            # Get current FPS (prior to changing)
            current_fps = proj.get("fps")
            current_fps_float = float(current_fps["num"]) / float(current_fps["den"])
            fps_factor = float(profile.info.fps.ToFloat() / current_fps_float)

            # Get current playback frame
            current_frame = win.preview_thread.current_frame
            adjusted_frame = round(current_frame * fps_factor)

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

            # Seek to the same location, adjusted for new frame rate
            win.SeekSignal.emit(adjusted_frame)

            # Refresh frame (since size of preview might have changed)
            QTimer.singleShot(500, win.refreshFrameSignal.emit)
            QTimer.singleShot(500, functools.partial(win.MaxSizeChanged.emit,
                                                     win.videoPreview.size()))

    def closeEvent(self, event):
        """Signal for closing Profile window"""
        # Invoke the close button
        self.reject()

    def reject(self):
        # Enable video caching
        openshot.Settings.Instance().ENABLE_PLAYBACK_CACHING = True

        # Close dialog
        super(Profile, self).reject()
