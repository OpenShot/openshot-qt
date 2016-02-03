""" 
 @file
 @brief This file contains the preview thread, used for displaying previews of the timeline
 @author Jonathan Thomas <jonathan@openshot.org>
 
 @section LICENSE
 
 Copyright (c) 2008-2016 OpenShot Studios, LLC
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
import sip

from PyQt5.QtCore import QObject, QThread,  QTimer,  pyqtSlot, pyqtSignal, QCoreApplication
import openshot  # Python module for libopenshot (required video editing module installed separately)

from classes.logger import log
from classes import settings

try:
    import json
except ImportError:
    import simplejson as json


class PreviewParent(QObject):
    """ Class which communicates with the PlayerWorker Class (running on a separate thread) """

    # Signal when the frame position changes in the preview player
    def onPositionChanged(self, current_frame):
        self.parent.movePlayhead(current_frame)

    # Signal when the playback mode changes in the preview player (i.e PLAY, PAUSE, STOP)
    def onModeChanged(self, current_mode):
        log.info('onModeChanged')

    @pyqtSlot(object, object)
    def Init(self, parent, timeline, video_widget):
        # Important vars
        self.parent = parent
        self.timeline = timeline

        # Background Worker Thread (for preview video process)
        self.background = QThread(self)
        self.worker = PlayerWorker()  # no parent!

        # Init worker variables
        self.worker.Init(parent, timeline, video_widget)

        # Hook up signals to Background Worker
        self.worker.position_changed.connect(self.onPositionChanged)
        self.worker.mode_changed.connect(self.onModeChanged)
        self.background.started.connect(self.worker.Start)
        self.worker.finished.connect(self.background.quit)

        # Connect preview thread to main UI signals
        self.parent.previewFrameSignal.connect(self.worker.previewFrame)
        self.parent.refreshFrameSignal.connect(self.worker.refreshFrame)
        self.parent.LoadFileSignal.connect(self.worker.LoadFile)
        self.parent.PlaySignal.connect(self.worker.Play)
        self.parent.PauseSignal.connect(self.worker.Pause)
        self.parent.SeekSignal.connect(self.worker.Seek)
        self.parent.SpeedSignal.connect(self.worker.Speed)

        # Move Worker to new thread, and Start
        self.worker.moveToThread(self.background)
        self.background.start()


class PlayerWorker(QObject):
    """ QT Player Worker Object (to preview video on a separate thread) """

    position_changed = pyqtSignal(int)
    mode_changed = pyqtSignal(object)
    finished = pyqtSignal()

    @pyqtSlot(object, object)
    def Init(self, parent, timeline, videoPreview):
        self.parent = parent
        self.timeline = timeline
        self.videoPreview = videoPreview
        self.clip_path = None
        self.clip_reader = None
        self.original_speed = 0
        self.original_position = 0
        self.previous_clip_mappers = []
        self.previous_clip_readers = []

    @pyqtSlot()
    def Start(self):
        """ This method starts the video player """
        log.info("QThread Start Method Invoked")

        # Flag to run thread
        self.is_running = True
        self.number = None
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

                if not self.clip_path:
                    # Emit position of overall timeline (don't emit this for clip previews)
                    self.position_changed.emit(self.current_frame)

                    # TODO: Remove this hack and really determine what's blocking the main thread
                    # Try and keep things responsive
                    QCoreApplication.processEvents()

            # Emit mode changed signal (if needed)
            if self.player.Mode() != self.current_mode:
                self.current_mode = self.player.Mode()
                self.mode_changed.emit(self.current_mode)

            # wait for a small delay
            time.sleep(0.01)

        self.finished.emit()
        log.info('exiting thread')

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

    def kill(self):
        """ Kill this thread """
        self.is_running = False

    def previewFrame(self, number):
        """ Preview a certain frame """

        log.info("previewFrame: %s" % number)

        # Mark frame number for processing
        self.player.Seek(number)

        log.info("self.player.Position(): %s" % self.player.Position())

    def refreshFrame(self):
        """ Refresh a certain frame """

        log.info("refreshFrame")

        # Always load back in the timeline reader
        self.LoadFile(None)

        # Mark frame number for processing
        self.player.Seek(self.player.Position())

        log.info("self.player.Position(): %s" % self.player.Position())

    def LoadFile(self, path=None):
        """ Load a media file into the video player """
        s = settings.get_settings()

        # Check to see if this path is already loaded
        # TODO: Determine why path is passed in as an empty string instead of None
        if path == self.clip_path or (not path and not self.clip_path):
            return

        # Determine the current frame of the timeline (when switching to a clip)
        seek_position = 1
        if path and not self.clip_path:
            # Track the current frame
            self.original_position = self.player.Position()

        # Stop player (very important to prevent crashing)
        self.original_speed = self.player.Speed()
        self.player.Speed(0)

        # If blank path, switch back to self.timeline reader
        if not path:
            # Return to self.timeline reader
            log.info("Set timeline reader again in player: %s" % self.timeline)
            self.player.Reader(self.timeline)

            # Set debug mode
            self.timeline.debug = s.get("debug-mode")

            # Clear clip reader reference
            self.clip_reader = None
            self.clip_path = None

            # Switch back to last timeline position
            seek_position = self.original_position
        else:
            # Get extension of media path
            ext = os.path.splitext(path)

            # Load Reader based on extension
            new_reader = None
            if ext in ['.avi', 'mov', 'mkv', 'mpg', 'mpeg', 'mp3', 'mp4', 'mts', 'ogg', 'wav', 'wmv', 'webm', 'vob']:
                try:
                    new_reader = openshot.FFmpegReader(path)
                    new_reader.Open()
                except:
                    try:
                        new_reader = openshot.QtImageReader(path)
                        new_reader.Open()
                    except:
                        log.error('Failed to load media file into video player: %s' % path)
                        return
            else:
                try:
                    new_reader = openshot.QtImageReader(path)
                    new_reader.Open()
                except:
                    try:
                        new_reader = openshot.FFmpegReader(path)
                        new_reader.Open()
                    except:
                        log.error('Failed to load media file into video player: %s' % path)
                        return



            # Wrap reader in FrameMapper (to match current settings of timeline)
            new_mapper = openshot.FrameMapper(new_reader, self.timeline.info.fps, openshot.PULLDOWN_NONE, self.timeline.info.sample_rate,
                                                    self.timeline.info.channels, self.timeline.info.channel_layout)

            # Keep track of previous clip readers (so we can Close it later)
            self.previous_clip_mappers.append(new_mapper)
            self.previous_clip_readers.append(new_reader)

            # Assign new clip_reader
            self.clip_reader = new_mapper
            self.clip_reader.debug = s.get("debug-mode")
            self.clip_path = path

            # Open reader
            self.clip_reader.Open()

            log.info("Set new FrameMapper reader in player: %s" % self.clip_reader)
            self.player.Reader(self.clip_reader)

        # Close and destroy old clip readers (leaving the 3 most recent)
        while len(self.previous_clip_readers) > 3:
            log.info('Removing old clip reader: %s' % self.previous_clip_readers[0])
            self.previous_clip_mappers.pop(0)
            self.previous_clip_readers.pop(0)

        # Seek to frame 1, and resume speed
        self.player.Seek(seek_position)
        self.player.Speed(self.original_speed)

    def Play(self):
        """ Start playing the video player """

        # Start playback
        self.player.Play()

    def Pause(self):
        """ Start playing the video player """

        # Start playback
        self.player.Pause()

    def Seek(self, number):
        """ Seek to a specific frame """

        # Start playback
        self.player.Seek(number)

    def Speed(self, new_speed):
        """ Set the speed of the video player """

        # Start playback
        self.player.Speed(new_speed)