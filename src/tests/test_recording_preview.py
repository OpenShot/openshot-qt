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
from unittest.mock import patch


PATH = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if PATH not in sys.path:
    sys.path.append(PATH)

from qt_api import QCoreApplication, QSize, Qt
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
        import windows.views.timeline as timeline_module
        cls.audio_recording_module = audio_recording_module
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
                if len(self.frame_numbers) >= 3:
                    self.job._stop.set()

        fps = types.SimpleNamespace(num=30, den=1)
        job = helper.LiveVideoRecordingJob(FakeReader(), "screen.mp4", 640, 480, fps)
        writer = FakeWriter(job)
        job._writer = writer
        job._start_time = 100.0

        with patch.object(helper.time, "monotonic", side_effect=[100.0, 100.5, 101.0]):
            job._run()

        self.assertEqual(writer.frame_numbers, [1, 16, 31])
        self.assertEqual(job.frames, 31)

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

    def test_live_video_stop_writes_final_gap_frame(self):
        helper = self.audio_recording_module

        class FakeFrame:
            def __init__(self):
                self.number = 0

            def SetFrameNumber(self, frame_number):
                self.number = frame_number

            def DeepCopy(self):
                copied = FakeFrame()
                copied.number = self.number
                return copied

        class FakeWriter:
            def __init__(self):
                self.frame_numbers = []

            def WriteFrame(self, frame):
                self.frame_numbers.append(frame.number)

        fps = types.SimpleNamespace(num=30, den=1)
        job = helper.LiveVideoRecordingJob(object(), "screen.mp4", 640, 480, fps)
        writer = FakeWriter()
        job._writer = writer
        job._start_time = 100.0
        job._last_output_frame_number = 31
        job._last_frame = FakeFrame()
        job._last_frame.SetFrameNumber(31)

        with patch.object(helper.time, "monotonic", return_value=105.0):
            job._write_final_gap_frame()

        self.assertEqual(writer.frame_numbers, [151])
        self.assertEqual(job.frames, 151)

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

        screen_data = helper._recording_preview_clips[1].data
        self.assertEqual(screen_data["file_id"], "temp-screen")
        self.assertEqual(screen_data["reader"]["id"], "temp-screen")
        self.assertTrue(screen_data["reader"]["has_video"])
        self.assertEqual(screen_data["reader"]["width"], 1920)
        self.assertEqual(screen_data["reader"]["video_length"], 90)


if __name__ == "__main__":
    unittest.main()
