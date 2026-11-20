"""
 @file
 @brief Targeted unit tests for Project Files export helpers.
"""

import importlib
import os
import sys
import types
import unittest


PATH = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if PATH not in sys.path:
    sys.path.append(PATH)

try:
    import openshot
except ModuleNotFoundError:
    openshot = types.SimpleNamespace(
        Fraction=lambda n, d: types.SimpleNamespace(num=n, den=d),
        FFmpegWriter=None,
        Clip=None,
    )
    sys.modules["openshot"] = openshot

from qt_api import QApplication
from tests.qt_test_app import ensure_app_state, get_or_create_app


class DummySettings:
    class actionType:
        EXPORT = "EXPORT"

    def __init__(self):
        self.default_path = "/default/export/path"

    def getDefaultPath(self, action):
        return self.default_path

    def setDefaultPath(self, action, path):
        self.default_path = path


class DummyApp(QApplication):
    def __init__(self):
        super().__init__([])

    def _tr(self, text):
        return text


class ExportClipsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app, cls._owns_app = get_or_create_app(DummyApp)
        cls.app = ensure_app_state(app, DummySettings)
        cls.export_clips = importlib.import_module("windows.export_clips")

    def test_image_sequence_detection_matches_printf_pattern(self):
        sequence = types.SimpleNamespace(data={"path": os.path.join("titles", "Title%04d.png")})
        normal_file = types.SimpleNamespace(data={"path": os.path.join("titles", "Title0001.png")})

        self.assertTrue(self.export_clips.isImageSequence(sequence))
        self.assertFalse(self.export_clips.isImageSequence(normal_file))

    def test_image_sequence_export_name_is_single_mp4(self):
        file_obj = types.SimpleNamespace(data={
            "path": os.path.join("titles", "Title%04d.png"),
            "fps": {"num": 25, "den": 1},
            "video_length": 300,
        })

        self.assertEqual(
            self.export_clips.nameOfImageSequenceExport(file_obj),
            "title [0.00 - 12.00].mp4",
        )

    def test_image_sequence_as_clip_sets_full_duration_range(self):
        file_obj = types.SimpleNamespace(data={
            "path": os.path.join("titles", "Title%04d.png"),
            "fps": {"num": 25, "den": 1},
            "video_length": 300,
            "width": 1920,
        })

        clip_obj = self.export_clips.imageSequenceAsClip(file_obj)

        self.assertEqual(clip_obj.data["start"], 0.0)
        self.assertEqual(clip_obj.data["end"], 12.0)
        self.assertEqual(clip_obj.data["path"], os.path.join("titles", "Title%04d.png"))
        self.assertEqual(clip_obj.data["width"], 1920)

    def test_setup_writer_disables_audio_for_silent_image_sequence(self):
        clip_obj = types.SimpleNamespace(data={
            "path": os.path.join("titles", "Title%04d.png"),
            "fps": {"num": 25, "den": 1},
            "pixel_ratio": {"num": 1, "den": 1},
            "width": 1920,
            "height": 1080,
            "has_audio": False,
            "sample_rate": 0,
            "channels": 0,
            "channel_layout": 0,
        })
        writer = types.SimpleNamespace(
            audio_options=None,
            video_options=None,
            prepare_count=0,
            opened=False,
        )
        writer.SetVideoOptions = lambda *args: setattr(writer, "video_options", args)
        writer.SetAudioOptions = lambda *args: setattr(writer, "audio_options", args)
        writer.PrepareStreams = lambda: setattr(writer, "prepare_count", writer.prepare_count + 1)
        writer.Open = lambda: setattr(writer, "opened", True)

        self.export_clips.setupWriter(clip_obj, writer)

        self.assertFalse(writer.audio_options[0])
        self.assertEqual(writer.audio_options[2], 48000)
        self.assertEqual(writer.audio_options[3], 2)
        self.assertEqual(writer.audio_options[4], 3)
        self.assertEqual(writer.prepare_count, 2)
        self.assertTrue(writer.opened)

    def test_get_destination_canceling_returns_false_and_clears_destination(self):
        # Reproduces issue #6063: cancelling target folder picker previously
        # fell back to default folder and exported anyway.
        win = self.export_clips.clipExportWindow.__new__(self.export_clips.clipExportWindow)
        from unittest.mock import patch
        with patch.object(self.export_clips.QFileDialog, "getExistingDirectory", return_value=""):
            result = win._getDestination()
        self.assertFalse(result)
        self.assertIsNone(win.export_destination)

    def test_get_destination_selected_returns_true_and_updates_settings(self):
        win = self.export_clips.clipExportWindow.__new__(self.export_clips.clipExportWindow)
        from unittest.mock import patch
        with patch.object(self.export_clips.QFileDialog, "getExistingDirectory", return_value="/new/export/folder"):
            result = win._getDestination()
        self.assertTrue(result)
        self.assertEqual(win.export_destination, "/new/export/folder")
        settings = self.app.get_settings()
        self.assertEqual(settings.getDefaultPath(settings.actionType.EXPORT), "/new/export/folder")

    def test_init_cancels_and_rejects_when_destination_dialog_canceled(self):
        from unittest.mock import Mock, patch
        scheduled = []
        with patch.object(self.export_clips.ui_util, "load_ui"), \
                patch.object(self.export_clips.QFileDialog, "getExistingDirectory", return_value=""), \
                patch.object(self.export_clips.QTimer, "singleShot", side_effect=lambda delay, func: scheduled.append(func)):
            win = self.export_clips.clipExportWindow([])
        self.assertTrue(win.canceled)
        self.assertIsNone(win.export_destination)
        self.assertIn(win.reject, scheduled)
        self.assertNotIn(win._exportPressed, scheduled)


if __name__ == "__main__":
    unittest.main()
