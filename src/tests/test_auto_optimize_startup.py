"""Exercise the actual main window wiring with an isolated user profile."""

import os
from pathlib import Path
import subprocess
import sys
import unittest


class AutoOptimizeStartupTests(unittest.TestCase):
    def test_menu_banner_and_project_switch_in_real_window(self):
        script = r'''
import os
import tempfile
import traceback
from unittest.mock import patch
from classes import info, version
profile_dir = tempfile.TemporaryDirectory(prefix="openshot-auto-optimize-test-")
original = info.USER_PATH
profile = os.path.join(profile_dir.name, ".openshot_qt")
for key, value in list(vars(info).items()):
    if isinstance(value, str) and value.startswith(original):
        setattr(info, key, profile + value[len(original):])
info._path_defaults = {key: profile + value[len(original):]
                       for key, value in info._path_defaults.items()}
info.setup_userdirs()
version.get_current_Version = lambda: None
from classes.app import OpenShotApp
from qt_api import QTimer
app = OpenShotApp([], mode="unittest")
app.settings.set("tutorial_enabled", False)
app.settings.set("send_metrics", False)
app.settings.set("auto-optimize", "ask")
passed = False

def verify():
    global passed
    try:
        window = app.window
        controller = window.auto_optimize
        action = window.actionAutoOptimize
        assert action in window.menuFile.actions()
        assert action.text() == "Auto-Optimize" and action.isCheckable()
        assert not action.icon().isNull() and action.isIconVisibleInMenu()
        assert action.shortcut().toString() == "Ctrl+Alt+O"
        assert app.project.get("auto_optimize") is None
        controller.timer.stop()
        controller._offer()
        for theme in ("Cosmic Dusk", "Humanity: Dark", "Retro"):
            app.theme_manager.apply_theme(theme)
            app.processEvents()
            banner = window.notification_area.banners["auto-optimize"]
            assert not banner.symbol.pixmap().isNull()
            assert banner.primary.isVisible()
        banner.primary.click()
        assert "auto-optimize" not in window.notification_area.banners
        assert app.project.get("auto_optimize") is True and action.isChecked()
        action.trigger()
        assert app.project.get("auto_optimize") is False and not action.isChecked()
        assert app.project.has_unsaved_changes
        # Loading another project resets the controller, not the saved decision.
        app.updates.load(app.project._data)
        controller.evaluate()
        assert "auto-optimize" not in window.notification_area.banners
        assert not action.isChecked()
        from windows.preferences import Preferences
        from qt_api import QSpinBox
        preferences = Preferences()
        assert "Optimize" in preferences.category_tabs
        threshold = preferences.findChild(QSpinBox, "auto-optimize-threshold")
        assert threshold is not None and threshold.value() == 200
        assert threshold.suffix().strip() == "ms"
        assert "Lower values" in threshold.toolTip()
        threshold.setValue(500)
        assert app.settings.get("auto-optimize-threshold") == 500
        preferences.close()
        passed = True
    except Exception:
        traceback.print_exc()
    finally:
        app.quit()

assert app.gui()
QTimer.singleShot(1500, verify)
app.exec_()
assert passed, "Auto-Optimize startup checks failed"
'''
        source = str(Path(__file__).resolve().parents[1])
        env = dict(os.environ, PYTHONPATH=os.pathsep.join(filter(None, (source, os.environ.get("PYTHONPATH")))),
                   QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software")
        result = subprocess.run([sys.executable, "-c", script], env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                universal_newlines=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout[-16000:])
