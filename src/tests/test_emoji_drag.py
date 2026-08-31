"""Tests for fast bundled-emoji import metadata."""

import json
import os
import unittest
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

    def test_non_bundled_svg_requires_normal_inspection(self):
        self.assertIsNone(builtin_emoji_reader_data("/tmp/custom-emoji.svg"))


if __name__ == "__main__":
    unittest.main()
