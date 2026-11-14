"""One-time feedback invitation using the shared notification banners."""

from qt_api import QAction, QApplication, QDesktopServices, QTimer, QUrl, QObject, QMessageBox

from classes import info
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
        distribution = get_distribution_info()
        self.store_review = (distribution.get("platform") == "windows"
                             and distribution.get("package_type") == "msix"
                             and distribution.get("official") is True)
        self.rating_action = None
        if self.store_review:
            self.rating_action = QAction(_("Leave Rating…"), window)
            self.rating_action.setObjectName("actionLeaveRating")
            window.actionLeaveRating = self.rating_action
            self.rating_action.setIconVisibleInMenu(True)
            self.rating_action.triggered.connect(self.open_rating)
        self.action = QAction(_("Share Feedback…"), window)
        self.action.setObjectName("actionShareFeedback")
        window.actionShareFeedback = self.action
        self.refresh_icon(self.area.theme)
        if hasattr(window, "ThemeChangedSignal"):
            window.ThemeChangedSignal.connect(self.refresh_icon)
        self.action.setIconVisibleInMenu(True)
        self.action.triggered.connect(self.open_from_menu)
        window.menuHelp.insertAction(window.actionUpdate, self.action)
        if self.rating_action:
            window.menuHelp.insertAction(window.actionUpdate, self.rating_action)
        # Only the launch preview polls; real invitations follow a successful export.
        self.timer = QTimer(self)
        self.timer.setInterval(250)
        self.timer.timeout.connect(self.tick)
        if preview:
            self.timer.start()

    def refresh_icon(self, theme=None):
        icon = notification_icon(self.window, "feedback", theme)
        self.action.setIcon(icon)
        if self.rating_action:
            self.rating_action.setIcon(notification_icon(self.window, "rating", theme))

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
        message = (_("Rate your experience with OpenShot.") if self.store_review
                   else _("Tell us about your experience with OpenShot."))
        action = _("Rate && review") if self.store_review else _("Share feedback")
        self.banner = NotificationBanner(
            self.window, message, action,
            self.open_from_banner, self.dismiss, _,
            icon_name="rating" if self.store_review else "feedback")
        self.area.add("feedback", self.banner)
        self.presented = True
        self.timer.stop()

    def open_from_banner(self):
        # A click acknowledges the banner even if launching feedback fails or is abandoned.
        self.dismiss()
        if self.store_review:
            self.open_rating()
        else:
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
        url = survey_url(get_distribution_info(), self.settings.get("unique_install_id"),
                         info.website_language())
        return self.open_url(url)

    def open_rating(self, checked=False):
        if not self.store_review:
            return False
        # Product ID from openshot.org/download/. Qt launches the Store protocol.
        # https://learn.microsoft.com/windows/apps/develop/launch/launch-store-app
        return self.open_url("ms-windows-store://review/?ProductId=9P6R2PMH4C04", store_review=True)

    def open_url(self, url, store_review=False):
        _ = self.translate
        try:
            opened = QDesktopServices.openUrl(QUrl(url))
        except Exception:
            opened = False
        if not opened:
            if store_review:
                QMessageBox.warning(self.window, _("Unable to open Microsoft Store"),
                                    _("Couldn’t open Microsoft Store. Please try again."))
                log.warning("Unable to open Microsoft Store review dialog")
            else:
                QMessageBox.warning(self.window, _("Unable to open browser"),
                                    _("Couldn’t open your browser. Please try again."))
                log.warning("Unable to open feedback survey in browser")
        return opened
