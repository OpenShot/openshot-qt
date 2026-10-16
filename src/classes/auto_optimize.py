"""Machine-local thumbnail measurements used by automatic optimization."""

import hashlib
import math
import os
import platform
from functools import lru_cache

MEASUREMENT_VERSION = 1
DEFAULT_THRESHOLD_MS = 200


@lru_cache(maxsize=1)
def machine_id():
    """Identify this computer without saving its hostname in a shared project."""
    identity = "|".join((platform.node(), platform.system(), platform.machine(), platform.processor()))
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]


def source_fingerprint(path):
    try:
        stat = os.stat(path)
        return {"size": stat.st_size, "mtime_ns": stat.st_mtime_ns}
    except (OSError, TypeError, ValueError):
        return None


def threshold_ms(value):
    try:
        value = float(value)
        if math.isfinite(value) and value > 0:
            return value
    except (TypeError, ValueError, OverflowError):
        pass
    return DEFAULT_THRESHOLD_MS


def valid_measurement(measurement, fingerprint):
    """Reject foreign, obsolete, changed-source, and invalid measurements."""
    if not isinstance(measurement, dict) or fingerprint is None:
        return False
    elapsed = measurement.get("frame_ms")
    return (measurement.get("version") == MEASUREMENT_VERSION
            and measurement.get("machine") == machine_id()
            and measurement.get("source") == fingerprint
            and measurement.get("frame") == 1
            and isinstance(elapsed, (int, float)) and not isinstance(elapsed, bool)
            and math.isfinite(elapsed) and elapsed >= 0)
