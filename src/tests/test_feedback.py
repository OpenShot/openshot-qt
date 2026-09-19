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
from classes.feedback import FeedbackPolicy, survey_url, FEEDBACK_DELAY_SECONDS
from classes import info
from windows.feedback import FeedbackController


class Settings:
    def __init__(self):
        self.data = {"feedback-shown": False, "feedback-use-seconds": 0,
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

    def test_cumulative_use_and_one_time_consumption(self):
        settings = Settings()
        policy = FeedbackPolicy(settings, info.VERSION)
        for category in ("structure", "structure", "adjustments"):
            policy.record_action(category)
        self.assertFalse(policy.advance(900))
        restarted = Settings()
        restarted.data = dict(settings.saved)
        policy = FeedbackPolicy(restarted, info.VERSION)
        self.assertTrue(policy.advance(900))
        self.assertTrue(policy.consume())
        self.assertTrue(restarted.saved["feedback-shown"])
        self.assertFalse(FeedbackPolicy(restarted, info.VERSION).consume())
        self.assertFalse(policy.advance(1800))

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
        for method in ("has_timeline_content", "playback_active"):
            mock = patch.object(controller, method, return_value=method == "has_timeline_content")
            mock.start()
            self.addCleanup(mock.stop)
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
        self.assertTrue(controller.timer.isActive())

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

    def test_foreground_time_and_suspend_guard(self):
        controller = self.make_controller(Settings())
        controller.last_input = 100
        controller.last_tick = 100
        controller.was_active = True
        with patch.object(controller.window, "isActiveWindow", return_value=True), \
                patch.object(controller.window, "isVisible", return_value=True), \
                patch("windows.feedback.time.monotonic", return_value=105):
            controller.tick()
        self.assertEqual(controller.settings.get("feedback-use-seconds"), 5)
        with patch("windows.feedback.time.monotonic", return_value=3700):
            controller.tick()
        self.assertEqual(controller.settings.get("feedback-use-seconds"), 5)

    def test_due_invitation_waits_for_modal_to_close(self):
        controller = self.make_controller(Settings())
        controller.settings.set("feedback-use-seconds", FEEDBACK_DELAY_SECONDS)
        for category in ("structure", "structure", "adjustments"):
            controller.record_action(category)
        controller.last_input = 0
        with patch.object(controller.window, "isActiveWindow", return_value=True), \
                patch.object(controller.window, "isVisible", return_value=True):
            with patch("windows.feedback.QApplication.activeModalWidget", return_value=object()):
                controller.tick()
            self.assertFalse(controller.policy.shown)
            controller.tick()
            self.assertIsNotNone(controller.banner)
            self.assertFalse(controller.policy.shown)

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

    def test_unanswered_banner_returns_on_next_session(self):
        settings = Settings()
        controller = self.make_controller(settings)
        for category in ("structure", "structure", "adjustments"):
            controller.record_action(category)
        controller.policy.advance(FEEDBACK_DELAY_SECONDS)
        controller.show_invitation()
        self.assertFalse(settings.get("feedback-shown"))
        restarted_settings = Settings()
        restarted_settings.data = dict(settings.saved)
        restarted = self.make_controller(restarted_settings)
        restarted.last_input = 0
        with patch.object(restarted.window, "isActiveWindow", return_value=True), \
                patch.object(restarted.window, "isVisible", return_value=True):
            restarted.tick()
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

    def test_invalid_elapsed_settings_do_not_disable_feedback(self):
        for value in ("invalid", float("nan"), float("inf"), -10, {}):
            settings = Settings()
            settings.set("feedback-use-seconds", value)
            self.assertFalse(FeedbackPolicy(settings, info.VERSION).advance(5))
            self.assertEqual(settings.get("feedback-use-seconds"), 5)

    def test_background_and_popup_time_does_not_count(self):
        controller = self.make_controller(Settings())
        controller.last_input = 100
        controller.last_tick = 100
        controller.was_active = True
        with patch.object(controller.window, "isActiveWindow", return_value=True), \
                patch.object(controller.window, "isVisible", return_value=True), \
                patch("windows.feedback.QApplication.activePopupWidget", return_value=object()), \
                patch("windows.feedback.time.monotonic", return_value=105):
            controller.tick()
        self.assertEqual(controller.settings.get("feedback-use-seconds"), 0)

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
            policy = FeedbackPolicy(settings, info.VERSION)
            for category in ("structure", "titles", "profile"):
                policy.record_action(category)
            self.assertFalse(policy.advance(900))
            restarted = SettingStore()
            restarted.load()
            self.assertEqual(restarted.get("feedback-use-seconds"), 900)
            policy = FeedbackPolicy(restarted, info.VERSION)
            self.assertTrue(policy.advance(900))
            self.assertTrue(policy.consume())
            restarted.set("dismissed-update-version", "4.1.0")
            restarted.save()
            restarted.restore("General")
            restored = SettingStore()
            restored.load()
            self.assertTrue(restored.get("feedback-shown"))
            self.assertEqual(restored.get("feedback-use-seconds"), FEEDBACK_DELAY_SECONDS)
            self.assertEqual(restored.get("feedback-release"), info.VERSION)
            self.assertEqual(restored.get("feedback-action-count"), 3)
            self.assertEqual(restored.get("feedback-action-categories"), ["profile", "structure", "titles"])
            self.assertEqual(restored.get("dismissed-update-version"), "4.1.0")
            self.assertEqual(restored.get("unique_install_id"), "persistent-test-id")
            self.assertEqual(restored.get("actionShareFeedback"), "F8")
            self.assertEqual(restored.get("actionUpdate"), "F9")

    def test_idle_empty_background_and_playback_time(self):
        for active, content, playing, idle, expected in (
                (True, True, False, 20, 5), (True, True, False, 61, 0),
                (True, False, False, 20, 0), (False, True, False, 20, 0),
                (True, True, True, 120, 5), (False, True, True, 20, 0)):
            with self.subTest(active=active, content=content, playing=playing, idle=idle):
                controller = self.make_controller(Settings())
                controller.last_tick = 200
                controller.last_input = 205 - idle
                controller.was_active = True
                with patch.object(controller.window, "isActiveWindow", return_value=active), \
                        patch.object(controller.window, "isVisible", return_value=True), \
                        patch.object(controller, "has_timeline_content", return_value=content), \
                        patch.object(controller, "playback_active", return_value=playing), \
                        patch("windows.feedback.time.monotonic", return_value=205):
                    controller.tick()
                self.assertEqual(controller.settings.get("feedback-use-seconds"), expected)

    def test_eligible_banner_waits_for_quiet_paused_input(self):
        controller = self.make_controller(Settings())
        for category in ("structure", "adjustments", "export"):
            controller.record_action(category)
        controller.policy.advance(FEEDBACK_DELAY_SECONDS)
        controller.last_input = 100
        controller.last_tick = 100
        with patch.object(controller.window, "isActiveWindow", return_value=True), \
                patch.object(controller.window, "isVisible", return_value=True):
            with patch("windows.feedback.time.monotonic", return_value=105):
                controller.tick()
            self.assertIsNone(controller.banner)
            with patch("windows.feedback.time.monotonic", return_value=110), \
                    patch.object(controller, "playback_active", return_value=True):
                controller.tick()
            self.assertIsNone(controller.banner)
            with patch("windows.feedback.time.monotonic", return_value=115):
                controller.tick()
            self.assertIsNotNone(controller.banner)
            self.assertFalse(controller.policy.shown)

    def test_input_filter_observes_only_our_window(self):
        from qt_api import QEvent, QWidget
        controller = self.make_controller(Settings())
        other_window = QWidget()
        self.addCleanup(other_window.deleteLater)
        controller.last_input = 0
        event = QEvent(QEvent.KeyPress)
        with patch("windows.feedback.time.monotonic", return_value=42):
            self.assertFalse(controller.eventFilter(other_window, event))
            self.assertEqual(controller.last_input, 0)
            self.assertFalse(controller.eventFilter(controller.window, event))
            self.assertEqual(controller.last_input, 42)

    def test_mouse_move_type_without_mouse_event_does_not_reset_idle_time(self):
        from qt_api import QContextMenuEvent, QEvent, QPoint

        # Sentry reported a QContextMenuEvent wrapper whose type was MouseMove.
        class MisclassifiedContextMenuEvent(QContextMenuEvent):
            def type(self):
                return QEvent.MouseMove

        controller = self.make_controller(Settings())
        events = (QEvent(QEvent.MouseMove),
                  MisclassifiedContextMenuEvent(QContextMenuEvent.Mouse, QPoint(1, 1)))
        controller.last_input = 0
        with patch("windows.feedback.time.monotonic", return_value=42):
            for event in events:
                with self.subTest(event=type(event).__name__):
                    self.assertFalse(controller.eventFilter(controller.window, event))
                    self.assertEqual(controller.last_input, 0)

    def test_mouse_drag_resets_idle_time_but_hover_does_not(self):
        from qt_api import QEvent, QMouseEvent, QPointF, Qt, QWidget
        controller = self.make_controller(Settings())
        child = QWidget(controller.window)
        controller.last_input = 0
        with patch("windows.feedback.time.monotonic", return_value=42):
            for buttons, expected in ((Qt.NoButton, 0), (Qt.LeftButton, 42)):
                with self.subTest(buttons=buttons):
                    event = QMouseEvent(QEvent.MouseMove, QPointF(1, 1),
                                        Qt.NoButton, buttons, Qt.NoModifier)
                    self.assertFalse(controller.eventFilter(child, event))
                    self.assertEqual(controller.last_input, expected)

    def test_shutdown_removes_input_filter_and_flushes_time(self):
        from qt_api import QEvent, QKeyEvent, Qt
        controller = self.make_controller(Settings())
        controller.policy.advance(25)
        controller.shutdown()
        self.assertFalse(controller.timer.isActive())
        self.assertEqual(controller.settings.saved["feedback-use-seconds"], 25)
        controller.last_input = 0
        with patch("windows.feedback.time.monotonic", return_value=42):
            QApplication.sendEvent(controller.window, QKeyEvent(QEvent.KeyPress, Qt.Key_A, Qt.NoModifier))
        self.assertEqual(controller.last_input, 0)

    def test_event_filter_does_not_access_deleted_main_window(self):
        from qt_api import QEvent, QCoreApplication, QWidget
        controller = self.make_controller(Settings())
        controller.timer.stop()
        window = controller.window
        window.deleteLater()
        QCoreApplication.sendPostedEvents(window, QEvent.DeferredDelete)
        self.assertTrue(isdeleted(window))
        other = QWidget()
        with patch.object(sys, "excepthook") as errors:
            self.assertFalse(controller.eventFilter(other, QEvent(QEvent.KeyPress)))
        errors.assert_not_called()
        other.deleteLater()


class EligibilityPolicyTests(unittest.TestCase):
    def test_requires_time_and_three_actions_in_two_categories(self):
        for actions, expected in (([], False), (["structure"] * 3, False),
                                  (["structure", "titles"], False),
                                  (["structure", "structure", "titles"], True)):
            with self.subTest(actions=actions):
                policy = FeedbackPolicy(Settings(), info.VERSION)
                for category in actions:
                    policy.record_action(category)
                self.assertFalse(policy.advance(FEEDBACK_DELAY_SECONDS - 1))
                self.assertEqual(policy.advance(1), expected)

    def test_time_can_complete_before_actions(self):
        policy = FeedbackPolicy(Settings(), info.VERSION)
        self.assertFalse(policy.advance(FEEDBACK_DELAY_SECONDS))
        for category in ("effects", "profile", "export"):
            policy.record_action(category)
        self.assertTrue(policy.advance(0))

    def test_new_release_resets_time_and_acknowledgement_only(self):
        settings = Settings()
        policy = FeedbackPolicy(settings, "4.0.0")
        for category in ("structure", "titles", "export"):
            policy.record_action(category)
        policy.advance(FEEDBACK_DELAY_SECONDS)
        policy.consume()
        restarted = FeedbackPolicy(settings, "4.0.0")
        self.assertTrue(restarted.shown)
        upgraded = FeedbackPolicy(settings, "4.1.0")
        self.assertFalse(upgraded.shown)
        self.assertTrue(upgraded.experienced)
        self.assertEqual(settings.get("feedback-use-seconds"), 0)
        self.assertFalse(upgraded.advance(FEEDBACK_DELAY_SECONDS - 1))
        self.assertTrue(upgraded.advance(1))

    def test_partial_action_progress_survives_upgrade(self):
        settings = Settings()
        policy = FeedbackPolicy(settings, "4.0.0")
        policy.record_action("structure")
        policy.advance(300)
        upgraded = FeedbackPolicy(settings, "4.1.0")
        self.assertEqual(upgraded.action_count, 1)
        self.assertEqual(upgraded.categories, {"structure"})
        self.assertFalse(upgraded.advance(FEEDBACK_DELAY_SECONDS))
        upgraded.record_action("titles")
        upgraded.record_action("profile")
        self.assertTrue(upgraded.advance(0))

    def test_legacy_dismissal_is_preserved_but_foreground_timer_is_discarded(self):
        settings = Settings()
        settings.data.pop("feedback-release")
        settings.set("feedback-shown", True)
        settings.set("feedback-use-seconds", 1800)
        policy = FeedbackPolicy(settings, "4.0.0")
        self.assertTrue(policy.shown)
        self.assertEqual(settings.get("feedback-use-seconds"), 0)
        self.assertFalse(FeedbackPolicy(settings, "4.1.0").shown)

    def test_counts_are_bounded_and_unknown_actions_ignored(self):
        policy = FeedbackPolicy(Settings(), info.VERSION)
        policy.record_action("open-properties")
        self.assertEqual(policy.action_count, 0)
        for _ in range(10):
            policy.record_action("structure")
        self.assertEqual(policy.action_count, 3)
        self.assertFalse(policy.experienced)
        policy.record_action("profile")
        self.assertTrue(policy.experienced)
        before = dict(policy.settings.data)
        policy.record_action("export")
        self.assertEqual(before, policy.settings.data)

    def test_short_session_flush_preserves_progress(self):
        settings = Settings()
        policy = FeedbackPolicy(settings, info.VERSION)
        policy.advance(25)
        policy.flush()
        restarted_settings = Settings()
        restarted_settings.data = dict(settings.saved)
        restarted = FeedbackPolicy(restarted_settings, info.VERSION)
        restarted.advance(5)
        self.assertEqual(restarted_settings.get("feedback-use-seconds"), 30)

    def test_corrupt_action_state_is_not_eligibility(self):
        for count, categories in (("3", ["structure", "titles"]),
                                   (3, "structure"), (-1, []),
                                   (3, [[], {}, "unknown", "structure"])):
            settings = Settings()
            settings.set("feedback-action-count", count)
            settings.set("feedback-action-categories", categories)
            policy = FeedbackPolicy(settings, info.VERSION)
            self.assertFalse(policy.advance(FEEDBACK_DELAY_SECONDS))
            policy.record_action("profile")

    def test_actions_still_accumulate_after_banner_acknowledgement(self):
        policy = FeedbackPolicy(Settings(), info.VERSION)
        policy.consume()
        for category in ("structure", "titles", "export"):
            policy.record_action(category)
        self.assertTrue(policy.experienced)
        self.assertFalse(policy.advance(FEEDBACK_DELAY_SECONDS))


class FeedbackActionHookTests(unittest.TestCase):
    def setUp(self):
        from classes.query import Clip
        self.policy = FeedbackPolicy(Settings(), info.VERSION)
        self.controller = SimpleNamespace(preview=False, policy=self.policy,
                                          record_action=self.policy.record_action)
        self.clips = {key: SimpleNamespace(data={"id": key, "start": 0, "end": 10})
                      for key in ("one", "two")}
        def get_clip(id):
            return self.clips.get(id)

        for mock in (patch("classes.app.get_app", return_value=SimpleNamespace(
                window=SimpleNamespace(feedback_controller=self.controller))),
                patch.object(Clip, "get", side_effect=get_clip)):
            mock.start()
            self.addCleanup(mock.stop)

    def test_command_counts_once_for_multiple_clips_and_skips_noops(self):
        from classes.feedback import feedback_command

        @feedback_command("structure")
        def trim(clip_ids, end):
            for clip_id in clip_ids:
                self.clips[clip_id].data["end"] = end
            return "committed"

        self.assertEqual(trim(["one", "two"], 8), "committed")
        self.assertEqual(self.policy.action_count, 1)
        trim(clip_ids=["one", "two"], end=8)
        trim([], 4)
        self.assertEqual(self.policy.action_count, 1)
        trim(["one"], 7)
        self.assertEqual(self.policy.action_count, 2)
        self.assertEqual(self.policy.categories, {"structure"})

    def test_qt_checked_argument_is_ignored_but_real_arguments_are_preserved(self):
        from functools import partial
        from qt_api import QAction
        from classes.feedback import feedback_command

        clips = self.clips

        class Commands:
            @feedback_command("structure")
            def trim(self, clip_ids, end):
                clips["one"].data["end"] = end
                return end

        commands = Commands()
        for checked, end in ((False, 8), (True, 7)):
            with self.subTest(checked=checked):
                action = QAction()
                action.setCheckable(True)
                action.triggered.connect(partial(commands.trim, ["one"], end))
                with patch.object(sys, "excepthook") as errors:
                    action.triggered.emit(checked)
                errors.assert_not_called()
                self.assertEqual(self.clips["one"].data["end"], end)
        self.assertEqual(self.policy.action_count, 2)
        # A legitimate boolean parameter must not be removed.
        self.assertIs(commands.trim(["one"], False), False)
        # Do not hide ordinary programming errors with other extra arguments.
        self.assertRaises(TypeError, commands.trim, ["one"], 7, "unexpected")

    def test_cancelled_or_failed_command_does_not_count(self):
        from classes.feedback import feedback_command

        @feedback_command("adjustments")
        def adjust(clip_ids, fail=False):
            if fail:
                raise ValueError("edit failed")
            return False  # cancelled without mutation

        self.assertFalse(adjust(["one"]))
        with self.assertRaises(ValueError):
            adjust(["one"], fail=True)
        self.assertEqual(self.policy.action_count, 0)

        @feedback_command("structure")
        def next_command(clip_ids):
            self.clips["one"].data["end"] = 6

        next_command(["one"])
        self.assertEqual(self.policy.action_count, 1)

    def test_nested_commands_share_a_snapshot_but_other_threads_do_not(self):
        from concurrent.futures import ThreadPoolExecutor
        from classes import feedback

        @feedback.feedback_command("adjustments")
        def inner(clip_ids):
            return "edited"

        @feedback.feedback_command("structure")
        def outer(clip_ids):
            self.assertEqual(inner(clip_ids), "edited")
            # A command in another thread must still take its own snapshot.
            with ThreadPoolExecutor(max_workers=1) as pool:
                self.assertEqual(pool.submit(inner, ["two"]).result(timeout=5), "edited")

        with patch.object(feedback, "_feedback_clip_snapshot", return_value={}) as snapshot:
            outer(["one"])
            self.assertEqual(snapshot.call_count, 2)
            snapshot.assert_any_call(["one"])
            snapshot.assert_any_call(["two"])
            inner(["one"])
            self.assertEqual(snapshot.call_count, 3)

    def test_tracking_failure_does_not_break_user_command(self):
        from classes.feedback import feedback_command

        @feedback_command("structure")
        def trim(clip_ids):
            self.clips["one"].data["end"] = 5
            return 17

        self.controller.record_action = Mock(side_effect=OSError("settings unavailable"))
        self.assertEqual(trim(["one"]), 17)
        self.assertEqual(self.clips["one"].data["end"], 5)

    def test_reader_serialization_and_transition_changes_do_not_count(self):
        from classes.feedback import record_feedback_changes
        before = {"one": dict(self.clips["one"].data, reader={"path": "media.mp4"})}
        record_feedback_changes("adjustments", before)
        record_feedback_changes("structure", {"transition-id": {"start": 0, "end": 1}})
        self.assertEqual(self.policy.action_count, 0)

    def test_resize_counts_bound_changes_but_not_movement(self):
        from classes.feedback import record_feedback_changes
        before = {key: dict(clip.data) for key, clip in self.clips.items()}
        self.clips["one"].data["position"] = 4
        record_feedback_changes("structure", before, fields=("start", "end"))
        self.assertEqual(self.policy.action_count, 0)
        self.clips["one"].data["end"] = 8
        self.clips["two"].data["end"] = 9
        record_feedback_changes("structure", before, fields=("start", "end"))
        self.assertEqual(self.policy.action_count, 1)

    def test_completed_milestones_skip_clip_queries(self):
        from classes.feedback import feedback_command
        from classes.query import Clip
        for category in ("structure", "effects", "titles"):
            self.policy.record_action(category)

        @feedback_command("adjustments")
        def adjust(clip_ids):
            return "done"

        with patch.object(Clip, "get") as query:
            self.assertEqual(adjust(["one"]), "done")
            query.assert_not_called()

    def test_property_transaction_counts_once_and_cancel_does_not_count(self):
        from windows.views.properties_tableview import PropertiesTableView
        originals = {key: {"type": "clip", "data": dict(clip.data)}
                     for key, clip in self.clips.items()}
        for clip in self.clips.values():
            clip.save = Mock()
            clip.data["end"] = 8
        app = SimpleNamespace(updates=Mock())
        view = SimpleNamespace(transaction_id="drag", original_data_map=originals,
                               update_in_progress=True)
        with patch("windows.views.properties_tableview.get_app", return_value=app):
            PropertiesTableView.finalize_transaction(view)
            PropertiesTableView.finalize_transaction(view)
        self.assertEqual(self.policy.action_count, 1)
        self.assertEqual(self.policy.categories, {"adjustments"})
        view.transaction_id = "cancelled-drag"
        view.original_data_map = originals
        view._restore_original_objects = Mock()
        with patch("windows.views.properties_tableview.get_app", return_value=app):
            PropertiesTableView.cancel_transaction(view)
        self.assertEqual(self.policy.action_count, 1)
