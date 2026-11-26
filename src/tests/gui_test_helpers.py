"""Bounded event-driven startup for real-window workflow tests."""

from time import monotonic
from unittest.mock import patch

from qt_api import QTimer


def run_when_ready(app, callback, timeout=10, ready=lambda: True):
    """Run after window/timeline initialization and queued startup focus events.

    Keep the deadline active on slow runners: failure must quit the child process,
    leaving its workflow's existing success assertion to report the failure.
    """
    deadline = monotonic() + timeout

    def check():
        window = getattr(app, "window", None)
        timeline = getattr(window, "timeline", None)
        if (getattr(window, "initialized", False)
                and window.isVisible()
                and timeline is not None and timeline.isVisible()
                and timeline.width() > 0 and timeline.height() > 0
                and ready()):
            QTimer.singleShot(0, callback)
        elif monotonic() >= deadline:
            print("GUI startup timed out waiting for window/timeline readiness", flush=True)
            app.quit()
        else:
            QTimer.singleShot(10, check)

    QTimer.singleShot(0, check)


def run_gui_workflow(app, callback, timeout=10, ready=lambda: True):
    """Run editor checks without a machine's missing audio device opening a modal.

    Keep this fixture active through exec_() returning: shutdown processes queued
    events, including delayed audio initialization errors. Audio-error behavior is
    covered separately by test_preview_audio_device.
    """
    with patch("windows.preview_thread.PreviewParent.onError"):
        if not app.gui():
            raise AssertionError("app.gui() failed")
        run_when_ready(app, callback, timeout=timeout, ready=ready)
        app.exec_()
