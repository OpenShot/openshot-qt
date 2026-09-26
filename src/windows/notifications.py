"""Shared, dismissible notification banners below the main toolbar."""

import os

from qt_api import (
    QObject, Qt, QEvent, QFrame, QHBoxLayout, QLabel, QPushButton, QToolBar,
    QVBoxLayout, QWidget, QSizePolicy, QPalette, QTimer, QIcon, QMessageBox, QPainter, QColor,
)

from classes.notifications import release_version, should_notify_update
from classes.logger import log
from classes import info


def notification_icon(window, name, theme=None):
    """Matching outline menu icons with each theme's foreground color."""
    theme_name = getattr(theme, "name", "")
    if not theme_name:
        background = window.palette().color(QPalette.Window)
        theme_name = "Retro" if background.lightness() >= 128 else "Cosmic Dusk"
    path = {
        "Cosmic Dusk": "cosmic/images/{}.svg",
        "Humanity: Dark": "humanity/images/{}-dark.svg",
        "Retro": "humanity/images/{}-retro.svg",
    }.get(theme_name, "cosmic/images/{}.svg").format(name)
    return QIcon(os.path.join(info.PATH, "themes", path))


def banner_colors(window, theme=None, kind="update"):
    """Theme colors with a distinct, welcoming treatment for feedback."""
    name = getattr(theme, "name", "")
    background = window.palette().color(QPalette.Window)
    if name == "Retro" or (not name and background.lightness() >= 128):
        if kind == "feedback":
            return dict(backdrop="#ededed", surface="#eef8f5", border="#a4d4c8",
                        text="#17665a", action="#155da6", close="#536579", hover="#d9f0e9")
        return dict(backdrop="#ededed", surface="#eef5fc", border="#b2c9e0", text="#155da6",
                    action="#155da6", close="#536579", hover="#dcebf9")
    if name == "Cosmic Dusk" or (not name and background.blue() > background.red() + 10):
        if kind == "feedback":
            return dict(backdrop="#192332", surface="#172d32", border="#386761",
                        text="#8cdbca", action="#a5d8f8", close="#a9bdc5", hover="#204149")
        return dict(backdrop="#192332", surface="#17283a", border="#365574", text="#a7d0ff",
                    action="#a7d0ff", close="#aebdcc", hover="#223d58")
    if kind == "feedback":
        return dict(backdrop="#303030", surface="#253632", border="#477669",
                    text="#9cdec7", action="#afd8ff", close="#b9c6c3", hover="#304b42")
    return dict(backdrop="#303030", surface="#26323f", border="#48637e", text="#acd3ff",
                action="#acd3ff", close="#bdc9d5", hover="#34475c")


