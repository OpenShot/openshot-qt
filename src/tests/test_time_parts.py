"""
 @file
 @brief Unit tests for time code helpers
"""

import os
import sys
import unittest
from collections import Counter


PATH = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if PATH not in sys.path:
    sys.path.append(PATH)

from classes.time_parts import secondsToTime, secondsToTimecode


class TimePartsTests(unittest.TestCase):
    def assert_unique_timecodes(self, fps_num, fps_den, seconds=60):
        fps = fps_num / fps_den
        codes = [secondsToTimecode(frame / fps, fps_num, fps_den) for frame in range(int(fps * seconds))]
        repeated = sorted(code for code, count in Counter(codes).items() if count > 1)
        self.assertEqual(repeated, [])
        self.assertEqual(codes, sorted(codes))

    def test_integer_frame_rates_have_one_timecode_per_frame(self):
        for fps_num, fps_den in ((24, 1), (25, 1), (30, 1), (60, 1)):
            with self.subTest(fps="%s/%s" % (fps_num, fps_den)):
                self.assert_unique_timecodes(fps_num, fps_den)

    def test_fractional_frame_rates_have_one_timecode_per_frame(self):
        for fps_num, fps_den in ((24000, 1001), (30000, 1001), (60000, 1001)):
            with self.subTest(fps="%s/%s" % (fps_num, fps_den)):
                self.assert_unique_timecodes(fps_num, fps_den)

    def test_last_frame_of_second_at_29_97_fps(self):
        self.assertEqual(secondsToTime(29 * 1001 / 30000, 30000, 1001)["frame"], "29")
        self.assertEqual(secondsToTimecode(30 * 1001 / 30000, 30000, 1001), "00:00:01:00")

    def test_integer_frame_rate_timecodes(self):
        self.assertEqual(secondsToTimecode(0.0, 30, 1), "00:00:00:00")
        self.assertEqual(secondsToTimecode(29 / 30, 30, 1), "00:00:00:29")
        self.assertEqual(secondsToTimecode(3661 + 12 / 25, 25, 1), "01:01:01:12")


if __name__ == "__main__":
    unittest.main()
