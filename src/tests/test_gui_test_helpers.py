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

    def test_audio_error_during_real_window_shutdown_does_not_open_dialog(self):
        script = r'''
import os
import tempfile
from unittest.mock import patch

root = tempfile.TemporaryDirectory(prefix="openshot-shutdown-audio-")
original_expanduser = os.path.expanduser
os.path.expanduser = lambda path: root.name if path == "~" else original_expanduser(path)
from classes import version
version.get_current_Version = lambda: None
from classes.app import OpenShotApp
from qt_api import QTimer
from tests.gui_test_helpers import run_gui_workflow

app = OpenShotApp([], mode="unittest")
from windows.main_window import MainWindow
app.settings.set("tutorial_enabled", False)
app.settings.set("send_metrics", False)
events = []
shutdown = MainWindow._shutdown

def shutdown_with_queued_error(window):
    if not window.shutting_down:
        worker = window.preview_thread
        def emit_error():
            events.append("audio error during shutdown")
            worker.error_found.emit("forced missing audio device")
        QTimer.singleShot(0, emit_error)
    shutdown(window)

def verify():
    events.append("workflow finished")
    app.quit()

with patch.object(MainWindow, "_shutdown", shutdown_with_queued_error), \
        patch("windows.preview_thread.QMessageBox.warning") as dialog:
    run_gui_workflow(app, verify)
    dialog.assert_not_called()
assert events == ["workflow finished", "audio error during shutdown"], events
'''
        source = str(Path(__file__).resolve().parents[1])
        env = dict(os.environ, QT_QPA_PLATFORM="offscreen",
                   PYTHONPATH=os.pathsep.join(filter(None, (source, os.environ.get("PYTHONPATH")))))
        result = subprocess.run([sys.executable, "-c", script], env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                universal_newlines=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout[-16000:])
