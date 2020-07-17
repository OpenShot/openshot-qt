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
from PyQt5.QtGui import QIcon, QStandardItemModel, QStandardItem, QPixmap
from PyQt5.QtWidgets import *
from PyQt5 import uic
import openshot  # Python module for libopenshot (required video editing module installed separately)

from classes import info, ui_util, settings, qt_types, updates
from classes.app import get_app
from classes.logger import log
from classes.metrics import *

class BbWindow(QDialog):
    def __init__(self, frame):
        super().__init__()
        self.setWindowModality(Qt.ApplicationModal)
        self.title = "Bounding Box Selector"
        self.top = 200
        self.left = 500
        self.width = 300
        self.height = 200
        self.windowIconName = os.path.join(info.PATH, 'xdg', 'openshot-arrow.png')
        self.rubberBand = QRubberBand(QRubberBand.Rectangle, self)
        self.InitWindow(frame)
        self.origin = QPoint()

    def InitWindow(self,frame):
        self.setWindowIcon(QIcon(self.windowIconName))
        self.setWindowTitle(self.title)
        self.setGeometry(self.left, self.top, self.width, self.height)
        vbox = QVBoxLayout()
        labelImage = QLabel(self)
        pixmap = QPixmap(frame)
        labelImage.setPixmap(pixmap)
        vbox.addWidget(labelImage)
        self.setLayout(vbox)
        self.show()

    def closeEvent(self, event):
        event.accept()

    # Set top left rectangle coordinate
    def mousePressEvent(self, event):
    
        if event.button() == Qt.LeftButton:
            self.origin = QPoint(event.pos())
            self.rubberBand.setGeometry(QRect(self.origin, QSize()))
            self.rubberBand.show()
    
    # Change rectangle selection while the mouse moves
    def mouseMoveEvent(self, event):

        if not self.origin.isNull():
            self.end = event.pos()
            self.rubberBand.setGeometry(QRect(self.origin, self.end).normalized())

    # Return bounding box selection coordinates
    def getBB(self):
        return self.origin.x(), self.origin.y(), self.end.x() - self.origin.x(), self.end.y() - self.origin.y()

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

        # flag to close the clip processing thread
        self.cancel_clip_processing = False
        self.effect = None

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
                self.clip_instance = clip_instance
                break

        # Create effect Id and protobuf data path
        ID = get_app().project.generate_id()

        protobufFolderPath = os.path.join(info.PATH, '..', 'protobuf_data')
        # Check if protobuf data folder exists, otherwise it will create one
        if not os.path.exists(protobufFolderPath):
            os.mkdir(protobufFolderPath)

        # Create protobuf data path
        protobufPath = os.path.join(protobufFolderPath, ID + '.data')

        # Load into JSON string info abou protobuf data path
        jsonString = self.generateJson(protobufPath)

        # Generate processed data
        processing = openshot.ClipProcessingJobs(self.effect_name, jsonString)
        processing.processClip(self.clip_instance)

        # get processing status
        while(not processing.IsDone() ):
            # update progressbar
            progressionStatus = processing.GetProgress()
            self.progressBar.setValue(progressionStatus)
            time.sleep(0.01)

            # Process any queued events
            QCoreApplication.processEvents()

            # if the cancel button was pressed, close the processing thread
            if(self.cancel_clip_processing):
                processing.CancelProcessing()

        if(not self.cancel_clip_processing):
        
            # Load processed data into effect
            self.effect = openshot.EffectInfo().CreateEffect(self.effect_name)
            self.effect.SetJson( '{"protobuf_data_path": "%s"}' % protobufPath )
            self.effect.Id(ID)
            
            print("Applied effect: %s to clip: %s" % (self.effect_name, self.clip_instance.Id()))

        # Accept dialog
        super(ProcessEffect, self).accept()

    def reject(self):
        # Cancel dialog
        self.exporting = False
        self.cancel_clip_processing = True
        super(ProcessEffect, self).reject()

    def generateJson(self, protobufPath):
        # Start JSON string with the protobuf data path, necessary for all pre-processing effects
        jsonString = '{"protobuf_data_path": "%s"' % protobufPath

        if self.effect_name == "Stabilizer":
            pass

        # Special case where more info is needed for the JSON string
        if self.effect_name == "Tracker":

            # Create temporary imagem to be shown in PyQt Window
            temp_img_path = protobufPath.split(".data")[0] + '.png'
            self.clip_instance.GetFrame(0).Save(temp_img_path, 1)

            # Show bounding box selection window
            bbWindow = BbWindow(temp_img_path)
            bbWindow.exec_()

            # Remove temporary image
            os.remove(temp_img_path)

            # Get bounding box selection coordinates
            bb = bbWindow.getBB()

            # Set tracker info in JSON string
            trackerType = "KCF"
            jsonString += ',"tracker_type": "%s"'%trackerType
            jsonString += ',"bbox": {"x": %d, "y": %d, "w": %d, "h": %d}'%(bb[0],bb[1],bb[2],bb[3])
        
        # Finish JSON string
        jsonString+='}'
        return jsonString
