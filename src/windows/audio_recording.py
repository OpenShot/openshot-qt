"""
 @file
 @brief Audio recording dock controls.
 @author Jonathan Thomas <jonathan@openshot.org>

 @section LICENSE

 Copyright (c) 2008-2026 OpenShot Studios, LLC
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

import openshot
from qt_api import (
    Qt, pyqtSignal, pyqtSlot, QPointF,
    QWidget, QLabel, QPushButton, QComboBox, QApplication,
    QVBoxLayout, QHBoxLayout, QGridLayout, QSizePolicy, QIcon, QTimer,
    QPainter, QColor, QPen,
)

from classes import info
from classes.app import get_app
from classes.assets import get_assets_path
from classes.logger import log
from classes.query import File, Track


class RecordingLevelMeter(QWidget):
    """Compact input meter for the recording dock."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._peak = [0.0]
        self._rms = [0.0]
        self._clipped = False
        self.setMinimumHeight(34)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setFocusPolicy(Qt.NoFocus)

    def update_levels(self, peak=None, rms=None, clipped=False):
        self._peak = list(peak or [0.0])
        self._rms = list(rms or [0.0])
        self._clipped = bool(clipped)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)
        painter.fillRect(self.rect(), QColor(28, 30, 34))

        channels = max(1, len(self._peak), len(self._rms))
        gap = 4
        usable_h = max(1, self.height() - (channels + 1) * gap)
        bar_h = max(8, usable_h // channels)

        for channel in range(channels):
            y = gap + channel * (bar_h + gap)
            rect_w = self.width() - (2 * gap)
            painter.fillRect(gap, y, rect_w, bar_h, QColor(45, 48, 54))

            rms = self._rms[channel] if channel < len(self._rms) else 0.0
            peak = self._peak[channel] if channel < len(self._peak) else 0.0
            rms_w = int(max(0.0, min(1.0, rms)) * rect_w)
            peak_x = gap + int(max(0.0, min(1.0, peak)) * rect_w)

            if rms_w:
                color = QColor(45, 185, 90)
                if rms > 0.75:
                    color = QColor(220, 70, 60)
                elif rms > 0.55:
                    color = QColor(220, 190, 55)
                painter.fillRect(gap, y, rms_w, bar_h, color)

            painter.setPen(QPen(QColor(255, 235, 90), 2))
            painter.drawLine(peak_x, y, peak_x, y + bar_h)

        if self._clipped:
            painter.fillRect(0, 0, self.width(), 4, QColor(230, 45, 45))


class AudioRecordingDockContent(QWidget):
    """Compact dock for recording audio from an input device."""

    recordingStarted = pyqtSignal()
    recordingStopped = pyqtSignal(str)

    def __init__(self, window, parent=None):
        super().__init__(parent)
        self.window = window
        self._recording = False
        self._starting = False
        self._recording_started_at = 0.0
        self._context_start = None
        self._context_track = None
        self._recorder = None
        self._monitor_recorder = None
        self._recording_path = ""
        self._recorded_duration = 0.0
        self._recording_preview_id = ""
        self._recording_timeline_position = 0.0
        self._recording_preview_size = None
        self._last_timeline_preview_at = 0.0
        self._last_timeline_preview_samples = 0
        self._preferred_format = "flac"
        self._sample_rate = 48000
        self._channels = 1

        _ = get_app()._tr
        self.setFocusPolicy(Qt.NoFocus)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 8)
        layout.setSpacing(6)

        device_row = QHBoxLayout()
        device_label = QLabel(_("Input:"), self)
        self.device_combo = QComboBox(self)
        self.device_combo.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self.device_combo.setMinimumContentsLength(16)
        device_row.addWidget(device_label)
        device_row.addWidget(self.device_combo, 1)
        layout.addLayout(device_row)

        self.level_meter = RecordingLevelMeter(self)
        layout.addWidget(self.level_meter)

        target_row = QHBoxLayout()
        target_label = QLabel(_("Target:"), self)
        self.track_combo = QComboBox(self)
        self.track_combo.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        target_row.addWidget(target_label)
        target_row.addWidget(self.track_combo, 1)
        layout.addLayout(target_row)

        options_row = QHBoxLayout()
        self.advanced_button = QPushButton(_("Advanced"), self)
        self.advanced_button.setFlat(True)
        self.advanced_button.setCheckable(True)
        self.advanced_button.setCursor(Qt.PointingHandCursor)
        self.advanced_button.setStyleSheet(
            "QPushButton { color: #9EC8F7; border: none; padding: 2px 0; text-align: right; }"
            "QPushButton:hover { color: #CFE5FF; text-decoration: underline; }"
        )
        options_row.addStretch()
        options_row.addWidget(self.advanced_button)
        layout.addLayout(options_row)

        self.advanced_panel = QWidget(self)
        advanced_layout = QGridLayout(self.advanced_panel)
        advanced_layout.setContentsMargins(0, 0, 0, 0)
        advanced_layout.setHorizontalSpacing(8)
        advanced_layout.setVerticalSpacing(4)

        preview_label = QLabel(_("Preview:"), self.advanced_panel)
        preview_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.preview_combo = QComboBox(self.advanced_panel)
        self.preview_combo.addItem(_("No Preview"), "none")
        self.preview_combo.addItem(_("Timeline (full)"), "full")
        self.preview_combo.addItem(_("Timeline (50%)"), "half")
        self.preview_combo.addItem(_("Timeline (25%)"), "quarter")
        self.preview_combo.setCurrentIndex(self.preview_combo.findData("full"))
        advanced_layout.addWidget(preview_label, 0, 0)
        advanced_layout.addWidget(self.preview_combo, 0, 1)

        format_label = QLabel(_("Format:"), self.advanced_panel)
        format_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.format_combo = QComboBox(self.advanced_panel)
        for key, label in (("wav", "WAV"), ("flac", "FLAC"), ("mp3", "MP3")):
            self.format_combo.addItem(label, key)
        self.format_combo.setCurrentIndex(self.format_combo.findData(self._preferred_format))
        advanced_layout.addWidget(format_label, 1, 0)
        advanced_layout.addWidget(self.format_combo, 1, 1)

        sample_rate_label = QLabel(_("Sample Rate:"), self.advanced_panel)
        sample_rate_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.sample_rate_combo = QComboBox(self.advanced_panel)
        for rate in (44100, 48000, 96000):
            self.sample_rate_combo.addItem("%s Hz" % rate, rate)
        advanced_layout.addWidget(sample_rate_label, 2, 0)
        advanced_layout.addWidget(self.sample_rate_combo, 2, 1)

        channels_label = QLabel(_("Channels:"), self.advanced_panel)
        channels_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.channels_combo = QComboBox(self.advanced_panel)
        self.channels_combo.addItem(_("Mono"), 1)
        self.channels_combo.addItem(_("Stereo"), 2)
        advanced_layout.addWidget(channels_label, 3, 0)
        advanced_layout.addWidget(self.channels_combo, 3, 1)
        advanced_layout.setColumnStretch(1, 1)
        self.advanced_panel.hide()
        layout.addWidget(self.advanced_panel)

        control_row = QHBoxLayout()
        self.record_button = QPushButton(_("Start Recording"), self)
        self.record_button.setIcon(QIcon(os.path.join(info.PATH, "themes/cosmic/images/tool-microphone.svg")))
        self.record_button.setMinimumHeight(38)
        self.record_button.setStyleSheet("font-weight: 600;")
        self.timer_label = QLabel("00:00.0", self)
        self.timer_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        timer_font = self.timer_label.font()
        timer_font.setPointSize(max(timer_font.pointSize() + 2, 12))
        timer_font.setBold(True)
        self.timer_label.setFont(timer_font)
        self.timer_label.setMinimumWidth(86)
        control_row.addWidget(self.record_button, 1)
        control_row.addWidget(self.timer_label)
        layout.addLayout(control_row)

        layout.addStretch()

        self.timer = QTimer(self)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self._update_elapsed_time)
        self.poll_timer = QTimer(self)
        self.poll_timer.setInterval(50)
        self.poll_timer.timeout.connect(self._poll_recording_feedback)
        self.record_button.clicked.connect(self._toggle_recording)
        self.advanced_button.toggled.connect(self._toggle_advanced)
        self.format_combo.currentIndexChanged.connect(self._format_changed)
        self.sample_rate_combo.currentIndexChanged.connect(self._sample_rate_changed)
        self.channels_combo.currentIndexChanged.connect(self._channels_changed)
        self.device_combo.currentIndexChanged.connect(self._restart_monitoring)

        self.refresh_devices()
        self.refresh_tracks()
        self._sync_backend_state()

    def _backend_available(self):
        return all(hasattr(openshot, name) for name in (
            "AudioRecorder",
            "AudioRecorderSettings",
        ))

    def _sync_backend_state(self):
        _ = get_app()._tr
        if self._recording:
            self._set_record_button_recording()
            return
        if self._starting:
            self._set_record_button_starting()
            return
        available = self._backend_available()
        if available:
            self._set_record_button_idle()
        else:
            self._set_record_button_unavailable()

    def refresh_devices(self):
        _ = get_app()._tr
        current = self.device_combo.currentData()
        self.device_combo.blockSignals(True)
        self.device_combo.clear()
        self.device_combo.addItem(_("Default input"), ("", ""))
        try:
            audio_devices = openshot.AudioDevices()
            if hasattr(audio_devices, "getInputNames"):
                devices = audio_devices.getInputNames()
            else:
                devices = audio_devices.getNames()
            for name, device_type in devices:
                self.device_combo.addItem(str(name), (str(name), str(device_type)))
        except Exception as ex:
            log.debug("Unable to list audio input devices: %s", ex, exc_info=True)
        if current:
            for index in range(self.device_combo.count()):
                if self.device_combo.itemData(index) == current:
                    self.device_combo.setCurrentIndex(index)
                    break
        self.device_combo.blockSignals(False)

    def refresh_tracks(self):
        _ = get_app()._tr
        selected = self._context_track or self.track_combo.currentData()
        self.track_combo.blockSignals(True)
        self.track_combo.clear()
        self.track_combo.addItem(_("Auto"), None)
        try:
            labels = self._track_labels()
            tracks = sorted(Track.filter(), key=lambda t: int(t.data.get("number", 0)), reverse=True)
            for track in tracks:
                number = int(track.data.get("number", 0))
                label = labels.get(number, _("Track %s") % number)
                self.track_combo.addItem(str(label), number)
        except Exception as ex:
            log.debug("Unable to list timeline tracks for recording: %s", ex, exc_info=True)
        if selected is not None:
            for index in range(self.track_combo.count()):
                if self.track_combo.itemData(index) == selected:
                    self.track_combo.setCurrentIndex(index)
                    break
        self.track_combo.blockSignals(False)

    def set_recording_context(self, start_time=None, track_number=None):
        self._context_start = start_time
        self._context_track = track_number
        self.refresh_tracks()

    def _track_labels(self):
        _ = get_app()._tr
        labels = {}
        try:
            layers = list(get_app().project.get("layers") or [])
            display_count = len(layers)
            for track in reversed(sorted(layers, key=lambda layer: int(layer.get("number", 0)))):
                number = int(track.get("number", 0))
                labels[number] = str(track.get("label") or _("Track %s") % display_count)
                display_count -= 1
        except Exception:
            for track in sorted(Track.filter(), key=lambda t: int(t.data.get("number", 0)), reverse=True):
                number = int(track.data.get("number", 0))
                labels[number] = str(track.data.get("label") or _("Track %s") % number)
        return labels

    @pyqtSlot()
    def _toggle_recording(self):
        if self._recording:
            self.stop_recording()
        elif self._starting:
            return
        else:
            self.start_recording()

    def start_recording(self):
        _ = get_app()._tr
        if not self._backend_available():
            self._sync_backend_state()
            return
        if self._recording:
            return

        self._starting = True
        self._set_record_button_starting()
        self.timer_label.setText("00:00.0")
        QApplication.processEvents()

        self._set_wait_cursor(True)
        self._stop_monitoring()
        try:
            self._recording_timeline_position = self._context_start
            if self._recording_timeline_position is None:
                self._recording_timeline_position = self._current_playhead_seconds()
            self._context_start = self._recording_timeline_position
            settings = self._build_recorder_settings(recording=True)
            recorder = openshot.AudioRecorder(settings)
            recorder.Open()
            if hasattr(recorder, "PrepareRecording"):
                recorder.PrepareRecording()
            self._recorder = recorder
            self._begin_recording()
        except Exception as ex:
            self._recorder = None
            self._recording = False
            self._starting = False
            self._restore_recording_preview_scale()
            self._set_record_button_idle()
            self.record_button.setToolTip(_("Unable to prepare recording: %s") % ex)
            log.error("Unable to prepare audio recording", exc_info=True)
            self._ensure_monitoring()
            return
        finally:
            self._set_wait_cursor(False)

    def _cancel_starting(self, restart_monitoring=True):
        self._starting = False
        if self._recorder:
            try:
                self._recorder.Close()
            except Exception:
                log.debug("Unable to close prepared audio recorder", exc_info=True)
            self._recorder = None
        if self._recording_path and os.path.exists(self._recording_path):
            try:
                os.remove(self._recording_path)
            except OSError:
                log.debug("Unable to remove canceled recording file: %s", self._recording_path, exc_info=True)
        self._recording_path = ""
        self._restore_recording_preview_scale()
        self._set_record_button_idle()
        self.timer_label.setText("00:00.0")
        if restart_monitoring:
            self._ensure_monitoring()

    def _begin_recording(self):
        _ = get_app()._tr
        try:
            if self._should_preview_timeline() or self._playback_active():
                self._recording_timeline_position = self._current_playhead_seconds()
            self._context_start = self._recording_timeline_position
            recorder = self._recorder
            if recorder is None:
                settings = self._build_recorder_settings(recording=True)
                recorder = openshot.AudioRecorder(settings)
                recorder.Open()
                self._recorder = recorder
            self._apply_recording_preview_scale()
            recorder.Start()
        except Exception as ex:
            self._recorder = None
            self._recording = False
            self._starting = False
            self._restore_recording_preview_scale()
            self._set_record_button_idle()
            self.record_button.setToolTip(_("Unable to start recording: %s") % ex)
            log.error("Unable to start audio recording", exc_info=True)
            self._ensure_monitoring()
            return

        self._starting = False
        self._recorder = recorder
        self._recording = True
        self._recording_started_at = time.monotonic()
        if self._should_preview_timeline():
            self._start_timeline_playback()
        self._last_timeline_preview_at = 0.0
        self._last_timeline_preview_samples = 0
        self._recording_preview_id = "recording-preview-%d" % int(self._recording_started_at * 1000)
        self._set_record_button_recording()
        self.level_meter.update_levels()
        self._update_timeline_preview([], 0.05)
        self.timer.start()
        self.poll_timer.start()
        self.recordingStarted.emit()

    def stop_recording(self):
        _ = get_app()._tr
        if self._starting:
            self._cancel_starting()
            return
        if not self._recording and not self._recorder:
            return

        recorded_duration = max(0.0, time.monotonic() - self._recording_started_at)
        self._recording = False
        self.timer.stop()
        self.poll_timer.stop()
        self._poll_recording_feedback()
        self._set_record_button_stopping()
        QApplication.processEvents()

        path = self._recording_path
        try:
            if self._recorder:
                self._recorder.Stop()
                try:
                    stats = self._recorder.GetStats()
                    recorded_duration = max(recorded_duration, float(getattr(stats, "duration", 0.0) or 0.0))
                except Exception:
                    log.debug("Unable to read audio recorder duration", exc_info=True)
                self._recorder.Close()
        except Exception as ex:
            self.record_button.setToolTip(_("Unable to finish recording: %s") % ex)
            log.error("Unable to finish audio recording", exc_info=True)
            path = ""
        finally:
            self._recorder = None
            self._recorded_duration = recorded_duration

        self._restore_recording_preview_scale()
        if path and os.path.exists(path):
            self._set_record_button_saving()
            QApplication.processEvents()
            self._import_recording(path)
            self._clear_timeline_preview()
        else:
            self._clear_timeline_preview()
        self._set_record_button_idle()
        self._ensure_monitoring()
        self.recordingStopped.emit(path or "")

    def _build_recorder_settings(self, recording=False):
        settings = openshot.AudioRecorderSettings()
        device_name, device_type = self.device_combo.currentData() or ("", "")
        path = self._next_recording_path() if recording else os.path.join(info.USER_PATH, "recording-monitor.wav")

        settings.path = path
        settings.device_name = device_name or ""
        settings.device_type = device_type or ""
        settings.sample_rate = int(self._sample_rate)
        settings.channels = int(self._channels)
        settings.channel_layout = openshot.LAYOUT_MONO if self._channels == 1 else openshot.LAYOUT_STEREO
        settings.bit_rate = 192000 if self._preferred_format != "mp3" else 160000
        settings.buffer_size = 512
        settings.waveform_samples_per_second = 20
        settings.max_queue_seconds = 10
        settings.codec = {
            "wav": "pcm_s16le",
            "flac": "flac",
            "mp3": "libmp3lame",
        }.get(self._preferred_format, "pcm_s16le")

        if recording:
            self._recording_path = path
        return settings

    def _next_recording_path(self):
        project_path = getattr(get_app().project, "current_filepath", None)
        assets_path = get_assets_path(project_path)
        recordings_path = os.path.join(assets_path or info.USER_PATH, "recordings")
        os.makedirs(recordings_path, exist_ok=True)

        timestamp = time.strftime("%Y%m%d-%H%M%S")
        extension = self._preferred_format or "wav"
        base = os.path.join(recordings_path, "Recording-%s.%s" % (timestamp, extension))
        if not os.path.exists(base):
            return base
        for index in range(2, 1000):
            candidate = os.path.join(
                recordings_path,
                "Recording-%s-%03d.%s" % (timestamp, index, extension),
            )
            if not os.path.exists(candidate):
                return candidate
        return base

    def _poll_recording_feedback(self):
        recorder = self._recorder or self._monitor_recorder
        if not recorder:
            return
        try:
            level = recorder.GetLevelSnapshot()
            level_vectors = level.vectors()
            peak = list(level_vectors[0]) if len(level_vectors) > 0 else []
            rms = list(level_vectors[1]) if len(level_vectors) > 1 else []
            clipped = bool(level.clipped)
            self.level_meter.update_levels(peak, rms, clipped)

            if not self._recording:
                return

            waveform = recorder.GetWaveformSnapshot()
            waveform_vectors = waveform.vectors()
            samples = list(waveform_vectors[0]) if len(waveform_vectors) > 0 else []
            self._update_timeline_preview_throttled(samples)
        except Exception:
            log.debug("Unable to poll audio recording feedback", exc_info=True)

    def _update_timeline_preview_throttled(self, samples):
        now = time.monotonic()
        sample_count = len(samples or [])
        duration = max(0.0, now - self._recording_started_at)
        if (
            sample_count == self._last_timeline_preview_samples
            and duration < 0.25
        ):
            return
        if (
            now - self._last_timeline_preview_at < 0.2
            and sample_count - self._last_timeline_preview_samples < 4
        ):
            return

        self._last_timeline_preview_at = now
        self._last_timeline_preview_samples = sample_count
        self._update_timeline_preview(samples, duration)

    def _update_timeline_preview(self, samples, duration):
        timeline = getattr(self.window, "timeline", None)
        if not timeline or not hasattr(timeline, "set_audio_recording_preview"):
            return
        track = self.track_combo.currentData()
        if track is None:
            track = self._context_track or 1
        position = self._context_start
        if position is None:
            position = self._recording_timeline_position
        timeline.set_audio_recording_preview(
            self._recording_preview_id,
            float(position or 0.0),
            int(track or 1),
            duration,
            samples,
        )

    def _clear_timeline_preview(self):
        timeline = getattr(self.window, "timeline", None)
        if timeline and hasattr(timeline, "clear_audio_recording_preview"):
            timeline.clear_audio_recording_preview()

    def _import_recording(self, path):
        try:
            self.window.files_model.add_files(
                path,
                quiet=True,
                prevent_image_seq=True,
                prevent_recent_folder=True,
            )
            self._apply_recording_duration(path)
            self.window.refreshFilesSignal.emit()
            self._add_recording_to_timeline(path)
        except Exception:
            log.error("Unable to import recorded audio file: %s", path, exc_info=True)

    def _apply_recording_duration(self, path):
        recorded_file = File.get(path=path)
        duration = float(self._recorded_duration or 0.0)
        if not recorded_file or duration <= 0.0:
            return
        try:
            if float(recorded_file.data.get("duration", 0.0) or 0.0) > 0.0:
                return
        except (TypeError, ValueError):
            pass

        try:
            fps = get_app().project.get("fps")
            fps_float = float(fps["num"]) / float(fps["den"])
        except Exception:
            fps_float = 30.0

        duration_frames = max(1, int(round(duration * fps_float)))
        snapped_duration = duration_frames / fps_float
        recorded_file.data["duration"] = snapped_duration
        recorded_file.data["start"] = 0.0
        recorded_file.data["end"] = snapped_duration
        recorded_file.data["video_length"] = duration_frames
        recorded_file.data["has_audio"] = True
        recorded_file.data["has_video"] = False
        recorded_file.data["media_type"] = "audio"
        recorded_file.save()

    def _add_recording_to_timeline(self, path):
        timeline = getattr(self.window, "timeline", None)
        if not timeline:
            return

        recorded_file = File.get(path=path)
        if not recorded_file:
            return

        position = self._context_start
        if position is None:
            position = self._recording_timeline_position

        track = self.track_combo.currentData()
        if track is None:
            track = self._context_track or 1

        new_clip = timeline.addClip(
            recorded_file.id,
            QPointF(float(position or 0.0), float(track)),
            int(track),
            ignore_refresh=False,
            call_manual_move=False,
        )
        self._select_recording_clip(new_clip, float(position or 0.0))

    def _select_recording_clip(self, clip_data, position):
        clip_id = clip_data.get("id") if isinstance(clip_data, dict) else None
        if clip_id and hasattr(self.window, "addSelection"):
            self.window.addSelection(clip_id, "clip", clear_existing=True)

        try:
            fps = get_app().project.get("fps")
            fps_float = float(fps["num"]) / float(fps["den"])
            frame_number = max(1, int(round(position * fps_float)) + 1)
            self.window.SeekSignal.emit(frame_number, True)
        except Exception:
            log.debug("Unable to seek to recorded audio clip start", exc_info=True)

    def _current_playhead_seconds(self):
        try:
            return float(self.window._current_timeline_seconds())
        except Exception:
            return 0.0

    def _playback_active(self):
        try:
            player = self.window.preview_thread.player
            return player.Mode() == openshot.PLAYBACK_PLAY and player.Speed() != 0
        except Exception:
            return False

    def _start_timeline_playback(self):
        if self._playback_active():
            return
        if hasattr(self.window, "actionPlay_trigger"):
            self.window.actionPlay_trigger()
        else:
            self.window.PlaySignal.emit()

    def _update_elapsed_time(self):
        elapsed = max(0.0, time.monotonic() - self._recording_started_at)
        minutes = int(elapsed // 60)
        seconds = elapsed - (minutes * 60)
        self.timer_label.setText("%02d:%04.1f" % (minutes, seconds))

    def _toggle_advanced(self, checked):
        self.advanced_panel.setVisible(bool(checked))

    def _set_record_button_idle(self):
        self.record_button.setEnabled(True)
        self.record_button.setText(get_app()._tr("Start Recording"))
        self.record_button.setStyleSheet("font-weight: 600;")
        self.record_button.setToolTip("")

    def _set_record_button_unavailable(self):
        self.record_button.setEnabled(False)
        self.record_button.setText(get_app()._tr("Unavailable"))
        self.record_button.setStyleSheet("font-weight: 600;")
        self.record_button.setToolTip("")

    def _set_record_button_starting(self):
        self.record_button.setEnabled(False)
        self.record_button.setText(get_app()._tr("Starting..."))
        self.record_button.setStyleSheet("font-weight: 600;")
        self.record_button.setToolTip("")

    def _set_record_button_stopping(self):
        self.record_button.setEnabled(False)
        self.record_button.setText(get_app()._tr("Stopping..."))
        self.record_button.setStyleSheet(
            "QPushButton { background-color: #8F2D2D; color: white; font-weight: 700; }"
        )
        self.record_button.setToolTip("")

    def _set_record_button_saving(self):
        self.record_button.setEnabled(False)
        self.record_button.setText(get_app()._tr("Saving..."))
        self.record_button.setStyleSheet("font-weight: 600;")
        self.record_button.setToolTip("")

    def _set_record_button_recording(self):
        self.record_button.setEnabled(True)
        self.record_button.setText(get_app()._tr("Stop Recording"))
        self.record_button.setStyleSheet(
            "QPushButton { background-color: #B83232; color: white; font-weight: 700; }"
            "QPushButton:hover { background-color: #C93A3A; }"
            "QPushButton:pressed { background-color: #972626; }"
        )
        self.record_button.setToolTip("")

    def _format_changed(self):
        self._set_format(self.format_combo.currentData() or "wav")

    def _sample_rate_changed(self):
        self._set_sample_rate(self.sample_rate_combo.currentData() or 48000)

    def _channels_changed(self):
        self._set_channels(self.channels_combo.currentData() or 1)

    def _set_format(self, value):
        self._preferred_format = value

    def _set_sample_rate(self, value):
        self._sample_rate = int(value)
        self._restart_monitoring()

    def _set_channels(self, value):
        self._channels = int(value)
        self._restart_monitoring()

    def _ensure_monitoring(self):
        if self._recording or self._starting or not self.isVisible() or not self._backend_available():
            return
        if self._monitor_recorder:
            return
        self._set_wait_cursor(True)
        try:
            settings = self._build_recorder_settings(recording=False)
            recorder = openshot.AudioRecorder(settings)
            recorder.Open()
            if hasattr(recorder, "StartMonitoring"):
                recorder.StartMonitoring()
            else:
                recorder.Close()
                return
            self._monitor_recorder = recorder
            if not self.poll_timer.isActive():
                self.poll_timer.start()
        except Exception as ex:
            self._monitor_recorder = None
            self.record_button.setToolTip(get_app()._tr("Unable to monitor input: %s") % ex)
            log.debug("Unable to monitor audio input", exc_info=True)
        finally:
            self._set_wait_cursor(False)

    def _stop_monitoring(self):
        recorder = self._monitor_recorder
        self._monitor_recorder = None
        if recorder:
            try:
                if hasattr(recorder, "StopMonitoring"):
                    recorder.StopMonitoring()
                recorder.Close()
            except Exception:
                log.debug("Unable to stop audio input monitoring", exc_info=True)
        if not self._recording and not self._starting:
            self.poll_timer.stop()

    def _restart_monitoring(self):
        if self._recording or self._starting:
            return
        self._stop_monitoring()
        self._ensure_monitoring()

    def _should_preview_timeline(self):
        return self.preview_combo.currentData() != "none"

    def _preview_scale(self):
        return {
            "half": 0.5,
            "quarter": 0.25,
        }.get(self.preview_combo.currentData(), 1.0)

    def _apply_recording_preview_scale(self):
        if not self._should_preview_timeline():
            return
        scale = self._preview_scale()
        if scale >= 1.0:
            return
        try:
            timeline = self.window.timeline_sync.timeline
            current_width = int(getattr(timeline, "preview_width", 0) or 0)
            current_height = int(getattr(timeline, "preview_height", 0) or 0)
            if current_width <= 0 or current_height <= 0:
                viewport = self.window.videoPreview.centeredViewport(
                    self.window.videoPreview.width(),
                    self.window.videoPreview.height(),
                )
                current_width = int(viewport.width())
                current_height = int(viewport.height())
            if current_width <= 0 or current_height <= 0:
                return

            self._recording_preview_size = (current_width, current_height)
            scaled_width = max(16, int(round(current_width * scale)))
            scaled_height = max(16, int(round(current_height * scale)))
            timeline.SetMaxSize(scaled_width, scaled_height)
            timeline.ClearAllCache(True)
            self.window.refreshFrameSignal.emit()
        except Exception:
            self._recording_preview_size = None
            log.debug("Unable to reduce recording preview resolution", exc_info=True)

    def _restore_recording_preview_scale(self):
        if not self._recording_preview_size:
            return
        try:
            width, height = self._recording_preview_size
            timeline = self.window.timeline_sync.timeline
            timeline.SetMaxSize(int(width), int(height))
            timeline.ClearAllCache(True)
            self.window.refreshFrameSignal.emit()
        except Exception:
            log.debug("Unable to restore recording preview resolution", exc_info=True)
        finally:
            self._recording_preview_size = None

    def _set_wait_cursor(self, enabled):
        try:
            self.window.WaitCursorSignal.emit(bool(enabled))
            QApplication.processEvents()
        except Exception:
            pass

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh_devices()
        self.refresh_tracks()
        self._sync_backend_state()
        self._ensure_monitoring()

    def hideEvent(self, event):
        if not self._recording:
            if self._starting:
                self._cancel_starting(restart_monitoring=False)
            self._stop_monitoring()
        super().hideEvent(event)
