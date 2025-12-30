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
import sip
import uuid

from PyQt5.QtCore import Qt, QRectF, QLocale, pyqtSignal, pyqtSlot, QEvent, QPoint
from PyQt5.QtGui import (
    QIcon, QColor, QBrush, QPen, QPalette, QPixmap,
    QPainter, QPainterPath, QLinearGradient, QFont, QFontInfo, QCursor,
)
from PyQt5.QtWidgets import (
    QTableView, QAbstractItemView, QSizePolicy,
    QHeaderView, QItemDelegate, QStyle, QLabel,
    QPushButton, QHBoxLayout, QFrame, QFontDialog
)

from classes.logger import log
from classes.app import get_app
from classes import info
from classes.query import Clip, Effect, Transition, File
from classes.thumbnail import GetThumbPath

from windows.models.properties_model import PropertiesModel
from windows.color_picker import ColorPicker
from .menu import StyledContextMenu

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

        # Get theme colors
        if get_app().theme_manager:
            theme = get_app().theme_manager.get_current_theme()
            if not theme:
                log.warning("No theme loaded yet. Skip rendering properties widget.")
                return
            foreground_color = theme.get_color(".property_value", "foreground-color")
            background_color = theme.get_color(".property_value", "background-color")
        else:
            log.warning("No ThemeManager loaded yet. Skip rendering properties widget.")

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
                painter.setBrush(background_color)
            else:
                painter.setBrush(background_color)

        if readonly:
            # Set text color for read only fields
            painter.setPen(QPen(get_app().window.palette().color(QPalette.Disabled, QPalette.Text)))
        else:
            path = QPainterPath()
            path.addRoundedRect(QRectF(option.rect), 15, 15)
            painter.fillPath(path, background_color)
            painter.drawPath(path)

            # Render mask rectangle
            painter.setBrush(QBrush(QColor("#000000")))
            mask_rect = QRectF(option.rect)
            mask_rect.setWidth(option.rect.width() * value_percent)
            painter.setClipRect(mask_rect, Qt.IntersectClip)

            # gradient for value box
            gradient = QLinearGradient(option.rect.topLeft(), option.rect.topRight())
            gradient.setColorAt(0, foreground_color)
            gradient.setColorAt(1, foreground_color)

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
    loadProperties = pyqtSignal(list)

    def event(self, event):
        # intercept the ShortcutOverride so our "." and "," keys
        # never reach the global QShortcuts when this view has focus
        if event.type() == QEvent.ShortcutOverride and self.hasFocus():
            key = event.key()
            if key in (Qt.Key_Period, Qt.Key_Comma):
                event.accept()
                return True
        # otherwise, default processing
        return super().event(event)

    def start_transaction(self, item):
        """Start a new undo/redo transaction and cache original values."""
        if (
            self.transaction_id
            or not item
            or self.clip_properties_model.ignore_update_signal
        ):
            return

        item_data = item.data()
        if not isinstance(item_data, list):
            return

        self.transaction_id = str(uuid.uuid4())
        get_app().updates.transaction_id = self.transaction_id
        get_app().updates.ignore_history = True

        self.original_data_map = {}

        for item_id, item_type in item_data:
            obj = None
            if item_type == "clip":
                obj = Clip.get(id=item_id)
            elif item_type == "transition":
                obj = Transition.get(id=item_id)
            elif item_type == "effect":
                obj = Effect.get(id=item_id)

            if obj and obj.data:
                self.original_data_map[item_id] = {
                    "type": item_type,
                    "data": json.loads(json.dumps(obj.data)),
                }

    def finalize_transaction(self):
        """Finalize current transaction and add actions to history."""
        if not self.transaction_id:
            return

        for item_id, info in self.original_data_map.items():
            item_type = info.get("type")
            original = info.get("data")
            obj = None
            if item_type == "clip":
                obj = Clip.get(id=item_id)
            elif item_type == "transition":
                obj = Transition.get(id=item_id)
            elif item_type == "effect":
                obj = Effect.get(id=item_id)

            if obj:
                get_app().updates.ignore_history = True
                get_app().updates.transaction_id = self.transaction_id
                obj.save()
                get_app().updates.apply_last_action_to_history(original)
                get_app().updates.ignore_history = False

        get_app().updates.transaction_id = None
        self.transaction_id = None
        self.original_data_map = {}
        self.update_in_progress = False

    def value_updated_wrapper(self, item):
        """Wrap PropertiesModel.value_updated to manage transactions."""
        if (
            self.clip_properties_model.ignore_update_signal
            or not item
            or item.column() != 1
        ):
            return

        self.start_transaction(item)
        self.update_in_progress = True
        self.clip_properties_model.value_updated(item)
        if not self.mouse_pressed:
            self.finalize_transaction()

    def mousePressEvent(self, event):
        self.mouse_pressed = True
        row = self.indexAt(event.pos()).row()
        model = self.clip_properties_model.model
        if model.item(row, 1):
            self.selected_item = model.item(row, 1)
            if not self.clip_properties_model.ignore_update_signal:
                self.start_transaction(self.selected_item)
        super().mousePressEvent(event)

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

        # Verify label has not been deleted
        if (self.selected_label and sip.isdeleted(self.selected_label)) or \
                (self.selected_item and sip.isdeleted(self.selected_item)):
            log.debug("Property has been deleted, skipping")
            self.selected_label = None
            self.selected_item = None

        # Is the user dragging on the value column
        if self.selected_label and self.selected_item and \
                self.selected_label.data() and type(self.selected_label.data()) == tuple:
            # Ignore undo/redo history temporarily (to avoid a huge pile of undo/redo history)
            get_app().updates.ignore_history = True

            # Disable video caching during drag operation (for performance reasons)
            openshot.Settings.Instance().ENABLE_PLAYBACK_CACHING = False
            log.debug('mouseMoveEvent: Stop caching frames on timeline')

            # Get the position of the cursor and % value
            value_column_x = self.columnViewportPosition(1)
            cursor_value = event.x() - value_column_x
            cursor_value_percent = cursor_value / self.columnWidth(1)

            # Get data from selected item
            try:
                cur_property = self.selected_label.data()
            except Exception:
                log.debug('Failed to access data on selected label widget')
                return

            if type(cur_property) != tuple:
                log.debug('Failed to access valid data on current selected label widget')
                return

            property_key = cur_property[0]
            property_name = cur_property[1]["name"]
            property_type = cur_property[1]["type"]
            property_max = cur_property[1]["max"]
            property_min = cur_property[1]["min"]
            readonly = cur_property[1]["readonly"]

            # Bail if readonly
            if readonly:
                return

            if (
                not self.transaction_id
                and not self.clip_properties_model.ignore_update_signal
            ):
                # Start transaction on first movement
                self.start_transaction(self.selected_item)
            self.update_in_progress = True

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
        self.mouse_pressed = False

        # Enable video caching again
        openshot.Settings.Instance().ENABLE_PLAYBACK_CACHING = True
        log.debug('mouseReleaseEvent: apply_last_action to history')

        if self.update_in_progress:
            self.finalize_transaction()

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
            log.debug(f"Color callback received: {newColor.name()}, Alpha: {newColor.alpha()}")
            if not self.clip_properties_model.ignore_update_signal:
                self.start_transaction(self.selected_item)
            self.update_in_progress = True
            self.clip_properties_model.color_update(
                self.selected_item, newColor)
            if not self.mouse_pressed:
                self.finalize_transaction()

    def doubleClickedCB(self, model_index):
        """Double click handler for the property table"""

        # Get translation object
        _ = get_app()._tr

        # Get data model and selection
        model = self.clip_properties_model.model

        row = model_index.row()
        selected_label = model.item(row, 0)
        self.selected_item = model.item(row, 1)

        if selected_label and selected_label.data() and type(selected_label.data()) == tuple:
            cur_property = selected_label.data()
            property_type = cur_property[1]["type"]

            if property_type == "color":
                # Get current value of color
                red = cur_property[1]["red"]["value"]
                green = cur_property[1]["green"]["value"]
                blue = cur_property[1]["blue"]["value"]
                # Get alpha value (if present) or default to fully opaque
                alpha = cur_property[1].get("alpha", {}).get("value", 255)

                # Show color dialog with alpha support
                try:
                    # Create color with alpha
                    currentColor = QColor(int(red), int(green), int(blue), int(alpha))
                except (ValueError, TypeError):
                    # Default to opaque red if conversion fails
                    currentColor = QColor(255, 0, 0, 255)

                ColorPicker(
                    currentColor, parent=self.win, title=_("Select a Color"),
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
                    if not self.clip_properties_model.ignore_update_signal:
                        self.start_transaction(self.selected_item)
                    self.update_in_progress = True
                    self.clip_properties_model.value_updated(self.selected_item, value=fontinfo.family())
                    if not self.mouse_pressed:
                        self.finalize_transaction()

    def caption_text_updated(self, new_caption_text, caption_model_row):
        """Caption text has been updated in the caption editor, and needs saving"""
        if not caption_model_row:
            # Ignore blank selections
            return

        caption_model_label = caption_model_row[0]
        caption_model_value = caption_model_row[1]

        # Verify label has not been deleted
        if (caption_model_label and sip.isdeleted(caption_model_label)) or \
                (caption_model_value and sip.isdeleted(caption_model_value)):
            log.debug("Property has been deleted, skipping")
            return

        # Get data model and selection
        cur_property = caption_model_label.data()
        property_type = cur_property[1]["type"]

        # Save caption text
        if property_type == "caption" and cur_property[1].get('memo') != new_caption_text:
            self.start_transaction(caption_model_value)
            self.update_in_progress = True
            self.clip_properties_model.value_updated(caption_model_value, value=new_caption_text)
            if not self.mouse_pressed:
                self.finalize_transaction()

    def select_item(self, selection):
        """Update the selected items in the properties window"""

        _ = get_app()._tr

        self.clip_properties_model.update_item(selection)

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

        # Skip any read-only properties
        cur_property = selected_label.data()
        readonly = cur_property[1]["readonly"]
        if readonly:
            return

        # Get translation object
        _ = get_app()._tr

        # If item selected
        if selected_label and selected_label.data() and type(selected_label.data()) == tuple:
            cur_property = selected_label.data()

            # Clear menu if models updated
            if self.menu_reset:
                self.choices = []
                self.menu_reset = False

            property_name = cur_property[1]["name"]
            self.property_type = cur_property[1]["type"]
            points = cur_property[1]["points"]
            self.choices = cur_property[1]["choices"]
            property_key = cur_property[0]

            for item_id, item_type in selected_value.data():
                log.info("Context menu shown for %s (%s) for item %s on frame %s" % (property_name, property_key, item_id, frame_number))
                log.info("Points: %s" % points)

                # Handle parent effect options
                if property_key == "parent_effect_id" and not self.choices:
                    # Instantiate this effect
                    effect = Effect.get(id=item_id)
                    if not effect:
                        return

                    # Loop through timeline's clips
                    clip_choices = []
                    for clip in Clip.filter():
                        file_id = clip.data.get("file_id")

                        # Look up parent clip id (if effect)
                        parent_clip_id = effect.parent.get("id")

                        # Avoid attach a clip to it's own object
                        if clip.id != parent_clip_id:
                            # Iterate through all project files (to find matching QIcon)
                            for file_index in range(self.files_model.rowCount()):
                                file_row = self.files_model.index(file_index, 0)
                                project_file_id = file_row.sibling(file_index, 5).data()
                                if file_id == project_file_id:
                                    clip_instance_icon = file_row.data(Qt.DecorationRole)
                                    break

                            effect_choices = []
                            # Iterate through clip's effects
                            for clip_effect_data in clip.data["effects"]:
                                # Make sure the user can only set a parent effect of the same type as this effect
                                if clip_effect_data['class_name'] == effect.data['class_name']:
                                    effect_id = clip_effect_data["id"]
                                    effect_icon = QIcon(QPixmap(os.path.join(info.PATH, "effects", "icons", "%s.png" % clip_effect_data['class_name'].lower())))
                                    effect_choices.append({"name": effect_id,
                                                    "value": effect_id,
                                                    "selected": False,
                                                    "icon": effect_icon})
                            if effect_choices:
                                clip_choices.append({"name": _(clip.data["title"]),
                                                    "value": effect_choices,
                                                    "selected": False,
                                                    "icon": clip_instance_icon})

                    self.choices.append({"name": _("None"), "value": "None", "selected": False, "icon": None})
                    if clip_choices:
                        self.choices.append({"name": _("Clips"), "value": clip_choices, "selected": False, "icon": None})

                # Handle selected object options (ObjectDetection effect)
                if property_key in ["selected_object_index", "class_filter"] and not self.choices:
                    if property_key == "class_filter":
                        # Use only class_name (if it has not already been added to the choices)
                        tracked_object_menu_name = _("Tracked Classes")
                        self.choices.append({"name": _("Clear"), "value": "", "selected": False, "icon": None})
                    else:
                        tracked_object_menu_name = _("Tracked Objects")

                    # Get all visible object's indexes
                    timeline_instance = get_app().window.timeline_sync.timeline
                    # Instantiate the effect
                    effect = timeline_instance.GetClipEffect(item_id)
                    # Get the indexes and IDs of the visible objects
                    visible_objects = json.loads(effect.GetVisibleObjects(frame_number))
                    # Add visible objects as choices
                    object_index_choices = []
                    for enum_index, object_index in enumerate(visible_objects["visible_objects_index"]):
                        class_name = visible_objects["visible_class_names"][enum_index]
                        object_name = f"{class_name}: {object_index}"
                        object_value = f"{object_index}"
                        skip_choice = False
                        if property_key == "class_filter":
                            # Use only class_name (if it has not already been added to the choices)
                            tracked_object_menu_name = _("Tracked Classes")
                            object_name = f"{class_name}"
                            object_value = f"{class_name}"
                            skip_choice = any(d.get('name') == class_name for d in object_index_choices)

                        if not skip_choice:
                            object_index_choices.append({
                                        "name": object_name,
                                        "value": object_value,
                                        "selected": False,
                                        "icon": None
                                    })
                    if object_index_choices:
                        self.choices.append({"name": tracked_object_menu_name, "value": object_index_choices, "selected": False, "icon": None})

                # Handle clip attach options
                if property_key in ["parentObjectId"] and not self.choices:
                    # Add all Clips as choices - initialize with None
                    tracked_choices = []
                    clip_choices = []
                    # Instantiate the timeline
                    timeline_instance = get_app().window.timeline_sync.timeline
                    # Loop through timeline's clips
                    for clip in Clip.filter():
                        file_id = clip.data.get("file_id")

                        # Look up parent clip id (if effect)
                        parent_clip_id = item_id
                        if item_type == "effect":
                            parent_clip_id = Effect.get(id=item_id).parent.get("id")
                            log.debug(f"Lookup parent clip ID for effect: '{item_id}' = '{parent_clip_id}'")

                        # Skip attaching to itself
                        if clip.id == parent_clip_id:
                            continue

                        # Get the file's icon
                        clip_icon = None
                        for row in range(self.files_model.rowCount()):
                            idx = self.files_model.index(row, 0)
                            if idx.sibling(row, 5).data() == file_id:
                                clip_icon = idx.data(Qt.DecorationRole)
                                break

                        # Add the clip as a choice
                        clip_choices.append({
                            "name": clip.data["title"],
                            "value": clip.id,
                            "selected": False,
                            "icon": clip_icon
                        })

                        # Now gather tracked objects under this clip
                        tracked_objects = []
                        for effect in clip.data["effects"]:
                            if effect.get("has_tracked_object"):
                                eff_inst = timeline_instance.GetClipEffect(effect["id"])
                                visible = json.loads(eff_inst.GetVisibleObjects(frame_number))
                                # Use the new "<effect-UUID>-<index>" IDs directly
                                for obj_id in visible["visible_objects_id"]:
                                    tracked_objects.append({
                                        "name": obj_id,
                                        "value": obj_id,
                                        "selected": False,
                                        "icon": None
                                    })

                        if tracked_objects:
                            tracked_choices.append({
                                "name": clip.data["title"],
                                "value": tracked_objects,
                                "selected": False,
                                "icon": clip_icon
                            })

                    # Build the final choices list
                    self.choices.append({"name": _("None"), "value": "None", "selected": False, "icon": None})
                    if tracked_choices:
                        self.choices.append({
                            "name": _("Tracked Objects"),
                            "value": tracked_choices,
                            "selected": False,
                            "icon": None
                        })
                    if clip_choices:
                        self.choices.append({
                            "name": _("Clips"),
                            "value": clip_choices,
                            "selected": False,
                            "icon": None
                        })

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

                # Add None option to clear the source
                self.choices.append({"name": _("None"), "value": "", "selected": False, "icon": None})


                # Add root file choice
                if file_choices:
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

            elif property_key == "lut_path":
                # “None” option
                self.choices = [{"name": _("None"), "value": "", "selected": False, "icon": None}]

                def _gather(dir_path):
                    try:
                        names = sorted(os.listdir(dir_path), key=str.lower)
                    except OSError:
                        return []
                    result = []
                    for name in names:
                        full = os.path.join(dir_path, name)
                        pretty = _(name.replace("_", " ").title()).replace("&", "&&")
                        if os.path.isdir(full):
                            # folder → submenu
                            children = [
                                {"name": _(os.path.splitext(fn)[0]
                                           .replace("_", " ")
                                           .title()).replace("&", "&&"),
                                 "value": os.path.join(full, fn),
                                 "selected": False,
                                 "icon": None}
                                for fn in sorted(os.listdir(full), key=str.lower)
                                if fn.lower().endswith(".cube")
                            ]
                            if children:
                                result.append({"name": pretty, "value": children})
                        elif name.lower().endswith(".cube"):
                            # loose .cube file
                            result.append({
                                "name": pretty,
                                "value": full,
                                "selected": False,
                                "icon": None
                            })
                    return result

                # user-defined group
                user_choices = _gather(info.USER_COLORS_PATH)
                if user_choices:
                    self.choices.append({"name": _("User-Defined"), "value": user_choices})

                # built-in LUTs
                self.choices.extend(_gather(info.COLORS_PATH))

            # Handle track choices
            if property_name == "Track" and self.property_type == "int" and not self.choices:
                # Populate all display track names
                all_tracks = get_app().project.get("layers")
                display_count = len(all_tracks)
                for track in reversed(sorted(all_tracks, key=itemgetter('number'))):
                    # Append track choice
                    track_name = track.get("label") or _("Track %s") % display_count
                    self.choices.append({"name": track_name, "value": track.get("number"), "selected": False, "icon": None})
                    display_count -= 1

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
            menu = StyledContextMenu(parent=self)
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
                menu.addSeparator()

            # Format menu nesting
            log.debug(f"Context menu choices: {self.choices}")
            self.menu = self.build_menu(self.choices, menu)

            # Show context menu (if any options present)
            # There is always at least 1 QAction in an empty menu though
            if len(self.menu.children()) > 1:
                self.menu.popup(event.globalPos())

    def build_menu(self, data, parent_menu=None):
        """Build a Context Menu, included nested sub-menus, and divide lists if too large"""
        if parent_menu is None:
            parent_menu = StyledContextMenu(parent=self)

        # Get translation object
        _ = get_app()._tr

        SubMenuSize = 25
        for choice in data:
            if isinstance(choice["value"], list) and choice["value"]:
                log.info("Add submenu: " + choice["name"])
                if choice.get("icon"):
                    SubMenuRoot = parent_menu.addMenu(QIcon(choice["icon"]), choice["name"])
                else:
                    SubMenuRoot = parent_menu.addMenu(choice["name"])

                # Check if the list needs to be divided into sub-menus
                if len(choice["value"]) > SubMenuSize:
                    for i in range(0, len(choice["value"]), SubMenuSize):
                        range_label = f"{i + 1}-{min(i + SubMenuSize, len(choice['value']))}"
                        SubMenu = SubMenuRoot.addMenu(range_label)
                        self.build_menu(choice["value"][i:i + SubMenuSize], SubMenu)
                else:
                    self.build_menu(choice["value"], SubMenuRoot)
            else:
                # Single choice, not a list, add directly to the menu
                log.info(" - Add choice: " + choice["name"])
                Choice_Action = parent_menu.addAction(_(choice["name"]))
                if choice.get("icon"):
                    Choice_Action.setIcon(QIcon(choice["icon"]))
                Choice_Action.setData(choice["value"])
                Choice_Action.triggered.connect(self.Choice_Action_Triggered)

        return parent_menu

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
        # Get alpha value (if present) or default to fully opaque
        alpha = int(cur_property[1].get("alpha", {}).get("value", 255))

        # Show color dialog with alpha support
        try:
            # Create color with alpha
            currentColor = QColor(red, green, blue, alpha)
        except (ValueError, TypeError):
            # Default to opaque red if conversion fails
            currentColor = QColor(255, 0, 0, 255)

        ColorPicker(
            currentColor, parent=self.win, title=_("Select a Color"),
            callback=self.color_callback)

    def Insert_Action_Triggered(self):
        log.info("Insert_Action_Triggered")

        # Verify label has not been deleted
        if (self.selected_label and sip.isdeleted(self.selected_label)) or \
                (self.selected_item and sip.isdeleted(self.selected_item)):
            log.debug("Property has been deleted, skipping")
            self.selected_label = None
            self.selected_item = None

        if self.selected_item:
            current_value = QLocale().system().toDouble(self.selected_item.text())[0]
            self.clip_properties_model.value_updated(self.selected_item, value=current_value)

    def Remove_Action_Triggered(self):
        log.info("Remove_Action_Triggered")
        if not self.clip_properties_model.ignore_update_signal:
            self.start_transaction(self.selected_item)
        self.update_in_progress = True
        self.clip_properties_model.remove_keyframe(self.selected_item)
        if not self.mouse_pressed:
            self.finalize_transaction()

    def Choice_Action_Triggered(self):
        log.info("Choice_Action_Triggered")
        choice_value = self.sender().data()

        # Update value of dropdown item
        if not self.clip_properties_model.ignore_update_signal:
            self.start_transaction(self.selected_item)
        self.update_in_progress = True
        self.clip_properties_model.value_updated(self.selected_item, value=choice_value)
        if not self.mouse_pressed:
            self.finalize_transaction()

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

        # Reconnect itemChanged signal to intercept edits
        try:
            self.clip_properties_model.model.itemChanged.disconnect(
                self.clip_properties_model.value_updated
            )
        except (TypeError, RuntimeError) as ex:
            log.debug("Failed to disconnect itemChanged: %s", ex)
        self.clip_properties_model.model.itemChanged.connect(self.value_updated_wrapper)

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
        self.original_data_map = {}
        self.transaction_id = None
        self.update_in_progress = False
        self.mouse_pressed = False
        self.lock_selection = False
        self.prev_row = None
        self.menu = None

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
        menu = StyledContextMenu(parent=self)

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

        # Choose which selection list to use
        selection = self.all_selection if self.all_selection else get_app().window.selected_items
        if not selection:
            return None

        # Add multi-selection option (if applicable)
        if len(selection) > 1:
            label = _("%d selections") % len(selection)
            action = menu.addAction(label)
            action.setData({'selection': list(selection)})
            action.triggered.connect(self.Action_Triggered)
            menu.addSeparator()

        # Add selections to menu, and switch to "wait"
        # cursor if things take too long
        cursor_set = False
        count = 0
        try:
            for selected in selection:
                count += 1
                if count > 10 and not cursor_set:
                    get_app().setOverrideCursor(QCursor(Qt.WaitCursor))
                    cursor_set = True
                elif cursor_set and count % 10 == 0:
                    get_app().processEvents()

                item_id = selected['id']
                item_type = selected['type']

                if item_type == "clip":
                    clip = Clip.get(id=item_id)
                    if not clip:
                        continue
                    item_name = clip.title()

                    # Get file for clip (if any)
                    file_id = clip.data.get("file_id")
                    file = File.get(id=file_id)
                    if not file:
                        continue

                    # Generate thumbnail for file (if needed)
                    media_type = file.data.get("media_type")
                    if media_type in ["video", "image"]:
                        # Video thumbnail
                        fps = file.data["fps"]
                        fps_float = float(fps["num"]) / float(fps["den"])
                        thumbnail_frame = round(float(clip.data['start']) * fps_float) + 1
                        thumb_icon = QIcon(GetThumbPath(file.id, thumbnail_frame))
                    else:
                        # Audio thumbnail
                        thumb_icon = QIcon(os.path.join(info.PATH, "images", "AudioThumbnail.svg"))

                    action = menu.addAction(thumb_icon, item_name)
                    action.setData({'item_id': item_id, 'item_type': 'clip'})
                    action.triggered.connect(self.Action_Triggered)

                    for effect_info in clip.data.get('effects', []):
                        effect = Effect.get(id=effect_info.get('id'))
                        if not effect:
                            continue
                        effect_name = effect.title()
                        effect_icon = QIcon(QPixmap(
                            os.path.join(info.PATH, "effects", "icons", "%s.png" % effect.data.get('class_name').lower())))
                        effect_action = menu.addAction(effect_icon, '  >  %s' % _(effect_name))
                        effect_action.setData({'item_id': effect.id, 'item_type': 'effect'})
                        effect_action.triggered.connect(self.Action_Triggered)

                elif item_type == "transition":
                    trans = Transition.get(id=item_id)
                    if not trans:
                        continue
                    item_name = _(trans.title())
                    item_icon = QIcon(QPixmap(trans.data.get('reader', {}).get('path')))
                    action = menu.addAction(item_icon, item_name)
                    action.setData({'item_id': item_id, 'item_type': 'transition'})
                    action.triggered.connect(self.Action_Triggered)

                elif item_type == "effect":
                    effect = Effect.get(id=item_id)
                    if not effect:
                        continue
                    item_name = _(effect.title())
                    item_icon = QIcon(QPixmap(
                        os.path.join(info.PATH, "effects", "icons", "%s.png" % effect.data.get('class_name').lower())))
                    action = menu.addAction(item_icon, item_name)
                    action.setData({'item_id': item_id, 'item_type': 'effect'})
                    action.triggered.connect(self.Action_Triggered)

        finally:
            if cursor_set:
                # Restore cursor
                get_app().restoreOverrideCursor()

        # Don't show menu if no actions were added
        if len(menu.actions()) == 0:
            return None

        # Return the menu object
        return menu

    def _selections_equal(self, first, second):
        def norm(s):
            return sorted([(i['id'], i['type']) for i in s])
        return norm(first) == norm(second)

    def open_menu(self):
        """Create and display the selection menu when requested."""
        menu = self.getMenu()
        if menu:
            menu.exec_(self.btnSelectionName.mapToGlobal(QPoint(0, self.btnSelectionName.height())))

    def Action_Triggered(self):
        data = self.sender().data()
        win = get_app().window

        if 'selection' in data:
            # User picked the multi-selection action → store the multi-selection, clear any target
            self.all_selection = list(data['selection'])  # Cache for toggling!
            self.target_selection = None
            # Restore full selection in timeline
            for idx, sel in enumerate(self.all_selection):
                win.timeline.AddSelectionJS(sel['id'], sel['type'], idx == 0)
        else:
            # User picked a single item. Don't overwrite all_selection!
            item_id = data['item_id']
            item_type = data['item_type']
            self.target_selection = [{'id': item_id, 'type': item_type}]
            # If we don't have a cached all_selection, set it now
            if not self.all_selection:
                self.all_selection = list(win.selected_items)
            win.timeline.AddSelectionJS(item_id, item_type, True)

    def select_item(self, selection):
        # Only update our internal selection state if this is a fresh selection
        if self.target_selection is not None:
            # We just triggered a toggle (to a single item), check if it's loaded
            if self._selections_equal(selection, self.target_selection):
                # UI loaded the requested single item; restore all_selection for the next time
                self.target_selection = None
                # Don't touch self.all_selection! Keep it alive for toggling back.
            else:
                # Ignore any intermediate reloads
                return
        else:
            # If selection changed outside menu, update all_selection
            if not self._selections_equal(selection, self.all_selection):
                self.all_selection = list(selection)

        count = len(selection)
        if count == 1:
            self.item_id = selection[0]['id']
            self.item_type = selection[0]['type']
        else:
            self.item_type = 'multi'

        # Get translation object
        _ = get_app()._tr

        # Look up item for more info
        if self.item_type == "multi":
            self.lblSelection.setText("<strong>%s</strong>" % _("Selection:"))
            self.btnSelectionName.setText(_("%d selections") % count)
            self.btnSelectionName.setVisible(True)
            self.btnSelectionName.setIcon(QIcon())
            self.btnSelectionName.setMenu(None)
            return
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
        self.btnSelectionName.setMenu(None)

    def __init__(self, *args):
        # Invoke parent init
        super().__init__(*args)
        self.item_id = None
        self.item_type = None
        self.item_name = None
        self.item_icon = None
        self.all_selection = []

        # Get translation object
        _ = get_app()._tr

        # Widgets
        self.lblSelection = QLabel()
        self.lblSelection.setText("<strong>%s</strong>" % _("No Selection"))
        self.btnSelectionName = QPushButton()
        self.btnSelectionName.setVisible(False)
        self.btnSelectionName.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.btnSelectionName.clicked.connect(self.open_menu)

        # Support rich text
        self.lblSelection.setTextFormat(Qt.RichText)

        hbox = QHBoxLayout()
        hbox.setContentsMargins(0, 0, 0, 0)
        hbox.addWidget(self.lblSelection)
        hbox.addWidget(self.btnSelectionName)
        self.setLayout(hbox)

        # Variables for managing dropdown selections
        self.target_selection = None
        self.previous_selection = []

        # Connect signals
        get_app().window.propertyTableView.loadProperties.connect(self.select_item)
