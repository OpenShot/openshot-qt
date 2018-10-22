"""
 @file
 @brief This file loads the Preferences dialog (i.e where is all preferences)
 @author Jonathan Thomas <jonathan@openshot.org>
 @author Olivier Girard <olivier@openshot.org>

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
import operator
import functools

from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from PyQt5.QtGui import QKeySequence
from PyQt5 import uic

from classes import info, ui_util, settings, qt_types, updates
from classes.app import get_app
from classes.language import get_all_languages
from classes.logger import log
from classes.metrics import *
import openshot


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

        # Track metrics
        track_metric_screen("preferences-screen")

        # Load all user values
        self.params = {}
        for item in self.settings_data:
            if "setting" in item and "value" in item:
                self.params[item["setting"]] = item

        self.requires_restart = False
        self.category_names = {}
        self.category_tabs = {}
        self.category_sort = {}

        # Loop through settings and find all unique categories
        for item in self.settings_data:
            category = item.get("category")
            setting_type = item.get("type")
            sort_category = item.get("sort")

            # Indicate sorted category
            if sort_category:
                self.category_sort[category] = sort_category

            if not setting_type == "hidden":
                # Load setting
                if not category in self.category_names:
                    self.category_names[category] = []

                    # Create scrollarea
                    scroll_area = QScrollArea(self)
                    scroll_area.setWidgetResizable(True)
                    scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
                    scroll_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

                    # Create tab widget and layout
                    layout = QVBoxLayout()
                    tabWidget = QWidget(self)
                    tabWidget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
                    tabWidget.setLayout(layout)
                    scroll_area.setWidget(tabWidget)

                    # Add tab
                    self.tabCategories.addTab(scroll_area, _(category))
                    self.category_tabs[category] = tabWidget

                # Append translated title
                item["title_tr"] = _(item.get("title"))

                # Append settings into correct category
                self.category_names[category].append(item)

        # Loop through each category setting, and add them to the tabs
        for category in self.category_tabs.keys():
            tabWidget = self.category_tabs[category]

            # Get list of items in category
            params = self.category_names[category]
            if self.category_sort.get(category):
                # Sort this category by translated title
                params.sort(key=operator.itemgetter("title_tr"))

            # Loop through settings for each category
            for param in params:

                # Create Label
                widget = None
                extraWidget = None
                label = QLabel()
                label.setText(_(param["title"]))
                label.setToolTip(_(param["title"]))

                if param["type"] == "spinner":
                    # create QDoubleSpinBox
                    widget = QDoubleSpinBox()
                    widget.setMinimum(float(param["min"]))
                    widget.setMaximum(float(param["max"]))
                    widget.setValue(float(param["value"]))
                    widget.setSingleStep(1.0)
                    widget.setToolTip(param["title"])
                    widget.valueChanged.connect(functools.partial(self.spinner_value_changed, param))

                if param["type"] == "spinner-int":
                    # create QDoubleSpinBox
                    widget = QSpinBox()
                    widget.setMinimum(int(param["min"]))
                    widget.setMaximum(int(param["max"]))
                    widget.setValue(int(param["value"]))
                    widget.setSingleStep(1.0)
                    widget.setToolTip(param["title"])
                    widget.valueChanged.connect(functools.partial(self.spinner_value_changed, param))

                elif param["type"] == "text":
                    # create QLineEdit
                    widget = QLineEdit()
                    widget.setText(_(param["value"]))
                    widget.textChanged.connect(functools.partial(self.text_value_changed, widget, param))

                elif param["type"] == "browse":
                    # create QLineEdit
                    widget = QLineEdit()
                    widget.setText(_(param["value"]))
                    widget.textChanged.connect(functools.partial(self.text_value_changed, widget, param))
                    extraWidget = QPushButton("Browse")
                    extraWidget.clicked.connect(functools.partial(self.selectExecutable, widget, param))

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

                    # Get values
                    value_list = param["values"]
                    # Overwrite value list (for profile dropdown)
                    if param["setting"] == "default-profile":
                        value_list = []
                        # Loop through profiles
                        for profile_folder in [info.USER_PROFILES_PATH, info.PROFILES_PATH]:
                            for file in os.listdir(profile_folder):
                                # Load Profile and append description
                                profile_path = os.path.join(profile_folder, file)
                                profile = openshot.Profile(profile_path)
                                value_list.append({"name":profile.info.description, "value":profile.info.description})
                        # Sort profile list
                        value_list.sort(key=operator.itemgetter("name"))

                    # Overwrite value list (for language dropdown)
                    if param["setting"] == "default-language":
                        value_list = []
                        # Loop through languages
                        for locale, language, country in get_all_languages():
                            # Load Profile and append description
                            if language:
                                lang_name = "%s (%s)" % (language, locale)
                                value_list.append({"name":lang_name, "value":locale})
                        # Sort profile list
                        value_list.sort(key=operator.itemgetter("name"))
                        # Add Default to top of list
                        value_list.insert(0, {"name":_("Default"), "value":"Default"})


                    # Add normal values
                    box_index = 0
                    for value_item in value_list:
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
                    # Add minimum size
                    label.setMinimumWidth(180);
                    label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
                    widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

                    # Create HBox layout
                    layout_hbox = QHBoxLayout()
                    layout_hbox.addWidget(label)
                    layout_hbox.addWidget(widget)
                    layout_hbox.addWidget(extraWidget)

                    # Add widget to layout
                    tabWidget.layout().addLayout(layout_hbox)
                elif (label):
                    # Add widget to layout
                    tabWidget.layout().addWidget(label)

            # Add stretch to bottom of layout
            tabWidget.layout().addStretch()

    def selectExecutable(self, widget, param):
        fileName, _ = QFileDialog.getOpenFileName(self,"Select executable file", QDir.rootPath(),"All Files (*)")
        if fileName:
            self.s.set(param["setting"], fileName)
            widget.setText(fileName)

    def check_for_restart(self, param):
        """Check if the app needs to restart"""
        if "restart" in param and param["restart"]:
            self.requires_restart = True

    def bool_value_changed(self, widget, param, state):
        # Save setting
        if state == Qt.Checked:
            self.s.set(param["setting"], True)
        else:
            self.s.set(param["setting"], False)

        # Trigger specific actions
        if param["setting"] == "debug-mode":
            # Update debug setting of timeline
            log.info("Setting debug-mode to %s" % (state == Qt.Checked))
            debug_enabled = (state == Qt.Checked)

            # Enable / Disable logger
            openshot.ZmqLogger.Instance().Enable(debug_enabled)

        elif param["setting"] == "enable-auto-save":
            # Toggle autosave
            if (state == Qt.Checked):
                # Start/Restart autosave timer
                get_app().window.auto_save_timer.start()
            else:
                # Stop autosave timer
                get_app().window.auto_save_timer.stop()

        elif param["setting"] == "hardware_decode":
            if (state == Qt.Checked):
                # Enable hardware decode environment variable
                os.environ['OS2_DECODE_HW'] = "1"
            else:
                # Disable hardware decode environment variable
                os.environ['OS2_DECODE_HW'] = "0"

        elif param["setting"] == "omp_threads_enabled":
            if (state == Qt.Checked):
                # Enable OMP multi-threading
                os.environ['OS2_OMP_THREADS'] = "1"
            else:
                # Disable OMP multi-threading
                os.environ['OS2_OMP_THREADS'] = "0"

        # Check for restart
        self.check_for_restart(param)

    def spinner_value_changed(self, param, value):
        # Save setting
        self.s.set(param["setting"], value)
        log.info(value)

        if param["setting"] == "autosave-interval":
            # Update autosave interval (# of minutes)
            get_app().window.auto_save_timer.setInterval(value * 1000 * 60)

        # Apply cache settings (if needed)
        if param["setting"] in ["cache-limit-mb", "cache-scale", "cache-quality"]:
            get_app().window.InitCacheSettings()

        # Check for restart
        self.check_for_restart(param)

    def text_value_changed(self, widget, param, value=None):
        try:
            # Attempt to load value from QTextEdit (i.e. multi-line)
            if not value:
                value = widget.toPlainText()
        except:
            pass

        # If this setting is a keyboard mapping, parse it first
        if param.get("category") == "Keyboard":
            previous_value = value
            value = QKeySequence(value).toString()
            log.info("Parsing keyboard mapping via QKeySequence from %s to %s" % (previous_value, value))

        # Save setting
        self.s.set(param["setting"], value)
        log.info(value)

        # Check for restart
        self.check_for_restart(param)

    def dropdown_index_changed(self, widget, param, index):
        # Save setting
        value = widget.itemData(index)
        self.s.set(param["setting"], value)
        log.info(value)

        # Apply cache settings (if needed)
        if param["setting"] in ["cache-mode", "cache-image-format"]:
            get_app().window.InitCacheSettings()

        # Check for restart
        self.check_for_restart(param)

    def closeEvent(self, event):
        """Signal for closing Preferences window"""
        # Invoke the close button
        self.reject()

    def reject(self):
        # Prompt user to restart openshot (if needed)
        if self.requires_restart:
            msg = QMessageBox()
            _ = get_app()._tr
            msg.setWindowTitle(_("Restart Required"))
            msg.setText(_("Please restart OpenShot for all preferences to take effect."))
            msg.exec_()

        # Close dialog
        super(Preferences, self).reject()
