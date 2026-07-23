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

import copy
import os
import json
import functools
import math
from operator import itemgetter
import uuid

from qt_api import Qt, QRectF, QLocale, pyqtSignal, pyqtSlot, QEvent, QPoint, QPointF, QTimer
from qt_api import isdeleted
from qt_api import get_font_dialog_selection
from qt_api import (
    QIcon, QColor, QBrush, QPen, QPalette, QPixmap,
    QPainter, QPainterPath, QLinearGradient, QFont, QFontInfo, QCursor, QGuiApplication,
)
from qt_api import (
    QTableView, QAbstractItemView, QSizePolicy,
    QHeaderView, QItemDelegate, QStyle, QLabel, QDockWidget,
    QPushButton, QHBoxLayout, QFrame, QScrollArea
)

from classes.logger import log
from classes.app import get_app
from classes import info
from classes.query import Clip, Effect, Transition, File
from classes.thumbnail import GetThumbPath

from windows.models.properties_model import PropertiesModel
from windows.color_picker import ColorPicker
from windows.color_grade_editor import (
    ColorGradeCurveDialog,
    ColorGradeWheelsPanel,
    curve_enabled_at_frame,
    curve_nodes_at_frame,
    curve_summary,
    default_curve_data,
    default_wheels_data,
    display_wheel_color,
    is_neutral_wheel,
    normalize_curve_data,
    normalize_wheels_data,
    puck_display_color,
    scope_angle_for_display_hue,
    wheels_snapshot,
    wheels_summary,
)
from .menu import StyledContextMenu, populate_keyframe_context_menu

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
        try:
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
            value_percent = 0.0
            # Only draw proportional blue fills for actual percentage/level properties
            if property_name in ["alpha", "volume", "rotation"]:
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
                    if abs(min_max_range) > 1e-12:
                        value_percent = current_value / min_max_range

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
            elif property_type in ["colorgrade_curve", "colorgrade_wheels"]:
                painter.setBrush(background_color)
            else:
                # Normal Keyframe
                state_selected = getattr(QStyle, "State_Selected", None)
                if state_selected is None:
                    state_flag = getattr(QStyle, "StateFlag", None)
                    if state_flag:
                        state_selected = getattr(state_flag, "State_Selected", None)
                if state_selected and option.state & state_selected:
                    painter.setBrush(background_color)
                else:
                    painter.setBrush(background_color)

            if readonly:
                # Set text color for read only fields
                painter.setPen(QPen(get_app().window.palette().color(QPalette.Disabled, QPalette.Text)))
            else:
                path = QPainterPath()
                path.addRoundedRect(QRectF(option.rect), 4, 4)
                painter.fillPath(path, background_color)
                painter.drawPath(path)

                # Render mask rectangle
                painter.setBrush(QBrush(QColor("#000000")))
                mask_rect = QRectF(option.rect)
                mask_rect.setWidth(option.rect.width() * value_percent)
                painter.setClipRect(mask_rect, Qt.IntersectClip)

                # gradient for value box
                gradient = QLinearGradient(QPointF(option.rect.topLeft()), QPointF(option.rect.topRight()))
                gradient.setColorAt(0, foreground_color)
                gradient.setColorAt(1, foreground_color)

                # Render progress
                painter.setBrush(gradient)
                path = QPainterPath()
                value_rect = QRectF(option.rect)
                path.addRoundedRect(value_rect, 4, 4)
                painter.fillPath(path, gradient)
                painter.drawPath(path)
                painter.setClipping(False)

                if points > 1 and property_type not in ["colorgrade_curve", "colorgrade_wheels"]:
                    # Draw interpolation icon on top
                    painter.drawPixmap(
                        int(option.rect.x() + option.rect.width() - 30.0),
                        int(option.rect.y() + 4),
                        self.curve_pixmaps[interpolation])

                # Set text color
                painter.setPen(QPen(Qt.white))

            if property_type == "colorgrade_curve":
                frame_number = getattr(get_app().window.propertyTableView.clip_properties_model, "frame_number", 1)
                preview_frame = cur_property[1].get("preview_frame")
                nodes = cur_property[1].get("preview_curve_nodes") if preview_frame == frame_number else None
                is_enabled = cur_property[1].get("preview_curve_enabled") if preview_frame == frame_number else None
                if nodes is None or is_enabled is None:
                    curve = normalize_curve_data(cur_property[1].get("curve"))
                    is_enabled = curve_enabled_at_frame(curve, frame_number)
                    nodes = curve_nodes_at_frame(curve, frame_number)
                preview_rect = QRectF(option.rect.adjusted(8, 8, -32 if points > 1 else -8, -8))
                line_color = Qt.white if is_enabled else QColor(100, 100, 100)
                painter.setPen(QPen(line_color, 1.5))
                path = QPainterPath()
                if nodes:
                    start = QPointF(preview_rect.left() + (nodes[0]["x"] * preview_rect.width()),
                                    preview_rect.bottom() - (nodes[0]["y"] * preview_rect.height()))
                    path.moveTo(start)
                    for idx in range(1, len(nodes)):
                        left = nodes[idx - 1]
                        right = nodes[idx]
                        right_point = QPointF(preview_rect.left() + (right["x"] * preview_rect.width()),
                                              preview_rect.bottom() - (right["y"] * preview_rect.height()))
                        if right["interpolation"] == openshot.CONSTANT:
                            left_point = QPointF(preview_rect.left() + (left["x"] * preview_rect.width()),
                                                 preview_rect.bottom() - (left["y"] * preview_rect.height()))
                            path.lineTo(QPointF(right_point.x(), left_point.y()))
                            path.lineTo(right_point)
                        elif right["interpolation"] == openshot.LINEAR:
                            path.lineTo(right_point)
                        else:
                            delta_x = right["x"] - left["x"]
                            delta_y = right["y"] - left["y"]
                            c1 = QPointF(
                                preview_rect.left() + ((left["x"] + (left["right_handle_x"] * delta_x)) * preview_rect.width()),
                                preview_rect.bottom() - ((left["y"] + (left["right_handle_y"] * delta_y)) * preview_rect.height()),
                            )
                            c2 = QPointF(
                                preview_rect.left() + ((left["x"] + (right["left_handle_x"] * delta_x)) * preview_rect.width()),
                                preview_rect.bottom() - ((left["y"] + (right["left_handle_y"] * delta_y)) * preview_rect.height()),
                            )
                            path.cubicTo(c1, c2, right_point)
                    painter.drawPath(path)
            elif property_type == "colorgrade_wheels":
                frame_number = getattr(get_app().window.propertyTableView.clip_properties_model, "frame_number", 1)
                preview_frame = cur_property[1].get("preview_frame")
                wheels = cur_property[1].get("preview_wheels") if preview_frame == frame_number else None
                if wheels is None:
                    wheels = wheels_snapshot(cur_property[1].get("wheels"), frame_number)
                is_enabled = wheels.get("enabled", True)
                circle_color = QColor(Qt.white) if is_enabled else QColor(100, 100, 100)
                names = ["global", "shadows", "midtones", "highlights"]
                preview_rect = QRectF(option.rect.adjusted(6, 4, -32 if points > 1 else -6, -4))
                wheel_width = preview_rect.width() / 4.0
                for idx, name in enumerate(names):
                    wheel = wheels[name]
                    rect = QRectF(preview_rect.x() + (idx * wheel_width), preview_rect.y(), wheel_width, preview_rect.height())
                    center = QPointF(rect.center().x(), rect.top() + rect.height() * 0.43)
                    radius = min(rect.width() * 0.34, rect.height() * 0.34)
                    painter.setPen(QPen(circle_color, 1.0))
                    painter.setBrush(QBrush(QColor(circle_color.red(), circle_color.green(), circle_color.blue(), 18)))
                    painter.drawEllipse(center, radius, radius)
                    if is_enabled:
                        color = display_wheel_color(wheel)
                        tint = QColor(color)
                        if is_neutral_wheel(wheel):
                            tint = QColor(255, 255, 255, 18)
                        else:
                            tint.setAlpha(32)
                        puck_color = puck_display_color(wheel)
                    else:
                        tint = QColor(100, 100, 100, 18)
                        puck_color = QColor(100, 100, 100)
                        color = QColor(100, 100, 100)
                    painter.setBrush(QBrush(tint))
                    painter.drawEllipse(center, radius * 0.92, radius * 0.92)
                    amount = float(wheel["amount"]) * radius * 0.85
                    hue = color.hueF() if color.hueF() >= 0 else 0.0
                    angle = math.radians(scope_angle_for_display_hue(hue * 360.0))
                    puck = QPointF(center.x() + math.cos(angle) * amount, center.y() - math.sin(angle) * amount)
                    painter.setPen(QPen(circle_color, 1.0))
                    painter.setBrush(QBrush(puck_color))
                    puck_radius = max(2.0, radius * 0.11)
                    painter.drawEllipse(puck, puck_radius, puck_radius)
                    luma_y = min(rect.bottom() - 4.0, center.y() + radius + 9.0)
                    luma_left = rect.center().x() - radius
                    luma_right = rect.center().x() + radius
                    painter.setPen(QPen(QColor(circle_color.red(), circle_color.green(), circle_color.blue(), 80), 1.0))
                    painter.drawLine(QPointF(luma_left, luma_y), QPointF(luma_right, luma_y))
                    luma_value = (float(wheel["luma"]) + 1.0) / 2.0
                    luma_fill_right = luma_left + ((luma_right - luma_left) * luma_value)
                    painter.setPen(QPen(circle_color, 2.0))
                    painter.drawLine(QPointF(luma_left, luma_y), QPointF(luma_fill_right, luma_y))

            if points > 1 and property_type in ["colorgrade_curve", "colorgrade_wheels"]:
                painter.drawPixmap(
                    int(option.rect.x() + option.rect.width() - 30.0),
                    int(option.rect.y() + 4),
                    self.curve_pixmaps[interpolation])

            value = index.data(Qt.DisplayRole)
            if value and property_type not in ["colorgrade_curve", "colorgrade_wheels"]:
                painter.drawText(option.rect, Qt.AlignCenter, value)
        finally:
            painter.restore()


