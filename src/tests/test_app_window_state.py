"""Tests for main-window startup state handling."""

import unittest
from unittest.mock import patch

from qt_api import Qt

from classes.app import OpenShotApp


class FakeWindow:
    def __init__(self, state):
        self.state = state
        self.calls = []

    def windowState(self):
        return self.state

    def show(self):
        self.calls.append("show")

    def showMaximized(self):
        self.calls.append("showMaximized")

    def showFullScreen(self):
        self.calls.append("showFullScreen")

    def showNormal(self):
        self.calls.append("showNormal")

    def _restore_saved_window_state(self):
        self.calls.append("restoreState")


class AppWindowStateTests(unittest.TestCase):
    def test_restored_maximized_window_is_shown_maximized(self):
        window = FakeWindow(Qt.WindowMaximized)

        with patch(
                "classes.app.QTimer.singleShot",
                lambda _delay, callback: callback()):
            OpenShotApp._show_main_window(window)

        self.assertEqual(
            window.calls,
            ["show", "showNormal", "showMaximized", "restoreState"])

    def test_restored_fullscreen_window_is_shown_fullscreen(self):
        window = FakeWindow(Qt.WindowFullScreen)

        with patch(
                "classes.app.QTimer.singleShot",
                lambda _delay, callback: callback()):
            OpenShotApp._show_main_window(window)

        self.assertEqual(
            window.calls,
            ["show", "showNormal", "showFullScreen", "restoreState"])

    def test_normal_window_uses_plain_show(self):
        window = FakeWindow(Qt.WindowNoState)

        with patch(
                "classes.app.QTimer.singleShot",
                lambda _delay, callback: callback()):
            OpenShotApp._show_main_window(window)

        self.assertEqual(window.calls, ["show", "restoreState"])


if __name__ == "__main__":
    unittest.main()
