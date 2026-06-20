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
import glob
import json
import re
import shutil
import subprocess
import sys
import threading
import time

import openshot
from qt_api import (
    Qt, QObject, pyqtSignal, pyqtSlot, QPointF,
    QWidget, QLabel, QPushButton, QComboBox, QApplication,
    QVBoxLayout, QHBoxLayout, QGridLayout, QSizePolicy, QIcon, QTimer,
    QPainter, QColor, QPen, QSpinBox, QLineEdit, QImage, QPixmap, QButtonGroup,
    QScrollArea, QPainterPath,
)

from classes import info
from classes.app import get_app
from classes.assets import get_assets_path
from classes.logger import log
from classes.query import Clip, File, Track
from classes.thumbnail import (
    RoundFrameToThumbnailGrid,
    ThumbnailPathForFrame,
)
from classes.tray_status import TrayStatus
from windows.models.files_model import inspect_media
from windows.recording_widgets import (
    RecordingSourceCard, RecordingSection, SegmentButton,
    pick_screen_region, pick_screen_window, screen_root_geometry, screen_root_size,
)


def frame_to_qimage(frame):
    """Copy a libopenshot RGBA frame into a Qt image for preview signals."""
    width = int(frame.GetWidth())
    height = int(frame.GetHeight())
    bytes_per_line = int(frame.GetBytesPerLine())
    pixels = frame.GetPixelsBytes()
    if not pixels or width <= 0 or height <= 0 or bytes_per_line <= 0:
        return None
    return QImage(
        pixels,
        width,
        height,
        bytes_per_line,
        QImage.Format_RGBA8888_Premultiplied,
    ).copy()


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


def recording_preview_file_id(session_id, source_type):
    """Return a stable temporary file ID for live recording previews."""
    safe_source = re.sub(r"[^A-Za-z0-9_-]+", "-", str(source_type or "source")).strip("-")
    return "recording-preview-%s-%s" % (session_id, safe_source or "source")


def screen_capture_backend():
    """Return the libopenshot screen backend best suited for the current session."""
    auto_backend = getattr(openshot, "SCREEN_CAPTURE_AUTO", None)
    default_backend = getattr(getattr(openshot, "ScreenCaptureReader", None), "DefaultBackend", None)
    if callable(default_backend):
        try:
            return default_backend()
        except Exception:
            log.debug("Unable to query default screen capture backend", exc_info=True)

    session = os.environ.get("XDG_SESSION_TYPE", "x11").lower()
    if session == "wayland" and hasattr(openshot, "SCREEN_CAPTURE_WAYLAND"):
        return openshot.SCREEN_CAPTURE_WAYLAND
    if sys.platform.startswith("win") and hasattr(openshot, "SCREEN_CAPTURE_WINDOWS_GDI"):
        return openshot.SCREEN_CAPTURE_WINDOWS_GDI
    if hasattr(openshot, "SCREEN_CAPTURE_X11"):
        return openshot.SCREEN_CAPTURE_X11
    return auto_backend


def screen_capture_backend_supported(backend=None):
    """Return whether libopenshot exposes and supports the selected screen backend."""
    if not all(hasattr(openshot, name) for name in ("ScreenCaptureReader", "ScreenCaptureSettings")):
        return False

    selected_backend = screen_capture_backend() if backend is None else backend
    if selected_backend == getattr(openshot, "SCREEN_CAPTURE_AUTO", object()):
        return False
    is_supported = getattr(openshot.ScreenCaptureReader, "IsBackendSupported", None)
    if callable(is_supported) and selected_backend is not None:
        try:
            return bool(is_supported(selected_backend))
        except Exception:
            log.debug("Unable to query screen capture backend support", exc_info=True)

    session = os.environ.get("XDG_SESSION_TYPE", "x11").lower()
    if session == "wayland":
        return False
    if sys.platform.startswith("win"):
        return selected_backend == getattr(openshot, "SCREEN_CAPTURE_WINDOWS_GDI", object())
    return selected_backend == getattr(openshot, "SCREEN_CAPTURE_X11", object())


def screen_capture_backend_is_wayland(backend=None):
    selected_backend = screen_capture_backend() if backend is None else backend
    return selected_backend == getattr(openshot, "SCREEN_CAPTURE_WAYLAND", object())


def screen_capture_backend_is_windows(backend=None):
    selected_backend = screen_capture_backend() if backend is None else backend
    return selected_backend == getattr(openshot, "SCREEN_CAPTURE_WINDOWS_GDI", object())


def camera_capture_backend():
    default_backend = getattr(getattr(openshot, "CameraCaptureReader", None), "DefaultBackend", None)
    if callable(default_backend):
        try:
            return default_backend()
        except Exception:
            log.debug("Unable to query default camera capture backend", exc_info=True)
    if sys.platform.startswith("win") and hasattr(openshot, "CAMERA_CAPTURE_WINDOWS_DSHOW"):
        return openshot.CAMERA_CAPTURE_WINDOWS_DSHOW
    if hasattr(openshot, "CAMERA_CAPTURE_V4L2"):
        return openshot.CAMERA_CAPTURE_V4L2
    return getattr(openshot, "CAMERA_CAPTURE_AUTO", None)


def camera_capture_backend_is_windows(backend=None):
    selected_backend = camera_capture_backend() if backend is None else backend
    return selected_backend == getattr(openshot, "CAMERA_CAPTURE_WINDOWS_DSHOW", object())


class LiveRecordingThumbnailCache:
    """Save coarse thumbnail-grid frames while a live video recording is written."""

    def __init__(self, file_id, fps, width=None, height=None, thumb_size=None):
        self.file_id = str(file_id or "")
        self.fps = float(fps or 0.0)
        self.saved_frames = set()
        if thumb_size is None:
            thumb_size = info.LIST_ICON_SIZE
        self.thumb_width = int(thumb_size.width())
        self.thumb_height = int(thumb_size.height())

    def thumbnail_frame_for_output_frame(self, frame_number):
        """Return the canonical thumbnail frame to save, or 0 if this frame is skipped."""
        if not self.file_id:
            return 0
        frame_number = max(1, int(frame_number or 1))
        thumbnail_frame = RoundFrameToThumbnailGrid(frame_number, self.fps)
        return thumbnail_frame if thumbnail_frame == frame_number else 0

    def save_frame(self, frame, frame_number):
        thumbnail_frame = self.thumbnail_frame_for_output_frame(frame_number)
        if not thumbnail_frame or thumbnail_frame in self.saved_frames:
            return ThumbnailPathForFrame(self.file_id, thumbnail_frame) if thumbnail_frame else ""
        thumb_path = ThumbnailPathForFrame(self.file_id, thumbnail_frame)
        if os.path.exists(thumb_path):
            self.saved_frames.add(thumbnail_frame)
            return thumb_path
        try:
            self._save_thumbnail_from_frame(frame, thumb_path)
            self.saved_frames.add(thumbnail_frame)
            return thumb_path
        except Exception:
            log.debug(
                "Unable to save live recording thumbnail file_id=%s frame=%s",
                self.file_id,
                thumbnail_frame,
                exc_info=True,
            )
        return ""

    def _save_thumbnail_from_frame(self, frame, thumb_path):
        image = frame_to_qimage(frame)
        if image is None or image.isNull():
            return False

        os.makedirs(os.path.dirname(thumb_path), exist_ok=True)
        scaled = image.scaled(
            self.thumb_width,
            self.thumb_height,
            Qt.KeepAspectRatioByExpanding,
            Qt.SmoothTransformation,
        )
        if scaled.width() > self.thumb_width or scaled.height() > self.thumb_height:
            x = max(0, int((scaled.width() - self.thumb_width) / 2))
            y = max(0, int((scaled.height() - self.thumb_height) / 2))
            scaled = scaled.copy(x, y, self.thumb_width, self.thumb_height)
        if not scaled.save(thumb_path, "PNG"):
            raise IOError("Unable to save thumbnail: %s" % thumb_path)
        return True

    def copy_to_file_id(self, final_file_id):
        """Copy live thumbnails to the final imported File ID folder."""
        final_file_id = str(final_file_id or "")
        if not self.file_id or not final_file_id or self.file_id == final_file_id:
            return 0
        source_dir = os.path.dirname(ThumbnailPathForFrame(self.file_id, 1))
        target_dir = os.path.dirname(ThumbnailPathForFrame(final_file_id, 1))
        if not os.path.isdir(source_dir):
            return 0
        copied = 0
        os.makedirs(target_dir, exist_ok=True)
        for filename in os.listdir(source_dir):
            if not filename.lower().endswith(".png"):
                continue
            source_path = os.path.join(source_dir, filename)
            target_path = os.path.join(target_dir, filename)
            if not os.path.isfile(source_path):
                continue
            try:
                shutil.copy2(source_path, target_path)
                copied += 1
            except OSError:
                log.debug("Unable to copy live thumbnail: %s", source_path, exc_info=True)
        return copied


