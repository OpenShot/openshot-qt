""" 
 @file
 @brief This file loads the clip cutting interface (quickly cut up a clip into smaller clips)
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
import functools
import math

from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
import openshot  # Python module for libopenshot (required video editing module installed separately)

from classes import info, ui_util, settings, qt_types, updates
from classes.app import get_app
from classes.logger import log
from classes.metrics import *
from windows.preview_thread import PreviewParent
from windows.video_widget import VideoWidget

try:
    import json
except ImportError:
    import simplejson as json


class Cutting(QDialog):
    """ Cutting Dialog """

    # Path to ui file
    ui_path = os.path.join(info.PATH, 'windows', 'ui', 'cutting.ui')

    # Signals for preview thread
    previewFrameSignal = pyqtSignal(int)
    refreshFrameSignal = pyqtSignal()
    LoadFileSignal = pyqtSignal(str)
    PlaySignal = pyqtSignal(int)
    PauseSignal = pyqtSignal()
    SeekSignal = pyqtSignal(int)
    SpeedSignal = pyqtSignal(float)
    StopSignal = pyqtSignal()

    def __init__(self, file=None):

        # Create dialog class
        QDialog.__init__(self)

        # Load UI from designer
        ui_util.load_ui(self, self.ui_path)

        # Init UI
        ui_util.init_ui(self)

        # Track metrics
        track_metric_screen("cutting-screen")

        self.start_frame = 1
        self.start_image = None
        self.end_frame = 1
        self.end_image = None

        # Keep track of file object
        self.file = file
        self.file_path = file.absolute_path()
        self.video_length = int(file.data['video_length'])
        self.fps_num = int(file.data['fps']['num'])
        self.fps_den = int(file.data['fps']['den'])
        self.fps = float(self.fps_num) / float(self.fps_den)

        # Open video file with Reader
        log.info(self.file_path)
        self.r = openshot.FFmpegReader(self.file_path)
        self.r.Open()

        # Add Video Widget
        self.videoPreview = VideoWidget()
        self.videoPreview.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.verticalLayout.insertWidget(0, self.videoPreview)

        # Start the preview thread
        self.preview_parent = PreviewParent()
        self.preview_parent.Init(self, self.r, self.videoPreview)
        self.preview_thread = self.preview_parent.worker

        # Set slider constraints
        self.sliderIgnoreSignal = False
        self.sliderVideo.setMinimum(1)
        self.sliderVideo.setMaximum(self.video_length)
        self.sliderVideo.setSingleStep(1)
        self.sliderVideo.setSingleStep(1)
        self.sliderVideo.setPageStep(24)

        # Determine if a start or end attribute is in this file
        start_frame = 1
        if 'start' in self.file.data.keys():
            start_frame = (float(self.file.data['start']) * self.fps) + 1

        # Display start frame (and then the previous frame)
        QTimer.singleShot(500, functools.partial(self.sliderVideo.setValue, start_frame + 1))
        QTimer.singleShot(600, functools.partial(self.sliderVideo.setValue, start_frame))

        # Connect signals
        self.btnPlay.clicked.connect(self.btnPlay_clicked)
        self.sliderVideo.valueChanged.connect(self.sliderVideo_valueChanged)
        self.btnStart.clicked.connect(self.btnStart_clicked)
        self.btnEnd.clicked.connect(self.btnEnd_clicked)
        self.btnClear.clicked.connect(self.btnClear_clicked)
        self.btnAddClip.clicked.connect(self.btnAddClip_clicked)

    def movePlayhead(self, frame_number):
        """Update the playhead position"""

        # Move slider to correct frame position
        self.sliderIgnoreSignal = True
        self.sliderVideo.setValue(frame_number)
        self.sliderIgnoreSignal = False

        # Convert frame to seconds
        seconds = (frame_number-1) / self.fps

        # Convert seconds to time stamp
        time_text = self.secondsToTime(seconds, self.fps_num, self.fps_den)
        timestamp = "%s:%s:%s:%s" % (time_text["hour"], time_text["min"], time_text["sec"], time_text["frame"])

        # Update label
        self.lblVideoTime.setText(timestamp)

    def btnPlay_clicked(self, force=None):
        log.info("btnPlay_clicked")

        if force == "pause":
            self.btnPlay.setChecked(False)
        elif force == "play":
            self.btnPlay.setChecked(True)

        if self.btnPlay.isChecked():
            log.info('play (icon to pause)')
            ui_util.setup_icon(self, self.btnPlay, "actionPlay", "media-playback-pause")
            self.preview_thread.Play(self.video_length)
        else:
            log.info('pause (icon to play)')
            ui_util.setup_icon(self, self.btnPlay, "actionPlay", "media-playback-start")  # to default
            self.preview_thread.Pause()

    def sliderVideo_valueChanged(self, new_frame):
        if self.preview_thread and not self.sliderIgnoreSignal:
            log.info('sliderVideo_valueChanged')

            # Pause video
            self.btnPlay_clicked(force="pause")

            # Seek to new frame
            self.preview_thread.previewFrame(new_frame)

    def btnStart_clicked(self):
        """Start of clip button was clicked"""
        _ = get_app()._tr

        # Pause video
        self.btnPlay_clicked(force="pause")

        # Get the current frame
        current_frame = self.sliderVideo.value()

        # Check if starting frame less than end frame
        if self.btnEnd.isEnabled() and current_frame >= self.end_frame:
            # Handle exception
            msg = QMessageBox()
            msg.setText(_("Please choose valid 'start' and 'end' values for your clip."))
            msg.exec_()
            return

        # remember frame #
        self.start_frame = current_frame

        # Save thumbnail image
        self.start_image = os.path.join(info.USER_PATH, 'thumbnail', '%s.png' % self.start_frame)
        self.r.GetFrame(self.start_frame).Thumbnail(self.start_image, 160, 90, '', '', '#000000', True)

        # Set CSS on button
        self.btnStart.setStyleSheet('background-image: url(%s);' % self.start_image.replace('\\', '/'))

        # Enable end button
        self.btnEnd.setEnabled(True)
        self.btnClear.setEnabled(True)

        log.info('btnStart_clicked, current frame: %s' % self.start_frame)

    def btnEnd_clicked(self):
        """End of clip button was clicked"""
        _ = get_app()._tr

        # Pause video
        self.btnPlay_clicked(force="pause")

        # Get the current frame
        current_frame = self.sliderVideo.value()

        # Check if ending frame greater than start frame
        if current_frame <= self.start_frame:
            # Handle exception
            msg = QMessageBox()
            msg.setText(_("Please choose valid 'start' and 'end' values for your clip."))
            msg.exec_()
            return

        # remember frame #
        self.end_frame = current_frame

        # Save thumbnail image
        self.end_image = os.path.join(info.USER_PATH, 'thumbnail', '%s.png' % self.end_frame)
        self.r.GetFrame(self.end_frame).Thumbnail(self.end_image, 160, 90, '', '', '#000000', True)

        # Set CSS on button
        self.btnEnd.setStyleSheet('background-image: url(%s);' % self.end_image.replace('\\', '/'))

        # Enable create button
        self.btnAddClip.setEnabled(True)

        log.info('btnEnd_clicked, current frame: %s' % self.end_frame)

    def btnClear_clicked(self):
        """Clear the current clip and reset the form"""
        log.info('btnClear_clicked')

        # Reset form
        self.clearForm()

    def clearForm(self):
        """Clear all form controls"""
        # Clear buttons
        self.start_frame = 1
        self.end_frame = 1
        self.start_image = ''
        self.end_image = ''
        self.btnStart.setStyleSheet('background-image: None;')
        self.btnEnd.setStyleSheet('background-image: None;')

        # Clear text
        self.txtName.setText('')

        # Disable buttons
        self.btnEnd.setEnabled(False)
        self.btnAddClip.setEnabled(False)
        self.btnClear.setEnabled(False)

    def btnAddClip_clicked(self):
        """Add the selected clip to the project"""
        log.info('btnAddClip_clicked')

        # Remove unneeded attributes
        if 'name' in self.file.data.keys():
            self.file.data.pop('name')

        # Save new file
        self.file.id = None
        self.file.key = None
        self.file.type = 'insert'
        self.file.data['start'] = (self.start_frame-1) / self.fps
        self.file.data['end'] = (self.end_frame-1) / self.fps
        if self.txtName.text():
            self.file.data['name'] = self.txtName.text()
        self.file.save()

        # Reset form
        self.clearForm()

    def padNumber(self, value, pad_length):
        format_mask = '%%0%sd' % pad_length
        return format_mask % value

    def secondsToTime(self, secs, fps_num, fps_den):
        # calculate time of playhead
        milliseconds = secs * 1000
        sec = math.floor(milliseconds/1000)
        milli = milliseconds % 1000
        min = math.floor(sec/60)
        sec = sec % 60
        hour = math.floor(min/60)
        min = min % 60
        day = math.floor(hour/24)
        hour = hour % 24
        week = math.floor(day/7)
        day = day % 7

        frame = round((milli / 1000.0) * (fps_num / fps_den)) + 1
        return { "week":self.padNumber(week,2), "day":self.padNumber(day,2), "hour":self.padNumber(hour,2), "min":self.padNumber(min,2), "sec":self.padNumber(sec,2), "milli":self.padNumber(milli,2), "frame":self.padNumber(frame,2) };

    # TODO: Remove these 4 methods
    def accept(self):
        """ Ok button clicked """
        log.info('accept')

    def close(self):
        """ Actually close window and accept dialog """
        log.info('close')

    def closeEvent(self, event):
        log.info('closeEvent')

        # Stop preview and kill thread
        self.preview_parent.worker.Pause()
        self.preview_parent.worker.kill()

        # Wait for thread
        self.preview_parent.background.wait(250)

        # Stop reader
        self.r.Close()

    def reject(self):
        log.info('reject')



