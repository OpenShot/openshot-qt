"""
Queue for heavy video tasks (Manim render, ffmpeg, export) so they run
in worker threads/processes without blocking the UI. Callbacks are
invoked on the main thread via Qt signals.
"""

import queue
import threading
from classes.logger import log

try:
    from PyQt5.QtCore import QObject, pyqtSignal
except ImportError:
    QObject = object
    pyqtSignal = None

# Priority levels: lower number = higher priority
PRIORITY_EXPORT = 0
PRIORITY_MANIM = 1
PRIORITY_VOICE = 2
PRIORITY_DEFAULT = 3


class VideoTaskQueue(QObject if QObject is not object else object):
    """
    Serializes heavy tasks (export, Manim render, etc.). One task runs at a time
    in a worker thread. Completion is reported to the main thread via callback.
    """

    if pyqtSignal is not None:
        task_finished = pyqtSignal(str, object, object)  # task_id, result, error

    def __init__(self, parent=None):
        if QObject is not object:
            super().__init__(parent)
        self._queue = queue.PriorityQueue()
        self._worker_thread = None
        self._running = False
        self._lock = threading.Lock()

    def submit(self, task_type, task_id, fn, *args, **kwargs):
        """
        Submit a task to run in the worker. fn(*args, **kwargs) will be called
        in the worker thread; result/exception will be emitted via task_finished
        on the main thread.
        task_type: string e.g. "export", "manim", "voice"
        task_id: optional string id for the finished signal
        """
        priority = kwargs.pop("_priority", PRIORITY_DEFAULT)
        self._queue.put((priority, (task_type, task_id or task_type, fn, args, kwargs)))
        self._ensure_worker()

    def _ensure_worker(self):
        with self._lock:
            if self._worker_thread is not None and self._worker_thread.is_alive():
                return
            self._running = True
            self._worker_thread = threading.Thread(target=self._run_worker, daemon=True)
            self._worker_thread.start()

    def _run_worker(self):
        while self._running:
            try:
                item = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue
            if item is None:
                break
            _, (task_type, task_id, fn, args, kwargs) = item
            try:
                result = fn(*args, **kwargs)
                self._emit_finished(task_id, result, None)
            except Exception as e:
                log.error("Task %s failed: %s", task_id, e, exc_info=True)
                self._emit_finished(task_id, None, e)
        self._running = False

    def _emit_finished(self, task_id, result, error):
        if pyqtSignal is not None and hasattr(self, "task_finished"):
            self.task_finished.emit(task_id, result, error)

    def shutdown(self):
        """Stop the worker after current task (if any)."""
        self._running = False
        self._queue.put(None)