class NotificationBanner(QFrame):
    def __init__(self, parent, message, action_text, on_action, on_dismiss, translate, icon_name="update"):
        super().__init__(parent)
        _ = translate
        self.setObjectName("notificationBanner")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setAttribute(Qt.WA_Hover, True)
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.setAccessibleName(message)
        self._action = on_action
        self._dismiss = on_dismiss
        self.icon_name = icon_name
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 4, 8, 4)
        layout.setSpacing(10)
        self.symbol = QLabel(self)
        self.symbol.setObjectName("notificationSymbol")
        self.symbol.setAlignment(Qt.AlignCenter)
        self.symbol.setFixedSize(20, 20)
        self.symbol.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        layout.addWidget(self.symbol)
        self.message = QLabel(message, self)
        self.message.setObjectName("notificationMessage")
        self.message.setWordWrap(True)
        self.message.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        layout.addWidget(self.message, 1)
        self.primary = QPushButton(action_text, self)
        self.primary.setObjectName("notificationAction")
        self.primary.setCursor(Qt.PointingHandCursor)
        self.primary.clicked.connect(on_action)
        layout.addWidget(self.primary)
        self.close_button = QPushButton("×", self)
        self.close_button.setObjectName("notificationClose")
        self.close_button.setCursor(Qt.PointingHandCursor)
        self.close_button.setAccessibleName(_("Dismiss notification"))
        self.close_button.setToolTip(_("Dismiss notification"))
        self.close_button.setFixedWidth(28)
        self.close_button.clicked.connect(on_dismiss)
        layout.addWidget(self.close_button)

    def apply_colors(self, colors, theme=None):
        # Reuse the menu artwork, preserving its alpha while matching banner text.
        # QIcon handles the display scale; request the label's logical size.
        pixmap = notification_icon(self, self.icon_name, theme).pixmap(self.symbol.size())
        painter = QPainter(pixmap)
        painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
        painter.fillRect(pixmap.rect(), QColor(colors["text"]))
        painter.end()
        self.symbol.setPixmap(pixmap)
        self.setStyleSheet("""
            QFrame#notificationBanner {
                background: %(surface)s; border: 1px solid %(border)s; border-radius: 6px;
            }
            QFrame#notificationBanner:hover { background: %(hover)s; }
            QFrame#notificationBanner QLabel {
                background: transparent; color: %(text)s; border: none; font-weight: 600;
            }
            QFrame#notificationBanner QPushButton {
                background: transparent; color: %(action)s; border: none;
                border-radius: 4px; padding: 4px 8px; font-weight: 600;
            }
            QFrame#notificationBanner QPushButton#notificationClose { color: %(close)s; padding: 4px; }
            QFrame#notificationBanner QPushButton:hover,
            QFrame#notificationBanner QPushButton:focus { background: %(hover)s; text-decoration: underline; }
        """ % colors)

    def show_error(self, message):
        self.message.setText(message)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.rect().contains(event.pos()):
            self._action()
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self._dismiss()
            event.accept()
        else:
            super().keyPressEvent(event)


class NotificationArea(QObject):
    """One shared row of stacked banners; collapses when the last one is removed."""

    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.toolbar = None
        self.banners = {}
        self.theme = None
        self.sync_timer = QTimer(self)
        self.sync_timer.setSingleShot(True)
        self.sync_timer.timeout.connect(self.sync_visibility)
        if hasattr(window, "ThemeChangedSignal"):
            window.ThemeChangedSignal.connect(self.apply_theme)

    def _create_toolbar(self):
        if self.toolbar:
            return
        self.toolbar = QToolBar(self.window)
        self.toolbar.setObjectName("notificationToolbar")
        self.toolbar.setMovable(False)
        self.toolbar.setFloatable(False)
        self.toolbar.setAllowedAreas(Qt.TopToolBarArea)
        self.toolbar.toggleViewAction().setVisible(False)
        self.toolbar.setStyleSheet("QToolBar { background: transparent; border: none; padding: 0; spacing: 0; }")
        self.container = QWidget(self.toolbar)
        self.container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.container.setObjectName("notificationContainer")
        self.layout = QVBoxLayout(self.container)
        self.layout.setContentsMargins(12, 8, 12, 6)
        self.layout.setSpacing(6)
        self.toolbar.addWidget(self.container)
        self.window.addToolBarBreak(Qt.TopToolBarArea)
        self.window.addToolBar(Qt.TopToolBarArea, self.toolbar)
        self.toolbar.installEventFilter(self)

    def add(self, key, banner):
        self._create_toolbar()
        self.remove(key)
        self.banners[key] = banner
        # Feedback stays above updates, independent of asynchronous response order.
        self.layout.insertWidget(0 if key == "feedback" else self.layout.count(), banner)
        self.apply_theme(self.theme)
        banner.show()
        self.toolbar.show()

    def remove(self, key):
        banner = self.banners.pop(key, None)
        if banner:
            self.layout.removeWidget(banner)
            banner.hide()
            banner.deleteLater()
        if self.toolbar and not self.banners:
            self.toolbar.hide()

    def apply_theme(self, theme=None):
        self.theme = theme
        colors = banner_colors(self.window, theme)
        if self.toolbar:
            self.toolbar.setStyleSheet(
                "QToolBar { background: %s; border: none; padding: 0; spacing: 0; }" % colors["backdrop"])
            self.container.setStyleSheet(
                "QWidget#notificationContainer { background: %s; }" % colors["backdrop"])
        for banner in self.banners.values():
            banner.apply_colors(banner_colors(self.window, theme, banner.icon_name), theme)

    def sync_visibility(self):
        if self.toolbar:
            # restoreState() can merge a newly introduced toolbar into the main row.
            # Notices must retain their own full-width row after workspace changes.
            if not self.window.toolBarBreak(self.toolbar):
                self.window.insertToolBarBreak(self.toolbar)
            self.toolbar.setVisible(bool(self.banners))

    def eventFilter(self, watched, event):
        # Saved workspace layouts must not resurrect a dismissed notification row.
        if watched is self.toolbar and event.type() in (
                QEvent.Show, QEvent.Hide, QEvent.Move, QEvent.Resize):
            self.sync_timer.start(0)
        return super().eventFilter(watched, event)