class LiveVideoRecordingJob(QObject):
    """Small background writer for live libopenshot video capture readers."""

    errorOccurred = pyqtSignal(str, str)
    finished = pyqtSignal(str)
    previewFrameReady = pyqtSignal(object)

    def __init__(self, reader, path, width, height, fps, codec="libx264", bit_rate=4000000,
                 source_type="video", use_reader_fps=True, preview_file_id=""):
        super().__init__()
        self.reader = reader
        self.path = path
        self.source_type = source_type
        self.width = int(width)
        self.height = int(height)
        self.fps = fps
        self.codec = codec
        self.bit_rate = int(bit_rate)
        self.error = None
        self.frames = 0
        self.use_reader_fps = bool(use_reader_fps)
        self.preview_file_id = str(preview_file_id or "")
        self.thumbnail_cache = None
        self._writer = None
        self._thread = None
        self._stop = threading.Event()
        self._writer_lock = threading.Lock()
        self._recording_started = threading.Event()
        self._start_time = 0.0
        self._initial_frame = None
        self._last_frame = None
        self._last_output_frame_number = 0
        self._opened = threading.Event()

    def start(self):
        self._open()
        self._thread = threading.Thread(target=self._run, name="OpenShotLiveVideoRecording", daemon=True)
        self._thread.start()

    def start_async(self):
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._open_and_run, name="OpenShotLiveVideoRecording", daemon=True)
        self._thread.start()

    def _open_and_run(self):
        try:
            self._open()
            if not self._stop.is_set():
                self._run()
        except Exception as ex:
            if not self._stop.is_set():
                self.error = ex
                self.errorOccurred.emit(self.source_type, str(ex))

    def _open(self):
        self.reader.Open()
        self._initial_frame = self.reader.GetFrame(1)
        frame_width = int(self._initial_frame.GetWidth() or 0)
        frame_height = int(self._initial_frame.GetHeight() or 0)
        actual_width = int(getattr(getattr(self.reader, "info", None), "width", 0) or 0)
        actual_height = int(getattr(getattr(self.reader, "info", None), "height", 0) or 0)
        if frame_width > 0 and frame_height > 0:
            self.width = self._safe_even_dimension(frame_width)
            self.height = self._safe_even_dimension(frame_height)
        elif actual_width > 0 and actual_height > 0:
            self.width = self._safe_even_dimension(actual_width)
            self.height = self._safe_even_dimension(actual_height)
        actual_fps = getattr(getattr(self.reader, "info", None), "fps", None)
        if self.use_reader_fps and actual_fps and getattr(actual_fps, "num", 0) > 0 and getattr(actual_fps, "den", 0) > 0:
            self.fps = actual_fps
        log.info(
            "Live %s capture opened: width=%s height=%s fps=%s/%s",
            self.source_type, self.width, self.height,
            self.fps.num, self.fps.den,
        )
        fps_value = max(1.0, float(self.fps.num) / float(self.fps.den or 1))
        if self.preview_file_id:
            self.thumbnail_cache = LiveRecordingThumbnailCache(
                self.preview_file_id,
                fps_value,
                self.width,
                self.height,
            )
        self._writer = openshot.FFmpegWriter(self.path)
        self._writer.SetVideoOptions(
            True,
            self.codec,
            self.fps,
            self.width,
            self.height,
            openshot.Fraction(1, 1),
            False,
            False,
            self.bit_rate,
        )
        self._writer.Open()
        self._opened.set()

    def wait_until_opened(self):
        while not self._opened.is_set() and not self.error and not self._stop.is_set():
            QApplication.processEvents()
            time.sleep(0.02)
        if self.error:
            raise self.error

    def begin(self, start_time=None):
        self._start_time = float(start_time or time.monotonic())
        self._recording_started.set()

    def _run(self):
        while not self._recording_started.is_set() and not self._stop.is_set():
            time.sleep(0.01)
        if self._stop.is_set():
            return
        capture_frame_number = 2 if self._initial_frame is not None else 1
        written_frames = 0
        last_output_frame_number = 0
        last_preview_emit = 0.0
        fps_value = max(1.0, float(self.fps.num) / float(self.fps.den or 1))
        try:
            while not self._stop.is_set():
                if self._initial_frame is not None:
                    frame = self._initial_frame
                    self._initial_frame = None
                else:
                    frame = self.reader.GetFrame(capture_frame_number)
                now = time.monotonic()
                elapsed = max(0.0, now - float(self._start_time or now))
                output_frame_number = max(1, int(round(elapsed * fps_value)) + 1)
                output_frame_number = max(output_frame_number, last_output_frame_number + 1)
                with self._writer_lock:
                    if not self._writer:
                        break
                    self._write_gap_frames(last_output_frame_number, output_frame_number)
                    self._write_numbered_frame(frame, output_frame_number)
                written_frames += 1
                if self.thumbnail_cache:
                    self.thumbnail_cache.save_frame(frame, output_frame_number)
                if self.source_type == "webcam":
                    if now - last_preview_emit >= 0.2:
                        image = frame_to_qimage(frame)
                        if image:
                            self.previewFrameReady.emit(image)
                        last_preview_emit = now
                last_output_frame_number = output_frame_number
                self.frames = output_frame_number
                self._last_output_frame_number = output_frame_number
                self._last_frame = self._copy_frame(frame)
                capture_frame_number += 1
        except Exception as ex:
            if not self._stop.is_set():
                self.error = ex
                self.errorOccurred.emit(self.source_type, str(ex))

    def stop(self):
        self._stop.set()
        self._recording_started.set()
        if self._thread:
            self._thread.join(timeout=2.0)
        if self._thread and self._thread.is_alive():
            try:
                self.reader.Close()
            except Exception:
                log.debug("Unable to close live video capture reader", exc_info=True)
            self._thread.join(timeout=5.0)
        else:
            try:
                self.reader.Close()
            except Exception:
                log.debug("Unable to close live video capture reader", exc_info=True)
        if self._thread and self._thread.is_alive():
            log.warning("Live video capture thread did not stop cleanly for %s", self.path)
            if not self.error:
                self.error = RuntimeError("Live video capture did not stop cleanly")
                self.errorOccurred.emit(self.source_type, str(self.error))
            return
        try:
            with self._writer_lock:
                if self._writer:
                    self._write_final_gap_frame()
                    self._writer.Close()
                    self._writer = None
        except Exception as ex:
            if not self.error:
                self.error = ex
                self.errorOccurred.emit(self.source_type, str(ex))
        self.finished.emit(self.path)

    def _write_final_gap_frame(self):
        if not self._writer or not self._last_frame or not self._start_time:
            return
        fps_value = max(1.0, float(self.fps.num) / float(self.fps.den or 1))
        elapsed = max(0.0, time.monotonic() - float(self._start_time))
        final_frame_number = max(1, int(round(elapsed * fps_value)) + 1)
        if final_frame_number <= self._last_output_frame_number + 1:
            return
        frame = self._copy_frame(self._last_frame)
        self._write_gap_frames(self._last_output_frame_number, final_frame_number)
        self._write_numbered_frame(frame, final_frame_number)
        self.frames = final_frame_number
        self._last_output_frame_number = final_frame_number

    def _write_gap_frames(self, last_frame_number, next_frame_number):
        if not self._writer or not self._last_frame:
            return
        for frame_number in range(int(last_frame_number) + 1, int(next_frame_number)):
            self._write_numbered_frame(self._last_frame, frame_number)

    def _write_numbered_frame(self, frame, frame_number):
        if not self._writer or frame is None:
            return
        frame_to_write = self._copy_frame(frame)
        if hasattr(frame_to_write, "SetFrameNumber"):
            frame_to_write.SetFrameNumber(frame_number)
        self._writer.WriteFrame(frame_to_write)

    def _copy_frame(self, frame):
        if frame is None:
            return None
        try:
            copied = openshot.Frame()
            copied.DeepCopy(frame)
            return copied
        except Exception:
            log.debug("Unable to deep copy live video frame", exc_info=True)
        return frame

    @staticmethod
    def _safe_even_dimension(value):
        value = max(16, int(value))
        return value if value % 2 == 0 else value - 1


class WebcamPreviewJob(QObject):
    frameReady = pyqtSignal(object)
    errorOccurred = pyqtSignal(str)

    def __init__(self, device, width, height, backend=None, parent=None):
        super().__init__(parent)
        self.device = device
        self.width = int(width)
        self.height = int(height)
        self.backend = backend if backend is not None else camera_capture_backend()
        self._reader = None
        self._thread = None
        self._stop = threading.Event()

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="OpenShotWebcamPreview", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)
        if self._thread and self._thread.is_alive():
            log.debug("Webcam preview thread did not stop cleanly")
            return
        if self._reader:
            try:
                self._reader.Close()
            except Exception:
                log.debug("Unable to close webcam preview reader", exc_info=True)

    def _run(self):
        try:
            settings = openshot.CameraCaptureSettings()
            settings.backend = self.backend
            settings.device = self.device
            settings.width = self.width
            settings.height = self.height
            settings.fps = openshot.Fraction(5, 1)
            self._reader = openshot.CameraCaptureReader(settings)
            self._reader.Open()
            frame_number = 1
            last_emit = 0.0
            while not self._stop.is_set():
                frame = self._reader.GetFrame(frame_number)
                now = time.monotonic()
                if now - last_emit >= 0.2:
                    image = frame_to_qimage(frame)
                    if image:
                        self.frameReady.emit(image)
                    last_emit = now
                frame_number += 1
        except Exception as ex:
            if not self._stop.is_set():
                self.errorOccurred.emit(str(ex))
        finally:
            if self._reader:
                try:
                    self._reader.Close()
                except Exception:
                    pass
            self._reader = None

