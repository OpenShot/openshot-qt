"""
 @file
 @brief Targeted unit tests for the main Export dialog's duplicate-file detection.
"""

import importlib
import os
import sys
import types
import unittest
from unittest.mock import patch


PATH = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if PATH not in sys.path:
    sys.path.append(PATH)

from qt_api import QApplication
from tests.qt_test_app import ensure_app_state, get_or_create_app


class DummySettings:
    pass


class DummyApp(QApplication):
    def __init__(self):
        super().__init__([])

    def _tr(self, text):
        return text


class ExportDuplicateDetectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app, cls._owns_app = get_or_create_app(DummyApp)
        cls.app = ensure_app_state(app, DummySettings)
        cls.export_module = importlib.import_module("windows.export")

    def test_find_file_by_normalized_path_matches_exact_path(self):
        module = self.export_module
        existing = types.SimpleNamespace(id="F1", data={"path": "/media/clip.mp4"})
        with patch.object(module.File, "filter", return_value=[existing]):
            result = module._find_file_by_normalized_path("/media/clip.mp4")
        self.assertIs(result, existing)

    def test_find_file_by_normalized_path_matches_through_symlink_indirection(self):
        module = self.export_module
        existing = types.SimpleNamespace(id="F1", data={"path": "/media/real/clip.mp4"})
        # A different path string that resolves to the same real file --
        # e.g. an export folder that happens to be a symlink/bind-mount alias.
        with patch.object(module.File, "filter", return_value=[existing]), \
             patch.object(module.os.path, "realpath", side_effect=lambda p: "/media/real/clip.mp4"):
            result = module._find_file_by_normalized_path("/media/alias/clip.mp4")
        self.assertIs(result, existing)

    def test_find_file_by_normalized_path_returns_none_for_distinct_files(self):
        module = self.export_module
        existing = types.SimpleNamespace(id="F1", data={"path": "/media/clip.mp4"})
        with patch.object(module.File, "filter", return_value=[existing]):
            result = module._find_file_by_normalized_path("/media/other.mp4")
        self.assertIsNone(result)

    def test_find_file_by_normalized_path_skips_entries_without_a_path(self):
        module = self.export_module
        existing = types.SimpleNamespace(id="F1", data={"path": ""})
        with patch.object(module.File, "filter", return_value=[existing]):
            result = module._find_file_by_normalized_path("/media/clip.mp4")
        self.assertIsNone(result)

    def test_file_is_on_timeline_true_when_a_clip_references_it(self):
        module = self.export_module
        clip = types.SimpleNamespace(data={"file_id": "F1"})
        with patch.object(module.Clip, "filter", return_value=[clip]):
            self.assertTrue(module._file_is_on_timeline("F1"))

    def test_file_is_on_timeline_false_when_no_clip_references_it(self):
        module = self.export_module
        clip = types.SimpleNamespace(data={"file_id": "F2"})
        with patch.object(module.Clip, "filter", return_value=[clip]):
            self.assertFalse(module._file_is_on_timeline("F1"))

    def test_file_is_on_timeline_false_for_empty_timeline(self):
        module = self.export_module
        with patch.object(module.Clip, "filter", return_value=[]):
            self.assertFalse(module._file_is_on_timeline("F1"))


if __name__ == "__main__":
    unittest.main()
