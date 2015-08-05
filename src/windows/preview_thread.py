""" 
 @file
 @brief This file contains the preview thread, used for displaying previews of the timeline
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

import os
import time
import uuid
import shutil
import threading
import subprocess
import re
from _sre import MAXREPEAT
from urllib.parse import urlparse
import functools
import sip

from PyQt5.QtCore import QObject, QThread, pyqtSlot, pyqtSignal
from classes.logger import log
import openshot  # Python module for libopenshot (required video editing module installed separately)


try:
    import json
except ImportError:
    import simplejson as json


class PreviewParent(QObject):
    """ Class which communicates with the PlayerWorker Class (running on a separate thread) """

    # Signal when the frame position changes in the preview player
    def onPositionChanged(self, current_frame):
        log.info('onPositionChanged')
        self.parent.movePlayhead(current_frame)

    # Signal when the playback mode changes in the preview player (i.e PLAY, PAUSE, STOP)
    def onModeChanged(self, current_mode):
        log.info('onModeChanged')

    @pyqtSlot(object, object)
    def Init(self, parent, timeline):
        # Important vars
        self.parent = parent
        self.timeline = timeline

        # Background Worker Thread (for Blender process)
        self.background = QThread(self)
        self.worker = PlayerWorker()  # no parent!

        # Init worker variables
        self.worker.Init(parent, timeline)

        # Hook up signals to Background Worker
        self.worker.position_changed.connect(self.onPositionChanged)
        self.worker.mode_changed.connect(self.onModeChanged)
        self.background.started.connect(self.worker.Start)

        # Move Worker to new thread, and Start
        self.worker.moveToThread(self.background)
        self.background.start()


class PlayerWorker(QObject):
    """ QT Player Worker Object (to preview video on a separate thread) """

    position_changed = pyqtSignal(int)
    mode_changed = pyqtSignal(object)

    @pyqtSlot(object, object)
    def Init(self, parent, timeline):
        self.parent = parent
        self.timeline = timeline

    @pyqtSlot()
    def Start(self):
        """ This method starts the video player """
        log.info("QThread Start Method Invoked")

        # Flag to run thread
        self.is_running = True
        self.number = None
        self.videoPreview = self.parent.videoPreview
        self.player = None
        self.current_frame = None
        self.current_mode = None

        # Init new player
        self.initPlayer()

        # Connect player to timeline reader
        self.player.Reader(self.timeline)
        self.player.Play()
        self.player.Pause()

        # Main loop, waiting for frames to process
        while self.is_running:

            # Emit position changed signal (if needed)
            if self.current_frame != self.player.Position():
                self.current_frame = self.player.Position()
                self.position_changed.emit(self.current_frame)

            # Emit mode changed signal (if needed)
            if self.player.Mode() != self.current_mode:
                self.current_mode = self.player.Mode()
                self.mode_changed.emit(self.current_mode)

            # wait for a small delay
            time.sleep(0.01)

    @pyqtSlot()
    def initPlayer(self):
        log.info("initPlayer")

        # Create QtPlayer class from libopenshot
        self.player = openshot.QtPlayer()

        # Get the address of the player's renderer (a QObject that emits signals when frames are ready)
        self.renderer_address = self.player.GetRendererQObject()
        self.player.SetQWidget(int(sip.unwrapinstance(self.videoPreview)))
        self.renderer = sip.wrapinstance(self.renderer_address, QObject)
        self.videoPreview.connectSignals(self.renderer)

    @pyqtSlot()
    def kill(self):
        """ Kill this thread """
        self.is_running = False

    @pyqtSlot(int)
    def previewFrame(self, number):
        """ Preview a certain frame """

        log.info("previewFrame: %s" % number)

        # Mark frame number for processing
        self.player.Seek(number)

        log.info("self.player.Position(): %s" % self.player.Position())

    @pyqtSlot(int)
    def refreshFrame(self):
        """ Refresh a certain frame """

        log.info("refreshFrame")

        # Mark frame number for processing
        self.player.Seek(self.player.Position())

        log.info("self.player.Position(): %s" % self.player.Position())

    @pyqtSlot(str)
    def LoadFile(self, path):
        """ Load a media file into the video player """

        # Load Reader
        log.info("loadReader...")
        self.reader = openshot.Clip(path).Reader()
        self.reader.Open()
        self.player.Reader(self.reader)

        # Seek to 1st frame
        self.player.Seek(1)

    @pyqtSlot()
    def Play(self):
        """ Start playing the video player """

        # Start playback
        log.info("Play...")
        self.player.Play()

    @pyqtSlot()
    def Pause(self):
        """ Start playing the video player """

        # Start playback
        log.info("Pause...")
        self.player.Pause()
