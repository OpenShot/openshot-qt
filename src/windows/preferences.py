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
import platform

from PyQt5.QtCore import Qt, QSize, QDir
from PyQt5.QtWidgets import (
    QWidget, QDialog, QMessageBox, QFileDialog,
    QVBoxLayout, QHBoxLayout, QSizePolicy,
    QScrollArea, QLabel, QLineEdit, QPushButton,
    QDoubleSpinBox, QComboBox, QCheckBox, QSpinBox,
)
from PyQt5.QtGui import QKeySequence, QIcon

from classes import info, ui_util
from classes import openshot_rc  # noqa
from classes.app import get_app
from classes.language import get_all_languages
from classes.logger import log
from classes.metrics import track_metric_screen

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

        # Get settings
        self.s = get_app().get_settings()

        # Dynamically load tabs from settings data
        self.settings_data = self.s.get_all_settings()

        # Track metrics
        track_metric_screen("preferences-screen")

        # Load all user values
        self.params = {}
        for item in self.settings_data:
            if "setting" in item and "value" in item:
                self.params[item["setting"]] = item

        # Connect search textbox
        self.txtSearch.textChanged.connect(self.txtSearch_changed)

        self.requires_restart = False
        self.category_names = {}
        self.category_tabs = {}
        self.category_sort = {}
        self.visible_category_names = {}

        # Tested hardware modes (default cpu mode with graphics card 0)
        self.hardware_tests_cards = {0: [0, ]}

        # Populate preferences
        self.Populate()

        # Restore normal cursor
        get_app().restoreOverrideCursor()

    def txtSearch_changed(self):
        """textChanged event handler for search box"""
        log.info("Search for %s", self.txtSearch.text())

        # Populate preferences
        self.Populate(filter=self.txtSearch.text())

    def DeleteAllTabs(self, onlyInVisible=False):
        """Delete all tabs"""
        for name, widget in dict(self.category_tabs).items():
            if (onlyInVisible and name not in self.visible_category_names) or not onlyInVisible:
                parent_widget = widget.parent().parent()
                parent_widget.parent().removeWidget(parent_widget)
                parent_widget.deleteLater()

                if name in self.category_names:
                    self.category_names.pop(name)
                if name in self.visible_category_names:
                    self.visible_category_names.pop(name)
                if name in self.category_tabs:
                    self.category_tabs.pop(name)

    def Populate(self, filter=""):
        """Populate all preferences and tabs"""

        # get translations
        app = get_app()
        _ = app._tr

        # Delete all tabs and widgets
        self.DeleteAllTabs()

        self.category_names = {}
        self.category_tabs = {}
        self.category_sort = {}
        self.visible_category_names = {}

        # Loop through settings and find all unique categories
        for item in self.settings_data:
            category = item.get("category")
            setting_type = item.get("type")
            sort_category = item.get("sort")

            # Indicate sorted category
            if sort_category:
                self.category_sort[category] = sort_category

            if setting_type != "hidden":
                # Load setting
                if category not in self.category_names:
                    self.category_names[category] = []

                    # Create scrollarea
                    scroll_area = QScrollArea(self)
                    scroll_area.setWidgetResizable(True)
                    scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
                    scroll_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                    scroll_area.setMinimumSize(675, 100)

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
        for category in dict(self.category_tabs).keys():
            tabWidget = self.category_tabs[category]
            filterFound = False

            # Get list of items in category
            params = self.category_names[category]
            if self.category_sort.get(category):
                # Sort this category by translated title
                params.sort(key=operator.itemgetter("title_tr"))

            # Loop through settings for each category
            for param in params:
                # Is filter found?
                if filter and (filter.lower() in _(param["title"]).lower() or filter.lower() in _(category).lower()):
                    filterFound = True
                elif not filter:
                    filterFound = True
                else:
                    filterFound = False

                # Visible Category
                if filterFound:
                    self.visible_category_names[category] = tabWidget

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
                    widget.setSingleStep(1)
                    widget.setToolTip(param["title"])
                    widget.valueChanged.connect(functools.partial(self.spinner_value_changed, param))

                elif param["type"] == "text" or param["type"] == "browse":
                    # create QLineEdit
                    widget = QLineEdit()
                    widget.setText(_(param["value"]))
                    widget.textChanged.connect(functools.partial(self.text_value_changed, widget, param))

                    if param["type"] == "browse":
                        # Add filesystem browser button
                        extraWidget = QPushButton(_("Browse..."))
                        extraWidget.clicked.connect(functools.partial(self.selectExecutable, widget, param))

                elif param["type"] == "bool":
                    # create spinner
                    widget = QCheckBox()
                    if param["value"] is True:
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
                                value_list.append({
                                    "name": profile.info.description,
                                    "value": profile.info.description
                                    })
                        # Sort profile list
                        value_list.sort(key=operator.itemgetter("name"))

                    # Overwrite value list (for audio device list dropdown)
                    if param["setting"] == "playback-audio-device":
                        value_list = []
                        # Loop through audio devices
                        value_list.append({"name": "Default", "value": ""})
                        for audio_device in get_app().window.preview_thread.player.GetAudioDeviceNames():
                            value_list.append({
                                "name": "%s: %s" % (
                                    audio_device.type, audio_device.name),
                                "value": audio_device.name,
                                })

                    # Overwrite value list (for language dropdown)
                    if param["setting"] == "default-language":
                        value_list = []
                        # Loop through languages
                        for locale, language, country in get_all_languages():
                            # Load Profile and append description
                            if language:
                                lang_name = "%s (%s)" % (language, locale)
                                value_list.append({
                                    "name": lang_name,
                                    "value": locale
                                    })
                        # Sort profile list
                        value_list.sort(key=operator.itemgetter("name"))
                        # Add Default to top of list
                        value_list.insert(0, {
                            "name": _("Default"),
                            "value": "Default"
                            })

                    # Overwrite value list (for hardware acceleration modes)
                    os_platform = platform.system()
                    if param["setting"] == "hw-decoder":
                        for value_item in list(value_list):
                            v = value_item["value"]
                            # Remove items that are operating system specific
                            if os_platform == "Darwin" and v not in ("0", "5", "2"):
                                value_list.remove(value_item)
                            elif os_platform == "Windows" and v not in ("0", "3", "4"):
                                value_list.remove(value_item)
                            elif os_platform == "Linux" and v not in ("0", "1", "2", "6"):
                                value_list.remove(value_item)

                        # Remove hardware mode items which cannot decode the example video
                        log.debug("Preparing to test hardware decoding: %s", value_list)
                        for value_item in list(value_list):
                            v = value_item["value"]
                            if (not self.testHardwareDecode(value_list, v, 0)
                               and not self.testHardwareDecode(value_list, v, 1)):
                                value_list.remove(value_item)
                        log.debug("Completed hardware decoding testing")

                    # Replace %s dropdown values for hardware acceleration
                    if param["setting"] in ("graca_number_en", "graca_number_de"):
                        for card_index in range(0, 3):
                            # Test each graphics card, and only include valid ones
                            if card_index in self.hardware_tests_cards and self.hardware_tests_cards.get(card_index):
                                # Loop through valid modes supported by this card
                                for mode in self.hardware_tests_cards.get(card_index):
                                    # Add supported graphics card for each mode (duplicates are okay)
                                    if mode == 0:
                                        # cpu only
                                        value_list.append({
                                            "value": card_index,
                                            "name": _("No acceleration"),
                                            "icon": mode
                                            })
                                    else:
                                        # hardware accelerated
                                        value_list.append({
                                            "value": card_index,
                                            "name": _("Graphics Card %s") % (card_index + 1),
                                            "icon": mode
                                            })

                        if os_platform in ["Darwin", "Windows"]:
                            # Disable graphics card selection for Mac and Windows (since libopenshot
                            # only supports device selection on Linux)
                            widget.setEnabled(False)
                            widget.setToolTip(_("Graphics card selection not supported in %s") % os_platform)

                    # Add normal values
                    box_index = 0
                    for value_item in value_list:
                        k = value_item["name"]
                        v = value_item["value"]
                        i = value_item.get("icon", None)

                        # Override icons for certain values
                        # TODO: Find a more elegant way to do this
                        icon = None
                        if k == "Linux VA-API" or i == 1:
                            icon = QIcon(":/hw/hw-accel-vaapi.svg")
                        elif k == "Nvidia NVDEC" or i == 2:
                            icon = QIcon(":/hw/hw-accel-nvdec.svg")
                        elif k == "Linux VDPAU" or i == 6:
                            icon = QIcon(":/hw/hw-accel-vdpau.svg")
                        elif k == "Windows D3D9" or i == 3:
                            icon = QIcon(":/hw/hw-accel-dx.svg")
                        elif k == "Windows D3D11" or i == 4:
                            icon = QIcon(":/hw/hw-accel-dx.svg")
                        elif k == "MacOS" or i == 5:
                            icon = QIcon(":/hw/hw-accel-vtb.svg")
                        elif k == "Intel QSV" or i == 7:
                            icon = QIcon(":/hw/hw-accel-qsv.svg")
                        elif k == "No acceleration" or i == 0:
                            icon = QIcon(":/hw/hw-accel-none.svg")

                        # add dropdown item
                        if icon:
                            widget.setIconSize(QSize(60, 18))
                            widget.addItem(icon, _(k), v)
                        else:
                            widget.addItem(_(k), v)

                        # select dropdown (if default)
                        if v == param["value"]:
                            widget.setCurrentIndex(box_index)
                        box_index = box_index + 1

                    widget.currentIndexChanged.connect(functools.partial(self.dropdown_index_changed, widget, param))

                # Add Label and Widget to the form
                if (widget and label and filterFound):
                    # Add minimum size
                    label.setMinimumWidth(180)
                    label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
                    widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

                    # Create HBox layout
                    layout_hbox = QHBoxLayout()
                    layout_hbox.addWidget(label)
                    layout_hbox.addWidget(widget)

                    if (extraWidget):
                        layout_hbox.addWidget(extraWidget)

                    # Add widget to layout
                    tabWidget.layout().addLayout(layout_hbox)
                elif (label and filterFound):
                    # Add widget to layout
                    tabWidget.layout().addWidget(label)

            # Add stretch to bottom of layout
            tabWidget.layout().addStretch()

        # Delete all tabs and widgets
        self.DeleteAllTabs(onlyInVisible=True)

    def selectExecutable(self, widget, param):
        _ = get_app()._tr

        # Fallback default to user home
        startpath = QDir.rootPath()

        # Start at directory of old setting, if it exists, or walk up the
        # path until we encounter a directory that does exist and start there
        if "setting" in param and param["setting"]:
            prev_val = self.s.get(param["setting"])
            while prev_val and not os.path.exists(prev_val):
                prev_val = os.path.dirname(prev_val)
            if prev_val and os.path.exists(prev_val):
                startpath = prev_val

        fileName = QFileDialog.getOpenFileName(
            self,
            _("Select executable file"),
            startpath)[0]
        if fileName:
            if platform.system() == "Darwin":
                # Check for Mac specific app-bundle executable file (if any)
                appBundlePath = os.path.join(fileName, 'Contents', 'MacOS')
                if os.path.exists(os.path.join(appBundlePath, 'blender')):
                    fileName = os.path.join(appBundlePath, 'blender')
                elif os.path.exists(os.path.join(appBundlePath, 'Blender')):
                    fileName = os.path.join(appBundlePath, 'Blender')
                elif os.path.exists(os.path.join(appBundlePath, 'Inkscape')):
                    fileName = os.path.join(appBundlePath, 'Inkscape')

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
            log.info("Setting debug-mode to %s", state == Qt.Checked)
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

        # Check for restart
        self.check_for_restart(param)

    def spinner_value_changed(self, param, value):
        # Save setting
        self.s.set(param["setting"], value)
        log.info(value)

        if param["setting"] == "autosave-interval":
            # Update autosave interval (# of minutes)
            get_app().window.auto_save_timer.setInterval(int(value * 1000 * 60))

        elif param["setting"] == "omp_threads_number":
            openshot.Settings.Instance().OMP_THREADS = max(2, int(str(value)))

        elif param["setting"] == "ff_threads_number":
            openshot.Settings.Instance().FF_THREADS = int(str(value))

        elif param["setting"] == "decode_hw_max_width":
            openshot.Settings.Instance().DE_LIMIT_WIDTH_MAX = int(str(value))

        elif param["setting"] == "decode_hw_max_height":
            openshot.Settings.Instance().DE_LIMIT_HEIGHT_MAX = int(str(value))

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
        except Exception:
            log.debug('Failed to get plain text from widget')

        # If this setting is a keyboard mapping, parse it first
        if param.get("category") == "Keyboard":
            previous_value = value
            value = QKeySequence(value).toString()
            log.info(
                "Parsing keyboard mapping via QKeySequence from %s to %s",
                previous_value, value)

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

        if param["setting"] == "hw-decoder":
            # Set Hardware Decoder
            openshot.Settings.Instance().HARDWARE_DECODER = int(value)

        if param["setting"] == "graca_number_de":
            openshot.Settings.Instance().HW_DE_DEVICE_SET = int(value)

        if param["setting"] == "graca_number_en":
            openshot.Settings.Instance().HW_EN_DEVICE_SET = int(value)

        # Check for restart
        self.check_for_restart(param)

    def testHardwareDecode(self, all_decoders, decoder, decoder_card="0"):
        """Test specific settings for hardware decode, so the UI can remove unsupported options."""
        is_supported = False
        example_media = os.path.join(info.RESOURCES_PATH, "hardware-example.mp4")
        decoder_name = next(item for item in all_decoders if item["value"] == str(decoder)).get("name", "Unknown")

        # Persist decoder card results
        if decoder_card not in self.hardware_tests_cards:
            # Init new decoder card list
            self.hardware_tests_cards[decoder_card] = []
        if int(decoder) in self.hardware_tests_cards.get(decoder_card):
            # Test already run and succeeded
            return True

        # Keep track of previous settings
        current_decoder = openshot.Settings.Instance().HARDWARE_DECODER
        current_decoder_card = openshot.Settings.Instance().HW_DE_DEVICE_SET
        current_decoder_name = next(
            item for item in all_decoders
            if item["value"] == str(current_decoder)
            ).get("name", "Unknown")
        log.debug(
            "Current hardware decoder: %s (%s-%s)",
            current_decoder_name, current_decoder, current_decoder_card)

        try:
            # Temp override hardware settings (to test them)
            log.debug(
                "Testing hardware decoder: %s (%s-%s)",
                decoder_name, decoder, decoder_card)
            openshot.Settings.Instance().HARDWARE_DECODER = int(decoder)
            openshot.Settings.Instance().HW_DE_DEVICE_SET = int(decoder_card)

            # Find reader
            clip = openshot.Clip(example_media)
            reader = clip.Reader()

            # Open reader
            reader.Open()

            # Test decoded pixel values for a valid decode (based on hardware-example.mp4)
            if reader.GetFrame(0).CheckPixel(0, 0, 2, 133, 255, 255, 5):
                is_supported = True
                self.hardware_tests_cards[decoder_card].append(int(decoder))
                log.debug(
                    "Successful hardware decoder! %s (%s-%s)",
                    decoder_name, decoder, decoder_card)
            else:
                log.debug(
                    "CheckPixel failed testing hardware decoding (i.e. wrong color found): %s (%s-%s)",
                    decoder_name, decoder, decoder_card)

            reader.Close()
            clip.Close()

        except Exception:
            log.debug(
                "Exception trying to test hardware decoding (this is expected): %s (%s-%s)",
                decoder_name, decoder, decoder_card)

        # Resume current settings
        openshot.Settings.Instance().HARDWARE_DECODER = current_decoder
        openshot.Settings.Instance().HW_DE_DEVICE_SET = current_decoder_card

        return is_supported

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
