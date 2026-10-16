"""Project-scoped automatic optimization and its one-time suggestion."""

import os
import tempfile
from concurrent.futures import ThreadPoolExecutor

import openshot
from qt_api import QAction, QObject, QPushButton, QTimer, Qt, pyqtSignal, pyqtSlot

from classes.app import get_app
from classes.auto_optimize import (MEASUREMENT_VERSION, machine_id, source_fingerprint,
                                   threshold_ms, valid_measurement)
from classes import info
from classes.thumbnail import GenerateThumbnail
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
        self.measured = set()
        self.measurement_future = None
        self.measurement_executor = None
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
            self.measured.clear()
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
        missing = []
        for file in files:
            if file.id in self.attempted or service.get_active_job_for_file(file.id):
                continue
            if service.has_proxy_reader(file) and not service.has_missing_proxy(file):
                continue
            if file.data.get("media_type") != "video" or file.data.get("type") != "FFmpegReader":
                continue
            measurement = file.data.get("thumbnail_performance")
            fingerprint = source_fingerprint(absolute_media_path(file.data.get("path")))
            if valid_measurement(measurement, fingerprint):
                if measurement["frame_ms"] > threshold:
                    qualifying.append(file)
            elif fingerprint is not None and file.id not in self.measured:
                missing.append((file.id, absolute_media_path(file.data.get("path")), fingerprint))
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

        # Schedule only one small thumbnail at a time. Stop looking once Ask has
        # an answer to offer; accepting resumes checks for the remaining files.
        if missing and not (mode == "ask" and qualifying):
            if self.measurement_future is None or self.measurement_future.done():
                file_id, path, fingerprint = missing[0]
                self.measured.add(file_id)
                if self.measurement_executor is None:
                    self.measurement_executor = ThreadPoolExecutor(
                        max_workers=1, thread_name_prefix="thumbnail-timing")
                self.measurement_future = self.measurement_executor.submit(
                    self._measure_thumbnail, self.epoch, file_id, path, fingerprint)
            self.timer.start(1500)

    def _measure_thumbnail(self, epoch, file_id, path, fingerprint):
        # Use a temporary thumbnail so switching projects cannot write into the
        # next project's cache. This uses the normal thumbnail decoder and size.
        try:
            with tempfile.TemporaryDirectory(prefix="openshot-thumbnail-timing-") as root:
                sample = GenerateThumbnail(
                    path, os.path.join(root, "thumbnail.png"), 1,
                    info.LIST_ICON_SIZE.width(), info.LIST_ICON_SIZE.height(),
                    os.path.join(info.IMAGES_PATH, "mask.png"), "")
            if isinstance(sample, dict) and not self.stopped:
                sample.update(version=MEASUREMENT_VERSION, machine=machine_id(), source=fingerprint)
                self.thumbnail_measured.emit(epoch, file_id, sample)
        except Exception:
            log.warning("Unable to measure thumbnail for %s", path, exc_info=True)

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
        if self.measurement_executor is not None:
            self.measurement_executor.shutdown(wait=True)
