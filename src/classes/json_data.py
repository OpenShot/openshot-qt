""" 
 @file
 @brief This file loads and saves settings (as JSON)
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

try:
    import json
except ImportError:
    import simplejson as json

import copy
import os
import re

from classes.logger import log
from classes import info

# Compiled path regex
path_regex = re.compile(r'\"(image|path)\":.*?\"(.*?)\"', re.UNICODE)
path_context = {}


class JsonDataStore:
    """ This class which allows getting/setting of key/value settings, and loading and saving to json files.
    Internal storage of a dictionary. Uses json or simplejson packages to serialize and deserialize from json to dictionary.
    Keys are assumed to be strings, but subclasses which override get/set methods may use different key types.
    The write_to_file and read_from_file methods are key type agnostic."""

    # Create default data storage and default data type for logging messages
    def __init__(self):
        self._data = {}  # Private data store, accessible through the get and set methods
        self.data_type = "json data"

    def get(self, key):
        """ Get copied value of a given key in data store """
        key = key.lower()

        # Determine if the root element is a dictionary or list (i.e. project data or settings data)
        if type(self._data) == list:
            # Settings data, search for matching "setting" attribute (i.e. list)
            # Load user setting's values (for easy merging)
            user_values = {}
            for item in self._data:
                if "setting" in item and "value" in item:
                    user_values[item["setting"].lower()] = item["value"]

            # Settings data
            return copy.deepcopy(user_values.get(key, None))
        else:
            # Project data (i.e dictionary)
            return copy.deepcopy(self._data.get(key, None))

    def set(self, key, value):
        """ Store value in key """
        key = key.lower()

        # Determine if the root element is a dictionary or list (i.e. project data or settings data)
        if type(self._data) == list:
            # Settings data, search for matching "setting" attribute (i.e. list)
            # Load user setting's values (for easy merging)
            user_values = {}
            for item in self._data:
                if "setting" in item and "value" in item:
                    user_values[item["setting"].lower()] = item

            # Settings data
            user_values[key]["value"] = value

        else:
            # Project data (i.e dictionary)
            self._data[key] = value

    def merge_settings(self, default, user):
        """ Merge settings files, removing invalid settings based on default settings
            This is only called by some sub-classes that use string keys """

        # Determine if the root element is a dictionary or list (i.e. project data or settings data)
        if type(default) == list:

            # Load user setting's values (for easy merging)
            user_values = {}
            for item in user:
                if "setting" in item and "value" in item:
                    user_values[item["setting"]] = item["value"]

            # Update default values to match user values
            for item in default:
                user_value = user_values.get(item["setting"], None)
                if user_value != None:
                    item["value"] = user_value

            # Return merged list
            return default

        else:
            # Root object is a dictionary (i.e. project data)
            for key in default:
                if key not in user:
                    # Add missing key to user dictionary
                    user[key] = default[key]

            # Return merged dictionary
            return user

    def read_from_file(self, file_path, path_mode="ignore"):
        """ Load JSON settings from a file """
        try:
            with open(file_path, 'r') as f:
                contents = f.read()
                if contents:
                    if path_mode == "absolute":
                        # Convert any paths to absolute
                        contents = self.convert_paths_to_absolute(file_path, contents)
                    return json.loads(contents, strict=False)
        except Exception as ex:
            msg = ("Couldn't load {} file: {}".format(self.data_type, ex))
            log.error(msg)
            raise Exception(msg)
        msg = ("Couldn't load {} file, no data.".format(self.data_type))
        log.warning(msg)
        raise Exception(msg)

    def write_to_file(self, file_path, data, path_mode="ignore", previous_path=None):
        """ Save JSON settings to a file """
        try:
            contents = json.dumps(data, indent=4)
            if path_mode == "relative":
                # Convert any paths to relative
                contents = self.convert_paths_to_relative(file_path, previous_path, contents)
            with open(file_path, 'w') as f:
                f.write(contents)
        except Exception as ex:
            msg = ("Couldn't save {} file:\n{}\n{}".format(self.data_type, file_path, ex))
            log.error(msg)
            raise Exception(msg)

    def replace_string_to_absolute(self, match):
        """Replace matched string for converting paths to relative paths"""
        key = match.groups(0)[0]
        path = match.groups(0)[1]

        # Find absolute path of file (if needed)
        utf_path = json.loads('"%s"' % path, encoding="utf-8")  # parse bytestring into unicode string
        if "@transitions" not in utf_path:
            # Convert path to the correct relative path (based on the existing folder)
            new_path = os.path.abspath(os.path.join(path_context.get("existing_project_folder", ""), utf_path))
            new_path = json.dumps(new_path)  # Escape backslashes
            return '"%s": %s' % (key, new_path)

        # Determine if @transitions path is found
        else:
            new_path = path.replace("@transitions", os.path.join(info.PATH, "transitions"))
            new_path = json.dumps(new_path)  # Escape backslashes
            return '"%s": %s' % (key, new_path)

    def convert_paths_to_absolute(self, file_path, data):
        """ Convert all paths to absolute using regex """
        try:
            # Get project folder
            path_context["new_project_folder"] = os.path.dirname(file_path)
            path_context["existing_project_folder"] = os.path.dirname(file_path)

            # Optimized regex replacement
            data = re.sub(path_regex, self.replace_string_to_absolute, data)

        except Exception as ex:
            log.error("Error while converting relative paths to absolute paths: %s" % str(ex))

        return data

    def replace_string_to_relative(self, match):
        """Replace matched string for converting paths to relative paths"""
        key = match.groups(0)[0]
        path = match.groups(0)[1]
        utf_path = json.loads('"%s"' % path, encoding="utf-8")  # parse bytestring into unicode string
        folder_path, file_path = os.path.split(os.path.abspath(utf_path))

        # Determine if thumbnail path is found
        if info.THUMBNAIL_PATH in folder_path:
            # Convert path to relative thumbnail path
            new_path = os.path.join("thumbnail", file_path).replace("\\", "/")
            new_path = json.dumps(new_path)  # Escape backslashes
            return '"%s": %s' % (key, new_path)

        # Determine if @transitions path is found
        elif os.path.join(info.PATH, "transitions") in folder_path:
            # Yes, this is an OpenShot transitions
            folder_path, category_path = os.path.split(folder_path)

            # Convert path to @transitions/ path
            new_path = os.path.join("@transitions", category_path, file_path).replace("\\", "/")
            new_path = json.dumps(new_path)  # Escape backslashes
            return '"%s": %s' % (key, new_path)

        # Find absolute path of file (if needed)
        else:
            # Convert path to the correct relative path (based on the existing folder)
            orig_abs_path = os.path.abspath(utf_path)

            # Remove file from abs path
            orig_abs_folder = os.path.split(orig_abs_path)[0]

            # Calculate new relateive path
            new_rel_path_folder = os.path.relpath(orig_abs_folder, path_context.get("new_project_folder", ""))
            new_rel_path = os.path.join(new_rel_path_folder, file_path).replace("\\", "/")
            new_rel_path = json.dumps(new_rel_path)  # Escape backslashes
            return '"%s": %s' % (key, new_rel_path)

    def convert_paths_to_relative(self, file_path, previous_path, data):
        """ Convert all paths relative to this filepath """
        try:
            # Get project folder
            path_context["new_project_folder"] = os.path.dirname(file_path)
            path_context["existing_project_folder"] = os.path.dirname(file_path)
            if previous_path:
                path_context["existing_project_folder"] = os.path.dirname(previous_path)

            # Optimized regex replacement
            data = re.sub(path_regex, self.replace_string_to_relative, data)

        except Exception as ex:
            log.error("Error while converting absolute paths to relative paths: %s" % str(ex))

        return data
