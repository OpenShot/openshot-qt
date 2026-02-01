import builtins
import sys
from typing import Final
from uuid import SafeUUID

from typing_extensions import LiteralString, TypeAlias

# Because UUID has properties called int and bytes we need to rename these temporarily.
_FieldsType: TypeAlias = tuple[int, int, int, int, int, int]

__version__: str

class UUID:
    """Instances of the UUID class represent UUIDs as specified in RFC 4122.
    UUID objects are immutable, hashable, and usable as dictionary keys.
    Converting a UUID to a string with str() yields something in the form
    '12345678-1234-1234-1234-123456789abc'.  The UUID constructor accepts
    five possible forms: a similar string of hexadecimal digits, or a tuple
    of six integer fields (with 32-bit, 16-bit, 16-bit, 8-bit, 8-bit, and
    48-bit values respectively) as an argument named 'fields', or a string
    of 16 bytes (with all the integer fields in big-endian order) as an
    argument named 'bytes', or a string of 16 bytes (with the first three
    fields in little-endian order) as an argument named 'bytes_le', or a
    single 128-bit integer as an argument named 'int'.

    UUIDs have these read-only attributes:

        bytes       the UUID as a 16-byte string (containing the six
                    integer fields in big-endian byte order)

        bytes_le    the UUID as a 16-byte string (with time_low, time_mid,
                    and time_hi_version in little-endian byte order)

        fields      a tuple of the six integer fields of the UUID,
                    which are also available as six individual attributes
                    and two derived attributes:

            time_low                the first 32 bits of the UUID
            time_mid                the next 16 bits of the UUID
            time_hi_version         the next 16 bits of the UUID
            clock_seq_hi_variant    the next 8 bits of the UUID
            clock_seq_low           the next 8 bits of the UUID
            node                    the last 48 bits of the UUID

            time                    the 60-bit timestamp
            clock_seq               the 14-bit sequence number

        hex         the UUID as a 32-character hexadecimal string

        int         the UUID as a 128-bit integer

        urn         the UUID as a URN as specified in RFC 4122

        variant     the UUID variant (one of the constants RESERVED_NCS,
                    RFC_4122, RESERVED_MICROSOFT, or RESERVED_FUTURE)

        version     the UUID version number

        is_safe     An enum indicating whether the UUID has been generated in
                    a way that is safe for multiprocessing applications, via
                    uuid_generate_time_safe(3).

        timestamp   The timestamp of the UUID in milliseconds since epoch.
                    Only works for UUID versions 1, 6 and 7,
                    otherwise raises ValueError.
    """

    is_safe: Final[SafeUUID]
    int: Final[builtins.int]

    def __init__(
        self,
        hex: str | None = None,
        bytes: builtins.bytes | None = None,
        bytes_le: builtins.bytes | None = None,
        fields: _FieldsType | None = None,
        int: builtins.int | None = None,
        version: builtins.int | None = None,
        *,
        is_safe: SafeUUID = ...,
    ) -> None: ...
    @property
    def bytes(self) -> builtins.bytes: ...
    @property
    def bytes_le(self) -> builtins.bytes: ...
    @property
    def clock_seq(self) -> builtins.int: ...
    @property
    def clock_seq_hi_variant(self) -> builtins.int: ...
    @property
    def clock_seq_low(self) -> builtins.int: ...
    @property
    def fields(self) -> _FieldsType: ...
    @property
    def hex(self) -> str: ...
    @property
    def node(self) -> builtins.int: ...
    @property
    def time(self) -> builtins.int: ...
    @property
    def time_hi_version(self) -> builtins.int: ...
    @property
    def time_low(self) -> builtins.int: ...
    @property
    def time_mid(self) -> builtins.int: ...
    @property
    def timestamp(self) -> builtins.int:
        """Get UUID timestamp milliseconds since epoch.
        Only works for UUID versions 1, 6 and 7, otherwise raises ValueError."""
        ...

    @property
    def urn(self) -> str: ...
    @property
    def variant(self) -> str: ...
    @property
    def version(self) -> builtins.int | None: ...
    def __int__(self) -> builtins.int: ...
    def __hash__(self) -> builtins.int: ...
    def __eq__(self, other: object) -> bool: ...
    def __lt__(self, other: UUID) -> bool: ...
    def __le__(self, other: UUID) -> bool: ...
    def __gt__(self, other: UUID) -> bool: ...
    def __ge__(self, other: UUID) -> bool: ...

def getnode() -> int: ...
def reseed_rng() -> None:
    """
    Reseeds the underlying rng.
    This is useful in cases where you fork, as without reseeding the
    generated uuids may be identical. This can be called manually in the child process,
    or automatically run after fork with:

    os.register_at_fork(after_in_child=uuid_utils.reseed_rng)
    """
    ...

def uuid1(node: int | None = None, clock_seq: int | None = None) -> UUID:
    """Generate a UUID from a host ID, sequence number, and the current time.
    If 'node' is not given, getnode() is used to obtain the hardware
    address.  If 'clock_seq' is given, it is used as the sequence number;
    otherwise a random 14-bit sequence number is chosen."""
    ...

if sys.version_info >= (3, 12):
    def uuid3(namespace: UUID, name: str | bytes) -> UUID:
        """Generate a UUID from the MD5 hash of a namespace UUID and a name."""
        ...
else:
    def uuid3(namespace: UUID, name: str) -> UUID:
        """Generate a UUID from the MD5 hash of a namespace UUID and a name."""
        ...

def uuid4() -> UUID:
    """Generate a random UUID."""
    ...

if sys.version_info >= (3, 12):
    def uuid5(namespace: UUID, name: str | bytes) -> UUID:
        """Generate a UUID from the SHA-1 hash of a namespace UUID and a name."""
        ...
else:
    def uuid5(namespace: UUID, name: str) -> UUID:
        """Generate a UUID from the SHA-1 hash of a namespace UUID and a name."""
        ...

def uuid6(
    node: int | None = None, timestamp: int | None = None, nanos: int | None = None
) -> UUID:
    """Generate a version 6 UUID using the given timestamp and a host ID.
    This is similar to version 1 UUIDs,
    except that it is lexicographically sortable by timestamp.
    """
    ...

def uuid7(timestamp: int | None = None, nanos: int | None = None) -> UUID:
    """Generate a version 7 UUID using a time value and random bytes."""
    ...

def uuid8(bytes: bytes) -> UUID:
    """Generate a custom UUID comprised almost entirely of user-supplied bytes."""
    ...

NAMESPACE_DNS: Final[UUID]
NAMESPACE_URL: Final[UUID]
NAMESPACE_OID: Final[UUID]
NAMESPACE_X500: Final[UUID]
RESERVED_NCS: Final[LiteralString]
RFC_4122: Final[LiteralString]
RESERVED_MICROSOFT: Final[LiteralString]
RESERVED_FUTURE: Final[LiteralString]
NIL: Final[UUID]
MAX: Final[UUID]

__all__ = [
    "MAX",
    "NAMESPACE_DNS",
    "NAMESPACE_OID",
    "NAMESPACE_URL",
    "NAMESPACE_X500",
    "NIL",
    "RESERVED_FUTURE",
    "RESERVED_MICROSOFT",
    "RESERVED_NCS",
    "RFC_4122",
    "UUID",
    "SafeUUID",
    "__version__",
    "getnode",
    "reseed_rng",
    "uuid1",
    "uuid3",
    "uuid4",
    "uuid5",
    "uuid6",
    "uuid7",
    "uuid8",
]
