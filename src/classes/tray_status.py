"""
 @file
 @brief Shared system tray status helper for long-running tasks.
 @author OpenShot Studios

 @section LICENSE

 Copyright (c) 2008-2026 OpenShot Studios, LLC
 SPDX-License-Identifier: GPL-3.0-or-later
 """

from qt_api import (
    Qt, QObject, QSystemTrayIcon, QMenu, QAction, QIcon, QPixmap,
    QPainter, QColor, QPen, QBrush,
)

from classes.app import get_app
from classes.logger import log


class TrayStatus(QObject):
    """Small owner for a task-oriented system tray icon."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tray = None
        self._menu = None
        self._mode = ""
        self._progress = 0.0

    def is_available(self):
        try:
            return bool(QSystemTrayIcon.isSystemTrayAvailable())
        except Exception:
            return False

    def show_recording(self, on_stop=None):
        if not self.is_available():
            return
        _ = get_app()._tr
        self._mode = "recording"
        self._ensure_tray()
        self._menu = QMenu()
        stop_action = QAction(_("Stop Recording"), self._menu)
        stop_action.triggered.connect(lambda: on_stop() if on_stop else None)
        self._menu.addAction(stop_action)
        self._tray.setContextMenu(self._menu)
        self._tray.setIcon(self._recording_icon())
        self._tray.setToolTip(_("Recording"))
        self._tray.show()

    def show_export(self, progress=0.0, on_cancel=None):
        if not self.is_available():
            return
        _ = get_app()._tr
        self._mode = "export"
        self._progress = max(0.0, min(1.0, float(progress or 0.0)))
        self._ensure_tray()
        self._menu = QMenu()
        cancel_action = QAction(_("Stop Export"), self._menu)
        cancel_action.triggered.connect(lambda: on_cancel() if on_cancel else None)
        self._menu.addAction(cancel_action)
        self._tray.setContextMenu(self._menu)
        self.update_export_progress(self._progress)
        self._tray.show()

    def update_export_progress(self, progress):
        if not self._tray or self._mode != "export":
            return
        _ = get_app()._tr
        self._progress = max(0.0, min(1.0, float(progress or 0.0)))
        self._tray.setIcon(self._progress_icon(self._progress))
        self._tray.setToolTip(_("Exporting %s%%") % int(round(self._progress * 100.0)))

    def hide(self):
        if self._tray:
            try:
                self._tray.hide()
            except Exception:
                log.debug("Unable to hide tray status icon", exc_info=True)
        self._mode = ""

    def _ensure_tray(self):
        if self._tray:
            return
        self._tray = QSystemTrayIcon(self)

    def _recording_icon(self):
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setBrush(QBrush(QColor(220, 36, 36)))
        painter.setPen(QPen(QColor(255, 255, 255), 4))
        painter.drawEllipse(10, 10, 44, 44)
        painter.end()
        return QIcon(pixmap)

    def _progress_icon(self, progress):
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(QPen(QColor(80, 100, 125), 5))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(10, 10, 44, 44)
        painter.setPen(QPen(QColor(0, 124, 255), 7))
        painter.drawArc(10, 10, 44, 44, 90 * 16, int(-360 * 16 * progress))
        painter.end()
        return QIcon(pixmap)
