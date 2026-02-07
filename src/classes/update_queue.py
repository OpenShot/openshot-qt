"""
Queue for agent-originated UpdateActions so they are applied one at a time
on the main thread, keeping the UI responsive. When from_agent is True,
UpdatesRouter sends insert/update/delete/load here instead of directly to
UpdateManager; _process_next dispatches them sequentially via QTimer.
"""

from collections import deque

from classes.logger import log

try:
    from PyQt5.QtCore import QTimer
except ImportError:
    QTimer = None


class UpdateQueue:
    """
    Holds pending UpdateActions and dispatches them one at a time to the
    wrapped UpdateManager, with QTimer.singleShot(0, ...) between each so
    the UI can stay responsive.
    """

    def __init__(self, updates):
        """
        Args:
            updates: The real UpdateManager instance to dispatch to.
        """
        self._updates = updates
        self._pending = deque()
        self._processing = False
        self._from_agent = False

    def set_agent_context(self, value):
        """Set whether the next update calls are from the AI agent (and should be queued)."""
        self._from_agent = value

    @property
    def from_agent(self):
        return self._from_agent

    def enqueue(self, action):
        """Append an UpdateAction to the pending queue and schedule processing."""
        self._pending.append(action)
        self._schedule_process()

    def _schedule_process(self):
        if self._processing or not self._pending:
            return
        if QTimer is not None:
            QTimer.singleShot(0, self._process_next)
        else:
            self._process_next()

    def _process_next(self):
        if self._processing or not self._pending:
            return
        self._processing = True
        try:
            action = self._pending.popleft()
            self._updates.dispatch_action(action)
        except Exception as ex:
            log.error("UpdateQueue._process_next failed: %s", ex, exc_info=True)
        finally:
            self._processing = False
        if self._pending:
            self._schedule_process()


class UpdatesRouter:
    """
    Presents the same interface as UpdateManager. When from_agent is True,
    insert/update/delete/load enqueue to UpdateQueue; otherwise they forward
    to the real UpdateManager. All other attributes (add_listener, undo, etc.)
    delegate to the real manager.
    """

    def __init__(self, real_updates, update_queue):
        self._updates = real_updates
        self._queue = update_queue

    def set_agent_context(self, value):
        self._queue.set_agent_context(value)

    def insert(self, key, values):
        from classes.updates import UpdateAction
        if self._queue.from_agent:
            self._queue.enqueue(UpdateAction("insert", key, values))
            return
        self._updates.insert(key, values)

    def update(self, key, values):
        from classes.updates import UpdateAction
        if self._queue.from_agent:
            self._queue.enqueue(UpdateAction("update", key, values))
            return
        self._updates.update(key, values)

    def delete(self, key):
        from classes.updates import UpdateAction
        if self._queue.from_agent:
            self._queue.enqueue(UpdateAction("delete", key))
            return
        self._updates.delete(key)

    def load(self, values, reset_history=True):
        from classes.updates import UpdateAction
        if self._queue.from_agent:
            self._queue.enqueue(UpdateAction("load", "", values))
            return
        self._updates.load(values, reset_history=reset_history)

    def __getattr__(self, name):
        return getattr(self._updates, name)