class AudioRecordingDockContent(QWidget):
    """Compact dock for recording audio, screen, and webcam sources."""

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
        self._video_jobs = []
        self._webcam_preview = None
        self._webcam_preview_pixmap = None
        self._tray_status = TrayStatus(self)
        self._camera_modes = {}
        self._camera_mode_formats = {}
        self._recording_path = ""
        self._recording_sources = []
        self._recorded_duration = 0.0
        self._audio_channel_support_cache = {}
        self._activation_pending = False
        self._recording_hidden_window_state = None
        self._hiding_openshot_window = False
        self._hide_openshot_user_set = False
        self._screen_window_id = ""
        self._recording_preview_id = ""
        self._recording_preview_file_ids = {}
        self._recording_track_map = {}
        self._recording_timeline_position = 0.0
        self._recording_preview_size = None
        self._recording_waveform_samples = []
        self._last_timeline_preview_at = 0.0
        self._last_timeline_preview_samples = 0
        self._preferred_format = "flac"
        self._sample_rate = 48000
        self._channels = 1

        _ = get_app()._tr
        self.setFocusPolicy(Qt.NoFocus)

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setFrameShape(QScrollArea.NoFrame)
        self.scroll_area.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        outer_layout.addWidget(self.scroll_area)

        self.scroll_content = QWidget()
        self.scroll_area.setWidget(self.scroll_content)
        layout = QVBoxLayout(self.scroll_content)
        layout.setContentsMargins(10, 8, 10, 10)
        layout.setSpacing(8)

        source_grid = QGridLayout()
        source_grid.setHorizontalSpacing(8)
        self.mic_card = RecordingSourceCard(_("Mic"), _("Record your voice"), "🎙", self)
        self.screen_card = RecordingSourceCard(_("Screen"), _("Capture your screen"), "▣", self)
        self.camera_card = RecordingSourceCard(_("Webcam"), _("Record yourself"), "◉", self)
        self.mic_card.setChecked(True)
        source_grid.addWidget(self.mic_card, 0, 0)
        source_grid.addWidget(self.screen_card, 0, 1)
        source_grid.addWidget(self.camera_card, 0, 2)
        layout.addLayout(source_grid)

        self.mic_section = RecordingSection(_("Mic"), "🎙", self)
        self.level_meter = RecordingLevelMeter(self.mic_section)
        mic_input_row = QHBoxLayout()
        mic_input_row.setContentsMargins(0, 0, 0, 0)
        mic_input_row.setSpacing(8)
        self.mono_button = SegmentButton(_("Mono"), self.mic_section)
        self.stereo_button = SegmentButton(_("Stereo"), self.mic_section)
        self.mono_button.setProperty("position", "left")
        self.stereo_button.setProperty("position", "right")
        self.mono_button.setChecked(True)
        self.channel_button_group = QButtonGroup(self.mic_section)
        self.channel_button_group.setExclusive(True)
        self.channel_button_group.addButton(self.mono_button, 1)
        self.channel_button_group.addButton(self.stereo_button, 2)
        channel_strip = QWidget(self.mic_section)
        channel_strip_layout = QHBoxLayout(channel_strip)
        channel_strip_layout.setContentsMargins(0, 0, 0, 0)
        channel_strip_layout.setSpacing(0)
        channel_strip_layout.addWidget(self.mono_button)
        channel_strip_layout.addWidget(self.stereo_button)
        mic_input_row.addWidget(self.level_meter, 1)
        mic_input_row.addWidget(channel_strip)
        self.mic_section.body_layout.addLayout(mic_input_row)

        self.device_combo = QComboBox(self.mic_section)
        self.device_combo.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self.device_combo.setMinimumContentsLength(16)
        self.format_combo = QComboBox(self.mic_section)
        for key, label in (("wav", "WAV"), ("flac", "FLAC"), ("mp3", "MP3")):
            self.format_combo.addItem(label, key)
        self.format_combo.setCurrentIndex(self.format_combo.findData(self._preferred_format))
        self.sample_rate_combo = QComboBox(self.mic_section)
        for rate in (44100, 48000, 96000):
            self.sample_rate_combo.addItem("%s Hz" % rate, rate)
        self.channels_combo = QComboBox(self.mic_section)
        self.channels_combo.addItem(_("Mono"), 1)
        self.channels_combo.addItem(_("Stereo"), 2)
        self.mic_section.advanced_layout.addWidget(QLabel(_("Input:"), self.mic_section), 0, 0)
        self.mic_section.advanced_layout.addWidget(self.device_combo, 0, 1)
        self.mic_section.advanced_layout.addWidget(QLabel(_("Format:"), self.mic_section), 1, 0)
        self.mic_section.advanced_layout.addWidget(self.format_combo, 1, 1)
        self.mic_section.advanced_layout.addWidget(QLabel(_("Sample Rate:"), self.mic_section), 2, 0)
        self.mic_section.advanced_layout.addWidget(self.sample_rate_combo, 2, 1)
        self.mic_section.advanced_layout.addWidget(QLabel(_("Channels:"), self.mic_section), 3, 0)
        self.mic_section.advanced_layout.addWidget(self.channels_combo, 3, 1)
        layout.addWidget(self.mic_section)

        self.screen_section = RecordingSection(_("Screen"), "▣", self)
        self.screen_mode_widget = QWidget(self.screen_section)
        screen_mode_row = QHBoxLayout(self.screen_mode_widget)
        screen_mode_row.setContentsMargins(0, 0, 0, 0)
        screen_mode_row.setSpacing(0)
        self.full_screen_button = SegmentButton(_("Full Screen"), self.screen_section)
        self.window_button = SegmentButton(_("Window"), self.screen_section)
        self.region_button = SegmentButton(_("Region"), self.screen_section)
        self.full_screen_button.setChecked(True)
        for button in (self.full_screen_button, self.window_button, self.region_button):
            screen_mode_row.addWidget(button)
        self.screen_section.body_layout.addWidget(self.screen_mode_widget)
        self.screen_status_label = QLabel("", self.screen_section)
        self.screen_status_label.setStyleSheet("color: #9aa8bd;")
        self.screen_status_label.setWordWrap(True)
        self.screen_section.body_layout.addWidget(self.screen_status_label)

        self.screen_display_edit = QLineEdit(
            "desktop" if sys.platform.startswith("win") else os.environ.get("DISPLAY", ":0.0"),
            self.screen_section,
        )
        self.screen_x_spin = QSpinBox(self.screen_section)
        self.screen_y_spin = QSpinBox(self.screen_section)
        self.screen_width_spin = QSpinBox(self.screen_section)
        self.screen_height_spin = QSpinBox(self.screen_section)
        for spin in (self.screen_x_spin, self.screen_y_spin):
            spin.setRange(-32768, 32767)
        for spin in (self.screen_width_spin, self.screen_height_spin):
            spin.setRange(16, 16384)
        self._set_screen_to_primary()
        self.capture_cursor_combo = QComboBox(self.screen_section)
        self.capture_cursor_combo.addItem(_("On"), True)
        self.capture_cursor_combo.addItem(_("Off"), False)
        self.hide_openshot_combo = QComboBox(self.screen_section)
        self.hide_openshot_combo.addItem(_("Yes"), True)
        self.hide_openshot_combo.addItem(_("No"), False)
        self.hide_openshot_combo.setToolTip(_("Temporarily hide OpenShot while selecting or recording a window or region."))
        self.video_fps_combo = QComboBox(self.screen_section)
        for fps in (15, 24, 30, 60):
            self.video_fps_combo.addItem(str(fps), fps)
        self.video_fps_combo.setCurrentIndex(self.video_fps_combo.findData(30))
        self.screen_display_label = QLabel(_("Display:"), self.screen_section)
        self.screen_x_label = QLabel("X:", self.screen_section)
        self.screen_y_label = QLabel("Y:", self.screen_section)
        self.screen_size_label = QLabel(_("Size:"), self.screen_section)
        self.screen_fps_label = QLabel(_("FPS:"), self.screen_section)
        self.screen_cursor_label = QLabel(_("Cursor:"), self.screen_section)
        self.screen_hide_label = QLabel(_("Hide OpenShot:"), self.screen_section)
        self.screen_section.advanced_layout.addWidget(self.screen_display_label, 0, 0)
        self.screen_section.advanced_layout.addWidget(self.screen_display_edit, 0, 1, 1, 3)
        self.screen_section.advanced_layout.addWidget(self.screen_x_label, 1, 0)
        self.screen_section.advanced_layout.addWidget(self.screen_x_spin, 1, 1)
        self.screen_section.advanced_layout.addWidget(self.screen_y_label, 1, 2)
        self.screen_section.advanced_layout.addWidget(self.screen_y_spin, 1, 3)
        self.screen_section.advanced_layout.addWidget(self.screen_size_label, 2, 0)
        self.screen_section.advanced_layout.addWidget(self.screen_width_spin, 2, 1)
        self.screen_section.advanced_layout.addWidget(self.screen_height_spin, 2, 2)
        self.screen_section.advanced_layout.addWidget(self.screen_fps_label, 3, 0)
        self.screen_section.advanced_layout.addWidget(self.video_fps_combo, 3, 1)
        self.screen_section.advanced_layout.addWidget(self.screen_cursor_label, 4, 0)
        self.screen_section.advanced_layout.addWidget(self.capture_cursor_combo, 4, 1)
        self.screen_section.advanced_layout.addWidget(self.screen_hide_label, 5, 0)
        self.screen_section.advanced_layout.addWidget(self.hide_openshot_combo, 5, 1)
        layout.addWidget(self.screen_section)

        self.camera_section = RecordingSection(_("Webcam"), "◉", self)
        self.webcam_preview_label = QLabel(_("Preview"), self.camera_section)
        self.webcam_preview_label.setAlignment(Qt.AlignCenter)
        self.webcam_preview_label.setFixedSize(220, 124)
        self.webcam_preview_label.setStyleSheet(
            "QLabel { background-color: rgba(8, 14, 24, 170); color: #8c9aaf; border-radius: 8px; }"
        )
        camera_details_row = QHBoxLayout()
        camera_details_row.setContentsMargins(0, 0, 0, 0)
        camera_details_row.setSpacing(12)
        camera_details_row.addWidget(self.webcam_preview_label, 0, Qt.AlignTop)

        camera_controls_box = QVBoxLayout()
        camera_controls_box.setSpacing(6)
        camera_options_label = QLabel(_("Options"), self.camera_section)
        camera_options_label.setStyleSheet("color: #9aa8bd;")
        camera_controls_box.addWidget(camera_options_label)
        self.webcam_layout_combo = QComboBox(self.camera_section)
        self.webcam_layout_combo.addItem(_("Bottom R"), "bottom-right")
        self.webcam_layout_combo.addItem(_("Top R"), "top-right")
        self.webcam_layout_combo.addItem(_("Bottom L"), "bottom-left")
        self.webcam_layout_combo.addItem(_("Top L"), "top-left")
        self.webcam_layout_combo.addItem(_("Left"), "left")
        self.webcam_layout_combo.addItem(_("Right"), "right")
        self.webcam_layout_combo.addItem(_("Center"), "center")
        self.webcam_layout_combo.addItem(_("Full"), "full")
        self.webcam_layout_combo.setToolTip(_("Layout"))
        camera_controls_box.addWidget(self.webcam_layout_combo)

        self.webcam_layout_size_combo = QComboBox(self.camera_section)
        self.webcam_layout_size_combo.addItem(_("Small"), 0.2)
        self.webcam_layout_size_combo.addItem(_("Medium"), 0.3)
        self.webcam_layout_size_combo.addItem(_("Large"), 0.5)
        self.webcam_layout_size_combo.setCurrentIndex(self.webcam_layout_size_combo.findData(0.3))
        self.webcam_layout_size_combo.setToolTip(_("Size"))
        camera_controls_box.addWidget(self.webcam_layout_size_combo)

        self.webcam_mask_combo = QComboBox(self.camera_section)
        self.webcam_mask_combo.addItem(_("Rounded"), "rounded")
        self.webcam_mask_combo.addItem(_("Circle"), "circle")
        self.webcam_mask_combo.addItem(_("None"), "none")
        self.webcam_mask_combo.setToolTip(_("Mask"))
        camera_controls_box.addWidget(self.webcam_mask_combo)
        camera_controls_box.addStretch()
        camera_details_row.addLayout(camera_controls_box)
        camera_details_row.addStretch()
        self.camera_section.body_layout.addLayout(camera_details_row)
        self.camera_combo = QComboBox(self.camera_section)
        self.camera_size_combo = QComboBox(self.camera_section)
        self.camera_fps_combo = QComboBox(self.camera_section)
        self.camera_section.advanced_layout.addWidget(QLabel(_("Input:"), self.camera_section), 0, 0)
        self.camera_section.advanced_layout.addWidget(self.camera_combo, 0, 1, 1, 2)
        self.camera_section.advanced_layout.addWidget(QLabel(_("Resolution:"), self.camera_section), 1, 0)
        self.camera_section.advanced_layout.addWidget(self.camera_size_combo, 1, 1, 1, 2)
        self.camera_section.advanced_layout.addWidget(QLabel(_("Record FPS:"), self.camera_section), 2, 0)
        self.camera_section.advanced_layout.addWidget(self.camera_fps_combo, 2, 1)
        layout.addWidget(self.camera_section)

        target_row = QHBoxLayout()
        target_label = QLabel(_("Track:"), self)
        self.track_combo = QComboBox(self)
        self.track_combo.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        target_row.addWidget(target_label)
        target_row.addWidget(self.track_combo, 1)
        layout.addLayout(target_row)

        self.preview_combo = QComboBox(self)
        self.preview_combo.addItem(_("No Preview"), "none")
        self.preview_combo.addItem(_("Timeline (full)"), "full")
        self.preview_combo.addItem(_("Timeline (50%)"), "half")
        self.preview_combo.addItem(_("Timeline (25%)"), "quarter")
        self.preview_combo.setCurrentIndex(self.preview_combo.findData("full"))
        self.preview_combo.hide()

        control_row = QHBoxLayout()
        self.record_button = QPushButton(_("Start Recording"), self)
        self.record_button.setObjectName("recordingPrimary")
        self.record_button.setIcon(QIcon(os.path.join(info.PATH, "themes/cosmic/images/tool-microphone.svg")))
        self.record_button.setMinimumHeight(38)
        self.record_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.record_button.setStyleSheet("font-weight: 600;")
        control_row.addWidget(self.record_button)
        layout.addLayout(control_row)

        layout.addStretch()

        self.timer = QTimer(self)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self._update_elapsed_time)
        self.poll_timer = QTimer(self)
        self.poll_timer.setInterval(50)
        self.poll_timer.timeout.connect(self._poll_recording_feedback)
        self.record_button.clicked.connect(self._toggle_recording)
        self.format_combo.currentIndexChanged.connect(self._format_changed)
        self.sample_rate_combo.currentIndexChanged.connect(self._sample_rate_changed)
        self.channels_combo.currentIndexChanged.connect(self._channels_changed)
        self.device_combo.currentIndexChanged.connect(self._mic_device_changed)
        self.hide_openshot_combo.currentIndexChanged.connect(self._hide_openshot_changed)
        self.mic_card.toggled.connect(self._source_toggled)
        self.screen_card.toggled.connect(self._source_toggled)
        self.camera_card.toggled.connect(self._source_toggled)
        self.camera_combo.currentIndexChanged.connect(self._camera_device_changed)
        self.camera_size_combo.currentIndexChanged.connect(self._camera_size_changed)
        self.camera_fps_combo.currentIndexChanged.connect(self._restart_webcam_preview)
        self.webcam_layout_combo.currentIndexChanged.connect(self._webcam_layout_changed)
        self.webcam_layout_size_combo.currentIndexChanged.connect(self._refresh_webcam_preview_mask)
        self.webcam_mask_combo.currentIndexChanged.connect(self._refresh_webcam_preview_mask)
        self.mono_button.clicked.connect(lambda: self._set_channels(1))
        self.stereo_button.clicked.connect(lambda: self._set_channels(2))
        self.full_screen_button.clicked.connect(self._select_full_screen)
        self.window_button.clicked.connect(self._select_window)
        self.region_button.clicked.connect(self._select_region)

        self._sync_source_availability()
        self._sync_source_sections()
        self._webcam_layout_changed()
        self._sync_backend_state()

    def _backend_available(self):
        audio_available = all(hasattr(openshot, name) for name in (
            "AudioRecorder",
            "AudioRecorderSettings",
        ))
        video_available = all(hasattr(openshot, name) for name in (
            "ScreenCaptureReader",
            "ScreenCaptureSettings",
            "CameraCaptureReader",
            "CameraCaptureSettings",
            "FFmpegWriter",
        ))
        return audio_available or video_available

    def _screen_backend_available(self):
        return screen_capture_backend_supported()

    def _camera_backend_available(self):
        if not all(hasattr(openshot, name) for name in ("CameraCaptureReader", "CameraCaptureSettings")):
            return False
        backend = camera_capture_backend()
        is_supported = getattr(openshot.CameraCaptureReader, "IsBackendSupported", None)
        if callable(is_supported) and backend is not None:
            try:
                return bool(is_supported(backend))
            except Exception:
                log.debug("Unable to query camera backend support", exc_info=True)
        return (
            backend == getattr(openshot, "CAMERA_CAPTURE_V4L2", object())
            and sys.platform.startswith("linux")
        ) or (
            backend == getattr(openshot, "CAMERA_CAPTURE_WINDOWS_DSHOW", object())
            and sys.platform.startswith("win")
        )

    def _selected_camera_device(self):
        device = self.camera_combo.currentData() if hasattr(self, "camera_combo") else None
        if device and (camera_capture_backend_is_windows() or os.path.exists(device)):
            return device
        return ""

    def _camera_device_available(self):
        return bool(self._camera_backend_available() and self._selected_camera_device())

    def _sync_source_availability(self):
        _ = get_app()._tr
        audio_available = all(hasattr(openshot, name) for name in ("AudioRecorder", "AudioRecorderSettings"))
        self.mic_card.setAvailable(audio_available, "" if audio_available else _("Audio recording is not available."))

        screen_available = self._screen_backend_available()
        screen_tip = "" if screen_available else _("Screen recording is not available for this platform or libopenshot build.")
        self.screen_card.setAvailable(screen_available, screen_tip)

        camera_backend_available = self._camera_backend_available()
        camera_available = camera_backend_available and self._camera_device_available()
        if not camera_backend_available:
            camera_tip = _("Webcam recording is not available for this platform or libopenshot build.")
        elif not camera_available:
            camera_tip = _("No webcam device was found.")
        else:
            camera_tip = ""
        self.camera_card.setAvailable(camera_available, camera_tip)
        self._sync_screen_backend_ui()

    def _sync_screen_backend_ui(self):
        _ = get_app()._tr
        wayland = screen_capture_backend_is_wayland()
        self.screen_mode_widget.setVisible(not wayland)
        self.screen_display_label.setVisible(not wayland)
        self.screen_display_edit.setVisible(not wayland)
        self.screen_x_label.setVisible(not wayland)
        self.screen_x_spin.setVisible(not wayland)
        self.screen_y_label.setVisible(not wayland)
        self.screen_y_spin.setVisible(not wayland)
        self.screen_size_label.setVisible(not wayland)
        self.screen_width_spin.setVisible(not wayland)
        self.screen_height_spin.setVisible(not wayland)
        self.window_button.setEnabled(not wayland)
        self.screen_hide_label.setVisible(not wayland)
        self.hide_openshot_combo.setVisible(not wayland)
        if wayland:
            self.screen_status_label.setText(_("Your desktop will ask what to share when recording starts."))
            self._screen_window_id = ""
        elif screen_capture_backend_is_windows():
            self.screen_status_label.setText(_("Windows screen recording uses full screen or numeric region bounds."))

    def _source_toggled(self):
        self._sync_source_sections()
        self._restart_monitoring()
        self._restart_webcam_preview()

    def _sync_source_sections(self):
        self.mic_section.setActive(self.mic_card.isChecked())
        self.screen_section.setActive(self.screen_card.isChecked())
        self.camera_section.setActive(self.camera_card.isChecked())
        if not self.camera_card.isChecked():
            self._stop_webcam_preview()

    def _set_screen_to_primary(self):
        root_x, root_y, root_width, root_height = screen_root_geometry()
        if root_width and root_height:
            self.screen_x_spin.setValue(int(root_x or 0))
            self.screen_y_spin.setValue(int(root_y or 0))
            self.screen_width_spin.setValue(int(root_width))
            self.screen_height_spin.setValue(int(root_height))
            self.screen_status_label.setText(get_app()._tr("Full screen: %sx%s") % (root_width, root_height))
            return
        try:
            screen = QApplication.primaryScreen()
            geometry = screen.geometry() if screen else None
            if geometry:
                self.screen_x_spin.setValue(int(geometry.x()))
                self.screen_y_spin.setValue(int(geometry.y()))
                self.screen_width_spin.setValue(int(geometry.width()))
                self.screen_height_spin.setValue(int(geometry.height()))
                self.screen_status_label.setText(get_app()._tr("Full screen: %sx%s") % (geometry.width(), geometry.height()))
                return
        except Exception:
            pass
        self.screen_x_spin.setValue(0)
        self.screen_y_spin.setValue(0)
        self.screen_width_spin.setValue(1280)
        self.screen_height_spin.setValue(720)
        self.screen_status_label.setText(get_app()._tr("Full screen"))

    def _set_screen_target(self, x, y, width, height, label):
        self.screen_x_spin.setValue(int(x))
        self.screen_y_spin.setValue(int(y))
        self.screen_width_spin.setValue(max(16, int(width)))
        self.screen_height_spin.setValue(max(16, int(height)))
        self.screen_status_label.setText(label)

    def _select_full_screen(self):
        if screen_capture_backend_is_wayland():
            self.screen_status_label.setText(get_app()._tr("Your desktop will ask what to share when recording starts."))
            return
        self.full_screen_button.setChecked(True)
        self.window_button.setChecked(False)
        self.region_button.setChecked(False)
        self._screen_window_id = ""
        self._set_hide_openshot_default(False)
        self._set_screen_to_primary()

    def _select_window(self):
        if screen_capture_backend_is_wayland():
            self.screen_status_label.setText(get_app()._tr("Your desktop will ask what to share when recording starts."))
            return
        self.window_button.setChecked(True)
        self.full_screen_button.setChecked(False)
        self.region_button.setChecked(False)
        self._set_hide_openshot_default(True)
        hidden_state = self._hide_openshot_for_picker()
        try:
            result = pick_screen_window()
        finally:
            self._restore_openshot_window(hidden_state)
        if result:
            x, y, width, height = result[:4]
            self._screen_window_id = str(result[4]) if len(result) > 4 and result[4] else ""
            self._set_screen_target(x, y, width, height, get_app()._tr("Window: %sx%s") % (width, height))
        else:
            self._screen_window_id = ""
            self.screen_status_label.setText(get_app()._tr("Window selection canceled."))

    def _select_region(self):
        if screen_capture_backend_is_wayland():
            self.screen_status_label.setText(get_app()._tr("Region selection is not available for Wayland screen recording."))
            return
        self.region_button.setChecked(True)
        self.full_screen_button.setChecked(False)
        self.window_button.setChecked(False)
        self._screen_window_id = ""
        self._set_hide_openshot_default(True)
        hidden_state = self._hide_openshot_for_picker()
        try:
            result = pick_screen_region(None if hidden_state is not None else self)
        finally:
            self._restore_openshot_window(hidden_state)
        if result:
            x, y, width, height = result
            self._set_screen_target(x, y, width, height, get_app()._tr("Region: %sx%s") % (width, height))
        else:
            self.screen_status_label.setText(get_app()._tr("Region selection canceled."))

    def _hide_openshot_changed(self):
        self._hide_openshot_user_set = True

    def _set_hide_openshot_default(self, checked):
        if self._hide_openshot_user_set:
            return
        self.hide_openshot_combo.blockSignals(True)
        index = self.hide_openshot_combo.findData(bool(checked))
        if index >= 0:
            self.hide_openshot_combo.setCurrentIndex(index)
        self.hide_openshot_combo.blockSignals(False)

    def _hide_openshot_enabled(self):
        if screen_capture_backend_is_wayland():
            return False
        return bool(self.hide_openshot_combo.currentData())

    def _hide_openshot_for_picker(self):
        if not self._hide_openshot_enabled():
            return None
        return self._hide_openshot_window(delay_ms=0)

    def _hide_openshot_for_recording(self):
        if (
            self._recording_hidden_window_state is not None
            or not self.screen_card.isChecked()
            or not self._hide_openshot_enabled()
        ):
            return
        self._recording_hidden_window_state = self._hide_openshot_window(delay_ms=50)

    def _restore_openshot_after_recording(self):
        state = self._recording_hidden_window_state
        self._recording_hidden_window_state = None
        self._restore_openshot_window(state)

    def _hide_openshot_window(self, delay_ms=75):
        if not self.window or not self.window.isVisible():
            return None
        state = {
            "window_state": self.window.windowState(),
            "geometry": self.window.saveGeometry(),
        }
        self._hiding_openshot_window = True
        try:
            self.window.hide()
            QApplication.processEvents()
            if delay_ms:
                deadline = time.monotonic() + (float(delay_ms) / 1000.0)
                while time.monotonic() < deadline:
                    QApplication.processEvents()
                    time.sleep(0.005)
                QApplication.processEvents()
            return state
        except Exception:
            log.debug("Unable to hide OpenShot window", exc_info=True)
        finally:
            self._hiding_openshot_window = False
        return None

    def _restore_openshot_window(self, state):
        if state is None or not self.window:
            return
        try:
            window_state = state.get("window_state") if isinstance(state, dict) else state
            geometry = state.get("geometry") if isinstance(state, dict) else None
            if geometry:
                self.window.restoreGeometry(geometry)
            if window_state & Qt.WindowFullScreen:
                self.window.showFullScreen()
            elif window_state & Qt.WindowMaximized:
                self.window.showMaximized()
            else:
                self.window.showNormal()
            self.window.raise_()
            self.window.activateWindow()
            QApplication.processEvents()
        except Exception:
            log.debug("Unable to restore OpenShot window", exc_info=True)

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

    def _mic_device_changed(self):
        self._stop_monitoring()
        self._sync_channel_options()
        self._restart_monitoring()

    def _sync_channel_options(self):
        supported = self._supported_audio_channels()
        if not supported:
            supported = {1, 2}

        self.mono_button.setEnabled(1 in supported)
        self.stereo_button.setEnabled(2 in supported)
        for channels in (1, 2):
            index = self.channels_combo.findData(channels)
            item = self.channels_combo.model().item(index) if index >= 0 else None
            if item:
                item.setEnabled(channels in supported)

        if self._channels not in supported:
            self._set_channels(1 if 1 in supported else 2, restart=False)
        else:
            self._set_channels(self._channels, restart=False)

    def _supported_audio_channels(self):
        cache_key = self.device_combo.currentData() or ("", "")
        if cache_key in self._audio_channel_support_cache:
            return set(self._audio_channel_support_cache[cache_key])
        supported = set()
        for channels in (1, 2):
            try:
                settings = self._build_recorder_settings(recording=False)
                settings.channels = channels
                settings.channel_layout = openshot.LAYOUT_MONO if channels == 1 else openshot.LAYOUT_STEREO
                settings.path = os.path.join(info.USER_PATH, "recording-channel-probe.wav")
                recorder = openshot.AudioRecorder(settings)
                recorder.Open()
                recorder.Close()
                supported.add(channels)
            except Exception:
                log.debug("Audio input does not support %s channel(s)", channels, exc_info=True)
        self._audio_channel_support_cache[cache_key] = set(supported)
        return supported

    def refresh_cameras(self):
        _ = get_app()._tr
        current = self.camera_combo.currentData() if hasattr(self, "camera_combo") else None
        self.camera_combo.blockSignals(True)
        self.camera_combo.clear()
        devices = []
        if camera_capture_backend_is_windows():
            try:
                get_devices = getattr(openshot.CameraCaptureReader, "GetDeviceNames", None)
                if callable(get_devices):
                    for label, device in get_devices(camera_capture_backend()):
                        devices.append((str(label or device), str(device or label)))
            except Exception as ex:
                log.debug("Unable to list DirectShow webcam devices: %s", ex, exc_info=True)
        else:
            devices = [
                (os.path.basename(device), device)
                for device in sorted(glob.glob("/dev/video*"))
                if os.path.exists(device)
            ]
        if not devices:
            self.camera_combo.addItem(_("No webcam found"), None)
        for label, device in devices:
            self.camera_combo.addItem(label, device)
        if current:
            for index in range(self.camera_combo.count()):
                if self.camera_combo.itemData(index) == current:
                    self.camera_combo.setCurrentIndex(index)
                    break
        self.camera_combo.blockSignals(False)
        self._refresh_camera_modes()
        self._sync_source_availability()

    def _camera_device_changed(self):
        self._refresh_camera_modes()
        self._sync_source_availability()
        self._restart_webcam_preview()

    def _camera_size_changed(self):
        self._update_webcam_preview_aspect()
        self._refresh_camera_fps_options()
        self._restart_webcam_preview()

    def _refresh_camera_modes(self):
        current_size = self.camera_size_combo.currentData() if hasattr(self, "camera_size_combo") else None
        device = self._selected_camera_device()
        if not device:
            self._camera_modes = {}
            self._camera_mode_formats = {}
            self.camera_size_combo.blockSignals(True)
            self.camera_size_combo.clear()
            self.camera_size_combo.blockSignals(False)
            self.camera_fps_combo.blockSignals(True)
            self.camera_fps_combo.clear()
            self.camera_fps_combo.blockSignals(False)
            self.webcam_preview_label.setText(get_app()._tr("No webcam found"))
            self._update_webcam_preview_aspect()
            return
        self._camera_modes = self._probe_camera_modes(device)

        common_order = [
            (3840, 2160), (2560, 1440), (1920, 1080), (1600, 900),
            (1280, 720), (1024, 768), (800, 600), (640, 480), (640, 360),
        ]
        common_sizes = [size for size in common_order if size in self._camera_modes]
        sizes = common_sizes or sorted(self._camera_modes.keys(), key=lambda size: (size[0] * size[1], size[0]), reverse=True)
        preferred = current_size if current_size in self._camera_modes else None
        if preferred is None:
            for candidate in ((1280, 720), (640, 480), (1920, 1080), (640, 360)):
                if candidate in self._camera_modes:
                    preferred = candidate
                    break
        if preferred is None and sizes:
            preferred = sizes[0]

        self.camera_size_combo.blockSignals(True)
        self.camera_size_combo.clear()
        for width, height in sizes:
            self.camera_size_combo.addItem("%s x %s" % (width, height), (width, height))
        if preferred:
            index = self.camera_size_combo.findData(preferred)
            if index >= 0:
                self.camera_size_combo.setCurrentIndex(index)
        self.camera_size_combo.blockSignals(False)
        self._update_webcam_preview_aspect()
        self._refresh_camera_fps_options()

    def _update_webcam_preview_aspect(self):
        size = self.camera_size_combo.currentData() if hasattr(self, "camera_size_combo") else None
        width, height = size or (16, 9)
        if width <= 0 or height <= 0:
            width, height = 16, 9
        preview_width = 220
        preview_height = max(80, int(round(preview_width * float(height) / float(width))))
        self.webcam_preview_label.setFixedSize(preview_width, preview_height)
        self._refresh_webcam_preview_mask()

    def _refresh_camera_fps_options(self):
        current_fps = self.camera_fps_combo.currentData() if hasattr(self, "camera_fps_combo") else None
        size = self.camera_size_combo.currentData()
        fps_values = sorted(self._camera_modes.get(size, {15, 24, 30, 60}))
        if 30 in fps_values:
            preferred = 30
        elif current_fps in fps_values:
            preferred = current_fps
        else:
            preferred = fps_values[0] if fps_values else 30

        self.camera_fps_combo.blockSignals(True)
        self.camera_fps_combo.clear()
        for fps in fps_values:
            self.camera_fps_combo.addItem(str(fps), fps)
        index = self.camera_fps_combo.findData(preferred)
        if index >= 0:
            self.camera_fps_combo.setCurrentIndex(index)
        self.camera_fps_combo.blockSignals(False)

    def _probe_camera_modes(self, device):
        fallback = {
            (1920, 1080): {30},
            (1280, 720): {30},
            (640, 480): {30},
            (640, 360): {30},
        }
        self._camera_mode_formats = {}
        if camera_capture_backend_is_windows():
            return fallback
        try:
            result = subprocess.run(
                ["v4l2-ctl", "--list-formats-ext", "-d", device],
                check=True,
                text=True,
                capture_output=True,
                timeout=4,
            )
        except Exception as ex:
            log.debug("Unable to probe webcam modes for %s: %s", device, ex)
            return fallback

        modes = {}
        current_size = None
        current_format = ""
        for line in result.stdout.splitlines():
            format_match = re.search(r"\[\d+\]:\s+'([^']+)'", line)
            if format_match:
                current_format = self._ffmpeg_v4l2_format(format_match.group(1))
                current_size = None
                continue
            size_match = re.search(r"Size:\s+Discrete\s+(\d+)x(\d+)", line)
            if size_match:
                current_size = (int(size_match.group(1)), int(size_match.group(2)))
                modes.setdefault(current_size, set())
                continue
            fps_match = re.search(r"\((\d+(?:\.\d+)?)\s+fps\)", line)
            if fps_match and current_size:
                fps = max(1, int(round(float(fps_match.group(1)))))
                modes.setdefault(current_size, set()).add(fps)
                if current_format:
                    key = (current_size[0], current_size[1], fps)
                    existing = self._camera_mode_formats.get(key)
                    if not existing or existing != "mjpeg":
                        self._camera_mode_formats[key] = current_format

        for size in list(modes):
            if not modes[size]:
                modes[size] = {30}
        return modes or fallback

    def _ffmpeg_v4l2_format(self, format_code):
        return {
            "MJPG": "mjpeg",
            "YUYV": "yuyv422",
        }.get(str(format_code).upper(), str(format_code).lower())

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
        if not self.mic_card.isChecked() and not self.screen_card.isChecked() and not self.camera_card.isChecked():
            self.record_button.setToolTip(_("Select at least one recording source."))
            return
        validation_error = self._recording_start_validation_error()
        if validation_error:
            self.record_button.setToolTip(validation_error)
            return

        self._starting = True
        self._set_record_button_starting()
        QApplication.processEvents()

        self._set_wait_cursor(True)
        self._stop_monitoring()
        self._stop_webcam_preview()
        try:
            self._recording_timeline_position = self._context_start
            if self._recording_timeline_position is None:
                self._recording_timeline_position = self._current_playhead_seconds()
            self._context_start = self._recording_timeline_position
            self._recording_sources = []
            source_types = self._selected_recording_source_types()
            session_id = str(int(time.monotonic() * 1000))
            self._recording_preview_id = "recording-preview-%s" % session_id
            self._recording_track_map = self._recording_track_assignments(source_types)
            self._recording_preview_file_ids = {
                source_type: recording_preview_file_id(session_id, source_type)
                for source_type in source_types
            }
            self._recorder = None
            self._recording_path = ""
            self._video_jobs = self._build_video_jobs()
            self._hide_openshot_for_recording()
            for job in self._video_jobs:
                job.errorOccurred.connect(self._live_video_recording_error)
                if job.source_type == "screen" and screen_capture_backend_is_wayland():
                    job.start_async()
                    job.wait_until_opened()
                else:
                    job.start()
                self._recording_sources.append((job.source_type, job.path))
            self._begin_recording()
        except Exception as ex:
            self._recorder = None
            self._recording = False
            self._starting = False
            self._restore_recording_preview_scale()
            self._restore_openshot_after_recording()
            self._set_record_button_idle()
            self.record_button.setToolTip(_("Unable to prepare recording: %s") % ex)
            self._stop_video_jobs(delete_files=True)
            log.error("Unable to prepare recording", exc_info=True)
            self._ensure_monitoring()
            self._restart_webcam_preview()
            return
        finally:
            self._set_wait_cursor(False)

    def _recording_start_validation_error(self):
        _ = get_app()._tr
        if self.screen_card.isChecked() and not self._screen_backend_available():
            return _("Screen recording is not available for this platform or libopenshot build.")
        if self.camera_card.isChecked():
            if not self._camera_backend_available():
                return _("Webcam recording is not available for this platform or libopenshot build.")
            device = self.camera_combo.currentData()
            if not device:
                return _("No webcam device was found.")
            if not camera_capture_backend_is_windows() and not os.path.exists(device):
                return _("Webcam device was not found: %s") % device
            if not camera_capture_backend_is_windows() and not os.access(device, os.R_OK):
                return _("Webcam device is not accessible: %s") % device
        return ""

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
        self._reset_recording_preview_state()
        self._restore_recording_preview_scale()
        self._restore_openshot_after_recording()
        self._set_record_button_idle()
        if restart_monitoring:
            self._ensure_monitoring()
            self._restart_webcam_preview()

    def _begin_recording(self):
        _ = get_app()._tr
        try:
            if self._should_preview_timeline() or self._playback_active():
                self._recording_timeline_position = self._current_playhead_seconds()
            self._context_start = self._recording_timeline_position
            recorder = self._recorder
            if recorder is None:
                if self.mic_card.isChecked():
                    settings = self._build_recorder_settings(recording=True)
                    recorder = openshot.AudioRecorder(settings)
                    recorder.Open()
                    if hasattr(recorder, "PrepareRecording"):
                        recorder.PrepareRecording()
                    self._recorder = recorder
            self._apply_recording_preview_scale()
            if recorder is not None:
                recorder.Start()
            recording_started_at = time.monotonic()
            for job in self._video_jobs or []:
                job.begin(recording_started_at)
        except Exception as ex:
            self._recorder = None
            self._recording = False
            self._starting = False
            self._restore_recording_preview_scale()
            self._restore_openshot_after_recording()
            self._set_record_button_idle()
            self.record_button.setToolTip(_("Unable to start recording: %s") % ex)
            self._stop_video_jobs(delete_files=True)
            log.error("Unable to start recording", exc_info=True)
            self._ensure_monitoring()
            self._restart_webcam_preview()
            return

        self._starting = False
        self._recorder = recorder
        self._recording = True
        self._recording_started_at = recording_started_at
        if self.mic_card.isChecked() and self._recording_path:
            self._recording_sources.append(("mic", self._recording_path))
        if self._should_preview_timeline():
            self._start_timeline_playback()
        self._last_timeline_preview_at = 0.0
        self._last_timeline_preview_samples = 0
        if not self._recording_preview_id:
            self._recording_preview_id = "recording-preview-%d" % int(self._recording_started_at * 1000)
        self._set_record_button_recording()
        self._show_recording_tray()
        self.level_meter.update_levels()
        self._recording_waveform_samples = []
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
        self._tray_status.hide()
        self.timer.stop()
        self.poll_timer.stop()
        self._poll_recording_feedback()
        self._set_record_button_stopping()
        QApplication.processEvents()

        path = self._recording_path
        sources = list(self._recording_sources)
        try:
            if self._recorder:
                self._recorder.Stop()
                try:
                    stats = self._recorder.GetStats()
                    recorded_duration = max(recorded_duration, float(getattr(stats, "duration", 0.0) or 0.0))
                except Exception:
                    log.debug("Unable to read audio recorder duration", exc_info=True)
                self._recorder.Close()
            self._stop_video_jobs(delete_files=False)
        except Exception as ex:
            self.record_button.setToolTip(_("Unable to finish recording: %s") % ex)
            log.error("Unable to finish audio recording", exc_info=True)
            path = ""
        finally:
            self._recorder = None
            self._recorded_duration = recorded_duration

        self._restore_recording_preview_scale()
        self._restore_openshot_after_recording()
        if any(record_path and os.path.exists(record_path) for _, record_path in sources):
            self._set_record_button_saving()
            QApplication.processEvents()
        self._import_recording_group(sources)
        self._clear_timeline_preview()
        self._set_record_button_idle()
        self._ensure_monitoring()
        self._restart_webcam_preview()
        self._reset_recording_preview_state()
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
        return self._next_named_recording_path("Mic", self._preferred_format or "wav")

    def _next_named_recording_path(self, prefix, extension):
        project_path = getattr(get_app().project, "current_filepath", None)
        assets_path = get_assets_path(project_path)
        recordings_path = os.path.join(assets_path or info.USER_PATH, "recordings")
        os.makedirs(recordings_path, exist_ok=True)

        timestamp = time.strftime("%Y%m%d-%H%M%S")
        base = os.path.join(recordings_path, "%s-%s.%s" % (prefix, timestamp, extension))
        if not os.path.exists(base):
            return base
        for index in range(2, 1000):
            candidate = os.path.join(
                recordings_path,
                "%s-%s-%03d.%s" % (prefix, timestamp, index, extension),
            )
            if not os.path.exists(candidate):
                return candidate
        return base

    def _build_video_jobs(self):
        jobs = []
        screen_fps = openshot.Fraction(int(self.video_fps_combo.currentData() or 30), 1)
        if self.screen_card.isChecked():
            screen_backend = screen_capture_backend()
            wayland_screen = screen_capture_backend_is_wayland(screen_backend)
            screen_x = int(self.screen_x_spin.value())
            screen_y = int(self.screen_y_spin.value())
            screen_width = self._safe_even_dimension(self.screen_width_spin.value())
            screen_height = self._safe_even_dimension(self.screen_height_spin.value())
            windows_screen = screen_capture_backend_is_windows(screen_backend)
            if wayland_screen:
                root_x, root_y, root_width, root_height = 0, 0, None, None
            else:
                root_x, root_y, root_width, root_height = screen_root_geometry()
            if not wayland_screen and root_width and root_height:
                root_x = int(root_x or 0)
                root_y = int(root_y or 0)
                root_width = int(root_width)
                root_height = int(root_height)
                root_right = root_x + root_width
                root_bottom = root_y + root_height
                screen_width = min(screen_width, root_width)
                screen_height = min(screen_height, root_height)
                screen_x = max(root_x, min(screen_x, max(root_x, root_right - screen_width)))
                screen_y = max(root_y, min(screen_y, max(root_y, root_bottom - screen_height)))
                screen_width = self._safe_even_dimension(min(screen_width, root_right - screen_x))
                screen_height = self._safe_even_dimension(min(screen_height, root_bottom - screen_y))
            settings = openshot.ScreenCaptureSettings()
            settings.backend = screen_backend
            settings.display = (
                "desktop" if windows_screen else self.screen_display_edit.text().strip() or os.environ.get("DISPLAY", ":0.0")
            )
            settings.x = screen_x
            settings.y = screen_y
            settings.width = screen_width
            settings.height = screen_height
            settings.fps = screen_fps
            settings.include_cursor = bool(self.capture_cursor_combo.currentData())
            if not wayland_screen and self._screen_window_id and self.window_button.isChecked():
                settings.options["window_id"] = str(self._screen_window_id)
            self.screen_x_spin.setValue(settings.x)
            self.screen_y_spin.setValue(settings.y)
            self.screen_width_spin.setValue(settings.width)
            self.screen_height_spin.setValue(settings.height)
            log.info(
                "Preparing screen capture: backend=%s display=%s x=%s y=%s width=%s height=%s fps=%s/%s",
                settings.backend, settings.display, settings.x, settings.y, settings.width, settings.height,
                screen_fps.num, screen_fps.den,
            )
            path = self._next_named_recording_path("Screen", "mp4")
            jobs.append(LiveVideoRecordingJob(
                openshot.ScreenCaptureReader(settings),
                path,
                settings.width,
                settings.height,
                screen_fps,
                source_type="screen",
                preview_file_id=self._recording_preview_file_ids.get("screen", ""),
            ))
        if self.camera_card.isChecked():
            camera_fps = openshot.Fraction(int(self.camera_fps_combo.currentData() or 30), 1)
            camera_size = self.camera_size_combo.currentData() or (1280, 720)
            camera_device = self._selected_camera_device()
            if not camera_device:
                raise RuntimeError(get_app()._tr("No webcam device was found."))
            settings = openshot.CameraCaptureSettings()
            settings.backend = camera_capture_backend()
            settings.device = camera_device
            settings.width = self._safe_even_dimension(camera_size[0])
            settings.height = self._safe_even_dimension(camera_size[1])
            settings.fps = camera_fps
            input_format = self._camera_mode_formats.get((settings.width, settings.height, int(camera_fps.num)))
            if input_format:
                settings.options["input_format"] = input_format
            log.info(
                "Preparing webcam capture: device=%s width=%s height=%s fps=%s/%s input_format=%s",
                settings.device, settings.width, settings.height, camera_fps.num, camera_fps.den,
                input_format or "default",
            )
            path = self._next_named_recording_path("Webcam", "mp4")
            job = LiveVideoRecordingJob(
                openshot.CameraCaptureReader(settings),
                path,
                settings.width,
                settings.height,
                camera_fps,
                source_type="webcam",
                use_reader_fps=False,
                preview_file_id=self._recording_preview_file_ids.get("webcam", ""),
            )
            job.previewFrameReady.connect(self._update_webcam_preview)
            jobs.append(job)
        return jobs

    def _stop_video_jobs(self, delete_files=False):
        jobs = list(self._video_jobs or [])
        self._video_jobs = []
        for job in jobs:
            try:
                job.stop()
                if job.error:
                    log.error("Live video recording error for %s: %s", job.path, job.error)
            except Exception:
                log.debug("Unable to stop live video recording job", exc_info=True)
            if delete_files and job.path and os.path.exists(job.path):
                try:
                    os.remove(job.path)
                except OSError:
                    log.debug("Unable to remove canceled video recording file: %s", job.path, exc_info=True)

    def _live_video_recording_error(self, source_type, message):
        log.error("Live video recording error for %s: %s", source_type, message)
        if self._recording:
            self.record_button.setToolTip(get_app()._tr("Recording stopped: %s") % message)
            QTimer.singleShot(0, self.stop_recording)

    def _restart_webcam_preview(self):
        if self._recording or self._starting:
            return
        self._stop_webcam_preview()
        if not self._dock_visible() or not self.camera_card.isChecked() or not self._camera_backend_available():
            return
        device = self._selected_camera_device()
        if not device:
            self.webcam_preview_label.setText(get_app()._tr("No webcam found"))
            return
        camera_size = self.camera_size_combo.currentData() or (640, 480)
        width = self._safe_even_dimension(camera_size[0])
        height = self._safe_even_dimension(camera_size[1])
        self._webcam_preview = WebcamPreviewJob(device, min(width, 640), min(height, 360), camera_capture_backend(), self)
        self._webcam_preview.frameReady.connect(self._update_webcam_preview)
        self._webcam_preview.errorOccurred.connect(self._webcam_preview_error)
        self._webcam_preview.start()

    def _stop_webcam_preview(self):
        preview = self._webcam_preview
        self._webcam_preview = None
        if preview:
            try:
                preview.stop()
            except Exception:
                log.debug("Unable to stop webcam preview", exc_info=True)

    @pyqtSlot(object)
    def _update_webcam_preview(self, image):
        if not image:
            return
        pixmap = QPixmap.fromImage(image)
        if not pixmap.isNull():
            self._webcam_preview_pixmap = pixmap
            self.webcam_preview_label.setPixmap(self._masked_webcam_pixmap(pixmap))

    def _refresh_webcam_preview_mask(self):
        pixmap = self._webcam_preview_pixmap
        if pixmap and not pixmap.isNull():
            self.webcam_preview_label.setPixmap(self._masked_webcam_pixmap(pixmap))

    def _webcam_layout_changed(self):
        self.webcam_layout_size_combo.setEnabled(self._webcam_layout() != "full")
        self._refresh_webcam_preview_mask()

    def _masked_webcam_pixmap(self, pixmap):
        target_size = self.webcam_preview_label.size()
        scaled = pixmap.scaled(target_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        canvas = QPixmap(target_size)
        canvas.fill(Qt.transparent)

        x = int((target_size.width() - scaled.width()) / 2)
        y = int((target_size.height() - scaled.height()) / 2)
        shape = self._webcam_mask_shape()
        painter = QPainter(canvas)
        painter.setRenderHint(QPainter.Antialiasing, True)
        if shape != "none":
            path = QPainterPath()
            if shape == "circle":
                diameter = min(scaled.width(), scaled.height())
                path.addEllipse(
                    x + int((scaled.width() - diameter) / 2),
                    y + int((scaled.height() - diameter) / 2),
                    diameter,
                    diameter,
                )
            else:
                path.addRoundedRect(x, y, scaled.width(), scaled.height(), 12, 12)
            painter.setClipPath(path)
        painter.drawPixmap(x, y, scaled)
        painter.end()
        return canvas

    @pyqtSlot(str)
    def _webcam_preview_error(self, message):
        self.webcam_preview_label.setText(get_app()._tr("Preview unavailable"))
        log.debug("Unable to update webcam preview: %s", message)

    def _safe_even_dimension(self, value):
        value = max(16, int(value))
        return value if value % 2 == 0 else value - 1

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
            self._recording_waveform_samples = samples
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
        if not timeline:
            return
        position = self._context_start
        if position is None:
            position = self._recording_timeline_position
        previews = self._recording_preview_payloads(float(position or 0.0), duration, samples)
        if hasattr(timeline, "set_audio_recording_previews"):
            timeline.set_audio_recording_previews(previews)
        elif hasattr(timeline, "set_audio_recording_preview") and previews:
            mic_preview = next((preview for preview in previews if preview.get("source_type") == "mic"), previews[0])
            timeline.set_audio_recording_preview(
                mic_preview["id"],
                mic_preview["position"],
                mic_preview["track"],
                mic_preview["duration"],
                mic_preview.get("audio_data") or [],
            )

    def _recording_preview_payloads(self, position, duration, samples):
        duration = max(0.05, float(duration or 0.0))
        previews = []
        source_types = self._selected_recording_source_types()
        assignments = self._recording_track_map or self._recording_track_assignments(source_types)
        file_ids = self._recording_preview_file_ids or {}
        for source_type in source_types:
            preview = {
                "id": "%s-%s" % (self._recording_preview_id or "recording-preview", source_type),
                "source_type": source_type,
                "position": float(position or 0.0),
                "track": int(assignments.get(source_type, self._recording_top_track()) or 1),
                "duration": duration,
                "file_id": file_ids.get(source_type, ""),
            }
            if source_type == "mic":
                preview["audio_data"] = list(samples or [])
            elif source_type == "screen":
                fps = float(self.video_fps_combo.currentData() or 30)
                preview.update({
                    "width": int(self.screen_width_spin.value()),
                    "height": int(self.screen_height_spin.value()),
                    "fps": fps,
                    "title": get_app()._tr("Screen Recording"),
                })
            elif source_type == "webcam":
                camera_size = self.camera_size_combo.currentData() or (1280, 720)
                fps = float(self.camera_fps_combo.currentData() or 30)
                preview.update({
                    "width": int(camera_size[0]),
                    "height": int(camera_size[1]),
                    "fps": fps,
                    "title": get_app()._tr("Webcam Recording"),
                })
            previews.append(preview)
        return previews

    def _clear_timeline_preview(self):
        timeline = getattr(self.window, "timeline", None)
        if timeline and hasattr(timeline, "clear_audio_recording_preview"):
            timeline.clear_audio_recording_preview()

    def _reset_recording_preview_state(self):
        self._recording_preview_id = ""
        self._recording_preview_file_ids = {}
        self._recording_track_map = {}
        self._recording_waveform_samples = []

    def _selected_recording_source_types(self):
        source_types = []
        if self.mic_card.isChecked():
            source_types.append("mic")
        if self.screen_card.isChecked():
            source_types.append("screen")
        if self.camera_card.isChecked():
            source_types.append("webcam")
        return source_types

    def _import_recording_group(self, sources):
        selected = []
        existing_sources = [
            (source_type, path)
            for source_type, path in sources
            if path and os.path.exists(path)
        ]
        assignments = self._recording_track_map or self._recording_track_assignments(
            [source_type for source_type, _ in existing_sources])
        if assignments:
            log.info("Recording track assignments: %s", assignments)
        import_order = {"mic": 0, "screen": 1, "webcam": 2}
        for source_type, path in sorted(existing_sources, key=lambda item: import_order.get(item[0], 99)):
            track = assignments.get(source_type, self._recording_top_track())
            clip_data = self._import_recording(path, source_type, track)
            if clip_data:
                selected.append(clip_data)

        if selected:
            self._select_recording_clip(selected[-1], float(self._recording_timeline_position or 0.0))

    def _recording_track_assignments(self, source_types):
        top_order = ["webcam", "screen", "mic"]
        source_set = set(source_types or [])
        ordered_sources = [source for source in top_order if source in source_set]
        if not ordered_sources:
            return {}

        tracks = self._recording_track_stack(len(ordered_sources))
        assignments = dict(zip(ordered_sources, tracks))
        return assignments

    def _recording_track_stack(self, count):
        available = self._available_recording_tracks()
        if not available:
            top_track = self._recording_top_track()
            return [max(1, top_track - index) for index in range(count)]

        selected = self.track_combo.currentData()
        try:
            selected = int(selected)
        except (TypeError, ValueError):
            selected = available[0]
        if selected not in available:
            selected = available[0]

        start_index = available.index(selected)
        tracks = available[start_index:start_index + count]
        if len(tracks) < count:
            tracks.extend([track for track in available[:start_index] if track not in tracks])
        if len(tracks) < count:
            lowest = min(available)
            while len(tracks) < count:
                lowest = max(1, lowest - 1)
                if lowest not in tracks:
                    tracks.append(lowest)
        return tracks[:count]

    def _available_recording_tracks(self):
        tracks = []
        try:
            layers = list(get_app().project.get("layers") or [])
            tracks = [int(layer.get("number", 0)) for layer in layers]
        except Exception:
            tracks = []
        if not tracks:
            try:
                tracks = [int(t.data.get("number", 0)) for t in Track.filter()]
            except Exception:
                tracks = []
        return sorted([track for track in tracks if track > 0], reverse=True)

    def _recording_top_track(self):
        track = self.track_combo.currentData()
        if track is not None:
            try:
                return max(1, int(track))
            except (TypeError, ValueError):
                pass
        try:
            tracks = [int(t.data.get("number", 0)) for t in Track.filter()]
            tracks = [number for number in tracks if number > 0]
            if tracks:
                return max(tracks)
        except Exception:
            log.debug("Unable to determine top recording track", exc_info=True)
        return 1

    def _import_recording(self, path, source_type="mic", track=None):
        try:
            self.window.files_model.add_files(
                path,
                quiet=True,
                prevent_image_seq=True,
                prevent_recent_folder=True,
            )
            if source_type == "mic":
                self._apply_recording_duration(path)
            self.window.refreshFilesSignal.emit()
            return self._add_recording_to_timeline(path, source_type=source_type, track=track)
        except Exception:
            log.error("Unable to import recorded file: %s", path, exc_info=True)
        return None

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

    def _add_recording_to_timeline(self, path, source_type="mic", track=None):
        timeline = getattr(self.window, "timeline", None)
        if not timeline:
            return

        recorded_file = File.get(path=path)
        if not recorded_file:
            return

        self._copy_live_recording_thumbnails(source_type, recorded_file.id)
        position = self._context_start
        if position is None:
            position = self._recording_timeline_position

        if track is None:
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
        if isinstance(new_clip, dict):
            new_clip["layer"] = int(track)
            clip_id = new_clip.get("id")
            saved_clip = Clip.get(id=clip_id) if clip_id else None
            if source_type == "webcam":
                self._apply_webcam_clip_layout(new_clip)
                self._apply_webcam_clip_mask(new_clip)
            if saved_clip and int(saved_clip.data.get("layer", 0) or 0) != int(track):
                saved_clip.data.update(new_clip)
                saved_clip.save()
            elif saved_clip and source_type == "webcam":
                saved_clip.data.update(new_clip)
                saved_clip.save()
            if source_type == "webcam":
                timeline.update_clip_data(new_clip, only_basic_props=False, ignore_refresh=False)
        return new_clip

    def _copy_live_recording_thumbnails(self, source_type, final_file_id):
        temp_file_id = (self._recording_preview_file_ids or {}).get(source_type)
        if not temp_file_id or not final_file_id:
            return 0
        cache = LiveRecordingThumbnailCache(temp_file_id, 0.0)
        copied = cache.copy_to_file_id(final_file_id)
        if copied:
            log.info(
                "Copied %s live recording thumbnails from %s to %s",
                copied,
                temp_file_id,
                final_file_id,
            )
        return copied

    def _apply_webcam_clip_layout(self, clip_data):
        layout = self._webcam_layout()
        scale = 1.0 if layout == "full" else self._webcam_layout_scale()
        gravity = {
            "top-left": openshot.GRAVITY_TOP_LEFT,
            "top-right": openshot.GRAVITY_TOP_RIGHT,
            "bottom-left": openshot.GRAVITY_BOTTOM_LEFT,
            "bottom-right": openshot.GRAVITY_BOTTOM_RIGHT,
            "left": openshot.GRAVITY_LEFT,
            "right": openshot.GRAVITY_RIGHT,
            "center": openshot.GRAVITY_CENTER,
            "full": openshot.GRAVITY_CENTER,
        }.get(layout, openshot.GRAVITY_BOTTOM_RIGHT)
        clip_data["gravity"] = gravity
        clip_data["scale"] = openshot.SCALE_FIT if layout != "full" else openshot.SCALE_STRETCH
        clip_data["scale_x"] = {"Points": [self._keyframe_point(scale)]}
        clip_data["scale_y"] = {"Points": [self._keyframe_point(scale)]}
        clip_data["location_x"] = {"Points": [self._keyframe_point(0.0)]}
        clip_data["location_y"] = {"Points": [self._keyframe_point(0.0)]}

    def _apply_webcam_clip_mask(self, clip_data):
        shape = self._webcam_mask_shape()
        if shape == "none":
            return
        mask_path = self._webcam_mask_path(shape)
        if not mask_path:
            return
        try:
            effect = openshot.EffectInfo().CreateEffect("Mask")
            effect.Id(get_app().project.generate_id())
            effect_data = json.loads(effect.Json())
            effect_data["mask_reader"], _ = inspect_media(mask_path)
            effect_data["order"] = len(clip_data.get("effects") or [])
            effects = clip_data.get("effects")
            if not isinstance(effects, list):
                effects = []
                clip_data["effects"] = effects
            effects.append(effect_data)
        except Exception:
            log.debug("Unable to attach webcam mask effect", exc_info=True)

    def _webcam_mask_path(self, shape):
        size = self.camera_size_combo.currentData() or (640, 480)
        width = self._safe_even_dimension(size[0])
        height = self._safe_even_dimension(size[1])
        recordings_path = os.path.dirname(self._next_named_recording_path("Mask", "png"))
        path = os.path.join(recordings_path, "webcam-alpha-mask-%s-%sx%s.png" % (shape, width, height))
        if os.path.exists(path):
            return path
        image = QImage(width, height, QImage.Format_RGB32)
        image.fill(QColor(255, 255, 255))
        painter = QPainter(image)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(0, 0, 0))
        if shape == "circle":
            diameter = min(width, height)
            painter.drawEllipse(
                int((width - diameter) / 2),
                int((height - diameter) / 2),
                diameter,
                diameter,
            )
        else:
            radius = max(12, int(min(width, height) * 0.08))
            painter.drawRoundedRect(0, 0, width, height, radius, radius)
        painter.end()
        return path if image.save(path) else ""

    def _webcam_mask_shape(self):
        return self.webcam_mask_combo.currentData() or "rounded"

    def _webcam_layout(self):
        return self.webcam_layout_combo.currentData() or "bottom-right"

    def _webcam_layout_scale(self):
        try:
            return float(self.webcam_layout_size_combo.currentData() or 0.3)
        except (TypeError, ValueError):
            return 0.3

    def _keyframe_point(self, value):
        return json.loads(openshot.Point(1, float(value), openshot.BEZIER).Json())

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
        self._set_record_button_recording(elapsed)
        self._update_timeline_preview(self._recording_waveform_samples, elapsed)

    def _format_elapsed_time(self, elapsed):
        minutes = int(elapsed // 60)
        seconds = elapsed - (minutes * 60)
        return "%02d:%04.1f" % (minutes, seconds)

    def _show_recording_tray(self):
        self._tray_status.show_recording(
            on_stop=lambda: QTimer.singleShot(0, self.stop_recording),
        )

    def _set_record_button_idle(self):
        self.record_button.setEnabled(True)
        self.record_button.setText(get_app()._tr("Start Recording"))
        self.record_button.setStyleSheet(
            "QPushButton { background-color: #087cff; color: white; border: none; border-radius: 8px; padding: 11px; font-weight: 700; }"
            "QPushButton:hover { background-color: #1688ff; }"
            "QPushButton:pressed { background-color: #0567d6; }"
        )
        self.record_button.setToolTip("")

    def _set_record_button_unavailable(self):
        self.record_button.setEnabled(False)
        self.record_button.setText(get_app()._tr("Unavailable"))
        self.record_button.setStyleSheet("QPushButton { color: #8b96a8; font-weight: 600; }")
        self.record_button.setToolTip("")

    def _set_record_button_starting(self):
        self.record_button.setEnabled(False)
        self.record_button.setText(get_app()._tr("Starting..."))
        self.record_button.setStyleSheet("QPushButton { color: #d8e3f2; font-weight: 600; }")
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
        self.record_button.setStyleSheet("QPushButton { color: #d8e3f2; font-weight: 600; }")
        self.record_button.setToolTip("")

    def _set_record_button_recording(self, elapsed=None):
        self.record_button.setEnabled(True)
        if elapsed is None:
            elapsed = 0.0
        self.record_button.setText(
            "%s  %s" % (get_app()._tr("Stop Recording"), self._format_elapsed_time(elapsed))
        )
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

    def _set_channels(self, value, restart=True):
        value = int(value)
        if value == 2 and not self.stereo_button.isEnabled():
            value = 1
        if value == 1 and not self.mono_button.isEnabled() and self.stereo_button.isEnabled():
            value = 2
        self._channels = value
        self.mono_button.setChecked(self._channels == 1)
        self.stereo_button.setChecked(self._channels == 2)
        index = self.channels_combo.findData(self._channels)
        if index >= 0 and self.channels_combo.currentIndex() != index:
            self.channels_combo.blockSignals(True)
            self.channels_combo.setCurrentIndex(index)
            self.channels_combo.blockSignals(False)
        if restart:
            self._restart_monitoring()

    def _ensure_monitoring(self):
        if (
            self._recording
            or self._starting
            or not self._dock_visible()
            or not self._backend_available()
            or not self.mic_card.isChecked()
        ):
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

    def _dock_visible(self):
        if not self.isVisible():
            return False
        dock = self.parentWidget()
        while dock is not None:
            if getattr(dock, "objectName", lambda: "")() == "dockAudioRecording":
                return dock.isVisible()
            dock = dock.parentWidget()
        return True

    def deactivate_if_hidden(self):
        if self._recording or self._starting:
            return
        self._stop_monitoring()
        self._stop_webcam_preview()

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
        self.activate_if_visible()

    def activate_if_visible(self):
        if self._activation_pending or not self._dock_visible():
            return
        self._activation_pending = True
        QTimer.singleShot(0, self._activate_after_show)

    def _activate_after_show(self):
        self._activation_pending = False
        if not self._dock_visible():
            return
        self._set_wait_cursor(True)
        started = time.monotonic()
        try:
            self.refresh_devices()
            self.refresh_cameras()
            self.refresh_tracks()
            self._sync_channel_options()
            self._sync_backend_state()
            if self._dock_visible():
                self._ensure_monitoring()
                self._restart_webcam_preview()
        finally:
            log.debug("Recording dock activation took %.3fs", time.monotonic() - started)
            self._set_wait_cursor(False)

    def hideEvent(self, event):
        if self._hiding_openshot_window:
            super().hideEvent(event)
            return
        if not self._recording:
            if self._starting:
                self._cancel_starting(restart_monitoring=False)
            self.deactivate_if_hidden()
        super().hideEvent(event)
