"""
 @file
 @brief This file loads the clip cutting interface (quickly cut up a clip into smaller clips)
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
import functools
import json
from copy import deepcopy

from PyQt5.QtCore import pyqtSignal, QTimer
from PyQt5.QtWidgets import QDialog, QMessageBox, QSizePolicy, QSlider
from PyQt5.QtCore import Qt, QEvent
import openshot  # Python module for libopenshot (required video editing module installed separately)

from classes import info, ui_util, time_parts
from classes.app import get_app
from classes.logger import log
from classes.metrics import track_metric_screen
from classes.ai_metadata_utils import adjust_scene_descriptions_for_subclip
from classes.query import File
from windows.preview_thread import PreviewParent
from windows.video_widget import VideoWidget


class Cutting(QDialog):
    """ Cutting Dialog """

    # Path to ui file
    ui_path = os.path.join(info.PATH, 'windows', 'ui', 'cutting.ui')

    # Signals for preview thread
    previewFrameSignal = pyqtSignal(int)
    refreshFrameSignal = pyqtSignal()
    LoadFileSignal = pyqtSignal(str)
    PlaySignal = pyqtSignal()
    PauseSignal = pyqtSignal()
    SeekSignal = pyqtSignal(int)
    SpeedSignal = pyqtSignal(float)
    StopSignal = pyqtSignal()

    def __init__(self, file=None, preview=False):
        _ = get_app()._tr

        # Create dialog class
        QDialog.__init__(self)

        # Load UI from designer
        ui_util.load_ui(self, self.ui_path)

        # Init UI
        ui_util.init_ui(self)

        # Track metrics
        track_metric_screen("cutting-screen")

        # Keep track of file object
        self.file = file
        self.file_path = file.absolute_path()
        self.video_length = int(file.data['video_length'])
        self.fps_num = int(file.data['fps']['num'])
        self.fps_den = int(file.data['fps']['den'])
        self.fps = float(self.fps_num) / float(self.fps_den)
        self.width = int(file.data['width'])
        self.height = int(file.data['height'])
        self.sample_rate = int(get_app().project.get("sample_rate"))
        self.channels = int(file.data['channels'])
        self.channel_layout = int(file.data['channel_layout'])

        self.start_frame = 1
        self.start_image = None
        self.end_frame = self.video_length
        self.end_image = None

        # If preview, hide cutting controls
        if preview:
            self.lblInstructions.setVisible(False)
            self.widgetControls.setVisible(False)
            self.setWindowTitle(_("Preview"))

        self.previous_start = 0.0
        if float(file.data.get("start", 0.0)) > 0.0:
            self.start_frame = round(file.data.get("start", 0) * self.fps) + 1

            # Remember the previous start property (on init)
            self.previous_start = self.file.data.get("start", 0.0)
        if float(file.data.get("end", 0.0)) > 0.0:
            self.end_frame = round(file.data.get("end", 0) * self.fps)
            self.video_length = (self.end_frame - self.start_frame) + 1

        # Set clip start / end
        clip_start = file.data.get("start", 0.0)
        clip_end = file.data.get("end", file.data.get("duration", 0.0))

        # Open video file with Reader
        log.info(self.file_path)

        # Add Video Widget
        self.videoPreview = VideoWidget()
        self.videoPreview.setObjectName("videoPreview")
        self.videoPreview.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.verticalLayout.insertWidget(0, self.videoPreview)

        # Set max size of video preview (for speed)
        viewport_rect = self.videoPreview.centeredViewport(self.videoPreview.width(), self.videoPreview.height())

        # Create an instance of a libopenshot Timeline object
        self.r = openshot.Timeline(
            viewport_rect.width(),
            viewport_rect.height(),
            openshot.Fraction(self.fps_num, self.fps_den),
            self.sample_rate,
            self.channels,
            self.channel_layout)
        self.r.info.channel_layout = self.channel_layout
        self.r.SetMaxSize(viewport_rect.width(), viewport_rect.height())

        try:
            # Add clip for current preview file
            self.clip = openshot.Clip(self.file_path)
            self.clip.SetJson(json.dumps({"reader": file.data}))
            self.clip.Start(clip_start)
            self.clip.End(clip_end)

            # Show waveform for audio files
            if not self.clip.Reader().info.has_video and self.clip.Reader().info.has_audio:
                self.clip.Waveform(True)

            # Set has_audio property
            self.r.info.has_audio = self.clip.Reader().info.has_audio

            # Update video_length property of the Timeline object
            self.r.info.video_length = self.video_length

            # Display frame #
            self.clip.display = openshot.FRAME_DISPLAY_CLIP
            self.r.AddClip(self.clip)

        except Exception:
            log.error(
                'Failed to load media file into preview player: %s',
                self.file_path)
            return

        # Open reader
        self.r.Open()

        # Start the preview thread
        self.initialized = False
        self.transforming_clip = False
        self.preview_parent = PreviewParent()
        self.preview_parent.Init(self, self.r, self.videoPreview, self.video_length)
        self.preview_thread = self.preview_parent.worker

        # Set slider constraints
        self.sliderIgnoreSignal = False
        self.sliderVideo.setMinimum(1)
        self.sliderVideo.setMaximum(self.video_length)
        self.sliderVideo.setSingleStep(1)
        self.sliderVideo.setSingleStep(1)
        self.sliderVideo.setPageStep(24)

        # Display start frame (and then the previous frame)
        QTimer.singleShot(500, functools.partial(self.sliderVideo.setValue, 2))
        QTimer.singleShot(600, functools.partial(self.sliderVideo.setValue, 1))

        # Connect signals
        self.actionPlay.triggered.connect(self.actionPlay_Triggered)
        self.btnPlay.clicked.connect(self.btnPlay_clicked)
        self.sliderVideo.valueChanged.connect(self.sliderVideo_valueChanged)
        self.sliderVideo.sliderReleased.connect(self.sliderVideo_released)
        self.btnStart.clicked.connect(self.btnStart_clicked)
        self.btnEnd.clicked.connect(self.btnEnd_clicked)
        self.btnClear.clicked.connect(self.btnClear_clicked)
        self.btnAddClip.clicked.connect(self.btnAddClip_clicked)
        self.txtName.installEventFilter(self)
        self.sliderVideo.installEventFilter(self)
        # Timer to ensure final preview update
        self.slider_timer = QTimer(self)
        self.slider_timer.setInterval(100)
        self.slider_timer.setSingleShot(True)
        self.slider_timer.timeout.connect(self.sliderVideo_timeout)
        self.initialized = True

    def eventFilter(self, obj, event):
        if event.type() == event.KeyPress and obj is self.txtName:
            # Handle ENTER key to create new clip
            if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
                if self.btnAddClip.isEnabled():
                    self.btnAddClip_clicked()
                    return True
        if event.type() == QEvent.MouseButtonPress and isinstance(obj, QSlider):
            # Handle QSlider click, jump to cursor position
            if event.button() == Qt.LeftButton:
                min_val = obj.minimum()
                max_val = obj.maximum()

                click_position = event.pos().x() if obj.orientation() == Qt.Horizontal else event.pos().y()
                slider_length = obj.width() if obj.orientation() == Qt.Horizontal else obj.height()
                new_value = min_val + ((max_val - min_val) * click_position) / slider_length

                obj.setValue(int(new_value))
                event.accept()
        return super().eventFilter(obj, event)

    def actionPlay_Triggered(self):
        # Trigger play button (This action is invoked from the preview thread, so it must exist here)
        self.btnPlay.click()

    def frame_to_timestamp(self, frame_number):
        """Return a timecode string for the given frame"""
        seconds = (frame_number - 1) / self.fps
        t = time_parts.secondsToTime(seconds, self.fps_num, self.fps_den)
        return "%s:%s:%s:%s" % (t["hour"], t["min"], t["sec"], t["frame"])

    def movePlayhead(self, frame_number):
        """Update the playhead position"""

        # Move slider to correct frame position
        self.sliderIgnoreSignal = True
        self.sliderVideo.setValue(frame_number)
        self.sliderIgnoreSignal = False

        # Update label
        self.lblVideoTime.setText(self.frame_to_timestamp(frame_number))

    def btnPlay_clicked(self, force=None):
        log.info("btnPlay_clicked")

        if force == "pause":
            self.btnPlay.setChecked(False)
        elif force == "play":
            self.btnPlay.setChecked(True)

        if self.btnPlay.isChecked():
            log.info('play (icon to pause)')
            ui_util.setup_icon(self, self.btnPlay, "actionPlay", "media-playback-pause")
            self.preview_thread.Play()
        else:
            log.info('pause (icon to play)')
            ui_util.setup_icon(self, self.btnPlay, "actionPlay", "media-playback-start")  # to default
            self.preview_thread.Pause()

        # Send focus back to toolbar
        self.sliderVideo.setFocus()

    def sliderVideo_valueChanged(self, new_frame):
        if self.preview_thread and not self.sliderIgnoreSignal:
            log.info('sliderVideo_valueChanged')
            # Pause video and update preview immediately
            self.btnPlay_clicked(force="pause")
            self.preview_thread.previewFrame(new_frame)
            # Start timer to ensure preview updates after dragging stops
            self.slider_timer.start()

    def sliderVideo_timeout(self):
        if self.preview_thread and not self.sliderIgnoreSignal:
            log.info('sliderVideo_timeout')
            self.btnPlay_clicked(force="pause")
            self.preview_thread.previewFrame(self.sliderVideo.value())

    def sliderVideo_released(self):
        if self.preview_thread and not self.sliderIgnoreSignal:
            log.info('sliderVideo_released')
            self.btnPlay_clicked(force="pause")
            self.preview_thread.previewFrame(self.sliderVideo.value())
            self.slider_timer.start()

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
        self.r.GetFrame(self.start_frame).Thumbnail(self.start_image, 160, 90, '', '', '#000000', True, 'png', 85)

        # Set CSS on button
        self.btnStart.setStyleSheet('background-image: url(%s);' % self.start_image.replace('\\', '/'))

        # Enable end button
        self.btnEnd.setEnabled(True)
        self.btnClear.setEnabled(True)

        # Send focus back to toolbar
        self.sliderVideo.setFocus()

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
        self.r.GetFrame(self.end_frame).Thumbnail(self.end_image, 160, 90, '', '', '#000000', True, 'png', 85)

        # Set CSS on button
        self.btnEnd.setStyleSheet('background-image: url(%s);' % self.end_image.replace('\\', '/'))

        # Enable create button
        self.btnAddClip.setEnabled(True)

        # Send focus back to toolbar
        self.sliderVideo.setFocus()

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

        # Calculate new start and end times
        new_start = self.previous_start + ((self.start_frame - 1) / self.fps)
        new_end = self.previous_start + (self.end_frame / self.fps)

        # Build a NEW File entry (do not mutate the original file object)
        new_file = File()
        new_file.data = deepcopy(self.file.data)
        new_file.data.pop('name', None)
        new_file.id = None
        new_file.key = None
        new_file.type = 'insert'
        new_file.data['start'] = new_start
        new_file.data['end'] = new_end

        # Handle ai_metadata translation for sub-clips (stored in source-media time)
        if 'ai_metadata' in new_file.data and isinstance(new_file.data.get('ai_metadata'), dict):
            new_file.data['ai_metadata'] = adjust_scene_descriptions_for_subclip(
                new_file.data['ai_metadata'], new_start, new_end
            )

        if self.txtName.text():
            new_file.data['name'] = self.txtName.text()
        else:
            global_frame = round(self.previous_start * self.fps) + self.start_frame
            timestamp = self.frame_to_timestamp(global_frame)
            base = os.path.splitext(os.path.basename(self.file_path))[0]
            new_file.data['name'] = f"{base} ({timestamp})"

        new_file.save()

        # Move to next frame
        self.sliderVideo.setValue(self.end_frame + 1)

        # Reset form
        self.clearForm()

    def closeEvent(self, event):
        log.debug('closeEvent')

        # Stop playback
        get_app().updates.disconnect_listener(self.videoPreview)
        if self.videoPreview:
            self.videoPreview.deleteLater()
            self.videoPreview = None
        self.preview_parent.Stop()

        # Close readers
        self.r.Close()
        self.clip.Close()
        self.r.ClearAllCache()

