""" 
 @file
 @brief This file listens to changes, and updates the primary project data
 @author Noah Figg <eggmunkee@hotmail.com>
 @author Jonathan Thomas <jonathan@openshot.org>
 @author Olivier Girard <eolinwen@gmail.com>
 
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
import random
import copy
import shutil
import glob

from classes.json_data import JsonDataStore
from classes.updates import UpdateInterface
from classes import info, settings
from classes.logger import log


class ProjectDataStore(JsonDataStore, UpdateInterface):
    """ This class allows advanced searching of data structure, implements changes interface """

    def __init__(self):
        JsonDataStore.__init__(self)
        self.data_type = "project data"  # Used in error messages
        self.default_project_filepath = os.path.join(info.PATH, 'settings', '_default.project')

        # Set default filepath to user's home folder
        self.current_filepath = None

        # Track changes after save
        self.has_unsaved_changes = False

        # Load default project data on creation
        self.new()

    def needs_save(self):
        """Returns if project data Has unsaved changes"""
        return self.has_unsaved_changes

    def get(self, key):
        """ Get copied value of a given key in data store """

        # Verify key is valid type
        if not isinstance(key, list):
            log.warning("get() key must be a list. key: {}".format(key))
            return None
        if not key:
            log.warning("Cannot get empty key.")
            return None

        # Get reference to internal data structure
        obj = self._data

        # Iterate through key list finding sub-objects either by name or by an object match criteria such as {"id":"ADB34"}.
        for key_index in range(len(key)):
            key_part = key[key_index]

            # Key_part must be a string or dictionary
            if not isinstance(key_part, dict) and not isinstance(key_part, str):
                log.error("Unexpected key part type: {}".format(type(key_part).__name__))
                return None

            # If key_part is a dictionary and obj is a list or dict, each key is tested as a property of the items in the current object
            # in the project data structure, and the first match is returned.
            if isinstance(key_part, dict) and isinstance(obj, list):
                # Overall status of finding a matching sub-object
                found = False
                # Loop through each item in object to find match
                for item_index in range(len(obj)):
                    item = obj[item_index]
                    # True until something disqualifies this as a match
                    match = True
                    # Check each key in key_part dictionary and if not found to be equal as a property in item, move on to next item in list
                    for subkey in key_part.keys():
                        # Get each key in dictionary (i.e. "id", "layer", etc...)
                        subkey = subkey.lower()
                        # If object is missing the key or the values differ, then it doesn't match.
                        if not (subkey in item and item[subkey] == key_part[subkey]):
                            match = False
                            break
                    # If matched, set key_part to index of list or dict and stop loop
                    if match:
                        found = True
                        obj = item
                        break
                # No match found, return None
                if not found:
                    return None

            # If key_part is a string, homogenize to lower case for comparisons
            if isinstance(key_part, str):
                key_part = key_part.lower()

                # Check current obj type (should be dictionary)
                if not isinstance(obj, dict):
                    log.warn(
                        "Invalid project data structure. Trying to use a key on a non-dictionary object. Key part: {} (\"{}\").\nKey: {}".format(
                            (key_index), key_part, key))
                    return None

                # If next part of path isn't in current dictionary, return failure
                if not key_part in obj:
                    log.warn("Key not found in project. Mismatch on key part {} (\"{}\").\nKey: {}".format((key_index),
                                                                                                           key_part,
                                                                                                           key))
                    return None

                # Get the matching item
                obj = obj[key_part]

        # After processing each key, we've found object, return copy of it
        return copy.deepcopy(obj)

    def set(self, key, value):
        """Prevent calling JsonDataStore set() method. It is not allowed in ProjectDataStore, as changes come from UpdateManager."""
        raise Exception("ProjectDataStore.set() is not allowed. Changes must route through UpdateManager.")

    def _set(self, key, values=None, add=False, partial_update=False, remove=False):
        """ Store setting, but adding isn't allowed. All possible settings must be in default settings file. """

        log.info(
            "_set key: {} values: {} add: {} partial: {} remove: {}".format(key, values, add, partial_update, remove))
        parent, my_key = None, ""

        # Verify key is valid type
        if not isinstance(key, list):
            log.warning("_set() key must be a list. key: {}".format(key))
            return None
        if not key:
            log.warning("Cannot set empty key.")
            return None

        # Get reference to internal data structure
        obj = self._data

        # Iterate through key list finding sub-objects either by name or by an object match criteria such as {"id":"ADB34"}.
        for key_index in range(len(key)):
            key_part = key[key_index]

            # Key_part must be a string or dictionary
            if not isinstance(key_part, dict) and not isinstance(key_part, str):
                log.error("Unexpected key part type: {}".format(type(key_part).__name__))
                return None

            # If key_part is a dictionary and obj is a list or dict, each key is tested as a property of the items in the current object
            # in the project data structure, and the first match is returned.
            if isinstance(key_part, dict) and isinstance(obj, list):
                # Overall status of finding a matching sub-object
                found = False
                # Loop through each item in object to find match
                for item_index in range(len(obj)):
                    item = obj[item_index]
                    # True until something disqualifies this as a match
                    match = True
                    # Check each key in key_part dictionary and if not found to be equal as a property in item, move on to next item in list
                    for subkey in key_part.keys():
                        # Get each key in dictionary (i.e. "id", "layer", etc...)
                        subkey = subkey.lower()
                        # If object is missing the key or the values differ, then it doesn't match.
                        if not (subkey in item and item[subkey] == key_part[subkey]):
                            match = False
                            break
                    # If matched, set key_part to index of list or dict and stop loop
                    if match:
                        found = True
                        obj = item
                        my_key = item_index
                        break
                # No match found, return None
                if not found:
                    return None


            # If key_part is a string, homogenize to lower case for comparisons
            if isinstance(key_part, str):
                key_part = key_part.lower()

                # Check current obj type (should be dictionary)
                if not isinstance(obj, dict):
                    return None

                # If next part of path isn't in current dictionary, return failure
                if not key_part in obj:
                    log.warn("Key not found in project. Mismatch on key part {} (\"{}\").\nKey: {}".format((key_index),
                                                                                                           key_part,
                                                                                                           key))
                    return None

                # Get sub-object based on part key as new object, continue to next part
                obj = obj[key_part]
                my_key = key_part


            # Set parent to the last set obj (if not final iteration)
            if key_index < (len(key) - 1) or key_index == 0:
                parent = obj


        # After processing each key, we've found object and parent, return former value/s on update
        ret = copy.deepcopy(obj)

        # Apply the correct action to the found item
        if remove:
            del parent[my_key]

        else:

            # Add or Full Update
            # For adds to list perform an insert to index or the end if not specified
            if add and isinstance(parent, list):
                # log.info("adding to list")
                parent.append(values)

            # Otherwise, set the given index
            elif isinstance(values, dict):
                # Update existing dictionary value
                obj.update(values)

            else:

                # Update root string
                self._data[my_key] = values

        # Return the previous value to the matching item (used for history tracking)
        return ret

    # Load default project data
    def new(self):
        """ Try to load default project settings file, will raise error on failure """
        import openshot
        self._data = self.read_from_file(self.default_project_filepath)
        self.current_filepath = None
        self.has_unsaved_changes = False

        # Get default profile
        s = settings.get_settings()
        default_profile = s.get("default-profile")

        # Loop through profiles
        for file in os.listdir(info.PROFILES_PATH):
            # Load Profile and append description
            profile_path = os.path.join(info.PROFILES_PATH, file)
            profile = openshot.Profile(profile_path)

            if default_profile == profile.info.description:
                log.info("Setting default profile to %s" % profile.info.description)

                # Update default profile
                self._data["profile"] = profile.info.description
                self._data["width"] = profile.info.width
                self._data["height"] = profile.info.height
                self._data["fps"] = {"num" : profile.info.fps.num, "den" : profile.info.fps.den}

        # Get the default audio settings for the timeline (and preview playback)
        default_sample_rate = int(s.get("default-samplerate"))
        default_channel_ayout = s.get("default-channellayout")

        channels = 2
        channel_layout = openshot.LAYOUT_STEREO
        if default_channel_ayout == "LAYOUT_MONO":
            channels = 1
            channel_layout = openshot.LAYOUT_MONO
        elif default_channel_ayout == "LAYOUT_STEREO":
            channels = 2
            channel_layout = openshot.LAYOUT_STEREO
        elif default_channel_ayout == "LAYOUT_SURROUND":
            channels = 3
            channel_layout = openshot.LAYOUT_SURROUND
        elif default_channel_ayout == "LAYOUT_5POINT1":
            channels = 6
            channel_layout = openshot.LAYOUT_5POINT1
        elif default_channel_ayout == "LAYOUT_7POINT1":
            channels = 8
            channel_layout = openshot.LAYOUT_7POINT1

        # Set default samplerate and channels
        self._data["sample_rate"] = default_sample_rate
        self._data["channels"] = channels
        self._data["channel_layout"] = channel_layout

    def load(self, file_path):
        """ Load project from file """

        self.new()

        if file_path:
            # Default project data
            default_project = self._data

            # Try to load project data, will raise error on failure
            project_data = self.read_from_file(file_path)

            # Merge default and project settings, excluding settings not in default.
            self._data = self.merge_settings(default_project, project_data)

            # On success, save current filepath
            self.current_filepath = file_path

            # Convert all paths back to absolute
            self.convert_paths_to_absolute()

            # Copy any project thumbnails to main THUMBNAILS folder
            loaded_project_folder = os.path.dirname(self.current_filepath)
            project_thumbnails_folder = os.path.join(loaded_project_folder, "thumbnail")
            if os.path.exists(project_thumbnails_folder):
                # Remove thumbnail path
                shutil.rmtree(info.THUMBNAIL_PATH, True)

                # Copy project thumbnails folder
                shutil.copytree(project_thumbnails_folder, info.THUMBNAIL_PATH)

            # Add to recent files setting
            self.add_to_recent_files(file_path)

            # Upgrade any data structures
            self.upgrade_project_data_structures()

        # Get app, and distribute all project data through update manager
        from classes.app import get_app
        get_app().updates.load(self._data)

        # Clear needs save flag
        self.has_unsaved_changes = False

    def upgrade_project_data_structures(self):
        """Fix any issues with old project files (if any)"""
        openshot_version = self._data["version"]["openshot-qt"]
        libopenshot_version = self._data["version"]["libopenshot"]

        log.info(openshot_version)
        log.info(libopenshot_version)

        if openshot_version == "0.0.0":
            # If version = 0.0.0, this is the beta of OpenShot
            # Fix alpha values (they are now flipped)
            for clip in self._data["clips"]:
                # Loop through keyframes for alpha
                for point in clip["alpha"]["Points"]:
                    # Flip the alpha value
                    if "co" in point:
                        point["co"]["Y"] = 1.0 - point["co"]["Y"]
                    if "handle_left" in point:
                        point["handle_left"]["Y"] = 1.0 - point["handle_left"]["Y"]
                    if "handle_right" in point:
                        point["handle_right"]["Y"] = 1.0 - point["handle_right"]["Y"]

    def save(self, file_path, move_temp_files=True, make_paths_relative=True):
        """ Save project file to disk """
        import openshot

        # Move all temp files (i.e. Blender animations) to the project folder
        if move_temp_files:
            self.move_temp_paths_to_project_folder(file_path)

        # Convert all file paths to relative based on this new project file's directory
        if make_paths_relative:
            self.convert_paths_to_relative(file_path)

        # Append version info
        v = openshot.GetVersion()
        self._data["version"] = { "openshot-qt" : info.VERSION,
                                  "libopenshot" : v.ToString() }

        # Try to save project settings file, will raise error on failure
        self.write_to_file(file_path, self._data)

        # On success, save current filepath
        self.current_filepath = file_path

        # Convert all paths back to absolute
        if make_paths_relative:
            self.convert_paths_to_absolute()

        # Add to recent files setting
        self.add_to_recent_files(file_path)

        # Track unsaved changes
        self.has_unsaved_changes = False

    def move_temp_paths_to_project_folder(self, file_path):
        """ Move all temp files (such as Thumbnails, Titles, and Blender animations) to the project folder. """
        try:
            # Get project folder
            new_project_folder = os.path.dirname(file_path)
            new_thumbnails_folder = os.path.join(new_project_folder, "thumbnail")

            # Create project thumbnails folder
            if not os.path.exists(new_thumbnails_folder):
                os.mkdir(new_thumbnails_folder)

            # Copy all thumbnails to project
            for filename in glob.glob(os.path.join(info.THUMBNAIL_PATH, '*.*')):
                shutil.copy(filename, new_thumbnails_folder)

            # Loop through each file
            for file in self._data["files"]:
                path = file["path"]

                # Find any temp BLENDER file paths
                if info.BLENDER_PATH in path:
                    log.info("Temp blender file path detected in file")

                    # Get folder of file
                    folder_path, file_name = os.path.split(path)
                    parent_path, folder_name = os.path.split(folder_path)
                    # Update path to new folder
                    path = os.path.join(new_project_folder, folder_name)
                    # Copy temp folder to project folder
                    shutil.copytree(folder_path, path)

                    # Update paths in project to new location
                    file["path"] = os.path.join(path, file_name)

            # Loop through each clip
            for clip in self._data["clips"]:
                path = clip["reader"]["path"]

                # Find any temp BLENDER file paths
                if info.BLENDER_PATH in path:
                    log.info("Temp blender file path detected in clip")

                    # Get folder of file
                    folder_path, file_name = os.path.split(path)
                    parent_path, folder_name = os.path.split(folder_path)
                    # Update path to new folder
                    path = os.path.join(new_project_folder, folder_name)

                    # Update paths in project to new location
                    clip["reader"]["path"] = os.path.join(path, file_name)

            # Loop through each file
            for clip in self._data["clips"]:
                path = clip["image"]

                # Find any temp BLENDER file paths
                if info.BLENDER_PATH in path:
                    log.info("Temp blender file path detected in clip thumbnail")

                    # Get folder of file
                    folder_path, file_name = os.path.split(path)
                    parent_path, folder_name = os.path.split(folder_path)
                    # Update path to new folder
                    path = os.path.join(new_project_folder, folder_name)

                    # Update paths in project to new location
                    clip["image"] = os.path.join(path, file_name)

        except Exception as ex:
            log.error("Error while moving temp files into project folder: %s" % str(ex))

    def add_to_recent_files(self, file_path):
        """ Add this project to the recent files list """

        s = settings.get_settings()
        recent_projects = s.get("recent_projects")

        # Remove existing project
        if file_path in recent_projects:
            recent_projects.remove(file_path)

        # Remove oldest item (if needed)
        if len(recent_projects) > 10:
            del recent_projects[0]

        # Append file path to end of recent files
        recent_projects.append(file_path)

        # Save setting
        s.set("recent_projects", recent_projects)

    def convert_paths_to_relative(self, file_path):
        """ Convert all paths relative to this filepath """
        try:
            # Get project folder
            existing_project_folder = None
            if self.current_filepath:
                existing_project_folder = os.path.dirname(self.current_filepath)
            new_project_folder = os.path.dirname(file_path)

            # Loop through each file
            for file in self._data["files"]:
                path = file["path"]
                # Find absolute path of file (if needed)
                if not os.path.isabs(path):
                    # Convert path to the correct relative path (based on the existing folder)
                    path = os.path.abspath(os.path.join(existing_project_folder, path))

                # Convert absolute path to relavite
                file["path"] = os.path.relpath(path, new_project_folder)

            # Loop through each clip
            for clip in self._data["clips"]:
                # Update reader path
                path = clip["reader"]["path"]
                # Find absolute path of file (if needed)
                if not os.path.isabs(path):
                    # Convert path to the correct relative path (based on the existing folder)
                    path = os.path.abspath(os.path.join(existing_project_folder, path))
                # Convert absolute path to relavite
                clip["reader"]["path"] = os.path.relpath(path, new_project_folder)

                # Update clip image path
                path = clip["image"]
                # Find absolute path of file (if needed)
                if not os.path.isabs(path):
                    # Convert path to the correct relative path (based on the existing folder)
                    path = os.path.abspath(os.path.join(existing_project_folder, path))
                # Convert absolute path to relavite
                clip["image"] = os.path.relpath(path, new_project_folder)

            # Loop through each transition
            for effect in self._data["effects"]:
                # Update reader path
                path = effect["reader"]["path"]

                # Determine if this path is the official transition path
                folder_path, file_path = os.path.split(path)
                if os.path.join(info.PATH, "transitions") in folder_path:
                    # Yes, this is an OpenShot transitions
                    folder_path, category_path = os.path.split(folder_path)

                    # Convert path to @transitions/ path
                    effect["reader"]["path"] = os.path.join("@transitions", category_path, file_path)
                    continue

                # Find absolute path of file (if needed)
                if not os.path.isabs(path):
                    # Convert path to the correct relative path (based on the existing folder)
                    path = os.path.abspath(os.path.join(existing_project_folder, path))
                # Convert absolute path to relavite
                effect["reader"]["path"] = os.path.relpath(path, new_project_folder)

        except Exception as ex:
            log.error("Error while converting absolute paths to relative paths: %s" % str(ex))


    def convert_paths_to_absolute(self):
        """ Convert all paths to absolute """
        try:
            # Get project folder
            existing_project_folder = None
            if self.current_filepath:
                existing_project_folder = os.path.dirname(self.current_filepath)

            # Loop through each file
            for file in self._data["files"]:
                path = file["path"]
                # Find absolute path of file (if needed)
                if not os.path.isabs(path):
                    # Convert path to the correct relative path (based on the existing folder)
                    path = os.path.abspath(os.path.join(existing_project_folder, path))

                # Convert absolute path to relavite
                file["path"] = path

            # Loop through each clip
            for clip in self._data["clips"]:
                # Update reader path
                path = clip["reader"]["path"]
                # Find absolute path of file (if needed)
                if not os.path.isabs(path):
                    # Convert path to the correct relative path (based on the existing folder)
                    path = os.path.abspath(os.path.join(existing_project_folder, path))
                # Convert absolute path to relavite
                clip["reader"]["path"] = path

                # Update clip image path
                path = clip["image"]
                # Find absolute path of file (if needed)
                if not os.path.isabs(path):
                    # Convert path to the correct relative path (based on the existing folder)
                    path = os.path.abspath(os.path.join(existing_project_folder, path))
                # Convert absolute path to relavite
                clip["image"] = path

            # Loop through each transition
            for effect in self._data["effects"]:
                # Update reader path
                path = effect["reader"]["path"]

                # Determine if @transitions path is found
                if "@transitions" in path:
                    path = path.replace("@transitions", os.path.join(info.PATH, "transitions"))

                # Find absolute path of file (if needed)
                if not os.path.isabs(path):
                    # Convert path to the correct relative path (based on the existing folder)
                    path = os.path.abspath(os.path.join(existing_project_folder, path))
                # Convert absolute path to relavite
                effect["reader"]["path"] = path

        except Exception as ex:
            log.error("Error while converting relative paths to absolute paths: %s" % str(ex))

    def changed(self, action):
        """ This method is invoked by the UpdateManager each time a change happens (i.e UpdateInterface) """
        # Track unsaved changes
        self.has_unsaved_changes = True

        if action.type == "insert":
            # Insert new item
            old_vals = self._set(action.key, action.values, add=True)
            action.set_old_values(old_vals)  # Save previous values to reverse this action

        elif action.type == "update":
            # Update existing item
            old_vals = self._set(action.key, action.values, partial_update=action.partial_update)
            action.set_old_values(old_vals)  # Save previous values to reverse this action

        elif action.type == "delete":
            # Delete existing item
            old_vals = self._set(action.key, remove=True)
            action.set_old_values(old_vals)  # Save previous values to reverse this action

    # Utility methods
    def generate_id(self, digits=10):
        """ Generate random alphanumeric ids """

        chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        id = ""
        for i in range(digits):
            c_index = random.randint(0, len(chars) - 1)
            id += (chars[c_index])
        return id
