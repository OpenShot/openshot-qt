"""
 @file
 @brief Unit tests for export filename format extension handling (issue #6069)
"""

import importlib
import os
import sys
import types
import unittest
from unittest.mock import Mock, patch

PATH = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if PATH not in sys.path:
    sys.path.append(PATH)

try:
    import openshot
except ModuleNotFoundError:
    openshot = Mock()
    openshot.LINEAR = 1
    openshot.BEZIER = 2
    openshot.CONSTANT = 3
    openshot.FFmpegWriter = Mock(IsValidCodec=lambda *args: True)
    openshot.EffectInfo = Mock()
    openshot.CacheMemory = Mock()
    openshot.Settings = Mock()
    sys.modules["openshot"] = openshot

from tests.qt_test_app import ensure_app_state, get_or_create_app
from tests.test_project_data import DummyApp


class DummySettings:
    pass


class ExportFilenameTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app, cls._owns_app = get_or_create_app(DummyApp)
        ensure_app_state(app, DummySettings)
        metrics = types.ModuleType("classes.metrics")
        metrics.track_metric_screen = Mock()
        metrics.track_metric_error = Mock()
        with patch.dict(sys.modules, {"classes.metrics": metrics}):
            cls.export_mod = importlib.import_module("windows.export")
        cls.format_export_filename = staticmethod(cls.export_mod.format_export_filename)

    def test_filename_ending_with_format_name_appends_dot_extension(self):
        # Reproduces issue #6069: "mygif" ends with "gif", so a naive endswith
        # check omitted the dot suffix, causing AVFormatContext allocation errors.
        self.assertEqual(self.format_export_filename("mygif", "gif"), "mygif.gif")
        self.assertEqual(self.format_export_filename("test_mp4", "mp4"), "test_mp4.mp4")
        self.assertEqual(self.format_export_filename("clip_avi", "avi"), "clip_avi.avi")
        self.assertEqual(self.format_export_filename("movie_mov", "mov"), "movie_mov.mov")

    def test_filename_with_existing_extension_not_duplicated(self):
        self.assertEqual(self.format_export_filename("mygif.gif", "gif"), "mygif.gif")
        self.assertEqual(self.format_export_filename("test.mp4", "mp4"), "test.mp4")

    def test_filename_with_uppercase_extension_preserved(self):
        self.assertEqual(self.format_export_filename("mygif.GIF", "gif"), "mygif.GIF")
        self.assertEqual(self.format_export_filename("test.MP4", "mp4"), "test.MP4")

    def test_filename_with_custom_suffix_appends_format_extension(self):
        self.assertEqual(self.format_export_filename("mygif.stuff", "gif"), "mygif.stuff.gif")

    def test_blank_filename_uses_default_with_extension(self):
        self.assertEqual(
            self.format_export_filename("", "mp4", default_filename="Untitled Project"),
            "Untitled Project.mp4",
        )
        self.assertEqual(
            self.format_export_filename("   ", "gif", default_filename="Untitled Project"),
            "Untitled Project.gif",
        )

    def test_format_with_leading_dot_handled(self):
        self.assertEqual(self.format_export_filename("mygif", ".gif"), "mygif.gif")
        self.assertEqual(self.format_export_filename("test", ".mp4"), "test.mp4")


if __name__ == "__main__":
    unittest.main()
