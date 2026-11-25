"""Tests for fast bundled-emoji import metadata."""

import json
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import openshot

from classes import info
from windows.views.emojis_listview import builtin_emoji_reader_data


class EmojiDragTests(unittest.TestCase):
    def test_bundled_emoji_metadata_avoids_reader_inspection(self):
        emoji_path = os.path.join(
            info.PATH, "emojis", "color", "svg", "1F600.svg"
        )

        with patch.object(
            openshot, "Clip", side_effect=AssertionError("unexpected inspection")
        ):
            data = builtin_emoji_reader_data(emoji_path)

        self.assertEqual(data["type"], "QtImageReader")
        self.assertEqual(data["path"], os.path.realpath(emoji_path))
        self.assertEqual((data["width"], data["height"]), (72, 72))
        self.assertTrue(data["has_single_image"])
        self.assertEqual(data["video_length"], 108000)

    def test_generated_metadata_builds_a_readable_clip(self):
        emoji_path = os.path.join(
            info.PATH, "emojis", "color", "svg", "1F600.svg"
        )
        reader_data = builtin_emoji_reader_data(emoji_path)
        clip = openshot.Clip()
        try:
            clip.SetJson(json.dumps({"reader": reader_data}))
            clip.Open()
            self.assertIsNotNone(clip.GetFrame(1))
        finally:
            clip.Close()

    def test_project_file_thumbnail_reuses_bundled_artwork_before_drag(self):
        from windows.models.files_model import FilesModel
        emoji_path = os.path.join(info.PATH, "emojis", "color", "svg", "1F600.svg")
        file = SimpleNamespace(id="emoji", data={"path": emoji_path, "name": "Grinning face", "media_type": "image"})
        with patch("windows.models.files_model.GetThumbPath", side_effect=AssertionError("cold native thumbnail request")):
            source, name, kind = FilesModel._thumbnail_source_for_file(None, file)
        self.assertTrue(os.path.isfile(source))
        self.assertTrue(source.endswith("1F600.png"))
        self.assertEqual((name, kind), ("Grinning face", "image"))

    def test_explicit_thumbnail_refresh_still_regenerates_emoji_artwork(self):
        from windows.models.files_model import FilesModel
        path = os.path.join(info.PATH, "emojis", "color", "svg", "1F600.svg")
        file = SimpleNamespace(id="emoji", data={"path": path, "media_type": "image"})
        model = SimpleNamespace(PROJECT_FILE_THUMB_ATTEMPTS=3)
        with patch("windows.models.files_model.GetThumbPath", return_value="fresh.png") as generate:
            source, _, _ = FilesModel._thumbnail_source_for_file(model, file, clear_cache=True)
        self.assertEqual(source, "fresh.png")
        generate.assert_called_once_with("emoji", 1, clear_cache=True, attempts=3)

    def test_missing_bundled_thumbnail_uses_normal_generation(self):
        from windows.models.files_model import FilesModel
        path = os.path.join(info.PATH, "emojis", "color", "svg", "1F600.svg")
        file = SimpleNamespace(id="emoji", data={"path": path, "media_type": "image"})
        model = SimpleNamespace(PROJECT_FILE_THUMB_ATTEMPTS=3)
        with patch("windows.models.files_model.builtin_emoji_thumbnail", return_value=None), \
                patch("windows.models.files_model.GetThumbPath", return_value="generated.png") as generate:
            self.assertEqual(FilesModel._thumbnail_source_for_file(model, file)[0], "generated.png")
        generate.assert_called_once()

    def test_non_bundled_svg_requires_normal_inspection(self):
        self.assertIsNone(builtin_emoji_reader_data("/tmp/custom-emoji.svg"))


if __name__ == "__main__":
    unittest.main()
