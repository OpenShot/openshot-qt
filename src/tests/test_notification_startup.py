"""Exercise notification wiring in a real application with an isolated profile."""

import os
from pathlib import Path
import subprocess
import sys
import unittest


class NotificationStartupTests(unittest.TestCase):
    def test_banner_icons_fit_and_keep_menu_artwork_at_display_scales(self):
        # Scaling is fixed when QApplication starts, so each scale needs a process.
        script = r'''
from types import SimpleNamespace
from qt_api import QApplication, Qt, QColor
QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)
app = QApplication([])
from windows.notifications import NotificationBanner, banner_colors, notification_icon
for kind in ('feedback', 'update'):
    banner = NotificationBanner(None, kind, 'Open', lambda: None, lambda: None,
                                str, icon_name=kind)
    for name in ('Cosmic Dusk', 'Humanity: Dark', 'Retro'):
        theme = SimpleNamespace(name=name)
        colors = banner_colors(banner, theme, kind)
        banner.apply_colors(colors, theme)
        pixmap = banner.symbol.pixmap()
        assert not pixmap.isNull(), (kind, name)
        ratio = pixmap.devicePixelRatioF()
        assert pixmap.width() / ratio == banner.symbol.width(), (kind, name, ratio)
        assert pixmap.height() / ratio == banner.symbol.height(), (kind, name, ratio)
        source = notification_icon(banner, kind, theme).pixmap(banner.symbol.size()).toImage()
        actual = pixmap.toImage()
        assert source.size() == actual.size()
        expected = QColor(colors['text'])
        visible = 0
        for y in range(actual.height()):
            for x in range(actual.width()):
                pixel = actual.pixelColor(x, y)
                assert pixel.alpha() == source.pixelColor(x, y).alpha()
                if pixel.alpha() > 128:
                    visible += 1
                    for channel in ('red', 'green', 'blue'):
                        assert abs(getattr(pixel, channel)() - getattr(expected, channel)()) <= 2
        assert visible > 0, (kind, name)
'''
        source = str(Path(__file__).resolve().parents[1])
        for scale in ('1', '1.5', '2'):
            with self.subTest(scale=scale):
                env = dict(os.environ, PYTHONPATH=source, QT_QPA_PLATFORM='offscreen',
                           QT_SCALE_FACTOR=scale)
                result = subprocess.run([sys.executable, '-c', script], env=env,
                                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                        universal_newlines=True, timeout=30)
                self.assertEqual(result.returncode, 0, result.stdout)

    def test_help_shortcuts_and_three_themes(self):
        # A subprocess isolates OpenShotApp from other tests' QApplication stubs.
        script = r'''
import importlib
import os
import tempfile
import traceback
from unittest.mock import patch
from classes import info, version

profile_dir = tempfile.TemporaryDirectory(prefix="openshot-notification-test-")
original = info.USER_PATH
profile = os.path.join(profile_dir.name, ".openshot_qt")
for key, value in list(vars(info).items()):
    if isinstance(value, str) and value.startswith(original):
        setattr(info, key, profile + value[len(original):])
info._path_defaults = {key: profile + value[len(original):]
                       for key, value in info._path_defaults.items()}
info.setup_userdirs()
info.FEEDBACK_PREVIEW = True
info.UPDATE_PREVIEW = True
version.get_current_Version = lambda: None
from classes.app import OpenShotApp
from qt_api import QTimer, Qt, QT_API
binding = {"pyqt5": "PyQt5", "pyqt6": "PyQt6", "pyside6": "PySide6"}[QT_API]
QTest = importlib.import_module(binding + ".QtTest").QTest
app = OpenShotApp([], mode="unittest")
app.settings.set("tutorial_enabled", False)
app.settings.set("unique_install_id", "preview-only")
app.settings.set("send_metrics", False)
passed = False

def verify():
    global passed
    try:
        window = app.window
        area = window.notification_area
        assert set(area.banners) == {"feedback", "update"}
        assert window.actionShareFeedback.shortcut().toString() == "F8"
        assert window.actionUpdate.shortcut().toString() == "F9"
        actions = window.menuHelp.actions()
        start = actions.index(window.actionShareFeedback)
        assert actions[start - 1].isSeparator()
        assert actions[start + 1] is window.actionUpdate
        assert actions[start + 2].isSeparator()
        assert actions[start + 3] is window.actionAbout
        for theme in ("Cosmic Dusk", "Humanity: Dark", "Retro"):
            app.theme_manager.apply_theme(theme)
            app.processEvents()
            app.processEvents()
            assert area.toolbar.width() >= window.width() * .95, theme
            assert area.toolbar.y() >= window.toolBar.geometry().bottom(), theme
            for action in (window.actionShareFeedback, window.actionUpdate):
                assert not action.icon().pixmap(24, 24).isNull(), theme
        window.activateWindow()
        app.processEvents()
        with patch("windows.feedback.QDesktopServices.openUrl", return_value=True) as opened:
            QTest.keyClick(window, Qt.Key_F8)
            app.processEvents()
            assert opened.call_count == 1
            assert set(area.banners) == {"feedback", "update"}
            area.banners["feedback"].primary.click()
            assert opened.call_count == 2
        assert set(area.banners) == {"update"}
        with patch("windows.main_window.webbrowser.open", return_value=True) as opened:
            QTest.keyClick(window, Qt.Key_F9)
            app.processEvents()
            assert opened.call_count == 1
        assert not area.banners
        assert area.toolbar.isHidden()
        assert not app.settings.get("feedback-shown")
        assert not app.settings.get("dismissed-update-version")
        passed = True
    except Exception:
        traceback.print_exc()
    finally:
        app.quit()

assert app.gui()
# Start after GUI initialization; slow builders may process events during gui().
QTimer.singleShot(4000, verify)
app.exec_()
assert passed, "Notification startup checks failed"
'''
        source = str(Path(__file__).resolve().parents[1])
        env = dict(os.environ, PYTHONPATH=source, QT_QPA_PLATFORM="offscreen",
                   QT_QUICK_BACKEND="software")
        result = subprocess.run([sys.executable, "-c", script], env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                universal_newlines=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout[-16000:])