def _event_posf(event):
    if hasattr(event, "position"):
        return event.position()
    return QPointF(event.pos())


class PropertiesTableView(QTableView):
    """ A Properties Table QWidget used on the main window """
    loadProperties = pyqtSignal(list)

    def _tracked_mask_source_choices(self, current_effect_id=None):
        _ = get_app()._tr
        tracked_effect_choices = []

        for clip in Clip.filter():
            file_id = clip.data.get("file_id")

            clip_icon = None
            for row in range(self.files_model.rowCount()):
                idx = self.files_model.index(row, 0)
                if idx.sibling(row, 5).data() == file_id:
                    clip_icon = idx.data(Qt.DecorationRole)
                    break

            effect_choices = []
            for effect in clip.data.get("effects", []):
                effect_id = effect.get("id")
                if not effect_id:
                    continue
                if current_effect_id and effect_id == current_effect_id:
                    continue
                if not effect.get("has_tracked_object"):
                    continue

                effect_class = effect.get("class_name", "")
                effect_name = effect.get("name") or effect_class or effect.get("id")
                effect_icon = None
                if effect_class:
                    effect_icon = QIcon(QPixmap(os.path.join(
                        info.PATH, "effects", "icons", "%s.png" % effect_class.lower())))

                effect_choices.append({
                    "name": f"{_(effect_name)} ({effect_id})",
                    "value": effect_id,
                    "selected": False,
                    "icon": effect_icon
                })

            if effect_choices:
                tracked_effect_choices.append({
                    "name": clip.data["title"],
                    "value": effect_choices,
                    "selected": False,
                    "icon": clip_icon
                })

        return tracked_effect_choices

    def _is_edit_text(self, event):
        if event.modifiers() & (Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier):
            return False

        text = event.text()
        if not text or text.isspace():
            return False

        return text in "0123456789.,-+"

    def _start_edit_on_key(self, event):
        key = event.key()
        is_numeric = self._is_edit_text(event)
        if key not in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space) and not is_numeric:
            return False

        index = self.currentIndex()
        if not index.isValid():
            return False

        if index.column() != 1:
            index = index.sibling(index.row(), 1)
            self.setCurrentIndex(index)

        if not (index.flags() & Qt.ItemIsEditable):
            return False

        result = self.edit(index, QAbstractItemView.EditKeyPressed, event)

        # For numeric keys, clobber the existing value with the typed character
        if result and is_numeric:
            from qt_api import QTimer
            typed_char = event.text()
            def set_initial_value():
                editor = self.indexWidget(index)
                if editor and hasattr(editor, 'setText'):
                    editor.setText(typed_char)
                    editor.setCursorPosition(len(typed_char))
                elif editor and hasattr(editor, 'lineEdit'):
                    # For QSpinBox/QDoubleSpinBox
                    editor.lineEdit().setText(typed_char)
                    editor.lineEdit().setCursorPosition(len(typed_char))
            QTimer.singleShot(0, set_initial_value)

        return result

    def event(self, event):
        # Intercept ShortcutOverride so these keys don't trigger global shortcuts
        # when this view has focus
        if event.type() == QEvent.ShortcutOverride and self.hasFocus():
            key = event.key()
            if key in (Qt.Key_Period, Qt.Key_Comma, Qt.Key_Up, Qt.Key_Down,
                       Qt.Key_Space, Qt.Key_Return, Qt.Key_Enter, Qt.Key_Escape):
                event.accept()
                return True
        # otherwise, default processing
        return super().event(event)

    def closeEditor(self, editor, hint):
        """Handle editor closing - restore focus to label column."""
        super().closeEditor(editor, hint)
        # Restore focus to column 0 (label column) for visible focus indicator
        current_row = self.currentIndex().row()
        if current_row >= 0:
            self.setCurrentIndex(self.clip_properties_model.model.index(current_row, 0))

    def keyPressEvent(self, event):
        if self._start_edit_on_key(event):
            return

        # Handle SPACE/ENTER for dropdown properties
        key = event.key()
        if key in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            index = self.currentIndex()
            if index.isValid():
                # Ensure we're on the value column
                if index.column() != 1:
                    index = index.sibling(index.row(), 1)

                # Check if this is a dropdown/choice property
                model = self.clip_properties_model.model
                label_item = model.item(index.row(), 0)
                if label_item and label_item.data() and isinstance(label_item.data(), tuple):
                    cur_property = label_item.data()
                    has_choices = bool(cur_property[1].get("choices"))
                    property_type = cur_property[1].get("type", "")

                    if has_choices or property_type in ["color", "font"]:
                        # Show context menu at the center of the value cell
                        rect = self.visualRect(index)
                        center = rect.center()
                        global_pos = self.viewport().mapToGlobal(center)
                        self._show_property_menu_at(index, global_pos)
                        return

        super().keyPressEvent(event)

    def _show_property_menu_at(self, index, global_pos):
        """Show the property context menu at a specific position."""
        # Create a fake event object that provides the position we want
        class FakeEvent:
            def __init__(self, gpos, lpos):
                self._global_pos = gpos
                self._local_pos = lpos
            def globalPos(self):
                return self._global_pos
            def pos(self):
                return self._local_pos
            def ignore(self):
                pass

        local_pos = self.viewport().mapFromGlobal(global_pos)
        fake_event = FakeEvent(global_pos, local_pos)
        self.contextMenuEvent(fake_event)

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

    def _restore_original_objects(self):
        for item_id, info in self.original_data_map.items():
            item_type = info.get("type")
            original = copy.deepcopy(info.get("data"))
            obj = None
            if item_type == "clip":
                obj = Clip.get(id=item_id)
            elif item_type == "transition":
                obj = Transition.get(id=item_id)
            elif item_type == "effect":
                obj = Effect.get(id=item_id)
            if obj:
                obj.data = original
                obj.save()
        get_app().window.refreshFrameSignal.emit()

    def cancel_transaction(self):
        if not self.transaction_id:
            return
        self._restore_original_objects()
        get_app().updates.transaction_id = None
        get_app().updates.ignore_history = False
        self.transaction_id = None
        self.original_data_map = {}
        self.update_in_progress = False

    def begin_live_property_session(self, item, property_type, property_key, original_value):
        if self.live_property_session:
            if self.live_property_session.get("property_type") == "colorgrade_wheels" and property_type == "colorgrade_curve":
                if self.transaction_id:
                    self.finalize_transaction()
                get_app().updates.ignore_history = False
                self.resume_live_property_caching()
                self.live_property_session = None
                self.color_grade_wheels_panel.setEnabled(False)
            elif self.live_property_session.get("property_type") == "colorgrade_wheels":
                self.accept_live_property_session()
            else:
                self.cancel_live_property_session()
        if not self.clip_properties_model.ignore_update_signal and property_type not in ("colorgrade_curve", "colorgrade_wheels"):
            self.start_transaction(item)
        self.live_property_session = {
            "item": item,
            "item_data": copy.deepcopy(item.data()) if item else None,
            "property_type": property_type,
            "property_key": property_key,
            "original_value": copy.deepcopy(original_value),
        }
        get_app().updates.ignore_history = True

    def preview_live_property_value(self, value):
        if not self.live_property_session:
            return
        self.update_in_progress = True
        self.clip_properties_model.value_updated(self.live_property_session["item"], value=value)
        self._update_live_property_preview(value)
        get_app().updates.ignore_history = True

    def _resolve_live_property_item(self, item, property_key, property_type, item_data=None):
        if item:
            try:
                if not isdeleted(item):
                    row = item.row()
                    label_item = self.clip_properties_model.model.item(row, 0)
                    if label_item:
                        cur_property = label_item.data()
                        if (
                            isinstance(cur_property, tuple)
                            and len(cur_property) == 2
                            and cur_property[0] == property_key
                            and cur_property[1].get("type") == property_type
                        ):
                            return item
            except RuntimeError:
                pass

        resolved_item, _property_meta = self._find_property_value_item(
            property_key,
            property_type=property_type,
            item_data=item_data,
        )
        return resolved_item

    def preview_curve_property_value(self, item, property_key, value, item_data=None):
        item = self._resolve_live_property_item(item, property_key, "colorgrade_curve", item_data)
        if not item:
            return
        self.update_in_progress = True
        self.clip_properties_model.value_updated(item, value=value)
        self._update_property_preview(item, "colorgrade_curve", property_key, value)
        get_app().updates.ignore_history = True

    def _update_live_property_preview(self, value):
        session = self.live_property_session or {}
        self._update_property_preview(
            session.get("item"),
            session.get("property_type"),
            session.get("property_key"),
            value,
        )

    def _update_color_grade_preview_meta(self, property_meta):
        if not isinstance(property_meta, dict):
            return
        frame_number = self.clip_properties_model.frame_number
        property_meta["preview_frame"] = frame_number
        if property_meta.get("type") == "colorgrade_curve":
            curve = normalize_curve_data(property_meta.get("curve"))
            property_meta["preview_curve_enabled"] = curve_enabled_at_frame(curve, frame_number)
            property_meta["preview_curve_nodes"] = curve_nodes_at_frame(curve, frame_number)
        elif property_meta.get("type") == "colorgrade_wheels":
            property_meta["preview_wheels"] = wheels_snapshot(property_meta.get("wheels"), frame_number)

    def _update_property_preview(self, item, property_type, property_key, value):
        if not item or property_type not in ["colorgrade_curve", "colorgrade_wheels"]:
            return

        model = self.clip_properties_model.model
        label_item = model.item(item.row(), 0)
        value_item = model.item(item.row(), 1)
        if not label_item:
            return

        current_property = label_item.data()
        if not isinstance(current_property, tuple) or len(current_property) != 2:
            return

        prop_name, prop_meta = current_property
        if prop_name != property_key:
            return

        updated_meta = prop_meta
        if property_type == "colorgrade_curve":
            updated_meta["curve"] = copy.deepcopy(value)
            updated_meta["summary"] = curve_summary(value, self.clip_properties_model.frame_number)
        elif property_type == "colorgrade_wheels":
            updated_meta["wheels"] = copy.deepcopy(value)
            updated_meta["summary"] = wheels_summary(value, self.clip_properties_model.frame_number)
        self._update_color_grade_preview_meta(updated_meta)
        if value_item:
            summary = updated_meta.get("summary") or updated_meta.get("memo") or ""
            value_item.setText(summary)

        self.viewport().update()

    def _find_property_value_item(self, property_key, property_type=None, item_data=None):
        model = self.clip_properties_model.model
        for row in range(model.rowCount()):
            label_item = model.item(row, 0)
            value_item = model.item(row, 1)
            if not label_item or not value_item:
                continue
            cur_property = label_item.data()
            if not isinstance(cur_property, tuple) or len(cur_property) != 2:
                continue
            row_property_key, property_meta = cur_property
            if row_property_key != property_key:
                continue
            if property_type and property_meta.get("type") != property_type:
                continue
            if item_data is not None and value_item.data() != item_data:
                continue
            return value_item, property_meta
        return None, None

    def _sync_color_grade_editors(self, property_type, property_key, value):
        item = self.selected_item
        item_data = item.data() if item else None

        if property_type == "colorgrade_curve":
            for dialog in list(getattr(self, "color_grade_curve_dialogs", [])):
                if isdeleted(dialog):
                    self.color_grade_curve_dialogs.discard(dialog)
                    continue
                if getattr(dialog, "_property_key", None) != property_key:
                    continue
                if getattr(dialog, "_item_data", None) != item_data:
                    continue
                dialog.set_frame_number(self.clip_properties_model.frame_number)
                dialog.curve_widget().blockSignals(True)
                dialog.curve_widget().set_curve_data(value)
                dialog.curve_widget().blockSignals(False)
                dialog._update_enabled_state()
        elif property_type == "colorgrade_wheels":
            session = self.live_property_session or {}
            if (
                session.get("property_type") == "colorgrade_wheels"
                and session.get("property_key") == property_key
                and session.get("item") is item
            ):
                self.color_grade_wheels_panel.set_frame_number(self.clip_properties_model.frame_number)
                self.color_grade_wheels_panel.set_wheels_data(value)

    def _sync_color_grade_editors_to_current_frame(self):
        if not hasattr(self, "color_grade_wheels_panel"):
            return
        model = self.clip_properties_model.model
        self.color_grade_wheels_panel.set_frame_number(self.clip_properties_model.frame_number)

        for row in range(model.rowCount()):
            label_item = model.item(row, 0)
            value_item = model.item(row, 1)
            if not label_item or not value_item:
                continue
            cur_property = label_item.data()
            if not isinstance(cur_property, tuple) or len(cur_property) != 2:
                continue
            property_key, property_meta = cur_property
            property_type = property_meta.get("type")
            if property_type == "colorgrade_curve":
                self._update_color_grade_preview_meta(property_meta)
                item_data = value_item.data()
                for dialog in list(getattr(self, "color_grade_curve_dialogs", [])):
                    if isdeleted(dialog):
                        self.color_grade_curve_dialogs.discard(dialog)
                        continue
                    if getattr(dialog, "_property_key", None) != property_key:
                        continue
                    if getattr(dialog, "_item_data", None) != item_data:
                        continue
                    dialog.set_frame_number(self.clip_properties_model.frame_number)
                    dialog.curve_widget().blockSignals(True)
                    dialog.curve_widget().set_curve_data(normalize_curve_data(property_meta.get("curve")))
                    dialog.curve_widget().blockSignals(False)
            elif property_type == "colorgrade_wheels":
                self._update_color_grade_preview_meta(property_meta)
        self._sync_color_grade_wheels_dock_from_model()
        self.viewport().update()

    def property_model_refreshed(self):
        """Rebind editor sessions after property rows are rebuilt by undo/redo or selection changes."""
        if not hasattr(self, "color_grade_wheels_panel"):
            return
        session = self.live_property_session or {}
        property_type = session.get("property_type")
        property_key = session.get("property_key")
        item_data = session.get("item_data")

        if property_type in ["colorgrade_curve", "colorgrade_wheels"] and property_key:
            item, property_meta = self._find_property_value_item(
                property_key,
                property_type=property_type,
                item_data=item_data,
            )
            if item:
                session["item"] = item
                session["item_data"] = copy.deepcopy(item.data())
                self.selected_item = item
                if property_type == "colorgrade_wheels":
                    self.color_grade_wheels_panel.set_frame_number(self.clip_properties_model.frame_number)
                    self.color_grade_wheels_panel.set_wheels_data(
                        normalize_wheels_data(property_meta.get("wheels"))
                    )

        self._sync_color_grade_editors_to_current_frame()

    def _is_playing(self):
        try:
            return get_app().window.preview_thread.player.Mode() == openshot.PLAYBACK_PLAY
        except Exception:
            return False

    def pause_live_property_caching(self):
        if self.live_property_cache_paused or self._is_playing():
            return
        openshot.Settings.Instance().ENABLE_PLAYBACK_CACHING = False
        self.live_property_cache_paused = True
        log.debug("pause_live_property_caching: Stop caching frames on timeline")

    def resume_live_property_caching(self):
        if not self.live_property_cache_paused:
            return
        self.live_property_cache_paused = False
        log.debug("resume_live_property_caching: Keep caching disabled until seek/play")

    def _wheels_drag_started(self):
        """Open a per-drag undo transaction when user starts dragging a wheel control."""
        self.pause_live_property_caching()
        session = self.live_property_session
        if session and session.get("property_type") == "colorgrade_wheels":
            item = session.get("item")
            if item:
                self.start_transaction(item)

    def _wheels_drag_finished(self):
        """Commit the drag as one undo step when the user releases a wheel control."""
        if self.transaction_id:
            self.finalize_transaction()
        # Keep history suppressed between drags so incidental signals don't leak in.
        get_app().updates.ignore_history = True
        self.resume_live_property_caching()

    def accept_live_property_session(self):
        if not self.live_property_session:
            return
        property_type = self.live_property_session.get("property_type")
        if self.transaction_id:
            self.finalize_transaction()
        get_app().updates.ignore_history = False
        self.resume_live_property_caching()
        self.live_property_session = None
        self.clip_properties_model.update_model(get_app().window.txtPropertyFilter.text())
        if property_type == "colorgrade_curve" and self.color_grade_wheels_dock.isVisible():
            self._update_color_grade_wheels_enabled()

    def _selection_is_color_grade(self, selection):
        if len(selection or []) != 1:
            return False
        item = selection[0]
        if item.get("type") != "effect":
            return False
        effect = Effect.get(id=item.get("id"))
        if not effect or not getattr(effect, "data", None):
            return False
        return effect.data.get("class_name") == "ColorGrade"

    def _update_color_grade_wheels_enabled(self, selection=None):
        if selection is None:
            selection = getattr(self, "current_selection", [])
        if self._selection_is_color_grade(selection):
            self.color_grade_wheels_panel.setEnabled(True)
        else:
            self._set_color_grade_wheels_unbound()

    def _find_color_grade_wheels_item(self):
        model = self.clip_properties_model.model
        for row in range(model.rowCount()):
            label_item = model.item(row, 0)
            value_item = model.item(row, 1)
            if not label_item or not value_item:
                continue
            cur_property = label_item.data()
            if not isinstance(cur_property, tuple) or len(cur_property) != 2:
                continue
            if cur_property[1].get("type") == "colorgrade_wheels":
                return value_item, cur_property[0], normalize_wheels_data(cur_property[1].get("wheels"))
        return None, None, None

    def _sync_color_grade_wheels_dock_from_model(self):
        """Refresh the visible wheels dock from current model data after external edits."""
        if not hasattr(self, "color_grade_wheels_dock") or not self.color_grade_wheels_dock.isVisible():
            return
        if not self._selection_is_color_grade(getattr(self, "current_selection", [])):
            self._set_color_grade_wheels_unbound()
            return

        item, property_key, wheels_data = self._find_color_grade_wheels_item()
        if not item or not property_key:
            self._set_color_grade_wheels_unbound()
            return

        self.selected_item = item
        self.color_grade_wheels_panel.setEnabled(True)
        self.color_grade_wheels_panel.set_frame_number(self.clip_properties_model.frame_number)
        self.color_grade_wheels_panel.blockSignals(True)
        self.color_grade_wheels_panel.set_wheels_data(wheels_data)
        self.color_grade_wheels_panel.blockSignals(False)

        session = self.live_property_session or {}
        if session.get("property_type") == "colorgrade_wheels":
            session["item"] = item
            session["item_data"] = copy.deepcopy(item.data())
            session["property_key"] = property_key

    def _disabled_color_grade_wheels_data(self):
        data = default_wheels_data()
        points = data.get("enabled_keyframes", {}).get("Points")
        if points:
            points[0].setdefault("co", {})["Y"] = 0.0
        return data

    def _set_color_grade_wheels_unbound(self):
        """Show neutral disabled wheels when no editable ColorGrade effect is bound."""
        if not hasattr(self, "color_grade_wheels_panel"):
            return
        self.color_grade_wheels_panel.blockSignals(True)
        self.color_grade_wheels_panel.set_frame_number(self.clip_properties_model.frame_number)
        self.color_grade_wheels_panel.set_wheels_data(self._disabled_color_grade_wheels_data())
        self.color_grade_wheels_panel.setEnabled(False)
        self.color_grade_wheels_panel.blockSignals(False)

    def _activate_color_grade_wheels_session(self, item, property_key, wheels_data):
        session = self.live_property_session or {}
        if session.get("property_type") == "colorgrade_wheels":
            if session.get("item") is item and session.get("property_key") == property_key:
                self.color_grade_wheels_panel.set_frame_number(self.clip_properties_model.frame_number)
                self.color_grade_wheels_panel.set_wheels_data(wheels_data)
                return
            if self.transaction_id:
                self.finalize_transaction()
            get_app().updates.ignore_history = False
            self.resume_live_property_caching()
            self.live_property_session = None
        elif self.live_property_session:
            self.cancel_live_property_session()

        self.begin_live_property_session(item, "colorgrade_wheels", property_key, wheels_data)
        self.color_grade_wheels_panel.set_frame_number(self.clip_properties_model.frame_number)
        self.color_grade_wheels_panel.set_wheels_data(wheels_data)

    def _auto_connect_color_grade_wheels_dock(self):
        if not self.color_grade_wheels_dock.isVisible():
            return
        if not self._selection_is_color_grade(self.current_selection):
            return

        item, property_key, wheels_data = self._find_color_grade_wheels_item()
        if not item or not property_key:
            return

        self.selected_item = item
        self._ensure_color_grade_wheels_dock_attached()
        self._activate_color_grade_wheels_session(item, property_key, wheels_data)

    def _reconnect_color_grade_wheels_session(self):
        """Re-establish the live session when the wheels dock is shown (dock already attached)."""
        if not self.color_grade_wheels_dock.isVisible():
            return
        if self.live_property_session:
            return
        if not self._selection_is_color_grade(self.current_selection):
            return
        item, property_key, wheels_data = self._find_color_grade_wheels_item()
        if not item or not property_key:
            return
        self.selected_item = item
        self._activate_color_grade_wheels_session(item, property_key, wheels_data)

    def _close_color_grade_editors(self, commit_changes=True):
        session = self.live_property_session or {}
        property_type = session.get("property_type")

        if property_type in ["colorgrade_curve", "colorgrade_wheels"]:
            if commit_changes:
                self.accept_live_property_session()
            else:
                self.cancel_live_property_session()

        for dialog in list(getattr(self, "color_grade_curve_dialogs", [])):
            if isdeleted(dialog):
                self.color_grade_curve_dialogs.discard(dialog)
                continue
            dialog.blockSignals(True)
            dialog.close()
            dialog.blockSignals(False)

    def cancel_live_property_session(self):
        if not self.live_property_session:
            return
        property_type = self.live_property_session.get("property_type")
        if self.transaction_id:
            self.cancel_transaction()
        self.resume_live_property_caching()
        self.live_property_session = None
        if property_type == "colorgrade_curve" and self.color_grade_wheels_dock.isVisible():
            self._update_color_grade_wheels_enabled()
        self.clip_properties_model.update_model(get_app().window.txtPropertyFilter.text())

    def start_live_property_change(self):
        session = self.live_property_session or {}
        self.start_property_change(session.get("item"))

    def start_property_change(self, item):
        if not item or self.transaction_id or self.clip_properties_model.ignore_update_signal:
            return
        self.start_transaction(item)
        get_app().updates.ignore_history = True

    def start_curve_property_change(self, item, property_key, item_data=None):
        item = self._resolve_live_property_item(item, property_key, "colorgrade_curve", item_data)
        self.start_property_change(item)

    def finish_live_property_change(self):
        self.finish_property_change()

    def finish_property_change(self):
        if self.transaction_id:
            self.finalize_transaction()
        get_app().updates.ignore_history = False
        self.clip_properties_model.update_model(get_app().window.txtPropertyFilter.text())

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
        if event.button() == Qt.LeftButton:
            self.mouse_pressed = True
        pos = _event_posf(event).toPoint()
        row = self.indexAt(pos).row()
        model = self.clip_properties_model.model
        if model.item(row, 1):
            self.selected_item = model.item(row, 1)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        # Get data model and selection
        model = self.clip_properties_model.model
        posf = _event_posf(event)
        pos = posf.toPoint()

        # Show resize cursor only over slider-type value cells (float/int, not read-only).
        # When not dragging (hover only), update cursor and return — don't touch drag state.
        idx = self.indexAt(pos)
        show_slider_cursor = False
        if idx.isValid() and idx.column() == 1:
            label_item = self.clip_properties_model.model.item(idx.row(), 0)
            if label_item:
                prop = label_item.data()
                if prop and isinstance(prop, tuple) and len(prop) > 1:
                    ptype = prop[1].get("type", "")
                    readonly = prop[1].get("readonly", False)
                    show_slider_cursor = ptype in ("float", "int") and not readonly
        if show_slider_cursor:
            self.viewport().setCursor(Qt.SizeHorCursor)
        else:
            self.viewport().unsetCursor()

        if not self.mouse_pressed:
            return

        # Do not change selected row during mouse move
        if self.lock_selection and self.prev_row:
            row = self.prev_row
        else:
            pos = _event_posf(event).toPoint()
            row = self.indexAt(pos).row()
            self.prev_row = row
            self.lock_selection = True

        if row is None:
            return

        event.accept()

        if model.item(row, 0):
            self.selected_label = model.item(row, 0)
            self.selected_item = model.item(row, 1)

        # Verify label has not been deleted
        if (self.selected_label and isdeleted(self.selected_label)) or \
                (self.selected_item and isdeleted(self.selected_item)):
            log.debug("Property has been deleted, skipping")
            self.selected_label = None
            self.selected_item = None

        # Is the user dragging on the value column
        if self.selected_label and self.selected_item and \
                self.selected_label.data() and type(self.selected_label.data()) == tuple:
            # Ignore undo/redo history temporarily (to avoid a huge pile of undo/redo history)
            get_app().updates.ignore_history = True

            # Disable video caching during drag (for performance), but not during playback
            if not self._is_playing():
                openshot.Settings.Instance().ENABLE_PLAYBACK_CACHING = False

            # Get the position of the cursor and % value
            value_column_x = self.columnViewportPosition(1)
            cursor_value = posf.x() - value_column_x
            value_column_width = self.columnWidth(1)
            if value_column_width <= 0:
                return
            cursor_value_percent = cursor_value / value_column_width

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

            # For numeric values, apply percentage within parameter's allowable range
            if property_type in ["float", "int"] and property_name != "Track":

                if self.previous_x == -1:
                    # Start tracking movement (init diff_length and previous_x)
                    self.diff_length = 10
                    self.previous_x = posf.x()

                # Calculate # of pixels dragged
                drag_diff = self.previous_x - posf.x()

                # update previous x
                self.previous_x = posf.x()

                # Ignore small initial movements
                if abs(drag_diff) < self.diff_length:
                    # Lower threshold to 0 incrementally, to guarantee it'll eventually be exceeded
                    self.diff_length = max(0, self.diff_length - 1)
                    return

                # Threshold cleared — start/continue transaction on first actual value change
                if (
                    not self.transaction_id
                    and not self.clip_properties_model.ignore_update_signal
                ):
                    self.start_transaction(self.selected_item)
                self.update_in_progress = True

                # Compute size of property's possible values range
                min_max_range = float(property_max) - float(property_min)

                if min_max_range < 1000.0:
                    # Small range - use cursor to calculate new value as percentage of total range
                    self.new_value = property_min + (min_max_range * cursor_value_percent)
                else:
                    # range is unreasonably long (such as position, start, end, etc.... which can be huge #'s)

                    # Get the current value and apply fixed adjustments in response to motion
                    if self.new_value is None:
                        self.new_value = QLocale().system().toDouble(self.selected_item.text())[0]
                    step = 1.0 if property_type == "int" else 0.50

                    if drag_diff > 0:
                        # Move to the left by a small amount
                        self.new_value -= step
                    elif drag_diff < 0:
                        # Move to the right by a small amount
                        self.new_value += step

                # Clamp value between min and max (just incase user drags too big)
                self.new_value = max(property_min, self.new_value)
                self.new_value = min(property_max, self.new_value)

                if property_type == "int":
                    if self.new_value >= 0:
                        self.new_value = math.floor(self.new_value + 0.5)
                    else:
                        self.new_value = math.ceil(self.new_value - 0.5)

                # Update value of this property
                self.clip_properties_model.value_updated(self.selected_item, -1, self.new_value)

                # Repaint
                self.viewport().update()

    def leaveEvent(self, event):
        self.viewport().unsetCursor()
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event):
        # Inform UpdateManager to accept updates, and only store our final update
        event.accept()
        get_app().updates.ignore_history = False
        self.mouse_pressed = False

        log.debug('mouseReleaseEvent: apply_last_action to history')

        if self.update_in_progress:
            self.finalize_transaction()

        # Get data model and selection
        model = self.clip_properties_model.model
        pos = _event_posf(event).toPoint()
        row = self.indexAt(pos).row()
        if model.item(row, 0):
            self.selected_label = model.item(row, 0)
            self.selected_item = model.item(row, 1)

        # Allow new selection and prepare to set minimum move threshold
        self.lock_selection = False
        self.previous_x = -1
        self.new_value = None

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
                font, ok = get_font_dialog_selection(current_font, self.win, _("Change Font"))

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

            elif property_type == "colorgrade_curve":
                self._open_curve_editor(cur_property, model_index)

            elif property_type == "colorgrade_wheels":
                self._open_wheels_editor(cur_property)

    def _open_curve_editor(self, cur_property, model_index):
        """Open the curve editor dialog for a colorgrade_curve property."""
        curve_data = normalize_curve_data(cur_property[1].get("curve"))
        property_key = cur_property[0]
        dialog = ColorGradeCurveDialog(curve_data, cur_property[1].get("channel", "all"),
                                       self.clip_properties_model.frame_number, self.win,
                                       title=cur_property[1].get("name"))
        item = self.selected_item
        dialog._property_key = property_key
        dialog._item_data = copy.deepcopy(item.data()) if item else None
        self.color_grade_curve_dialogs.add(dialog)
        dialog.destroyed.connect(lambda *_args, dlg=dialog: self.color_grade_curve_dialogs.discard(dlg))
        dialog.curve_widget().curveChanged.connect(
            lambda value, item=item, key=property_key, dlg=dialog: self.preview_curve_property_value(
                item, key, value, getattr(dlg, "_item_data", None))
        )
        dialog.changeStarted.connect(
            lambda item=item, key=property_key, dlg=dialog: self.start_curve_property_change(
                item, key, getattr(dlg, "_item_data", None)))
        dialog.changeStarted.connect(self.pause_live_property_caching)
        dialog.changeFinished.connect(self.resume_live_property_caching)
        dialog.changeFinished.connect(self.finish_property_change)
        dialog.setAttribute(Qt.WA_DeleteOnClose, True)
        self._place_curve_dialog_near_index(dialog, model_index)
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def _open_wheels_editor(self, cur_property):
        """Open (or raise) the color wheels dock for a colorgrade_wheels property."""
        wheels_data = normalize_wheels_data(cur_property[1].get("wheels"))
        property_key = cur_property[0]
        self._ensure_color_grade_wheels_dock_attached()
        self.color_grade_wheels_panel.setEnabled(True)
        if self.live_property_session and self.live_property_session.get("property_type") == "colorgrade_wheels":
            self.color_grade_wheels_dock.show()
            self.color_grade_wheels_dock.raise_()
            return
        self._activate_color_grade_wheels_session(self.selected_item, property_key, wheels_data)
        self.color_grade_wheels_dock.show()
        self.color_grade_wheels_dock.raise_()

    def Edit_Color_Grade_Action_Triggered(self):
        """Context menu handler: open the curve or wheels editor for the selected property."""
        row = self.selected_item.row() if self.selected_item else None
        if row is None:
            return
        model = self.clip_properties_model.model
        selected_label = model.item(row, 0)
        if not selected_label or not selected_label.data():
            return
        cur_property = selected_label.data()
        # Use cell rect centre as a stand-in model_index for dialog placement
        model_index = model.index(row, 1)
        if self.property_type == "colorgrade_curve":
            self._open_curve_editor(cur_property, model_index)
        elif self.property_type == "colorgrade_wheels":
            self._open_wheels_editor(cur_property)

    def caption_text_updated(self, new_caption_text, caption_model_row):
        """Caption text has been updated in the caption editor, and needs saving"""
        if caption_model_row is None:
            # Ignore blank selections
            return

        caption_model_label = caption_model_row[0]
        caption_model_value = caption_model_row[1]

        # Verify label has not been deleted
        if (caption_model_label and isdeleted(caption_model_label)) or \
                (caption_model_value and isdeleted(caption_model_value)):
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

    def caption_text_committed(self, caption_model_row):
        """Finalize a batch of live Caption editor updates into one undo action."""
        if caption_model_row is None:
            return
        if self.update_in_progress:
            self.finalize_transaction()

    def select_item(self, selection):
        """Update the selected items in the properties window"""

        self.current_selection = list(selection or [])
        if selection and not self._selection_is_color_grade(selection):
            self._close_color_grade_editors(commit_changes=True)

        self._update_color_grade_wheels_enabled(selection)
        self.clip_properties_model.update_item(selection)
        QTimer.singleShot(125, self._auto_connect_color_grade_wheels_dock)

    def select_frame(self, frame_number):
        """ Update the values of the selected clip, based on the current frame """

        # Update item
        self.clip_properties_model.update_frame(frame_number)
        self._sync_color_grade_editors_to_current_frame()

    def filter_changed(self, value=None):
        """ Filter the list of properties """

        # Update property model (and re-trigger filter logic)
        self.clip_properties_model.update_model(value)

        # Filter keyframes visible on timeline
        get_app().window.SetKeyframeFilter.emit(value)

    def contextMenuEvent(self, event):
        """ Display context menu """
        # Get property being acted on
        pos = _event_posf(event).toPoint()
        index = self.indexAt(pos)
        if not index.isValid():
            event.ignore()
            return

        # Get data model and selection
        idx = self.indexAt(pos)
        row = idx.row()
        selected_label = idx.model().item(row, 0)
        selected_value = idx.model().item(row, 1)
        self.selected_item = selected_value
        self.selected_label = selected_label
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
            # Work on a copy so dynamic menu construction doesn't mutate the
            # property's stored choices and leave stale entries behind.
            self.choices = copy.deepcopy(cur_property[1]["choices"])
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

                # Handle generated mask source effect options
                if property_key == "mask_source_id" and not self.choices:
                    tracked_effect_choices = self._tracked_mask_source_choices(item_id)

                    self.choices.append({"name": _("None"), "value": "", "selected": False, "icon": None})
                    if tracked_effect_choices:
                        self.choices.append({
                            "name": _("Tracked Objects"),
                            "value": tracked_effect_choices,
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
                    file_id = idx.sibling(i, 5).data()
                    file_obj = File.get(id=file_id) if file_id else None
                    path = file_obj.absolute_path() if file_obj else ""
                    if not path:
                        continue
                    file_data = getattr(file_obj, "data", {}) or {}

                    # Append file choice
                    file_choices.append({"name": name,
                                         "value": {
                                             "file_id": file_id,
                                             "path": path,
                                             "start": file_data.get("start"),
                                             "end": file_data.get("end"),
                                         },
                                         "selected": False,
                                         "icon": icon
                                         })

                # Add None option to clear the source
                self.choices.append({"name": _("None"), "value": "", "selected": False, "icon": None})


                # Add root file choice
                if file_choices:
                    self.choices.append({"name": _("Files"), "value": file_choices, "selected": False, "icon": None})

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
                    track_name = track.get("label") or _("Track %s") % QLocale().toString(display_count)
                    self.choices.append({"name": track_name, "value": track.get("number"), "selected": False, "icon": None})
                    display_count -= 1

            elif self.property_type == "font":
                # Get font from user
                current_font_name = cur_property[1].get("memo", "sans")
                current_font = QFont(current_font_name)
                font, ok = get_font_dialog_selection(current_font, self.win, _("Change Font"))

                # Update font
                if ok and font:
                    fontinfo = QFontInfo(font)
                    self.clip_properties_model.value_updated(self.selected_item, value=fontinfo.family())

            # Add menu options for keyframes
            menu = StyledContextMenu(parent=self)
            if self.property_type == "color":
                Color_Action = menu.addAction(_("Select a Color"))
                Color_Action.triggered.connect(functools.partial(self.Color_Picker_Triggered, cur_property))
                menu.addSeparator()
            if self.property_type in ["colorgrade_curve", "colorgrade_wheels"]:
                Edit_Action = menu.addAction(_("Edit"))
                Edit_Action.triggered.connect(self.Edit_Color_Grade_Action_Triggered)
                menu.addSeparator()
                Reset_Action = menu.addAction(_("Reset"))
                Reset_Action.triggered.connect(self.Reset_Color_Grade_Action_Triggered)
                menu.addSeparator()
            if points > 1:
                # Menu items only for multiple points
                populate_keyframe_context_menu(
                    menu,
                    bezier_callback=self.Bezier_Action_Triggered,
                    linear_callback=self.Linear_Action_Triggered,
                    constant_callback=self.Constant_Action_Triggered,
                    bezier_icon=self.bezier_icon,
                    linear_icon=self.linear_icon,
                    constant_icon=self.constant_icon,
                )
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
                self.menu.show_at(event)
                # Focus the first menu item for keyboard navigation
                actions = self.menu.actions()
                if actions:
                    self.menu.setActiveAction(actions[0])

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

    def Reset_Color_Grade_Action_Triggered(self):
        log.info("Reset_Color_Grade_Action_Triggered")
        if self.property_type == "colorgrade_curve":
            current_value = normalize_curve_data(self.selected_label.data()[1].get("curve"))
            reset_value = default_curve_data()
            reset_value["enabled"] = copy.deepcopy(current_value.get("enabled"))
        elif self.property_type == "colorgrade_wheels":
            current_value = normalize_wheels_data(self.selected_label.data()[1].get("wheels"))
            reset_value = default_wheels_data()
            reset_value["enabled_keyframes"] = copy.deepcopy(current_value.get("enabled_keyframes"))
        else:
            return

        if not self.clip_properties_model.ignore_update_signal:
            self.start_transaction(self.selected_item)
        self.update_in_progress = True
        self.clip_properties_model.value_updated(self.selected_item, value=reset_value)
        property_key = self.selected_label.data()[0]
        self._update_property_preview(self.selected_item, self.property_type, property_key, reset_value)
        self._sync_color_grade_editors(self.property_type, property_key, reset_value)
        if not self.mouse_pressed:
            self.finalize_transaction()

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
        if (self.selected_label and isdeleted(self.selected_label)) or \
                (self.selected_item and isdeleted(self.selected_item)):
            log.debug("Property has been deleted, skipping")
            self.selected_label = None
            self.selected_item = None

        if self.selected_item:
            self.clip_properties_model.insert_keyframe(self.selected_item)

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

        # Restore focus to label column (column 0) for visible focus indicator
        current_row = self.currentIndex().row()
        if current_row >= 0:
            self.setCurrentIndex(self.clip_properties_model.model.index(current_row, 0))

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
        self.win.files_model.ModelRefreshed.connect(self.refresh_menu)
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
        self.current_selection = []
        self.live_property_session = None
        self.live_property_cache_paused = False
        self.color_grade_curve_dialogs = set()

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

        # Enable hover cursor updates without requiring a button press
        self.viewport().setMouseTracking(True)

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
        get_app().window.CaptionTextCommitted.connect(self.caption_text_committed)

        self.color_grade_wheels_dock = QDockWidget(get_app()._tr("Color Wheels"), self.win)
        self.color_grade_wheels_dock.setObjectName("dockColorGradeWheels")
        self.color_grade_wheels_panel = ColorGradeWheelsPanel(
            frame_number=self.clip_properties_model.frame_number,
            parent=self.color_grade_wheels_dock,
        )
        self.color_grade_wheels_scroll = QScrollArea(self.color_grade_wheels_dock)
        self.color_grade_wheels_scroll.setWidgetResizable(True)
        self.color_grade_wheels_scroll.setFrameShape(QFrame.NoFrame)
        self.color_grade_wheels_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.color_grade_wheels_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.color_grade_wheels_scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }"
            "QScrollArea > QWidget { background: transparent; }"
        )
        self.color_grade_wheels_scroll.setWidget(self.color_grade_wheels_panel)
        self.color_grade_wheels_dock.setWidget(self.color_grade_wheels_scroll)
        self.color_grade_wheels_panel.setEnabled(False)
        self.color_grade_wheels_dock.hide()
        self.win.addDocks([self.color_grade_wheels_dock], Qt.RightDockWidgetArea)
        self.color_grade_wheels_panel.wheelsChanged.connect(self.preview_live_property_value)
        self.color_grade_wheels_panel.dragStarted.connect(self._wheels_drag_started)
        self.color_grade_wheels_panel.dragFinished.connect(self._wheels_drag_finished)
        self.color_grade_wheels_dock.visibilityChanged.connect(self._color_grade_wheels_visibility_changed)

    def _show_scope_docks_if_hidden(self):
        """Show scope docks if currently hidden."""
        win = self.win
        for attr in ("dockLumaWaveform", "dockHistogram", "dockVectorscope", "dockAudio"):
            dock = getattr(win, attr, None)
            if dock and not dock.isVisible():
                dock.show()

    def _ensure_color_grade_wheels_dock_attached(self):
        if self.win.dockWidgetArea(self.color_grade_wheels_dock) == Qt.NoDockWidgetArea:
            self.win.addDocks([self.color_grade_wheels_dock], Qt.RightDockWidgetArea)
        if self.color_grade_wheels_dock.isFloating():
            # Only call setFloating(False) when actually floating — calling it
            # unconditionally triggers setWindowFlags → reparentFocusWidgets over
            # the entire (large) ColorGradeWheelsPanel widget tree, freezing the UI.
            self.color_grade_wheels_dock.setFloating(False)

    def _color_grade_wheels_visibility_changed(self, visible):
        if visible:
            if self.win.dockWidgetArea(self.color_grade_wheels_dock) == Qt.NoDockWidgetArea:
                self.win.addDocks([self.color_grade_wheels_dock], Qt.RightDockWidgetArea)
                # If scope docks are already at bottom-right, split so Wheels sits above them
                scope_docks = [self.win.dockLumaWaveform,
                               self.win.dockHistogram,
                               self.win.dockVectorscope,
                               self.win.dockAudio]
                anchored_scope = [d for d in scope_docks
                                  if self.win.dockWidgetArea(d) != Qt.NoDockWidgetArea
                                  and d.isVisible()]
                if anchored_scope:
                    self.win.splitDockWidget(
                        self.color_grade_wheels_dock, anchored_scope[0], Qt.Vertical)
                self.color_grade_wheels_dock.show()
                self.color_grade_wheels_dock.raise_()
            self._update_color_grade_wheels_enabled()
            QTimer.singleShot(125, self._reconnect_color_grade_wheels_session)
            return
        # Only end the session if the dock was truly closed, not just hidden behind
        # another tab in a tabified group (dockWidgetArea still valid in that case).
        if self.win.dockWidgetArea(self.color_grade_wheels_dock) != Qt.NoDockWidgetArea:
            return
        if self.live_property_session and self.live_property_session.get("property_type") == "colorgrade_wheels":
            self.accept_live_property_session()

    def _place_curve_dialog_near_index(self, dialog, index):
        rect = self.visualRect(index)
        if not rect.isValid():
            return

        top_left = self.viewport().mapToGlobal(rect.topLeft())
        top_right = self.viewport().mapToGlobal(rect.topRight())
        anchor_center_x = (top_left.x() + top_right.x()) // 2

        dialog_size = dialog.sizeHint()
        x = anchor_center_x - (dialog_size.width() // 2)
        y = top_left.y() - dialog_size.height() - 6

        screen = QGuiApplication.screenAt(QPoint(anchor_center_x, top_left.y()))
        if not screen:
            screen = self.window().screen()
        if not screen:
            dialog.move(x, y)
            return

        available = screen.availableGeometry()
        min_x = available.left()
        max_x = available.right() - dialog_size.width() + 1
        x = max(min_x, min(x, max_x))

        min_y = available.top()
        if y < min_y:
            y = self.viewport().mapToGlobal(rect.bottomLeft()).y() + 6
            max_y = available.bottom() - dialog_size.height() + 1
            y = max(min_y, min(y, max_y))

        dialog.move(x, y)


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
            get_app().window.dockProperties.setWindowTitle(_("%d selections") % count)
            self.lblSelection.setVisible(False)
            self.btnSelectionName.setVisible(False)
            return
        def _set_item_icon(path):
            if path and isinstance(path, (str, bytes, os.PathLike)) and os.path.exists(path):
                self.item_icon = QIcon(QPixmap(path))
            else:
                self.item_icon = QIcon()

        if self.item_type == "clip":
            clip = Clip.get(id=self.item_id)
            if clip:
                self.item_name = clip.title()
                _set_item_icon(clip.data.get('image'))
        elif self.item_type == "transition":
            trans = Transition.get(id=self.item_id)
            if trans:
                self.item_name = _(trans.title())
                _set_item_icon(trans.data.get('reader', {}).get('path'))
        elif self.item_type == "effect":
            effect = Effect.get(id=self.item_id)
            if effect:
                self.item_name = _(effect.title())
                _set_item_icon(os.path.join(info.PATH, "effects", "icons", "%s.png" % effect.data.get('class_name').lower()))

        # Truncate long text
        if self.item_name and len(self.item_name) > 25:
            self.item_name = "%s..." % self.item_name[:22]

        # Set label and Dock window title
        win = get_app().window
        if self.item_id:
            win.dockProperties.setWindowTitle(self.item_name)
            self.lblSelection.setVisible(False)
            self.btnSelectionName.setVisible(False)
        else:
            win.dockProperties.setWindowTitle(_("Properties"))
            self.lblSelection.setVisible(False)
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
        self.setObjectName("selectionLabel")
        self.btnSelectionName.setObjectName("btnSelectionName")
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
