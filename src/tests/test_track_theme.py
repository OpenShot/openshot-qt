"""Theme round trips must not retain obsolete dock controls or rebuild the divider."""

import os
from pathlib import Path
import subprocess
import sys
import unittest


class TrackThemeTests(unittest.TestCase):
    def test_theme_round_trips_dispose_old_titlebars_and_keep_timeline_header(self):
        script = r'''
import os
import tempfile
import traceback
root = tempfile.TemporaryDirectory(prefix="openshot-theme-roundtrip-")
expanduser = os.path.expanduser
os.path.expanduser = lambda path: root.name if path == "~" else expanduser(path)
from classes import version
version.get_current_Version = lambda: None
from classes.app import OpenShotApp
from classes.title_bar import HiddenTitleBar
from qt_api import QCoreApplication, QEvent
from tests.gui_test_helpers import run_gui_workflow
app = OpenShotApp([], mode="unittest")
app.settings.set("tutorial_enabled", False)
app.settings.set("send_metrics", False)
passed = False

def verify():
    global passed
    try:
        window = app.window
        window.style_dock_widgets()
        timeline_bar = window.dockTimeline.titleBarWidget()
        for theme in ("Humanity: Dark", "Cosmic Dusk", "Retro", "Cosmic Dusk"):
            app.theme_manager.apply_theme(theme)
            window.style_dock_widgets(theme_changed=True)
            QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
            active = [dock.titleBarWidget() for dock in window.getDocks()
                      if isinstance(dock.titleBarWidget(), HiddenTitleBar)]
            retained = window.findChildren(HiddenTitleBar)
            assert set(retained) == set(active), (theme, len(retained), len(active))
            assert window.dockTimeline.titleBarWidget() is timeline_bar, theme
        passed = True
    except Exception:
        traceback.print_exc()
    finally:
        app.quit()

run_gui_workflow(app, verify)
assert passed, "Theme round-trip checks failed"
'''
        source = str(Path(__file__).resolve().parents[1])
        env = dict(os.environ, QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software",
                   PYTHONPATH=os.pathsep.join(filter(None, (source, os.environ.get("PYTHONPATH")))))
        result = subprocess.run([sys.executable, "-c", script], env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                universal_newlines=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout[-16000:])
