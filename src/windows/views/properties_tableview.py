""" 
 @file
 @brief This file contains the properties tableview, used by the main window
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

from PyQt5.QtGui import *
from PyQt5.QtWidgets import QTableView, QAbstractItemView, QMenu, QSizePolicy, QHeaderView, QColorDialog

from classes.logger import log
from classes.app import get_app
from windows.models.properties_model import PropertiesModel

try:
    import json
except ImportError:
    import simplejson as json


class PropertiesTableView(QTableView):
    """ A Properties Table QWidget used on the main window """

    # def mousePressEvent(self, event):
    #     """Mouse press handler for the property table"""
    #     if event.button() == 2:
    #         # Show context menu
    #         self.contextMenuEvent(event.pos())


    def double_click(self, model_index):
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

        # Set label
        if item_id:
            get_app().window.lblSelectedItem.setText(_("Selection: %s") % item_id)
        else:
            get_app().window.lblSelectedItem.setText(_("No Selection"))

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

            # Add menu options for keyframes
            menu = QMenu(self)
            if points > 1:
                # Menu for more than 1 point
                Bezier_Action = menu.addAction(_("Bezier"))
                Bezier_Action.triggered.connect(self.Bezier_Action_Triggered)
                Linear_Action = menu.addAction(_("Linear"))
                Linear_Action.triggered.connect(self.Linear_Action_Triggered)
                Constant_Action = menu.addAction(_("Constant"))
                Constant_Action.triggered.connect(self.Constant_Action_Triggered)
                menu.addSeparator()
                Remove_Action = menu.addAction(_("Remove Keyframe"))
                Remove_Action.triggered.connect(self.Remove_Action_Triggered)
                menu.popup(QCursor.pos())
            elif points == 1:
                # Menu for a single point
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

    def Bezier_Action_Triggered(self, event):
        log.info("Bezier_Action_Triggered")
        if self.property_type != "color":
            # Update keyframe interpolation mode
            self.clip_properties_model.value_updated(self.selected_item, 0)
        else:
            # Update colors interpolation mode
            self.clip_properties_model.color_update(self.selected_item, QColor("#000"), 0)

    def Linear_Action_Triggered(self, event):
        log.info("Linear_Action_Triggered")
        if self.property_type != "color":
            # Update keyframe interpolation mode
            self.clip_properties_model.value_updated(self.selected_item, 1)
        else:
            # Update colors interpolation mode
            self.clip_properties_model.color_update(self.selected_item, QColor("#000"), 1)

    def Constant_Action_Triggered(self, event):
        log.info("Constant_Action_Triggered")
        if self.property_type != "color":
            # Update keyframe interpolation mode
            self.clip_properties_model.value_updated(self.selected_item, 2)
        else:
            # Update colors interpolation mode
            self.clip_properties_model.color_update(self.selected_item, QColor("#000"), 2)

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
        self.selected_item = None

        # Setup header columns
        self.setModel(self.clip_properties_model.model)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setWordWrap(True)

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
        self.doubleClicked.connect(self.double_click)
