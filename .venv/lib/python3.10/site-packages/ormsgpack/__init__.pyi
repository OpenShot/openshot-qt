from collections.abc import Callable
from typing import Any

__version__: str

def packb(
    obj: Any,
    /,
    default: Callable[[Any], Any] | None = ...,
    option: int | None = None,
) -> bytes: ...
def unpackb(
    obj: bytes | bytearray | memoryview,
    /,
    *,
    ext_hook: Callable[[int, bytes], Any] | None = ...,
    option: int | None = ...,
) -> Any: ...

class MsgpackDecodeError(ValueError): ...
class MsgpackEncodeError(TypeError): ...

class Ext:
    def __init__(self, tag: int, data: bytes) -> None: ...

OPT_DATETIME_AS_TIMESTAMP_EXT: int
OPT_NAIVE_UTC: int
OPT_OMIT_MICROSECONDS: int
OPT_PASSTHROUGH_BIG_INT: int
OPT_PASSTHROUGH_DATACLASS: int
OPT_PASSTHROUGH_DATETIME: int
OPT_PASSTHROUGH_ENUM: int
OPT_PASSTHROUGH_SUBCLASS: int
OPT_PASSTHROUGH_TUPLE: int
OPT_PASSTHROUGH_UUID: int
OPT_REPLACE_SURROGATES: int
OPT_SERIALIZE_NUMPY: int
OPT_SERIALIZE_PYDANTIC: int
OPT_NON_STR_KEYS: int
OPT_SORT_KEYS: int
OPT_UTC_Z: int
