"""Regression coverage for easing_presets() and exceptions.tail_file().

These helpers are pure (no Qt, no libopenshot) and are used by the GUI menus,
the CLI animation, and crash recovery. They previously had no test coverage.
"""
import io
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from classes import easing
from classes import exceptions


class EasingPresetsTests(unittest.TestCase):
    def setUp(self):
        self.presets = easing.easing_presets()

    def test_returns_a_nonempty_list_of_tuples(self):
        self.assertIsInstance(self.presets, list)
        self.assertGreater(len(self.presets), 0)
        for entry in self.presets:
            self.assertEqual(len(entry), 3)

    def test_each_preset_has_a_unique_id_and_four_control_points(self):
        ids = [entry[0] for entry in self.presets]
        self.assertEqual(len(ids), len(set(ids)))
        for entry in self.presets:
            self.assertEqual(len(entry[1]), 4)
            for coord in entry[1]:
                self.assertIsInstance(coord, (int, float))

    def test_default_ease_is_first_and_matches_css(self):
        self.assertEqual(self.presets[0][0], "ease")
        self.assertEqual(self.presets[0][1], (0.250, 0.100, 0.250, 1.000))

    def test_translate_callback_localises_labels(self):
        translated = easing.easing_presets(translate=lambda text: "FR:" + text)
        self.assertEqual(translated[0][2], "FR:Ease (Default)")
        # IDs and control points are never translated.
        self.assertEqual(translated[0][0], self.presets[0][0])
        self.assertEqual(translated[0][1], self.presets[0][1])


class TailFileTests(unittest.TestCase):
    def _tail(self, content, n, offset=None):
        f = io.BytesIO(content)
        return exceptions.tail_file(f, n, offset)

    def test_returns_last_n_lines(self):
        content = b"line1\nline2\nline3\nline4\nline5\n"
        self.assertEqual(self._tail(content, 3), [b"line3", b"line4", b"line5"])

    def test_offset_skips_lines_from_the_end(self):
        content = b"line1\nline2\nline3\nline4\nline5\n"
        self.assertEqual(self._tail(content, 3, offset=1),
                         [b"line2", b"line3", b"line4"])

    def test_returns_everything_when_file_is_short(self):
        self.assertEqual(self._tail(b"short\n", 10), [b"short"])

    def test_handles_empty_file(self):
        self.assertEqual(self._tail(b"", 5), [])


if __name__ == "__main__":
    unittest.main()