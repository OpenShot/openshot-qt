import os
import time
from threading import Thread, Lock

import sentry_sdk
from sentry_sdk.utils import logger

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Optional


MAX_DOWNSAMPLE_FACTOR = 10


class Monitor:
    """
    Performs health checks in a separate thread once every interval seconds
    and updates the internal state. Other parts of the SDK only read this state
    and act accordingly.
    """

    name = "sentry.monitor"

    def __init__(
        self, transport: "sentry_sdk.transport.Transport", interval: float = 10
    ) -> None:
        self.transport: "sentry_sdk.transport.Transport" = transport
        self.interval: float = interval

        self._healthy = True
        self._downsample_factor: int = 0

        self._thread: "Optional[Thread]" = None
        self._thread_lock = Lock()
        self._thread_for_pid: "Optional[int]" = None
        self._running = True

    def _ensure_running(self) -> None:
        """
        Check that the monitor has an active thread to run in, or create one if not.

        Note that this might fail (e.g. in Python 3.12 it's not possible to
        spawn new threads at interpreter shutdown). In that case self._running
        will be False after running this function.
        """
        if self._thread_for_pid == os.getpid() and self._thread is not None:
            return None

        with self._thread_lock:
            if self._thread_for_pid == os.getpid() and self._thread is not None:
                return None

            def _thread() -> None:
                while self._running:
                    time.sleep(self.interval)
                    if self._running:
                        self.run()

            thread = Thread(name=self.name, target=_thread)
            thread.daemon = True
            try:
                thread.start()
            except RuntimeError:
                # Unfortunately at this point the interpreter is in a state that no
                # longer allows us to spawn a thread and we have to bail.
                self._running = False
                return None

            self._thread = thread
            self._thread_for_pid = os.getpid()

        return None

    def run(self) -> None:
        self.check_health()
        self.set_downsample_factor()

    def set_downsample_factor(self) -> None:
        if self._healthy:
            if self._downsample_factor > 0:
                logger.debug(
                    "[Monitor] health check positive, reverting to normal sampling"
                )
            self._downsample_factor = 0
        else:
            if self.downsample_factor < MAX_DOWNSAMPLE_FACTOR:
                self._downsample_factor += 1
            logger.debug(
                "[Monitor] health check negative, downsampling with a factor of %d",
                self._downsample_factor,
            )

    def check_health(self) -> None:
        """
        Perform the actual health checks,
        currently only checks if the transport is rate-limited.
        TODO: augment in the future with more checks.
        """
        self._healthy = self.transport.is_healthy()

    def is_healthy(self) -> bool:
        self._ensure_running()
        return self._healthy

    @property
    def downsample_factor(self) -> int:
        self._ensure_running()
        return self._downsample_factor

    def kill(self) -> None:
        self._running = False
