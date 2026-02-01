"""
 @file
 @brief This file can easily query Clips, Files, and other project data
 @author Jonathan Thomas <jonathan@openshot.org>

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
import json
import os

import openshot

from classes import info
from classes.app import get_app
from classes.path_utils import absolute_media_path


class QueryObject:
    """ This class allows one or more project data objects to be queried """

    # Cache detached project objects per update version
    _cache_version = None
    _cache = {}

    def __init__(self):
        """ Constructor """

        self.id = None  # Unique ID of object
        self.key = None  # Key path to object in project data
        self.data = None  # Data dictionary of object
        self.parent = None  # Only used with effects (who belong to clips)
        self.type = "insert"  # Type of operation needed to save

    def save(self, OBJECT_TYPE):
        """ Save the object back to the project data store """

        # Insert or Update this data into the project data store
        if not self.id and self.type == "insert":

            # Insert record, and Generate id
            self.id = get_app().project.generate_id()

            # save id in data (if attribute found)
            self.data["id"] = json.loads(json.dumps(self.id))

            # Set key (if needed)
            if not self.key:
                self.key = json.loads(json.dumps(OBJECT_TYPE.object_key))
                self.key.append({"id": self.id})

            # Insert into project data
            get_app().updates.insert(json.loads(json.dumps(OBJECT_TYPE.object_key)), json.loads(json.dumps(self.data)))

            # Mark record as 'update' now... so another call to this method won't insert it again
            self.type = "update"

        elif self.id and self.type == "update":

            # Update existing project data
            get_app().updates.update(self.key, self.data)

    def delete(self, OBJECT_TYPE):
        """ Delete the object from the project data store """

        # Delete if object found and not pending insert
        if self.id and self.type == "update":
            # Delete from project data store
            get_app().updates.delete(self.key)
            self.type = "delete"

    def title(self):
        """ Get the translated display title of this item """
        # Needs to be overwritten in each derived class
        return None

    @classmethod
    def _get_cached_child(cls, OBJECT_TYPE, child):
        """Return a cached, detached copy of child, clearing cache when project changes"""
        updates = get_app().updates
        current_version = getattr(updates, "data_version", 0)

        if cls._cache_version != current_version:
            cls._cache = {}
            cls._cache_version = current_version

        object_cache = cls._cache.setdefault(OBJECT_TYPE.object_name, {})
        child_id = child.get("id")

        # Cache deep copies by id; reuse within the same project version
        cached = object_cache.get(child_id)
        if cached is None:
            cached = copy.deepcopy(child)
            object_cache[child_id] = cached
        return cached

    def filter(OBJECT_TYPE, **kwargs):
        """ Take any arguments given as filters, and find a list of matching objects """

        # Get a list of all objects of this type
        parent = get_app().project.get(OBJECT_TYPE.object_key)

        if not parent:
            return []

        matching_objects = []

        # Loop through all children objects
        for child in parent:

            # Protect against non-iterable/subscriptables
            if not child:
                continue

            # Loop through all kwargs (and look for matches)
            match = True
            for key, value in kwargs.items():

                if key in child and child[key] != value:
                    match = False
                    break

                # Intersection Position
                if key == "intersect" and (
                    child.get("position", 0) > value
                    or child.get("position", 0) + (child.get("end", 0) - child.get("start", 0)) < value
                ):
                    match = False


            # Add matched record
            if match:
                object = OBJECT_TYPE()
                object.id = child["id"]
                object.key = [OBJECT_TYPE.object_name, {"id": object.id}]
                object.data = QueryObject._get_cached_child(OBJECT_TYPE, child)
                object.type = "update"
                matching_objects.append(object)

        # Return matching objects
        return matching_objects

    def get(OBJECT_TYPE, **kwargs):
        """ Take any arguments given as filters, and find the first matching object """

        # Look for matching objects
        matching_objects = QueryObject.filter(OBJECT_TYPE, **kwargs)

        if matching_objects:
            return matching_objects[0]
        else:
            return None


class Clip(QueryObject):
    """ This class allows Clips to be queried, updated, and deleted from the project data. """
    object_name = "clips"  # Derived classes should define this
    object_key = [object_name]  # Derived classes should define this also

    def save(self):
        """ Save the object back to the project data store """
        super().save(Clip)

    def delete(self):
        """ Delete the object from the project data store """
        super().delete(Clip)

    def filter(**kwargs):
        """ Take any arguments given as filters, and find a list of matching objects """
        return QueryObject.filter(Clip, **kwargs)

    def get(**kwargs):
        """ Take any arguments given as filters, and find the first matching object """
        return QueryObject.get(Clip, **kwargs)

    def title(self):
        """ Get the translated display title of this item """
        path = self.data.get("reader", {}).get("path")
        return os.path.basename(path)

class Transition(QueryObject):
    """ This class allows Transitions (i.e. timeline effects) to be queried, updated, and deleted from the project data. """
    object_name = "effects"  # Derived classes should define this
    object_key = [object_name]  # Derived classes should define this also

    def save(self):
        """ Save the object back to the project data store """
        super().save(Transition)

    def delete(self):
        """ Delete the object from the project data store """
        super().delete(Transition)

    def filter(**kwargs):
        """ Take any arguments given as filters, and find a list of matching objects """
        return QueryObject.filter(Transition, **kwargs)

    def get(**kwargs):
        """ Take any arguments given as filters, and find the first matching object """
        return QueryObject.get(Transition, **kwargs)

    def title(self):
        """ Get the translated display title of this item """
        path = self.data.get("reader", {}).get("path")
        if not path:
            return None
        fileBaseName = os.path.splitext(os.path.basename(path))[0]

        # split the name into parts (looking for a number)
        suffix_number = None
        name_parts = fileBaseName.split("_")
        if name_parts[-1].isdigit():
            suffix_number = name_parts[-1]
        # get name of transition
        item_name = fileBaseName.replace("_", " ").capitalize()

        # replace suffix number with placeholder (if any)
        if suffix_number:
            item_name = item_name.replace(suffix_number, "%s")
            item_name = get_app()._tr(item_name) % suffix_number
        else:
            item_name = get_app()._tr(item_name)
        return item_name


class File(QueryObject):
    """ This class allows Files to be queried, updated, and deleted from the project data. """
    object_name = "files"  # Derived classes should define this
    object_key = [object_name]  # Derived classes should define this also

    def save(self):
        """ Save the object back to the project data store """
        super().save(File)

    def delete(self):
        """ Delete the object from the project data store """
        super().delete(File)

    def filter(**kwargs):
        """ Take any arguments given as filters, and find a list of matching objects """
        return QueryObject.filter(File, **kwargs)

    def get(**kwargs):
        """ Take any arguments given as filters, and find the first matching object """
        return QueryObject.get(File, **kwargs)

    def absolute_path(self):
        """ Get absolute file path of file """

        file_path = self.data.get("path")
        resolved = absolute_media_path(file_path)
        if resolved:
            return resolved
        return file_path or ""

    def relative_path(self):
        """ Get relative path (based on the current working directory) """

        file_path = self.absolute_path()
        # Convert path to relative (based on current working directory of Python)
        return os.path.relpath(file_path, info.CWD)

    def get_ai_metadata(self) -> dict:
        """Get AI metadata for this file"""
        return self.data.get('ai_metadata', {})
    
    def has_ai_metadata(self) -> bool:
        """Check if file has been analyzed by AI"""
        ai_meta = self.get_ai_metadata()
        return ai_meta.get('analyzed', False)
    
    def get_ai_tags(self) -> dict:
        """Get AI-generated tags"""
        ai_meta = self.get_ai_metadata()
        return ai_meta.get('tags', {})
    
    def get_ai_description(self) -> str:
        """Get AI-generated description"""
        ai_meta = self.get_ai_metadata()
        return ai_meta.get('description', '')
    
    def profile(self):
        """ Get the profile of the file """
        # Load file Json into Profile object
        file_profile = openshot.Profile()
        file_profile.SetJson(json.dumps(self.data))

        if file_profile.info.display_ratio.num == 1 and file_profile.info.display_ratio.den == 1:
            # Some audio / image files have inaccurate DAR - calculate from size and pixel ratio
            file_profile.info.display_ratio = openshot.Fraction(round(file_profile.info.width * file_profile.info.pixel_ratio.ToFloat()), file_profile.info.height)
            file_profile.info.display_ratio.Reduce()

        # Iterate through all possible profiles
        for profile_folder in [info.USER_PROFILES_PATH, info.PROFILES_PATH]:
            for file in reversed(sorted(os.listdir(profile_folder))):
                profile_path = os.path.join(profile_folder, file)
                if os.path.isdir(profile_path):
                    continue
                try:
                    # Load Profile
                    profile = openshot.Profile(profile_path)
                    if profile == file_profile:
                        return profile
                except RuntimeError as e:
                    pass
        return file_profile


class Marker(QueryObject):
    """ This class allows Markers to be queried, updated, and deleted from the project data. """
    object_name = "markers"  # Derived classes should define this
    object_key = [object_name]  # Derived classes should define this also

    def save(self):
        """ Save the object back to the project data store """
        super().save(Marker)

    def delete(self):
        """ Delete the object from the project data store """
        super().delete(Marker)

    def filter(**kwargs):
        """ Take any arguments given as filters, and find a list of matching objects """
        return QueryObject.filter(Marker, **kwargs)

    def get(**kwargs):
        """ Take any arguments given as filters, and find the first matching object """
        return QueryObject.get(Marker, **kwargs)


class Track(QueryObject):
    """ This class allows Tracks to be queried, updated, and deleted from the project data. """
    object_name = "layers"  # Derived classes should define this
    object_key = [object_name]  # Derived classes should define this also

    def save(self):
        """ Save the object back to the project data store """
        super().save(Track)

    def delete(self):
        """ Delete the object from the project data store """
        super().delete(Track)

    def filter(**kwargs):
        """ Take any arguments given as filters, and find a list of matching objects """
        return QueryObject.filter(Track, **kwargs)

    def get(**kwargs):
        """ Take any arguments given as filters, and find the first matching object """
        return QueryObject.get(Track, **kwargs)

    def __lt__(self, other):
        return self.data.get('number', 0) < other.data.get('number', 0)

    def __gt__(self, other):
        return self.data.get('number', 0) > other.data.get('number', 0)


class Effect(QueryObject):
    """ This class allows Effects to be queried, updated, and deleted from the project data. """
    object_name = "effects"  # Derived classes should define this
    object_key = [object_name]  # Derived classes should define this also

    def save(self):
        """ Save the object back to the project data store """
        super().save(Effect)

    def delete(self):
        """ Delete the object from the project data store """
        super().delete(Effect)

    def filter(**kwargs):
        """ Take any arguments given as filters, and find a list of matching objects """

        # Get a list of clips
        clips = get_app().project.get("clips")
        matching_objects = []

        # Loop through all clips
        if clips:
            for clip in clips:
                # Loop through all effects
                if "effects" in clip:
                    for child in clip["effects"]:

                        # Loop through all kwargs (and look for matches)
                        match = True
                        for key, value in kwargs.items():
                            if key in child and child[key] != value:
                                match = False
                                break

                        # Add matched record
                        if match:
                            object = Effect()
                            object.id = child["id"]
                            object.key = ["clips", {"id": clip["id"]}, "effects", {"id": object.id}]
                            object.data = json.loads(json.dumps(child))
                            object.type = "update"
                            object.parent = clip
                            matching_objects.append(object)

        # Return matching objects
        return matching_objects

    def title(self):
        """ Get the translated display title of this item """
        return self.data.get("name") or self.data.get("type")

    def get(**kwargs):
        """ Take any arguments given as filters, and find the first matching object """
        # Look for matching objects
        matching_objects = Effect.filter(**kwargs)

        if matching_objects:
            return matching_objects[0]
        else:
            return None
