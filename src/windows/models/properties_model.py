""" 
 @file
 @brief This file contains the clip properties model, used by the properties view
 @author Jonathan Thomas <jonathan@openshot.org>
 
 @section LICENSE
 
 Copyright (c) 2008-2014 OpenShot Studios, LLC
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
from collections import OrderedDict

from PyQt5.QtCore import QMimeData, Qt
from PyQt5.QtGui import *

from classes import updates
from classes import info
from classes.query import Clip, Transition, Effect
from classes.logger import log
from classes.app import get_app

try:
    import json
except ImportError:
    import simplejson as json


class ClipStandardItemModel(QStandardItemModel):
    def __init__(self, parent=None):
        QStandardItemModel.__init__(self)

    def mimeData(self, indexes):
        # Create MimeData for drag operation
        data = QMimeData()

        # Get list of all selected file ids
        property_names = []
        for item in indexes:
            selected_row = self.itemFromIndex(item).row()
            property_names.append(self.item(selected_row, 0).data())
        data.setText(json.dumps(property_names))

        # Return Mimedata
        return data


class PropertiesModel(updates.UpdateInterface):
    # This method is invoked by the UpdateManager each time a change happens (i.e UpdateInterface)
    def changed(self, action):

        # Handle change
        if action.key and action.key[0] == "clips":
            log.info(action.values)
            # Update the model data
            self.update_model(get_app().window.txtPropertyFilter.text())

    # Update the selected item (which drives what properties show up)
    def update_item(self, item_id, item_type):
        # Clear previous selection
        self.selected = []

        log.info("Update item: %s" % item_type)

        if item_type == "clip":
            c = None
            clips = get_app().window.timeline_sync.timeline.Clips()
            for clip in clips:
                if clip.Id() == item_id:
                    c = clip
                    break

            # Append to selected clips
            self.selected.append((c, item_type))

        if item_type == "transition":
            t = None
            trans = get_app().window.timeline_sync.timeline.Effects()
            for tran in trans:
                if tran.Id() == item_id:
                    t = tran
                    break

            # Append to selected clips
            self.selected.append((t, item_type))

        if item_type == "effect":
            e = None
            clips = get_app().window.timeline_sync.timeline.Clips()
            for clip in clips:
                for effect in clip.Effects():
                    if effect.Id() == item_id:
                        e = effect
                        break

            # Append to selected items
            self.selected.append((e, item_type))


        # Get ID of item
        self.new_item = True

        # Update the model data
        self.update_model(get_app().window.txtPropertyFilter.text())

    # Update the values of the selected clip, based on the current frame
    def update_frame(self, frame_number):

        # Check for a selected clip
        if self.selected:
            clip, item_type = self.selected[0]

            # Get FPS from project
            fps = get_app().project.get(["fps"])
            fps_float = float(fps["num"]) / float(fps["den"])

            # Requested time
            requested_time = float(frame_number - 1) / fps_float

            # Determine the frame needed for this clip (based on the position on the timeline)
            time_diff = (requested_time - clip.Position()) + clip.Start();
            self.frame_number = int(time_diff * fps_float) + 1;

            # Calculate biggest and smallest possible frames
            min_frame_number = int((clip.Start() * fps_float)) + 1
            max_frame_number = int((clip.End() * fps_float)) + 1

            # Adjust frame number if out of range
            if self.frame_number < min_frame_number:
                self.frame_number = min_frame_number
            if self.frame_number > max_frame_number:
                self.frame_number = max_frame_number

            log.info("Update frame to %s" % self.frame_number)

            # Update the model data
            self.update_model(get_app().window.txtPropertyFilter.text())

    def value_updated(self, item, interpolation=-1):
        """ Table cell change event - also handles context menu to update interpolation value """

        if self.ignore_update_signal:
            log.info("value_updated: ignored")
            return

        # Determine what was changed
        property = self.model.item(item.row(), 0).data()
        property_name = property[1]["name"]
        closest_point_x = property[1]["closest_point_x"]
        property_type = property[1]["type"]
        property_key = property[0]
        clip_id, item_type = item.data()

        # Get value (if any)
        if item.text():
            new_value = float(item.text())
        else:
            new_value = None

        log.info("%s for %s changed to %s at frame %s with interpolation: %s at closest x: %s" % (property_key, clip_id, new_value, self.frame_number, interpolation, closest_point_x))


        # Find this clip
        c = None
        clip_updated = False

        if item_type == "clip":
            # Get clip object
            c = Clip.get(id=clip_id)
        elif item_type == "transition":
            # Get transition object
            c = Transition.get(id=clip_id)
        elif item_type == "effect":
            # Get effect object
            c = Effect.get(id=clip_id)

        if c:
            # Update clip attribute
            if property_key in c.data:
                log.info(c.data)

                # Check the type of property (some are keyframe, and some are not)
                if type(c.data[property_key]) == dict:
                    # Keyframe
                    # Loop through points, find a matching points on this frame
                    found_point = False
                    point_to_delete = None
                    for point in c.data[property_key]["Points"]:
                        log.info("looping points: co.X = %s" % point["co"]["X"])
                        if interpolation == -1 and point["co"]["X"] == self.frame_number:
                            # Found point, Update value
                            found_point = True
                            clip_updated = True
                            # Update or delete point
                            if new_value != None:
                                point["co"]["Y"] = float(new_value)
                                log.info("updating point: co.X = %s to value: %s" % (point["co"]["X"], float(new_value)))
                            else:
                                point_to_delete = point
                            break

                        elif interpolation > -1 and point["co"]["X"] == closest_point_x:
                            # Only update interpolation type
                            found_point = True
                            clip_updated = True
                            point["interpolation"] = interpolation
                            log.info("updating interpolation mode point: co.X = %s to %s" % (point["co"]["X"], interpolation))
                            break

                    # Delete point (if needed)
                    if point_to_delete:
                        clip_updated = True
                        log.info("Found point to delete at X=%s" % point_to_delete["co"]["X"])
                        c.data[property_key]["Points"].remove(point_to_delete)

                    # Create new point (if needed)
                    elif not found_point and new_value != None:
                        clip_updated = True
                        log.info("Created new point at X=%s" % self.frame_number)
                        c.data[property_key]["Points"].append({'co': {'X': self.frame_number, 'Y': new_value}, 'interpolation': 1})

                elif property_type == "int":
                    # Integer
                    clip_updated = True
                    c.data[property_key] = int(new_value)

                elif property_type == "float":
                    # Float
                    clip_updated = True
                    c.data[property_key] = float(new_value)

                elif property_type == "bool":
                    # Boolean
                    clip_updated = True
                    c.data[property_key] = bool(new_value)

                elif property_type == "string":
                    # String
                    clip_updated = True
                    c.data[property_key] = str(new_value)


            # Reduce # of clip properties we are saving (performance boost)
            c.data = {property_key: c.data[property_key]}

            # Save changes
            if clip_updated:
                # Save
                c.save()

                # Update the preview
                get_app().window.preview_thread.refreshFrame()

            # Clear selection
            self.parent.clearSelection()

    def update_model(self, filter=""):
        log.info("updating clip properties model.")
        app = get_app()

        # Check for a selected clip
        if self.selected and self.selected[0]:
            c, item_type = self.selected[0]

            # Get raw unordered JSON properties
            raw_properties = json.loads(c.PropertiesJSON(self.frame_number))
            all_properties = OrderedDict(sorted(raw_properties.items(), key=lambda x: x[1]['name']))

            log.info("Getting properties for frame %s: %s" % (self.frame_number, str(all_properties)))

            # Check if the properties changed for this clip?
            hash = "%s-%s" % (filter, raw_properties["hash"]["memo"])
            if hash != self.previous_hash:
                self.previous_hash = hash

                if self.previous_filter != filter:
                    self.previous_filter = filter
                    self.new_item = True  # filter changed, so we need to regenerate the entire model
            else:
                # Properties don't need to be updated (they haven't changed)
                return

            # Ignore any events from this method
            self.ignore_update_signal = True

            # Clear previous model data (if item is different)
            if self.new_item:
                # Prepare for new properties
                self.items = {}
                self.model.clear()

                log.info("Clear property model: %s" % raw_properties["hash"]["memo"])

                # Add Headers
                self.model.setHorizontalHeaderLabels(["Property", "Value"])


            # Loop through properties, and build a model
            for property in all_properties.items():
                label = property[1]["name"]
                name = property[0]
                value = property[1]["value"]
                type = property[1]["type"]
                memo = property[1]["memo"]
                readonly = property[1]["readonly"]
                keyframe = property[1]["keyframe"]
                points = property[1]["points"]
                interpolation = property[1]["interpolation"]
                closest_point_x = property[1]["closest_point_x"]

                # Hide filtered out properties
                if filter and filter.lower() not in name.lower():
                    continue

                # Insert new data into model, or update existing values
                row = []
                if self.new_item:

                    # Append Property Name
                    col = QStandardItem("Property")
                    col.setText(label)
                    col.setData(property)
                    if keyframe and points > 1:
                        col.setBackground(QColor("green"))  # Highlight keyframe background
                    elif points > 1:
                        col.setBackground(QColor(42, 130, 218))  # Highlight interpolated value background
                    col.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
                    row.append(col)

                    # Append Value
                    col = QStandardItem("Value")
                    col.setText("%0.2f" % value)
                    col.setData((c.Id(), item_type))
                    if points > 1:
                        # Apply icon to cell
                        my_icon = QPixmap(os.path.join(info.IMAGES_PATH, "keyframe-%s.png" % interpolation))
                        col.setData(my_icon, Qt.DecorationRole)

                        log.info(os.path.join(info.IMAGES_PATH, "keyframe-%s.png" % interpolation))

                        # Set the background color of the cell
                        if keyframe:
                            col.setBackground(QColor("green"))  # Highlight keyframe background
                        else:
                            col.setBackground(QColor(42, 130, 218))  # Highlight interpolated value background

                    col.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsUserCheckable | Qt.ItemIsEditable)
                    row.append(col)

                    # Append ROW to MODEL (if does not already exist in model)
                    self.model.appendRow(row)

                else:
                    # Update the value of the existing model
                    # Get 1st Column
                    col = self.items[name]["row"][0]
                    col.setData(property)
                    if keyframe and points > 1:
                        col.setBackground(QColor("green"))  # Highlight keyframe background
                    elif points > 1:
                        col.setBackground(QColor(42, 130, 218))  # Highlight interpolated value background
                    else:
                        col.setBackground(QStandardItem("Empty").background())

                    # Update helper dictionary
                    row.append(col)

                    # Get 2nd Column
                    col = self.items[name]["row"][1]
                    col.setText("%0.2f" % value)

                    if points > 1:
                        # Apply icon to cell
                        my_icon = QPixmap(os.path.join(info.IMAGES_PATH, "keyframe-%s.png" % interpolation))
                        col.setData(my_icon, Qt.DecorationRole)

                        # Set the background color of the cell
                        if keyframe:
                            col.setBackground(QColor("green"))  # Highlight keyframe background
                        else:
                            col.setBackground(QColor(42, 130, 218))  # Highlight interpolated value background
                    else:
                        # clear background color
                        col.setBackground(QStandardItem("Empty").background())

                    # Update helper dictionary
                    row.append(col)

                # Keep track of items in a dictionary (for quick look up)
                self.items[name] = {"row": row, "property": property}

            # Update the values on the next call to this method (instead of adding rows)
            self.new_item = False

        else:
            # Clear previous properties hash
            self.previous_hash = ""

            # Clear previous model data (if any)
            self.model.clear()

            # Add Headers
            self.model.setHorizontalHeaderLabels(["Property", "Value"])


        # Done updating model
        self.ignore_update_signal = False

    def __init__(self, parent, *args):

        # Keep track of the selected items (clips, transitions, etc...)
        self.selected = []
        self.current_item_id = None
        self.frame_number = 1
        self.previous_hash = ""
        self.new_item = True
        self.items = {}
        self.ignore_update_signal = False
        self.parent = parent
        self.previous_filter = None

        # Create standard model
        self.model = ClipStandardItemModel()
        self.model.setColumnCount(2)

        # Connect data changed signal
        self.model.itemChanged.connect(self.value_updated)

        # Add self as listener to project data updates (used to update the timeline)
        get_app().updates.add_listener(self)
