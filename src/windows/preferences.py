"""
 @file
 @brief This file loads the Preferences dialog (i.e where is all preferences)
 @author Jonathan Thomas <jonathan@openshot.org>
 @author Olivier Girard <olivier@openshot.org>

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
import sys
import functools

from PyQt5.QtCore import *
from PyQt5.QtGui import QIcon, QStandardItemModel, QStandardItem
from PyQt5.QtWidgets import *
from PyQt5 import uic

from classes import info, ui_util, settings, qt_types, updates
from classes.app import get_app
from classes.logger import log
from windows.profile_manager import ProfileManager


class Preferences(QDialog):
    """ Preferences Dialog """

    # Path to ui file
    ui_path = os.path.join(info.PATH, 'windows', 'ui', 'preferences.ui')

    def __init__(self):

        # Create dialog class
        QDialog.__init__(self)

        # Load UI from designer
        ui_util.load_ui(self, self.ui_path)

        # Init UI
        ui_util.init_ui(self)

        # get translations
        app = get_app()
        _ = app._tr

        # Get settings
        self.s = settings.get_settings()

        # Dynamically load tabs from settings data
        self.settings_data = settings.get_settings().get_all_settings()

        # Load all user values
        self.params = {}
        for item in self.settings_data:
            if "setting" in item and "value" in item:
                self.params[item["setting"]] = item

        self.category_names = {}
        self.category_tabs = {}
        # Loop through settings and find all unique categories
        for item in self.settings_data:
            category = item["category"]
            setting_type = item["type"]

            if not setting_type == "hidden":
                # Load setting
                if not category in self.category_names:
                    self.category_names[category] = []

                    # Add new category as a tab
                    tabWidget = QWidget(self)
                    self.tabCategories.addTab(tabWidget, _(category))
                    self.category_tabs[category] = tabWidget

                    # Add form layout to this tab
                    layout = QFormLayout(tabWidget)

                # Append settings into correct category
                self.category_names[category].append(item)

        # Loop through each category setting, and add them to the tabs
        for category in self.category_tabs.keys():
            tabWidget = self.category_tabs[category]

            # Loop through settings for each category
            for param in self.category_names[category]:

                # Create Label
                widget = None
                label = QLabel()
                label.setText(_(param["title"]))
                label.setToolTip(_(param["title"]))

                if param["type"] == "spinner":
                    # create spinner
                    widget = QDoubleSpinBox()
                    widget.setMinimum(float(param["min"]))
                    widget.setMaximum(float(param["max"]))
                    widget.setValue(float(param["value"]))
                    widget.setSingleStep(1.0)
                    widget.setToolTip(param["title"])
                    widget.valueChanged.connect(functools.partial(self.spinner_value_changed, param))

                elif param["type"] == "text":
                    # create spinner
                    widget = QLineEdit()
                    widget.setText(_(param["value"]))
                    widget.textChanged.connect(functools.partial(self.text_value_changed, widget, param))

                elif param["type"] == "bool":
                    # create spinner
                    widget = QCheckBox()
                    if param["value"] == True:
                        widget.setCheckState(Qt.Checked)
                    else:
                        widget.setCheckState(Qt.Unchecked)
                    widget.stateChanged.connect(functools.partial(self.bool_value_changed, widget, param))

                elif param["type"] == "dropdown":

                    # create spinner
                    widget = QComboBox()

                    # Add normal values
                    box_index = 0
                    for value_item in param["values"]:
                        k = value_item["name"]
                        v = value_item["value"]
                        # add dropdown item
                        widget.addItem(_(k), v)

                        # select dropdown (if default)
                        if v == param["value"]:
                            widget.setCurrentIndex(box_index)
                        box_index = box_index + 1

                    widget.currentIndexChanged.connect(functools.partial(self.dropdown_index_changed, widget, param))


                # Add Label and Widget to the form
                if (widget and label):
                    tabWidget.layout().addRow(label, widget)
                elif (label):
                    tabWidget.layout().addRow(label)

    def bool_value_changed(self, widget, param, state):
        # Save setting
        if state == Qt.Checked:
            self.s.set(param["setting"], True)
        else:
            self.s.set(param["setting"], False)
        log.info(value)

    def spinner_value_changed(self, param, value):
        # Save setting
        self.s.set(param["setting"], value)
        log.info(value)

    def text_value_changed(self, widget, param, value=None):
        try:
            # Attempt to load value from QTextEdit (i.e. multi-line)
            if not value:
                value = widget.toPlainText()
        except:
            pass

        # Save setting
        self.s.set(param["setting"], value)
        log.info(value)

    def dropdown_index_changed(self, widget, param, index):
        # Save setting
        value = widget.itemData(index)
        self.s.set(param["setting"], value)
        log.info(value)

    def load_profile_manager(self):
        window = ProfileManager()
        window.exec_()
