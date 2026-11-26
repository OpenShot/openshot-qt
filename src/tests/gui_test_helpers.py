"""Bounded event-driven startup for real-window workflow tests."""

from time import monotonic

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
