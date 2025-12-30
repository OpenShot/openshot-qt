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

from PyQt5.QtCore import QObject, QThread, pyqtSignal, pyqtSlot

from classes.logger import log
from classes.thumbnail import GetThumbPath


class _ThumbnailWorker(QObject):
    """Worker object that resolves thumbnail paths on a background thread."""

    thumbnail_ready = pyqtSignal(str, int, str, int)

    def __init__(self):
        super().__init__()
        self._queue = deque()
        self._processing = False

    @pyqtSlot(str, str, int, int)
    def request_thumbnail(self, clip_id, file_id, frame, generation):
        """Queue a thumbnail request."""
        self._queue.append((clip_id, file_id, frame, generation))
        if not self._processing:
            self._process_next()

    @pyqtSlot()
    def clear_pending(self):
        """Discard any pending thumbnail work."""
        self._queue.clear()
        self._processing = False

    def _process_next(self):
        while self._queue:
            clip_id, file_id, frame, generation = self._queue.popleft()
            self._processing = True
            path = ""
            if clip_id and file_id and frame > 0:
                try:
                    path = GetThumbPath(file_id, frame)
                except Exception:
                    log.warning(
                        "Thumbnail request failed for file_id=%s frame=%s",
                        file_id,
                        frame,
                        exc_info=1,
                    )
            self.thumbnail_ready.emit(clip_id, frame, path or "", generation)
        self._processing = False


class TimelineThumbnailManager(QObject):
    """Qt helper that forwards thumbnail requests to a worker thread."""

    thumbnail_ready = pyqtSignal(str, int, str, int)
    _request_job = pyqtSignal(str, str, int, int)
    _clear_jobs = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._thread = QThread(self)
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
        self._clear_jobs.emit()
        if self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(2000)
