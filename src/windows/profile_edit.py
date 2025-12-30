"""
 @file
 @brief This file loads the profile editor (duplicate and edit profiles)
 @author Jonathan Thomas <jonathan@openshot.org>

 @section LICENSE

 Copyright (c) 2008-2024 OpenShot Studios, LLC
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

import openshot
from PyQt5.QtWidgets import QDialog, QMessageBox
from classes import ui_util, info
from classes.app import get_app
from classes.logger import log


class EditProfileDialog(QDialog):
    """ Edit Profile Dialog """

    # Path to ui file
    ui_path = os.path.join(info.PATH, 'windows', 'ui', 'profile-edit.ui')

    def __init__(self, profile, duplicate):
        super(EditProfileDialog, self).__init__()

        # Make copy of profile
        self.original_profile = profile.Json()
        self.profile = profile
        self.duplicate = duplicate
        if duplicate:
            # Clear reference to original profile
            self.profile = openshot.Profile()
            self.profile.SetJson(self.original_profile)

        # Save initial file path (if editing, this needs to be removed)
        self.existing_path = None
        if hasattr(profile, "path"):
            self.existing_path = profile.path

        # Load UI from designer & init
        ui_util.load_ui(self, self.ui_path)
        ui_util.init_ui(self)

        # Populate fields from profile
        self.initialize()

    def initialize(self):
        """Initialize the form fields with data from the profile."""
        # get translations
        _ = get_app()._tr

        # Update windows title
        if self.duplicate:
            self.setWindowTitle(_('Create Profile'))
        else:
            self.setWindowTitle(_('Edit Profile'))

        # Add options to cboInterlaced dropdown
        self.cboInterlaced.addItem(_('Yes'))
        self.cboInterlaced.addItem(_('No'))

        # Add options to cboSpherical dropdown
        self.cboSpherical.addItem(_('Yes'))
        self.cboSpherical.addItem(_('No'))

        self.txtProfileName.setText(self.profile.info.description)
        self.txtWidth.setValue(self.profile.info.width)
        self.txtHeight.setValue(self.profile.info.height)
        self.txtAspectRatioNum.setValue(self.profile.info.display_ratio.num)
        self.txtAspectRatioDen.setValue(self.profile.info.display_ratio.den)
        self.txtPixelRatioNum.setValue(self.profile.info.pixel_ratio.num)
        self.txtPixelRatioDen.setValue(self.profile.info.pixel_ratio.den)
        self.txtFrameRateNum.setValue(self.profile.info.fps.num)
        self.txtFrameRateDen.setValue(self.profile.info.fps.den)
        self.cboInterlaced.setCurrentText(_('Yes') if self.profile.info.interlaced_frame == 1 else _('No'))
        self.cboSpherical.setCurrentText(_('Yes') if self.profile.info.spherical else _('No'))

        # Connect all signals
        self.connect_signals()

    def connect_signals(self):
        """Connect input fields to update profile on change."""
        self.txtProfileName.textChanged.connect(self.update_profile_description)
        self.txtWidth.valueChanged.connect(self.update_profile_width)
        self.txtHeight.valueChanged.connect(self.update_profile_height)
        self.txtPixelRatioNum.valueChanged.connect(self.update_profile_pixel_ratio)
        self.txtPixelRatioDen.valueChanged.connect(self.update_profile_pixel_ratio)
        self.txtFrameRateNum.valueChanged.connect(self.update_profile_frame_rate_num)
        self.txtFrameRateDen.valueChanged.connect(self.update_profile_frame_rate_den)
        self.cboInterlaced.currentTextChanged.connect(self.update_profile_interlaced)
        self.cboSpherical.currentTextChanged.connect(self.update_profile_spherical)
        self.txtProfileName.setFocus()

    # Handlers for updating profile
    def update_profile_description(self, value):
        self.profile.info.description = value
        self.update_profile_path()

    def update_profile_width(self, value):
        self.profile.info.width = value
        self.update_display_aspect_ratio()
        self.update_profile_path()

    def update_profile_height(self, value):
        self.profile.info.height = value
        self.update_display_aspect_ratio()
        self.update_profile_path()

    def update_profile_pixel_ratio(self):
        num = self.txtPixelRatioNum.value()
        den = self.txtPixelRatioDen.value()
        self.profile.info.pixel_ratio.num = num
        self.profile.info.pixel_ratio.den = den
        self.update_display_aspect_ratio()
        self.update_profile_path()

    def update_display_aspect_ratio(self):
        """Update display aspect ratio based on width, height, and pixel ratio."""
        width = self.profile.info.width
        height = self.profile.info.height
        pixel_ratio_num = self.profile.info.pixel_ratio.num
        pixel_ratio_den = self.profile.info.pixel_ratio.den

        if height != 0 and pixel_ratio_den != 0:
            self.profile.info.display_ratio.num = width * pixel_ratio_num
            self.profile.info.display_ratio.den = height * pixel_ratio_den
            self.profile.info.display_ratio.Reduce()

        # Update the aspect ratio fields in the UI
        self.txtAspectRatioNum.setValue(self.profile.info.display_ratio.num)
        self.txtAspectRatioDen.setValue(self.profile.info.display_ratio.den)

    def update_profile_frame_rate_num(self, value):
        self.profile.info.fps.num = value
        self.update_profile_path()

    def update_profile_frame_rate_den(self, value):
        self.profile.info.fps.den = value
        self.update_profile_path()

    def update_profile_interlaced(self, value):
        # get translations
        _ = get_app()._tr

        self.profile.info.interlaced_frame = True if value == _('Yes') else False
        self.update_profile_path()

    def update_profile_spherical(self, value):
        # get translations
        _ = get_app()._tr

        self.profile.info.spherical = True if value == _('Yes') else False
        self.update_profile_path()

    def update_profile_path(self):
        if self.existing_path and os.path.exists(self.existing_path) and not self.duplicate:
            profiles_path = self.existing_path
        else:
            profiles_path = os.path.join(info.USER_PROFILES_PATH, self.profile.Key())

        profile_suffix = 1
        while self.duplicate and os.path.exists(profiles_path):
            # Add suffix if 'duplicate' mode - and existing file found
            profiles_path = f"{os.path.join(info.USER_PROFILES_PATH, self.profile.Key())}-{profile_suffix}"
            profile_suffix += 1
        self.lblFilePathValue.setText(profiles_path)

    def accept(self):
        """Save the profile to a file when the user accepts the dialog."""
        # get translations
        _ = get_app()._tr

        # Prevent saving with no description
        error_title = _("Profile Error")
        error_message = _("Please enter a <b>unique</b> description for this profile.")
        if not self.profile.info.description.strip():
            QMessageBox.warning(self, error_title, error_message)
            return

        # Verify description is unique
        for profile_folder in [info.USER_PROFILES_PATH, info.PROFILES_PATH]:
            for file in reversed(sorted(os.listdir(profile_folder))):
                profile_verify_path = os.path.join(profile_folder, file)
                if os.path.isdir(profile_verify_path) or profile_verify_path == self.lblFilePathValue.text():
                    continue
                try:
                    # Load Profile
                    p = openshot.Profile(profile_verify_path)
                    if p.info.description.strip() == self.profile.info.description.strip():
                        QMessageBox.warning(self, error_title, error_message)
                        return
                except RuntimeError as e:
                    log.warning("Failed to parse file '%s' as a profile: %s" % (profile_verify_path, e))

        # Save the profile data as a text file in the user profiles folder
        profile_path = self.lblFilePathValue.text()
        log.info(f"Saving custom profile: {profile_path}")
        self.profile.Save(profile_path)
        self.profile.user_created = True
        self.profile.path = profile_path

        # Accept the dialog
        super(EditProfileDialog, self).accept()

    def reject(self):
        """Close the dialog without saving changes."""
        # restore original profile
        self.profile.SetJson(self.original_profile)

        super(EditProfileDialog, self).reject()
