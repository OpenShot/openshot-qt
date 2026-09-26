"""Shared notification layout, release dismissal, and theme behavior."""

import importlib
import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

PATH = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if PATH not in sys.path:
    sys.path.append(PATH)

from qt_api import QApplication, QMainWindow, QAction, QColor, Qt, QT_API
from classes.notifications import should_notify_update
from windows.notifications import NotificationBanner, notification_area, UpdateNotificationController, banner_colors

binding = {"pyqt5": "PyQt5", "pyqt6": "PyQt6", "pyside6": "PySide6"}[QT_API]
QTest = importlib.import_module(binding + ".QtTest").QTest


class Settings:
    def __init__(self):
        self.data = {"dismissed-update-version": ""}
        self.saved = {}

    def get(self, key):
        return self.data.get(key)

    def set(self, key, value):
        self.data[key] = value

    def save(self):
        self.saved = dict(self.data)


class NotificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def make_window(self):
        window = QMainWindow()
        window.resize(1100, 650)
        window.addToolBar("Main").addAction("Open")
        window.actionUpdate = QAction("Update", window)
        self.addCleanup(window.deleteLater)
        return window

    def test_numeric_release_order_and_dismissed_release(self):
        self.assertTrue(should_notify_update("4.10.0", "4.9.0", "4.9.1"))
        self.assertFalse(should_notify_update("4.9.0", "4.10.0", ""))
        self.assertFalse(should_notify_update("4.1.0", "4.0.0", "4.1"))
        self.assertFalse(should_notify_update("4.1.0", "4.0.0", "4.2.0"))
        self.assertFalse(should_notify_update("<invalid>", "4.0.0", ""))

    def test_dismissal_survives_restart_and_next_release_reappears(self):
        settings = Settings()
        controller = UpdateNotificationController(self.make_window(), settings, str, "4.0.0", lambda: True)
        controller.offer("4.1.0")
        controller.banner.close_button.click()
        self.assertEqual(settings.saved["dismissed-update-version"], "4.1.0")
        controller.offer("4.1.0")
        self.assertIsNone(controller.banner)
        restarted_settings = Settings()
        restarted_settings.data = dict(settings.saved)
        restarted = UpdateNotificationController(self.make_window(), restarted_settings, str, "4.0.0", lambda: True)
        restarted.offer("4.1.0")
        self.assertIsNone(restarted.banner)
        restarted.offer("4.2.0")
        self.assertIsNotNone(restarted.banner)
        self.assertEqual(restarted.version, "4.2.0")

    def test_preview_can_be_dismissed_without_saving(self):
        settings = Settings()
        controller = UpdateNotificationController(self.make_window(), settings, str, "4.0.0", lambda: True, preview=True)
        controller.offer("4.0.0")
        controller.banner.close_button.click()
        controller.offer("4.1.0")
        self.assertIsNone(controller.banner)
        self.assertEqual(settings.saved, {})

    def test_duplicate_response_and_failed_browser_keep_existing_banner(self):
        controller = UpdateNotificationController(self.make_window(), Settings(), str, "4.0.0", lambda: False)
        controller.offer("4.2.0")
        original = controller.banner
        controller.offer("4.2.0")
        controller.offer("4.1.0")
        self.assertIs(controller.banner, original)
        controller.banner.primary.click()
        self.assertIs(controller.banner, original)
        self.assertEqual(controller.settings.saved, {})

    def test_stale_response_does_not_change_menu_version(self):
        controller = UpdateNotificationController(self.make_window(), Settings(), str, "4.0.0", lambda: True)
        controller.offer("4.2.0")
        tooltip = controller.window.actionUpdate.toolTip()
        controller.offer("4.1.0")
        self.assertEqual(controller.window.actionUpdate.toolTip(), tooltip)
        self.assertEqual(controller.version, "4.2.0")

    def test_equivalent_releases_do_not_duplicate_banner(self):
        controller = UpdateNotificationController(self.make_window(), Settings(), str, "4.0.0", lambda: True)
        controller.offer("4.1")
        banner = controller.banner
        controller.offer("4.1.0")
        self.assertIs(controller.banner, banner)

    def test_menu_navigation_after_saved_dismissal_and_failure_feedback(self):
        settings = Settings()
        settings.set("dismissed-update-version", "4.1.0")
        open_download = Mock(return_value=False)
        controller = UpdateNotificationController(self.make_window(), settings, str, "4.0.0", open_download)
        controller.offer("4.1.0")
        self.assertEqual(controller.version, "4.1.0")
        self.assertIsNone(controller.banner)
        with patch("windows.notifications.QMessageBox.warning") as warning:
            self.assertFalse(controller.activate())
        warning.assert_called_once()
        open_download.return_value = True
        self.assertTrue(controller.activate())

    def test_browser_exception_does_not_escape_qt_slot(self):
        controller = UpdateNotificationController(self.make_window(), Settings(), str, "4.0.0", Mock(side_effect=OSError("no browser")))
        controller.offer("4.1.0")
        controller.banner.primary.click()
        self.assertIsNotNone(controller.banner)
        self.assertEqual(controller.settings.saved, {})

    def test_dismiss_does_not_overwrite_a_newer_saved_version(self):
        settings = Settings()
        controller = UpdateNotificationController(self.make_window(), settings, str, "4.0.0", lambda: True)
        controller.offer("4.1.0")
        settings.set("dismissed-update-version", "4.2.0")
        controller.dismiss()
        self.assertEqual(settings.get("dismissed-update-version"), "4.2.0")

    def test_save_failure_still_suppresses_update_for_session(self):
        settings = Settings()
        controller = UpdateNotificationController(self.make_window(), settings, str, "4.0.0", lambda: True)
        controller.offer("4.1.0")
        with patch.object(settings, "save", side_effect=OSError("disk full")):
            controller.dismiss()
        controller.offer("4.1")
        self.assertIsNone(controller.banner)

    def test_shared_area_order_collapse_and_theme_switches(self):
        window = self.make_window()
        area = notification_area(window)
        for key in ("update", "feedback"):
            banner = NotificationBanner(window, key, "Open", lambda: None,
                                        lambda checked=False, k=key: area.remove(k), str)
            area.add(key, banner)
        self.assertIs(area.layout.itemAt(0).widget(), area.banners["feedback"])
        self.assertIs(area.layout.itemAt(1).widget(), area.banners["update"])
        window.show()
        self.app.processEvents()
        window.removeToolBarBreak(area.toolbar)
        self.app.processEvents()
        self.app.processEvents()
        self.assertTrue(window.toolBarBreak(area.toolbar))
        for theme in ("Cosmic Dusk", "Humanity: Dark", "Retro"):
            area.apply_theme(SimpleNamespace(name=theme))
            for banner in area.banners.values():
                colors = banner_colors(window, SimpleNamespace(name=theme), banner.icon_name)
                self.assertIn(colors["surface"], banner.styleSheet())
                self.assertLess(banner.close_button.geometry().right(), banner.width())
        area.banners["feedback"].close_button.click()
        self.assertFalse(area.toolbar.isHidden())
        area.banners["update"].close_button.click()
        self.assertTrue(area.toolbar.isHidden())
        # A stored workspace's visible toolbar state cannot revive empty banners.
        area.toolbar.show()
        self.app.processEvents()
        self.assertTrue(area.toolbar.isHidden())
        window.close()

    def test_theme_text_contrast(self):
        def luminance(color):
            c = QColor(color)
            channels = [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4
                        for x in (c.redF(), c.greenF(), c.blueF())]
            return sum(a * b for a, b in zip(channels, (0.2126, 0.7152, 0.0722)))
        for name in ("Cosmic Dusk", "Humanity: Dark", "Retro"):
            for kind in ("update", "feedback"):
                colors = banner_colors(self.make_window(), SimpleNamespace(name=name), kind)
                for role in ("text", "action", "close"):
                    values = sorted([luminance(colors["surface"]), luminance(colors[role])])
                    self.assertGreaterEqual((values[1] + 0.05) / (values[0] + 0.05), 4.5)

    def test_banner_surface_click_and_dismiss_are_separate(self):
        window = self.make_window()
        action = Mock()
        dismiss = Mock()
        banner = NotificationBanner(window, "Your feedback matters", "Share feedback",
                                    action, dismiss, str, icon_name="feedback")
        area = notification_area(window)
        area.add("feedback", banner)
        window.show()
        self.app.processEvents()
        self.assertEqual(banner.cursor().shape(), Qt.PointingHandCursor)
        self.assertTrue(banner.message.testAttribute(Qt.WA_TransparentForMouseEvents))
        self.assertIn("QFrame#notificationBanner:hover", banner.styleSheet())
        for child in (banner.message, banner.symbol):
            self.assertIs(QApplication.widgetAt(child.mapToGlobal(child.rect().center())), banner)
        for point in (banner.rect().center(), banner.message.geometry().center(),
                      banner.symbol.geometry().center()):
            QTest.mouseClick(banner, Qt.LeftButton, pos=point)
        banner.primary.click()
        self.assertEqual(action.call_count, 4)
        banner.close_button.click()
        dismiss.assert_called_once()
        self.assertEqual(action.call_count, 4)
        window.close()
