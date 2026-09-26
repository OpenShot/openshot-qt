"""Regression coverage for the Qt application's lifetime across test classes."""

import os
from pathlib import Path
import subprocess
import sys
import unittest


class QtTestAppLifetimeTests(unittest.TestCase):
    def test_timeline_teardown_keeps_real_razor_timers_running(self):
        # A subprocess guarantees the timeline class creates the QApplication.
        # Full discovery can hide the bug by creating it in another module first.
        source = str(Path(__file__).resolve().parents[1])
        env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
        env["PYTHONPATH"] = os.pathsep.join(filter(None, (source, env.get("PYTHONPATH"))))
        result = subprocess.run(
            [sys.executable, "-m", "unittest", "-q",
             "tests.test_timeline_helpers.TimelineHelperTests.test_timecode_editor_parses_blank_and_zero_as_timeline_start",
             "tests.test_razor.RazorTests.test_shift_tap_stays_released_through_real_timer_refreshes"],
            env=env, capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
