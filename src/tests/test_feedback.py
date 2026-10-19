"""Survey persistence, routing, and actual Qt invitation behavior."""

import base64
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch, Mock
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

PATH = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if PATH not in sys.path:
    sys.path.append(PATH)

from qt_api import QApplication, QMainWindow, isdeleted
from classes.feedback import FeedbackPolicy, survey_url
from classes import info
from windows.feedback import FeedbackController


class Settings:
    def __init__(self):
        self.data = {"feedback-shown": False,
                     "unique_install_id": "test-install-id", "feedback-release": info.VERSION}
        self.saved = {}

    def get(self, key):
        return self.data.get(key)

    def set(self, key, value):
        self.data[key] = value

    def save(self):
        self.saved = dict(self.data)


class FeedbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_one_time_consumption_survives_restart(self):
        settings = Settings()
        policy = FeedbackPolicy(settings, info.VERSION)
        self.assertFalse(policy.shown)
        self.assertTrue(policy.consume())
        self.assertTrue(settings.saved["feedback-shown"])
        restarted = Settings()
        restarted.data = dict(settings.saved)
        self.assertFalse(FeedbackPolicy(restarted, info.VERSION).consume())

    def test_failed_persistence_does_not_consume_invitation(self):
        policy = FeedbackPolicy(Settings(), info.VERSION)
        with patch.object(policy.settings, "save", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                policy.consume()
        self.assertFalse(policy.shown)

    def decode_context(self, url, path="/feedback/"):
        parsed = urlparse(url)
        self.assertEqual(parsed.scheme, "https")
        self.assertEqual(parsed.netloc, "www.openshot.org")
        self.assertEqual(parsed.path, path)
        params = parse_qs(parsed.query)
        self.assertEqual(set(params), {"context"})
        context, = params["context"]
        self.assertRegex(context, r"^[A-Za-z0-9_-]+$")
        return json.loads(base64.urlsafe_b64decode(context + "=" * (-len(context) % 4)))

    def test_url_encodes_v1_context_and_unicode_id(self):
        distribution = {"official": True, "package_type": "exe",
                        "app_version": "4.0.1", "platform": "windows",
                        "architecture": "AMD64", "build_name": "test-build"}
        before = dict(distribution)
        payload = self.decode_context(survey_url(distribution, "id&with spaces/é?"))
        self.assertEqual(payload, {"v": 1, "version": "4.0.1", "os": "windows",
                                   "source": "direct", "install_uuid": "id&with spaces/é?"})
        self.assertEqual(distribution, before)

    def test_context_source_and_os_mapping(self):
        for kind, official, source in (
                ("exe", True, "direct"), ("appimage", True, "direct"),
                ("appbundle", True, "direct"), ("exe", False, "unknown"),
                ("appimage", False, "unknown"), ("appbundle", False, "unknown"),
                ("msix", True, "microsoft-store"), ("msix", False, "unknown"),
                ("snap", False, "snap"), ("flatpak", False, "flatpak"),
                ("unknown", False, "unknown")):
            with self.subTest(kind=kind, official=official):
                payload = self.decode_context(survey_url(
                    {"official": official, "package_type": kind,
                     "app_version": "4.0.1", "platform": "darwin"}, "test-id"))
                self.assertEqual(payload["source"], source)
                self.assertEqual(payload["os"], "macos")

    def test_context_os_uses_only_supported_values(self):
        for system, expected in (("windows", "windows"), ("Linux", "linux"),
                                 ("darwin", "macos"), ("macos", "macos"),
                                 ("FreeBSD", "unknown"), ("", "unknown")):
            with self.subTest(system=system):
                payload = self.decode_context(survey_url(
                    {"app_version": "4.0.1", "platform": system}, "test-id"))
                self.assertEqual(payload["os"], expected)
                self.assertEqual(payload["source"], "unknown")

    def make_controller(self, settings, preview=False):
        window = QMainWindow()
        window.resize(1000, 700)
        window.menuHelp = window.menuBar().addMenu("Help")
        window.actionReportBug = window.menuHelp.addAction("Report a Bug…")
        window.menuHelp.addSeparator()
        window.actionUpdate = window.menuHelp.addAction("Update Available")
        window.menuHelp.addSeparator()
        window.actionAbout = window.menuHelp.addAction("About")
        controller = FeedbackController(window, settings, lambda text: text, preview=preview)
        self.addCleanup(lambda: window.deleteLater() if not isdeleted(window) else None)
        self.addCleanup(lambda: controller.timer.stop() if not isdeleted(controller.timer) else None)
        return controller


    def test_help_opens_browser_without_acknowledging_banner(self):
        settings = Settings()
        controller = self.make_controller(settings)
        self.assertFalse(controller.action.icon().isNull())
        actions = controller.window.menuHelp.actions()
        self.assertEqual(actions.index(controller.action) + 1,
                         actions.index(controller.window.actionUpdate))
        self.assertTrue(actions[actions.index(controller.action) - 1].isSeparator())
        self.assertTrue(actions[actions.index(controller.window.actionUpdate) + 1].isSeparator())
        with patch("windows.feedback.QDesktopServices.openUrl", return_value=True) as opened:
            controller.action.trigger()
        self.assertEqual(self.decode_context(opened.call_args[0][0].toString())["install_uuid"],
                         "test-install-id")
        self.assertIsNone(controller.banner)
        self.assertFalse(settings.get("feedback-shown"))
        self.assertTrue(controller.action.isEnabled())
        self.assertFalse(controller.timer.isActive())

    def test_help_browser_failure_allows_retry_without_nag(self):
        controller = self.make_controller(Settings())
        with patch("windows.feedback.QDesktopServices.openUrl", return_value=False), \
                patch("windows.feedback.QMessageBox.warning") as warning:
            controller.action.trigger()
        warning.assert_called_once()
        self.assertIsNone(controller.banner)
        self.assertTrue(controller.action.isEnabled())
        self.assertFalse(controller.policy.shown)

    def test_banner_and_help_use_active_interface_language(self):
        from classes import info

        languages = [(code, code + "/") for code in (
            "ar", "bn", "hr", "nl", "fr", "fi", "de", "hi", "is", "id", "it",
            "ja", "ko", "nb", "fa", "pl", "pt", "ro", "ru", "es", "tr", "vi", "uk",
        )] + [("zh_CN", "zh-hans/"), ("zh_TW", "zh-hant/"),
             ("en_US", ""), ("pt_BR", "pt/")]
        distribution = {"app_version": "4.0.1", "platform": "linux"}
        for language, prefix in languages:
            for entry_point in ("banner", "help"):
                with self.subTest(language=language, entry_point=entry_point):
                    settings = Settings()
                    # The active language can override a saved preference (e.g. --lang).
                    settings.set("default-language", "en_US")
                    controller = self.make_controller(settings, preview=True)
                    controller.show_invitation()
                    with patch.object(info, "CURRENT_LANGUAGE", language), \
                            patch("windows.feedback.get_distribution_info", return_value=distribution), \
                            patch("windows.feedback.QDesktopServices.openUrl", return_value=True) as opened:
                        if entry_point == "banner":
                            controller.banner.primary.click()
                        else:
                            controller.action.trigger()
                    opened.assert_called_once()
                    payload = self.decode_context(opened.call_args[0][0].toString(),
                                                  "/" + prefix + "feedback/")
                    self.assertEqual(payload, {"v": 1, "version": "4.0.1", "os": "linux",
                                               "source": "unknown", "install_uuid": "test-install-id"})

    def test_help_remains_usable_after_dismissal_and_restart(self):
        settings = Settings()
        controller = self.make_controller(settings)
        controller.show_invitation()
        controller.banner.close_button.click()
        restarted = self.make_controller(settings)
        for current in (controller, restarted):
            with self.subTest(restarted=current is restarted):
                self.assertTrue(current.action.isEnabled())
                with patch("windows.feedback.QDesktopServices.openUrl", return_value=True) as opened:
                    current.action.trigger()
                    current.action.trigger()
                self.assertEqual(opened.call_count, 2)
                current.show_invitation()
                self.assertIsNone(current.banner)
                self.assertFalse(current.timer.isActive())
                self.assertTrue(settings.get("feedback-shown"))

    def test_help_failure_after_completion_does_not_reset_banner_history(self):
        settings = Settings()
        settings.set("feedback-shown", True)
        controller = self.make_controller(settings)
        with patch("windows.feedback.QDesktopServices.openUrl", return_value=False), \
                patch("windows.feedback.QMessageBox.warning") as warning:
            controller.action.trigger()
        warning.assert_called_once()
        self.assertTrue(controller.action.isEnabled())
        self.assertTrue(settings.get("feedback-shown"))
        controller.show_invitation()
        self.assertIsNone(controller.banner)

    def test_dismissing_automatic_banner_prevents_repeat(self):
        controller = self.make_controller(Settings())
        controller.show_invitation()
        controller.banner.close_button.click()
        controller.show_invitation()
        self.assertIsNone(controller.banner)
        self.assertTrue(controller.area.toolbar.isHidden())
        self.assertTrue(controller.settings.saved["feedback-shown"])

    def test_banner_click_acknowledges_even_when_browser_fails(self):
        for outcome in (False, OSError("no browser")):
            with self.subTest(outcome=outcome):
                controller = self.make_controller(Settings())
                controller.show_invitation()
                with patch("windows.feedback.QDesktopServices.openUrl", return_value=False,
                           side_effect=outcome if isinstance(outcome, Exception) else None), \
                        patch("windows.feedback.QMessageBox.warning") as warning:
                    controller.banner.primary.click()
                warning.assert_called_once()
                self.assertIsNone(controller.banner)
                self.assertTrue(controller.policy.shown)
                self.assertTrue(controller.action.isEnabled())

    def test_successful_export_queues_banner_behind_export_dialog(self):
        settings = Settings()
        controller = self.make_controller(settings)
        self.assertIsNone(controller.banner)
        # A modal export dialog is still open; the banner waits behind it.
        with patch("windows.feedback.QApplication.activeModalWidget", return_value=object()):
            controller.record_export()
        self.assertIsNotNone(controller.banner)
        self.assertIn("feedback", controller.area.banners)
        self.assertFalse(settings.get("feedback-shown"))
        controller.record_export()
        self.assertEqual(list(controller.area.banners), ["feedback"])

    def test_export_after_acknowledgement_does_not_repeat_this_release(self):
        settings = Settings()
        settings.set("feedback-shown", True)
        controller = self.make_controller(settings)
        controller.record_export()
        self.assertIsNone(controller.banner)

    def test_preview_ignores_real_exports(self):
        controller = self.make_controller(Settings(), preview=True)
        controller.timer.stop()
        controller.record_export()
        self.assertIsNone(controller.banner)

    def test_preview_bypasses_saved_nag_without_modifying_settings(self):
        settings = Settings()
        settings.set("feedback-shown", True)
        before = dict(settings.data)
        controller = self.make_controller(settings, preview=True)
        with patch.object(controller.window, "isVisible", return_value=True):
            controller.tick()
        self.assertIsNotNone(controller.banner)
        self.assertFalse(controller.timer.isActive())
        self.assertEqual(settings.data, before)
        self.assertEqual(settings.saved, {})

    def test_banner_preview_close_collapses_toolbar_and_does_not_repeat(self):
        controller = self.make_controller(Settings(), preview=True)
        controller.show_invitation()
        controller.banner.close_button.click()
        self.assertTrue(controller.area.toolbar.isHidden())
        controller.show_invitation()
        self.assertTrue(controller.area.toolbar.isHidden())
        self.assertFalse(controller.policy.shown)

    def test_preview_survey_does_not_consume_real_invitation(self):
        controller = self.make_controller(Settings(), preview=True)
        controller.show_invitation()
        with patch("windows.feedback.QDesktopServices.openUrl", return_value=True):
            controller.open_from_banner()
        self.assertFalse(controller.policy.shown)
        self.assertEqual(controller.settings.saved, {})
        self.assertTrue(controller.area.toolbar.isHidden())


    def test_unanswered_banner_returns_after_next_sessions_export(self):
        settings = Settings()
        controller = self.make_controller(settings)
        controller.record_export()
        self.assertFalse(settings.get("feedback-shown"))
        restarted_settings = Settings()
        restarted_settings.data = dict(settings.data)
        restarted = self.make_controller(restarted_settings)
        self.assertIsNone(restarted.banner)
        restarted.record_export()
        self.assertIsNotNone(restarted.banner)
        restarted.banner.close_button.click()
        self.assertTrue(restarted_settings.saved["feedback-shown"])

    def test_help_does_not_acknowledge_a_visible_banner(self):
        controller = self.make_controller(Settings())
        controller.show_invitation()
        self.assertTrue(controller.action.isEnabled())
        with patch("windows.feedback.QDesktopServices.openUrl", return_value=True):
            controller.action.trigger()
        self.assertIsNotNone(controller.banner)
        self.assertFalse(controller.policy.shown)

    def test_persistence_failure_still_dismisses_for_this_session(self):
        controller = self.make_controller(Settings())
        controller.show_invitation()
        with patch.object(controller.settings, "save", side_effect=OSError("disk full")):
            controller.banner.close_button.click()
        controller.show_invitation()
        self.assertIsNone(controller.banner)
        self.assertTrue(controller.completed)
        self.assertTrue(controller.action.isEnabled())


    def test_real_settings_reload_and_reset_preserve_notification_history(self):
        from classes import info
        from classes.settings import SettingStore

        with tempfile.TemporaryDirectory() as profile, patch.object(info, "USER_PATH", profile):
            settings = SettingStore()
            settings.load()
            settings.set("unique_install_id", "persistent-test-id")
            settings.set("export-celebrated", True)
            self.assertEqual(settings.get("export-celebration"), "first")
            policy = FeedbackPolicy(settings, info.VERSION)
            self.assertTrue(policy.consume())
            restarted = SettingStore()
            restarted.load()
            self.assertTrue(FeedbackPolicy(restarted, info.VERSION).shown)
            restarted.set("dismissed-update-version", "4.1.0")
            restarted.save()
            restarted.restore("General")
            restored = SettingStore()
            restored.load()
            self.assertTrue(restored.get("feedback-shown"))
            self.assertTrue(restored.get("export-celebrated"))
            self.assertEqual(restored.get("feedback-release"), info.VERSION)
            self.assertEqual(restored.get("dismissed-update-version"), "4.1.0")
            self.assertEqual(restored.get("unique_install_id"), "persistent-test-id")
            self.assertEqual(restored.get("actionShareFeedback"), "F8")
            self.assertEqual(restored.get("actionUpdate"), "F9")

    def test_new_release_resets_acknowledgement(self):
        settings = Settings()
        FeedbackPolicy(settings, "4.0.0").consume()
        self.assertTrue(FeedbackPolicy(settings, "4.0.0").shown)
        self.assertFalse(FeedbackPolicy(settings, "4.1.0").shown)

    def test_legacy_dismissal_is_preserved(self):
        settings = Settings()
        settings.data.pop("feedback-release")
        settings.set("feedback-shown", True)
        self.assertTrue(FeedbackPolicy(settings, "4.0.0").shown)
        self.assertFalse(FeedbackPolicy(settings, "4.1.0").shown)
