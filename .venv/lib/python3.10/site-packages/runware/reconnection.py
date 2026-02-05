# runware/reconnection.py
import time
import random
import logging
from enum import Enum
from typing import Optional
from dataclasses import dataclass


class ConnectionState(Enum):
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    CIRCUIT_OPEN = "circuit_open"


@dataclass
class ReconnectionConfig:
    initial_backoff: float = 1.0
    max_backoff: float = 60.0
    backoff_multiplier: float = 2.0
    jitter_factor: float = 0.3
    auth_error_window: float = 30.0
    max_auth_errors_per_window: int = 5
    circuit_probe_interval: float = 120.0


class ReconnectionManager:
    def __init__(
            self,
            config: Optional[ReconnectionConfig] = None,
            logger: Optional[logging.Logger] = None,
    ):
        self._config = config or ReconnectionConfig()
        self._logger = logger or logging.getLogger(__name__)

        self._state: ConnectionState = ConnectionState.CONNECTED
        self._backoff_delay: float = self._config.initial_backoff

        self._had_successful_auth: bool = False
        self._auth_error_window_start: Optional[float] = None
        self._auth_errors_in_window: int = 0

    def calculate_delay(self) -> float:
        if self._state == ConnectionState.CIRCUIT_OPEN:
            return self._config.circuit_probe_interval

        base_delay = min(self._backoff_delay, self._config.max_backoff)
        jitter_range = base_delay * self._config.jitter_factor
        jitter = random.uniform(-jitter_range, jitter_range)
        delay = max(0.1, base_delay + jitter)

        self._backoff_delay = min(
            self._backoff_delay * self._config.backoff_multiplier,
            self._config.max_backoff
        )

        return delay

    def on_connection_success(self):
        self._logger.info(f"Connection successful (was {self._state.value})")
        self._state = ConnectionState.CONNECTED
        self._backoff_delay = self._config.initial_backoff
        self._had_successful_auth = True
        self._auth_error_window_start = None
        self._auth_errors_in_window = 0

    def on_auth_failure(self) -> bool:
        now = time.time()

        if self._auth_error_window_start is None:
            self._auth_error_window_start = now
            self._auth_errors_in_window = 1
        else:
            window_elapsed = now - self._auth_error_window_start
            if window_elapsed > self._config.auth_error_window:
                self._auth_error_window_start = now
                self._auth_errors_in_window = 1
            else:
                self._auth_errors_in_window += 1

        if self._auth_errors_in_window >= self._config.max_auth_errors_per_window:
            window_elapsed = now - self._auth_error_window_start
            if window_elapsed < self._config.auth_error_window:
                self._logger.error(
                    f"Too many auth failures ({self._auth_errors_in_window}) "
                    f"in short time ({window_elapsed:.1f}s), opening circuit"
                )
                self._state = ConnectionState.CIRCUIT_OPEN
                return True

        if self._state == ConnectionState.CONNECTED:
            self._state = ConnectionState.RECONNECTING

        return False

    def on_connection_failure(self):
        if self._state == ConnectionState.CONNECTED:
            self._state = ConnectionState.RECONNECTING

    def get_state(self) -> ConnectionState:
        return self._state