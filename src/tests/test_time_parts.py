"""Regression coverage for secondsToTimecode() at fractional frame rates.

At 23.976, 29.97 and 59.94 fps the old code rounded the frame number while the
seconds were floored, which gave two different frames the same timecode and
skipped the last frame of each second (e.g. 29.97 fps showed 28 instead of 29).
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.realpath(__file__))))

from classes.time_parts import secondsToTimecode


class TimePartsTests(unittest.TestCase):
    def _unique_timecodes(self, fps, fps_den, frame_count=43200):
        """Return the number of duplicate timecodes for the first N frames."""
        seen = {}
        for frame in range(frame_count):
            tc = secondsToTimecode(frame / (fps / fps_den), fps, fps_den)
            seen.setdefault(tc, []).append(frame)
        return sum(1 for frames in seen.values() if len(frames) > 1)

    def test_integer_frame_rates_unchanged(self):
        for fps in (24, 25, 30, 50, 60, 120):
            self.assertEqual(self._unique_timecodes(fps, 1), 0)

    def test_fractional_frame_rates_have_no_duplicates(self):
        for fps, den in ((23976, 1000), (29970, 1000), (59940, 1000)):
            self.assertEqual(self._unique_timecodes(fps, den), 0)

    def test_last_frame_of_second_at_2997(self):
        # Frame 29 of a 29.97 fps second must be 29, not 28.
        self.assertEqual(secondsToTimecode(29 / 29.97, 29970, 1000), "00:00:00:29")
        # The next frame rolls the seconds over.
        self.assertEqual(secondsToTimecode(30 / 29.97, 29970, 1000), "00:00:01:00")

    def test_millisecond_format_unchanged(self):
        # The caption editor uses milliseconds; this must not shift.
        self.assertEqual(secondsToTimecode(1.5, 30, 1, use_milliseconds=True),
                         "00:00:01:500")


if __name__ == "__main__":
    unittest.main()