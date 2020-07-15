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
import sys
import time

from PyQt5.QtCore import *
from PyQt5.QtGui import QIcon, QStandardItemModel, QStandardItem
from PyQt5.QtWidgets import *
from PyQt5 import uic
import openshot  # Python module for libopenshot (required video editing module installed separately)

from classes import info, ui_util, settings, qt_types, updates
from classes.app import get_app
from classes.logger import log
from classes.metrics import *


class ProcessEffect(QDialog):
    """ Choose Profile Dialog """
    progress = pyqtSignal(int)

    # Path to ui file
    ui_path = os.path.join(info.PATH, 'windows', 'ui', 'process-effect.ui')

    def __init__(self, clip_id, effect_name):

        # Create dialog class
        QDialog.__init__(self)

        # Load UI from designer & init
        ui_util.load_ui(self, self.ui_path)
        ui_util.init_ui(self)

        # get translations
        _ = get_app()._tr

        # Pause playback (to prevent crash since we are fixing to change the timeline's max size)
        get_app().window.actionPlay_trigger(None, force="pause")

        # Track metrics
        track_metric_screen("process-effect-screen")

        # Init form
        self.progressBar.setValue(0)
        self.txtAdvanced.setText("{}")
        self.setWindowTitle(_("%s: Initialize Effect") % effect_name)
        self.clip_id = clip_id
        self.effect_name = effect_name

        # Add combo entries
        self.cboOptions.addItem("Option 1", 1)
        self.cboOptions.addItem("Option 2", 2)
        self.cboOptions.addItem("Option 3", 3)

        # Add buttons
        self.cancel_button = QPushButton(_('Cancel'))
        self.process_button = QPushButton(_('Process Effect'))
        self.buttonBox.addButton(self.process_button, QDialogButtonBox.AcceptRole)
        self.buttonBox.addButton(self.cancel_button, QDialogButtonBox.RejectRole)

    def accept(self):
        """ Start processing effect """
        # Disable UI
        self.cboOptions.setEnabled(False)
        self.txtAdvanced.setEnabled(False)
        self.process_button.setEnabled(False)

        # DO WORK HERE, and periodically set progressBar value
        # Access C++ timeline and find the Clip instance which this effect should be applied to
        timeline_instance = get_app().window.timeline_sync.timeline
        for clip_instance in timeline_instance.Clips():
            if clip_instance.Id() == self.clip_id:
                self.protobufPath = openshot.ClipProcessingJobs(self.effect_name, clip_instance).stabilizeVideo(clip_instance)
                self.effect = openshot.EffectInfo().CreateEffect(self.effect_name, "/media/brenno/Data/projects/openshot/stabilization.data")
                # self.effect.SetJson('{"Stabilizer":{"protobuf_data_path": "/home/gustavostahl/LabVisao/VideoEditor/openshot-qt/stabilization.data"}}')
                # clip_instance.AddEffect(self.effect)
                # return self.effect
                print("Apply effect: %s to clip: %s" % (self.effect_name, clip_instance.Id()))
                

        # EXAMPLE progress updates
        # for value in range(1, 100, 4):
        #     self.progressBar.setValue(value)
        #     time.sleep(0.25)

        #     # Process any queued events
        #     QCoreApplication.processEvents()

        # Accept dialog
        super(ProcessEffect, self).accept()

    def reject(self):
        # Cancel dialog
        self.exporting = False
        super(ProcessEffect, self).reject()
