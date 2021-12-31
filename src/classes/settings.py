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


class SettingStore(JsonDataStore):
    """ This class only allows setting pre-existing keys taken from default settings file, and merges user settings
    on load, assumes default OS dir."""

    def __init__(self, parent=None):
        super().__init__()
        # Also keep track of our parent, if defined
        self.app = parent
        # Set the data type name for logging clarity (base class functions use this variable)
        self.data_type = "user settings"
        self.settings_filename = "openshot.settings"
        self.defaults_path = os.path.join(info.PATH, 'settings', '_default.settings')

    def get_all_settings(self):
        """ Get the entire list of settings (with all metadata) """
        return self._data

    def set(self, key, value):
        """ Store setting, but adding isn't allowed. All possible settings must be in default settings file. """
        key = key.lower()

        # Index settings values (for easy updates)
        user_values = {
            item["setting"].lower(): item
            for item in self._data
            if all(["setting" in item, "value" in item])
        }

        # Save setting
        if key in user_values:
            user_values[key].update({"value": value})
        else:
            log.warn(
                "{} key '{}' not valid. The following are valid: {}".format(
                    self.data_type,
                    key,
                    list(self._data.keys()),
                ))

    def load(self):
        """ Load user settings file from disk, merging with allowed settings in default settings file.
        Creates user settings if missing. """

        # try to load default settings, on failure will raise exception to caller
        default_settings = self.read_from_file(self.defaults_path)
        self._data = default_settings

        # Try to find user settings dir, give up if it's not there
        if not os.path.exists(info.CONFIG_PATH):
            return True

        # Load or create user settings
        file_path = os.path.join(info.CONFIG_PATH, self.settings_filename)
        if os.path.exists(os.fsencode(file_path)):
            try:
                user_settings = self.read_from_file(file_path)
                # Merge sources, excluding user settings not found in default
                self._data = self.merge_settings(default_settings, user_settings)
            except Exception as ex:
                log.error("Error loading settings file: %s", ex)
                if self.app:
                    # We have a parent, ask to show a message box
                    self.app.settings_load_error(file_path)

        # Return success of saving user settings file back after merge
        return self.write_to_file(file_path, self._data)

    def save(self):
        """ Save user settings file to disk """

        # Try to find user settings file
        if os.path.exists(info.CONFIG_PATH):
            file_path = os.path.join(info.CONFIG_PATH, self.settings_filename)
            # try to save data to file, will raise exception on failure
            self.write_to_file(file_path, self._data)
