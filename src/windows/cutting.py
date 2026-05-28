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

from qt_api import pyqtSignal, QTimer, QSize
from qt_api import Qt, QEvent
from qt_api import QIcon
from qt_api import QDialog, QMessageBox, QSizePolicy, QSlider, QToolButton, QLineEdit
import openshot  # Python module for libopenshot (required video editing module installed separately)

from classes import info, ui_util, time_parts
from classes.app import get_app
from classes.clip_utils import is_single_image_media
from classes.logger import log
from classes.metrics import track_metric_screen
from classes.proxy_service import dialog_preview_reader_data
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
    LoadTimelineAndSeekSignal = pyqtSignal(int)
    SpeedSignal = pyqtSignal(float)
    StopSignal = pyqtSignal()

    @staticmethod
    def _preview_window_title(file_obj, translate):
        _ = translate
        if not file_obj or not hasattr(file_obj, "data") or not isinstance(file_obj.data, dict):
            return _("Preview")
        friendly_name = str(file_obj.data.get("name") or "").strip()
        if not friendly_name:
            friendly_name = os.path.basename(str(file_obj.data.get("path") or "").strip())
        if friendly_name:
            return _("Preview: %s") % friendly_name
        return _("Preview")

    def __init__(self, file=None, preview=False):
        _ = get_app()._tr
        self.is_preview_mode = preview
        self._preview_autoplay_active = preview
        self._preview_autoplay_attempts = 0
        self._shutdown_in_progress = False
        self._close_after_shutdown = False
        self.loop_playback = bool(preview)

        # Create dialog class
        super().__init__()

        # Load UI from designer
        ui_util.load_ui(self, self.ui_path)

        # Init UI
        ui_util.init_ui(self)
        self.setWindowFlags(
            (self.windowFlags() & ~Qt.Dialog)
            | Qt.Window
            | Qt.WindowMinMaxButtonsHint
            | Qt.WindowMaximizeButtonHint
        )
        self.setSizeGripEnabled(True)

        # Track metrics
        track_metric_screen("cutting-screen")

        # Keep track of file object
        self.file = file
        self.source_reader_data = dialog_preview_reader_data(file, prefer_proxy=False)
        self.proxy_reader_data = dialog_preview_reader_data(file, prefer_proxy=True)
        self.reader_data = self.proxy_reader_data
        self.file_path = str(self.reader_data.get("path") or file.absolute_path() or "")
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
            self.setWindowTitle(self._preview_window_title(file, _))

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
        self.videoPreview = VideoWidget(watch_project=False)
        self.videoPreview.win = self
        self.videoPreview.setObjectName("videoPreview")
        self.videoPreview.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.verticalLayout.insertWidget(0, self.videoPreview)

        # Set max size of video preview (for speed)
        viewport_rect = self.videoPreview.centeredViewport(self.videoPreview.width(), self.videoPreview.height())

        try:
            self._build_preview_timeline(self.reader_data, QSize(viewport_rect.width(), viewport_rect.height()))
        except Exception:
            log.error(
                'Failed to load media file into preview player: %s',
                self.file_path)
            return

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
        self.sliderVideo.setPageStep(24)
        if self.is_preview_mode:
            self._build_preview_repeat_button()

        # Initialize first frame display.
        # For cutting mode, preserve the legacy two-step seek refresh.
        # For preview mode, avoid the seek/pause startup hack so autoplay
        # isn't fighting initialization pauses.
        if self.is_preview_mode:
            self.sliderIgnoreSignal = True
            self.sliderVideo.setValue(1)
            self.sliderIgnoreSignal = False
        else:
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
        self.videoPreview.delayed_resize_timer.timeout.connect(self._apply_dynamic_preview_max_size)
        self.initialized = True

    def _build_preview_repeat_button(self):
        _ = get_app()._tr
        self.btnRepeat = QToolButton(self)
        self.btnRepeat.setObjectName("btnRepeat")
        self.btnRepeat.setCheckable(True)
        self.btnRepeat.setChecked(True)
        self.btnRepeat.setAutoRaise(True)
        self.btnRepeat.setFixedSize(24, 24)
        self.btnRepeat.setToolTip(_("Repeat"))
        self.btnRepeat.setStyleSheet(
            "QToolButton#btnRepeat { border-radius: 4px; }"
            "QToolButton#btnRepeat:checked { background-color: rgba(83,160,237,80); }"
        )
        self.btnRepeat.toggled.connect(self._on_repeat_toggled)
        self.horizontalLayout_3.insertWidget(2, self.btnRepeat)

        icon = ui_util.get_icon("media-playlist-repeat")
        if icon is None or icon.isNull():
            icon_path = os.path.join(info.PATH, "themes", "cosmic", "images", "tool-media-repeat.svg")
            icon = QIcon(icon_path)
        self.btnRepeat.setIcon(icon)

    def _on_repeat_toggled(self, checked):
        self.loop_playback = bool(checked)

    def keyPressEvent(self, event):
        if event and event.key() == Qt.Key_Space:
            focused = self.focusWidget()
            if focused and isinstance(focused, QLineEdit):
                return super(Cutting, self).keyPressEvent(event)
            if hasattr(self, "btnPlay") and self.btnPlay is not None:
                self.btnPlay.click()
                event.accept()
                return
        return super(Cutting, self).keyPressEvent(event)

    def _target_preview_max_size(self):
        viewport_rect = self.videoPreview.centeredViewport(self.videoPreview.width(), self.videoPreview.height())
        device_pixel_ratio = self.devicePixelRatioF()
        requested = QSize(
            max(2, int(round(viewport_rect.width() * device_pixel_ratio))),
            max(2, int(round(viewport_rect.height() * device_pixel_ratio))),
        )

        source_width = int(getattr(self, "width", 0) or 0)
        source_height = int(getattr(self, "height", 0) or 0)
        file_data = getattr(getattr(self, "file", None), "data", {})
        if is_single_image_media(getattr(self, "reader_data", {})) or is_single_image_media(file_data):
            project = getattr(get_app(), "project", None)
            if project:
                source_width = max(source_width, int(project.get("width") or 0))
                source_height = max(source_height, int(project.get("height") or 0))
        if source_width > 0 and source_height > 0:
            source_size = QSize(source_width, source_height)
            if requested.width() > source_width or requested.height() > source_height:
                capped = QSize(source_size)
            else:
                capped = QSize(requested)
        else:
            capped = requested

        if capped.height() > 0:
            ratio = float(capped.width()) / float(capped.height())
            even_width = max(2, int(round(capped.width() / 2.0) * 2))
            even_height = max(2, int(round(round(even_width / ratio) / 2.0) * 2))
            capped = QSize(even_width, even_height)

        return capped

    def _reader_capacity(self, reader_data):
        try:
            return int(reader_data.get("width", 0) or 0), int(reader_data.get("height", 0) or 0)
        except Exception:
            return 0, 0

    def _select_reader_data_for_size(self, target_size):
        _ = target_size
        proxy_data = getattr(self, "proxy_reader_data", None) or {}
        source_data = getattr(self, "source_reader_data", None) or {}
        proxy_path = str(proxy_data.get("path") or "")
        if proxy_path:
            return proxy_data
        return source_data or proxy_data

    def _build_preview_timeline(self, reader_data, max_size):
        self.reader_data = reader_data
        self.file_path = str(reader_data.get("path") or self.file.absolute_path() or "")
        is_single_image = bool(is_single_image_media(reader_data) or is_single_image_media(getattr(self.file, "data", {})))
        source_path = str(getattr(self.source_reader_data, "get", lambda *_: "")("path") or "")
        proxy_path = str(getattr(self.proxy_reader_data, "get", lambda *_: "")("path") or "")
        if self.file_path and self.file_path == proxy_path and proxy_path != source_path:
            reader_kind = "proxy_reader"
        else:
            reader_kind = "source_reader"
        log.debug(
            "Preview dialog opening with %s path=%s size=%sx%s",
            reader_kind,
            self.file_path,
            int(reader_data.get("width", 0) or 0),
            int(reader_data.get("height", 0) or 0),
        )

        self.clip = openshot.Clip(self.file_path)
        if not is_single_image:
            self.clip.SetJson(json.dumps({
                "reader_orientation_mode": "reader",
                "reader": self.reader_data,
            }))
        self.clip.Open()

        c_info = self.clip.Reader().info
        self.width = int(getattr(c_info, "width", self.width))
        self.height = int(getattr(c_info, "height", self.height))
        fps_info = getattr(c_info, "fps", None)
        self.fps_num = int(getattr(fps_info, "num", self.fps_num))
        self.fps_den = int(getattr(fps_info, "den", self.fps_den))
        self.fps = float(self.fps_num) / float(self.fps_den or 1)
        project = getattr(get_app(), "project", None)
        if project:
            self.sample_rate = int(project.get("sample_rate"))
            self.channels = int(project.get("channels"))
            self.channel_layout = int(project.get("channel_layout"))

        base_width = max(2, int(self.width or max_size.width() or 2))
        base_height = max(2, int(self.height or max_size.height() or 2))
        if is_single_image:
            project = getattr(get_app(), "project", None)
            if project:
                base_width = max(base_width, int(project.get("width") or 0))
                base_height = max(base_height, int(project.get("height") or 0))

        aspect_ratio = openshot.Fraction(base_width, base_height)
        aspect_ratio.Reduce()
        self.videoPreview.aspect_ratio = aspect_ratio
        viewport_rect = self.videoPreview.centeredViewport(self.videoPreview.width(), self.videoPreview.height())
        max_size = QSize(max(2, int(viewport_rect.width())), max(2, int(viewport_rect.height())))

        self.r = openshot.Timeline(
            base_width,
            base_height,
            openshot.Fraction(self.fps_num, self.fps_den),
            self.sample_rate,
            self.channels,
            self.channel_layout)
        self.r.info.channel_layout = self.channel_layout
        self.r.SetMaxSize(max_size.width(), max_size.height())

        self.clip.Start(self.file.data.get("start", 0.0))
        self.clip.End(self.file.data.get("end", self.file.data.get("duration", 0.0)))

        if not self.clip.Reader().info.has_video and self.clip.Reader().info.has_audio:
            self.clip.Waveform(True)

        self.r.info.has_audio = self.clip.Reader().info.has_audio
        self.r.info.video_length = self.video_length
        self.clip.display = openshot.FRAME_DISPLAY_CLIP
        self.r.AddClip(self.clip)
        self.r.Open()

    def _reload_preview_reader(self, reader_data, max_size):
        current_frame = max(1, int(self.sliderVideo.value() or 1))
        old_preview_parent = getattr(self, "preview_parent", None)
        old_timeline = getattr(self, "r", None)
        old_clip = getattr(self, "clip", None)
        was_playing = False
        try:
            was_playing = (
                getattr(self, "preview_thread", None) is not None
                and self.preview_thread.player.Mode() == openshot.PLAYBACK_PLAY
                and self.preview_thread.player.Speed() != 0.0
            )
        except Exception:
            was_playing = False

        self.initialized = False
        if old_preview_parent:
            try:
                old_preview_parent.Stop(wait_for_thread=True)
            except Exception as exc:
                log.warning("Failed to stop previous cutting preview thread cleanly: %s", exc)

        self._build_preview_timeline(reader_data, max_size)

        self.preview_parent = PreviewParent()
        self.preview_parent.Init(self, self.r, self.videoPreview, self.video_length)
        self.preview_thread = self.preview_parent.worker
        self.initialized = True
        self.LoadTimelineAndSeekSignal.emit(current_frame)
        if was_playing:
            QTimer.singleShot(0, lambda: self.btnPlay_clicked(force="play"))

        if old_timeline:
            try:
                old_timeline.Close()
                old_timeline.ClearAllCache(True)
            except Exception:
                pass
        if old_clip:
            try:
                old_clip.Close()
            except Exception:
                pass

    def _apply_dynamic_preview_max_size(self):
        if not getattr(self, "initialized", False) or not getattr(self, "r", None):
            return

        new_size = self._target_preview_max_size()
        desired_reader_data = self._select_reader_data_for_size(new_size)
        if str(desired_reader_data.get("path") or "") != str(getattr(self, "reader_data", {}).get("path") or ""):
            self._reload_preview_reader(desired_reader_data, new_size)
            return

        previous_width = int(getattr(self.r, "preview_width", 0) or 0)
        previous_height = int(getattr(self.r, "preview_height", 0) or 0)

        if previous_width == new_size.width() and previous_height == new_size.height():
            return

        was_playing = False
        try:
            was_playing = (
                getattr(self, "preview_thread", None) is not None
                and self.preview_thread.player.Mode() == openshot.PLAYBACK_PLAY
                and self.preview_thread.player.Speed() != 0.0
            )
        except Exception:
            was_playing = False

        self.PauseSignal.emit()
        self.r.SetMaxSize(new_size.width(), new_size.height())
        self.r.ClearAllCache(True)
        self.refreshFrameSignal.emit()
        if was_playing:
            QTimer.singleShot(0, lambda: self.btnPlay_clicked(force="play"))

    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress and obj is self.txtName:
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

    def frame_to_compact_timestamp(self, frame_number, include_hours=False, include_minutes=False):
        """Return a compact timecode for split clip names"""
        seconds = (frame_number - 1) / self.fps
        t = time_parts.secondsToTime(seconds, self.fps_num, self.fps_den)

        hours = int(t["hour"])
        minutes = int(t["min"])
        secs = int(t["sec"])
        frames = int(t["frame"])

        if include_hours:
            return f"{hours:02d}:{minutes:02d}:{secs:02d};{frames:02d}"
        if include_minutes:
            return f"{minutes:02d}:{secs:02d};{frames:02d}"
        return f"{secs:02d};{frames:02d}"

    def movePlayhead(self, frame_number):
        """Update the playhead position"""

        # Keep slider drag native; ignore async playhead pushes while dragging.
        if self.sliderVideo.isSliderDown():
            self.lblVideoTime.setText(self.frame_to_timestamp(self.sliderVideo.value()))
            return

        # Move slider to correct frame position
        self.sliderIgnoreSignal = True
        self.sliderVideo.setValue(frame_number)
        self.sliderIgnoreSignal = False

        # Update label
        self.lblVideoTime.setText(self.frame_to_timestamp(frame_number))

    def btnPlay_clicked(self, force=None):
        log.info("btnPlay_clicked")

        if force is None and self._preview_autoplay_active:
            # Respect explicit user input (don't keep forcing startup autoplay).
            self._preview_autoplay_active = False

        if force == "pause":
            self.btnPlay.setChecked(False)
        elif force == "play":
            self.btnPlay.setChecked(True)

        if self.btnPlay.isChecked():
            log.info('play (icon to pause)')
            ui_util.setup_icon(self, self.btnPlay, "actionPlay", "media-playback-pause")
            # In non-loop mode, replay from the beginning when currently at end.
            if not self.loop_playback:
                try:
                    current_pos = int(self.preview_thread.player.Position())
                except Exception:
                    current_pos = 1
                if current_pos >= int(self.video_length):
                    self.SeekSignal.emit(1)
            self.PlaySignal.emit()
        else:
            log.info('pause (icon to play)')
            ui_util.setup_icon(self, self.btnPlay, "actionPlay", "media-playback-start")  # to default
            self.PauseSignal.emit()

        # Send focus back to toolbar
        self.sliderVideo.setFocus()

    def _start_preview_autoplay(self):
        if not self._preview_autoplay_active or not self.is_preview_mode:
            return
        if not getattr(self, "initialized", False):
            QTimer.singleShot(120, lambda: Cutting._start_preview_autoplay(self))
            return
        if not getattr(self, "preview_thread", None):
            QTimer.singleShot(120, lambda: Cutting._start_preview_autoplay(self))
            return
        if (
            getattr(self, "videoPreview", None) is not None
            and getattr(self.videoPreview, "delayed_resize_timer", None) is not None
            and self.videoPreview.delayed_resize_timer.isActive()
        ):
            # Let preview resize/max-size settling finish before forcing the
            # first autoplay attempt, otherwise startup can pause/clear the
            # preview cache mid-play and produce an audible glitch.
            QTimer.singleShot(120, lambda: Cutting._start_preview_autoplay(self))
            return
        if self._preview_autoplay_attempts >= 30:
            self._preview_autoplay_active = False
            return

        self._preview_autoplay_attempts += 1
        self.btnPlay_clicked(force="play")

        QTimer.singleShot(120, lambda: Cutting._start_preview_autoplay(self))

    def _preview_ready(self):
        if not self.is_preview_mode:
            return
        if getattr(self, "preview_thread", None):
            # Startup preview should show frame 1 immediately without waiting for
            # preroll/cache work before the first autoplay attempt.
            self.preview_thread.Seek(1, False)
        else:
            self.SeekSignal.emit(1)
        if self._preview_autoplay_active:
            QTimer.singleShot(0, self._start_preview_autoplay)

    def _preview_mode_changed(self, mode):
        play_mode = getattr(openshot, "PLAYBACK_PLAY", None)
        paused_mode = getattr(openshot, "PLAYBACK_PAUSED", getattr(openshot, "PLAYBACK_PAUSE", None))
        stop_mode = getattr(openshot, "PLAYBACK_STOPPED", getattr(openshot, "PLAYBACK_STOP", None))

        # Keep the play button state visually in sync with current playback mode.
        if mode == play_mode and not self.btnPlay.isChecked():
            self.btnPlay.setChecked(True)
            ui_util.setup_icon(self, self.btnPlay, "actionPlay", "media-playback-pause")
        if mode == play_mode and self._preview_autoplay_active and self._preview_autoplay_attempts > 0:
            self._preview_autoplay_active = False
        elif mode in (paused_mode, stop_mode) and self.btnPlay.isChecked():
            self.btnPlay.setChecked(False)
            ui_util.setup_icon(self, self.btnPlay, "actionPlay", "media-playback-start")

        if not self.is_preview_mode or not self._preview_autoplay_active:
            return

    def sliderVideo_valueChanged(self, new_frame):
        if self.preview_thread and not self.sliderIgnoreSignal:
            log.info('sliderVideo_valueChanged')
            # Pause video and update preview immediately
            self.btnPlay_clicked(force="pause")
            self.previewFrameSignal.emit(new_frame)
            # Start timer to ensure preview updates after dragging stops
            self.slider_timer.start()

    def sliderVideo_timeout(self):
        if self.preview_thread and not self.sliderIgnoreSignal:
            log.info('sliderVideo_timeout')
            self.btnPlay_clicked(force="pause")
            self.previewFrameSignal.emit(self.sliderVideo.value())

    def sliderVideo_released(self):
        if self.preview_thread and not self.sliderIgnoreSignal:
            log.info('sliderVideo_released')
            self.btnPlay_clicked(force="pause")
            self.previewFrameSignal.emit(self.sliderVideo.value())
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

        # Remove unneeded attributes
        if 'name' in self.file.data:
            self.file.data.pop('name')

        # Save new file
        self.file.id = None
        self.file.key = None
        self.file.type = 'insert'
        self.file.data['start'] = self.previous_start + ((self.start_frame - 1) / self.fps)
        self.file.data['end'] = self.previous_start + (self.end_frame / self.fps)
        if self.txtName.text():
            self.file.data['name'] = self.txtName.text()
        else:
            global_start_frame = round(self.previous_start * self.fps) + self.start_frame
            global_end_frame = round(self.previous_start * self.fps) + self.end_frame
            start_seconds = (global_start_frame - 1) / self.fps
            end_seconds = (global_end_frame - 1) / self.fps
            start_parts = time_parts.secondsToTime(start_seconds, self.fps_num, self.fps_den)
            end_parts = time_parts.secondsToTime(end_seconds, self.fps_num, self.fps_den)

            include_hours = int(start_parts["hour"]) > 0 or int(end_parts["hour"]) > 0
            include_minutes = (
                include_hours
                or int(start_parts["min"]) > 0
                or int(end_parts["min"]) > 0
            )
            start_timestamp = self.frame_to_compact_timestamp(
                global_start_frame, include_hours=include_hours, include_minutes=include_minutes)
            end_timestamp = self.frame_to_compact_timestamp(
                global_end_frame, include_hours=include_hours, include_minutes=include_minutes)
            base = os.path.splitext(os.path.basename(self.file_path))[0]
            self.file.data['name'] = f"{base} ({start_timestamp} to {end_timestamp})"
        self.file.save()

        # Move to next frame
        self.sliderVideo.setValue(self.end_frame + 1)

        # Reset form
        self.clearForm()

    def _finalize_preview_shutdown(self):
        if getattr(self, "videoPreview", None):
            get_app().updates.disconnect_listener(self.videoPreview)
            self.videoPreview.deleteLater()
            self.videoPreview = None

        if getattr(self, "r", None):
            try:
                self.r.Close()
                self.r.ClearAllCache()
            except Exception:
                pass
        if getattr(self, "clip", None):
            try:
                self.clip.Close()
            except Exception:
                pass

        self.preview_parent = None
        self.preview_thread = None

    def _on_preview_stopped(self):
        self._finalize_preview_shutdown()
        self._shutdown_in_progress = False
        if self._close_after_shutdown:
            self._close_after_shutdown = False
            super().reject()

    def _shutdown_preview(self, close_dialog=False):
        # Stop playback and preview worker safely (used by ESC/reject and close).
        if close_dialog:
            self._close_after_shutdown = True

        if self._shutdown_in_progress:
            return
        self._shutdown_in_progress = True

        if getattr(self, "preview_thread", None):
            try:
                self.PauseSignal.emit()
                self.StopSignal.emit()
            except Exception:
                pass

        if getattr(self, "preview_parent", None):
            background = getattr(self.preview_parent, "background", None)
            if background and background.isRunning():
                try:
                    background.finished.disconnect(self._on_preview_stopped)
                except Exception:
                    pass
                background.finished.connect(self._on_preview_stopped)
                try:
                    self.preview_parent.Stop(wait_for_thread=False)
                    return
                except Exception:
                    pass

            try:
                self.preview_parent.Stop(wait_for_thread=True)
            except Exception:
                pass

        self._on_preview_stopped()

    def reject(self):
        log.debug('reject')
        self.hide()
        self._shutdown_preview(close_dialog=True)

    def closeEvent(self, event):
        log.debug('closeEvent')
        event.ignore()
        self.reject()
