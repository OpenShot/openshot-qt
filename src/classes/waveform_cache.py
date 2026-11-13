"""Content-addressed waveform envelopes, outside project and undo JSON.

Samples are little-endian float32 compressed with zlib. References are portable
between projects; the project assets directory holds every referenced envelope,
including those retained by undo history. The user cache serves unsaved projects.
"""
from array import array
from collections import OrderedDict
import hashlib
import os
import re
import sys
import tempfile
import threading
import zlib

_REF = "waveform_cache"
_KEYS = ("audio_data", "audio_data_rms")
_lock = threading.RLock()
_buffers = OrderedDict()
_buffer_bytes = 0
_MAX_MEMORY = 64 * 1024 * 1024


def cache_directory():
    from classes import info
    return os.path.join(info.USER_PATH, "waveforms")


def is_reference(value):
    return (isinstance(value, dict)
            and isinstance(value.get(_REF), str)
            and re.fullmatch(r"[0-9a-f]{64}", value[_REF]) is not None
            and type(value.get("count")) is int
            and 0 < value["count"] <= 100_000_000)


def sample_count(value):
    if is_reference(value):
        return value["count"]
    return len(value) if isinstance(value, (list, tuple, array, memoryview)) else 0


def _remember(key, data):
    global _buffer_bytes
    with _lock:
        old = _buffers.pop(key, None)
        if old is not None:
            _buffer_bytes -= len(old) * 4
        # Large individual envelopes may be used by the caller, but must not
        # permanently bypass the retained-buffer budget.
        if len(data) * 4 > _MAX_MEMORY:
            return data
        _buffers[key] = data
        _buffer_bytes += len(data) * 4
        while _buffer_bytes > _MAX_MEMORY:
            _, old = _buffers.popitem(last=False)
            _buffer_bytes -= len(old) * 4
    return data


def _atomic_write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, "wb") as output:
            output.write(data)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def store_samples(values):
    """Return a small JSON reference, sharing identical buffers by digest."""
    if is_reference(values) or not sample_count(values):
        return values
    packed = array("f", values)
    if sys.byteorder != "little":
        packed.byteswap()
    raw = packed.tobytes()
    key = hashlib.sha256(raw).hexdigest()
    path = os.path.join(cache_directory(), key + ".wfc")
    if not os.path.isfile(path) or not samples({_REF: key, "count": len(packed)}):
        _atomic_write(path, zlib.compress(raw, 1))
    # Expose immutable buffers so renderers cannot contaminate shared samples.
    if sys.byteorder != "little":
        packed.byteswap()
    _remember(key, memoryview(packed.tobytes()).cast("f"))
    return {_REF: key, "count": len(packed)}


def samples(value):
    """Resolve a reference on demand; missing/corrupt caches are regenerable."""
    if not is_reference(value):
        return value if isinstance(value, (list, tuple, array, memoryview)) else ()
    key = value[_REF]
    with _lock:
        cached = _buffers.get(key)
        if cached is not None and len(cached) == value["count"]:
            _buffers.move_to_end(key)
            return cached
    try:
        with open(os.path.join(cache_directory(), key + ".wfc"), "rb") as source:
            decoder = zlib.decompressobj()
            raw = decoder.decompress(source.read(), value["count"] * 4 + 1)
        if (len(raw) != value["count"] * 4 or not decoder.eof
                or hashlib.sha256(raw).hexdigest() != key):
            return ()
        if sys.byteorder != "little":
            packed = array("f")
            packed.frombytes(raw)
            packed.byteswap()
            raw = packed.tobytes()
        return _remember(key, memoryview(raw).cast("f"))
    except (OSError, ValueError, zlib.error):
        return ()


def externalize(value):
    """Replace legacy arrays, including detached undo snapshots, in place."""
    if isinstance(value, dict):
        for key, child in list(value.items()):
            if key in _KEYS:
                value[key] = store_samples(child)
            elif isinstance(child, (dict, list)):
                externalize(child)
    elif isinstance(value, list):
        for child in value:
            if isinstance(child, (dict, list)):
                externalize(child)
    return value


def transfer(value, directory, importing=False):
    """Copy referenced envelopes for open/save/save-as, including history."""
    if is_reference(value):
        name = value[_REF] + ".wfc"
        source, target = os.path.join(cache_directory(), name), os.path.join(directory, name)
        if importing:
            source, target = target, source
        if os.path.isfile(source) and not os.path.isfile(target):
            with open(source, "rb") as stream:
                _atomic_write(target, stream.read())
    elif isinstance(value, dict):
        for child in value.values():
            transfer(child, directory, importing)
    elif isinstance(value, list):
        for child in value:
            if isinstance(child, (dict, list)):
                transfer(child, directory, importing)
