"""
 @file
 @brief Lightweight thumbnail request manager for the QWidget timeline backend.
 @author Jonathan Thomas <jonathan@openshot.org>

 @section LICENSE

 Copyright (c) 2008-2025 OpenShot Studios, LLC
 (http://www.openshotstudios.com). This file is part of
 OpenShot Video Editor (http://www.openshot.org), an open-source project
 dedicated to delivering high quality video editing and animation solutions
 to the world.

 OpenShot Video Editor is free software: you can redistribute it and/or modify
 it under the terms of the GNU General Public License as published by
 the Free Software Foundation, either version 3 of the License, or
 (at your option) any later version.

 OpenShot Video Editor is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 GNU General Public License for more details.

 You should have received a copy of the GNU General Public License
 along with OpenShot Library.  If not, see <http://www.gnu.org/licenses/>.
 """

from collections import deque

from qt_api import QObject, QThread, QTimer, pyqtSignal, pyqtSlot

from classes.logger import log
from classes.thumbnail import GetThumbPath


class _ThumbnailWorker(QObject):
    """Worker object that resolves thumbnail paths on a background thread."""

    thumbnail_ready = pyqtSignal(str, int, str, int)

    def __init__(self):
        super().__init__()
        self._queue = deque()
        self._processing = False
        self._scheduled = False

    @pyqtSlot(str, str, int, int)
    def request_thumbnail(self, clip_id, file_id, frame, generation):
        """Queue a thumbnail request."""
        self._queue.append((str(clip_id or ""), str(file_id or ""), int(frame or 0), int(generation or 0)))
        self._queue = deque(sorted(self._queue, key=lambda job: (job[2], job[0], job[3])))
        if not self._processing and not self._scheduled:
            self._scheduled = True
            QTimer.singleShot(0, self._process_next)

    @pyqtSlot()
    def clear_pending(self):
        """Discard any pending thumbnail work."""
        self._queue.clear()
        # Keep any already scheduled callback: it will see the updated queue.

    def _process_next(self):
        if self._processing:
            return
        self._scheduled = False
        if not self._queue:
            return
        clip_id, file_id, frame, generation = self._queue.popleft()
        self._processing = True
        path = ""
        try:
            if clip_id and file_id and frame > 0:
                path = GetThumbPath(file_id, frame)
        except Exception:
            log.warning(
                "Thumbnail request failed for file_id=%s frame=%s",
                file_id,
                frame,
                exc_info=1,
            )
        finally:
            self._processing = False
        self.thumbnail_ready.emit(clip_id, frame, path or "", generation)
        # Yield after every decode so queued cancellations and new viewport
        # requests can run before we start another (potentially slow) decode.
        if self._queue and not self._scheduled:
            self._scheduled = True
            QTimer.singleShot(0, self._process_next)


class TimelineThumbnailManager(QObject):
    """Qt helper that forwards thumbnail requests to a worker thread."""

    thumbnail_ready = pyqtSignal(str, int, str, int)
    _request_job = pyqtSignal(str, str, int, int)
    _clear_jobs = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._thread = QThread(self)
        self._thread.setObjectName("timeline_thumbnail")
        self._worker = _ThumbnailWorker()
        self._worker.moveToThread(self._thread)
        self._request_job.connect(self._worker.request_thumbnail)
        self._clear_jobs.connect(self._worker.clear_pending)
        self._worker.thumbnail_ready.connect(self.thumbnail_ready)
        self._thread.start()

    def request_thumbnail(self, clip_id, file_id, frame, generation):
        """Queue a thumbnail request."""
        clip_id = str(clip_id or "")
        file_id = str(file_id or "")
        frame = int(frame or 0)
        generation = int(generation or 0)
        self._request_job.emit(clip_id, file_id, frame, generation)

    def clear_pending(self):
        """Drop any pending requests."""
        self._clear_jobs.emit()

    def shutdown(self):
        """Stop the worker thread."""
        if self._thread is None:
            return
        self._clear_jobs.emit()
        was_running = self._thread.isRunning()
        if was_running:
            self._thread.quit()
            stopped = self._thread.wait(2000)
            log.info(
                "Timeline thumbnail thread stop result running_before=%s running_after=%s",
                was_running,
                self._thread.isRunning(),
            )
            if not stopped:
                log.warning("Timeline thumbnail thread did not stop within 2 seconds")
        self._worker.deleteLater()
        self._thread.deleteLater()
        self._thread = None
