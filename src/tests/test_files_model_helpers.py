"""
 @file
 @brief Targeted unit tests for project-file thumbnail helper logic.
"""

import importlib
import os
import sys
import types
import unittest
from unittest.mock import patch


PATH = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
THUMBNAIL_PATH = os.path.join(PATH, "images", "thumb.png")
if PATH not in sys.path:
    sys.path.append(PATH)


class FilesModelHelperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.files_model_module = importlib.import_module("windows.models.files_model")

    def test_icon_from_thumbnail_source_prefers_freshly_loaded_pixmap(self):
        def load_pixmap(_, path):
            return path == THUMBNAIL_PATH

        pixmap = type(
            "PixmapStub",
            (),
            {
                "load": load_pixmap,
                "isNull": lambda self: False,
            },
        )()

        with patch.object(self.files_model_module, "QPixmap", return_value=pixmap), \
                patch.object(self.files_model_module, "QIcon", side_effect=lambda arg: ("icon", arg)) as qicon:
            result = self.files_model_module.FilesModel._icon_from_thumbnail_source(THUMBNAIL_PATH)

        self.assertEqual(result, ("icon", pixmap))
        qicon.assert_called_once_with(pixmap)

    def test_icon_from_thumbnail_source_falls_back_to_path_when_pixmap_load_fails(self):
        pixmap = type(
            "PixmapStub",
            (),
            {
                "load": lambda self, path: False,
                "isNull": lambda self: True,
            },
        )()

        with patch.object(self.files_model_module, "QPixmap", return_value=pixmap), \
                patch.object(self.files_model_module, "QIcon", side_effect=lambda arg: ("icon", arg)) as qicon:
            result = self.files_model_module.FilesModel._icon_from_thumbnail_source(THUMBNAIL_PATH)

        self.assertEqual(result, ("icon", THUMBNAIL_PATH))
        qicon.assert_called_once_with(THUMBNAIL_PATH)


class _FakeIndex:
    def __init__(self, value):
        self._value = value

    def data(self, role):
        return self._value


class UpdateTimelineHighlightFromSelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.files_model_module = importlib.import_module("windows.models.files_model")

    def _fake_self(self, selected_rows):
        module = self.files_model_module
        fake_self = types.SimpleNamespace(
            selection_model=types.SimpleNamespace(
                selectedRows=lambda column: selected_rows,
            ),
            PLACEHOLDER_PREFIX=module.FilesModel.PLACEHOLDER_PREFIX,
        )
        fake_self._is_generation_placeholder = (
            lambda file_id: module.FilesModel._is_generation_placeholder(fake_self, file_id)
        )
        return fake_self

    def test_highlights_the_single_selected_file(self):
        module = self.files_model_module
        fake_self = self._fake_self([_FakeIndex("file-123")])
        highlighted = []
        fake_window = types.SimpleNamespace(set_highlighted_file=highlighted.append)
        with patch.object(module, "get_app", return_value=types.SimpleNamespace(window=fake_window)):
            module.FilesModel._update_timeline_highlight_from_selection(fake_self)
        self.assertEqual(highlighted, ["file-123"])

    def test_clears_highlight_when_nothing_selected(self):
        module = self.files_model_module
        fake_self = self._fake_self([])
        highlighted = []
        fake_window = types.SimpleNamespace(set_highlighted_file=highlighted.append)
        with patch.object(module, "get_app", return_value=types.SimpleNamespace(window=fake_window)):
            module.FilesModel._update_timeline_highlight_from_selection(fake_self)
        self.assertEqual(highlighted, [None])

    def test_clears_highlight_when_multiple_files_selected(self):
        module = self.files_model_module
        fake_self = self._fake_self([_FakeIndex("file-1"), _FakeIndex("file-2")])
        highlighted = []
        fake_window = types.SimpleNamespace(set_highlighted_file=highlighted.append)
        with patch.object(module, "get_app", return_value=types.SimpleNamespace(window=fake_window)):
            module.FilesModel._update_timeline_highlight_from_selection(fake_self)
        self.assertEqual(highlighted, [None])

    def test_ignores_generation_placeholder_selection(self):
        module = self.files_model_module
        fake_self = self._fake_self([_FakeIndex("__genjob__:job-1")])
        highlighted = []
        fake_window = types.SimpleNamespace(set_highlighted_file=highlighted.append)
        with patch.object(module, "get_app", return_value=types.SimpleNamespace(window=fake_window)):
            module.FilesModel._update_timeline_highlight_from_selection(fake_self)
        self.assertEqual(highlighted, [None])


if __name__ == "__main__":
    unittest.main()
