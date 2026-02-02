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

import json

import copy
import os
import re

from classes.assets import get_assets_path
from classes.logger import log
from classes import info
from classes.app import get_app

# Compiled path regex
path_regex = re.compile(r'"(image|path|protobuf_data_path|lut_path)"\s*:\s*"(.*?)"')
path_context = {}

# Determine regex pattern type (compatible with older Python versions)
try:
    _REGEX_TYPE = re.Pattern
except AttributeError:
    _REGEX_TYPE = type(re.compile(""))


class JsonDataStore:
    """ This class which allows getting/setting of key/value settings, and loading and saving to json files.
    Internal storage of a dictionary. Uses json module to serialize and deserialize from json to dictionary.
    Keys are assumed to be strings, but subclasses which override get/set methods may use different key types.
    The write_to_file and read_from_file methods are key type agnostic."""

    # Create default data storage and default data type for logging messages
    def __init__(self):
        self._data = {}  # Private data store, accessible through the get and set methods
        self.data_type = "json data"

        # Regular expressions for file version detection of possible corruption
        self.version_re_250 = re.compile(r'"openshot-qt".*"2.5.0')
        self.version_re_260 = re.compile(r'"openshot-qt".*"2.6.0')

        # Regular expression matching likely corruption in project files
        self.damage_re = re.compile(r'/u([0-9a-fA-F]{4})')

        # Regular expression matching likely windows drive letter corruption in project files
        self.damage_re_windows_drives = re.compile(r'(\n\s*)(\w*):')

        # Regular expression used to detect lost slashes, when repairing data
        self.slash_repair_re = re.compile(r'(["/][.]+)(/u[0-9a-fA-F]{4})')

    def __deepcopy__(self, memo):
        """Custom deepcopy to handle regex objects on older Python versions."""
        cls = self.__class__
        result = cls.__new__(cls)
        memo[id(self)] = result
        for key, value in self.__dict__.items():
            if isinstance(value, _REGEX_TYPE):
                setattr(result, key, value)
            else:
                setattr(result, key, copy.deepcopy(value, memo))
        return result

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
            return json.loads(json.dumps(user_values.get(key, None)))
        else:
            # Project data (i.e dictionary)
            return json.loads(json.dumps(self._data.get(key, None)))

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
                if user_value is not None:
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
            with open(file_path, 'r', encoding='utf-8') as f:
                contents = f.read()
            if not contents:
                raise RuntimeError("Couldn't load {} file, no data.".format(self.data_type))

            # Scan for and correct possible OpenShot 2.6.0 corruption
            if self.damage_re_windows_drives.search(contents) and self.version_re_260.search(contents):
                # File contains corruptions, backup and repair
                self.make_repair_backup(file_path, contents)

                # Repair lost quotes
                contents = self.damage_re_windows_drives.sub(r'\1"\2":', contents)

                # We have to de- and re-serialize the data, to complete repairs
                temp_data = json.loads(contents)
                contents = json.dumps(temp_data, ensure_ascii=False, indent=1)

                # Save the repaired data back to the original file
                with open(file_path, "w", encoding="utf-8") as fout:
                    fout.write(contents)

                msg_log = "Repaired windows drive corruptions in file {}"
                log.info(msg_log.format(file_path))

            # Scan for and correct possible OpenShot 2.5.0 corruption
            if self.damage_re.search(contents) and self.version_re_250.search(contents):
                # File contains corruptions, backup and repair
                self.make_repair_backup(file_path, contents)

                # Repair lost slashes, then fix all corrupted escapes
                contents = self.slash_repair_re.sub(r'\1/\2', contents)
                contents, subs_count = self.damage_re.subn(r'\\u\1', contents)

                if subs_count < 1:
                    # Nothing to do!
                    log.info("No recovery substitutions on {}".format(file_path))
                else:
                    # We have to de- and re-serialize the data, to complete repairs
                    temp_data = json.loads(contents)
                    contents = json.dumps(temp_data, ensure_ascii=False, indent=1)

                    # Save the repaired data back to the original file
                    with open(file_path, "w", encoding="utf-8") as fout:
                        fout.write(contents)

                    msg_log = "Repaired {} corruptions in file {}"
                    log.info(msg_log.format(subs_count, file_path))

            # Process JSON data
            if path_mode == "absolute":
                # Convert any paths to absolute
                contents = self.convert_paths_to_absolute(file_path, contents)
            return json.loads(contents)
        except RuntimeError as ex:
            log.error(str(ex))
            raise
        except Exception as ex:
            msg = "Couldn't load {} file".format(self.data_type)
            log.error(msg, exc_info=1)
            raise Exception(msg) from ex
        raise Exception("Unknown error (should be unreachable)")

    def write_to_file(self, file_path, data, path_mode="ignore", previous_path=None):
        """ Save JSON settings to a file """
        try:
            contents = json.dumps(data, ensure_ascii=False, indent=1)
            if path_mode == "relative":
                # Convert any paths to relative
                contents = self.convert_paths_to_relative(file_path, previous_path, contents)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(contents)
        except Exception as ex:
            msg = "Couldn't save {} file:\n{}\n{}".format(self.data_type, file_path, ex)
            log.error(msg)
            raise ex

    def replace_string_to_absolute(self, match):
        """Replace matched string for converting paths to relative paths"""
        key = match.groups(0)[0]
        path = match.groups(0)[1]

        # Convert escaped path back into python str.
        # Some characters, such as backslashes and quotes
        # are escaped during the JSON dumps() conversion.
        #   /Videos/quote \\"/  instead of  /Videos/quote "/
        path = json.loads('"%s"' % path)

        # Find absolute path of file (if needed)
        if "@transitions" in path:
            new_path = path.replace("@transitions", os.path.join(info.PATH, "transitions"))
            new_path = json.dumps(new_path, ensure_ascii=False)
            return '"%s": %s' % (key, new_path)

        elif "@colors" in path:
            new_path = path.replace("@colors", os.path.join(info.COLORS_PATH))
            new_path = json.dumps(new_path, ensure_ascii=False)
            return '"%s": %s' % (key, new_path)

        elif "@emojis" in path:
            new_path = path.replace("@emojis", os.path.join(info.PATH, "emojis", "color", "svg"))
            new_path = json.dumps(new_path, ensure_ascii=False)
            return '"%s": %s' % (key, new_path)

        elif "@assets" in path:
            new_path = path.replace("@assets", path_context["new_project_assets"])
            new_path = json.dumps(new_path, ensure_ascii=False)
            return '"%s": %s' % (key, new_path)

        else:
            # Convert path to the correct relative path
            new_path = os.path.abspath(os.path.join(path_context.get("new_project_folder", ""), path))
            new_path = json.dumps(new_path, ensure_ascii=False)
            return '"%s": %s' % (key, new_path)

    def convert_paths_to_absolute(self, file_path, data):
        """ Convert all paths to absolute using regex """
        try:
            # Get project folder
            path_context["new_project_folder"] = os.path.dirname(file_path)
            path_context["existing_project_folder"] = os.path.dirname(file_path)
            path_context["new_project_assets"] = get_assets_path(file_path, create_paths=False)
            path_context["existing_project_assets"] = get_assets_path(file_path, create_paths=False)

            # Optimized regex replacement
            data = re.sub(path_regex, self.replace_string_to_absolute, data)

        except Exception:
            log.error("Error while converting relative paths to absolute paths", exc_info=1)

        return data

    def replace_string_to_relative(self, match):
        """Replace matched string for converting paths to relative paths"""
        key = match.groups(0)[0]
        path = match.groups(0)[1]

        # Convert escaped path back into python str.
        # Some characters, such as backslashes and quotes
        # are escaped during the JSON dumps() conversion.
        #   /Videos/quote \\"/  instead of  /Videos/quote "/
        path = json.loads('"%s"' % path)

        # Split path into folder and file
        folder_path, file_path = os.path.split(os.path.abspath(path))

        # Determine if thumbnail path is found
        if info.THUMBNAIL_PATH in folder_path:
            log.debug("Generating relative thumbnail path to %s in %s",
                      file_path, folder_path)
            new_path = os.path.join("thumbnail", file_path).replace("\\", "/")
            new_path = json.dumps(new_path, ensure_ascii=False)
            return '"%s": %s' % (key, new_path)

        # Determine if @transitions path is found
        elif os.path.join(info.PATH, "transitions") in folder_path:
            log.debug("Generating relative @transitions path for %s in %s",
                      file_path, folder_path)
            folder_path, category_path = os.path.split(folder_path)

            # Convert path to @transitions/ path
            new_path = os.path.join("@transitions", category_path, file_path).replace("\\", "/")
            new_path = json.dumps(new_path, ensure_ascii=False)
            return '"%s": %s' % (key, new_path)

        # Determine if @colors path is found
        elif info.COLORS_PATH in folder_path:
            rel = os.path.relpath(os.path.join(folder_path, file_path), info.COLORS_PATH)
            path = json.dumps(f"@colors/{rel.replace(os.sep, '/')}", ensure_ascii=False)
            return f'"{key}": {path}'

        # Determine if @emojis path is found
        elif os.path.join(info.PATH, "emojis") in folder_path:
            log.debug("Generating relative @emojis path for %s in %s",
                      file_path, folder_path)
            new_path = os.path.join("@emojis", file_path).replace("\\", "/")
            new_path = json.dumps(new_path, ensure_ascii=False)
            return '"%s": %s' % (key, new_path)

        # Determine if @assets path is found
        elif path_context["new_project_assets"] in folder_path:
            log.debug("Replacing path to %s in %s", file_path, folder_path)
            folder_path = folder_path.replace(path_context["new_project_assets"], "@assets")

            # Convert path to @assets/ path
            new_path = os.path.join(folder_path, file_path).replace("\\", "/")
            new_path = json.dumps(new_path, ensure_ascii=False)
            return '"%s": %s' % (key, new_path)

        # Find absolute path of file (if needed)
        else:
            # Convert path to the correct relative path (based on the existing folder)
            orig_abs_path = os.path.abspath(path)

            # Determine windows drives that the project and file are on
            project_win_drive = os.path.splitdrive(path_context.get("new_project_folder", ""))[0]
            file_win_drive = os.path.splitdrive(path)[0]
            if file_win_drive != project_win_drive:
                log.debug("Drive mismatch, not making path relative: %s", orig_abs_path)
                # If the file is on different drive. Don't abbreviate the path.
                clean_path = orig_abs_path.replace("\\", "/")
                clean_path = json.dumps(clean_path, ensure_ascii=False)
                return f"\"{key}\": {clean_path}"

            # Remove file from abs path
            orig_abs_folder = os.path.dirname(orig_abs_path)

            log.debug("Generating new relative path for %s", orig_abs_path)
            new_rel_path_folder = os.path.relpath(orig_abs_folder, path_context.get("new_project_folder", ""))
            new_rel_path = os.path.join(new_rel_path_folder, file_path).replace("\\", "/")
            new_rel_path = json.dumps(new_rel_path, ensure_ascii=False)
            return '"%s": %s' % (key, new_rel_path)

    def convert_paths_to_relative(self, file_path, previous_path, data):
        """ Convert all paths relative to this filepath """
        try:
            # Get project folder
            path_context["new_project_folder"] = os.path.dirname(file_path)
            path_context["new_project_assets"] = get_assets_path(file_path, create_paths=False)
            path_context["existing_project_folder"] = os.path.dirname(file_path)
            path_context["existing_project_assets"] = get_assets_path(file_path, create_paths=False)
            if previous_path and file_path != previous_path:
                path_context["existing_project_folder"] = os.path.dirname(previous_path)
                path_context["existing_project_assets"] = get_assets_path(previous_path, create_paths=False)

            # Optimized regex replacement
            data = re.sub(path_regex, self.replace_string_to_relative, data)

        except Exception:
            log.error("Error while converting absolute paths to relative paths", exc_info=1)

        return data

    def make_repair_backup(self, file_path, jsondata, backup_dir=None):
        """ Make a backup copy of an OSP file before performing recovery """
        app = get_app()
        _ = app._tr

        if backup_dir:
            backup_base = os.path.join(backup_dir, os.path.basename(file_path))
        else:
            backup_base = os.path.realpath(file_path)

        # Generate a filename.zvn.bak (or filename.zvn.bak.1...) backup file name
        backup_file = "{}.bak".format(backup_base)
        dup_count = 1
        while os.path.exists(backup_file) and dup_count <= 999:
            backup_file = "{}.bak.{}".format(backup_base, dup_count)
            dup_count += 1

        if dup_count >= 1000:
            # Something's wrong, we can't find a free save file name; bail
            raise Exception("Aborting recovery, cannot create backup file")

        # Attempt to open backup file for writing and store original data
        try:
            with open(backup_file, "w") as fout:
                fout.write(jsondata)

            if hasattr(app, "window") and hasattr(app.window, "statusBar"):
                app.window.statusBar.showMessage(_("Saved backup file {}").format(backup_file), 5000)
            log.info("Backed up {} as {}".format(file_path, backup_file))
        except (PermissionError, FileExistsError) as ex:
            # Couldn't write to backup file! Try alternate location
            log.error("Couldn't write to backup file {}: {}".format(backup_file, ex))
            if not backup_dir:
                # Retry in alternate location
                log.info("Attempting to save backup in user config directory")
                self.make_repair_backup(file_path, jsondata, backup_dir=info.USER_PATH)
            else:
                raise Exception("Aborting recovery, cannot write backup file") from ex
