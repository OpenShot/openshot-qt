"""One-time feedback invitation using the shared notification banners."""

from qt_api import QAction, QApplication, QDesktopServices, QTimer, QUrl, QObject, QMessageBox

from classes import info
from classes.app import get_app
from classes.distribution import get_distribution_info
from classes.feedback import FeedbackPolicy, survey_url
from classes.logger import log
from windows.notifications import NotificationBanner, notification_area, notification_icon


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
        # Only the launch preview polls; real invitations follow a successful export.
        self.timer = QTimer(self)
        self.timer.setInterval(250)
        self.timer.timeout.connect(self.tick)
        if preview:
            self.timer.start()

    def refresh_icon(self, theme=None):
        self.action.setIcon(notification_icon(self.window, "feedback", theme))

    def record_export(self):
        """Queue the invitation behind the export dialog, so closing it reveals the banner."""
        if not self.preview:
            self.show_invitation()

    def shutdown(self):
        self.timer.stop()

    def tick(self):
        if self.window.isVisible() and not QApplication.activeModalWidget():
            self.show_invitation()

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
