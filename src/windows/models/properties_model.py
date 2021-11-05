"""
 @file
 @brief This file contains the clip properties model, used by the properties view
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
from collections import OrderedDict
from operator import itemgetter

from PyQt5.QtCore import QMimeData, Qt, QLocale, QTimer
from PyQt5.QtGui import (
    QStandardItemModel, QStandardItem,
    QPixmap, QColor,
    )

from classes import info, updates
from classes import openshot_rc  # noqa
from classes.query import Clip, Transition, Effect
from classes.logger import log
from classes.app import get_app
import openshot

import json


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
        if action.key and action.key[0] in ["clips", "effects"] and action.type in ["update", "insert"]:
            log.debug(action.values)
            # Update the model data
            self.update_model(get_app().window.txtPropertyFilter.text())

    # Update the selected item (which drives what properties show up)
    def update_item(self, item_id, item_type):
        # Keep track of id and type
        self.next_item_id = item_id
        self.next_item_type = item_type

        # Update the model data
        self.update_timer.start()

    # Update the next item (once the timer runs out)
    def update_item_timeout(self):
        # Get the next item id, and type
        item_id = self.next_item_id
        item_type = self.next_item_type

        # Clear previous selection
        self.selected = []
        self.filter_base_properties = []

        log.debug("Update item: %s" % item_type)

        timeline = get_app().window.timeline_sync.timeline
        if item_type == "clip":
            c = timeline.GetClip(item_id)
            if c:
                # Append to selected items
                self.selected.append((c, item_type))
        if item_type == "transition":
            t = timeline.GetEffect(item_id)
            if t:
                # Append to selected items
                self.selected.append((t, item_type))
        if item_type == "effect":
            e = timeline.GetClipEffect(item_id)
            if e:
                # Filter out basic properties, since this is an effect on a clip
                self.filter_base_properties = ["position", "layer", "start", "end", "duration"]
                # Append to selected items
                self.selected.append((e, item_type))
                self.selected_parent = e.ParentClip()

        # Update frame # from timeline
        self.update_frame(get_app().window.preview_thread.player.Position(), reload_model=False)

        # Get ID of item
        self.new_item = True

        # Update the model data
        self.update_model(get_app().window.txtPropertyFilter.text())

    # Update the values of the selected clip, based on the current frame
    def update_frame(self, frame_number, reload_model=True):

        # Check for a selected clip
        if self.selected:
            clip, item_type = self.selected[0]

            if not clip:
                # Ignore null clip
                return

            # If effect, we really care about the position of the parent clip
            if item_type == "effect":
                clip = self.selected_parent

            # Get FPS from project
            fps = get_app().project.get("fps")
            fps_float = float(fps["num"]) / float(fps["den"])

            # Requested time
            requested_time = float(frame_number - 1) / fps_float

            # Determine the frame needed for this clip (based on the position on the timeline)
            time_diff = (requested_time - clip.Position()) + clip.Start()
            self.frame_number = round(time_diff * fps_float) + 1

            # Calculate biggest and smallest possible frames
            min_frame_number = round((clip.Start() * fps_float)) + 1
            max_frame_number = round((clip.End() * fps_float)) + 1

            # Adjust frame number if out of range
            if self.frame_number < min_frame_number:
                self.frame_number = min_frame_number
            if self.frame_number > max_frame_number:
                self.frame_number = max_frame_number

            log.debug("Update frame to %s" % self.frame_number)

            # Update the model data
            if reload_model:
                self.update_model(get_app().window.txtPropertyFilter.text())

    def remove_keyframe(self, item):
        """Remove an existing keyframe (if any)"""

        # Determine what was changed
        property = self.model.item(item.row(), 0).data()
        property_type = property[1]["type"]
        closest_point_x = property[1]["closest_point_x"]
        property_type = property[1]["type"]
        property_key = property[0]
        object_id = property[1]["object_id"]
        clip_id, item_type = item.data()

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

        if not c:
            return

        # Create reference
        clip_data = c.data
        if object_id:
            clip_data = c.data.get('objects').get(object_id)

        if property_key in clip_data:  # Update clip attribute
            log_id = "{}/{}".format(clip_id, object_id) if object_id else clip_id
            log.debug("%s: remove %s keyframe. %s", log_id, property_key, clip_data.get(property_key))

            # Determine type of keyframe (normal or color)
            keyframe_list = []
            if property_type == "color":
                keyframe_list = [clip_data[property_key]["red"], clip_data[property_key]["blue"], clip_data[property_key]["green"]]
            else:
                keyframe_list = [clip_data[property_key]]

            # Loop through each keyframe (red, blue, and green)
            for keyframe in keyframe_list:

                # Keyframe
                # Loop through points, find a matching points on this frame
                closest_point = None
                point_to_delete = None
                for point in keyframe["Points"]:
                    if point["co"]["X"] == self.frame_number:
                        # Found point, Update value
                        clip_updated = True
                        point_to_delete = point
                        break
                    if point["co"]["X"] == closest_point_x:
                        closest_point = point

                # If no point found, use closest point x
                if not point_to_delete:
                    point_to_delete = closest_point

                # Delete point (if needed)
                if point_to_delete:
                    clip_updated = True
                    log.debug("Found point to delete at X=%s" % point_to_delete["co"]["X"])
                    keyframe["Points"].remove(point_to_delete)

            # Reduce # of clip properties we are saving (performance boost)
            clip_data = {property_key: clip_data[property_key]}
            if object_id:
                clip_data = {'objects': {object_id: clip_data}}

            # Save changes
            if clip_updated:
                # Save
                c.save()

                # Update the preview
                get_app().window.refreshFrameSignal.emit()

            # Clear selection
            self.parent.clearSelection()

    def color_update(self, item, new_color, interpolation=-1, interpolation_details=[]):
        """Insert/Update a color keyframe for the selected row"""

        # Determine what was changed
        property = self.model.item(item.row(), 0).data()
        property_type = property[1]["type"]
        closest_point_x = property[1]["closest_point_x"]
        previous_point_x = property[1]["previous_point_x"]
        property_key = property[0]
        object_id = property[1]["object_id"]
        clip_id, item_type = item.data()

        if property_type == "color":
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
                # Create reference
                clip_data = c.data
                if object_id:
                    clip_data = c.data.get('objects').get(object_id)

                # Update clip attribute
                if property_key in clip_data:
                    log_id = "{}/{}".format(clip_id, object_id) if object_id else clip_id
                    log.debug("%s: update color property %s. %s", log_id, property_key, clip_data.get(property_key))

                    # Loop through each keyframe (red, blue, and green)
                    for color, new_value in [
                            ("red", new_color.red()),
                            ("blue", new_color.blue()),
                            ("green", new_color.green()),
                            ]:

                        # Keyframe
                        # Loop through points, find a matching points on this frame
                        found_point = False
                        for point in clip_data[property_key][color].get("Points", []):
                            log.debug("looping points: co.X = %s" % point["co"]["X"])
                            if interpolation == -1 and point["co"]["X"] == self.frame_number:
                                # Found point, Update value
                                found_point = True
                                clip_updated = True
                                # Update point
                                point["co"]["Y"] = new_value
                                log.debug(
                                    "updating point: co.X = %d to value: %.3f",
                                    point["co"]["X"], float(new_value))
                                break

                            elif interpolation > -1 and point["co"]["X"] == previous_point_x:
                                # Only update the LEFT side of the curve (i.e. the previous point's right handle)
                                found_point = True
                                clip_updated = True
                                if point.get("interpolation", 2) == 0 and interpolation_details:
                                    point["handle_right"] = point.get("handle_right") or {"Y": 0.0, "X": 0.0}
                                    point["handle_right"]["X"] = interpolation_details[0]
                                    point["handle_right"]["Y"] = interpolation_details[1]

                                    log.debug("updating previous point (right handle): co.X = %d", point["co"]["X"])
                                    log.debug("use interpolation preset: %s", str(interpolation_details))
                                else:
                                    # Remove unused bezier property
                                    point.pop("handle_right", None)

                            elif interpolation > -1 and point["co"]["X"] == closest_point_x:
                                # Only update interpolation type (and the RIGHT side of the curve)
                                found_point = True
                                clip_updated = True
                                point["interpolation"] = interpolation
                                if interpolation == 0 and interpolation_details:
                                    point["handle_left"] = point.get("handle_left") or {"Y": 0.0, "X": 0.0}
                                    point["handle_left"]["X"] = interpolation_details[2]
                                    point["handle_left"]["Y"] = interpolation_details[3]
                                else:
                                    # Remove unused bezier property
                                    point.pop("handle_left", None)

                                log.debug("updating interpolation mode point: co.X = %d to %d",
                                          point["co"]["X"], interpolation)
                                log.debug("use interpolation preset: %s", str(interpolation_details))

                        # Create new point (if needed)
                        if not found_point:
                            clip_updated = True
                            log.debug("Created new point at X=%d", self.frame_number)
                            clip_data[property_key][color].setdefault("Points", []).append({
                                'co': {'X': self.frame_number, 'Y': new_value},
                                'interpolation': 1,
                                })

                # Reduce # of clip properties we are saving (performance boost)
                clip_data = {property_key: clip_data[property_key]}
                if object_id:
                    clip_data = {'objects': {object_id: clip_data}}

                # Save changes
                if clip_updated:
                    # Save
                    c.save()

                    # Update the preview
                    get_app().window.refreshFrameSignal.emit()

                # Clear selection
                self.parent.clearSelection()

    def value_updated(self, item, interpolation=-1, value=None, interpolation_details=[]):
        """ Table cell change event - also handles context menu to update interpolation value """

        if self.ignore_update_signal:
            return

        # Get translation method
        _ = get_app()._tr

        # Determine what was changed
        property = self.model.item(item.row(), 0).data()
        closest_point_x = property[1]["closest_point_x"]
        previous_point_x = property[1]["previous_point_x"]
        property_type = property[1]["type"]
        property_key = property[0]
        object_id = property[1]["object_id"]
        clip_id, item_type = item.data()

        # Get value (if any)
        if item.text():
            # Set and format value based on property type
            if value is not None:
                # Override value
                new_value = value
            elif property_type == "string":
                # Use string value
                new_value = item.text()
            elif property_type == "bool":
                # Use boolean value
                if item.text() == _("False"):
                    new_value = False
                else:
                    new_value = True
            elif property_type == "int":
                # Use int value
                new_value = QLocale().system().toInt(item.text())[0]
            else:
                # Use decimal value
                new_value = QLocale().system().toFloat(item.text())[0]
        else:
            new_value = None

        log.info(
            "%s for %s changed to %s at frame %s with interpolation: %s at closest x: %s",
            property_key, clip_id, new_value, self.frame_number, interpolation, closest_point_x)

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

            # Create reference
            clip_data = c.data
            if object_id:
                clip_data = c.data.get('objects').get(object_id)

            # Update clip attribute
            if property_key in clip_data:
                log_id = "{}/{}".format(clip_id, object_id) if object_id else clip_id
                log.debug("%s: update property %s. %s", log_id, property_key, clip_data.get(property_key))

                # Check the type of property (some are keyframe, and some are not)
                if property_type != "reader" and type(clip_data[property_key]) == dict:
                    # Keyframe
                    # Loop through points, find a matching points on this frame
                    found_point = False
                    point_to_delete = None
                    for point in clip_data[property_key].get('Points', []):
                        log.debug("looping points: co.X = %s" % point["co"]["X"])
                        if interpolation == -1 and point["co"]["X"] == self.frame_number:
                            # Found point, Update value
                            found_point = True
                            clip_updated = True
                            # Update or delete point
                            if new_value is not None:
                                point["co"]["Y"] = float(new_value)
                                log.debug("updating point: co.X = %d to value: %.3f",
                                          point["co"]["X"], float(new_value))
                            else:
                                point_to_delete = point
                            break

                        if interpolation > -1 and point["co"]["X"] == previous_point_x:
                            # Only update the LEFT side of the curve (i.e. the previous point's right handle)
                            found_point = True
                            clip_updated = True
                            if point.get("interpolation", 2) == 0 and interpolation_details:
                                point["handle_right"] = point.get("handle_right") or {"Y": 0.0, "X": 0.0}
                                point["handle_right"]["X"] = interpolation_details[0]
                                point["handle_right"]["Y"] = interpolation_details[1]

                                log.debug("updating previous point (right handle): co.X = %d", point["co"]["X"])
                                log.debug("use interpolation preset: %s", str(interpolation_details))
                            else:
                                # Remove unused bezier property
                                point.pop("handle_right", None)

                        if interpolation > -1 and point["co"]["X"] == closest_point_x:
                            # Only update the RIGHT side of the curve (i.e. the closest point's left handle
                            # and interpolation mode (only the RIGHT SIDE POINT controls the interpolation mode)
                            found_point = True
                            clip_updated = True
                            point["interpolation"] = interpolation
                            if interpolation == 0 and interpolation_details:
                                point["handle_left"] = point.get("handle_left") or {"Y": 0.0, "X": 0.0}
                                point["handle_left"]["X"] = interpolation_details[2]
                                point["handle_left"]["Y"] = interpolation_details[3]
                            else:
                                # Remove unused bezier property
                                point.pop("handle_left", None)

                            log.debug("updating interpolation mode point: co.X = %d to %d",
                                      point["co"]["X"], interpolation)
                            log.debug("use interpolation preset: %s", str(interpolation_details))

                    # Delete point (if needed)
                    if point_to_delete:
                        clip_updated = True
                        log.debug("Found point to delete at X=%s" % point_to_delete["co"]["X"])
                        clip_data[property_key]["Points"].remove(point_to_delete)

                    # Create new point (if needed)
                    elif not found_point and new_value is not None:
                        clip_updated = True
                        log.debug("Created new point at X=%d", self.frame_number)
                        clip_data[property_key].setdefault('Points', []).append({
                            'co': {'X': self.frame_number, 'Y': new_value},
                            'interpolation': 1})

            if not clip_updated:
                # If no keyframe was found, set a basic property
                if property_type == "int":
                    clip_updated = True
                    try:
                        clip_data[property_key] = int(new_value)
                    except Exception as ex:
                        log.warn('Invalid Integer value passed to property', exc_info=1)

                elif property_type == "float":
                    clip_updated = True
                    try:
                        clip_data[property_key] = float(new_value)
                    except Exception as ex:
                        log.warn('Invalid Float value passed to property', exc_info=1)

                elif property_type == "bool":
                    clip_updated = True
                    try:
                        clip_data[property_key] = bool(new_value)
                    except Exception as ex:
                        log.warn('Invalid Boolean value passed to property', exc_info=1)

                elif property_type == "string":
                    clip_updated = True
                    try:
                        clip_data[property_key] = str(new_value)
                    except Exception:
                        log.warn('Invalid String value passed to property', exc_info=1)

                elif property_type in ["font", "caption"]:
                    clip_updated = True
                    try:
                        clip_data[property_key] = str(new_value)
                    except Exception:
                        log.warn('Invalid Font/Caption value passed to property', exc_info=1)

                elif property_type == "reader":
                    # Transition
                    clip_updated = True
                    try:
                        clip_object = openshot.Clip(value)
                        clip_object.Open()
                        clip_data[property_key] = json.loads(clip_object.Reader().Json())
                        clip_object.Close()
                        clip_object = None
                    except Exception:
                        log.warn('Invalid Reader value passed to property: %s (%s)', value, exc_info=1)

            # Reduce # of clip properties we are saving (performance boost)
            clip_data = {property_key: clip_data.get(property_key)}
            if object_id:
                clip_data = {'objects': {object_id: clip_data}}

            # Save changes
            if clip_updated:
                # Save
                c.save()

                # Update the preview
                get_app().window.refreshFrameSignal.emit()

                log.info("Item %s: changed %s to %s at frame %s (x: %s)" % (clip_id, property_key, new_value, self.frame_number, closest_point_x))

            # Clear selection
            self.parent.clearSelection()

    def set_property(self, property, filter, c, item_type, object_id=None):
        app = get_app()
        _ = app._tr
        label = property[1]["name"]
        name = property[0]
        value = property[1]["value"]
        type = property[1]["type"]
        memo = property[1]["memo"]
        readonly = property[1]["readonly"]
        keyframe = property[1]["keyframe"]
        points = property[1]["points"]
        interpolation = property[1]["interpolation"]
        choices = property[1]["choices"]
        # Add object id reference to QStandardItem
        property[1]["object_id"] = object_id

        # Adding Transparency to translation file
        transparency_label = _("Transparency")  # noqa

        selected_choice = None
        if choices:
            selected_choice = [c for c in choices if c["selected"] is True][0]["name"]

        # Hide filtered out properties
        if filter and filter.lower() not in _(label).lower():
            return

        # Hide unused base properties (if any)
        if name in self.filter_base_properties:
            return

        # Insert new data into model, or update existing values
        row = []
        if self.new_item:

            # Append Property Name
            col = QStandardItem("Property")
            col.setText(_(label))
            col.setData(property)
            if keyframe and points > 1:
                col.setBackground(QColor("green"))  # Highlight keyframe background
            elif points > 1:
                col.setBackground(QColor(42, 130, 218))  # Highlight interpolated value background
            if readonly or type in ["color", "font", "caption"] or choices or label == "Track":
                col.setFlags(Qt.ItemIsEnabled)
            else:
                col.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
            row.append(col)

            # Append Value
            col = QStandardItem("Value")
            if selected_choice:
                col.setText(_(selected_choice))
            elif type == "string":
                # Use string value
                col.setText(memo)
            elif type == "font":
                # Use font value
                col.setText(memo)
            elif type == "caption":
                # Use caption value
                col.setText(memo)
                # Load caption editor also
                get_app().window.CaptionTextLoaded.emit(memo, row)
            elif type == "bool":
                # Use boolean value
                if value:
                    col.setText(_("True"))
                else:
                    col.setText(_("False"))
            elif type == "color":
                # Don't output a value for colors
                col.setText("")
            elif type == "reader":
                reader_json = json.loads(memo or "{}")
                reader_path = reader_json.get("path", "/")
                fileName = os.path.basename(reader_path)
                col.setText(fileName)
            elif type == "int" and label == "Track":
                # Find track display name
                all_tracks = get_app().project.get("layers")
                display_count = len(all_tracks)
                display_label = None
                for track in reversed(sorted(all_tracks, key=itemgetter('number'))):
                    if track.get("number") == value:
                        display_label = track.get("label")
                        break
                    display_count -= 1
                track_name = display_label or _("Track %s") % display_count
                col.setText(track_name)

            elif type == "int":
                col.setText("%d" % value)
            else:
                # Use numeric value
                col.setText(QLocale().system().toString(float(value), "f", precision=2))
            col.setData((c.Id(), item_type))
            if points > 1:
                # Apply icon to cell
                my_icon = QPixmap(":/curves/keyframe-%s.png" % interpolation)
                col.setData(my_icon, Qt.DecorationRole)

                # Set the background color of the cell
                if keyframe:
                    col.setBackground(QColor("green"))  # Highlight keyframe background
                else:
                    col.setBackground(QColor(42, 130, 218))  # Highlight interpolated value background

            if type == "color":
                # Color needs to be handled special
                red = int(property[1]["red"]["value"])
                green = int(property[1]["green"]["value"])
                blue = int(property[1]["blue"]["value"])
                col.setBackground(QColor(red, green, blue))

            if readonly or type in ["color", "font", "caption"] or choices or label == "Track":
                col.setFlags(Qt.ItemIsEnabled)
            else:
                col.setFlags(
                    Qt.ItemIsSelectable
                    | Qt.ItemIsEnabled
                    | Qt.ItemIsUserCheckable
                    | Qt.ItemIsEditable)
            row.append(col)

            # Append ROW to MODEL (if does not already exist in model)
            self.model.appendRow(row)

        else:
            # Update the value of the existing model
            # Get 1st Column
            col = self.items[name]["row"][0]
            col.setData(property)

            # For non-color types, update the background color
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
            if selected_choice:
                col.setText(_(selected_choice))
            elif type == "string":
                # Use string value
                col.setText(memo)
            elif type == "font":
                # Use font value
                col.setText(memo)
            elif type == "caption":
                # Use caption value
                col.setText(memo)
            elif type == "bool":
                # Use boolean value
                if value:
                    col.setText(_("True"))
                else:
                    col.setText(_("False"))
            elif type == "color":
                # Don't output a value for colors
                col.setText("")
            elif type == "int" and label == "Track":
                # Find track display name
                all_tracks = get_app().project.get("layers")
                display_count = len(all_tracks)
                display_label = None
                for track in reversed(sorted(all_tracks, key=itemgetter('number'))):
                    if track.get("number") == value:
                        display_label = track.get("label")
                        break
                    display_count -= 1
                track_name = display_label or _("Track %s") % display_count
                col.setText(track_name)
            elif type == "int":
                col.setText("%d" % value)
            elif type == "reader":
                reader_json = json.loads(property[1].get("memo", "{}"))
                reader_path = reader_json.get("path", "/")
                fileName = os.path.basename(reader_path)
                col.setText("%s" % fileName)
            else:
                # Use numeric value
                col.setText(QLocale().system().toString(float(value), "f", precision=2))

            if points > 1:
                # Apply icon to cell
                my_icon = QPixmap(":/curves/keyframe-%s.png" % interpolation)
                col.setData(my_icon, Qt.DecorationRole)

                # Set the background color of the cell
                if keyframe:
                    col.setBackground(QColor("green"))  # Highlight keyframe background
                else:
                    col.setBackground(QColor(42, 130, 218))  # Highlight interpolated value background

            else:
                # clear background color
                col.setBackground(QStandardItem("Empty").background())

                # clear icon
                my_icon = QPixmap()
                col.setData(my_icon, Qt.DecorationRole)

            if type == "color":
                # Update the color based on the color curves
                red = int(property[1]["red"]["value"])
                green = int(property[1]["green"]["value"])
                blue = int(property[1]["blue"]["value"])
                col.setBackground(QColor(red, green, blue))

            # Update helper dictionary
            row.append(col)

        # Keep track of items in a dictionary (for quick look up)
        self.items[name] = {"row": row, "property": property}

    def update_model(self, filter=""):
        log.debug("updating clip properties model.")
        app = get_app()
        _ = app._tr

        # Check for a selected clip
        if self.selected and self.selected[0]:
            c, item_type = self.selected[0]

            # Skip blank clips
            # TODO: Determine why c is occasional = None
            if not c:
                return

            # Get raw unordered JSON properties
            raw_properties = json.loads(c.PropertiesJSON(self.frame_number))
            objects_raw_properties = raw_properties.pop('objects', None)

            all_properties = OrderedDict(sorted(raw_properties.items(), key=lambda x: x[1]['name']))

            # Check if filter was changed (if so, wipe previous model data)
            if self.previous_filter != filter:
                self.previous_filter = filter
                self.new_item = True  # filter changed, so we need to regenerate the entire model

            # Ignore any events from this method
            self.ignore_update_signal = True

            # Clear previous model data (if item is different)
            if self.new_item:
                # Prepare for new properties
                self.items = {}
                self.model.clear()

                # Add Headers
                self.model.setHorizontalHeaderLabels([_("Property"), _("Value")])

                # Clear caption editor
                get_app().window.CaptionTextLoaded.emit("", None)

            # Loop through properties, and build a model
            for property in all_properties.items():
                self.set_property(property, filter, c, item_type)

            # Insert objects properties from custom effects
            if objects_raw_properties:
                for obj_id in objects_raw_properties:
                    objects_all_properties = OrderedDict(sorted(objects_raw_properties[obj_id].items(), key=lambda x: x[1]['name']))
                    for property in objects_all_properties.items():
                        self.set_property(property, filter, c, item_type, object_id=obj_id)

            # Update the values on the next call to this method (instead of adding rows)
            self.new_item = False

        else:
            # Clear previous properties hash
            self.previous_hash = ""

            # Clear previous model data (if any)
            self.model.clear()

            # Add Headers
            self.model.setHorizontalHeaderLabels([_("Property"), _("Value")])

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
        self.filter_base_properties = []

        # Create standard model
        self.model = ClipStandardItemModel()
        self.model.setColumnCount(2)

        # Timer to use a delay before showing properties (to prevent a mass selection from trying
        # to update the property model hundreds of times)
        self.update_timer = QTimer(parent)
        self.update_timer.setInterval(100)
        self.update_timer.setSingleShot(True)
        self.update_timer.timeout.connect(self.update_item_timeout)
        self.next_item_id = None
        self.next_item_type = None

        # Connect data changed signal
        self.model.itemChanged.connect(self.value_updated)

        # Add self as listener to project data updates (used to update the timeline)
        get_app().updates.add_listener(self)
