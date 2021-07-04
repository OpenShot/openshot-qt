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

import os
import copy

from classes import info
from classes.app import get_app


# Get project data reference
app = get_app()
project = app.project


class QueryObject:
    """ This class allows one or more project data objects to be queried """

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
            self.id = project.generate_id()

            # save id in data (if attribute found)
            self.data["id"] = copy.deepcopy(self.id)

            # Set key (if needed)
            if not self.key:
                self.key = copy.deepcopy(OBJECT_TYPE.object_key)
                self.key.append({"id": self.id})

            # Insert into project data
            app.updates.insert(copy.deepcopy(OBJECT_TYPE.object_key), copy.deepcopy(self.data))

            # Mark record as 'update' now... so another call to this method won't insert it again
            self.type = "update"

        elif self.id and self.type == "update":

            # Update existing project data
            app.updates.update(self.key, self.data)

    def delete(self, OBJECT_TYPE):
        """ Delete the object from the project data store """

        # Delete if object found and not pending insert
        if self.id and self.type == "update":
            # Delete from project data store
            app.updates.delete(self.key)
            self.type = "delete"

    def title(self):
        """ Get the translated display title of this item """
        # Needs to be overwritten in each derived class
        return None

    def filter(OBJECT_TYPE, **kwargs):
        """ Take any arguments given as filters, and find a list of matching objects """

        # Get a list of all objects of this type
        parent = project.get(OBJECT_TYPE.object_key)

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
                object.data = copy.deepcopy(child)  # copy of object
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

        # Get project folder (if any)
        project_folder = None
        if project.current_filepath:
            project_folder = os.path.dirname(project.current_filepath)

        # Convert relative file path into absolute (if needed)
        file_path = self.data["path"]
        if not os.path.isabs(file_path) and project_folder:
            file_path = os.path.abspath(os.path.join(project_folder, self.data["path"]))

        # Return absolute path of file
        return file_path

    def relative_path(self):
        """ Get relative path (based on the current working directory) """

        # Get absolute file path
        file_path = self.absolute_path()

        # Convert path to relative (based on current working directory of Python)
        file_path = os.path.relpath(file_path, info.CWD)

        # Return relative path
        return file_path


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
        clips = project.get("clips")
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
                            object.data = copy.deepcopy(child)
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
