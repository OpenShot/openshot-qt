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
from functools import partial
from PyQt5.QtCore import Qt, QRectF, QLocale, pyqtSignal, Qt, QObject, QTimer
from PyQt5.QtGui import *
from PyQt5.QtWidgets import QTableView, QAbstractItemView, QMenu, QSizePolicy, QHeaderView, QColorDialog, QItemDelegate, QStyle, QLabel, QPushButton, QHBoxLayout, QFrame

from classes.logger import log
from classes.app import get_app
from classes import info
from classes.query import Clip, Effect, Transition
from windows.models.properties_model import PropertiesModel

import openshot

try:
    import json
except ImportError:
    import simplejson as json


class PropertyDelegate(QItemDelegate):
    def __init__(self, parent=None, *args):
        QItemDelegate.__init__(self, parent, *args)

        # pixmaps for curve icons
        self.curve_pixmaps = { openshot.BEZIER: QPixmap(os.path.join(info.IMAGES_PATH, "keyframe-%s.png" % openshot.BEZIER)),
                               openshot.LINEAR: QPixmap(os.path.join(info.IMAGES_PATH, "keyframe-%s.png" % openshot.LINEAR)),
                               openshot.CONSTANT: QPixmap(os.path.join(info.IMAGES_PATH, "keyframe-%s.png" % openshot.CONSTANT))
                             }

    def paint(self, painter, option, index):
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)

        # Get data model and selection
        model = get_app().window.propertyTableView.clip_properties_model.model
        row = model.itemFromIndex(index).row()
        selected_label = model.item(row, 0)
        selected_value = model.item(row, 1)
        property = selected_label.data()

        # Get min/max values for this property
        property_name = property[1]["name"]
        property_type = property[1]["type"]
        property_max = property[1]["max"]
        property_min = property[1]["min"]
        readonly = property[1]["readonly"]
        keyframe = property[1]["keyframe"]
        points = property[1]["points"]
        interpolation = property[1]["interpolation"]

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
            red = property[1]["red"]["value"]
            green = property[1]["green"]["value"]
            blue = property[1]["blue"]["value"]
            painter.setBrush(QBrush(QColor(QColor(red, green, blue))))
        else:
            # Normal Keyframe
            if option.state & QStyle.State_Selected:
                painter.setBrush(QBrush(QColor("#575757")))
            else:
                painter.setBrush(QBrush(QColor("#3e3e3e")))

        if not readonly:
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
            path.addRoundedRect(value_rect, 15, 15);
            painter.fillPath(path, gradient)
            painter.drawPath(path);
            painter.setClipping(False)

            if points > 1:
                # Draw interpolation icon on top
                painter.drawPixmap(option.rect.x() + option.rect.width() - 30.0, option.rect.y() + 4, self.curve_pixmaps[interpolation])

        # set text color
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
        row = self.indexAt(event.pos()).row()
        column = self.indexAt(event.pos()).column()
        if model.item(row, 0):
            self.selected_label = model.item(row, 0)
            self.selected_item = model.item(row, 1)

        # Is the user dragging on the value column
        if self.selected_label and self.selected_item:
            frame_number = self.clip_properties_model.frame_number

            # Get the position of the cursor and % value
            value_column_x = self.columnViewportPosition(1)
            value_column_y = value_column_x + self.columnWidth(1)
            cursor_value = event.x() - value_column_x
            cursor_value_percent = cursor_value / self.columnWidth(1)

            try:
                property = self.selected_label.data()
            except Exception as ex:
                # If item is deleted during this drag... an exception can occur
                # Just ignore, since this is harmless
                return

            property_key = property[0]
            property_name = property[1]["name"]
            property_type = property[1]["type"]
            property_max = property[1]["max"]
            property_min = property[1]["min"]
            property_value = property[1]["value"]
            readonly = property[1]["readonly"]
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

                if c:
                    if property_key in c.data:
                        # Grab the original data for this item/property
                        self.original_data = c.data

            # Calculate percentage value
            if property_type in ["float", "int"]:
                min_max_range = float(property_max) - float(property_min)

                # Determine if range is unreasonably long (such as position, start, end, etc.... which can be huge #'s)
                if min_max_range > 1000.0:
                    # Get the current value
                    self.new_value = QLocale().system().toDouble(self.selected_item.text())[0]

                    # Huge range - increment / decrement slowly
                    if self.previous_x == -1:
                        # init previous_x for the first time
                        self.previous_x = event.x()
                    # calculate # of pixels dragged
                    drag_diff = self.previous_x - event.x()
                    if drag_diff > 0:
                        # Move to the left by a small amount
                        self.new_value -= 0.50
                    elif drag_diff < 0:
                        # Move to the right by a small amount
                        self.new_value += 0.50
                    # update previous x
                    self.previous_x = event.x()
                else:
                    # Small range - use cursor % to calculate new value
                    self.new_value = property_min + (min_max_range * cursor_value_percent)

                # Clamp value between min and max (just incase user drags too big)
                self.new_value = max(property_min, self.new_value)
                self.new_value = min(property_max, self.new_value)

                # Update value of this property
                self.clip_properties_model.value_updated(self.selected_item, -1, self.new_value)

                # Repaint
                self.viewport().update()

    def mouseReleaseEvent(self, event):
        # Inform UpdateManager to accept updates, and only store our final update
        get_app().updates.ignore_history = False

        # Add final update to undo/redo history
        get_app().updates.apply_last_action_to_history(self.original_data)

        # Clear original data
        self.original_data = None

        # Get data model and selection
        model = self.clip_properties_model.model
        row = self.indexAt(event.pos()).row()
        column = self.indexAt(event.pos()).column()
        if model.item(row, 0):
            self.selected_label = model.item(row, 0)
            self.selected_item = model.item(row, 1)

    def doubleClickedCB(self, model_index):
        """Double click handler for the property table"""
        # Get data model and selection
        model = self.clip_properties_model.model

        row = model_index.row()
        selected_label = model.item(row, 0)
        self.selected_item = model.item(row, 1)

        if selected_label:
            property = selected_label.data()
            property_type = property[1]["type"]

            if property_type == "color":
                # Get current value of color
                red = property[1]["red"]["value"]
                green = property[1]["green"]["value"]
                blue = property[1]["blue"]["value"]

                # Show color dialog
                currentColor = QColor(red, green, blue)
                newColor = QColorDialog.getColor(currentColor)

                # Set the new color keyframe
                self.clip_properties_model.color_update(self.selected_item, newColor)

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

        # Update model
        self.clip_properties_model.update_model(value)

    def contextMenuEvent(self, event):
        # Get data model and selection
        model = self.clip_properties_model.model
        row = self.indexAt(event.pos()).row()
        selected_label = model.item(row, 0)
        selected_value = model.item(row, 1)
        self.selected_item = selected_value
        frame_number = self.clip_properties_model.frame_number

        # Get translation object
        _ = get_app()._tr

        # If item selected
        if selected_label:
            # Get data from selected item
            property = selected_label.data()
            property_name = property[1]["name"]
            self.property_type = property[1]["type"]
            points = property[1]["points"]
            self.choices = property[1]["choices"]
            property_key = property[0]
            clip_id, item_type = selected_value.data()

            log.info("Context menu shown for %s (%s) for clip %s on frame %s" % (
                property_name, property_key, clip_id, frame_number))
            log.info("Points: %s" % points)
            log.info("Property: %s" % str(property))

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

            bezier_icon = QIcon(QPixmap(os.path.join(info.IMAGES_PATH, "keyframe-%s.png" % openshot.BEZIER)))
            linear_icon = QIcon(QPixmap(os.path.join(info.IMAGES_PATH, "keyframe-%s.png" % openshot.LINEAR)))
            constant_icon = QIcon(QPixmap(os.path.join(info.IMAGES_PATH, "keyframe-%s.png" % openshot.CONSTANT)))

            # Add menu options for keyframes
            menu = QMenu(self)
            if points > 1:
                # Menu for more than 1 point
                Bezier_Menu = QMenu(_("Bezier"), self)
                Bezier_Menu.setIcon(bezier_icon)
                for bezier_preset in bezier_presets:
                    preset_action = Bezier_Menu.addAction(bezier_preset[4])
                    preset_action.triggered.connect(partial(self.Bezier_Action_Triggered, bezier_preset))
                menu.addMenu(Bezier_Menu)
                Linear_Action = menu.addAction(_("Linear"))
                Linear_Action.setIcon(linear_icon)
                Linear_Action.triggered.connect(self.Linear_Action_Triggered)
                Constant_Action = menu.addAction(_("Constant"))
                Constant_Action.setIcon(constant_icon)
                Constant_Action.triggered.connect(self.Constant_Action_Triggered)
                menu.addSeparator()
                Insert_Action = menu.addAction(_("Insert Keyframe"))
                Insert_Action.triggered.connect(self.Insert_Action_Triggered)
                Remove_Action = menu.addAction(_("Remove Keyframe"))
                Remove_Action.triggered.connect(self.Remove_Action_Triggered)
                menu.popup(QCursor.pos())
            elif points == 1:
                # Menu for a single point
                Insert_Action = menu.addAction(_("Insert Keyframe"))
                Insert_Action.triggered.connect(self.Insert_Action_Triggered)
                Remove_Action = menu.addAction(_("Remove Keyframe"))
                Remove_Action.triggered.connect(self.Remove_Action_Triggered)
                menu.popup(QCursor.pos())

            if self.choices:
                # Menu for choices
                for choice in self.choices:
                    Choice_Action = menu.addAction(_(choice["name"]))
                    Choice_Action.setData(choice["value"])
                    Choice_Action.triggered.connect(self.Choice_Action_Triggered)
                # Show choice menu
                menu.popup(QCursor.pos())

    def Bezier_Action_Triggered(self, preset=[]):
        log.info("Bezier_Action_Triggered: %s" % str(preset))
        if self.property_type != "color":
            # Update keyframe interpolation mode
            self.clip_properties_model.value_updated(self.selected_item, interpolation=0, interpolation_details=preset)
        else:
            # Update colors interpolation mode
            self.clip_properties_model.color_update(self.selected_item, QColor("#000"), interpolation=0, interpolation_details=preset)

    def Linear_Action_Triggered(self, event):
        log.info("Linear_Action_Triggered")
        if self.property_type != "color":
            # Update keyframe interpolation mode
            self.clip_properties_model.value_updated(self.selected_item, interpolation=1)
        else:
            # Update colors interpolation mode
            self.clip_properties_model.color_update(self.selected_item, QColor("#000"), interpolation=1, interpolation_details=[])

    def Constant_Action_Triggered(self, event):
        log.info("Constant_Action_Triggered")
        if self.property_type != "color":
            # Update keyframe interpolation mode
            self.clip_properties_model.value_updated(self.selected_item, interpolation=2)
        else:
            # Update colors interpolation mode
            self.clip_properties_model.color_update(self.selected_item, QColor("#000"), interpolation=2, interpolation_details=[])

    def Insert_Action_Triggered(self, event):
        log.info("Insert_Action_Triggered")
        if self.selected_item:
            current_value = QLocale().system().toDouble(self.selected_item.text())[0]
            self.clip_properties_model.value_updated(self.selected_item, value=current_value)

    def Remove_Action_Triggered(self, event):
        log.info("Remove_Action_Triggered")
        self.clip_properties_model.remove_keyframe(self.selected_item)

    def Choice_Action_Triggered(self, event):
        log.info("Choice_Action_Triggered")
        choice_value = self.sender().data()

        # Update value of dropdown item
        self.clip_properties_model.value_updated(self.selected_item, value=choice_value)

    def __init__(self, *args):
        # Invoke parent init
        QTableView.__init__(self, *args)

        # Get a reference to the window object
        self.win = get_app().window

        # Get Model data
        self.clip_properties_model = PropertiesModel(self)

        # Keep track of mouse press start position to determine when to start drag
        self.selected = []
        self.selected_label = None
        self.selected_item = None
        self.new_value = None
        self.original_data = None

        # Setup header columns
        self.setModel(self.clip_properties_model.model)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setWordWrap(True)

        # Set delegate
        delegate = PropertyDelegate()
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
                action = menu.addAction(item_name)
                action.setIcon(item_icon)
                action.setData({'item_id':item_id, 'item_type':'clip'})
                action.triggered.connect(self.Action_Triggered)

                # Add effects for these clips (if any)
                for effect in clip.data.get('effects'):
                    effect = Effect.get(id=effect.get('id'))
                    if effect:
                        item_name = effect.title()
                        item_icon = QIcon(QPixmap(os.path.join(info.PATH, "effects", "icons", "%s.png" % effect.data.get('class_name').lower())))
                        action = menu.addAction('  >  %s' % _(item_name))
                        action.setIcon(item_icon)
                        action.setData({'item_id': effect.id, 'item_type': 'effect'})
                        action.triggered.connect(self.Action_Triggered)

        # Add selected transitions
        for item_id in get_app().window.selected_transitions:
            trans = Transition.get(id=item_id)
            if trans:
                item_name = _(trans.title())
                item_icon = QIcon(QPixmap(trans.data.get('reader',{}).get('path')))
                action = menu.addAction(_(item_name))
                action.setIcon(item_icon)
                action.setData({'item_id': item_id, 'item_type': 'transition'})
                action.triggered.connect(self.Action_Triggered)

        # Add selected effects
        for item_id in get_app().window.selected_effects:
            effect = Effect.get(id=item_id)
            if effect:
                item_name = _(effect.title())
                item_icon = QIcon(QPixmap(os.path.join(info.PATH, "effects", "icons", "%s.png" % effect.data.get('class_name').lower())))
                action = menu.addAction(_(item_name))
                action.setIcon(item_icon)
                action.setData({'item_id': item_id, 'item_type': 'effect'})
                action.triggered.connect(self.Action_Triggered)

        # Return the menu object
        return menu

    def Action_Triggered(self, event):
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
        QFrame.__init__(self, *args)
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
        hbox.setContentsMargins(0,0,0,0)
        hbox.addWidget(self.lblSelection)
        hbox.addWidget(self.btnSelectionName)
        self.setLayout(hbox)

        # Connect signals
        get_app().window.propertyTableView.loadProperties.connect(self.select_item)