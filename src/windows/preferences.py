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
    QDoubleSpinBox, QComboBox, QCheckBox, QSpinBox, QStyle,
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

        # Define the custom category order
        self.custom_order = ["General", "Preview", "Autosave", "Cache", "Debug", "Keyboard", "Performance", "Location", "AI", "Experimental"]

        # Get settings
        self.s = get_app().get_settings()

        # Dynamically load tabs from settings data
        self.settings_data = self.s.get_all_settings()

        # Track metrics
        track_metric_screen("preferences-screen")

        # Disable video caching
        openshot.Settings.Instance().ENABLE_PLAYBACK_CACHING = False

        # Load all user values
        self.params = {}
        for item in self.settings_data:
            if "setting" in item and "value" in item:
                self.params[item["setting"]] = item

        # Track widgets and dependencies between settings
        self.setting_widgets = {}
        self.dependency_map = {}

        # Connect signals
        self.txtSearch.textChanged.connect(self.txtSearch_changed)
        self.btnRestoreDefaults.clicked.connect(self.confirm_restore_defaults)
        self.tabCategories.currentChanged.connect(self.category_tab_changed)

        self.requires_restart = False
        self.category_names = {}
        self.category_tabs = {}
        self.category_sort = {}
        self.visible_category_names = {}

        # Tested hardware modes (default cpu mode with graphics card 0)
        self.hardware_tests_cards = {0: [0, ]}

        # Populate preferences
        self.Populate()

        # Highlight invalid keyboard shortcuts
        self.check_shortcut_validity()

        # Restore normal cursor
        get_app().restoreOverrideCursor()

    def category_tab_changed(self, index):
        """Update the Restore Defaults button label based on the selected tab."""
        # Get the current widget for the selected tab
        current_widget = self.tabCategories.widget(index)
        if not current_widget:
            return

        # Retrieve the non-translated category using the object name
        non_translated_category = current_widget.objectName()

        # Update the Restore Defaults button label
        if non_translated_category:
            self.btnRestoreDefaults.setText(f"Restore Defaults: {non_translated_category}")

    def txtSearch_changed(self):
        """textChanged event handler for search box"""
        log.info("Search for %s", self.txtSearch.text())

        # Populate preferences
        self.Populate(filter=self.txtSearch.text())

    def DeleteAllTabs(self, onlyInVisible=False):
        """Delete all tabs and ensure they are fully removed from memory."""
        for name, widget in dict(self.category_tabs).items():
            # Check visibility condition
            if (onlyInVisible and name not in self.visible_category_names) or not onlyInVisible:
                # Remove hidden widgets
                parent_widget = widget.parent().parent()
                parent_widget.setParent(None)
                parent_widget.deleteLater()

                # Clean up the references in the internal tracking dictionaries
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
        self.visible_category_names = {}

        # Reset widget/dependency trackers each time preferences are rebuilt
        self.setting_widgets = {}
        self.dependency_map = {}

        # Loop through settings and collect categories
        for item in self.settings_data:
            category = item.get("category")
            setting_type = item.get("type")
            sort_type = item.get("sort")

            if setting_type != "hidden":
                # Load setting
                if category not in self.category_names:
                    self.category_names[category] = []
                if sort_type:
                    self.category_sort[category] = sort_type

                # Append settings into correct category
                self.category_names[category].append(item)

        # Create tabs in the predefined order (only add categories present in settings_data)
        for category in self.custom_order:
            if category in self.category_names:
                # Create scroll area
                scroll_area = QScrollArea(self)
                scroll_area.setWidgetResizable(True)
                scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
                scroll_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                scroll_area.setMinimumSize(675, 100)

                # Create tab widget and layout
                layout = QVBoxLayout()
                tabWidget = QWidget(self)
                tabWidget.setObjectName("PreferencePanel")
                tabWidget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
                tabWidget.setLayout(layout)
                scroll_area.setWidget(tabWidget)
                scroll_area.setObjectName(category)

                # Add tab in the predefined order
                self.tabCategories.addTab(scroll_area, _(category))
                self.category_tabs[category] = tabWidget

        # Now populate each tab with settings
        for category in self.custom_order:
            tabWidget = self.category_tabs[category]
            filterFound = False

            # Get list of items in category
            params = self.category_names[category]
            if self.category_sort.get(category):
                # Sort this category by translated title
                params.sort(key=lambda setting: _(setting.get("title")))

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
                    widget.setSingleStep(param.get("step", 1.0))
                    widget.setToolTip(param["title"])
                    widget.valueChanged.connect(functools.partial(self.spinner_value_changed, param))

                if param["type"] == "spinner-int":
                    # create QDoubleSpinBox
                    widget = QSpinBox()
                    widget.setMinimum(int(param["min"]))
                    widget.setMaximum(int(param["max"]))
                    widget.setValue(int(param["value"]))
                    widget.setSingleStep(param.get("step", 1))
                    widget.setToolTip(param["title"])
                    widget.valueChanged.connect(functools.partial(self.spinner_value_changed, param))

                elif param["type"] == "text" or param["type"] == "browse":
                    # create QLineEdit
                    widget = QLineEdit()
                    widget.setText(_(param["value"]))
                    widget.setObjectName(param["setting"])
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
                    widget.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)

                    # Get values
                    value_list = param["values"]
                    # Overwrite value list (for profile dropdown)
                    if param["setting"] == "default-profile":
                        value_list = []
                        # Loop through profiles
                        for profile_folder in [info.USER_PROFILES_PATH, info.PROFILES_PATH]:
                            for file in reversed(sorted(os.listdir(profile_folder))):
                                # Load Profile and append description
                                profile_path = os.path.join(profile_folder, file)
                                if os.path.isdir(profile_path):
                                    continue
                                profile = openshot.Profile(profile_path)
                                profile_lbl = f"{profile.info.description} ({profile.info.width}x{profile.info.height})"
                                value_list.append({
                                    "name": profile_lbl,
                                    "value": profile.info.description
                                    })

                        # Add test button
                        extraWidget = QPushButton()
                        extraWidget.setToolTip(_("Search Profiles"))
                        extraWidget.setIcon(QIcon(":/icons/Humanity/mimes/16/video-x-generic.svg"))
                        extraWidget.clicked.connect(functools.partial(self.btnBrowseProfiles_clicked, widget))

                    # Overwrite value list (for audio device list dropdown)
                    if param["setting"] == "playback-audio-device":
                        value_list = []
                        # Loop through audio devices
                        value_list.append({"name": "Default", "value": ""})
                        for audio_device in get_app().window.preview_thread.player.GetAudioDeviceNames():
                            # Text:  Type first, then device name  (i.e. "ALSA: PulseAudio Sound Server")
                            # Value: Name first, ||, then device type  (i.e. "PulseAudio Sound Server||ALSA")
                            value_list.append({
                                "name": "%s: %s" % (audio_device[1], audio_device[0]),
                                "value": "%s||%s" % (audio_device[0], audio_device[1])
                            })

                    # Overwrite value list (for theme names)
                    if param["setting"] == "theme":
                        from themes.manager import ThemeName
                        value_list = []
                        for theme_name in ThemeName.get_sorted_theme_names():
                            value_list.append({
                                "name": _(theme_name), "value": theme_name
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

                            # Add test button
                            extraWidget = QPushButton(_("Test"))
                            extraWidget.clicked.connect(functools.partial(self.testHardwareDecode, widget,
                                                                          param, extraWidget))

                    # Replace %s dropdown values for hardware acceleration
                    if param["setting"] in ("graca_number_en", "graca_number_de"):
                        value_list = []
                        for card_index in range(0, 3):
                            # hardware accelerated
                            value_list.append({
                                "value": card_index,
                                "name": _("Graphics Card %s") % card_index
                            })

                    # Add normal values
                    box_index = 0
                    for value_item in value_list:
                        k = value_item.get("name")
                        v = value_item.get("value")
                        i = value_item.get("icon", None)

                        # Translate dropdown item (if needed)
                        if param.get("translate_values"):
                            k = _(value_item["name"])

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
                    self.register_setting_widget(param, widget, label)
                elif (label and filterFound):
                    # Add widget to layout
                    tabWidget.layout().addWidget(label)

            # Add stretch to bottom of layout
            tabWidget.layout().addStretch()

        self.apply_all_dependencies()

        # Delete all tabs and widgets
        self.DeleteAllTabs(onlyInVisible=True)

    def register_setting_widget(self, param, widget, label=None):
        """Store widget references and register dependency relationships."""
        setting_name = param.get("setting")
        if not setting_name or not widget:
            return

        self.setting_widgets[setting_name] = widget
        widget.setObjectName(setting_name)

        dependency = param.get("dependency")
        if dependency:
            self.dependency_map.setdefault(dependency, []).append((widget, label))

    def apply_all_dependencies(self):
        """Apply dependency state to all registered widgets."""
        for setting_name in list(self.dependency_map.keys()):
            self.apply_dependency_state(setting_name)

    def apply_dependency_state(self, setting_name):
        """Enable/disable dependent widgets based on controller state."""
        controlled_widgets = self.dependency_map.get(setting_name, [])
        if not controlled_widgets:
            return

        enabled = bool(self.s.get(setting_name))
        for widget, label in controlled_widgets:
            if widget:
                widget.setEnabled(enabled)
            if label:
                label.setEnabled(enabled)

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

    def _apply_timeline_thumbnail_style(self):
        """Push the current thumbnail preference to the QWidget timeline."""
        timeline_widget = getattr(get_app().window, "timeline", None)
        if not hasattr(timeline_widget, "set_thumbnail_style"):
            return
        try:
            timeline_widget.set_thumbnail_style(self.s.get("timeline-thumbnail-style"))
        except Exception:
            log.warning("Failed to apply timeline thumbnail style live", exc_info=1)

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

        # Update any dependent widgets
        if param.get("setting"):
            self.apply_dependency_state(param["setting"])

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
        if param["setting"] in ["cache-limit-mb", "cache-scale", "cache-quality",
                                "cache-ahead-percent", "cache-preroll-min-frames",
                                "cache-preroll-max-frames", "cache-max-frames"]:
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

            # Split the input value by the '|' delimiter
            key_sequences = value.split('|')

            # Parse each sequence part and re-join them with ' | ' after parsing
            parsed_sequences = [QKeySequence(seq).toString() for seq in key_sequences]

            # Join the parsed sequences back with ' | '
            value = ' | '.join(parsed_sequences)
            log.info("Parsing keyboard mapping via QKeySequence from %s to %s", previous_value, value)

        # Save setting
        self.s.set(param["setting"], value)
        log.info(value)

        # Reload shortcuts (if needed)
        if param.get("category") == "Keyboard":
            get_app().window.initShortcuts()

            # Check for duplicates and update UI feedback
            self.check_shortcut_validity()

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

        if param["setting"] == "theme":
            # Apply selected theme to UI
            if get_app().theme_manager:
                get_app().theme_manager.apply_theme(value)

        if param["setting"] == "timeline-thumbnail-style":
            self._apply_timeline_thumbnail_style()

        # Check for restart
        self.check_for_restart(param)

    def btnBrowseProfiles_clicked(self, widget):
        """Search profile button clicked"""
        # Get current selection profile object
        profile_description = widget.currentData()

        # Find matching profile path
        matching_profile_path = None
        for profile_folder in [info.USER_PROFILES_PATH, info.PROFILES_PATH]:
            for file in reversed(sorted(os.listdir(profile_folder))):
                # Load Profile and append description
                matching_profile_path = os.path.join(profile_folder, file)
                if os.path.isdir(matching_profile_path):
                    continue
                profile = openshot.Profile(matching_profile_path)
                if profile.info.description == profile_description:
                    break

        # Load matching profile
        current_profile = openshot.Profile(matching_profile_path)

        # Show dialog (init to current selection)
        from windows.profile import Profile
        log.debug("Showing profile dialog")
        win = Profile(current_profile.Key())
        # Run the dialog event loop - blocking interaction on this window during this time
        result = win.exec_()

        profile = win.selected_profile
        if result == QDialog.Accepted and profile:

            # select the project's current profile
            profile_index = self.getVideoProfileIndex(widget, profile)
            if profile_index != -1:
                # Re-select project profile (if found in list)
                widget.setCurrentIndex(profile_index)
            else:
                # Previous profile not in list, so
                # default to first profile in list
                widget.setCurrentIndex(0)

    def getVideoProfileIndex(self, widget, profile):
        """Get the index of a profile name or profile key (-1 if not found)"""
        for index in range(widget.count()):
            combo_profile_description = widget.itemData(index)
            if profile.info.description == combo_profile_description:
                return index
        return -1

    def testHardwareDecode(self, widget, param, btn):
        """Test specific settings for hardware decode"""
        all_decoders = param.get("values", [])
        is_supported = False

        # Keep track of previous settings
        current_decoder = openshot.Settings.Instance().HARDWARE_DECODER
        current_decoder_card = openshot.Settings.Instance().HW_DE_DEVICE_SET
        current_decoder_name = next(item for item in all_decoders
                                    if item["value"] == str(current_decoder)).get("name", "Unknown")
        log.debug("Testing hardware decoder: %s (Decoder Type: %s, Graphics Card: %s)",
            current_decoder_name, current_decoder, current_decoder_card)

        try:
            # Find reader
            example_media = os.path.join(info.RESOURCES_PATH, "hardware-example.mp4")
            clip = openshot.Clip(example_media)
            reader = clip.Reader()

            # Open reader
            reader.Open()

            # Test decoded pixel values for a valid decode (based on hardware-example.mp4)
            if reader.GetFrame(0).CheckPixel(0, 0, 2, 133, 255, 255, 5):
                is_supported = True
                log.debug("Successful test of hardware decoder: %s (Decoder Type: %s, Graphics Card: %s)",
                          current_decoder_name, current_decoder, current_decoder_card)
            else:
                log.debug("Failed test of hardware decoder (incorrect pixel color found): "
                          "%s (Decoder Type: %s, Graphics Card: %s)",
                          current_decoder_name, current_decoder, current_decoder_card)

            reader.Close()
            clip.Close()

        except Exception as ex:
            log.debug("Exception testing hardware decoder: %s (Decoder Type: %s, Graphics Card: %s) %s",
                      current_decoder_name, current_decoder, current_decoder_card, str(ex))

        # Show icon on test button (checkmark vs X)
        icon_name = "SP_DialogApplyButton"
        if not is_supported:
            icon_name = "SP_DialogCancelButton"
        pixmapi = getattr(QStyle, icon_name)
        icon = self.style().standardIcon(pixmapi)
        btn.setIcon(icon)

        return is_supported

    def confirm_restore_defaults(self):
        """Prompt the user for confirmation before restoring defaults for the current tab."""
        # Get the current tab index and widget
        current_index = self.tabCategories.currentIndex()
        current_widget = self.tabCategories.widget(current_index)

        # Retrieve the non-translated category using the object name
        category = current_widget.objectName()

        # Prompt the user for confirmation using named placeholders in the translation
        _ = get_app()._tr
        reply = QMessageBox.question(
            self,
            _('Restore Defaults').format(category=category),
            _('Restore default values for {category}?').format(category=category),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        # If the user confirms, restore the settings for the current category
        if reply == QMessageBox.Yes:
            # Restore category settings
            self.requires_restart = self.s.restore(category_filter=category)
            self.settings_data = self.s.get_all_settings()

            # Re-apply thumbnail style to the QWidget timeline if it changed
            self._apply_timeline_thumbnail_style()

            # Repopulate preferences
            self.Populate()
            self.tabCategories.setCurrentIndex(current_index)

            # Update shortcuts on main window
            get_app().window.initShortcuts()

            # Highlight invalid keyboard shortcuts
            self.check_shortcut_validity()

    def check_shortcut_validity(self):
        """Check all keyboard settings for duplicate or invalid shortcuts and update the UI."""

        # Set to track all key sequences and prevent duplication
        used_shortcuts = {}

        # Iterate over all keyboard shortcuts from the application settings
        for shortcut in get_app().window.getAllKeyboardShortcuts():
            method_name = shortcut.get('setting')

            # Get list of key sequences (divided by | delimiter)
            shortcut_sequences = get_app().window.getShortcutByName(method_name)

            # Create QKeySequence list for each sequence
            key_sequences = [QKeySequence(seq).toString() for seq in shortcut_sequences if seq]

            for key_sequence in key_sequences:
                if key_sequence in used_shortcuts:
                    # Mark both current and new shortcut as duplicates
                    used_shortcuts[key_sequence]['is_duplicate'] = True
                    used_shortcuts[key_sequence]['params'].append(method_name)
                else:
                    used_shortcuts[key_sequence] = {'is_duplicate': False, 'params': [method_name]}

        # Update the UI based on shortcut validation
        self.update_shortcut_visual_feedback(used_shortcuts)

    def update_shortcut_visual_feedback(self, shortcut_map):
        """Update the UI to provide feedback for duplicated/invalid shortcuts."""

        for key_sequence, info in shortcut_map.items():
            for param_name in info['params']:
                # Find the QLineEdit using the objectName (which is set to the param name)
                widget = self.findChild(QLineEdit, param_name)

                if widget:
                    if info['is_duplicate']:
                        # Mark the field with red text and border for duplicates
                        widget.setStyleSheet("color: red;")

    def closeEvent(self, event):
        """Signal for closing Preferences window"""
        # Invoke the close button
        self.reject()

    def reject(self):
        # Save all settings to disk
        self.s.save()
        
        # Enable video caching
        openshot.Settings.Instance().ENABLE_PLAYBACK_CACHING = True

        # Prompt user to restart Flowcut (if needed)
        if self.requires_restart:
            msg = QMessageBox()
            _ = get_app()._tr
            msg.setWindowTitle(_("Restart Required"))
            msg.setText(_("Please restart Flowcut for all preferences to take effect."))
            msg.exec_()

        # Close dialog
        super(Preferences, self).reject()
