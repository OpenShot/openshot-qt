"""Project-scoped automatic optimization and its one-time suggestion."""

import openshot
from qt_api import QAction, QObject, QPushButton, QTimer, Qt, pyqtSignal, pyqtSlot

from classes.app import get_app
from classes.auto_optimize import source_fingerprint, threshold_ms, valid_measurement
from classes.logger import log
from classes.path_utils import absolute_media_path
from classes.query import File
from windows.notifications import NotificationBanner, notification_area
from windows.views.optimized_preview_menu import optimized_preview_icon


class AutoOptimizeController(QObject):
    thumbnail_measured = pyqtSignal(int, str, object)

    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.app = get_app()
        self.area = notification_area(window)
        self.epoch = 0
        self.attempted = set()
        self.stopped = False
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.evaluate)
        self.thumbnail_measured.connect(self._record_thumbnail, Qt.QueuedConnection)
        _ = self.app._tr
        self.action = QAction(_("Auto-Optimize"), window)
        self.action.setObjectName("actionAutoOptimize")
        self.action.setIcon(optimized_preview_icon())
        self.action.setIconVisibleInMenu(True)
        self.action.setCheckable(True)
        self.action.setChecked(self.mode() == "always")
        self.action.setToolTip(_("Automatically optimize videos with slow thumbnail generation in this project."))
        self.action.triggered.connect(self.choose)
        window.actionAutoOptimize = self.action
        window.menuFile.insertAction(window.actionSaveFrame, self.action)
        self.app.updates.add_listener(self)
        self.timer.start(1500)

    def mode(self):
        choice = self.app.project.get("auto_optimize")
        if isinstance(choice, bool):
            return "always" if choice else "never"
        return self.app.get_settings().get("auto-optimize") or "ask"

    def changed(self, action):
        if action.type == "load":
            for file_id in self.attempted:
                self.window.proxy_service.cancel_job(file_id)
            self.epoch += 1
            self.attempted.clear()
            self.area.remove("auto-optimize")
        if action.type == "load" or (action.key and action.key[0] in ("files", "auto_optimize")):
            self.action.setChecked(self.mode() == "always")
            self.timer.start(1500)

    def choose(self, enabled):
        self.area.remove("auto-optimize")
        self.app.updates.update_untracked(["auto_optimize"], bool(enabled))
        self.action.setChecked(bool(enabled))
        self.timer.start(0)

    def refresh(self):
        """Apply preferences without requiring a project reload."""
        self.area.remove("auto-optimize")
        self.action.setChecked(self.mode() == "always")
        self.timer.start(0)

    def _busy(self):
        player = getattr(getattr(self.window, "preview_thread", None), "player", None)
        return (getattr(self.window, "_project_loading", False)
                or (player is not None and player.Mode() == openshot.PLAYBACK_PLAY))

    @pyqtSlot(int, str, object)
    def _record_thumbnail(self, epoch, file_id, measurement):
        """Persist worker results on the UI thread without adding an undo step."""
        if self.stopped or epoch != self.epoch:
            return
        file = File.get(id=file_id)
        if not file or file.data.get("media_type") != "video" or file.data.get("type") != "FFmpegReader":
            return
        fingerprint = source_fingerprint(absolute_media_path(file.data.get("path")))
        if not valid_measurement(measurement, fingerprint):
            return
        # Keep the first valid observation, avoiding changes from repeated cache refreshes.
        if valid_measurement(file.data.get("thumbnail_performance"), fingerprint):
            return
        self.app.updates.update_untracked(
            ["files", {"id": file_id}], {"thumbnail_performance": measurement})

    def evaluate(self):
        if self.stopped:
            return
        mode = self.mode()
        self.action.setChecked(mode == "always")
        if mode == "never":
            self.area.remove("auto-optimize")
            return
        if self._busy():
            self.timer.start(1500)
            return
        service = self.window.proxy_service
        threshold = threshold_ms(self.app.get_settings().get("auto-optimize-threshold"))
        files = list(File.filter())
        # Existing edits get their timeline sources checked first.
        used = {clip.get("file_id") for clip in (self.app.project.get("clips") or [])}
        files.sort(key=lambda file: file.id not in used)
        qualifying = []
        for file in files:
            if file.id in self.attempted or service.get_active_job_for_file(file.id):
                continue
            if service.has_proxy_reader(file) and not service.has_missing_proxy(file):
                continue
            if file.data.get("media_type") != "video" or file.data.get("type") != "FFmpegReader":
                continue
            measurement = file.data.get("thumbnail_performance")
            fingerprint = source_fingerprint(absolute_media_path(file.data.get("path")))
            if valid_measurement(measurement, fingerprint) and measurement["frame_ms"] > threshold:
                qualifying.append(file)
        if qualifying:
            if mode == "always":
                self.area.remove("auto-optimize")
                self.attempted.update(file.id for file in qualifying)
                try:
                    service.create_for_files(qualifying)
                except Exception:
                    log.warning("Unable to start automatic optimization", exc_info=True)
                    self.window.statusBar().showMessage(
                        self.app._tr("Could not start optimization. Retry from the Optimize menu."), 5000)
            elif "auto-optimize" not in self.area.banners:
                self._offer()
        else:
            self.area.remove("auto-optimize")

    def _offer(self):
        _ = self.app._tr
        banner = NotificationBanner(
            self.window,
            _("Optimize videos for smoother playback? Originals and export quality stay unchanged."),
            _("Optimize Automatically"), lambda: self.choose(True), lambda: self.choose(False), _,
            icon_name="tool-optimize-preview",
        )
        later = QPushButton(_("Not Now"), banner)
        later.clicked.connect(lambda: self.choose(False))
        banner.layout().insertWidget(banner.layout().count() - 1, later)
        banner.close_button.setToolTip(_("Do not suggest optimization again for this project."))
        self.area.add("auto-optimize", banner)

    def shutdown(self):
        self.stopped = True
        self.timer.stop()
