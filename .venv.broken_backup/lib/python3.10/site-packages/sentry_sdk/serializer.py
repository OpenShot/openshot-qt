import sys
import math
from collections.abc import Mapping, Sequence, Set
from datetime import datetime

from sentry_sdk.utils import (
    AnnotatedValue,
    capture_internal_exception,
    disable_capture_event,
    format_timestamp,
    safe_repr,
    strip_string,
)

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from types import TracebackType

    from typing import Any
    from typing import Callable
    from typing import ContextManager
    from typing import Dict
    from typing import List
    from typing import Optional
    from typing import Type
    from typing import Union

    from sentry_sdk._types import NotImplementedType

    Span = Dict[str, Any]

    ReprProcessor = Callable[[Any, Dict[str, Any]], Union[NotImplementedType, str]]
    Segment = Union[str, int]


# Bytes are technically not strings in Python 3, but we can serialize them
serializable_str_types = (str, bytes, bytearray, memoryview)


# Maximum length of JSON-serialized event payloads that can be safely sent
# before the server may reject the event due to its size. This is not intended
# to reflect actual values defined server-side, but rather only be an upper
# bound for events sent by the SDK.
#
# Can be overwritten if wanting to send more bytes, e.g. with a custom server.
# When changing this, keep in mind that events may be a little bit larger than
# this value due to attached metadata, so keep the number conservative.
MAX_EVENT_BYTES = 10**6

# Maximum depth and breadth of databags. Excess data will be trimmed. If
# max_request_body_size is "always", request bodies won't be trimmed.
MAX_DATABAG_DEPTH = 5
MAX_DATABAG_BREADTH = 10
CYCLE_MARKER = "<cyclic>"


global_repr_processors: "List[ReprProcessor]" = []


def add_global_repr_processor(processor: "ReprProcessor") -> None:
    global_repr_processors.append(processor)


sequence_types: "List[type]" = [Sequence, Set]


def add_repr_sequence_type(ty: type) -> None:
    sequence_types.append(ty)


class Memo:
    __slots__ = ("_ids", "_objs")

    def __init__(self) -> None:
        self._ids: "Dict[int, Any]" = {}
        self._objs: "List[Any]" = []

    def memoize(self, obj: "Any") -> "ContextManager[bool]":
        self._objs.append(obj)
        return self

    def __enter__(self) -> bool:
        obj = self._objs[-1]
        if id(obj) in self._ids:
            return True
        else:
            self._ids[id(obj)] = obj
            return False

    def __exit__(
        self,
        ty: "Optional[Type[BaseException]]",
        value: "Optional[BaseException]",
        tb: "Optional[TracebackType]",
    ) -> None:
        self._ids.pop(id(self._objs.pop()), None)


