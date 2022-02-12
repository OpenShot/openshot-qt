"""
 @file
 @brief This file contains the preview thread, used for displaying previews of the timeline
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

import time
import sip

from PyQt5.QtCore import QObject, QThread, pyqtSlot, pyqtSignal, QCoreApplication
from PyQt5.QtWidgets import QMessageBox
import openshot  # Python module for libopenshot (required video editing module installed separately)

from classes.app import get_app
from classes.logger import log


class PreviewParent(QObject):
    """ Class which communicates with the PlayerWorker Class (running on a separate thread) """

    # Signal when the frame position changes in the preview player
    def onPositionChanged(self, current_frame):
        self.parent.movePlayhead(current_frame)

        # Check if we are at the end of the timeline
        if self.worker.player.Mode() == openshot.PLAYBACK_PLAY and current_frame >= self.worker.timeline_length and self.worker.timeline_length != -1:
            # Yes, pause the video
            self.parent.actionPlay.trigger()
            self.worker.timeline_length = -1

    # Signal when the playback mode changes in the preview player (i.e PLAY, PAUSE, STOP)
    def onModeChanged(self, current_mode):
        log.debug('Playback mode changed to %s', current_mode)
        try:
            if current_mode is openshot.PLAYBACK_PLAY:
                self.parent.SetPlayheadFollow(False)
            else:
                self.parent.SetPlayheadFollow(True)
        except AttributeError:
            # Parent object doesn't need the playhead follow code
            pass

    # Signal when the playback encounters an error
    def onError(self, error):
        log.warning('Player error: %s', error)

        # Get translation object
        _ = get_app()._tr

        # Only JUCE audio errors bubble up here now
        QMessageBox.warning(self.parent, _("Audio Error"), _("Please fix the following error and restart OpenShot\n%s") % error)

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
        self.worker.error_found.connect(self.onError)

        # Connect preview thread to main UI signals
        self.parent.previewFrameSignal.connect(self.worker.previewFrame)
        self.parent.refreshFrameSignal.connect(self.worker.refreshFrame)
        self.parent.LoadFileSignal.connect(self.worker.LoadFile)
        self.parent.PlaySignal.connect(self.worker.Play)
        self.parent.PauseSignal.connect(self.worker.Pause)
        self.parent.SeekSignal.connect(self.worker.Seek)
        self.parent.SpeedSignal.connect(self.worker.Speed)
        self.parent.StopSignal.connect(self.worker.Stop)

        # Move Worker to new thread, and Start
        self.worker.moveToThread(self.background)
        self.background.start()


class PlayerWorker(QObject):
    """ QT Player Worker Object (to preview video on a separate thread) """

    position_changed = pyqtSignal(int)
    mode_changed = pyqtSignal(object)
    error_found = pyqtSignal(object)
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
        self.previous_clips = []
        self.previous_clip_readers = []
        self.is_running = True
        self.number = None
        self.current_frame = None
        self.current_mode = None
        self.timeline_length = -1

        # Create QtPlayer class from libopenshot
        self.player = openshot.QtPlayer()

    @pyqtSlot()
    def Start(self):
        """ This method starts the video player """
        log.info("QThread Start Method Invoked")

        # Init new player
        self.initPlayer()

        # Connect player to timeline reader
        self.player.Reader(self.timeline)
        self.player.Play()
        self.player.Pause()

        # Check for any Player initialization errors (only JUCE errors bubble up here now)
        if self.player.GetError():
            # Emit error_found signal
            self.error_found.emit(self.player.GetError())

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
            QCoreApplication.processEvents()

        self.finished.emit()
        log.debug('exiting playback thread')

    @pyqtSlot()
    def initPlayer(self):
        log.debug("initPlayer")

        # Get the address of the player's renderer (a QObject that emits signals when frames are ready)
        self.renderer_address = self.player.GetRendererQObject()
        self.player.SetQWidget(sip.unwrapinstance(self.videoPreview))
        self.renderer = sip.wrapinstance(self.renderer_address, QObject)
        self.videoPreview.connectSignals(self.renderer)

    def kill(self):
        """ Kill this thread """
        self.is_running = False

    def previewFrame(self, number):
        """ Preview a certain frame """
        # Mark frame number for processing
        self.Seek(number)

        log.debug(
            "previewFrame: %s, player Position(): %s",
            number, self.player.Position())

    def refreshFrame(self):
        """ Refresh a certain frame """
        log.debug("refreshFrame")

        # Always load back in the timeline reader
        self.parent.LoadFileSignal.emit('')

        # Mark frame number for processing (if parent is done initializing)
        self.Seek(self.player.Position())

        log.info("player Position(): %s", self.player.Position())

    def LoadFile(self, path=None):
        """ Load a media file into the video player """
        # Check to see if this path is already loaded
        # TODO: Determine why path is passed in as an empty string instead of None
        if path == self.clip_path or (not path and not self.clip_path):
            return

        log.info("LoadFile %s" % path)

        # Determine the current frame of the timeline (when switching to a clip)
        seek_position = 1
        if path and not self.clip_path:
            # Track the current frame
            self.original_position = self.player.Position()

        # If blank path, switch back to self.timeline reader
        if not path:
            # Return to self.timeline reader
            log.debug("Set timeline reader again in player: %s" % self.timeline)
            self.player.Reader(self.timeline)

            # Clear clip reader reference
            self.clip_reader = None
            self.clip_path = None

            # Switch back to last timeline position
            seek_position = self.original_position
        else:
            # Create new timeline reader (to preview selected clip)
            project = get_app().project

            # Get some settings from the project
            fps = project.get("fps")
            width = project.get("width")
            height = project.get("height")
            sample_rate = project.get("sample_rate")
            channels = project.get("channels")
            channel_layout = project.get("channel_layout")

            # Create an instance of a libopenshot Timeline object
            self.clip_reader = openshot.Timeline(width, height, openshot.Fraction(fps["num"], fps["den"]), sample_rate, channels, channel_layout)
            self.clip_reader.info.channel_layout = channel_layout
            self.clip_reader.info.has_audio = True
            self.clip_reader.info.has_video = True
            self.clip_reader.info.video_length = 999999
            self.clip_reader.info.duration = 999999
            self.clip_reader.info.sample_rate = sample_rate
            self.clip_reader.info.channels = channels

            try:
                # Add clip for current preview file
                new_clip = openshot.Clip(path)
                self.clip_reader.AddClip(new_clip)
            except:
                log.error('Failed to load media file into video player: %s' % path)
                return

            # Assign new clip_reader
            self.clip_path = path

            # Keep track of previous clip readers (so we can Close it later)
            self.previous_clips.append(new_clip)
            self.previous_clip_readers.append(self.clip_reader)

            # Open and set reader
            self.clip_reader.Open()
            self.player.Reader(self.clip_reader)

        # Close and destroy old clip readers (leaving the 3 most recent)
        while len(self.previous_clip_readers) > 3:
            log.debug('Removing old clips from preview: %s' % self.previous_clip_readers[0])
            previous_clip = self.previous_clips.pop(0)
            previous_clip.Close()
            previous_reader = self.previous_clip_readers.pop(0)
            previous_reader.Close()

        # Seek to frame 1, and resume speed
        self.Seek(seek_position)

    def Play(self, timeline_length):
        """ Start playing the video player """

        # Set length of timeline in frames
        self.timeline_length = timeline_length

        # Start playback
        if self.parent.initialized:
            self.player.Play()

    def Pause(self):
        """ Pause the video player """

        # Pause playback
        if self.parent.initialized:
            self.player.Pause()

    def Stop(self):
        """ Stop the video player and terminate the playback threads """

        # Stop playback
        if self.parent.initialized:
            self.player.Stop()

    def Seek(self, number):
        """ Seek to a specific frame """

        # Seek to frame
        if self.parent.initialized:
            self.player.Seek(number)

    def Speed(self, new_speed):
        """ Set the speed of the video player """

        # Set speed
        if self.parent.initialized and self.player.Speed() != new_speed:
            self.player.Speed(new_speed)
