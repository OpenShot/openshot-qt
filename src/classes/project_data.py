"""
 @file
 @brief This file listens to changes, and updates the primary project data
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

import copy
import glob
import os
import random
import shutil

from classes import info, settings
from classes.image_types import is_image
from classes.json_data import JsonDataStore
from classes.logger import log
from classes.updates import UpdateInterface
from windows.views.find_file import find_missing_file


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
        if not key:
            log.warning("Cannot get empty key.")
            return None
        if not isinstance(key, list):
            key = [key]

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

        # After processing each key, we've found object, return it
        return obj

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

        # Try to load user default project
        if os.path.exists(info.USER_DEFAULT_PROJECT):
            try:
                self._data = self.read_from_file(info.USER_DEFAULT_PROJECT)
            except (FileNotFoundError, PermissionError) as ex:
                log.warning("Unable to load user project defaults from {}: {}".format(info.USER_DEFAULT_PROJECT, ex))
            except Exception:
                raise
            else:
                log.info("Loaded user project defaults from {}".format(info.USER_DEFAULT_PROJECT))
        else:
            # Fall back to OpenShot defaults, if user defaults didn't load
            self._data = self.read_from_file(self.default_project_filepath)

        self.current_filepath = None
        self.has_unsaved_changes = False

        # Get default profile
        s = settings.get_settings()
        default_profile = s.get("default-profile")

        # Loop through profiles
        for profile_folder in [info.USER_PROFILES_PATH, info.PROFILES_PATH]:
            for file in os.listdir(profile_folder):
                # Load Profile and append description
                profile_path = os.path.join(profile_folder, file)
                profile = openshot.Profile(profile_path)

                if default_profile == profile.info.description:
                    log.info("Setting default profile to %s" % profile.info.description)

                    # Update default profile
                    self._data["profile"] = profile.info.description
                    self._data["width"] = profile.info.width
                    self._data["height"] = profile.info.height
                    self._data["fps"] = {"num" : profile.info.fps.num, "den" : profile.info.fps.den}
                    break

        # Get the default audio settings for the timeline (and preview playback)
        default_sample_rate = int(s.get("default-samplerate"))
        default_channel_layout = s.get("default-channellayout")

        channels = 2
        channel_layout = openshot.LAYOUT_STEREO
        if default_channel_layout == "LAYOUT_MONO":
            channels = 1
            channel_layout = openshot.LAYOUT_MONO
        elif default_channel_layout == "LAYOUT_STEREO":
            channels = 2
            channel_layout = openshot.LAYOUT_STEREO
        elif default_channel_layout == "LAYOUT_SURROUND":
            channels = 3
            channel_layout = openshot.LAYOUT_SURROUND
        elif default_channel_layout == "LAYOUT_5POINT1":
            channels = 6
            channel_layout = openshot.LAYOUT_5POINT1
        elif default_channel_layout == "LAYOUT_7POINT1":
            channels = 8
            channel_layout = openshot.LAYOUT_7POINT1

        # Set default samplerate and channels
        self._data["sample_rate"] = default_sample_rate
        self._data["channels"] = channels
        self._data["channel_layout"] = channel_layout

        # Set default project ID
        self._data["id"] = self.generate_id()

    def load(self, file_path, clear_thumbnails=True):
        """ Load project from file """

        self.new()

        if file_path:
            log.info("Loading project file: {}".format(file_path))

            # Default project data
            default_project = self._data

            try:
                # Attempt to load v2.X project file
                project_data = self.read_from_file(file_path, path_mode="absolute")

                # Fix history (if broken)
                if not project_data.get("history"):
                    project_data["history"] = {"undo": [], "redo": []}

            except Exception as ex:
                try:
                    # Attempt to load legacy project file (v1.X version)
                    project_data = self.read_legacy_project_file(file_path)

                except Exception as ex:
                    # Project file not recognized as v1.X or v2.X, bubble up error
                    raise

            # Merge default and project settings, excluding settings not in default.
            self._data = self.merge_settings(default_project, project_data)

            # On success, save current filepath
            self.current_filepath = file_path

            # Clear needs save flag
            self.has_unsaved_changes = False

            # Check if paths are all valid
            self.check_if_paths_are_valid()

            # Copy any project thumbnails to main THUMBNAILS folder
            loaded_project_folder = os.path.dirname(self.current_filepath)
            project_thumbnails_folder = os.path.join(loaded_project_folder, "thumbnail")
            if os.path.exists(project_thumbnails_folder) and clear_thumbnails:
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

    def scale_keyframe_value(self, original_value, scale_factor):
        """Scale keyframe X coordinate by some factor, except for 1 (leave that alone)"""
        if original_value == 1.0:
            # This represents the first frame of a clip (so we want to maintain that)
            return original_value
        else:
            # Round to nearest INT
            return round(original_value * scale_factor)

    def rescale_keyframes(self, scale_factor):
        """Adjust all keyframe coordinates from previous FPS to new FPS (using a scale factor)"""
        log.info('Scale all keyframes by a factor of %s' % scale_factor)

        # Loop through all clips (and look for Keyframe objects)
        # Scale the X coordinate by factor (which represents the frame #)
        for clip in self._data.get('clips', []):
            for attribute in clip:
                if type(clip.get(attribute)) == dict and "Points" in clip.get(attribute):
                    for point in clip.get(attribute).get("Points"):
                        if "co" in point:
                            point["co"]["X"] = self.scale_keyframe_value(point["co"].get("X", 0.0), scale_factor)
                if type(clip.get(attribute)) == dict and "red" in clip.get(attribute):
                    for color in clip.get(attribute):
                        for point in clip.get(attribute).get(color).get("Points"):
                            if "co" in point:
                                point["co"]["X"] = self.scale_keyframe_value(point["co"].get("X", 0.0), scale_factor)
            for effect in clip.get("effects", []):
                for attribute in effect:
                    if type(effect.get(attribute)) == dict and "Points" in effect.get(attribute):
                        for point in effect.get(attribute).get("Points"):
                            if "co" in point:
                                point["co"]["X"] = self.scale_keyframe_value(point["co"].get("X", 0.0), scale_factor)
                    if type(effect.get(attribute)) == dict and "red" in effect.get(attribute):
                        for color in effect.get(attribute):
                            for point in effect.get(attribute).get(color).get("Points"):
                                if "co" in point:
                                    point["co"]["X"] = self.scale_keyframe_value(point["co"].get("X", 0.0), scale_factor)

        # Loop through all effects/transitions (and look for Keyframe objects)
        # Scale the X coordinate by factor (which represents the frame #)
        for effect in self._data.get('effects',[]):
            for attribute in effect:
                if type(effect.get(attribute)) == dict and "Points" in effect.get(attribute):
                    for point in effect.get(attribute).get("Points"):
                        if "co" in point:
                            point["co"]["X"] = self.scale_keyframe_value(point["co"].get("X", 0.0), scale_factor)
                if type(effect.get(attribute)) == dict and "red" in effect.get(attribute):
                    for color in effect.get(attribute):
                        for point in effect.get(attribute).get(color).get("Points"):
                            if "co" in point:
                                point["co"]["X"] = self.scale_keyframe_value(point["co"].get("X", 0.0), scale_factor)

        # Get app, and distribute all project data through update manager
        from classes.app import get_app
        get_app().updates.load(self._data)

    def read_legacy_project_file(self, file_path):
        """Attempt to read a legacy version 1.x openshot project file"""
        import sys, pickle
        from classes.query import File, Track, Clip, Transition
        from classes.app import get_app
        import openshot
        import json

        # Get translation method
        _ = get_app()._tr

        # Append version info
        v = openshot.GetVersion()
        project_data = {}
        project_data["version"] = {"openshot-qt" : info.VERSION,
                                   "libopenshot" : v.ToString()}

        # Get FPS from project
        from classes.app import get_app
        fps = get_app().project.get("fps")
        fps_float = float(fps["num"]) / float(fps["den"])

        # Import legacy openshot classes (from version 1.X)
        from classes.legacy.openshot import classes as legacy_classes
        from classes.legacy.openshot.classes import project as legacy_project
        from classes.legacy.openshot.classes import sequences as legacy_sequences
        from classes.legacy.openshot.classes import track as legacy_track
        from classes.legacy.openshot.classes import clip as legacy_clip
        from classes.legacy.openshot.classes import keyframe as legacy_keyframe
        from classes.legacy.openshot.classes import files as legacy_files
        from classes.legacy.openshot.classes import transition as legacy_transition
        from classes.legacy.openshot.classes import effect as legacy_effect
        from classes.legacy.openshot.classes import marker as legacy_marker
        sys.modules['openshot.classes'] = legacy_classes
        sys.modules['classes.project'] = legacy_project
        sys.modules['classes.sequences'] = legacy_sequences
        sys.modules['classes.track'] = legacy_track
        sys.modules['classes.clip'] = legacy_clip
        sys.modules['classes.keyframe'] = legacy_keyframe
        sys.modules['classes.files'] = legacy_files
        sys.modules['classes.transition'] = legacy_transition
        sys.modules['classes.effect'] = legacy_effect
        sys.modules['classes.marker'] = legacy_marker

        # Keep track of files that failed to load
        failed_files = []

        with open(file_path.encode('UTF-8'), 'rb') as f:
            try:
                # Unpickle legacy openshot project file
                v1_data = pickle.load(f, fix_imports=True, encoding="UTF-8")
                file_lookup = {}

                # Loop through files
                for item in v1_data.project_folder.items:
                    # Is this item a File (i.e. ignore folders)
                    if isinstance(item, legacy_files.OpenShotFile):
                        # Create file
                        try:
                            clip = openshot.Clip(item.name)
                            reader = clip.Reader()
                            file_data = json.loads(reader.Json(), strict=False)

                            # Determine media type
                            if file_data["has_video"] and not is_image(file_data):
                                file_data["media_type"] = "video"
                            elif file_data["has_video"] and is_image(file_data):
                                file_data["media_type"] = "image"
                            elif file_data["has_audio"] and not file_data["has_video"]:
                                file_data["media_type"] = "audio"

                            # Save new file to the project data
                            file = File()
                            file.data = file_data
                            file.save()

                            # Keep track of new ids and old ids
                            file_lookup[item.unique_id] = file

                        except:
                            # Handle exception quietly
                            msg = ("%s is not a valid video, audio, or image file." % item.name)
                            log.error(msg)
                            failed_files.append(item.name)

                # Delete all tracks
                track_list = copy.deepcopy(Track.filter())
                for track in track_list:
                    track.delete()

                # Create new tracks
                track_counter = 0
                for legacy_t in reversed(v1_data.sequences[0].tracks):
                    t = Track()
                    t.data = {"number": track_counter, "y": 0, "label": legacy_t.name}
                    t.save()

                    track_counter += 1

                # Loop through clips
                track_counter = 0
                for sequence in v1_data.sequences:
                    for track in reversed(sequence.tracks):
                        for clip in track.clips:
                            # Get associated file for this clip
                            if clip.file_object.unique_id in file_lookup.keys():
                                file = file_lookup[clip.file_object.unique_id]
                            else:
                                # Skip missing file
                                log.info("Skipping importing missing file: %s" % clip.file_object.unique_id)
                                continue

                            # Create clip
                            if (file.data["media_type"] == "video" or file.data["media_type"] == "image"):
                                # Determine thumb path
                                thumb_path = os.path.join(info.THUMBNAIL_PATH, "%s.png" % file.data["id"])
                            else:
                                # Audio file
                                thumb_path = os.path.join(info.PATH, "images", "AudioThumbnail.png")

                            # Get file name
                            path, filename = os.path.split(file.data["path"])

                            # Convert path to the correct relative path (based on this folder)
                            file_path = file.absolute_path()

                            # Create clip object for this file
                            c = openshot.Clip(file_path)

                            # Append missing attributes to Clip JSON
                            new_clip = json.loads(c.Json(), strict=False)
                            new_clip["file_id"] = file.id
                            new_clip["title"] = filename
                            new_clip["image"] = thumb_path

                            # Check for optional start and end attributes
                            new_clip["start"] = clip.start_time
                            new_clip["end"] = clip.end_time
                            new_clip["position"] = clip.position_on_track
                            new_clip["layer"] = track_counter

                            # Clear alpha (if needed)
                            if clip.video_fade_in or clip.video_fade_out:
                                new_clip["alpha"]["Points"] = []

                            # Video Fade IN
                            if clip.video_fade_in:
                                # Add keyframes
                                start = openshot.Point(round(clip.start_time * fps_float) + 1, 0.0, openshot.BEZIER)
                                start_object = json.loads(start.Json(), strict=False)
                                end = openshot.Point(round((clip.start_time + clip.video_fade_in_amount) * fps_float) + 1, 1.0, openshot.BEZIER)
                                end_object = json.loads(end.Json(), strict=False)
                                new_clip["alpha"]["Points"].append(start_object)
                                new_clip["alpha"]["Points"].append(end_object)

                            # Video Fade OUT
                            if clip.video_fade_out:
                                # Add keyframes
                                start = openshot.Point(round((clip.end_time - clip.video_fade_out_amount) * fps_float) + 1, 1.0, openshot.BEZIER)
                                start_object = json.loads(start.Json(), strict=False)
                                end = openshot.Point(round(clip.end_time * fps_float) + 1, 0.0, openshot.BEZIER)
                                end_object = json.loads(end.Json(), strict=False)
                                new_clip["alpha"]["Points"].append(start_object)
                                new_clip["alpha"]["Points"].append(end_object)

                            # Clear Audio (if needed)
                            if clip.audio_fade_in or clip.audio_fade_out:
                                new_clip["volume"]["Points"] = []
                            else:
                                p = openshot.Point(1, clip.volume / 100.0, openshot.BEZIER)
                                p_object = json.loads(p.Json(), strict=False)
                                new_clip["volume"] = { "Points" : [p_object]}

                            # Audio Fade IN
                            if clip.audio_fade_in:
                                # Add keyframes
                                start = openshot.Point(round(clip.start_time * fps_float) + 1, 0.0, openshot.BEZIER)
                                start_object = json.loads(start.Json(), strict=False)
                                end = openshot.Point(round((clip.start_time + clip.video_fade_in_amount) * fps_float) + 1, clip.volume / 100.0, openshot.BEZIER)
                                end_object = json.loads(end.Json(), strict=False)
                                new_clip["volume"]["Points"].append(start_object)
                                new_clip["volume"]["Points"].append(end_object)

                            # Audio Fade OUT
                            if clip.audio_fade_out:
                                # Add keyframes
                                start = openshot.Point(round((clip.end_time - clip.video_fade_out_amount) * fps_float) + 1, clip.volume / 100.0, openshot.BEZIER)
                                start_object = json.loads(start.Json(), strict=False)
                                end = openshot.Point(round(clip.end_time * fps_float) + 1, 0.0, openshot.BEZIER)
                                end_object = json.loads(end.Json(), strict=False)
                                new_clip["volume"]["Points"].append(start_object)
                                new_clip["volume"]["Points"].append(end_object)

                            # Save clip
                            clip_object = Clip()
                            clip_object.data = new_clip
                            clip_object.save()

                        # Loop through transitions
                        for trans in track.transitions:
                            # Fix default transition
                            if not trans.resource or not os.path.exists(trans.resource):
                                trans.resource = os.path.join(info.PATH, "transitions", "common", "fade.svg")

                            # Open up QtImageReader for transition Image
                            transition_reader = openshot.QtImageReader(trans.resource)

                            trans_begin_value = 1.0
                            trans_end_value = -1.0
                            if trans.reverse:
                                trans_begin_value = -1.0
                                trans_end_value = 1.0

                            brightness = openshot.Keyframe()
                            brightness.AddPoint(1, trans_begin_value, openshot.BEZIER)
                            brightness.AddPoint(round(trans.length * fps_float) + 1, trans_end_value, openshot.BEZIER)
                            contrast = openshot.Keyframe(trans.softness * 10.0)

                            # Create transition dictionary
                            transitions_data = {
                                "id": get_app().project.generate_id(),
                                "layer": track_counter,
                                "title": "Transition",
                                "type": "Mask",
                                "position": trans.position_on_track,
                                "start": 0,
                                "end": trans.length,
                                "brightness": json.loads(brightness.Json(), strict=False),
                                "contrast": json.loads(contrast.Json(), strict=False),
                                "reader": json.loads(transition_reader.Json(), strict=False),
                                "replace_image": False
                            }

                            # Save transition
                            t = Transition()
                            t.data = transitions_data
                            t.save()

                        # Increment track counter
                        track_counter += 1

            except Exception as ex:
                # Error parsing legacy contents
                msg = _("Failed to load project file %(path)s: %(error)s" % {"path": file_path, "error": ex})
                log.error(msg)
                raise Exception(msg)

        # Show warning if some files failed to load
        if failed_files:
            # Throw exception
            raise Exception(_("Failed to load the following files:\n%s" % ", ".join(failed_files)))

        # Return mostly empty project_data dict (with just the current version #)
        log.info("Successfully loaded legacy project file: %s" % file_path)
        return project_data

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

        elif openshot_version <= "2.1.0-dev":
            # Fix handle_left and handle_right coordinates and default to ease in/out bezier curve
            # using the new percent based keyframes
            for clip_type in ["clips", "effects"]:
                for clip in self._data[clip_type]:
                    for object in [clip] + clip.get('effects',[]):
                        for item_key, item_data in object.items():
                            # Does clip attribute have a {"Points": [...]} list
                            if type(item_data) == dict and "Points" in item_data:
                                for point in item_data.get("Points"):
                                    # Convert to percent-based curves
                                    if "handle_left" in point:
                                        # Left handle
                                        point.get("handle_left")["X"] = 0.5
                                        point.get("handle_left")["Y"] = 1.0
                                    if "handle_right" in point:
                                        # Right handle
                                        point.get("handle_right")["X"] = 0.5
                                        point.get("handle_right")["Y"] = 0.0

                            elif type(item_data) == dict and "red" in item_data:
                                for color in ["red", "blue", "green", "alpha"]:
                                    for point in item_data.get(color).get("Points"):
                                        # Convert to percent-based curves
                                        if "handle_left" in point:
                                            # Left handle
                                            point.get("handle_left")["X"] = 0.5
                                            point.get("handle_left")["Y"] = 1.0
                                        if "handle_right" in point:
                                            # Right handle
                                            point.get("handle_right")["X"] = 0.5
                                            point.get("handle_right")["Y"] = 0.0

        # Fix default project id (if found)
        if self._data.get("id") == "T0":
            self._data["id"] = self.generate_id()

    def save(self, file_path, move_temp_files=True, make_paths_relative=True):
        """ Save project file to disk """
        import openshot

        log.info("Saving project file: {}".format(file_path))

        # Move all temp files (i.e. Blender animations) to the project folder
        if move_temp_files:
            self.move_temp_paths_to_project_folder(file_path, previous_path=self.current_filepath)

        # Append version info
        v = openshot.GetVersion()
        self._data["version"] = { "openshot-qt" : info.VERSION,
                                  "libopenshot" : v.ToString() }

        # Try to save project settings file, will raise error on failure
        self.write_to_file(file_path, self._data, path_mode="relative", previous_path=self.current_filepath)

        # On success, save current filepath
        self.current_filepath = file_path

        # Add to recent files setting
        self.add_to_recent_files(file_path)

        # Track unsaved changes
        self.has_unsaved_changes = False

    def move_temp_paths_to_project_folder(self, file_path, previous_path=None):
        """ Move all temp files (such as Thumbnails, Titles, and Blender animations) to the project asset folder. """
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
                if info.BLENDER_PATH in path or info.ASSETS_PATH in path:
                    log.info("Temp blender file path detected in file")

                    # Get folder of file
                    folder_path, file_name = os.path.split(path)
                    parent_path, folder_name = os.path.split(folder_path)
                    new_parent_path = new_project_folder

                    if os.path.isdir(path) or "%" in path:
                        # Update path to new folder
                        new_parent_path = os.path.join(new_project_folder, folder_name)

                        # Copy blender tree into new folder
                        shutil.copytree(folder_path, new_parent_path)
                    else:
                        # New path
                        new_parent_path = os.path.join(new_project_folder, "assets")

                        # Ensure blender folder exists
                        if not os.path.exists(new_parent_path):
                            os.mkdir(new_parent_path)

                        # Copy titles/individual files into new folder
                        shutil.copy2(path, os.path.join(new_parent_path, file_name))

                    # Update paths in project to new location
                    file["path"] = os.path.join(new_parent_path, file_name)

            # Loop through each clip
            for clip in self._data["clips"]:
                path = clip["reader"]["path"]

                # Find any temp BLENDER file paths
                if info.BLENDER_PATH in path or info.ASSETS_PATH in path:
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
                if info.BLENDER_PATH in path or info.ASSETS_PATH in path:
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
        if not file_path or "backup.osp" in file_path:
            # Ignore backup recovery project
            return

        s = settings.get_settings()
        recent_projects = s.get("recent_projects")

        # Make sure file_path is absolute
        file_path = os.path.abspath(file_path)

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
        s.save()

    def check_if_paths_are_valid(self):
        """Check if all paths are valid, and prompt to update them if needed"""
        # Get import path or project folder
        starting_folder = None
        if self._data["import_path"]:
            starting_folder = os.path.join(self._data["import_path"])
        elif self.current_filepath:
            starting_folder = os.path.dirname(self.current_filepath)

        # Get translation method
        from classes.app import get_app
        _ = get_app()._tr

        from PyQt5.QtWidgets import QFileDialog, QMessageBox

        log.info("checking project files...")

        # Loop through each files (in reverse order)
        for file in reversed(self._data["files"]):
            path = file["path"]
            parent_path, file_name_with_ext = os.path.split(path)

            log.info("checking file %s" % path)
            if not os.path.exists(path) and "%" not in path:
                # File is missing
                path, is_modified, is_skipped = find_missing_file(path)
                if path and is_modified and not is_skipped:
                    # Found file, update path
                    file["path"] = path
                    get_app().updates.update(["import_path"], os.path.dirname(path))
                    log.info("Auto-updated missing file: %s" % path)
                elif is_skipped:
                    # Remove missing file
                    log.info('Removed missing file: %s' % file_name_with_ext)
                    self._data["files"].remove(file)

        # Loop through each clip (in reverse order)
        for clip in reversed(self._data["clips"]):
            path = clip["reader"]["path"]

            if not os.path.exists(path) and "%" not in path:
                # File is missing
                path, is_modified, is_skipped = find_missing_file(path)
                file_name_with_ext = os.path.basename(path)

                if path and is_modified and not is_skipped:
                    # Found file, update path
                    clip["reader"]["path"] = path
                    log.info("Auto-updated missing file: %s" % clip["reader"]["path"])
                elif is_skipped:
                    # Remove missing file
                    log.info('Removed missing clip: %s' % file_name_with_ext)
                    self._data["clips"].remove(clip)

    def changed(self, action):
        """ This method is invoked by the UpdateManager each time a change happens (i.e UpdateInterface) """
        if action.type == "insert":
            # Insert new item
            old_vals = self._set(action.key, action.values, add=True)
            action.set_old_values(old_vals)  # Save previous values to reverse this action
            self.has_unsaved_changes = True

        elif action.type == "update":
            # Update existing item
            old_vals = self._set(action.key, action.values, partial_update=action.partial_update)
            action.set_old_values(old_vals)  # Save previous values to reverse this action
            self.has_unsaved_changes = True

        elif action.type == "delete":
            # Delete existing item
            old_vals = self._set(action.key, remove=True)
            action.set_old_values(old_vals)  # Save previous values to reverse this action
            self.has_unsaved_changes = True

        elif action.type == "load":
            # Don't track unsaved changes when loading a project
            pass

    # Utility methods
    def generate_id(self, digits=10):
        """ Generate random alphanumeric ids """

        chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        id = ""
        for i in range(digits):
            c_index = random.randint(0, len(chars) - 1)
            id += (chars[c_index])
        return id
