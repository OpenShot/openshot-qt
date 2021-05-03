"""
 @file
 @brief This file loads and saves settings
 @author Noah Figg <eggmunkee@hotmail.com>
 @author Jonathan Thomas <jonathan@openshot.org>
 @author Olivier Girard <eolinwen@gmail.com>

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

# SettingStore - class which allows getting/storing of settings, loading and saving to json
import os

from classes import info
from classes.logger import log
from classes.json_data import JsonDataStore


def get_settings():
    """ Get the current application's settings instance """
    return SettingStore.get_app().settings


class SettingStore(JsonDataStore):
    """ This class only allows setting pre-existing keys taken from default settings file, and merges user settings
    on load, assumes default OS dir."""

    @classmethod
    def save_app(cls, app_reference):
        cls._app = app_reference

    @classmethod
    def get_app(cls):
        if hasattr(cls, "_app"):
            return cls._app
        return None

    def __init__(self, parent=None):
        super().__init__()
        # Also keep track of our parent, if defined
        if parent:
            SettingStore.save_app(parent)
        # Set the data type name for logging clarity (base class functions use this variable)
        self.data_type = "user settings"
        self.settings_filename = "openshot.settings"
        self.default_settings_filename = os.path.join(info.PATH, 'settings', '_default.settings')

    def get_all_settings(self):
        """ Get the entire list of settings (with all metadata) """
        return self._data

    def set(self, key, value):
        """ Store setting, but adding isn't allowed. All possible settings must be in default settings file. """
        key = key.lower()

        # Load user setting's values (for easy merging)
        user_values = {}
        for item in self._data:
            if "setting" in item and "value" in item:
                user_values[item["setting"].lower()] = item

        # Save setting
        if key in user_values:
            user_values[key]["value"] = value
        else:
            log.warn(
                "{} key '{}' not valid. The following are valid: {}".format(
                self.data_type, key,
                list(self._data.keys()),
                ))

    def load(self):
        """ Load user settings file from disk, merging with allowed settings in default settings file.
        Creates user settings if missing. """

        # Default and user settings objects
        default_settings, user_settings = {}, {}

        # try to load default settings, on failure will raise exception to caller
        default_settings = self.read_from_file(self.default_settings_filename)

        # Try to find user settings file
        file_path = os.path.join(info.USER_PATH, self.settings_filename)

        # Load user settings (if found)
        if os.path.exists(os.fsencode(file_path)):
            # Will raise exception to caller on failure to read
            try:
                user_settings = self.read_from_file(file_path)
            except Exception as ex:
                log.error("Error loading settings file: %s", ex)
                user_settings = {}
                app = SettingStore.get_app()
                if app:
                    # We have a parent, ask to show a message box
                    app.settings_load_error(file_path)

        # Merge default and user settings, excluding settings not in default, Save settings
        self._data = self.merge_settings(default_settings, user_settings)

        # Return success of saving user settings file back after merge
        return self.write_to_file(file_path, self._data)

    def save(self):
        """ Save user settings file to disk """

        # Try to find user settings file
        file_path = os.path.join(info.USER_PATH, self.settings_filename)

        # try to save data to file, will raise exception on failure
        self.write_to_file(file_path, self._data)
