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
from enum import Enum, unique, auto

from classes import info
from classes.app import get_app
from classes.logger import log
from classes.json_data import JsonDataStore


class SettingStore(JsonDataStore):
    """ This class only allows setting pre-existing keys taken from default settings file, and merges user settings
    on load, assumes default OS dir."""

    @unique
    class pathType(Enum):
        RECENT=0 # Return the last used path for the same action
        PROJECT=1 # Return the current project path

    @unique
    class actions(Enum):
        IMPORT=auto()
        EXPORT=auto()
        LOAD=auto()
        SAVE=auto()

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
        if not os.path.exists(info.USER_PATH):
            return True

        # Load or create user settings
        file_path = os.path.join(info.USER_PATH, self.settings_filename)
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
        if os.path.exists(info.USER_PATH):
            file_path = os.path.join(info.USER_PATH, self.settings_filename)
            # try to save data to file, will raise exception on failure
            self.write_to_file(file_path, self._data)

    def pathSettings(self, action: actions):
        """Given an action, return the corresponding setting names"""
        if action == self.actions.IMPORT:
            return {'type':"locationImportType", 'path':"locationImportPath"}
        if action == self.actions.EXPORT:
            return {'type': "locationExportType", 'path': "locationExportPath"}
        if action in [self.actions.SAVE, self.actions.LOAD]:
            return {'type': "locationProjectType", 'path': "locationProjectPath"}
        log.info("Action not recognized")
        log.error("Given action is not valid %s" % action)
        return None

    def setDefaultPath(self, action: pathType, recent_path: str):
        """ Change the path setting corresponding to the given action """
        if not os.path.exists(recent_path):
            return
        if os.path.isfile(recent_path):
            recent_path=os.path.dirname(recent_path)
        try:
            setting = self.pathSettings(action)
            log.debug(f"Setting %s to %s" % (action.value, recent_path))
            self.set(setting["path"], recent_path)
        except:
            log.error(f"Error setting the path of %s" % setting["path"])

    def getDefaultPath(self, action: actions):
        """
        Returns the starting path for file browsing
        - validates paths before returning them
        - Actions: import, export, project open/save-as
        - Types
            RECENT: return the last directory where this action occurred
            PROJECT: return the directory of the current project
        """
        _ = self.app._tr

        default_path = ""
        # If there isn't a current project, use the most recent one
        project_path = self.app.project.current_filepath or ""
        if not project_path and len(self.get("recent_projects")):
            project_path = self.get("recent_projects")[0]
        setting = self.pathSettings(action)

        try:
            recentOrProject = self.get(setting["type"])
        except:
            log.error(f"getting setting %s" % setting["type"])

        if recentOrProject == self.pathType.PROJECT.value:
            log.debug("Using Project Path")
            default_path = project_path
        else:
            try:
                log.debug("Using Recent Path")
                default_path = self.get(setting["path"])
            except:
                log.error("getting setting %s" % setting["path"])

        if os.path.isfile(default_path):
            # Default set to a file, not a dir. Fixing it.
            log.info("Default path is a file. Correcting.")
            default_path = os.path.dirname(default_path)
            self.setDefaultPath(action,default_path)

        if (not default_path) or (not os.path.exists(default_path)):
            log.debug("Default path invalid. Falling back to home directory")
            return os.path.expanduser("~")

        if action == self.actions.SAVE:
            log.info("Adding file name for project path")
            # Only get project name if one is currently active.
            project_name = os.path.basename(self.app.project.current_filepath or "") or "%s.osp" % _("Untitled Project")
            default_path = os.path.join(default_path, project_name)
        return default_path
