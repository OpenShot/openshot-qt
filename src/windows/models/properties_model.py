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

from classes.waveform import get_audio_data
from classes import info, updates
from classes import openshot_rc  # noqa
from classes.clip_utils import clamp_timing_to_media, clip_time_bounds
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
        if action and len(action.key) >= 1 and action.key[0] in ["clips", "effects"] and action.type in ["update", "insert"]:
            log.debug(action.values)
            # Update the model data
            self.update_model(get_app().window.txtPropertyFilter.text())

    # Update the selected item (which drives what properties show up)
    def update_item(self, selection):
        """Update selected items list"""
        self.next_selection = selection

        if not selection and self.selected:
            self.update_item_timeout()
        else:
            self.update_timer.start()

    # Update the next item (once the timer runs out)
    def update_item_timeout(self):
        # Get the next item id, and type
        selection = self.next_selection or []

        # Clear previous selection
        self.selected = []
        self.filter_base_properties = []

        if selection:
            timeline = get_app().window.timeline_sync.timeline
            for sel in selection:
                item_id = sel.get("id")
                item_type = sel.get("type")
                if item_type == "clip":
                    c = timeline.GetClip(item_id)
                    if c:
                        self.selected.append((c, item_type))
                elif item_type == "transition":
                    t = timeline.GetEffect(item_id)
                    if t:
                        self.selected.append((t, item_type))
                elif item_type == "effect":
                    e = timeline.GetClipEffect(item_id)
                    if e:
                        self.filter_base_properties = ["position", "layer", "start", "end", "duration"]
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
            new_frame_number = round(time_diff * fps_float) + 1
            if new_frame_number != self.frame_number:
                # If frame # has changed
                self.frame_number = new_frame_number

                # Calculate biggest and smallest possible frames
                min_frame_number = round((clip.Start() * fps_float)) + 1
                max_frame_number = round((clip.End() * fps_float))

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
        item_data = item.data()

        for item_id, item_type in item_data:
            # Find this clip
            c = None
            clip_updated = False

            if item_type == "clip":
                # Get clip object
                c = Clip.get(id=item_id)
            elif item_type == "transition":
                # Get transition object
                c = Transition.get(id=item_id)
            elif item_type == "effect":
                # Get effect object
                c = Effect.get(id=item_id)

            if not c:
                return

            # Create reference
            clip_data = c.data
            if object_id:
                objects = c.data.get('objects', {})
                clip_data = objects.pop(object_id, {})
                if not clip_data:
                    log.debug("No clip data found for this object id")
                    return

            if property_key in clip_data:  # Update clip attribute
                log_id = "{}/{}".format(item_id, object_id) if object_id else item_id
                log.debug("%s: remove %s keyframe. %s", log_id, property_key, clip_data.get(property_key))

                # Determine type of keyframe (normal or color)
                keyframe_list = []
                if property_type == "color":
                    keyframe_list = [clip_data[property_key]["red"], clip_data[property_key]["blue"], clip_data[property_key]["green"]]
                else:
                    keyframe_list = [clip_data[property_key]]

                # Loop through each keyframe (red, blue, and green)
                for keyframe_index, keyframe in enumerate(keyframe_list):
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

                        # Check for 0 keyframes (and use sane defaults instead of the 0.0 default value)
                        default_value = None
                        if not keyframe["Points"]:
                            if property_key in ["alpha", "scale_x", "scale_y", "time", "volume"]:
                                default_value = 1.0
                            elif property_key in ["origin_x", "origin_y"]:
                                default_value = 0.5
                            elif property_key in ["location_x", "location_y", "rotation", "shear_x", "shear_y"]:
                                default_value = 0.0
                            elif property_key in ["has_audio", "has_video", "channel_filter", "channel_mapping"]:
                                default_value = -1.0
                            elif property_key in ["wave_color"]:
                                if keyframe_index == 0:
                                    # Red
                                    default_value = 0.0
                                elif keyframe_index == 1:
                                    # Blue
                                    default_value = 255.0
                                elif keyframe_index == 2:
                                    # Green
                                    default_value = 123.0
                            if default_value is not None:
                                keyframe["Points"].append({
                                    'co': {'X': self.frame_number, 'Y': default_value},
                                    'interpolation': 1})

                # Enforce clip timing constraints
                if property_key in ("time", "start", "end", "duration"):
                    clamp_timing_to_media(clip_data, c)

                # Determine if waveforms are impacted by this change
                has_waveform = False
                waveform_file_id = None
                if property_key == "volume":
                    if clip_data.get("ui", {}).get("audio_data", []):
                        waveform_file_id = c.data.get("file_id")
                        has_waveform = True

                # Reduce # of clip properties we are saving (performance boost)
                if not object_id:
                    if property_key == "time":
                        clip_data = {k: clip_data.get(k) for k in ("time", "end", "duration", "start")}
                    else:
                        clip_data = {property_key: clip_data.get(property_key)}
                else:
                    # If objects dict detected - don't reduce the # of objects
                    objects[object_id] = clip_data
                    clip_data = {'objects': objects}

                # Save changes
                if clip_updated:
                    # Save
                    c.data = clip_data
                    c.save()

                    # Update waveforms (if needed)
                    if has_waveform:
                        get_audio_data({waveform_file_id: [c.id]})

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
        item_data = item.data()

        for item_id, item_type in item_data:
            if property_type == "color":
                # Find this clip
                c = None
                clip_updated = False

                if item_type == "clip":
                    # Get clip object
                    c = Clip.get(id=item_id)
                elif item_type == "transition":
                    # Get transition object
                    c = Transition.get(id=item_id)
                elif item_type == "effect":
                    # Get effect object
                    c = Effect.get(id=item_id)

                if c:
                    # Create reference
                    clip_data = c.data
                    if object_id:
                        objects = c.data.get('objects', {})
                        clip_data = objects.pop(object_id, {})
                        if not clip_data:
                            log.debug("No clip data found for this object id")
                            return

                    # Update clip attribute
                    if property_key in clip_data:
                        log_id = "{}/{}".format(item_id, object_id) if object_id else item_id
                        log.debug("%s: update color property %s. %s", log_id, property_key, clip_data.get(property_key))

                        # Loop through each keyframe (red, blue, green, and alpha)
                        for color, new_value in [
                                ("red", new_color.red()),
                                ("blue", new_color.blue()),
                                ("green", new_color.green()),
                                ("alpha", new_color.alpha()),
                                ]:

                            # Keyframe
                            # Make sure this color property exists in the clip data
                            if color not in clip_data[property_key]:
                                log.debug(f"Creating new color component: {color}")
                                clip_data[property_key][color] = {"Points": []}

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
                    if not object_id:
                        clip_data = {property_key: clip_data.get(property_key)}
                    else:
                        # If objects dict detected - don't reduce the # of objects
                        objects[object_id] = clip_data
                        clip_data = {'objects': objects}

                    # Save changes
                    if clip_updated:
                        # Save
                        c.data = clip_data
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
        objects = {}
        item_data = item.data()

        # Get value (if any)
        if item.text() or value:
            # Set and format value based on property type
            if value == "None":
                new_value = ""
            elif value is not None:
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

        for item_id, item_type in item_data:
            log.info(
                "%s for %s changed to %s at frame %s with interpolation: %s at closest x: %s",
                property_key, item_id, new_value, self.frame_number, interpolation, closest_point_x)

            # Start each iteration with the original value
            value = new_value

            # Find this clip
            c = None
            clip_updated = False

            if item_type == "clip":
                # Get clip object
                c = Clip.get(id=item_id)
            elif item_type == "transition":
                # Get transition object
                c = Transition.get(id=item_id)
            elif item_type == "effect":
                # Get effect object
                c = Effect.get(id=item_id)

            if c and c.data:

                # Create reference
                clip_data = c.data
                if object_id:
                    objects = c.data.get('objects', {})
                    clip_data = objects.pop(object_id, {})
                    if not clip_data:
                        log.debug("No clip data found for this object id")
                        return

                # Update clip attribute
                if property_key in clip_data:
                    log_id = "{}/{}".format(item_id, object_id) if object_id else item_id
                    log.debug("%s: update property %s. %s", log_id, property_key, clip_data.get(property_key))

                    # Check the type of property (some are keyframe, and some are not)
                    if property_type != "reader" and isinstance(clip_data[property_key], dict):
                        # Keyframe

                        # Protection from HUGE scale values
                        if property_key in ['scale_x', 'scale_y', 'shear_x', 'shear_y'] and value:
                            width = get_app().project.get("width")
                            height = get_app().project.get("height")
                            is_svg = clip_data.get("reader", {}).get("path", "").lower().endswith("svg")
                            if is_svg:
                                max_multiple = 15
                            else:
                                max_multiple = 50
                            if width > 0 and height > 0:
                                # Clamp the max scale based on project size
                                max_multiple = round((2000 * max_multiple) / max(width, height))

                            # Apply the calculated max_multiple to value
                            value = max(min(value, max_multiple), -max_multiple)

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
                                if value is not None:
                                    point["co"]["Y"] = int(value) if property_key == "time" else float(value)
                                    log.debug("updating point: co.X = %d to value: %s",
                                              point["co"]["X"], value)
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
                        elif not found_point and value is not None:
                            clip_updated = True
                            log.debug("Created new point at X=%d", self.frame_number)
                            clip_data[property_key].setdefault('Points', []).append({
                                'co': {'X': self.frame_number, 'Y': int(value) if property_key == "time" else value},
                                'interpolation': 1})

                if not clip_updated:
                    # If no keyframe was found, set a basic property
                    if property_type == "int":
                        clip_updated = True
                        try:
                            clip_data[property_key] = int(value)
                        except Exception:
                            log.warn('Invalid Integer value passed to property', exc_info=1)

                    elif property_type == "float":
                        clip_updated = True
                        try:
                            clip_data[property_key] = float(value)

                            # Fix precision issues with time properties by snapping to FPS grid
                            if property_key in ['position', 'start', 'end']:
                                fps_num = get_app().project.get("fps").get("num")
                                fps_den = get_app().project.get("fps").get("den")
                                frame_duration = fps_den / fps_num

                                # Snap the value to the nearest frame
                                clip_data[property_key] = round(clip_data[property_key] / frame_duration) * frame_duration

                        except Exception:
                            log.warn('Invalid Float value passed to property', exc_info=1)

                    elif property_type == "bool":
                        clip_updated = True
                        try:
                            clip_data[property_key] = bool(value)
                        except Exception:
                            log.warn('Invalid Boolean value passed to property', exc_info=1)

                    elif property_type == "string":
                        clip_updated = True
                        try:
                            clip_data[property_key] = str(value or "")
                        except Exception:
                            log.warn('Invalid String value passed to property', exc_info=1)

                    elif property_type in ["font", "caption"]:
                        clip_updated = True
                        try:
                            clip_data[property_key] = str(value)
                        except Exception:
                            log.warn('Invalid Font/Caption value passed to property', exc_info=1)

                    elif property_type == "reader":
                        # Transition
                        clip_updated = True
                        try:
                            if value:
                                # Set a new source
                                clip_object = openshot.Clip(value)
                                clip_object.Open()
                                clip_data[property_key] = json.loads(clip_object.Reader().Json())
                                clip_object.Close()
                                clip_object = None
                            else:
                                # Clear the source (set to a dict with a type field)
                                clip_data[property_key] = {"type": ""}
                        except Exception:
                            log.warn('Invalid Reader value passed to property: %s', value, exc_info=1)

                # Enforce clip timing constraints
                if property_key in ("time", "start", "end", "duration"):
                    clamp_timing_to_media(clip_data, c)

                # Determine if waveforms are impacted by this change
                has_waveform = False
                waveform_file_id = None
                if property_key == "volume":
                    if clip_data.get("ui", {}).get("audio_data", []):
                        waveform_file_id = c.data.get("file_id")
                        has_waveform = True

                # Reduce # of clip properties we are saving (performance boost)
                if not object_id:
                    if property_key == "time":
                        clip_data = {k: clip_data.get(k) for k in ("time", "end", "duration", "start")}
                    else:
                        clip_data = {property_key: clip_data.get(property_key)}
                else:
                    # If objects dict detected - don't reduce the # of objects
                    objects[object_id] = clip_data
                    clip_data = {'objects': objects}

                # Save changes
                if clip_updated:
                    # Save
                    c.data = clip_data
                    c.save()

                    # Update waveforms (if needed)
                    if has_waveform:
                        get_audio_data({waveform_file_id: [c.id]})

                    # Update the preview
                    get_app().window.refreshFrameSignal.emit()

                    log.info("Item %s: changed %s to %s at frame %s (x: %s)" % (item_id, property_key, value, self.frame_number, closest_point_x))

                # Clear selection
                self.parent.clearSelection()

    def set_property(self, property, filter, c, item_type, object_id=None):
        app = get_app()
        _ = app._tr
        label = property[1]["name"]
        name = property[0]

        # Constrain time keyframes to the reader's frame range
        if name == "time" and getattr(c, "data", None):
            _, max_frames = clip_time_bounds(c.data, c)
            if max_frames:
                property[1]["min"] = 1
                property[1]["max"] = float(max_frames)

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
            selected_choices = [c for c in choices if c.get("selected") is True]
            if selected_choices:
                selected_choice = selected_choices[0]["name"]

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
                try:
                    value_int = int(float(value))
                except (TypeError, ValueError):
                    value_int = value
                for track in reversed(sorted(all_tracks, key=itemgetter('number'))):
                    if track.get("number") == value_int:
                        display_label = track.get("label")
                        break
                    display_count -= 1
                track_name = display_label or _("Track %s") % display_count
                col.setText(track_name)

            elif type == "int":
                try:
                    int_value = int(float(value))
                    col.setText("%d" % int_value)
                except (TypeError, ValueError):
                    col.setText("" if value is None else str(value))
            else:
                # Use numeric value
                if value == "" or value is None:
                    col.setText("")
                else:
                    col.setText(QLocale().system().toString(float(value), "f", precision=3))
            col.setData([(obj.Id(), t) for obj, t in self.selected])
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
                vals = property[1]
                # r, g, b
                r, g, b = (int(vals[c]["value"]) for c in ("red", "green", "blue"))
                # alpha falls back to vals["max"] (usually 255) if missing
                a = int(vals.get("alpha", {}).get("value", vals.get("max", 255.0)))
                col.setBackground(QColor(r, g, b, a))

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

        elif name in self.items and self.items[name]["row"]:
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
                reader_json = json.loads(property[1].get("memo") or "{}")
                reader_path = reader_json.get("path", "/")
                fileName = os.path.basename(reader_path)
                col.setText("%s" % fileName)
            else:
                # Use numeric value
                if value == "" or value is None:
                    col.setText("")
                else:
                    col.setText(QLocale().system().toString(float(value), "f", precision=3))

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
                vals = property[1]
                # r, g, b
                r, g, b = (int(vals[c]["value"]) for c in ("red", "green", "blue"))
                # alpha falls back to vals["max"] (usually 255) if missing
                a = int(vals.get("alpha", {}).get("value", vals.get("max", 255.0)))
                col.setBackground(QColor(r, g, b, a))

            # Update helper dictionary
            row.append(col)

        # Keep track of items in a dictionary (for quick look up)
        self.items[name] = {"row": row, "property": property}

    def update_model(self, filter=""):
        log.debug("updating clip properties model.")
        app = get_app()
        _ = app._tr

        if self.ignore_update_signal:
            log.debug("ignoring update signal, because we are already in an update...")
            return

        # Ignore any events from this method
        self.ignore_update_signal = True

        try:
            # Check for a selected clip
            if self.selected and self.selected[0]:
                c, item_type = self.selected[0]

                # Skip blank clips
                # TODO: Determine why c is occasional = None
                if not c:
                    return

                # Build list of raw properties for all selected items
                all_raw_properties = []
                for obj, _item_type in self.selected:
                    props = json.loads(obj.PropertiesJSON(self.frame_number))
                    all_raw_properties.append(props)

                # Use first item's properties as baseline
                raw_properties = all_raw_properties[0]
                tracked_object_id = None
                tracked_object_properties = {}

                if len(all_raw_properties) == 1:
                    tracked_objects_raw_properties = raw_properties.pop('objects', None)
                    if tracked_objects_raw_properties:
                        tracked_object_id = list(tracked_objects_raw_properties.keys())[0]
                        tracked_object_properties = tracked_objects_raw_properties[tracked_object_id]
                        raw_properties.update(tracked_object_properties)
                else:
                    # Remove tracked object lists before comparing
                    if 'objects' in raw_properties:
                        raw_properties.pop('objects')
                    for props in all_raw_properties[1:]:
                        props.pop('objects', None)

                    # Determine shared properties across all selected items
                    shared = {}
                    for key, prop in raw_properties.items():
                        matches = True
                        for other in all_raw_properties[1:]:
                            if key not in other or other[key].get('type') != prop.get('type') or other[key].get('name') != prop.get('name'):
                                matches = False
                                break
                        if matches:
                            values = [other[key]['value'] for other in all_raw_properties]
                            memos = [other[key]['memo'] for other in all_raw_properties]
                            new_prop = prop.copy()
                            if all(v == values[0] for v in values):
                                new_prop['value'] = values[0]
                            else:
                                new_prop['value'] = ''
                            if all(m == memos[0] for m in memos):
                                new_prop['memo'] = memos[0]
                            else:
                                new_prop['memo'] = ''
                            shared[key] = new_prop

                    raw_properties = shared

                # Sort all properties (by 'name')
                all_properties = OrderedDict(sorted(raw_properties.items(), key=lambda x: x[1]['name']))

                # Check if filter was changed (if so, wipe previous model data)
                if self.previous_filter != filter:
                    self.previous_filter = filter
                    self.new_item = True  # filter changed, so we need to regenerate the entire model

                # Build or update the model
                if self.new_item:
                    # Prepare for new properties
                    self.items = {}
                    self.model.clear()

                    # Add Headers
                    self.model.setHorizontalHeaderLabels([_("Property"), _("Value")])

                    # Clear caption editor
                    get_app().window.CaptionTextLoaded.emit("", None)

                # Loop through properties, and build/update the model
                for property in all_properties.items():
                    if property[0] in tracked_object_properties:
                        # Add/update tracked object property
                        self.set_property(property, filter, c, item_type, object_id=tracked_object_id)
                    else:
                        # Add/update base property
                        self.set_property(property, filter, c, item_type)

                # After first render, future calls will update in place
                self.new_item = False

            else:
                # Clear previous model data (if any)
                self.model.clear()

                # Add Headers
                self.model.setHorizontalHeaderLabels([_("Property"), _("Value")])
        finally:
            # Done updating model (even if we returned early)
            self.ignore_update_signal = False

    def __init__(self, parent, *args):

        # Keep track of the selected items (clips, transitions, etc...)
        self.selected = []
        self.current_item_id = None
        self.frame_number = 1
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
        self.next_selection = None

        # Connect data changed signal
        self.model.itemChanged.connect(self.value_updated)

        # Add self as listener to project data updates (used to update the timeline)
        get_app().updates.add_listener(self)
