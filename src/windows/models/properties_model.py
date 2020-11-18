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

from PyQt5.QtCore import Qt, pyqtSlot, QObject, QLocale, QTimer, QMimeData
from PyQt5.QtGui import (
    QStandardItemModel, QStandardItem,
    QPixmap, QColor,
    )

from classes import updates
from classes import openshot_rc  # noqa
from classes.query import QueryObject, Clip, Transition, Effect
from classes.logger import log
from classes.app import get_app
import openshot

import json


class ClipStandardItemModel(QStandardItemModel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("properties.ClipStandardItemModel")

    def mimeData(self, indexes):
        # Create MimeData for drag operation
        data = QMimeData(self)
        data.setObjectName("properties.mimeData")

        # Get list of all selected file ids
        property_names = []
        for item in indexes:
            selected_row = self.itemFromIndex(item).row()
            property_names.append(self.item(selected_row, 0).data())
        data.setText(json.dumps(property_names))

        # Return Mimedata
        return data


class PropertiesModel(updates.UpdateInterface, QObject):
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

        log.debug("Update %s item %s", item_type, item_id)

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
            global_time = float(frame_number - 1) / fps_float

            # Map to clip time (constrained within [Start:End])
            clip_time = max(clip.Start(),
                            min(clip.End(),
                                (global_time - clip.Position())
                                + clip.Start()
                                ))
            clip_frame = round(clip_time * fps_float) + 1

            if clip_frame != self.frame_number:
                self.frame_number = clip_frame
                log.info("Update frame to %s" % self.frame_number)

            # Update the model data
            if reload_model:
                self.update_model(get_app().window.txtPropertyFilter.text())

    @staticmethod
    def get_query_object(q_id: str, q_type: str) -> QueryObject:
        """Find the query object for a timeline item, by ID"""
        if q_type == "clip":
            return Clip.get(id=q_id)
        if q_type == "transition":
            return Transition.get(id=q_id)
        if q_type == "effect":
            return Effect.get(id=q_id)
        return None

    @staticmethod
    def make_dataref(c, obj) -> dict:
        try:
            if obj:
                return c.data.get('objects', {}).get(object_id)
            else:
                return c.data
        except Exception:
            log.error("Couldn't interpret query object", exc_info=1)

    @staticmethod
    def optimize_data(c, prop_key, prop_data, obj=None):
        """Reduce a query object to just the updated part"""
        try:
            if obj:
                c.data = {'objects': {obj: {prop_key: prop_data}}}
            else:
                c.data = {prop_key: prop_data}
        except Exception:
            log.error("Failed to update query object", exc_info=1)

    @staticmethod
    def interpret_as_type(prop_type: str, prop_value):
        try:
            if prop_type == "int":
                return int(prop_value)
            if prop_type == "float":
                return float(prop_value)
            if prop_type == "bool":
                return bool(prop_value)
            if prop_type in ["string", "font", "caption"]:
                return str(prop_value)
            if prop_type == "color":
                return {
                    "red": prop_value.red(),
                    "green": prop_value.green(),
                    "blue": prop_value.blue(),
                }
            if prop_type == "reader":
                clip_object = openshot.Clip(prop_value)
                clip_object.Open()
                reader_json = json.loads(clip_object.Reader().Json())
                clip_object.Close()
                del clip_object
                return reader_json
        except Exception as ex:
            log.warn(
                'Invalid %s value %s passed to property: %s',
                prop_type, prop_value, ex)
            return None

    def update_value(self, item, value):
        """Insert/Update a keyframe point for the selected row"""
        # Determine what was changed
        prop_key, prop_data = self.model.item(item.row(), 0).data()
        prop_type = prop_data.get("type")
        item_id, item_type = item.data()
        object_id = prop_data.get("object_id")
        c = PropertiesModel.get_query_object(item_id, item_type)
        d = PropertiesModel.make_dataref(c, object_id)
        # Convert the new value to the correct type for this property
        new_value = PropertiesModel.interpret_as_type(prop_type, value)
        # Sanity checks
        if new_value is None or not c or prop_key not in d:
            log.error(
                "%s %s: can't update %s property %s to %s",
                item_type, item_id, prop_type, prop_key, str(value))
            return
        # Are we updating a value with keyframes?
        if (prop_type != "reader"
           and isinstance(d[prop_key], dict)):
            if prop_type == "color":
                # Colors have three keyframe lists
                points_to_update = [
                   (d[prop_key].get(color, {}).get("Points", []), color_value)
                   for color, color_value in new_value.items()
                   ]
            else:
                points_to_update = [(d[prop_key].get("Points", []), new_value)]
            # Will return True if any call produces True, else False
            updated = any([
                PropertiesModel.set_point(
                    points, self.frame_number, point_value)
                for points, point_value in points_to_update
                ])
            if not updated:
                return
        else:
            # No keyframes, just set value directly (if changed)
            if d[prop_key] == new_value:
                return
            d[prop_key] = new_value
            obj_log = f" for object {object_id}" if object_id else ""
            log.debug(
                "%s %s: set %s property%s %s to %s",
                item_type, item_id,
                obj_log,
                prop_type, prop_key,
                str(value),
                )
        # Reduce # of clip properties we are saving (performance boost)
        PropertiesModel.optimize_data(c, prop_key, d[prop_key], object_id)
        c.save()
        # Update the preview
        get_app().window.refreshFrameSignal.emit()
        self.parent().clearSelection()

    @staticmethod
    def set_point(points: list, x_pos: int, value: float) -> bool:
        """Set a keyframe value in list 'points'"""
        # Sanity check
        if len(points) < 1 or "co" not in points[0]:
            log.warning("Cannot interpret points list!")
            return False
        for point in sorted(points, key=lambda p: p["co"]["X"]):
            log.debug("looping points: co.X = %d", point["co"]["X"])
            if point["co"]["X"] < x_pos:
                continue
            if point["co"]["X"] == x_pos:
                # Found point, Update value if changed
                if point["co"]["Y"] == value:
                    return False
                log.debug(
                    "updating point: co.X = %d to value: %.3f",
                    point["co"]["X"], value)
                point["co"]["Y"] = value
                return True
            if point["co"]["X"] > x_pos:
                # We passed the point, stop looking
                break
        # If we haven't returned, no such point
        log.debug(
            "Adding new point at co.X = %d, value %0.3f",
            x_pos, value)
        points.append({
            'co': {'X': x_pos, 'Y': value},
            'interpolation': 1,
            })
        points.sort(key=lambda p: p["co"]["X"])
        return True

    def update_interpolation(self, item, interpolation=-1, handles=[0, 0, 0, 0]):
        """Change the interpolation type of the current curve segment"""
        # Determine what will be changed
        prop_key, prop_data = self.model.item(item.row(), 0).data()
        item_id, item_type = item.data()
        object_id = prop_data.get("object_id")
        c = PropertiesModel.get_query_object(item_id, item_type)
        d = PropertiesModel.make_dataref(c, object_id)
        # Sanity checks
        if not c or prop_key not in d:
            log.error(
                "Can't find property %s for %s %s",
                prop_key, item_type, item_id)
            # Can't find correct values to update
            return
        if item_type == "color":
            # Colors have three keyframe lists
            points_to_update = [
                d[prop_key].get(color, {}).get("Points", [])
                for color in ["red", "green", "blue"]
                ]
        else:
            points_to_update = [d[prop_key].get("Points", [])]
        # Will return True if any call produces True, else False
        updated = any([
            PropertiesModel.set_interpolation(
                points,
                prop_data.get("previous_point_x"),
                prop_data.get("closest_point_x"),
                interpolation,
                handles,
            ) for points in points_to_update])
        if not updated:
            return
        # Reduce # of clip properties we are saving (performance boost)
        PropertiesModel.optimize_data(c, prop_key, d[prop_key], object_id)
        c.save()
        # Update the preview
        get_app().window.refreshFrameSignal.emit()
        self.parent().clearSelection()

    @staticmethod
    def set_interpolation(points: list, prev_x: float, closest_x: float, interp: int, handles: list):
        """Set the interpolation between two keyframe points"""
        if len(points) < 1 or "co" not in points[0]:
            log.warning("Cannot interpret points list!")
            return False
        if prev_x == closest_x:
            log.warning(
                "Can't set interpolation: Both endpoints at co.X = %d, segment too short",
                closest_x)
            return False
        for point in sorted(points, key=lambda p: p["co"]["X"]):
            log.debug("Searching for segment endpoints, co.X = %s", point["co"]["X"])
            if point["co"]["X"] < prev_x:
                continue
            if point["co"]["X"] == prev_x and interp == openshot.BEZIER:
                log.debug(
                    "Setting co.X = %s handle_right(X, Y): %s",
                    point["co"]["X"], str(handles[0:2]))
                point.update({
                    "handle_right": {"X": handles[0], "Y": handles[1]},
                    })
                continue
            if point["co"]["X"] == closest_x:
                log.debug(
                    "Setting co.X = %s interpolation %s",
                    point["co"]["X"], interp)
                point.update({"interpolation": interp})
                if interp == openshot.BEZIER:
                    log.debug(
                        "Setting co.X = %s handle_left(X, Y): %s",
                        point["co"]["X"], str(handles[2:4]))
                    point.update({
                        "handle_left": {"X": handles[2], "Y": handles[3]},
                    })
                break
            if point["co"]["X"] > closest_x:
                log.warning(
                    "Could not find curve endpoint %s", closest_x)
                return False
        return True

    def remove_keyframe(self, item):
        """Remove an existing keyframe point (if any)"""
        # Determine what will be changed
        prop_key, prop_data = self.model.item(item.row(), 0).data()
        prop_type = prop_data.get("type")
        closest_x = prop_data.get("closest_point_x")
        object_id = prop_data.get("object_id", None)
        item_id, item_type = item.data()
        c = PropertiesModel.get_query_object(item_id, item_type)
        d = PropertiesModel.make_dataref(c, object_id)

        # Sanity checks
        if not c or prop_key not in d:
            log.error(
                "%s %s: can't find %s property %s",
                item_type, item_id, prop_type, prop_key)
            return
        log.debug(
            "%s %s: Removing point %d",
            item_type, item_id, closest_x)
        if prop_type == "color":
            # Colors have three keyframe lists
            points_to_remove = [
                d[prop_key].get(color, {}).get("Points", [])
                for color in ["red", "green", "blue"]
                ]
        else:
            points_to_remove = [d[prop_key].get("Points", [])]
        for points in points_to_remove:
            for point in sorted(points, key=lambda p: p["co"]["X"]):
                if point["co"]["X"] == closest_x:
                    points.remove(point)
                    break
            else:
                log.warning("Can't find point to remove at %d", closest_x)
                return
        # Reduce # of clip properties we are saving (performance boost)
        PropertiesModel.optimize_data(c, prop_key, d[prop_key], object_id)
        c.save()
        # Update the preview
        get_app().window.refreshFrameSignal.emit()
        self.parent().clearSelection()

    @pyqtSlot('QStandardItem*')
    def item_changed(self, item: QStandardItem):
        """Handle itemChanged signals from underlying model"""
        if self.ignore_update_signal:
            return
        new_value = item.data(Qt.EditRole)
        log.debug("item value changed to %s", new_value)
        self.update_value(item, new_value)

    def set_property(self, prop, filt, c, item_type, object_id=None):
        app = get_app()
        _ = app._tr
        name = prop[0]
        prop_data = prop[1]
        label = prop_data["name"]
        value = prop_data["value"]
        prop_type = prop_data["type"]
        memo = prop_data["memo"]
        readonly = prop_data["readonly"]
        keyframe = prop_data["keyframe"]
        points = prop_data["points"]
        interpolation = prop_data["interpolation"]
        choices = prop_data["choices"]
        # Add object id reference to QStandardItem
        prop_data["object_id"] = object_id

        # Adding Transparency to translation file
        transparency_label = _("Transparency")  # noqa

        selected_choice = None
        if choices:
            selected_choice = [c for c in choices if c["selected"] is True][0]["name"]

        # Hide filtered out properties
        if filt and filt.lower() not in _(label).lower():
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
            col.setData(prop)
            if keyframe and points > 1:
                col.setBackground(QColor("green"))  # Highlight keyframe background
            elif points > 1:
                col.setBackground(QColor(42, 130, 218))  # Highlight interpolated value background
            if readonly or prop_type in ["color", "font", "caption"] or choices or label == "Track":
                col.setFlags(Qt.ItemIsEnabled)
            else:
                col.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
            row.append(col)

            # Append Value
            col = QStandardItem("Value")
            if selected_choice:
                col.setText(_(selected_choice))
            elif prop_type == "string":
                # Use string value
                col.setText(memo)
            elif prop_type == "font":
                # Use font value
                col.setText(memo)
            elif prop_type == "caption":
                # Use caption value
                col.setText(memo)
                # Load caption editor also
                get_app().window.CaptionTextLoaded.emit(memo, row)
            elif prop_type == "bool":
                # Use boolean value
                if value:
                    col.setText(_("True"))
                else:
                    col.setText(_("False"))
            elif prop_type == "color":
                # Don't output a value for colors
                col.setText("")
            elif type == "reader":
                reader_json = json.loads(memo or "{}")
                reader_path = reader_json.get("path", "/")
                fileName = os.path.basename(reader_path)
                col.setText(fileName)
            elif prop_type == "int" and label == "Track":
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

            elif prop_type == "int":
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

            if prop_type == "color":
                # Color needs to be handled special
                red = prop_data["red"]["value"]
                green = prop_data["green"]["value"]
                blue = prop_data["blue"]["value"]
                col.setBackground(QColor(red, green, blue))

            if readonly or prop_type in ["color", "font", "caption"] or choices or label == "Track":
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
            col.setData(prop)

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
            elif prop_type == "string":
                # Use string value
                col.setText(memo)
            elif prop_type == "font":
                # Use font value
                col.setText(memo)
            elif prop_type == "caption":
                # Use caption value
                col.setText(memo)
            elif prop_type == "bool":
                # Use boolean value
                if value:
                    col.setText(_("True"))
                else:
                    col.setText(_("False"))
            elif prop_type == "color":
                # Don't output a value for colors
                col.setText("")
            elif prop_type == "int" and label == "Track":
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
            elif prop_type == "int":
                col.setText("%d" % value)
            elif prop_type == "reader":
                reader_json = json.loads(prop_data.get("memo", "{}"))
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

            if prop_type == "color":
                # Update the color based on the color curves
                red = prop_data["red"]["value"]
                green = prop_data["green"]["value"]
                blue = prop_data["blue"]["value"]
                col.setBackground(QColor(red, green, blue))

            # Update helper dictionary
            row.append(col)

        # Keep track of items in a dictionary (for quick look up)
        self.items[name] = {"row": row, "property": prop}

    def update_model(self, filt=""):
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
            if self.previous_filter != filt:
                self.previous_filter = filt
                self.new_item = True

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
            for prop in all_properties.items():
                self.set_property(prop, filt, c, item_type)

            # Insert objects properties from custom effects
            if objects_raw_properties:
                for obj_id in objects_raw_properties:
                    objects_all_properties = OrderedDict(sorted(objects_raw_properties[obj_id].items(), key=lambda x: x[1]['name']))
                    for prop in objects_all_properties.items():
                        self.set_property(prop, filt, c, item_type, object_id=obj_id)

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

    def __init__(self, parent=None, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)

        # Keep track of the selected items (clips, transitions, etc...)
        self.selected = []
        self.current_item_id = None
        self.frame_number = 1
        self.previous_hash = ""
        self.new_item = True
        self.items = {}
        self.ignore_update_signal = False
        self.previous_filter = None
        self.filter_base_properties = []

        # Create standard model
        self.model = ClipStandardItemModel(self)
        self.model.setColumnCount(2)

        # Timer to use a delay before showing properties (to prevent a mass selection from trying
        # to update the property model hundreds of times)
        self.update_timer = QTimer(self)
        self.update_timer.setObjectName("properties.update_timer")
        self.update_timer.setInterval(100)
        self.update_timer.setSingleShot(True)
        self.update_timer.timeout.connect(self.update_item_timeout)
        self.next_item_id = None
        self.next_item_type = None

        # Connect data changed signal for underlying model
        self.model.itemChanged.connect(self.item_changed)

        # Add self as listener to project data updates (used to update the timeline)
        get_app().updates.add_listener(self)
