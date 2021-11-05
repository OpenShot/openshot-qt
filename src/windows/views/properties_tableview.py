"""
 @file
 @brief This file contains the properties tableview, used by the main window
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
import json
import functools
from operator import itemgetter

from PyQt5.QtCore import Qt, QRectF, QLocale, pyqtSignal, pyqtSlot, QRect
from PyQt5.QtGui import (
    QCursor, QIcon, QColor, QBrush, QPen, QPalette, QPixmap,
    QPainter, QPainterPath, QLinearGradient, QFont, QFontInfo,
)
from PyQt5.QtWidgets import (
    QTableView, QAbstractItemView, QMenu, QSizePolicy,
    QHeaderView, QItemDelegate, QStyle, QLabel,
    QPushButton, QHBoxLayout, QFrame, QFontDialog
)

from classes.logger import log
from classes.app import get_app
from classes import info
from classes.query import Clip, Effect, Transition

from windows.models.properties_model import PropertiesModel
from windows.color_picker import ColorPicker

import openshot


class PropertyDelegate(QItemDelegate):
    def __init__(self, parent=None, *args, **kwargs):

        self.model = kwargs.pop("model", None)
        if not self.model:
            log.error("Cannot create delegate without data model!")

        super().__init__(parent, *args, **kwargs)

        # pixmaps for curve icons
        self.curve_pixmaps = {
            openshot.BEZIER: QIcon(":/curves/keyframe-%s.png" % openshot.BEZIER).pixmap(20, 20),
            openshot.LINEAR: QIcon(":/curves/keyframe-%s.png" % openshot.LINEAR).pixmap(20, 20),
            openshot.CONSTANT: QIcon(":/curves/keyframe-%s.png" % openshot.CONSTANT).pixmap(20, 20)
            }

    def paint(self, painter, option, index):
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)

        # Get data model and selection
        model = self.model
        row = model.itemFromIndex(index).row()
        selected_label = model.item(row, 0)
        selected_value = model.item(row, 1)
        cur_property = selected_label.data()

        # Get min/max values for this property
        property_type = cur_property[1]["type"]
        property_max = cur_property[1]["max"]
        property_min = cur_property[1]["min"]
        readonly = cur_property[1]["readonly"]
        points = cur_property[1]["points"]
        interpolation = cur_property[1]["interpolation"]

        # Calculate percentage value
        if property_type in ["float", "int"]:
            # Get the current value
            current_value = QLocale().system().toDouble(selected_value.text())[0]

            # Shift my range to be positive
            if property_min < 0.0:
                property_shift = 0.0 - property_min
                property_min += property_shift
                property_max += property_shift
                current_value += property_shift

            # Calculate current value as % of min/max range
            min_max_range = float(property_max) - float(property_min)
            value_percent = current_value / min_max_range
        else:
            value_percent = 0.0

        # set background color
        painter.setPen(QPen(Qt.NoPen))
        if property_type == "color":
            # Color keyframe
            red = int(cur_property[1]["red"]["value"])
            green = int(cur_property[1]["green"]["value"])
            blue = int(cur_property[1]["blue"]["value"])
            painter.setBrush(QColor(red, green, blue))
        else:
            # Normal Keyframe
            if option.state & QStyle.State_Selected:
                painter.setBrush(QColor("#575757"))
            else:
                painter.setBrush(QColor("#3e3e3e"))

        if readonly:
            # Set text color for read only fields
            painter.setPen(QPen(get_app().window.palette().color(QPalette.Disabled, QPalette.Text)))
        else:
            path = QPainterPath()
            path.addRoundedRect(QRectF(option.rect), 15, 15)
            painter.fillPath(path, QColor("#3e3e3e"))
            painter.drawPath(path)

            # Render mask rectangle
            painter.setBrush(QBrush(QColor("#000000")))
            mask_rect = QRectF(option.rect)
            mask_rect.setWidth(option.rect.width() * value_percent)
            painter.setClipRect(mask_rect, Qt.IntersectClip)

            # gradient for value box
            gradient = QLinearGradient(option.rect.topLeft(), option.rect.topRight())
            gradient.setColorAt(0, QColor("#828282"))
            gradient.setColorAt(1, QColor("#828282"))

            # Render progress
            painter.setBrush(gradient)
            path = QPainterPath()
            value_rect = QRectF(option.rect)
            path.addRoundedRect(value_rect, 15, 15)
            painter.fillPath(path, gradient)
            painter.drawPath(path)
            painter.setClipping(False)

            if points > 1:
                # Draw interpolation icon on top
                painter.drawPixmap(
                    int(option.rect.x() + option.rect.width() - 30.0),
                    int(option.rect.y() + 4),
                    self.curve_pixmaps[interpolation])

            # Set text color
            painter.setPen(QPen(Qt.white))

        value = index.data(Qt.DisplayRole)
        if value:
            painter.drawText(option.rect, Qt.AlignCenter, value)

        painter.restore()


class PropertiesTableView(QTableView):
    """ A Properties Table QWidget used on the main window """
    loadProperties = pyqtSignal(str, str)

    def mouseMoveEvent(self, event):
        # Get data model and selection
        model = self.clip_properties_model.model

        # Do not change selected row during mouse move
        if self.lock_selection and self.prev_row:
            row = self.prev_row
        else:
            row = self.indexAt(event.pos()).row()
            self.prev_row = row
            self.lock_selection = True

        if row is None:
            return

        event.accept()

        if model.item(row, 0):
            self.selected_label = model.item(row, 0)
            self.selected_item = model.item(row, 1)

        # Is the user dragging on the value column
        if self.selected_label and self.selected_item:
            # Get the position of the cursor and % value
            value_column_x = self.columnViewportPosition(1)
            cursor_value = event.x() - value_column_x
            cursor_value_percent = cursor_value / self.columnWidth(1)

            try:
                cur_property = self.selected_label.data()
            except Exception:
                # If item is deleted during this drag... an exception can occur
                # Just ignore, since this is harmless
                log.debug('Failed to access data on selected label widget')

            property_key = cur_property[0]
            property_name = cur_property[1]["name"]
            property_type = cur_property[1]["type"]
            property_max = cur_property[1]["max"]
            property_min = cur_property[1]["min"]
            readonly = cur_property[1]["readonly"]
            item_id, item_type = self.selected_item.data()

            # Bail if readonly
            if readonly:
                return

            # Get the original data of this item (prior to any updates, for the undo/redo system)
            if not self.original_data:
                # Ignore undo/redo history temporarily (to avoid a huge pile of undo/redo history)
                get_app().updates.ignore_history = True

                # Find this clip
                c = None
                if item_type == "clip":
                    # Get clip object
                    c = Clip.get(id=item_id)
                elif item_type == "transition":
                    # Get transition object
                    c = Transition.get(id=item_id)
                elif item_type == "effect":
                    # Get effect object
                    c = Effect.get(id=item_id)

                if c and property_key in c.data:
                    # Grab the original data for this item/property
                    self.original_data = c.data

            # For numeric values, apply percentage within parameter's allowable range
            if property_type in ["float", "int"] and property_name != "Track":

                if self.previous_x == -1:
                    # Start tracking movement (init diff_length and previous_x)
                    self.diff_length = 10
                    self.previous_x = event.x()

                # Calculate # of pixels dragged
                drag_diff = self.previous_x - event.x()

                # update previous x
                self.previous_x = event.x()

                # Ignore small initial movements
                if abs(drag_diff) < self.diff_length:
                    # Lower threshold to 0 incrementally, to guarantee it'll eventually be exceeded
                    self.diff_length = max(0, self.diff_length - 1)
                    return

                # Compute size of property's possible values range
                min_max_range = float(property_max) - float(property_min)

                if min_max_range < 1000.0:
                    # Small range - use cursor to calculate new value as percentage of total range
                    self.new_value = property_min + (min_max_range * cursor_value_percent)
                else:
                    # range is unreasonably long (such as position, start, end, etc.... which can be huge #'s)

                    # Get the current value and apply fixed adjustments in response to motion
                    self.new_value = QLocale().system().toDouble(self.selected_item.text())[0]

                    if drag_diff > 0:
                        # Move to the left by a small amount
                        self.new_value -= 0.50
                    elif drag_diff < 0:
                        # Move to the right by a small amount
                        self.new_value += 0.50

                # Clamp value between min and max (just incase user drags too big)
                self.new_value = max(property_min, self.new_value)
                self.new_value = min(property_max, self.new_value)

                if property_type == "int":
                    self.new_value = round(self.new_value, 0)

                # Update value of this property
                self.clip_properties_model.value_updated(self.selected_item, -1, self.new_value)

                # Repaint
                self.viewport().update()

    def mouseReleaseEvent(self, event):
        # Inform UpdateManager to accept updates, and only store our final update
        event.accept()
        get_app().updates.ignore_history = False

        # Add final update to undo/redo history
        get_app().updates.apply_last_action_to_history(self.original_data)

        # Clear original data
        self.original_data = None

        # Get data model and selection
        model = self.clip_properties_model.model
        row = self.indexAt(event.pos()).row()
        if model.item(row, 0):
            self.selected_label = model.item(row, 0)
            self.selected_item = model.item(row, 1)

        # Allow new selection and prepare to set minimum move threshold
        self.lock_selection = False
        self.previous_x = -1

    @pyqtSlot(QColor)
    def color_callback(self, newColor: QColor):
        # Set the new color keyframe
        if newColor.isValid():
            self.clip_properties_model.color_update(
                self.selected_item, newColor)

    def doubleClickedCB(self, model_index):
        """Double click handler for the property table"""

        # Get translation object
        _ = get_app()._tr

        # Get data model and selection
        model = self.clip_properties_model.model

        row = model_index.row()
        selected_label = model.item(row, 0)
        self.selected_item = model.item(row, 1)

        if selected_label:
            cur_property = selected_label.data()
            property_type = cur_property[1]["type"]

            if property_type == "color":
                # Get current value of color
                red = cur_property[1]["red"]["value"]
                green = cur_property[1]["green"]["value"]
                blue = cur_property[1]["blue"]["value"]

                # Show color dialog
                currentColor = QColor(red, green, blue)
                log.debug("Launching ColorPicker for %s", currentColor.name())
                ColorPicker(
                    currentColor, parent=self, title=_("Select a Color"),
                    callback=self.color_callback)
                return

            elif property_type == "font":
                # Get font from user
                current_font_name = cur_property[1].get("memo", "sans")
                current_font = QFont(current_font_name)
                font, ok = QFontDialog.getFont(current_font, caption=("Change Font"))

                # Update font
                if ok and font:
                    fontinfo = QFontInfo(font)
                    # TODO: pass font details to value_updated so we can set multiple values
                    font_details = { "font_family": fontinfo.family(),
                                     "font_style": fontinfo.styleName(),
                                     "font_weight": fontinfo.weight(),
                                     "font_size_pixel": fontinfo.pixelSize() }
                    self.clip_properties_model.value_updated(self.selected_item, value=fontinfo.family())

    def caption_text_updated(self, new_caption_text, caption_model_row):
        """Caption text has been updated in the caption editor, and needs saving"""
        if not caption_model_row:
            # Ignore blank selections
            return

        # Get data model and selection
        cur_property = caption_model_row[0].data()
        property_type = cur_property[1]["type"]

        # Save caption text
        if property_type == "caption" and cur_property[1].get('memo') != new_caption_text:
            self.clip_properties_model.value_updated(caption_model_row[1], value=new_caption_text)

    def select_item(self, item_id, item_type):
        """ Update the selected item in the properties window """

        # Get translation object
        _ = get_app()._tr

        # Update item
        self.clip_properties_model.update_item(item_id, item_type)

    def select_frame(self, frame_number):
        """ Update the values of the selected clip, based on the current frame """

        # Update item
        self.clip_properties_model.update_frame(frame_number)

    def filter_changed(self, value=None):
        """ Filter the list of properties """

        # Update property model (and re-trigger filter logic)
        self.clip_properties_model.update_model(value)

        # Filter keyframes visible on timeline
        get_app().window.SetKeyframeFilter.emit(value)

    def contextMenuEvent(self, event):
        """ Display context menu """
        # Get property being acted on
        index = self.indexAt(event.pos())
        if not index.isValid():
            event.ignore()
            return

        # Get data model and selection
        idx = self.indexAt(event.pos())
        row = idx.row()
        selected_label = idx.model().item(row, 0)
        selected_value = idx.model().item(row, 1)
        self.selected_item = selected_value
        frame_number = self.clip_properties_model.frame_number

        # Get translation object
        _ = get_app()._tr

        # If item selected
        if selected_label:
            # Clear menu if models updated
            if self.menu_reset:
                self.choices = []
                self.menu_reset = False

            # Get data from selected item
            cur_property = selected_label.data()
            property_name = cur_property[1]["name"]
            self.property_type = cur_property[1]["type"]
            points = cur_property[1]["points"]
            self.choices = cur_property[1]["choices"]
            property_key = cur_property[0]
            clip_id, item_type = selected_value.data()
            log.info("Context menu shown for %s (%s) for clip %s on frame %s" % (property_name, property_key, clip_id, frame_number))
            log.info("Points: %s" % points)

            # Handle parent effect options
            if property_key == "parent_effect_id" and not self.choices:
                clip_choices = [{
                    "name": "None",
                    "value": "None",
                    "selected": False,
                    "icon": QIcon()
                }]
                # Instantiate the timeline
                timeline_instance = get_app().window.timeline_sync.timeline
                # Instantiate this effect
                effect = timeline_instance.GetClipEffect(clip_id)
                effect_json = json.loads(effect.Json())

                # Loop through timeline's clips
                for clip_instance in timeline_instance.Clips():
                    clip_instance_id = clip_instance.Id()
                    # Avoid parent a clip effect to it's own effect
                    if (clip_instance_id != effect.ParentClipId()):
                        # Clip's propertyJSON data
                        clip_instance_data = Clip.get(id = clip_instance_id).data
                        # Path to the clip file
                        clip_instance_path = clip_instance_data["reader"]["path"]
                        # Iterate through all clip files on the timeline
                        for clip_number in range(self.files_model.rowCount()):
                            clip_index = self.files_model.index(clip_number, 0)
                            clip_name = clip_index.sibling(clip_number, 1).data()
                            clip_path = os.path.join(clip_index.sibling(clip_number, 4).data(), clip_name)
                            # Check if the timeline's clip file name matches the clip the user selected
                            if (clip_path == clip_instance_path):
                                # Generate the clip icon to show in the selection menu
                                clip_instance_icon = clip_index.data(Qt.DecorationRole)
                        effect_choices = [{"name": "None",
                                            "value": "None",
                                            "selected": False,
                                            "icon": QIcon()}]
                        # Iterate through clip's effects
                        for effect_data in clip_instance_data["effects"]:
                            # Make sure the user can only set a parent effect of the same type as this effect
                            if effect_data['class_name'] == effect_json['class_name']:
                                effect_id = effect_data["id"]
                                effect_name = effect_data['class_name']
                                effect_icon = QIcon(QPixmap(os.path.join(info.PATH, "effects", "icons", "%s.png" % effect_data['class_name'].lower())))
                                effect_choices.append({"name": effect_id,
                                                "value": effect_id,
                                                "selected": False,
                                                "icon": effect_icon})
                        self.choices.append({"name": _(clip_instance_data["title"]),
                                            "value": effect_choices,
                                            "selected": False,
                                            "icon": clip_instance_icon})


            # Handle selected object options (ObjectDetection effect)
            if property_key == "selected_object_index" and not self.choices:
                # Get all visible object's indexes
                timeline_instance = get_app().window.timeline_sync.timeline
                # Instantiate the effect
                effect = timeline_instance.GetClipEffect(clip_id)
                # Get the indexes and IDs of the visible objects
                visible_objects = json.loads(effect.GetVisibleObjects(frame_number))
                # Add visible objects as choices
                object_index_choices = []
                for object_index in visible_objects["visible_objects_index"]:
                    object_index_choices.append({
                                "name": str(object_index),
                                "value": str(object_index),
                                "selected": False,
                                "icon": QIcon()
                            })
                self.choices.append({"name": _("Detected Objects"), "value": object_index_choices, "selected": False, "icon": None})

            # Handle property to set the Tracked Object's child clip
            if property_key == "child_clip_id" and not self.choices:
                clip_choices = [{
                    "name": "None",
                    "value": "None",
                    "selected": False,
                    "icon": QIcon()
                }]
                # Instantiate the timeline
                timeline_instance = get_app().window.timeline_sync.timeline
                current_effect = timeline_instance.GetClipEffect(clip_id)

                # Loop through timeline's clips
                for clip_instance in timeline_instance.Clips():
                    clip_instance_id = clip_instance.Id()

                    # Avoid attach a clip to it's own object
                    if (clip_instance_id != clip_id and (current_effect and clip_instance_id != current_effect.ParentClip().Id())):
                        # Clip's propertyJSON data
                        clip_instance_data = Clip.get(id = clip_instance_id).data
                        # Path to the clip file
                        clip_instance_path = clip_instance_data["reader"]["path"]
                        # Iterate through all clip files on the timeline
                        for clip_number in range(self.files_model.rowCount()):
                            clip_index = self.files_model.index(clip_number, 0)
                            clip_name = clip_index.sibling(clip_number, 1).data()
                            clip_path = os.path.join(clip_index.sibling(clip_number, 4).data(), clip_name)
                            # Check if the timeline's clip file name matches the clip the user selected
                            if (clip_path == clip_instance_path):
                                # Generate the clip icon to show in the selection menu
                                clip_instance_icon = clip_index.data(Qt.DecorationRole)
                                self.choices.append({"name": clip_instance_data["title"],
                                              "value": clip_instance_id,
                                              "selected": False,
                                              "icon": clip_instance_icon})

            # Handle clip attach options
            if property_key == "parentObjectId" and not self.choices:
                # Add all Clips as choices - initialize with None
                tracked_choices = [{
                    "name": "None",
                    "value": "None",
                    "selected": False,
                    "icon": QIcon()
                }]
                clip_choices = [{
                    "name": "None",
                    "value": "None",
                    "selected": False,
                    "icon": QIcon()
                }]
                # Instantiate the timeline
                timeline_instance = get_app().window.timeline_sync.timeline
                # Loop through timeline's clips
                for clip_instance in timeline_instance.Clips():
                    clip_instance_id = clip_instance.Id()
                    # Avoid attach a clip to it's own object
                    if (clip_instance_id != clip_id):
                        # Clip's propertyJSON data
                        clip_instance_data = Clip.get(id = clip_instance_id).data
                        # Path to the clip file
                        clip_instance_path = clip_instance_data["reader"]["path"]
                        # Iterate through all clip files on the timeline
                        for clip_number in range(self.files_model.rowCount()):
                            clip_index = self.files_model.index(clip_number, 0)
                            clip_name = clip_index.sibling(clip_number, 1).data()
                            clip_path = os.path.join(clip_index.sibling(clip_number, 4).data(), clip_name)
                            # Check if the timeline's clip file name matches the clip the user selected
                            if (clip_path == clip_instance_path):
                                # Generate the clip icon to show in the selection menu
                                clip_instance_icon = clip_index.data(Qt.DecorationRole)
                                clip_choices.append({"name": clip_instance_data["title"],
                                              "value": clip_instance_id,
                                              "selected": False,
                                              "icon": clip_instance_icon})
                        # Get the pixmap of the clip icon
                        icon_size = 72
                        icon_pixmap = clip_instance_icon.pixmap(icon_size, icon_size)
                        # Add tracked objects to the selection menu
                        tracked_objects = []
                        for effect in clip_instance_data["effects"]:
                            # Check if effect has a tracked object
                            if effect.get("has_tracked_object"):
                                # Instantiate the effect
                                effect_instance = timeline_instance.GetClipEffect(effect["id"])
                                # Get the visible object's ids
                                visible_objects_id = json.loads(effect_instance.GetVisibleObjects(frame_number))["visible_objects_id"]
                                for object_id in visible_objects_id:
                                    # Get the Tracked Object properties
                                    object_properties = json.loads(timeline_instance.GetTrackedObjectValues(object_id, 0))
                                    x1 = object_properties['x1']
                                    y1 = object_properties['y1']
                                    x2 = object_properties['x2']
                                    y2 = object_properties['y2']
                                    # Get the tracked object's icon from the clip's icon
                                    tracked_object_icon = icon_pixmap.copy(QRect(x1*icon_size, y1*icon_size, (x2-x1)*icon_size, (y2-y1)*icon_size)).scaled(icon_size, icon_size)
                                    tracked_objects.append({"name": str(object_id),
                                                            "value": str(object_id),
                                                            "selected": False,
                                                            "icon": QIcon(tracked_object_icon)})
                        tracked_choices.append({"name": clip_instance_data["title"],
                                              "value": tracked_objects,
                                              "selected": False,
                                              "icon": clip_instance_icon})
                self.choices.append({"name": _("Tracked Objects"), "value": tracked_choices, "selected": False, "icon": None})
                self.choices.append({"name": _("Clips"), "value": clip_choices, "selected": False, "icon": None})

            # Handle reader type values
            if self.property_type == "reader" and not self.choices:
                # Add all files
                file_choices = []
                for i in range(self.files_model.rowCount()):
                    idx = self.files_model.index(i, 0)
                    if not idx.isValid():
                        continue
                    icon = idx.data(Qt.DecorationRole)
                    name = idx.sibling(i, 1).data()
                    path = os.path.join(idx.sibling(i, 4).data(), name)

                    # Append file choice
                    file_choices.append({"name": name,
                                         "value": path,
                                         "selected": False,
                                         "icon": icon
                                         })

                # Add root file choice
                self.choices.append({"name": _("Files"), "value": file_choices, "selected": False, icon: None})

                # Add all transitions
                trans_choices = []
                for i in range(self.transition_model.rowCount()):
                    idx = self.transition_model.index(i, 0)
                    if not idx.isValid():
                        continue
                    icon = idx.data(Qt.DecorationRole)
                    name = idx.sibling(i, 1).data()
                    path = idx.sibling(i, 3).data()

                    # Append transition choice
                    trans_choices.append({"name": name,
                                          "value": path,
                                          "selected": False,
                                          "icon": icon
                                          })

                # Add root transitions choice
                self.choices.append({"name": _("Transitions"), "value": trans_choices, "selected": False})

            # Handle reader type values
            if property_name == "Track" and self.property_type == "int" and not self.choices:
                # Populate all display track names
                all_tracks = get_app().project.get("layers")
                display_count = len(all_tracks)
                for track in reversed(sorted(all_tracks, key=itemgetter('number'))):
                    # Append track choice
                    track_name = track.get("label") or _("Track %s") % display_count
                    self.choices.append({"name": track_name, "value": track.get("number"), "selected": False, "icon": None})
                    display_count -= 1
                return

            elif self.property_type == "font":
                # Get font from user
                current_font_name = cur_property[1].get("memo", "sans")
                current_font = QFont(current_font_name)
                font, ok = QFontDialog.getFont(current_font, caption=("Change Font"))

                # Update font
                if ok and font:
                    fontinfo = QFontInfo(font)
                    self.clip_properties_model.value_updated(self.selected_item, value=fontinfo.family())

            # Define bezier presets
            bezier_presets = [
                (0.250, 0.100, 0.250, 1.000, _("Ease (Default)")),
                (0.420, 0.000, 1.000, 1.000, _("Ease In")),
                (0.000, 0.000, 0.580, 1.000, _("Ease Out")),
                (0.420, 0.000, 0.580, 1.000, _("Ease In/Out")),

                (0.550, 0.085, 0.680, 0.530, _("Ease In (Quad)")),
                (0.550, 0.055, 0.675, 0.190, _("Ease In (Cubic)")),
                (0.895, 0.030, 0.685, 0.220, _("Ease In (Quart)")),
                (0.755, 0.050, 0.855, 0.060, _("Ease In (Quint)")),
                (0.470, 0.000, 0.745, 0.715, _("Ease In (Sine)")),
                (0.950, 0.050, 0.795, 0.035, _("Ease In (Expo)")),
                (0.600, 0.040, 0.980, 0.335, _("Ease In (Circ)")),
                (0.600, -0.280, 0.735, 0.045, _("Ease In (Back)")),

                (0.250, 0.460, 0.450, 0.940, _("Ease Out (Quad)")),
                (0.215, 0.610, 0.355, 1.000, _("Ease Out (Cubic)")),
                (0.165, 0.840, 0.440, 1.000, _("Ease Out (Quart)")),
                (0.230, 1.000, 0.320, 1.000, _("Ease Out (Quint)")),
                (0.390, 0.575, 0.565, 1.000, _("Ease Out (Sine)")),
                (0.190, 1.000, 0.220, 1.000, _("Ease Out (Expo)")),
                (0.075, 0.820, 0.165, 1.000, _("Ease Out (Circ)")),
                (0.175, 0.885, 0.320, 1.275, _("Ease Out (Back)")),

                (0.455, 0.030, 0.515, 0.955, _("Ease In/Out (Quad)")),
                (0.645, 0.045, 0.355, 1.000, _("Ease In/Out (Cubic)")),
                (0.770, 0.000, 0.175, 1.000, _("Ease In/Out (Quart)")),
                (0.860, 0.000, 0.070, 1.000, _("Ease In/Out (Quint)")),
                (0.445, 0.050, 0.550, 0.950, _("Ease In/Out (Sine)")),
                (1.000, 0.000, 0.000, 1.000, _("Ease In/Out (Expo)")),
                (0.785, 0.135, 0.150, 0.860, _("Ease In/Out (Circ)")),
                (0.680, -0.550, 0.265, 1.550, _("Ease In/Out (Back)"))
            ]

            # Add menu options for keyframes
            menu = QMenu(self)
            if self.property_type == "color":
                Color_Action = menu.addAction(_("Select a Color"))
                Color_Action.triggered.connect(functools.partial(self.Color_Picker_Triggered, cur_property))
                menu.addSeparator()
            if points > 1:
                # Menu items only for multiple points
                Bezier_Menu = menu.addMenu(self.bezier_icon, _("Bezier"))
                for bezier_preset in bezier_presets:
                    preset_action = Bezier_Menu.addAction(bezier_preset[4])
                    preset_action.triggered.connect(functools.partial(
                        self.Bezier_Action_Triggered, bezier_preset))
                Linear_Action = menu.addAction(self.linear_icon, _("Linear"))
                Linear_Action.triggered.connect(self.Linear_Action_Triggered)
                Constant_Action = menu.addAction(self.constant_icon, _("Constant"))
                Constant_Action.triggered.connect(self.Constant_Action_Triggered)
                menu.addSeparator()
            if points >= 1:
                # Menu items for one or more points
                Insert_Action = menu.addAction(_("Insert Keyframe"))
                Insert_Action.triggered.connect(self.Insert_Action_Triggered)
                Remove_Action = menu.addAction(_("Remove Keyframe"))
                Remove_Action.triggered.connect(self.Remove_Action_Triggered)
                menu.popup(event.globalPos())

            # Menu for choices
            if not self.choices:
                return
            for choice in self.choices:
                if type(choice["value"]) != list:
                    # Just add root choice item
                    Choice_Action = menu.addAction(_(choice["name"]))
                    Choice_Action.setData(choice["value"])
                    Choice_Action.triggered.connect(self.Choice_Action_Triggered)
                    continue

                # Add sub-choice items (for nested choice lists)
                # Divide into smaller QMenus (since large lists cover the entire screen)
                # For example: Transitions -> 1 -> sub items
                SubMenu = None
                if choice.get("icon") is not None:
                    SubMenuRoot = menu.addMenu(choice["icon"], choice["name"])
                else:
                    SubMenuRoot = menu.addMenu(choice["name"])

                SubMenuSize = 25
                SubMenuNumber = 0
                if len(choice["value"]) > SubMenuSize:
                    SubMenu = SubMenuRoot.addMenu(str(SubMenuNumber))
                else:
                    SubMenu = SubMenuRoot
                for i, sub_choice in enumerate(choice["value"], 1):
                    # Divide SubMenu if it's item is a list
                    if type(sub_choice["value"]) == list:
                        SubSubMenu = SubMenu.addMenu(sub_choice["icon"], sub_choice["name"])
                        for sub_sub_choice in sub_choice["value"]:
                            Choice_Action = SubSubMenu.addAction(
                                sub_sub_choice["icon"], sub_sub_choice["name"])
                            Choice_Action.setData(sub_sub_choice["value"])
                            Choice_Action.triggered.connect(self.Choice_Action_Triggered)
                    else:
                        if i % SubMenuSize == 0:
                            SubMenuNumber += 1
                            SubMenu = SubMenuRoot.addMenu(str(SubMenuNumber))
                        Choice_Action = SubMenu.addAction(
                            sub_choice["icon"], _(sub_choice["name"]))
                        Choice_Action.setData(sub_choice["value"])
                        Choice_Action.triggered.connect(self.Choice_Action_Triggered)

            # Show choice menuk
            menu.popup(event.globalPos())

    def Bezier_Action_Triggered(self, preset=[]):
        log.info("Bezier_Action_Triggered: %s" % str(preset))
        if self.property_type != "color":
            # Update keyframe interpolation mode
            self.clip_properties_model.value_updated(self.selected_item, interpolation=0, interpolation_details=preset)
        else:
            # Update colors interpolation mode
            self.clip_properties_model.color_update(self.selected_item, QColor("#000"), interpolation=0, interpolation_details=preset)

    def Linear_Action_Triggered(self):
        log.info("Linear_Action_Triggered")
        if self.property_type != "color":
            # Update keyframe interpolation mode
            self.clip_properties_model.value_updated(self.selected_item, interpolation=1)
        else:
            # Update colors interpolation mode
            self.clip_properties_model.color_update(self.selected_item, QColor("#000"), interpolation=1, interpolation_details=[])

    def Constant_Action_Triggered(self):
        log.info("Constant_Action_Triggered")
        if self.property_type != "color":
            # Update keyframe interpolation mode
            self.clip_properties_model.value_updated(self.selected_item, interpolation=2)
        else:
            # Update colors interpolation mode
            self.clip_properties_model.color_update(self.selected_item, QColor("#000"), interpolation=2, interpolation_details=[])

    def Color_Picker_Triggered(self, cur_property):
        log.info("Color_Picker_Triggered")

        _ = get_app()._tr

        # Get current value of color
        red = int(cur_property[1]["red"]["value"])
        green = int(cur_property[1]["green"]["value"])
        blue = int(cur_property[1]["blue"]["value"])

        # Show color dialog
        currentColor = QColor(red, green, blue)
        log.debug("Launching ColorPicker for %s", currentColor.name())
        ColorPicker(
            currentColor, parent=self, title=_("Select a Color"),
            callback=self.color_callback)

    def Insert_Action_Triggered(self):
        log.info("Insert_Action_Triggered")
        if self.selected_item:
            current_value = QLocale().system().toDouble(self.selected_item.text())[0]
            self.clip_properties_model.value_updated(self.selected_item, value=current_value)

    def Remove_Action_Triggered(self):
        log.info("Remove_Action_Triggered")
        self.clip_properties_model.remove_keyframe(self.selected_item)

    def Choice_Action_Triggered(self):
        log.info("Choice_Action_Triggered")
        choice_value = self.sender().data()

        # Update value of dropdown item
        self.clip_properties_model.value_updated(self.selected_item, value=choice_value)

    def refresh_menu(self):
        """ Ensure we update the menu when our source models change """
        self.menu_reset = True

    def __init__(self, *args):
        # Invoke parent init
        QTableView.__init__(self, *args)

        # Get a reference to the window object
        self.win = get_app().window

        # Create properties model
        self.clip_properties_model = PropertiesModel(self)

        # Get base models for files, transitions
        self.transition_model = self.win.transition_model.model
        self.files_model = self.win.files_model.model

        # Connect to update signals, so our menus stay current
        self.files_model.dataChanged.connect(self.refresh_menu)
        self.win.transition_model.ModelRefreshed.connect(self.refresh_menu)
        self.menu_reset = False

        # Keep track of mouse press start position to determine when to start drag
        self.selected = []
        self.selected_label = None
        self.selected_item = None
        self.new_value = None
        self.original_data = None
        self.lock_selection = False
        self.prev_row = None

        # Context menu icons
        self.bezier_icon = QIcon(QPixmap(os.path.join(info.IMAGES_PATH, "keyframe-%s.png" % openshot.BEZIER)))
        self.linear_icon = QIcon(QPixmap(os.path.join(info.IMAGES_PATH, "keyframe-%s.png" % openshot.LINEAR)))
        self.constant_icon = QIcon(QPixmap(os.path.join(info.IMAGES_PATH, "keyframe-%s.png" % openshot.CONSTANT)))

        # Setup header columns
        self.setModel(self.clip_properties_model.model)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setWordWrap(True)

        # Set delegate
        delegate = PropertyDelegate(model=self.clip_properties_model.model)
        self.setItemDelegateForColumn(1, delegate)
        self.previous_x = -1

        # Get table header
        horizontal_header = self.horizontalHeader()
        horizontal_header.setSectionResizeMode(QHeaderView.Stretch)
        vertical_header = self.verticalHeader()
        vertical_header.setVisible(False)

        # Refresh view
        self.clip_properties_model.update_model()

        # Resize columns
        self.resizeColumnToContents(0)
        self.resizeColumnToContents(1)

        # Connect filter signals
        get_app().window.txtPropertyFilter.textChanged.connect(self.filter_changed)
        get_app().window.InsertKeyframe.connect(self.Insert_Action_Triggered)
        self.doubleClicked.connect(self.doubleClickedCB)
        self.loadProperties.connect(self.select_item)
        get_app().window.CaptionTextUpdated.connect(self.caption_text_updated)


class SelectionLabel(QFrame):
    """ The label to display selections """

    def getMenu(self):
        # Build menu for selection button
        menu = QMenu(self)

        # Get translation object
        _ = get_app()._tr

        # Look up item for more info
        if self.item_type == "clip":
            item = Clip.get(id=self.item_id)
            if item:
                self.item_name = item.title()
        elif self.item_type == "transition":
            item = Transition.get(id=self.item_id)
            if item:
                self.item_name = item.title()
        elif self.item_type == "effect":
            item = Effect.get(id=self.item_id)
            if item:
                self.item_name = item.title()

        # Bail if no item name was found
        if not self.item_name:
            return

        # Add selected clips
        for item_id in get_app().window.selected_clips:
            clip = Clip.get(id=item_id)
            if clip:
                item_name = clip.title()
                item_icon = QIcon(QPixmap(clip.data.get('image')))
                action = menu.addAction(item_icon, item_name)
                action.setData({'item_id': item_id, 'item_type': 'clip'})
                action.triggered.connect(self.Action_Triggered)

                # Add effects for these clips (if any)
                for effect in clip.data.get('effects'):
                    effect = Effect.get(id=effect.get('id'))
                    if effect:
                        item_name = effect.title()
                        item_icon = QIcon(QPixmap(os.path.join(info.PATH, "effects", "icons", "%s.png" % effect.data.get('class_name').lower())))
                        action = menu.addAction(item_icon, '  >  %s' % _(item_name))
                        action.setData({'item_id': effect.id, 'item_type': 'effect'})
                        action.triggered.connect(self.Action_Triggered)

        # Add selected transitions
        for item_id in get_app().window.selected_transitions:
            trans = Transition.get(id=item_id)
            if trans:
                item_name = _(trans.title())
                item_icon = QIcon(QPixmap(trans.data.get('reader', {}).get('path')))
                action = menu.addAction(item_icon, _(item_name))
                action.setData({'item_id': item_id, 'item_type': 'transition'})
                action.triggered.connect(self.Action_Triggered)

        # Add selected effects
        for item_id in get_app().window.selected_effects:
            effect = Effect.get(id=item_id)
            if effect:
                item_name = _(effect.title())
                item_icon = QIcon(QPixmap(os.path.join(info.PATH, "effects", "icons", "%s.png" % effect.data.get('class_name').lower())))
                action = menu.addAction(item_icon, _(item_name))
                action.setData({'item_id': item_id, 'item_type': 'effect'})
                action.triggered.connect(self.Action_Triggered)

        # Return the menu object
        return menu

    def Action_Triggered(self):
        # Switch selection
        item_id = self.sender().data()['item_id']
        item_type = self.sender().data()['item_type']
        log.info('switch selection to %s:%s' % (item_id, item_type))

        # Set the property tableview to the new item
        get_app().window.propertyTableView.loadProperties.emit(item_id, item_type)

    # Update selected item label
    def select_item(self, item_id, item_type):
        self.item_name = None
        self.item_icon = None
        self.item_type = item_type
        self.item_id = item_id

        # Get translation object
        _ = get_app()._tr

        # Look up item for more info
        if self.item_type == "clip":
            clip = Clip.get(id=self.item_id)
            if clip:
                self.item_name = clip.title()
                self.item_icon = QIcon(QPixmap(clip.data.get('image')))
        elif self.item_type == "transition":
            trans = Transition.get(id=self.item_id)
            if trans:
                self.item_name = _(trans.title())
                self.item_icon = QIcon(QPixmap(trans.data.get('reader', {}).get('path')))
        elif self.item_type == "effect":
            effect = Effect.get(id=self.item_id)
            if effect:
                self.item_name = _(effect.title())
                self.item_icon = QIcon(QPixmap(os.path.join(info.PATH, "effects", "icons", "%s.png" % effect.data.get('class_name').lower())))

        # Truncate long text
        if self.item_name and len(self.item_name) > 25:
            self.item_name = "%s..." % self.item_name[:22]

        # Set label
        if self.item_id:
            self.lblSelection.setText("<strong>%s</strong>" % _("Selection:"))
            self.btnSelectionName.setText(self.item_name)
            self.btnSelectionName.setVisible(True)
            if self.item_icon:
                self.btnSelectionName.setIcon(self.item_icon)
        else:
            self.lblSelection.setText("<strong>%s</strong>" % _("No Selection"))
            self.btnSelectionName.setVisible(False)

        # Set the menu on the button
        self.btnSelectionName.setMenu(self.getMenu())

    def __init__(self, *args):
        # Invoke parent init
        super().__init__(*args)
        self.item_id = None
        self.item_type = None

        # Get translation object
        _ = get_app()._tr

        # Widgets
        self.lblSelection = QLabel()
        self.lblSelection.setText("<strong>%s</strong>" % _("No Selection"))
        self.btnSelectionName = QPushButton()
        self.btnSelectionName.setVisible(False)
        self.btnSelectionName.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        # Support rich text
        self.lblSelection.setTextFormat(Qt.RichText)

        hbox = QHBoxLayout()
        hbox.setContentsMargins(0, 0, 0, 0)
        hbox.addWidget(self.lblSelection)
        hbox.addWidget(self.btnSelectionName)
        self.setLayout(hbox)

        # Connect signals
        get_app().window.propertyTableView.loadProperties.connect(self.select_item)