def notification_area(window):
    if not hasattr(window, "notification_area"):
        window.notification_area = NotificationArea(window)
    return window.notification_area


class UpdateNotificationController(QObject):
    def __init__(self, window, settings, translate, current_version, open_download, preview=False):
        super().__init__(window)
        self.window = window
        self.settings = settings
        self.translate = translate
        self.current_version = current_version
        self.open_download = open_download
        self.preview = preview
        self.area = notification_area(window)
        self.version = None
        self.dismissed = set()
        self.banner = None
        self.refresh_icon(self.area.theme)
        if hasattr(window, "ThemeChangedSignal"):
            window.ThemeChangedSignal.connect(self.refresh_icon)

    def refresh_icon(self, theme=None):
        self.window.actionUpdate.setIcon(notification_icon(self.window, "update", theme))
        self.window.actionUpdate.setIconVisibleInMenu(True)

    def offer(self, version):
        _ = self.translate
        if self.preview:
            version = self.current_version
        elif not should_notify_update(version, self.current_version, ""):
            return
        version_key = release_version(version)
        if self.version and version_key < release_version(self.version):
            return
        previous_version = self.version
        self.version = version
        # Keep the explicit Help action available even when its banner was dismissed.
        if hasattr(self.window, "actionUpdate"):
            self.window.actionUpdate.setVisible(True)
            self.window.actionUpdate.setText(_("Update Available"))
            self.window.actionUpdate.setToolTip(_("Update Available: %s") % version)
        if (version_key in self.dismissed or (not self.preview and not should_notify_update(
                version, self.current_version, self.settings.get("dismissed-update-version")))):
            self.area.remove("update")
            self.banner = None
            return
        if self.banner and version_key == release_version(previous_version):
            return
        self.banner = NotificationBanner(
            self.window, _("Upgrade to the latest version of OpenShot."), _("Upgrade"),
            self.activate, self.dismiss, _)
        self.banner.setToolTip(_("Update Available: %s") % (_("Preview") if self.preview else version))
        self.area.add("update", self.banner)

    def dismiss(self):
        if not self.version:
            return
        version_key = release_version(self.version)
        self.dismissed.add(version_key)
        previous = release_version(self.settings.get("dismissed-update-version"))
        if not self.preview and (previous is None or version_key > previous):
            self.settings.set("dismissed-update-version", self.version)
            try:
                self.settings.save()
            except Exception:
                log.warning("Unable to save dismissed update version", exc_info=True)
        self.area.remove("update")
        self.banner = None

    def activate(self):
        _ = self.translate
        try:
            opened = self.open_download()
        except Exception:
            opened = False
            log.warning("Unable to open update download page", exc_info=True)
        if opened:
            self.dismiss()
        elif self.banner:
            self.banner.show_error(_("Couldn’t open your browser. Please try again."))
        else:
            QMessageBox.warning(self.window, _("Unable to open browser"),
                                _("Couldn’t open your browser. Please try again."))
        return opened
