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

from qt_api import QMimeData, Qt, QLocale, QTimer
from qt_api import (
    QStandardItemModel, QStandardItem,
    QPixmap, QColor,
    )

from classes.waveform import get_audio_data
from classes import info, updates
from classes import openshot_rc  # noqa
from classes.clip_utils import clamp_timing_to_media, clip_time_bounds, is_single_image_media
from classes.query import Clip, Transition, Effect, File
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
    def _insert_colorgrade_keyframe(self, data, property_type, frame_number):
        from windows.color_grade_editor import (
            _set_color_value,
            _set_keyframe_value,
            curve_enabled_at_frame,
            curve_nodes_at_frame,
            normalize_curve_data,
            normalize_wheels_data,
            wheels_enabled_at_frame,
            wheels_snapshot,
        )

        frame_number = int(round(frame_number))
        if property_type == "colorgrade_curve":
            updated = normalize_curve_data(data)
            enabled = 1.0 if curve_enabled_at_frame(updated, frame_number) else 0.0
            updated["enabled"] = _set_keyframe_value(
                updated.get("enabled"), frame_number, enabled, openshot.LINEAR)
            nodes_at_frame = {
                node["id"]: node
                for node in curve_nodes_at_frame(updated, frame_number)
            }
            for node in updated.get("nodes", []):
                snapshot = nodes_at_frame.get(node.get("id"))
                if not snapshot:
                    continue
                for key in ("x", "y", "left_handle_x", "left_handle_y", "right_handle_x", "right_handle_y"):
                    node[key] = _set_keyframe_value(
                        node.get(key), frame_number, snapshot.get(key, 0.0), openshot.LINEAR)
            return normalize_curve_data(updated)

        updated = normalize_wheels_data(data)
        snapshot = wheels_snapshot(updated, frame_number)
        enabled = 1.0 if wheels_enabled_at_frame(updated, frame_number) else 0.0
        updated["enabled_keyframes"] = _set_keyframe_value(
            updated.get("enabled_keyframes"), frame_number, enabled, openshot.LINEAR)
        for name in ("global", "shadows", "midtones", "highlights"):
            wheel = updated.get(name, {})
            wheel_snapshot = snapshot.get(name, {})
            wheel["color_keyframes"] = _set_color_value(
                wheel.get("color_keyframes"), frame_number, QColor(wheel_snapshot.get("color", "#ffffff")),
                openshot.LINEAR)
            wheel["amount_keyframes"] = _set_keyframe_value(
                wheel.get("amount_keyframes"), frame_number, wheel_snapshot.get("amount", 0.0), openshot.LINEAR)
            wheel["luma_keyframes"] = _set_keyframe_value(
                wheel.get("luma_keyframes"), frame_number, wheel_snapshot.get("luma", 0.0), openshot.LINEAR)
        return normalize_wheels_data(updated)

    def _remove_colorgrade_keyframe(self, data, property_type, frame_number):
        from windows.color_grade_editor import normalize_curve_data, normalize_wheels_data

        frame_number = int(round(frame_number))
        if property_type == "colorgrade_curve":
            updated = normalize_curve_data(data)
        else:
            updated = normalize_wheels_data(data)

        changed = False

        def _remove_from_keyframe(kf_data):
            nonlocal changed
            points = kf_data.get("Points") if isinstance(kf_data, dict) else None
            if not isinstance(points, list) or len(points) <= 1:
                return
            filtered = []
            for point in points:
                try:
                    keep = int(round(float(point.get("co", {}).get("X")))) != frame_number
                except (TypeError, ValueError):
                    keep = True
                if keep:
                    filtered.append(point)
            if len(filtered) != len(points):
                kf_data["Points"] = filtered
                changed = True

        def _walk(value):
            if isinstance(value, dict):
                if isinstance(value.get("Points"), list):
                    _remove_from_keyframe(value)
                    return
                for child in value.values():
                    _walk(child)
            elif isinstance(value, list):
                for child in value:
                    _walk(child)

        _walk(updated)
        if property_type == "colorgrade_curve":
            return normalize_curve_data(updated), changed
        return normalize_wheels_data(updated), changed

    def _save_colorgrade_keyframe_update(self, item, operation):
        property = self.model.item(item.row(), 0).data()
        property_type = property[1]["type"]
        property_key = property[0]
        object_id = property[1]["object_id"]
        item_data = item.data()
        any_updated = False

        for item_id, item_type in item_data:
            clip_updated = False
            c = None
            if item_type == "clip":
                c = Clip.get(id=item_id)
            elif item_type == "transition":
                c = Transition.get(id=item_id)
            elif item_type == "effect":
                c = Effect.get(id=item_id)
            if not c or not c.data:
                continue

            clip_data = c.data
            objects = {}
            if object_id:
                objects = c.data.get('objects', {})
                clip_data = objects.get(object_id, {})
                if not clip_data:
                    log.debug("No clip data found for this object id")
                    continue
            if property_key not in clip_data:
                continue

            if operation == "insert":
                clip_data[property_key] = self._insert_colorgrade_keyframe(
                    clip_data[property_key], property_type, self.frame_number)
                clip_updated = True
            else:
                clip_data[property_key], clip_updated = self._remove_colorgrade_keyframe(
                    clip_data[property_key], property_type, self.frame_number)

            if not clip_updated:
                continue
            if not object_id:
                clip_data = {property_key: clip_data.get(property_key)}
            else:
                clip_data = self._tracked_object_update_payload(c.data, object_id, clip_data, property_key)
            c.data = clip_data
            c.save()
            any_updated = True

        if any_updated:
            if not self._trim_preview_mode:
                get_app().window.refreshFrameSignal.emit()

        current_row = self.parent.currentIndex().row()
        self.parent.clearSelection()
        if current_row >= 0:
            self.parent.setCurrentIndex(self.model.index(current_row, 0))

    def insert_keyframe(self, item):
        property = self.model.item(item.row(), 0).data()
        property_type = property[1]["type"]
        if property_type in ("colorgrade_curve", "colorgrade_wheels"):
            self._save_colorgrade_keyframe_update(item, "insert")
            return
        if property_type == "color":
            property_data = property[1]
            current_color = QColor(
                int(property_data["red"]["value"]),
                int(property_data["green"]["value"]),
                int(property_data["blue"]["value"]),
                int(property_data.get("alpha", {}).get("value", property_data.get("max", 255.0))),
            )
            self.color_update(item, current_color)
            return

        value = QLocale().system().toDouble(item.text())[0]
        self.value_updated(item, value=value)

    def _resolve_reader_source_path(self, value):
        """Resolve a reader property value to a filesystem path when possible."""
        if value in (None, ""):
            return ""

        if isinstance(value, dict):
            value = value.get("path", "")

        source_value = str(value).strip()
        if not source_value:
            return ""

        if os.path.exists(source_value):
            return source_value

        file_obj = File.get(path=source_value)
        if file_obj:
            return file_obj.absolute_path()

        return source_value

    def _reader_display_name(self, selected_item, reader_memo):
        """Resolve a human-friendly reader display name from File.name when available."""
        reader_json = json.loads(reader_memo or "{}")
        reader_path = reader_json.get("path", "")
        file_id = reader_json.get("id")

        if getattr(selected_item, "data", None):
            file_id = selected_item.data.get("file_id") or file_id

        if file_id:
            file_obj = File.get(id=file_id)
            if file_obj:
                file_name = str(file_obj.data.get("name", "")).strip()
                if file_name:
                    return file_name

        return os.path.basename(reader_path)

    def _mask_reader_data(self, data):
        reader = {}
        if isinstance(data, dict):
            for key in ("mask_reader", "reader"):
                candidate = data.get(key)
                if isinstance(candidate, dict):
                    reader = candidate
                    break
        return reader

    def _transition_uses_static_mask(self, transition_data):
        reader = self._mask_reader_data(transition_data)
        if not reader:
            return True
        if not reader.get("path") and not reader.get("id") and not reader.get("has_single_image"):
            return True
        if isinstance(reader, dict) and "has_single_image" in reader:
            return bool(reader.get("has_single_image"))
        return bool(is_single_image_media(reader))

    def _mask_source_is_animated(self, data):
        reader = self._mask_reader_data(data)
        return bool(isinstance(reader, dict) and reader.get("has_single_image") is False)

    def _transition_default_keyframes(self, duration, start_value, end_value, contrast_value):
        fps = get_app().project.get("fps")
        fps_float = float(fps["num"]) / float(fps["den"])
        duration = max(0.0, float(duration or 0.0))

        brightness = openshot.Keyframe()
        brightness.AddPoint(1, float(start_value), openshot.BEZIER)
        if float(start_value) != float(end_value):
            brightness.AddPoint(round(duration * fps_float) + 1, float(end_value), openshot.BEZIER)
        contrast = openshot.Keyframe(float(contrast_value))
        return json.loads(brightness.Json()), json.loads(contrast.Json())

    def _effect_filter_base_properties(self, effect_data):
        """Return effect base properties that should remain hidden."""
        hidden = ["position", "layer", "start", "end", "duration"]
        if not isinstance(effect_data, dict):
            return hidden

        is_mask = (
            effect_data.get("type") == "Mask"
            or effect_data.get("class_name") == "Mask"
            or "mask_reader" in effect_data
        )
        if is_mask and self._mask_source_is_animated(effect_data):
            return ["position", "layer", "duration"]
        return hidden

    def _refresh_selected_effect_filters(self):
        if not self.selected:
            return
        item, item_type = self.selected[0]
        if item_type != "effect":
            return

        effect_id = None
        try:
            effect_id = item.Id()
        except Exception:
            effect_id = None
        effect_obj = Effect.get(id=effect_id) if effect_id else None
        next_filter_base_properties = self._effect_filter_base_properties(
            getattr(effect_obj, "data", None)
        )
        if next_filter_base_properties != self.filter_base_properties:
            self.filter_base_properties = next_filter_base_properties
            self.new_item = True
        else:
            self.filter_base_properties = next_filter_base_properties

    def _resolve_tracked_object_id(self, raw_properties, tracked_objects_raw_properties):
        """Resolve selected tracked object ID from properties payload."""
        if not tracked_objects_raw_properties:
            return None

        selected_idx = raw_properties.get("selected_object_index", {}).get("value")
        if selected_idx not in (None, "", "None"):
            selected_idx = str(selected_idx)
            try:
                selected_idx_number = int(float(selected_idx))
            except (TypeError, ValueError):
                selected_idx_number = None
            if selected_idx_number == -1 and "all" in tracked_objects_raw_properties:
                return "all"
            if selected_idx in tracked_objects_raw_properties:
                return selected_idx

            # Newer tracked-object IDs are "<effect-uuid>-<index>".
            suffix = f"-{selected_idx}"
            for object_id in tracked_objects_raw_properties.keys():
                if object_id.endswith(suffix):
                    return object_id

        # Fallback to first tracked object
        return next(iter(tracked_objects_raw_properties.keys()))

    def _tracked_object_is_all(self, object_id):
        return str(object_id).strip().lower() in {"all", "*", "-1"}

    def _tracked_object_clip_data(self, effect_data, object_id):
        """Return editable tracked object data, using a real object as template for 'all'."""
        objects = effect_data.get('objects', {})
        if not object_id:
            return effect_data, False
        if self._tracked_object_is_all(object_id):
            template = objects.get("all")
            if not isinstance(template, dict):
                template = next((value for key, value in objects.items()
                                 if not self._tracked_object_is_all(key) and isinstance(value, dict)), {})
            return json.loads(json.dumps(template or {})), True
        return objects.get(object_id, {}), False

    def _tracked_object_update_payload(self, effect_data, object_id, clip_data, property_key):
        """Build an effect update payload for one tracked object property edit."""
        property_payload = json.loads(json.dumps(clip_data.get(property_key)))
        if self._tracked_object_is_all(object_id):
            objects_payload = {object_id: {property_key: property_payload}}
            for existing_id, existing_data in effect_data.get('objects', {}).items():
                if self._tracked_object_is_all(existing_id) or not isinstance(existing_data, dict):
                    continue
                objects_payload[existing_id] = {property_key: property_payload}
            return {'objects': objects_payload}
        return {'objects': {object_id: {property_key: property_payload}}}

    # This method is invoked by the UpdateManager each time a change happens (i.e UpdateInterface)
    def changed(self, action):

        # Handle change
        if action and len(action.key) >= 1 and action.key[0] in ["clips", "effects"] and action.type in ["update", "insert"]:
            log.debug(action.values)
            self._refresh_selected_effect_filters()
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
                        self.selected.append((e, item_type))
                        self.selected_parent = e.ParentClip()
                        self._refresh_selected_effect_filters()

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

        if property_type in ("colorgrade_curve", "colorgrade_wheels"):
            self._save_colorgrade_keyframe_update(item, "remove")
            return

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
                clip_data, _ = self._tracked_object_clip_data(c.data, object_id)
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

                use_transition_update = item_type == "transition" and not object_id and property_key == "mask_reader"
                full_transition_data = clip_data if use_transition_update else None

                # Reduce # of clip properties we are saving (performance boost)
                if use_transition_update:
                    pass
                elif not object_id:
                    if property_key == "time":
                        clip_data = {k: clip_data.get(k) for k in ("time", "end", "duration", "start")}
                    else:
                        clip_data = {property_key: clip_data.get(property_key)}
                else:
                    clip_data = self._tracked_object_update_payload(c.data, object_id, clip_data, property_key)

                # Save changes
                if clip_updated:
                    if use_transition_update:
                        timeline = getattr(get_app().window, "timeline", None)
                        if timeline:
                            timeline.update_transition_data(full_transition_data, only_basic_props=False)
                            c = Transition.get(id=item_id) or c
                        else:
                            log.warning(
                                "Timeline unavailable for transition mask_reader update; saving transition %s directly",
                                item_id,
                            )
                            c.data = full_transition_data
                            c.save()
                    else:
                        # Save
                        c.data = clip_data
                        c.save()

                    # Update waveforms (if needed)
                    if has_waveform:
                        get_audio_data({waveform_file_id: [c.id]})

                    # Update the preview
                    if not self._trim_preview_mode:
                        get_app().window.refreshFrameSignal.emit()

                # Clear selection and restore focus to label column
                current_row = self.parent.currentIndex().row()
                self.parent.clearSelection()
                if current_row >= 0:
                    self.parent.setCurrentIndex(self.model.index(current_row, 0))

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
                        clip_data, _ = self._tracked_object_clip_data(c.data, object_id)
                        if not isinstance(clip_data, dict):
                            clip_data = {}

                    # Update clip attribute
                    if property_key not in clip_data and object_id:
                        clip_data[property_key] = {
                            channel: json.loads(json.dumps(property[1].get(channel, {"Points": []})))
                            for channel in ("red", "blue", "green", "alpha")
                            if channel in property[1]
                        }
                        for channel in ("red", "blue", "green"):
                            clip_data[property_key].setdefault(channel, {"Points": []})

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
                        clip_data = self._tracked_object_update_payload(c.data, object_id, clip_data, property_key)

                    # Save changes
                    if clip_updated:
                        # Save
                        c.data = clip_data
                        c.save()

                        # Update the preview
                        if not self._trim_preview_mode:
                            get_app().window.refreshFrameSignal.emit()

                    # Clear selection and restore focus to label column
                    current_row = self.parent.currentIndex().row()
                    self.parent.clearSelection()
                    if current_row >= 0:
                        self.parent.setCurrentIndex(self.model.index(current_row, 0))

    def _colorgrade_interpolation_at_frame(self, data, property_type, frame_number):
        def _find_in_keyframe(kf_data):
            points = kf_data.get("Points") if isinstance(kf_data, dict) else None
            if not isinstance(points, list):
                return None
            for point in points:
                try:
                    if int(round(float(point["co"]["X"]))) == int(round(frame_number)):
                        return int(point.get("interpolation", openshot.LINEAR))
                except (KeyError, TypeError, ValueError):
                    continue
            return None

        def _walk(value):
            found = _find_in_keyframe(value)
            if found is not None:
                return found
            if isinstance(value, dict):
                for child in value.values():
                    found = _walk(child)
                    if found is not None:
                        return found
            elif isinstance(value, list):
                for child in value:
                    found = _walk(child)
                    if found is not None:
                        return found
            return None

        found = _walk(data)
        return openshot.LINEAR if found is None else found

    def _apply_colorgrade_interpolation(self, data, property_type, previous_point_x,
                                        closest_point_x, interpolation, interpolation_details):
        if interpolation < 0:
            return data, False

        from windows.color_grade_editor import normalize_curve_data, normalize_wheels_data

        if property_type == "colorgrade_curve":
            updated = normalize_curve_data(data)
        else:
            updated = normalize_wheels_data(data)

        changed = False
        previous_frame = int(round(previous_point_x))
        closest_frame = int(round(closest_point_x))

        def _frame_matches(point, frame):
            try:
                return int(round(float(point.get("co", {}).get("X")))) == frame
            except (TypeError, ValueError):
                return False

        def _update_keyframe(kf_data):
            nonlocal changed
            points = kf_data.get("Points") if isinstance(kf_data, dict) else None
            if not isinstance(points, list):
                return
            for point in points:
                if _frame_matches(point, previous_frame):
                    changed = True
                    if int(point.get("interpolation", openshot.LINEAR)) == openshot.BEZIER and interpolation_details:
                        point["handle_right"] = point.get("handle_right") or {"Y": 0.0, "X": 0.0}
                        point["handle_right"]["X"] = interpolation_details[0]
                        point["handle_right"]["Y"] = interpolation_details[1]
                    else:
                        point.pop("handle_right", None)
                if _frame_matches(point, closest_frame):
                    changed = True
                    point["interpolation"] = interpolation
                    if interpolation == openshot.BEZIER and interpolation_details:
                        point["handle_left"] = point.get("handle_left") or {"Y": 0.0, "X": 0.0}
                        point["handle_left"]["X"] = interpolation_details[2]
                        point["handle_left"]["Y"] = interpolation_details[3]
                    else:
                        point.pop("handle_left", None)

        def _walk(value):
            if isinstance(value, dict):
                if isinstance(value.get("Points"), list):
                    _update_keyframe(value)
                    return
                for child in value.values():
                    _walk(child)
            elif isinstance(value, list):
                for child in value:
                    _walk(child)

        _walk(updated)
        return updated, changed

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
        property_choices = property[1].get("choices") or []
        choice_keyframes_use_constant = bool(property_choices) and interpolation == -1
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
                is_mask_reader_update = (
                    not object_id
                    and property_key == "mask_reader"
                )

                # Create reference
                clip_data = c.data
                if object_id:
                    clip_data, _ = self._tracked_object_clip_data(c.data, object_id)
                    if not clip_data:
                        log.debug("No clip data found for this object id")
                        return

                if (
                    property_key not in clip_data
                    and item_type == "effect"
                    and property_key in {"left", "top", "right", "bottom"}
                    and property_type == "float"
                ):
                    clip_data[property_key] = {"Points": []}
                elif (
                    property_key not in clip_data
                    and object_id
                    and property_type in {"bool", "float", "int"}
                ):
                    clip_data[property_key] = {
                        "Points": json.loads(json.dumps(property[1].get("Points", [])))
                    }

                # Update clip attribute
                if property_key in clip_data:
                    log_id = "{}/{}".format(item_id, object_id) if object_id else item_id
                    log.debug("%s: update property %s. %s", log_id, property_key, clip_data.get(property_key))

                    # Check the type of property (some are keyframe, and some are not)
                    if property_type in ["colorgrade_curve", "colorgrade_wheels"] and interpolation > -1:
                        updated_value, clip_updated = self._apply_colorgrade_interpolation(
                            clip_data[property_key],
                            property_type,
                            previous_point_x,
                            closest_point_x,
                            interpolation,
                            interpolation_details,
                        )
                        if clip_updated:
                            clip_data[property_key] = updated_value

                    elif property_type not in ["reader", "colorgrade_curve", "colorgrade_wheels"] and isinstance(clip_data[property_key], dict):
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
                                    if choice_keyframes_use_constant:
                                        point["interpolation"] = openshot.CONSTANT
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
                                'interpolation': openshot.CONSTANT if choice_keyframes_use_constant else openshot.LINEAR})

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

                    elif property_type in ["colorgrade_curve", "colorgrade_wheels"]:
                        clip_updated = True
                        try:
                            if isinstance(value, str):
                                clip_data[property_key] = json.loads(value)
                            elif isinstance(value, dict):
                                clip_data[property_key] = value
                            else:
                                clip_data[property_key] = {}
                        except Exception:
                            log.warn('Invalid rich JSON value passed to property', exc_info=1)

                    elif property_type == "reader":
                        # Reader / mask source
                        clip_updated = True
                        try:
                            selection_data = value if isinstance(value, dict) else {}
                            selected_start = selection_data.get("start")
                            selected_end = selection_data.get("end")
                            reader_value = {"type": ""}
                            if value:
                                # Set a new source
                                resolved_value = self._resolve_reader_source_path(value)
                                clip_object = openshot.Clip(resolved_value)
                                clip_object.Open()
                                reader_value = json.loads(clip_object.Reader().Json())
                                clip_object.Close()
                                clip_object = None
                            # Clear the source (set to a dict with a type field)
                            clip_data[property_key] = reader_value
                            if is_mask_reader_update:
                                clip_data["mask_reader"] = reader_value
                                clip_data["reader"] = reader_value

                            if is_mask_reader_update:
                                start_source = selected_start if selected_start is not None else clip_data.get("start", 0.0)
                                end_source = selected_end if selected_end is not None else clip_data.get("end", start_source)
                                start = float(start_source or 0.0)
                                end = float(end_source or start)
                                if end < start:
                                    end = start
                                duration = max(0.0, end - start)

                                if self._transition_uses_static_mask(clip_data):
                                    clip_data["start"] = 0.0
                                    clip_data["end"] = duration
                                    brightness, contrast = self._transition_default_keyframes(
                                        duration, 1.0, -1.0, 3.0
                                    )
                                else:
                                    clip_data["start"] = start
                                    clip_data["end"] = end
                                    brightness, contrast = self._transition_default_keyframes(
                                        duration, 0.0, 0.0, 0.0
                                    )

                                clip_data["duration"] = max(
                                    0.0,
                                    float(clip_data.get("end", 0.0) or 0.0) - float(clip_data.get("start", 0.0) or 0.0),
                                )
                                clip_data["brightness"] = brightness
                                clip_data["contrast"] = contrast
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
                if is_mask_reader_update:
                    pass
                elif not object_id:
                    if property_key == "time":
                        clip_data = {k: clip_data.get(k) for k in ("time", "end", "duration", "start")}
                    else:
                        clip_data = {property_key: clip_data.get(property_key)}
                else:
                    clip_data = self._tracked_object_update_payload(c.data, object_id, clip_data, property_key)

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

                # Clear selection and restore focus to label column
                current_row = self.parent.currentIndex().row()
                self.parent.clearSelection()
                if current_row >= 0:
                    self.parent.setCurrentIndex(self.model.index(current_row, 0))

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

        # Colorgrade types store nested keyframe structures libopenshot doesn't parse,
        # so compute keyframe/points from the actual nested data.
        if type in ["colorgrade_curve", "colorgrade_wheels"]:
            from windows.color_grade_editor import colorgrade_keyframe_frames
            data_key = "curve" if type == "colorgrade_curve" else "wheels"
            colorgrade_data = property[1].get(data_key)
            frame_set = colorgrade_keyframe_frames(colorgrade_data, type)
            points = max(1, len(frame_set))
            keyframe = int(round(self.frame_number)) in frame_set
            if frame_set:
                sorted_frames = sorted(frame_set)
                current_frame = int(round(self.frame_number))
                closest_frame = next((frame for frame in sorted_frames if frame >= current_frame), sorted_frames[-1])
                closest_index = sorted_frames.index(closest_frame)
                previous_frame = sorted_frames[max(0, closest_index - 1)]
                property[1]["closest_point_x"] = closest_frame
                property[1]["previous_point_x"] = previous_frame
                interpolation = self._colorgrade_interpolation_at_frame(colorgrade_data, type, closest_frame)
                property[1]["interpolation"] = interpolation
            property[1]["points"] = points
            property[1]["keyframe"] = keyframe
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
                col.setText(self._reader_display_name(c, memo))
            elif type in ["colorgrade_curve", "colorgrade_wheels"]:
                col.setText(property[1].get("summary", memo))
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
                track_name = display_label or _("Track %s") % QLocale().toString(display_count)
                col.setText(track_name)

            elif type == "int":
                try:
                    int_value = int(float(value))
                    if label in ["Channel Filter", "Channel Mapping"] and int_value == -1:
                        col.setText(_("All channels"))
                    else:
                        col.setText("%d" % int_value)
                except (TypeError, ValueError):
                    col.setText("" if value is None else str(value))
            else:
                # Use numeric value
                if value == "" or value is None:
                    col.setText("")
                else:
                    if name in ["duration", "end", "start", "time"]:
                        try:
                            fps = get_app().project.get("fps")
                            fps_float = float(fps["num"]) / float(fps["den"])
                            frames = int(round(float(value) * fps_float))
                            h = frames // int(fps_float * 3600)
                            m = (frames // int(fps_float * 60)) % 60
                            s = (frames // int(fps_float)) % 60
                            f = frames % int(fps_float)
                            col.setText(f"{h:02d}:{m:02d}:{s:02d};{f:02d}")
                        except Exception:
                            col.setText(QLocale().system().toString(float(value), "f", precision=3))
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

            if readonly or type in ["color", "font", "caption", "colorgrade_curve", "colorgrade_wheels"] or choices or label == "Track":
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
            if type == "caption":
                # Load caption editor after both label/value cells exist.
                get_app().window.CaptionTextLoaded.emit(memo, row)

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
            elif type in ["colorgrade_curve", "colorgrade_wheels"]:
                col.setText(property[1].get("summary", memo))
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
                track_name = display_label or _("Track %s") % QLocale().toString(display_count)
                col.setText(track_name)
            elif type == "int":
                try:
                    int_value = int(float(value))
                    if label in ["Channel Filter", "Channel Mapping"] and int_value == -1:
                        col.setText(_("All channels"))
                    else:
                        col.setText("%d" % int_value)
                except (TypeError, ValueError):
                    col.setText("" if value is None else str(value))
            elif type == "reader":
                col.setText(self._reader_display_name(c, property[1].get("memo")))
            else:
                # Use numeric value
                if value == "" or value is None:
                    col.setText("")
                else:
                    if name in ["duration", "end", "start", "time"]:
                        try:
                            fps = get_app().project.get("fps")
                            fps_float = float(fps["num"]) / float(fps["den"])
                            frames = int(round(float(value) * fps_float))
                            h = frames // int(fps_float * 3600)
                            m = (frames // int(fps_float * 60)) % 60
                            s = (frames // int(fps_float)) % 60
                            f = frames % int(fps_float)
                            col.setText(f"{h:02d}:{m:02d}:{s:02d};{f:02d}")
                        except Exception:
                            col.setText(QLocale().system().toString(float(value), "f", precision=3))
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
            if type == "caption":
                # Keep the editor enabled and synchronized on property refreshes.
                get_app().window.CaptionTextLoaded.emit(memo, row)

        # Keep track of items in a dictionary (for quick look up)
        self.items[name] = {"row": row, "property": property}

    def update_model(self, filter=""):
        app = get_app()
        _ = app._tr
        refreshed = False

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
                        tracked_object_id = self._resolve_tracked_object_id(
                            raw_properties, tracked_objects_raw_properties)
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

                # Sort all properties (by task group, then name)
                def sort_key(x):
                    name = x[1].get('name', '').lower()
                    if name in ['location x', 'location y', 'scale x', 'scale y', 'rotation', 'shear x', 'shear y', 'origin x', 'origin y', 'gravity']:
                        return (0, name)
                    elif name in ['alpha', 'color', 'color_offset', 'perspective c1 x', 'perspective c1 y', 'perspective c2 x', 'perspective c2 y', 'perspective c3 x', 'perspective c3 y', 'perspective c4 x', 'perspective c4 y', 'enable video']:
                        return (1, name)
                    elif name in ['duration', 'end', 'start', 'time', 'layer', 'track']:
                        return (2, name)
                    elif name in ['volume', 'channel mapping', 'channel filter', 'enable audio']:
                        return (3, name)
                    return (4, name)

                all_properties = OrderedDict(sorted(raw_properties.items(), key=sort_key))

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
                refreshed = True

            else:
                # Clear previous model data (if any)
                self.model.clear()

                # Add Headers
                self.model.setHorizontalHeaderLabels([_("Property"), _("Value")])
                refreshed = True
        finally:
            # Done updating model (even if we returned early)
            self.ignore_update_signal = False

        if refreshed:
            refresh_callback = getattr(self.parent, "property_model_refreshed", None)
            if callable(refresh_callback):
                refresh_callback()

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
        self._trim_preview_mode = False

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
        get_app().window.TrimPreviewMode.connect(self._enter_trim_preview)
        get_app().window.TimelinePreviewMode.connect(self._exit_trim_preview)

    def _enter_trim_preview(self):
        self._trim_preview_mode = True

    def _exit_trim_preview(self):
        self._trim_preview_mode = False
