from uuid import (
    NAMESPACE_DNS,
    NAMESPACE_OID,
    NAMESPACE_URL,
    NAMESPACE_X500,
    RESERVED_FUTURE,
    RESERVED_MICROSOFT,
    RESERVED_NCS,
    RFC_4122,
    UUID,
    getnode,
)

import uuid_utils

NIL = UUID("00000000-0000-0000-0000-000000000000")
MAX = UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")


def uuid1(node=None, clock_seq=None):
    """Generate a UUID from a host ID, sequence number, and the current time.
    If 'node' is not given, getnode() is used to obtain the hardware
    address.  If 'clock_seq' is given, it is used as the sequence number;
    otherwise a random 14-bit sequence number is chosen."""
    return UUID(int=uuid_utils.uuid1(node, clock_seq).int)


def uuid3(namespace, name):
    """Generate a UUID from the MD5 hash of a namespace UUID and a name."""
    namespace = uuid_utils.UUID(namespace.hex) if namespace else namespace
    return UUID(int=uuid_utils.uuid3(namespace, name).int)


def uuid4():
    """Generate a random UUID."""
    return UUID(int=uuid_utils.uuid4().int)


def uuid5(namespace, name):
    """Generate a UUID from the SHA-1 hash of a namespace UUID and a name."""
    namespace = uuid_utils.UUID(namespace.hex) if namespace else namespace
    return UUID(int=uuid_utils.uuid5(namespace, name).int)


def uuid6(node=None, timestamp=None):
    """Generate a version 6 UUID using the given timestamp and a host ID.
    This is similar to version 1 UUIDs,
    except that it is lexicographically sortable by timestamp.
    """
    return UUID(int=uuid_utils.uuid6(node, timestamp).int)


def uuid7(timestamp=None, nanos=None):
    """Generate a version 7 UUID using a time value and random bytes."""
    return UUID(int=uuid_utils.uuid7(timestamp, nanos).int)


def uuid8(bytes):
    """Generate a custom UUID comprised almost entirely of user-supplied bytes.."""
    return UUID(bytes=uuid_utils.uuid8(bytes).bytes)


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
    "getnode",
    "uuid1",
    "uuid3",
    "uuid4",
    "uuid5",
    "uuid6",
    "uuid7",
    "uuid8",
]