def serialize(event: "Dict[str, Any]", **kwargs: "Any") -> "Dict[str, Any]":
    """
    A very smart serializer that takes a dict and emits a json-friendly dict.
    Currently used for serializing the final Event and also prematurely while fetching the stack
    local variables for each frame in a stacktrace.

    It works internally with 'databags' which are arbitrary data structures like Mapping, Sequence and Set.
    The algorithm itself is a recursive graph walk down the data structures it encounters.

    It has the following responsibilities:
    * Trimming databags and keeping them within MAX_DATABAG_BREADTH and MAX_DATABAG_DEPTH.
    * Calling safe_repr() on objects appropriately to keep them informative and readable in the final payload.
    * Annotating the payload with the _meta field whenever trimming happens.

    :param max_request_body_size: If set to "always", will never trim request bodies.
    :param max_value_length: The max length to strip strings to, defaults to sentry_sdk.consts.DEFAULT_MAX_VALUE_LENGTH
    :param is_vars: If we're serializing vars early, we want to repr() things that are JSON-serializable to make their type more apparent. For example, it's useful to see the difference between a unicode-string and a bytestring when viewing a stacktrace.
    :param custom_repr: A custom repr function that runs before safe_repr on the object to be serialized. If it returns None or throws internally, we will fallback to safe_repr.

    """
    memo = Memo()
    path: "List[Segment]" = []
    meta_stack: "List[Dict[str, Any]]" = []

    keep_request_bodies: bool = kwargs.pop("max_request_body_size", None) == "always"
    max_value_length: "Optional[int]" = kwargs.pop("max_value_length", None)
    is_vars = kwargs.pop("is_vars", False)
    custom_repr: "Callable[..., Optional[str]]" = kwargs.pop("custom_repr", None)

    def _safe_repr_wrapper(value: "Any") -> str:
        try:
            repr_value = None
            if custom_repr is not None:
                repr_value = custom_repr(value)
            return repr_value or safe_repr(value)
        except Exception:
            return safe_repr(value)

    def _annotate(**meta: "Any") -> None:
        while len(meta_stack) <= len(path):
            try:
                segment = path[len(meta_stack) - 1]
                node = meta_stack[-1].setdefault(str(segment), {})
            except IndexError:
                node = {}

            meta_stack.append(node)

        meta_stack[-1].setdefault("", {}).update(meta)

    def _is_databag() -> "Optional[bool]":
        """
        A databag is any value that we need to trim.
        True for stuff like vars, request bodies, breadcrumbs and extra.

        :returns: `True` for "yes", `False` for :"no", `None` for "maybe soon".
        """
        try:
            if is_vars:
                return True

            is_request_body = _is_request_body()
            if is_request_body in (True, None):
                return is_request_body

            p0 = path[0]
            if p0 == "breadcrumbs" and path[1] == "values":
                path[2]
                return True

            if p0 == "extra":
                return True

        except IndexError:
            return None

        return False

    def _is_span_attribute() -> "Optional[bool]":
        try:
            if path[0] == "spans" and path[2] == "data":
                return True
        except IndexError:
            return None

        return False

    def _is_request_body() -> "Optional[bool]":
        try:
            if path[0] == "request" and path[1] == "data":
                return True
        except IndexError:
            return None

        return False

    def _serialize_node(
        obj: "Any",
        is_databag: "Optional[bool]" = None,
        is_request_body: "Optional[bool]" = None,
        should_repr_strings: "Optional[bool]" = None,
        segment: "Optional[Segment]" = None,
        remaining_breadth: "Optional[Union[int, float]]" = None,
        remaining_depth: "Optional[Union[int, float]]" = None,
    ) -> "Any":
        if segment is not None:
            path.append(segment)

        try:
            with memo.memoize(obj) as result:
                if result:
                    return CYCLE_MARKER

                return _serialize_node_impl(
                    obj,
                    is_databag=is_databag,
                    is_request_body=is_request_body,
                    should_repr_strings=should_repr_strings,
                    remaining_depth=remaining_depth,
                    remaining_breadth=remaining_breadth,
                )
        except BaseException:
            capture_internal_exception(sys.exc_info())

            if is_databag:
                return "<failed to serialize, use init(debug=True) to see error logs>"

            return None
        finally:
            if segment is not None:
                path.pop()
                del meta_stack[len(path) + 1 :]

    def _flatten_annotated(obj: "Any") -> "Any":
        if isinstance(obj, AnnotatedValue):
            _annotate(**obj.metadata)
            obj = obj.value
        return obj

    def _serialize_node_impl(
        obj: "Any",
        is_databag: "Optional[bool]",
        is_request_body: "Optional[bool]",
        should_repr_strings: "Optional[bool]",
        remaining_depth: "Optional[Union[float, int]]",
        remaining_breadth: "Optional[Union[float, int]]",
    ) -> "Any":
        if isinstance(obj, AnnotatedValue):
            should_repr_strings = False
        if should_repr_strings is None:
            should_repr_strings = is_vars

        if is_databag is None:
            is_databag = _is_databag()

        if is_request_body is None:
            is_request_body = _is_request_body()

        if is_databag:
            if is_request_body and keep_request_bodies:
                remaining_depth = float("inf")
                remaining_breadth = float("inf")
            else:
                if remaining_depth is None:
                    remaining_depth = MAX_DATABAG_DEPTH
                if remaining_breadth is None:
                    remaining_breadth = MAX_DATABAG_BREADTH

        obj = _flatten_annotated(obj)

        if remaining_depth is not None and remaining_depth <= 0:
            _annotate(rem=[["!limit", "x"]])
            if is_databag:
                return _flatten_annotated(
                    strip_string(_safe_repr_wrapper(obj), max_length=max_value_length)
                )
            return None

        is_span_attribute = _is_span_attribute()
        if (is_databag or is_span_attribute) and global_repr_processors:
            hints = {"memo": memo, "remaining_depth": remaining_depth}
            for processor in global_repr_processors:
                result = processor(obj, hints)
                if result is not NotImplemented:
                    return _flatten_annotated(result)

        sentry_repr = getattr(type(obj), "__sentry_repr__", None)

        if obj is None or isinstance(obj, (bool, int, float)):
            if should_repr_strings or (
                isinstance(obj, float) and (math.isinf(obj) or math.isnan(obj))
            ):
                return _safe_repr_wrapper(obj)
            else:
                return obj

        elif callable(sentry_repr):
            return sentry_repr(obj)

        elif isinstance(obj, datetime):
            return (
                str(format_timestamp(obj))
                if not should_repr_strings
                else _safe_repr_wrapper(obj)
            )

        elif isinstance(obj, Mapping):
            # Create temporary copy here to avoid calling too much code that
            # might mutate our dictionary while we're still iterating over it.
            obj = dict(obj.items())

            rv_dict: "Dict[str, Any]" = {}
            i = 0

            for k, v in obj.items():
                if remaining_breadth is not None and i >= remaining_breadth:
                    _annotate(len=len(obj))
                    break

                str_k = str(k)
                v = _serialize_node(
                    v,
                    segment=str_k,
                    should_repr_strings=should_repr_strings,
                    is_databag=is_databag,
                    is_request_body=is_request_body,
                    remaining_depth=(
                        remaining_depth - 1 if remaining_depth is not None else None
                    ),
                    remaining_breadth=remaining_breadth,
                )
                rv_dict[str_k] = v
                i += 1

            return rv_dict

        elif not isinstance(obj, serializable_str_types) and isinstance(
            obj, tuple(sequence_types)
        ):
            rv_list = []

            for i, v in enumerate(obj):
                if remaining_breadth is not None and i >= remaining_breadth:
                    _annotate(len=len(obj))
                    break

                rv_list.append(
                    _serialize_node(
                        v,
                        segment=i,
                        should_repr_strings=should_repr_strings,
                        is_databag=is_databag,
                        is_request_body=is_request_body,
                        remaining_depth=(
                            remaining_depth - 1 if remaining_depth is not None else None
                        ),
                        remaining_breadth=remaining_breadth,
                    )
                )

            return rv_list

        if should_repr_strings:
            obj = _safe_repr_wrapper(obj)
        else:
            if isinstance(obj, bytes) or isinstance(obj, bytearray):
                obj = obj.decode("utf-8", "replace")

            if not isinstance(obj, str):
                obj = _safe_repr_wrapper(obj)

        is_span_description = (
            len(path) == 3 and path[0] == "spans" and path[-1] == "description"
        )
        if is_span_description:
            return obj

        return _flatten_annotated(strip_string(obj, max_length=max_value_length))

    #
    # Start of serialize() function
    #
    disable_capture_event.set(True)
    try:
        serialized_event = _serialize_node(event, **kwargs)
        if not is_vars and meta_stack and isinstance(serialized_event, dict):
            serialized_event["_meta"] = meta_stack[0]

        return serialized_event
    finally:
        disable_capture_event.set(False)
