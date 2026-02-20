import os
import random
import threading
from datetime import datetime, timezone
from typing import TYPE_CHECKING, TypeVar, Generic

from sentry_sdk.utils import format_timestamp, safe_repr, serialize_attribute
from sentry_sdk.envelope import Envelope, Item, PayloadRef

if TYPE_CHECKING:
    from typing import Optional, Callable, Any

T = TypeVar("T")


class Batcher(Generic[T]):
    MAX_BEFORE_FLUSH = 100
    MAX_BEFORE_DROP = 1_000
    FLUSH_WAIT_TIME = 5.0

    TYPE = ""
    CONTENT_TYPE = ""

    def __init__(
        self,
        capture_func: "Callable[[Envelope], None]",
        record_lost_func: "Callable[..., None]",
    ) -> None:
        self._buffer: "list[T]" = []
        self._capture_func = capture_func
        self._record_lost_func = record_lost_func
        self._running = True
        self._lock = threading.Lock()

        self._flush_event: "threading.Event" = threading.Event()

        self._flusher: "Optional[threading.Thread]" = None
        self._flusher_pid: "Optional[int]" = None

    def _ensure_thread(self) -> bool:
        """For forking processes we might need to restart this thread.
        This ensures that our process actually has that thread running.
        """
        if not self._running:
            return False

        pid = os.getpid()
        if self._flusher_pid == pid:
            return True

        with self._lock:
            # Recheck to make sure another thread didn't get here and start the
            # the flusher in the meantime
            if self._flusher_pid == pid:
                return True

            self._flusher_pid = pid

            self._flusher = threading.Thread(target=self._flush_loop)
            self._flusher.daemon = True

            try:
                self._flusher.start()
            except RuntimeError:
                # Unfortunately at this point the interpreter is in a state that no
                # longer allows us to spawn a thread and we have to bail.
                self._running = False
                return False

        return True

    def _flush_loop(self) -> None:
        while self._running:
            self._flush_event.wait(self.FLUSH_WAIT_TIME + random.random())
            self._flush_event.clear()
            self._flush()

    def add(self, item: "T") -> None:
        if not self._ensure_thread() or self._flusher is None:
            return None

        with self._lock:
            if len(self._buffer) >= self.MAX_BEFORE_DROP:
                self._record_lost(item)
                return None

            self._buffer.append(item)
            if len(self._buffer) >= self.MAX_BEFORE_FLUSH:
                self._flush_event.set()

    def kill(self) -> None:
        if self._flusher is None:
            return

        self._running = False
        self._flush_event.set()
        self._flusher = None

    def flush(self) -> None:
        self._flush()

    def _add_to_envelope(self, envelope: "Envelope") -> None:
        envelope.add_item(
            Item(
                type=self.TYPE,
                content_type=self.CONTENT_TYPE,
                headers={
                    "item_count": len(self._buffer),
                },
                payload=PayloadRef(
                    json={
                        "items": [
                            self._to_transport_format(item) for item in self._buffer
                        ]
                    }
                ),
            )
        )

    def _flush(self) -> "Optional[Envelope]":
        envelope = Envelope(
            headers={"sent_at": format_timestamp(datetime.now(timezone.utc))}
        )
        with self._lock:
            if len(self._buffer) == 0:
                return None

            self._add_to_envelope(envelope)
            self._buffer.clear()

        self._capture_func(envelope)
        return envelope

    def _record_lost(self, item: "T") -> None:
        pass

    @staticmethod
    def _to_transport_format(item: "T") -> "Any":
        pass
