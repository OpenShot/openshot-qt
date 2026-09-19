"""One-time feedback invitation using the shared notification banners."""

import time

import openshot

from qt_api import QAction, QApplication, QDesktopServices, QTimer, QUrl, QObject, QMessageBox, QEvent, QMouseEvent, QWidget, Qt, isdeleted

from classes import info
from classes.app import get_app
from classes.distribution import get_distribution_info
from classes.feedback import FeedbackPolicy, survey_url
from classes.logger import log
from windows.notifications import NotificationBanner, notification_area, notification_icon

IDLE_SECONDS = 60
QUIET_SECONDS = 10


class FeedbackController(QObject):
    def __init__(self, window, settings, translate, preview=False):
        super().__init__(window)
        _ = translate
        self.window = window
        self.settings = settings
        self.translate = translate
        self.policy = FeedbackPolicy(settings, None if preview else info.VERSION)
        self.preview = preview
        self.presented = False
        self.completed = False
        self.area = notification_area(window)
        self.banner = None
        self.action = QAction(_("Share Feedback…"), window)
        self.action.setObjectName("actionShareFeedback")
        window.actionShareFeedback = self.action
        self.refresh_icon(self.area.theme)
        if hasattr(window, "ThemeChangedSignal"):
            window.ThemeChangedSignal.connect(self.refresh_icon)
        self.action.setIconVisibleInMenu(True)
        self.action.triggered.connect(self.open_from_menu)
        window.menuHelp.insertAction(window.actionUpdate, self.action)
        self.last_tick = time.monotonic()
        self.last_input = self.last_tick
        self.was_active = False
        self.timer = QTimer(self)
        self.timer.setInterval(5000)
        self.timer.timeout.connect(self.tick)
        QApplication.instance().installEventFilter(self)
        if preview:
            self.timer.setInterval(250)
            self.timer.start()
        elif not self.policy.shown:
            self.timer.start()

    def refresh_icon(self, theme=None):
        self.action.setIcon(notification_icon(self.window, "feedback", theme))

    def record_action(self, category):
        if not self.preview:
            self.policy.record_action(category)
        self.last_input = time.monotonic()

    def eventFilter(self, watched, event):
        if isdeleted(self.window):
            return False
        # Observe input without swallowing it or treating passive mouse movement as editing.
        if isinstance(watched, QWidget) and (watched is self.window or self.window.isAncestorOf(watched)):
            if event.type() in (QEvent.KeyPress, QEvent.MouseButtonPress, QEvent.MouseButtonRelease,
                                QEvent.Wheel, QEvent.TouchBegin, QEvent.TouchUpdate, QEvent.WindowActivate):
                self.last_input = time.monotonic()
            elif (event.type() == QEvent.MouseMove and isinstance(event, QMouseEvent)
                  and event.buttons() != Qt.NoButton):
                self.last_input = time.monotonic()
        return False

    def playback_active(self):
        preview = getattr(self.window, "preview_thread", None)
        player = getattr(preview, "player", None)
        return bool(player and player.Mode() == openshot.PLAYBACK_PLAY and player.Speed() != 0)

    def has_timeline_content(self):
        return bool(get_app().project.get("clips"))

    def shutdown(self):
        self.timer.stop()
        QApplication.instance().removeEventFilter(self)
        self.flush()

    def flush(self):
        try:
            self.policy.flush()
        except Exception:
            log.warning("Unable to save feedback editing time", exc_info=True)

    def tick(self):
        if self.preview:
            if self.window.isVisible() and not QApplication.activeModalWidget():
                self.show_invitation()
            return
        now = time.monotonic()
        seconds = now - self.last_tick
        self.last_tick = now
        active = (self.window.isActiveWindow() and self.window.isVisible()
                  and not self.window.isMinimized() and not QApplication.activeModalWidget()
                  and not QApplication.activePopupWidget()
                  and not getattr(self.window, "shutting_down", False))
        # Ignore suspended/event-loop-blocked intervals instead of counting idle hours.
        playing = self.playback_active() if active else False
        idle_seconds = now - self.last_input
        editing = active and self.has_timeline_content() and (playing or idle_seconds <= IDLE_SECONDS)
        elapsed = seconds if editing and self.was_active and seconds <= 10 else 0
        self.was_active = editing
        try:
            if (self.policy.advance(elapsed) and active and not playing and idle_seconds >= QUIET_SECONDS
                    and seconds <= 10 and QApplication.mouseButtons() == Qt.NoButton):
                self.show_invitation()
        except Exception:
            log.warning("Unable to save feedback invitation state", exc_info=True)
            self.timer.stop()

    def show_invitation(self, checked=False):
        if self.presented or self.completed or (not self.preview and self.policy.shown):
            return
        _ = self.translate
        self.banner = NotificationBanner(
            self.window, _("Help us make OpenShot even better!"), _("Share feedback"),
            self.open_from_banner, self.dismiss, _, icon_name="feedback")
        self.area.add("feedback", self.banner)
        self.presented = True
        self.timer.stop()

    def open_from_banner(self):
        # A click acknowledges the banner even if the browser fails or the survey is abandoned.
        self.dismiss()
        self.open_survey()

    def open_from_menu(self, checked=False):
        # Voluntary feedback remains available after the one-time invitation ends.
        self.open_survey()

    def dismiss(self):
        self.completed = True
        if not self.preview:
            try:
                self.policy.consume()
            except Exception:
                log.warning("Unable to save feedback invitation state", exc_info=True)
        self.timer.stop()
        if self.banner:
            self.area.remove("feedback")
            self.banner = None

    def open_survey(self):
        _ = self.translate
        url = survey_url(get_distribution_info(), self.settings.get("unique_install_id"),
                         info.website_language())
        try:
            opened = QDesktopServices.openUrl(QUrl(url))
        except Exception:
            opened = False
        if not opened:
            QMessageBox.warning(self.window, _("Unable to open browser"),
                                _("Couldn’t open your browser. Please try again."))
            log.warning("Unable to open feedback survey in browser")
        return opened
