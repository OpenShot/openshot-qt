"""Regression coverage for the Qt application's lifetime across test classes."""

import os
from pathlib import Path
import subprocess  # nosec B404 - Isolate the real Qt application in a test process.
import sys
import unittest


class QtTestAppLifetimeTests(unittest.TestCase):
    def test_timeline_teardown_keeps_real_razor_timers_running(self):
        # A subprocess guarantees the timeline class creates the QApplication.
        # Full discovery can hide the bug by creating it in another module first.
        source = str(Path(__file__).resolve().parents[1])
        env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
        env["PYTHONPATH"] = os.pathsep.join(filter(None, (source, env.get("PYTHONPATH"))))
        # Run the current interpreter with fixed test names, without a shell.
        result = subprocess.run(  # nosec B603
            [sys.executable, "-m", "unittest", "-q",
             "tests.test_timeline_helpers.TimelineHelperTests.test_timecode_editor_parses_blank_and_zero_as_timeline_start",
             "tests.test_razor.RazorTests.test_shift_tap_stays_released_through_real_timer_refreshes"],
            env=env, capture_output=True, text=True, timeout=30, shell=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
