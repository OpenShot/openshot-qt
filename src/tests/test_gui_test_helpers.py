"""Startup waits must follow readiness and fail promptly when it never arrives."""

import os
from pathlib import Path
import subprocess
import sys
import unittest


class GuiTestHelpersTests(unittest.TestCase):
    def test_delayed_readiness_and_timeout(self):
        script = r'''
from types import SimpleNamespace
from qt_api import QApplication, QWidget, QTimer
from tests.gui_test_helpers import run_when_ready

app = QApplication([])
window = QWidget()
window.timeline = QWidget(window)
window.initialized = False
window.resize(400, 300)
window.timeline.resize(200, 100)
app.window = window
window.show()
events = []
state = SimpleNamespace(ready=False)

def initialize():
    window.initialized = True
    events.append("initialized")
    QTimer.singleShot(0, lambda: events.append("focus settled"))
    QTimer.singleShot(20, lambda: setattr(state, "ready", True))

def verify():
    assert events == ["initialized", "focus settled"], events
    assert state.ready
    events.append("verified")
    app.quit()

run_when_ready(app, verify, ready=lambda: state.ready)
QTimer.singleShot(0, initialize)
app.exec_()
assert events[-1] == "verified", events

# A ready window with an unmet workflow condition must time out, not run early
# or leave its subprocess hanging until the outer 60/90-second safety limit.
run_when_ready(app, lambda: events.append("unexpected"), timeout=.02, ready=lambda: False)
app.exec_()
assert events[-1] == "verified", events
'''
        source = str(Path(__file__).resolve().parents[1])
        env = dict(os.environ, QT_QPA_PLATFORM="offscreen",
                   PYTHONPATH=os.pathsep.join(filter(None, (source, os.environ.get("PYTHONPATH")))))
        result = subprocess.run([sys.executable, "-c", script], env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                universal_newlines=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("GUI startup timed out", result.stdout)
