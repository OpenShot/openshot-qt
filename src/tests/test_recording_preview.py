"""
 @file
 @brief Tests for recording preview and live thumbnail helpers.
"""

import os
import shutil
import sys
import tempfile
import types
import unittest
from unittest.mock import MagicMock, call, patch


PATH = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if PATH not in sys.path:
    sys.path.append(PATH)

from qt_api import QByteArray, QCoreApplication, QSize, Qt
from qt_api import QApplication

from tests.qt_test_app import ensure_app_state as ensure_qt_app_state, get_or_create_app

QCoreApplication.setAttribute(Qt.AA_ShareOpenGLContexts, True)


class DummySettings:
    def __init__(self):
        self.values = {
            "default-profile": "HD 720p 30 fps",
            "default-samplerate": 48000,
            "default-channels": 2,
            "default-image-length": 10.0,
        }

    def get(self, key):
        return self.values.get(key)


class DummyApp(QApplication):
    def __init__(self):
        super().__init__([])
        self.settings = DummySettings()

    def get_settings(self):
        return self.settings

    def _tr(self, text):
        return text


def ensure_app_state(app):
    return ensure_qt_app_state(app, DummySettings)


class RecordingPreviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app, cls._owns_app = get_or_create_app(DummyApp)
        cls.app = ensure_app_state(app)
        import windows.audio_recording as audio_recording_module
        import windows.recording_widgets as recording_widgets_module
        import windows.views.timeline as timeline_module
        cls.audio_recording_module = audio_recording_module
        cls.recording_widgets_module = recording_widgets_module
        cls.timeline_module = timeline_module

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "_owns_app", False) and cls.app:
            cls.app.quit()

    def test_recording_preview_file_id_sanitizes_source(self):
        helper = self.audio_recording_module

        self.assertEqual(
            helper.recording_preview_file_id("session-1", "screen capture"),
            "recording-preview-session-1-screen-capture",
        )
        self.assertEqual(
            helper.recording_preview_file_id("session-1", ""),
            "recording-preview-session-1-source",
        )

    def test_recording_dock_starts_with_microphone_unselected(self):
        helper = self.audio_recording_module
        content_class = helper.AudioRecordingDockContent
        with patch.object(content_class, "_sync_source_availability"), \
                patch.object(content_class, "_webcam_layout_changed"), \
                patch.object(content_class, "_sync_backend_state"):
            dock = content_class(types.SimpleNamespace())
        try:
            self.assertFalse(dock.mic_card.isChecked())
            self.assertFalse(dock.mic_section.property("active"))
            self.assertFalse(dock.mic_section.advanced_button.isEnabled())
        finally:
            dock.deleteLater()

    def test_recording_button_requires_selected_source_while_idle(self):
        helper = self.audio_recording_module

        class FakeButton:
            def setEnabled(self, enabled):
                self.enabled = enabled

            def setText(self, text):
                self.text = text

            def setStyleSheet(self, stylesheet):
                self.stylesheet = stylesheet

            def setToolTip(self, tooltip):
                self.tooltip = tooltip

        selected = {"mic": False}
        dock = types.SimpleNamespace(
            mic_card=types.SimpleNamespace(isChecked=lambda: selected["mic"]),
            screen_card=types.SimpleNamespace(isChecked=lambda: False),
            camera_card=types.SimpleNamespace(isChecked=lambda: False),
            record_button=FakeButton(),
        )
        dock._has_selected_recording_source = lambda: (
            helper.AudioRecordingDockContent._has_selected_recording_source(dock)
        )

        helper.AudioRecordingDockContent._set_record_button_idle(dock)
        self.assertFalse(dock.record_button.enabled)
        self.assertIn("Select at least one", dock.record_button.tooltip)
        self.assertIn("QPushButton:disabled", dock.record_button.stylesheet)

        selected["mic"] = True
        helper.AudioRecordingDockContent._set_record_button_idle(dock)
        self.assertTrue(dock.record_button.enabled)
        self.assertEqual(dock.record_button.tooltip, "")

    def test_recording_dock_idle_activation_skips_device_discovery(self):
        helper = self.audio_recording_module
        dock = types.SimpleNamespace(
            _activation_pending=True,
            mic_card=types.SimpleNamespace(isChecked=lambda: False),
            camera_card=types.SimpleNamespace(isChecked=lambda: False),
            _dock_visible=lambda: True,
            refresh_tracks=MagicMock(),
            _sync_backend_state=MagicMock(),
            _refresh_source_devices=MagicMock(),
            _ensure_monitoring=MagicMock(),
            _restart_webcam_preview=MagicMock(),
        )

        helper.AudioRecordingDockContent._activate_after_show(dock)

        self.assertFalse(dock._activation_pending)
        dock.refresh_tracks.assert_called_once_with()
        dock._refresh_source_devices.assert_called_once_with(
            microphone=False,
            camera=False,
        )
        dock._ensure_monitoring.assert_called_once_with()
        dock._restart_webcam_preview.assert_called_once_with()

    def test_recording_source_discovery_runs_only_for_requested_source(self):
        helper = self.audio_recording_module
        dock = types.SimpleNamespace(
            _set_wait_cursor=MagicMock(),
            refresh_devices=MagicMock(),
            _sync_channel_options=MagicMock(),
            refresh_cameras=MagicMock(),
        )

        helper.AudioRecordingDockContent._refresh_source_devices(
            dock, microphone=True
        )

        dock.refresh_devices.assert_called_once_with()
        dock._sync_channel_options.assert_called_once_with()
        dock.refresh_cameras.assert_not_called()
        self.assertEqual(
            dock._set_wait_cursor.call_args_list,
            [call(True), call(False)],
        )

    def test_webcam_source_stays_selectable_until_lazy_discovery_runs(self):
        helper = self.audio_recording_module
        dock = types.SimpleNamespace(
            mic_card=types.SimpleNamespace(setAvailable=MagicMock()),
            screen_card=types.SimpleNamespace(setAvailable=MagicMock()),
            camera_card=types.SimpleNamespace(setAvailable=MagicMock()),
            _screen_backend_available=lambda: False,
            _camera_backend_available=lambda: True,
            _camera_device_available=lambda: False,
            _sync_screen_backend_ui=MagicMock(),
            _camera_devices_refreshed=False,
        )

        helper.AudioRecordingDockContent._sync_source_availability(dock)

        dock.camera_card.setAvailable.assert_called_once_with(True, "")

        dock.camera_card.setAvailable.reset_mock()
        dock._camera_devices_refreshed = True
        helper.AudioRecordingDockContent._sync_source_availability(dock)

        available, tooltip = dock.camera_card.setAvailable.call_args.args
        self.assertFalse(available)
        self.assertIn("No webcam", tooltip)

    def test_webcam_preview_stop_closes_reader_before_joining_worker(self):
        helper = self.audio_recording_module
        released = helper.threading.Event()

        class BlockingReader:
            def __init__(self):
                self.closed = False

            def Close(self):
                self.closed = True
                released.set()

        reader = BlockingReader()
        job = helper.WebcamPreviewJob("", 640, 480)
        job._reader = reader
        job._thread = helper.threading.Thread(target=released.wait, daemon=True)
        job._thread.start()

        job.stop()

        self.assertTrue(reader.closed)
        self.assertFalse(job._thread.is_alive())

    def test_xdotool_window_picker_rejects_invalid_window_id(self):
        helper = self.recording_widgets_module
        selected = types.SimpleNamespace(stdout="123;touch /tmp/not-safe\n")

        with patch.object(helper.shutil, "which", return_value="/usr/bin/xdotool"), \
                patch.object(helper.subprocess, "run", return_value=selected) as run:
            self.assertIsNone(helper.pick_x11_window_with_xdotool())

        run.assert_called_once_with(
            ["xdotool", "selectwindow"],
            check=True,
            text=True,
            capture_output=True,
            timeout=30,
        )

    def test_screen_capture_backend_uses_libopenshot_default_backend(self):
        helper = self.audio_recording_module

        class FakeReader:
            @staticmethod
            def DefaultBackend():
                return 2

            @staticmethod
            def IsBackendSupported(backend):
                return backend == 2

        fake_openshot = types.SimpleNamespace(
            ScreenCaptureReader=FakeReader,
            ScreenCaptureSettings=object,
            SCREEN_CAPTURE_AUTO=0,
            SCREEN_CAPTURE_X11=1,
            SCREEN_CAPTURE_WAYLAND=2,
        )

        with patch.object(helper.sys, "platform", "linux"), patch.object(helper, "openshot", fake_openshot):
            self.assertEqual(helper.screen_capture_backend(), 2)
            self.assertTrue(helper.screen_capture_backend_is_wayland())
            self.assertTrue(helper.screen_capture_backend_supported())

    def test_screen_capture_auto_backend_does_not_enable_screen_source(self):
        helper = self.audio_recording_module

        class FakeReader:
            @staticmethod
            def DefaultBackend():
                return 0

            @staticmethod
            def IsBackendSupported(backend):
                return backend == 0

        fake_openshot = types.SimpleNamespace(
            ScreenCaptureReader=FakeReader,
            ScreenCaptureSettings=object,
            SCREEN_CAPTURE_AUTO=0,
            SCREEN_CAPTURE_X11=1,
            SCREEN_CAPTURE_WAYLAND=2,
        )

        with patch.object(helper.sys, "platform", "linux"), patch.object(helper, "openshot", fake_openshot):
            self.assertEqual(helper.screen_capture_backend(), 0)
            self.assertFalse(helper.screen_capture_backend_supported())

    def test_screen_capture_backend_requires_explicit_wayland_support(self):
        helper = self.audio_recording_module

        fake_openshot = types.SimpleNamespace(
            ScreenCaptureReader=object,
            ScreenCaptureSettings=object,
            SCREEN_CAPTURE_AUTO=0,
            SCREEN_CAPTURE_X11=1,
            SCREEN_CAPTURE_WAYLAND=2,
        )

        with patch.object(helper.sys, "platform", "linux"), patch.object(helper, "openshot", fake_openshot):
            with patch.dict(helper.os.environ, {"XDG_SESSION_TYPE": "wayland"}, clear=False):
                self.assertEqual(helper.screen_capture_backend(), 2)
                self.assertFalse(helper.screen_capture_backend_supported())

    def test_windows_screen_capture_backend_uses_gdi_when_supported(self):
        helper = self.audio_recording_module

        class FakeReader:
            @staticmethod
            def DefaultBackend():
                return 3

            @staticmethod
            def IsBackendSupported(backend):
                return backend == 3

        fake_openshot = types.SimpleNamespace(
            ScreenCaptureReader=FakeReader,
            ScreenCaptureSettings=object,
            SCREEN_CAPTURE_AUTO=0,
            SCREEN_CAPTURE_X11=1,
            SCREEN_CAPTURE_WAYLAND=2,
            SCREEN_CAPTURE_WINDOWS_GDI=3,
        )

        with patch.object(helper.sys, "platform", "win32"), patch.object(helper, "openshot", fake_openshot):
            self.assertEqual(helper.screen_capture_backend(), 3)
            self.assertTrue(helper.screen_capture_backend_is_windows())
            self.assertTrue(helper.screen_capture_backend_supported())

    def test_live_thumbnail_cache_saves_only_grid_frames_once(self):
        helper = self.audio_recording_module
        temp_dir = tempfile.mkdtemp()
        calls = []

        def fake_save(self, frame, path):
            calls.append((frame, path, self.thumb_width, self.thumb_height))
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as output:
                output.write(b"png")

        try:
            with patch.object(helper.info, "THUMBNAIL_PATH", temp_dir), patch.object(
                helper.LiveRecordingThumbnailCache,
                "_save_thumbnail_from_frame",
                fake_save,
            ):
                cache = helper.LiveRecordingThumbnailCache(
                    "temp-file",
                    8.0,
                    thumb_size=QSize(64, 36),
                )

                self.assertTrue(cache.save_frame("frame-1", 1).endswith(os.path.join("temp-file", "1.png")))
                self.assertEqual(cache.save_frame("frame-2", 2), "")
                self.assertTrue(cache.save_frame("frame-3", 3).endswith(os.path.join("temp-file", "3.png")))
                self.assertTrue(cache.save_frame("frame-3b", 3).endswith(os.path.join("temp-file", "3.png")))

            self.assertEqual([call[0] for call in calls], ["frame-1", "frame-3"])
            self.assertEqual(calls[0][2:4], (64, 36))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_live_thumbnail_cache_copies_temp_folder_to_final_file_id(self):
        helper = self.audio_recording_module
        temp_dir = tempfile.mkdtemp()
        try:
            with patch.object(helper.info, "THUMBNAIL_PATH", temp_dir):
                source_dir = os.path.join(temp_dir, "temp-file")
                os.makedirs(source_dir)
                with open(os.path.join(source_dir, "1.png"), "wb") as output:
                    output.write(b"one")
                with open(os.path.join(source_dir, "note.txt"), "w") as output:
                    output.write("skip")

                copied = helper.LiveRecordingThumbnailCache("temp-file", 30.0).copy_to_file_id("final-file")

            self.assertEqual(copied, 1)
            with open(os.path.join(temp_dir, "final-file", "1.png"), "rb") as copied_file:
                self.assertEqual(copied_file.read(), b"one")
            self.assertFalse(os.path.exists(os.path.join(temp_dir, "final-file", "note.txt")))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_live_video_recording_preserves_elapsed_frame_numbers(self):
        helper = self.audio_recording_module

        class FakeFrame:
            def __init__(self):
                self.number = 0

            def SetFrameNumber(self, frame_number):
                self.number = frame_number

        class FakeReader:
            def GetFrame(self, _frame_number):
                return FakeFrame()

        class FakeWriter:
            def __init__(self, job):
                self.job = job
                self.frame_numbers = []

            def WriteFrame(self, frame):
                self.frame_numbers.append(frame.number)
                if frame.number >= 31:
                    self.job._stop.set()

        fps = types.SimpleNamespace(num=30, den=1)
        job = helper.LiveVideoRecordingJob(FakeReader(), "screen.mp4", 640, 480, fps)
        writer = FakeWriter(job)
        job._writer = writer
        job.begin(100.0)

        with patch.object(helper.time, "monotonic", side_effect=[100.0, 100.5, 101.0]):
            job._run()

        self.assertEqual(writer.frame_numbers, [1, 16, 31])
        self.assertEqual(job.frames, 31)

    def test_live_video_writer_enables_audio_for_screen_reader_audio(self):
        helper = self.audio_recording_module

        class FakeFrame:
            def GetWidth(self):
                return 640

            def GetHeight(self):
                return 360

        class FakeReader:
            info = types.SimpleNamespace(
                width=640,
                height=360,
                fps=types.SimpleNamespace(num=30, den=1),
                has_audio=True,
                sample_rate=48000,
                channels=2,
            )

            def Open(self):
                pass

            def GetFrame(self, _number):
                return FakeFrame()

        class FakeWriter:
            instance = None

            def __init__(self, path):
                self.path = path
                self.audio_options = None
                FakeWriter.instance = self

            def SetVideoOptions(self, *args):
                pass

            def SetAudioOptions(self, *args):
                self.audio_options = args

            def Open(self):
                pass

        fps = types.SimpleNamespace(num=30, den=1)
        job = helper.LiveVideoRecordingJob(FakeReader(), "screen.mp4", 640, 360, fps)
        with patch.object(helper.openshot, "FFmpegWriter", FakeWriter):
            job._open()

        self.assertEqual(
            FakeWriter.instance.audio_options,
            (True, "aac", 48000, 2, helper.openshot.LAYOUT_STEREO, 192000),
        )

    def test_live_video_recording_drops_frames_that_arrive_before_next_fps_slot(self):
        helper = self.audio_recording_module
        frame_times = [100.0, 100.010, 100.020, 100.0334, 100.050, 100.0667, 100.100]

        class FakeFrame:
            def __init__(self):
                self.number = 0

            def SetFrameNumber(self, frame_number):
                self.number = frame_number

        class FakeReader:
            def __init__(self):
                self.job = None
                self.frames_read = 0
                self.audio_frames = []
                self.audio_reset = False

            def GetFrame(self, _frame_number):
                self.frames_read += 1
                if self.job and self.frames_read >= len(frame_times):
                    self.job._stop.set()
                return FakeFrame()

            def ResetSystemAudio(self):
                self.audio_reset = True

            def AddSystemAudio(self, _frame, frame_number):
                self.audio_frames.append(frame_number)

        class FakeWriter:
            def __init__(self):
                self.frame_numbers = []

            def WriteFrame(self, frame):
                self.frame_numbers.append(frame.number)

        fps = types.SimpleNamespace(num=30, den=1)
        reader = FakeReader()
        job = helper.LiveVideoRecordingJob(reader, "screen.mp4", 640, 480, fps)
        reader.job = job
        writer = FakeWriter()
        job._writer = writer
        job.begin(100.0)

        with patch.object(helper.time, "monotonic", side_effect=frame_times):
            job._run()

        self.assertEqual(writer.frame_numbers, [1, 2, 3, 4])
        self.assertTrue(reader.audio_reset)
        self.assertEqual(reader.audio_frames, [1, 2, 3, 4])

    def test_live_video_recording_discards_prestart_initial_frame(self):
        helper = self.audio_recording_module

        class FakeFrame:
            def __init__(self, label):
                self.label = label
                self.number = 0

            def SetFrameNumber(self, frame_number):
                self.number = frame_number

        class FakeReader:
            def GetFrame(self, _frame_number):
                return FakeFrame("fresh")

        class FakeWriter:
            def __init__(self, job):
                self.job = job
                self.frames = []

            def WriteFrame(self, frame):
                self.frames.append((frame.label, frame.number))
                self.job._stop.set()

        fps = types.SimpleNamespace(num=30, den=1)
        job = helper.LiveVideoRecordingJob(FakeReader(), "webcam.mp4", 640, 480, fps)
        writer = FakeWriter(job)
        job._writer = writer
        job._initial_frame = FakeFrame("stale")
        job._initial_frame_time = 99.0
        job.begin(100.0)

        with patch.object(helper.time, "monotonic", return_value=100.0):
            job._run()

        self.assertEqual(writer.frames, [("fresh", 1)])

    def test_live_video_recording_drops_queued_source_frames_before_start(self):
        helper = self.audio_recording_module

        class FakeFrame:
            def __init__(self, label, capture_timestamp):
                self.label = label
                self.capture_timestamp = capture_timestamp
                self.number = 0

            def SetFrameNumber(self, frame_number):
                self.number = frame_number

        class FakeReader:
            def __init__(self):
                self.frames = [
                    FakeFrame("queued-1", 10.033),
                    FakeFrame("queued-2", 10.066),
                    FakeFrame("live-1", 10.300),
                    FakeFrame("live-2", 10.333),
                ]

            def GetFrame(self, _frame_number):
                return self.frames.pop(0)

        class FakeWriter:
            def __init__(self, job):
                self.job = job
                self.frames = []

            def WriteFrame(self, frame):
                self.frames.append((frame.label, frame.number))
                if len(self.frames) >= 2:
                    self.job._stop.set()

        fps = types.SimpleNamespace(num=30, den=1)
        reader = FakeReader()
        job = helper.LiveVideoRecordingJob(reader, "webcam.mp4", 640, 480, fps)
        writer = FakeWriter(job)
        job._writer = writer
        job._initial_frame = FakeFrame("stale", 10.0)
        job._initial_frame_time = 100.0
        job._initial_capture_timestamp = 10.0
        job.begin(100.3)

        with patch.object(helper.time, "monotonic", return_value=100.3):
            job._run()

        self.assertEqual(writer.frames, [("live-1", 1), ("live-2", 2)])

    def test_live_video_stop_closes_reader_to_unblock_and_finalizes_writer(self):
        helper = self.audio_recording_module

        class FakeReader:
            def __init__(self):
                self.closed = False

            def Close(self):
                self.closed = True

        class FakeWriter:
            def __init__(self):
                self.closed = False

            def Close(self):
                self.closed = True

        class FakeThread:
            def __init__(self):
                self.joins = 0

            def join(self, timeout=None):
                self.joins += 1

            def is_alive(self):
                return self.joins < 2

        reader = FakeReader()
        writer = FakeWriter()
        fps = types.SimpleNamespace(num=30, den=1)
        job = helper.LiveVideoRecordingJob(reader, "screen.mp4", 640, 480, fps)
        job._thread = FakeThread()
        job._writer = writer

        job.stop()

        self.assertTrue(reader.closed)
        self.assertTrue(writer.closed)
        self.assertIsNone(job._writer)

    def test_stop_video_jobs_requests_shared_stop_before_finalize(self):
        helper = self.audio_recording_module
        calls = []

        class FakeJob:
            path = "screen.mp4"
            error = None

            def __init__(self, name):
                self.name = name

            def request_stop(self, stop_time):
                calls.append(("request", self.name, stop_time))

            def finish_stop(self):
                calls.append(("finish", self.name, None))

        dock = types.SimpleNamespace(_video_jobs=[FakeJob("screen"), FakeJob("webcam")])

        helper.AudioRecordingDockContent._stop_video_jobs(dock, stop_time=123.45)

        self.assertEqual(calls[:2], [("request", "screen", 123.45), ("request", "webcam", 123.45)])
        self.assertEqual(calls[2:], [("finish", "screen", None), ("finish", "webcam", None)])
        self.assertEqual(dock._video_jobs, [])

    def test_live_video_write_uses_write_frame_at_when_available(self):
        helper = self.audio_recording_module

        class FakeFrame:
            def __init__(self):
                self.number = 0

            def SetFrameNumber(self, frame_number):
                self.number = frame_number

        class FakeWriter:
            def __init__(self):
                self.frame_numbers = []

            def WriteFrameAt(self, frame, frame_number):
                self.frame_numbers.append((frame.number, frame_number))

        fps = types.SimpleNamespace(num=30, den=1)
        job = helper.LiveVideoRecordingJob(object(), "screen.mp4", 640, 480, fps)
        writer = FakeWriter()
        job._writer = writer
        frame = FakeFrame()

        job._write_numbered_frame(frame, 42)

        self.assertEqual(writer.frame_numbers, [(42, 42)])

    def test_live_video_stop_does_not_write_final_gap_frames(self):
        helper = self.audio_recording_module

        class FakeFrame:
            def __init__(self):
                self.number = 0

            def SetFrameNumber(self, frame_number):
                self.number = frame_number

        class FakeWriter:
            def __init__(self):
                self.frame_numbers = []
                self.closed = False

            def WriteFrame(self, frame):
                self.frame_numbers.append(frame.number)

            def Close(self):
                self.closed = True

        class FakeReader:
            def Close(self):
                pass

        fps = types.SimpleNamespace(num=30, den=1)
        job = helper.LiveVideoRecordingJob(FakeReader(), "screen.mp4", 640, 480, fps)
        writer = FakeWriter()
        job._writer = writer
        job._start_time = 100.0
        job._last_output_frame_number = 31
        job._last_frame = FakeFrame()
        job._last_frame.SetFrameNumber(31)

        with patch.object(helper.time, "monotonic", return_value=110.0):
            job.stop()

        self.assertIsNone(job._writer)
        self.assertTrue(writer.closed)
        self.assertEqual(writer.frame_numbers, [])
        self.assertEqual(job.frames, 0)

    def test_live_video_wait_until_opened_times_out_and_closes_reader(self):
        helper = self.audio_recording_module

        class FakeReader:
            def __init__(self):
                self.closed = False

            def Close(self):
                self.closed = True

        reader = FakeReader()
        fps = types.SimpleNamespace(num=30, den=1)
        job = helper.LiveVideoRecordingJob(reader, "screen.mp4", 640, 480, fps)

        with self.assertRaises(RuntimeError):
            job.wait_until_opened(timeout=0.01)

        self.assertTrue(reader.closed)
        self.assertTrue(job._stop.is_set())

    def test_recording_duration_keeps_existing_media_duration(self):
        helper = self.audio_recording_module

        class FakeFile:
            def __init__(self):
                self.data = {
                    "duration": 1.0,
                    "end": 1.0,
                    "video_length": 30,
                    "has_video": True,
                    "has_audio": False,
                    "media_type": "video",
                }
                self.saved = False

            def save(self):
                self.saved = True

        fake_file = FakeFile()
        fake_app = types.SimpleNamespace(
            project=types.SimpleNamespace(get=lambda key: {"num": 30, "den": 1} if key == "fps" else None)
        )
        dock = types.SimpleNamespace(_recorded_duration=2.49)

        with patch.object(helper.File, "get", return_value=fake_file), patch.object(helper, "get_app", return_value=fake_app):
            helper.AudioRecordingDockContent._apply_recording_duration(dock, "mic.wav")

        self.assertFalse(fake_file.saved)
        self.assertEqual(fake_file.data["duration"], 1.0)
        self.assertEqual(fake_file.data["end"], 1.0)
        self.assertEqual(fake_file.data["video_length"], 30)

    def test_webcam_layout_defaults_follow_screen_selection(self):
        helper = self.audio_recording_module

        class FakeCard:
            def __init__(self, checked):
                self.checked = checked

            def isChecked(self):
                return self.checked

        class FakeCombo:
            def __init__(self, values, current):
                self.values = list(values)
                self.index = self.values.index(current)

            def findData(self, value):
                try:
                    return self.values.index(value)
                except ValueError:
                    return -1

            def currentIndex(self):
                return self.index

            def setCurrentIndex(self, index):
                self.index = index

            def currentData(self):
                return self.values[self.index]

        dock = types.SimpleNamespace(
            camera_card=FakeCard(True),
            screen_card=FakeCard(False),
            webcam_layout_combo=FakeCombo(["bottom-right", "full"], "bottom-right"),
            webcam_layout_size_combo=FakeCombo([0.2, 0.3, 0.4], 0.4),
            webcam_corner_radius_combo=FakeCombo([0.0, 0.15, 0.5], 0.15),
            _webcam_layout_default_state=None,
        )
        dock._set_combo_data = lambda combo, value: helper.AudioRecordingDockContent._set_combo_data(dock, combo, value)

        helper.AudioRecordingDockContent._sync_webcam_layout_defaults(dock)

        self.assertEqual(dock.webcam_layout_combo.currentData(), "full")
        self.assertEqual(dock.webcam_corner_radius_combo.currentData(), 0.0)
        self.assertEqual(helper.AudioRecordingDockContent._webcam_layout(dock), "full")
        self.assertEqual(helper.AudioRecordingDockContent._webcam_corner_radius(dock), 0.0)

        dock.screen_card.checked = True
        helper.AudioRecordingDockContent._sync_webcam_layout_defaults(dock)

        self.assertEqual(dock.webcam_layout_combo.currentData(), "bottom-right")
        self.assertEqual(dock.webcam_layout_size_combo.currentData(), 0.3)
        self.assertEqual(dock.webcam_corner_radius_combo.currentData(), 0.15)

        dock.webcam_layout_combo.setCurrentIndex(dock.webcam_layout_combo.findData("full"))
        helper.AudioRecordingDockContent._sync_webcam_layout_defaults(dock)

        self.assertEqual(dock.webcam_layout_combo.currentData(), "full")

    def test_screen_recording_forces_preview_off_then_restores_it(self):
        helper = self.audio_recording_module

        class FakeCard:
            checked = False

            def isChecked(self):
                return self.checked

        class FakeCombo:
            values = ["none", "full", "half", "quarter"]

            def __init__(self):
                self.index = self.values.index("half")
                self.enabled = True

            def currentData(self):
                return self.values[self.index]

            def currentIndex(self):
                return self.index

            def findData(self, value):
                return self.values.index(value)

            def setCurrentIndex(self, index):
                self.index = index

            def setEnabled(self, enabled):
                self.enabled = enabled

        card = FakeCard()
        combo = FakeCombo()
        label = types.SimpleNamespace(setEnabled=lambda enabled: setattr(label, "enabled", enabled))
        dock = types.SimpleNamespace(
            screen_card=card,
            preview_combo=combo,
            preview_label=label,
            _preview_before_screen="full",
            _preview_forced_off=False,
        )
        dock._set_combo_data = lambda target, value: helper.AudioRecordingDockContent._set_combo_data(dock, target, value)

        card.checked = True
        helper.AudioRecordingDockContent._sync_preview_control(dock)
        self.assertEqual(combo.currentData(), "none")
        self.assertFalse(combo.enabled)
        self.assertFalse(label.enabled)

        card.checked = False
        helper.AudioRecordingDockContent._sync_preview_control(dock)
        self.assertEqual(combo.currentData(), "half")
        self.assertTrue(combo.enabled)
        self.assertTrue(label.enabled)

    def test_recording_only_stops_playback_it_started(self):
        helper = self.audio_recording_module
        pause_calls = []
        dock = types.SimpleNamespace(
            _timeline_playback_started=True,
            _playback_active=lambda: True,
            window=types.SimpleNamespace(
                PauseSignal=types.SimpleNamespace(emit=lambda: pause_calls.append(True)),
            ),
        )

        helper.AudioRecordingDockContent._stop_timeline_playback(dock)
        helper.AudioRecordingDockContent._stop_timeline_playback(dock)

        self.assertEqual(pause_calls, [True])
        self.assertFalse(dock._timeline_playback_started)

    def test_recording_start_context_is_consumed_once(self):
        helper = self.audio_recording_module
        playhead = {"position": 20.0}
        dock = types.SimpleNamespace(
            _context_start=5.0,
            _recording_timeline_position=0.0,
            _current_playhead_seconds=lambda: playhead["position"],
        )

        first = helper.AudioRecordingDockContent._capture_recording_timeline_position(dock)
        self.assertEqual(first, 5.0)
        self.assertIsNone(dock._context_start)

        playhead["position"] = 30.0
        second = helper.AudioRecordingDockContent._capture_recording_timeline_position(dock)
        self.assertEqual(second, 30.0)
        self.assertEqual(dock._recording_timeline_position, 30.0)

    def test_restore_hidden_openshot_maximized_window_keeps_maximized_state(self):
        helper = self.audio_recording_module

        class FakeWindow:
            def __init__(self):
                self.calls = []

            def restoreGeometry(self, geometry):
                self.calls.append(("restoreGeometry", bytes(geometry)))

            def showFullScreen(self):
                self.calls.append("showFullScreen")

            def showMaximized(self):
                self.calls.append("showMaximized")

            def showNormal(self):
                self.calls.append("showNormal")

            def raise_(self):
                self.calls.append("raise")

            def activateWindow(self):
                self.calls.append("activateWindow")

        window = FakeWindow()
        dock = types.SimpleNamespace(window=window)
        state = {
            "window_state": Qt.WindowMaximized,
            "geometry": QByteArray(b"saved-geometry"),
        }

        helper.AudioRecordingDockContent._restore_openshot_window(dock, state)

        self.assertEqual(window.calls[:3], ["showMaximized", "raise", "activateWindow"])
        self.assertNotIn(("restoreGeometry", b"saved-geometry"), window.calls)

    def test_restore_hidden_openshot_normal_window_restores_geometry(self):
        helper = self.audio_recording_module

        class FakeWindow:
            def __init__(self):
                self.calls = []

            def restoreGeometry(self, geometry):
                self.calls.append(("restoreGeometry", bytes(geometry)))

            def showFullScreen(self):
                self.calls.append("showFullScreen")

            def showMaximized(self):
                self.calls.append("showMaximized")

            def showNormal(self):
                self.calls.append("showNormal")

            def raise_(self):
                self.calls.append("raise")

            def activateWindow(self):
                self.calls.append("activateWindow")

        window = FakeWindow()
        dock = types.SimpleNamespace(window=window)
        state = {
            "window_state": Qt.WindowNoState,
            "geometry": QByteArray(b"saved-geometry"),
        }

        helper.AudioRecordingDockContent._restore_openshot_window(dock, state)

        self.assertEqual(
            window.calls[:4],
            [("restoreGeometry", b"saved-geometry"), "showNormal", "raise", "activateWindow"],
        )

    def test_webcam_corner_layout_uses_native_margin_and_corner_radius(self):
        helper = self.audio_recording_module

        class FakeCard:
            def __init__(self, checked):
                self.checked = checked

            def isChecked(self):
                return self.checked

        class FakeCombo:
            def __init__(self, value):
                self.value = value

            def currentData(self):
                return self.value

        dock = types.SimpleNamespace(
            screen_card=FakeCard(True),
            webcam_layout_combo=FakeCombo("bottom-right"),
            webcam_layout_size_combo=FakeCombo(0.3),
            webcam_corner_radius_combo=FakeCombo(0.15),
            _keyframe_point=lambda value: {"co": {"X": 1.0, "Y": float(value)}},
        )
        dock._webcam_layout = lambda: helper.AudioRecordingDockContent._webcam_layout(dock)
        dock._webcam_layout_scale = lambda: helper.AudioRecordingDockContent._webcam_layout_scale(dock)
        dock._webcam_corner_radius = lambda: helper.AudioRecordingDockContent._webcam_corner_radius(dock)
        clip_data = {}

        helper.AudioRecordingDockContent._apply_webcam_clip_layout(dock, clip_data)

        self.assertEqual(clip_data["scale_x"]["Points"][0]["co"]["Y"], 0.3)
        self.assertEqual(clip_data["scale_y"]["Points"][0]["co"]["Y"], 0.3)
        self.assertEqual(clip_data["scale"], helper.openshot.SCALE_FIT)
        self.assertEqual(clip_data["margin"]["Points"][0]["co"]["Y"], 0.03)
        self.assertEqual(clip_data["corner_radius"]["Points"][0]["co"]["Y"], 0.15)
        self.assertNotIn("effects", clip_data)

    def test_webcam_full_layout_uses_best_fit_not_stretch(self):
        helper = self.audio_recording_module

        class FakeCard:
            def __init__(self, checked):
                self.checked = checked

            def isChecked(self):
                return self.checked

        class FakeCombo:
            def __init__(self, value):
                self.value = value

            def currentData(self):
                return self.value

        dock = types.SimpleNamespace(
            screen_card=FakeCard(False),
            webcam_layout_combo=FakeCombo("full"),
            webcam_layout_size_combo=FakeCombo(0.3),
            webcam_corner_radius_combo=FakeCombo(0.15),
            _keyframe_point=lambda value: {"co": {"X": 1.0, "Y": float(value)}},
        )
        dock._webcam_layout = lambda: helper.AudioRecordingDockContent._webcam_layout(dock)
        dock._webcam_layout_scale = lambda: helper.AudioRecordingDockContent._webcam_layout_scale(dock)
        dock._webcam_corner_radius = lambda: helper.AudioRecordingDockContent._webcam_corner_radius(dock)
        clip_data = {"scale": helper.openshot.SCALE_STRETCH}

        helper.AudioRecordingDockContent._apply_webcam_clip_layout(dock, clip_data)

        self.assertEqual(clip_data["gravity"], helper.openshot.GRAVITY_CENTER)
        self.assertEqual(clip_data["scale"], helper.openshot.SCALE_FIT)
        self.assertEqual(clip_data["scale_x"]["Points"][0]["co"]["Y"], 1.0)
        self.assertEqual(clip_data["scale_y"]["Points"][0]["co"]["Y"], 1.0)
        self.assertEqual(clip_data["margin"]["Points"][0]["co"]["Y"], 0.0)
        self.assertEqual(clip_data["corner_radius"]["Points"][0]["co"]["Y"], 0.0)

    def test_recording_clip_defaults_use_best_fit(self):
        helper = self.audio_recording_module
        dock = types.SimpleNamespace()
        clip_data = {"scale": helper.openshot.SCALE_STRETCH}

        helper.AudioRecordingDockContent._apply_recording_clip_defaults(dock, clip_data)

        self.assertEqual(clip_data["scale"], helper.openshot.SCALE_FIT)

    def test_recording_track_stack_creates_lower_tracks_when_needed(self):
        helper = self.audio_recording_module

        class FakeCombo:
            def currentData(self):
                return 2000000

        created = []
        fake_window = types.SimpleNamespace(
            create_track_below=lambda layer: created.append(max(1, int(layer / 2))) or created[-1]
        )
        fake_app = types.SimpleNamespace(window=fake_window)
        dock = types.SimpleNamespace(track_combo=FakeCombo())
        dock._available_recording_tracks = lambda: [2000000, 1000000]

        with patch.object(helper, "get_app", return_value=fake_app):
            tracks = helper.AudioRecordingDockContent._recording_track_stack(dock, 3)

        self.assertEqual(tracks, [2000000, 1000000, 500000])
        self.assertEqual(created, [500000])

    def test_screen_source_maps_to_backend_value(self):
        helper = self.audio_recording_module

        class FakeScreenCombo:
            def __init__(self, source):
                self.source = source

            def currentData(self):
                return self.source

        dock = types.SimpleNamespace(screen_display_edit=FakeScreenCombo({"display": ":0.0"}))
        dock._selected_screen_source = lambda: helper.AudioRecordingDockContent._selected_screen_source(dock)
        self.assertEqual(
            helper.AudioRecordingDockContent._screen_display_value(dock, ":1.0"),
            ":0.0",
        )

        dock.screen_display_edit.source = {}
        self.assertEqual(
            helper.AudioRecordingDockContent._screen_display_value(dock, ":1.0"),
            ":1.0",
        )

    def test_selected_screen_source_sets_full_screen_bounds(self):
        helper = self.audio_recording_module

        class FakeScreenCombo:
            def currentData(self):
                return {
                    "id": "screen-2",
                    "display": "desktop",
                    "x": 1920,
                    "y": 0,
                    "width": 1280,
                    "height": 720,
                    "all": False,
                }

        class FakeSpin:
            def __init__(self):
                self.value = None

            def setValue(self, value):
                self.value = value

        class FakeLabel:
            def __init__(self):
                self.text = ""

            def setText(self, text):
                self.text = text

        dock = types.SimpleNamespace(
            screen_display_edit=FakeScreenCombo(),
            screen_x_spin=FakeSpin(),
            screen_y_spin=FakeSpin(),
            screen_width_spin=FakeSpin(),
            screen_height_spin=FakeSpin(),
            screen_status_label=FakeLabel(),
        )
        dock._selected_screen_source = lambda: helper.AudioRecordingDockContent._selected_screen_source(dock)

        helper.AudioRecordingDockContent._set_screen_to_selected_source(dock)

        self.assertEqual(dock.screen_x_spin.value, 1920)
        self.assertEqual(dock.screen_y_spin.value, 0)
        self.assertEqual(dock.screen_width_spin.value, 1280)
        self.assertEqual(dock.screen_height_spin.value, 720)
        self.assertIn("1280x720", dock.screen_status_label.text)

    def test_timeline_recording_previews_build_audio_and_video_clip_data(self):
        timeline_module = self.timeline_module
        helper = types.SimpleNamespace(
            _recording_preview_clips=[],
            fps_float=30.0,
            geometry=types.SimpleNamespace(mark_dirty=lambda: setattr(helper, "dirty", True)),
            dirty=False,
            updated=False,
        )
        helper.update = lambda: setattr(helper, "updated", True)

        timeline_module.TimelineView.set_audio_recording_previews(helper, [
            {
                "id": "preview-mic",
                "source_type": "mic",
                "position": 12.0,
                "track": 2,
                "duration": 3.0,
                "audio_data": [0.1, 0.4],
                "audio_data_rms": [0.05, 0.2],
                "audio_data_rate": 200,
            },
            {
                "id": "preview-screen",
                "source_type": "screen",
                "position": 12.0,
                "track": 3,
                "duration": 3.0,
                "file_id": "temp-screen",
                "width": 1920,
                "height": 1080,
                "fps": 30.0,
            },
        ])

        self.assertTrue(helper.dirty)
        self.assertTrue(helper.updated)
        self.assertEqual(len(helper._recording_preview_clips), 2)

        mic_data = helper._recording_preview_clips[0].data
        self.assertEqual(mic_data["layer"], 2)
        self.assertTrue(mic_data["reader"]["has_audio"])
        self.assertFalse(mic_data["reader"]["has_video"])
        self.assertEqual(mic_data["ui"]["audio_data"], [0.1, 0.4])
        self.assertEqual(mic_data["ui"]["audio_data_rms"], [0.05, 0.2])
        self.assertEqual(mic_data["ui"]["audio_data_rate"], 200)
        self.assertEqual(mic_data["ui"]["audio_data_format"], "absolute_peak_v2")

        screen_data = helper._recording_preview_clips[1].data
        self.assertEqual(screen_data["file_id"], "temp-screen")
        self.assertEqual(screen_data["reader"]["id"], "temp-screen")
        self.assertTrue(screen_data["reader"]["has_video"])
        self.assertEqual(screen_data["reader"]["width"], 1920)
        self.assertEqual(screen_data["reader"]["video_length"], 90)


if __name__ == "__main__":
    unittest.main()
