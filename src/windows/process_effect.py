"""
 @file
 @brief This file loads the Initialize Effects / Pre-process effects dialog
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
import time
import json
import functools
import webbrowser

from PyQt5.QtCore import Qt, pyqtSignal, QCoreApplication
from PyQt5.QtGui import QPainter
from PyQt5.QtWidgets import QPushButton, QDialog, QLabel, QDoubleSpinBox, QSpinBox, QLineEdit, QCheckBox, QComboBox, QDialogButtonBox, QSizePolicy
import openshot  # Python module for libopenshot (required video editing module installed separately)

from classes import info
from classes import ui_util
from classes.app import get_app
from classes.logger import log
from classes.metrics import *


class RegionButton(QPushButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.qimage = None

    def setImage(self, qimage):
        self.qimage = qimage
        self.update()  # Trigger a repaint

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.qimage:
            painter = QPainter(self)
            resized_qimage = self.qimage.scaled(self.size(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            painter.drawImage(0, 0, resized_qimage)
        else:
            super().paintEvent(event)  # Draw the normal button


class ProcessEffect(QDialog):
    """ Choose Profile Dialog """
    progress = pyqtSignal(int)

    # Path to ui file
    ui_path = os.path.join(info.PATH, 'windows', 'ui', 'process-effect.ui')

    def __init__(self, clip_id, effect_class, effect_params):

        if not openshot.Clip().COMPILED_WITH_CV:
            raise ModuleNotFoundError("Openshot not compiled with OpenCV")

        # Create dialog class
        QDialog.__init__(self)
        # Track effect details
        self.clip_id = clip_id
        self.effect_name = ""
        self.effect_class = effect_class
        self.context = {}

        # Get all effect JSON data, and find effect's display name (based on the class name)
        raw_effects_list = json.loads(openshot.EffectInfo.Json())
        for raw_effect in raw_effects_list:
            if raw_effect.get("class_name") == self.effect_class:
                self.effect_name = raw_effect.get("name")
                break

        # Access C++ timeline and find the Clip instance which this effect should be applied to
        timeline_instance = get_app().window.timeline_sync.timeline
        for clip_instance in timeline_instance.Clips():
            if clip_instance.Id() == self.clip_id:
                self.clip_instance = clip_instance
                break

        # Load UI from designer & init
        ui_util.load_ui(self, self.ui_path)
        ui_util.init_ui(self)

        # get translations
        _ = get_app()._tr

        # Update window title
        self.setWindowTitle(self.windowTitle() % _(self.effect_name))

        # Pause playback
        get_app().window.PauseSignal.emit()

        # Track metrics
        track_metric_screen("process-effect-screen")

        # Loop through options and create widgets
        row_count = 0
        for param in effect_params:

            # Create Label
            widget = None
            label = QLabel()
            label.setText(_(param["title"]))
            label.setToolTip(_(param["title"]))

            if param["type"] == "link":
                # create a clickable link
                label.setText('<a href="%s" style="color: #FFFFFF">%s</a>' % (param["value"], _(param["title"])))
                label.setTextInteractionFlags(Qt.TextBrowserInteraction)
                label.linkActivated.connect(functools.partial(self.link_activated, widget, param))

            if param["type"] == "spinner":
                # create QDoubleSpinBox
                widget = QDoubleSpinBox()
                widget.setMinimum(float(param["min"]))
                widget.setMaximum(float(param["max"]))
                widget.setValue(float(param["value"]))
                widget.setSingleStep(1.0)
                widget.setToolTip(_(param["title"]))
                widget.valueChanged.connect(functools.partial(self.spinner_value_changed, widget, param))

                # Set initial context
                self.context[param["setting"]] = float(param["value"])

            if param["type"] == "rect":
                # create QPushButton which opens up a display of the clip, with ability to select Rectangle
                widget = RegionButton(_("Click to Select"))
                widget.setMinimumHeight(80)
                widget.setToolTip(_(param["title"]))
                widget.clicked.connect(functools.partial(self.rect_select_clicked, widget, param))

                # Set initial context
                self.context[param["setting"]] = {"button-clicked": False, "x": 0, "y": 0, "width": 0, "height": 0}

            if param["type"] == "spinner-int":
                # create QDoubleSpinBox
                widget = QSpinBox()
                widget.setMinimum(int(param["min"]))
                widget.setMaximum(int(param["max"]))
                widget.setValue(int(param["value"]))
                widget.setSingleStep(1)
                widget.setToolTip(_(param["title"]))
                widget.valueChanged.connect(functools.partial(self.spinner_value_changed, widget, param))

                # Set initial context
                self.context[param["setting"]] = int(param["value"])

            elif param["type"] == "text":
                # create QLineEdit
                widget = QLineEdit()
                widget.setText(_(param["value"]))
                widget.textChanged.connect(functools.partial(self.text_value_changed, widget, param))

                # Set initial context
                self.context[param["setting"]] = param["value"]

            elif param["type"] == "bool":
                # create spinner
                widget = QCheckBox()
                if param["value"] == True:
                    widget.setCheckState(Qt.Checked)
                    self.context[param["setting"]] = True
                else:
                    widget.setCheckState(Qt.Unchecked)
                    self.context[param["setting"]] = False
                widget.stateChanged.connect(functools.partial(self.bool_value_changed, widget, param))

            elif param["type"] == "dropdown":

                # create spinner
                widget = QComboBox()

                # Get values
                value_list = param["values"]

                # Add normal values
                box_index = 0
                for value_item in value_list:
                    k = value_item["name"]
                    v = value_item["value"]
                    i = value_item.get("icon", None)

                    # add dropdown item
                    widget.addItem(_(k), v)

                    # select dropdown (if default)
                    if v == param["value"]:
                        widget.setCurrentIndex(box_index)

                        # Set initial context
                        self.context[param["setting"]] = param["value"]
                    box_index = box_index + 1

                widget.currentIndexChanged.connect(functools.partial(self.dropdown_index_changed, widget, param))

            # Add Label and Widget to the form
            if widget and label:
                # Add minimum size
                label.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Preferred)
                widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

                # Create HBoxLayout for each field
                self.scrollAreaWidgetContents.layout().insertRow(row_count, label, widget)

            elif not widget and label:
                label.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)
                self.scrollAreaWidgetContents.layout().insertRow(row_count, label)

            row_count += 1

        # Add error field
        self.error_label = QLabel("", self)
        self.error_label.setStyleSheet("color: red;")
        self.scrollAreaWidgetContents.layout().insertRow(row_count, self.error_label)

        # Add buttons
        self.cancel_button = QPushButton(_('Cancel'))
        self.process_button = QPushButton(_('Process Effect'))
        self.buttonBox.addButton(self.process_button, QDialogButtonBox.AcceptRole)
        self.buttonBox.addButton(self.cancel_button, QDialogButtonBox.RejectRole)

        # flag to close the clip processing thread
        self.cancel_clip_processing = False
        self.effect = None

    def link_activated(self, widget, param, value):
        """Link activated"""
        webbrowser.open(value, new=1)

    def spinner_value_changed(self, widget, param, value):
        """Spinner value change callback"""
        self.context[param["setting"]] = value
        log.info(self.context)

    def bool_value_changed(self, widget, param, state):
        """Boolean value change callback"""
        if state == Qt.Checked:
            self.context[param["setting"]] = True
        else:
            self.context[param["setting"]] = False
        log.info(self.context)

    def dropdown_index_changed(self, widget, param, index):
        """Dropdown value change callback"""
        value = widget.itemData(index)
        self.context[param["setting"]] = value
        log.info(self.context)

    def text_value_changed(self, widget, param, value=None):
        """Textbox value change callback"""
        try:
            # Attempt to load value from QTextEdit (i.e. multi-line)
            if not value:
                value = widget.toPlainText()
        except:
            log.debug('Failed to get plain text from widget')

        self.context[param["setting"]] = value
        log.info(self.context)

    def rect_select_clicked(self, widget, param):
        """Rect select button clicked"""
        self.context[param["setting"]].update({"button-clicked": True})

        # show dialog
        from windows.region import SelectRegion
        from classes.query import File, Clip

        c = Clip.get(id=self.clip_id)
        reader_path = c.data.get('reader', {}).get('path','')
        f = File.get(path=reader_path)
        if f:
            win = SelectRegion(f, self.clip_instance)
            # Run the dialog event loop - blocking interaction on this window during that time
            result = win.exec_()
            if result == QDialog.Accepted:
                # self.first_frame = win.current_frame
                # Region selected (get coordinates if any)
                topLeft = win.videoPreview.regionTopLeftHandle
                bottomRight = win.videoPreview.regionBottomRightHandle
                viewPortSize = win.viewport_rect
                curr_frame_size = win.videoPreview.curr_frame_size

                x1 = topLeft.x() / curr_frame_size.width()
                y1 = topLeft.y() / curr_frame_size.height()
                x2 = bottomRight.x() / curr_frame_size.width()
                y2 = bottomRight.y() / curr_frame_size.height()

                # Get QImage of region
                if win.videoPreview.region_qimage:
                    region_qimage = win.videoPreview.region_qimage

                    # Resize QImage to match button size
                    resized_qimage = region_qimage.scaled(widget.size(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)

                    # Remove button text (so region QImage is more visible)
                    widget.setImage(resized_qimage)
                    widget.setText("")

                # If data found, add to context
                if topLeft and bottomRight:
                    self.context[param["setting"]].update({"normalized_x": x1, "normalized_y": y1,
                                                           "normalized_width": x2-x1,
                                                           "normalized_height": y2-y1,
                                                           "first-frame": win.current_frame,
                                                           })
                    log.info(self.context)

        else:
            log.error('No file found with path: %s' % reader_path)

    def accept(self):
        """ Start processing effect """
        # Enable ProgressBar
        self.progressBar.setEnabled(True)
        self.process_button.setEnabled(False)

        # Print effect settings
        log.info(self.context)

        # Create effect Id and protobuf data path
        ID = get_app().project.generate_id()

        # Create protobuf data path
        protobufPath = os.path.join(info.PROTOBUF_DATA_PATH, ID + '.data')
        if os.name == 'nt' : protobufPath = protobufPath.replace("\\", "/")

        self.context["protobuf_data_path"] = protobufPath

        # Load into JSON string info about protobuf data path
        jsonString = json.dumps(self.context)

        # Generate processed data
        processing = openshot.ClipProcessingJobs(self.effect_class, jsonString)
        processing.processClip(self.clip_instance, jsonString)

        # TODO: This is just a temporary fix. We need to find a better way to allow the user to fix the error
        # The while loop is handling the error message. If pre-processing returns an error, a message
        # will be displayed for 3 seconds and the effect will be closed.
        start = time.time()
        while processing.GetError():
            self.error_label.setText(processing.GetErrorMessage())
            self.error_label.repaint()
            if (time.time() - start) > 3:
                self.exporting = False
                processing.CancelProcessing()
                while(not processing.IsDone() ):
                    continue
                super(ProcessEffect, self).reject()

        # get processing status
        while(not processing.IsDone() ):
            # update progressbar
            progressionStatus = processing.GetProgress()
            self.progressBar.setValue(int(progressionStatus))
            time.sleep(0.01)

            # Process any queued events
            QCoreApplication.processEvents()

            # if the cancel button was pressed, close the processing thread
            if(self.cancel_clip_processing):
                processing.CancelProcessing()

        if(not self.cancel_clip_processing):
            # Load processed data into effect
            self.effect = openshot.EffectInfo().CreateEffect(self.effect_class)
            self.effect.SetJson( '{"protobuf_data_path": "%s"}' % protobufPath )
            self.effect.Id(ID)

            # Accept dialog
            super(ProcessEffect, self).accept()

    def reject(self):
        # Cancel dialog
        self.exporting = False
        self.cancel_clip_processing = True
        super(ProcessEffect, self).reject()
