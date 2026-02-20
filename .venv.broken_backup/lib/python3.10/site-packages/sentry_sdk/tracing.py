import uuid
import warnings
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import TYPE_CHECKING

import sentry_sdk
from sentry_sdk.consts import INSTRUMENTER, SPANDATA, SPANSTATUS, SPANTEMPLATE
from sentry_sdk.profiler.continuous_profiler import get_profiler_id
from sentry_sdk.utils import (
    capture_internal_exceptions,
    get_current_thread_meta,
    is_valid_sample_rate,
    logger,
    nanosecond_time,
    should_be_treated_as_error,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, MutableMapping
    from typing import (
        Any,
        Dict,
        Iterator,
        List,
        Optional,
        ParamSpec,
        Set,
        Tuple,
        TypeVar,
        Union,
        overload,
    )

    from typing_extensions import TypedDict, Unpack

    P = ParamSpec("P")
    R = TypeVar("R")

    from sentry_sdk._types import (
        Event,
        MeasurementUnit,
        MeasurementValue,
        SamplingContext,
    )
    from sentry_sdk.profiler.continuous_profiler import ContinuousProfile
    from sentry_sdk.profiler.transaction_profiler import Profile

    class SpanKwargs(TypedDict, total=False):
        trace_id: str
        """
        The trace ID of the root span. If this new span is to be the root span,
        omit this parameter, and a new trace ID will be generated.
        """

        span_id: str
        """The span ID of this span. If omitted, a new span ID will be generated."""

        parent_span_id: str
        """The span ID of the parent span, if applicable."""

        same_process_as_parent: bool
        """Whether this span is in the same process as the parent span."""

        sampled: bool
        """
        Whether the span should be sampled. Overrides the default sampling decision
        for this span when provided.
        """

        op: str
        """
        The span's operation. A list of recommended values is available here:
        https://develop.sentry.dev/sdk/performance/span-operations/
        """

        description: str
        """A description of what operation is being performed within the span. This argument is DEPRECATED. Please use the `name` parameter, instead."""

        hub: "Optional[sentry_sdk.Hub]"
        """The hub to use for this span. This argument is DEPRECATED. Please use the `scope` parameter, instead."""

        status: str
        """The span's status. Possible values are listed at https://develop.sentry.dev/sdk/event-payloads/span/"""

        containing_transaction: "Optional[Transaction]"
        """The transaction that this span belongs to."""

        start_timestamp: "Optional[Union[datetime, float]]"
        """
        The timestamp when the span started. If omitted, the current time
        will be used.
        """

        scope: "sentry_sdk.Scope"
        """The scope to use for this span. If not provided, we use the current scope."""

        origin: str
        """
        The origin of the span.
        See https://develop.sentry.dev/sdk/performance/trace-origin/
        Default "manual".
        """

        name: str
        """A string describing what operation is being performed within the span/transaction."""

    class TransactionKwargs(SpanKwargs, total=False):
        source: str
        """
        A string describing the source of the transaction name. This will be used to determine the transaction's type.
        See https://develop.sentry.dev/sdk/event-payloads/transaction/#transaction-annotations for more information.
        Default "custom".
        """

        parent_sampled: bool
        """Whether the parent transaction was sampled. If True this transaction will be kept, if False it will be discarded."""

        baggage: "Baggage"
        """The W3C baggage header value. (see https://www.w3.org/TR/baggage/)"""

    ProfileContext = TypedDict(
        "ProfileContext",
        {
            "profiler_id": str,
        },
    )

BAGGAGE_HEADER_NAME = "baggage"
SENTRY_TRACE_HEADER_NAME = "sentry-trace"


# Transaction source
# see https://develop.sentry.dev/sdk/event-payloads/transaction/#transaction-annotations
class TransactionSource(str, Enum):
    COMPONENT = "component"
    CUSTOM = "custom"
    ROUTE = "route"
    TASK = "task"
    URL = "url"
    VIEW = "view"

    def __str__(self) -> str:
        return self.value


# These are typically high cardinality and the server hates them
LOW_QUALITY_TRANSACTION_SOURCES = [
    TransactionSource.URL,
]

SOURCE_FOR_STYLE = {
    "endpoint": TransactionSource.COMPONENT,
    "function_name": TransactionSource.COMPONENT,
    "handler_name": TransactionSource.COMPONENT,
    "method_and_path_pattern": TransactionSource.ROUTE,
    "path": TransactionSource.URL,
    "route_name": TransactionSource.COMPONENT,
    "route_pattern": TransactionSource.ROUTE,
    "uri_template": TransactionSource.ROUTE,
    "url": TransactionSource.ROUTE,
}


def get_span_status_from_http_code(http_status_code: int) -> str:
    """
    Returns the Sentry status corresponding to the given HTTP status code.

    See: https://develop.sentry.dev/sdk/event-payloads/contexts/#trace-context
    """
    if http_status_code < 400:
        return SPANSTATUS.OK

    elif 400 <= http_status_code < 500:
        if http_status_code == 403:
            return SPANSTATUS.PERMISSION_DENIED
        elif http_status_code == 404:
            return SPANSTATUS.NOT_FOUND
        elif http_status_code == 429:
            return SPANSTATUS.RESOURCE_EXHAUSTED
        elif http_status_code == 413:
            return SPANSTATUS.FAILED_PRECONDITION
        elif http_status_code == 401:
            return SPANSTATUS.UNAUTHENTICATED
        elif http_status_code == 409:
            return SPANSTATUS.ALREADY_EXISTS
        else:
            return SPANSTATUS.INVALID_ARGUMENT

    elif 500 <= http_status_code < 600:
        if http_status_code == 504:
            return SPANSTATUS.DEADLINE_EXCEEDED
        elif http_status_code == 501:
            return SPANSTATUS.UNIMPLEMENTED
        elif http_status_code == 503:
            return SPANSTATUS.UNAVAILABLE
        else:
            return SPANSTATUS.INTERNAL_ERROR

    return SPANSTATUS.UNKNOWN_ERROR


class _SpanRecorder:
    """Limits the number of spans recorded in a transaction."""

    __slots__ = ("maxlen", "spans", "dropped_spans")

    def __init__(self, maxlen: int) -> None:
        # FIXME: this is `maxlen - 1` only to preserve historical behavior
        # enforced by tests.
        # Either this should be changed to `maxlen` or the JS SDK implementation
        # should be changed to match a consistent interpretation of what maxlen
        # limits: either transaction+spans or only child spans.
        self.maxlen = maxlen - 1
        self.spans: "List[Span]" = []
        self.dropped_spans: int = 0

    def add(self, span: "Span") -> None:
        if len(self.spans) > self.maxlen:
            span._span_recorder = None
            self.dropped_spans += 1
        else:
            self.spans.append(span)


class Span:
    """A span holds timing information of a block of code.
    Spans can have multiple child spans thus forming a span tree.

    :param trace_id: The trace ID of the root span. If this new span is to be the root span,
        omit this parameter, and a new trace ID will be generated.
    :param span_id: The span ID of this span. If omitted, a new span ID will be generated.
    :param parent_span_id: The span ID of the parent span, if applicable.
    :param same_process_as_parent: Whether this span is in the same process as the parent span.
    :param sampled: Whether the span should be sampled. Overrides the default sampling decision
        for this span when provided.
    :param op: The span's operation. A list of recommended values is available here:
        https://develop.sentry.dev/sdk/performance/span-operations/
    :param description: A description of what operation is being performed within the span.

        .. deprecated:: 2.15.0
            Please use the `name` parameter, instead.
    :param name: A string describing what operation is being performed within the span.
    :param hub: The hub to use for this span.

        .. deprecated:: 2.0.0
            Please use the `scope` parameter, instead.
    :param status: The span's status. Possible values are listed at
        https://develop.sentry.dev/sdk/event-payloads/span/
    :param containing_transaction: The transaction that this span belongs to.
    :param start_timestamp: The timestamp when the span started. If omitted, the current time
        will be used.
    :param scope: The scope to use for this span. If not provided, we use the current scope.
    """

    __slots__ = (
        "_trace_id",
        "_span_id",
        "parent_span_id",
        "same_process_as_parent",
        "sampled",
        "op",
        "description",
        "_measurements",
        "start_timestamp",
        "_start_timestamp_monotonic_ns",
        "status",
        "timestamp",
        "_tags",
        "_data",
        "_span_recorder",
        "hub",
        "_context_manager_state",
        "_containing_transaction",
        "scope",
        "origin",
        "name",
        "_flags",
        "_flags_capacity",
    )

    def __init__(
        self,
        trace_id: "Optional[str]" = None,
        span_id: "Optional[str]" = None,
        parent_span_id: "Optional[str]" = None,
        same_process_as_parent: bool = True,
        sampled: "Optional[bool]" = None,
        op: "Optional[str]" = None,
        description: "Optional[str]" = None,
        hub: "Optional[sentry_sdk.Hub]" = None,  # deprecated
        status: "Optional[str]" = None,
        containing_transaction: "Optional[Transaction]" = None,
        start_timestamp: "Optional[Union[datetime, float]]" = None,
        scope: "Optional[sentry_sdk.Scope]" = None,
        origin: str = "manual",
        name: "Optional[str]" = None,
    ) -> None:
        self._trace_id = trace_id
        self._span_id = span_id
        self.parent_span_id = parent_span_id
        self.same_process_as_parent = same_process_as_parent
        self.sampled = sampled
        self.op = op
        self.description = name or description
        self.status = status
        self.hub = hub  # backwards compatibility
        self.scope = scope
        self.origin = origin
        self._measurements: "Dict[str, MeasurementValue]" = {}
        self._tags: "MutableMapping[str, str]" = {}
        self._data: "Dict[str, Any]" = {}
        self._containing_transaction = containing_transaction
        self._flags: "Dict[str, bool]" = {}
        self._flags_capacity = 10

        if hub is not None:
            warnings.warn(
                "The `hub` parameter is deprecated. Please use `scope` instead.",
                DeprecationWarning,
                stacklevel=2,
            )

            self.scope = self.scope or hub.scope

        if start_timestamp is None:
            start_timestamp = datetime.now(timezone.utc)
        elif isinstance(start_timestamp, float):
            start_timestamp = datetime.fromtimestamp(start_timestamp, timezone.utc)
        self.start_timestamp = start_timestamp
        try:
            # profiling depends on this value and requires that
            # it is measured in nanoseconds
            self._start_timestamp_monotonic_ns = nanosecond_time()
        except AttributeError:
            pass

        #: End timestamp of span
        self.timestamp: "Optional[datetime]" = None

        self._span_recorder: "Optional[_SpanRecorder]" = None

        self.update_active_thread()
        self.set_profiler_id(get_profiler_id())

    # TODO this should really live on the Transaction class rather than the Span
    # class
    def init_span_recorder(self, maxlen: int) -> None:
        if self._span_recorder is None:
            self._span_recorder = _SpanRecorder(maxlen)

    @property
    def trace_id(self) -> str:
        if not self._trace_id:
            self._trace_id = uuid.uuid4().hex

        return self._trace_id

    @trace_id.setter
    def trace_id(self, value: str) -> None:
        self._trace_id = value

    @property
    def span_id(self) -> str:
        if not self._span_id:
            self._span_id = uuid.uuid4().hex[16:]

        return self._span_id

    @span_id.setter
    def span_id(self, value: str) -> None:
        self._span_id = value

    def __repr__(self) -> str:
        return (
            "<%s(op=%r, description:%r, trace_id=%r, span_id=%r, parent_span_id=%r, sampled=%r, origin=%r)>"
            % (
                self.__class__.__name__,
                self.op,
                self.description,
                self.trace_id,
                self.span_id,
                self.parent_span_id,
                self.sampled,
                self.origin,
            )
        )

    def __enter__(self) -> "Span":
        scope = self.scope or sentry_sdk.get_current_scope()
        old_span = scope.span
        scope.span = self
        self._context_manager_state = (scope, old_span)
        return self

    def __exit__(
        self, ty: "Optional[Any]", value: "Optional[Any]", tb: "Optional[Any]"
    ) -> None:
        if value is not None and should_be_treated_as_error(ty, value):
            self.set_status(SPANSTATUS.INTERNAL_ERROR)

        with capture_internal_exceptions():
            scope, old_span = self._context_manager_state
            del self._context_manager_state
            self.finish(scope)
            scope.span = old_span

    @property
    def containing_transaction(self) -> "Optional[Transaction]":
        """The ``Transaction`` that this span belongs to.
        The ``Transaction`` is the root of the span tree,
        so one could also think of this ``Transaction`` as the "root span"."""

        # this is a getter rather than a regular attribute so that transactions
        # can return `self` here instead (as a way to prevent them circularly
        # referencing themselves)
        return self._containing_transaction

    def start_child(
        self, instrumenter: str = INSTRUMENTER.SENTRY, **kwargs: "Any"
    ) -> "Span":
        """
        Start a sub-span from the current span or transaction.

        Takes the same arguments as the initializer of :py:class:`Span`. The
        trace id, sampling decision, transaction pointer, and span recorder are
        inherited from the current span/transaction.

        The instrumenter parameter is deprecated for user code, and it will
        be removed in the next major version. Going forward, it should only
        be used by the SDK itself.
        """
        if kwargs.get("description") is not None:
            warnings.warn(
                "The `description` parameter is deprecated. Please use `name` instead.",
                DeprecationWarning,
                stacklevel=2,
            )

        configuration_instrumenter = sentry_sdk.get_client().options["instrumenter"]

        if instrumenter != configuration_instrumenter:
            return NoOpSpan()

        kwargs.setdefault("sampled", self.sampled)

        child = Span(
            trace_id=self.trace_id,
            parent_span_id=self.span_id,
            containing_transaction=self.containing_transaction,
            **kwargs,
        )

        span_recorder = (
            self.containing_transaction and self.containing_transaction._span_recorder
        )
        if span_recorder:
            span_recorder.add(child)

        return child

    @classmethod
    def continue_from_environ(
        cls,
        environ: "Mapping[str, str]",
        **kwargs: "Any",
    ) -> "Transaction":
        """
        DEPRECATED: Use :py:meth:`sentry_sdk.continue_trace`.

        Create a Transaction with the given params, then add in data pulled from
        the ``sentry-trace`` and ``baggage`` headers from the environ (if any)
        before returning the Transaction.

        This is different from :py:meth:`~sentry_sdk.tracing.Span.continue_from_headers`
        in that it assumes header names in the form ``HTTP_HEADER_NAME`` -
        such as you would get from a WSGI/ASGI environ -
        rather than the form ``header-name``.

        :param environ: The ASGI/WSGI environ to pull information from.
        """
        return Transaction.continue_from_headers(EnvironHeaders(environ), **kwargs)

    @classmethod
    def continue_from_headers(
        cls,
        headers: "Mapping[str, str]",
        *,
        _sample_rand: "Optional[str]" = None,
        **kwargs: "Any",
    ) -> "Transaction":
        """
        DEPRECATED: Use :py:meth:`sentry_sdk.continue_trace`.

        Create a transaction with the given params (including any data pulled from
        the ``sentry-trace`` and ``baggage`` headers).

        :param headers: The dictionary with the HTTP headers to pull information from.
        :param _sample_rand: If provided, we override the sample_rand value from the
            incoming headers with this value. (internal use only)
        """
        logger.warning("Deprecated: use sentry_sdk.continue_trace instead.")

        # TODO-neel move away from this kwargs stuff, it's confusing and opaque
        # make more explicit
        baggage = Baggage.from_incoming_header(
            headers.get(BAGGAGE_HEADER_NAME), _sample_rand=_sample_rand
        )
        kwargs.update({BAGGAGE_HEADER_NAME: baggage})

        sentrytrace_kwargs = extract_sentrytrace_data(
            headers.get(SENTRY_TRACE_HEADER_NAME)
        )

        if sentrytrace_kwargs is not None:
            kwargs.update(sentrytrace_kwargs)

            # If there's an incoming sentry-trace but no incoming baggage header,
            # for instance in traces coming from older SDKs,
            # baggage will be empty and immutable and won't be populated as head SDK.
            baggage.freeze()

        transaction = Transaction(**kwargs)
        transaction.same_process_as_parent = False

        return transaction

    def iter_headers(self) -> "Iterator[Tuple[str, str]]":
        """
        Creates a generator which returns the span's ``sentry-trace`` and ``baggage`` headers.
        If the span's containing transaction doesn't yet have a ``baggage`` value,
        this will cause one to be generated and stored.
        """
        if not self.containing_transaction:
            # Do not propagate headers if there is no containing transaction. Otherwise, this
            # span ends up being the root span of a new trace, and since it does not get sent
            # to Sentry, the trace will be missing a root transaction. The dynamic sampling
            # context will also be missing, breaking dynamic sampling & traces.
            return

        yield SENTRY_TRACE_HEADER_NAME, self.to_traceparent()

        baggage = self.containing_transaction.get_baggage().serialize()
        if baggage:
            yield BAGGAGE_HEADER_NAME, baggage

    @classmethod
    def from_traceparent(
        cls,
        traceparent: "Optional[str]",
        **kwargs: "Any",
    ) -> "Optional[Transaction]":
        """
        DEPRECATED: Use :py:meth:`sentry_sdk.continue_trace`.

        Create a ``Transaction`` with the given params, then add in data pulled from
        the given ``sentry-trace`` header value before returning the ``Transaction``.
        """
        if not traceparent:
            return None

        return cls.continue_from_headers(
            {SENTRY_TRACE_HEADER_NAME: traceparent}, **kwargs
        )

    def to_traceparent(self) -> str:
        if self.sampled is True:
            sampled = "1"
        elif self.sampled is False:
            sampled = "0"
        else:
            sampled = None

        traceparent = "%s-%s" % (self.trace_id, self.span_id)
        if sampled is not None:
            traceparent += "-%s" % (sampled,)

        return traceparent

    def to_baggage(self) -> "Optional[Baggage]":
        """Returns the :py:class:`~sentry_sdk.tracing_utils.Baggage`
        associated with this ``Span``, if any. (Taken from the root of the span tree.)
        """
        if self.containing_transaction:
            return self.containing_transaction.get_baggage()
        return None

    def set_tag(self, key: str, value: "Any") -> None:
        self._tags[key] = value

    def set_data(self, key: str, value: "Any") -> None:
        self._data[key] = value

    def update_data(self, data: "Dict[str, Any]") -> None:
        self._data.update(data)

    def set_flag(self, flag: str, result: bool) -> None:
        if len(self._flags) < self._flags_capacity:
            self._flags[flag] = result

    def set_status(self, value: str) -> None:
        self.status = value

    def set_measurement(
        self, name: str, value: float, unit: "MeasurementUnit" = ""
    ) -> None:
        """
        .. deprecated:: 2.28.0
            This function is deprecated and will be removed in the next major release.
        """

        warnings.warn(
            "`set_measurement()` is deprecated and will be removed in the next major version. Please use `set_data()` instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        self._measurements[name] = {"value": value, "unit": unit}

    def set_thread(
        self, thread_id: "Optional[int]", thread_name: "Optional[str]"
    ) -> None:
        if thread_id is not None:
            self.set_data(SPANDATA.THREAD_ID, str(thread_id))

            if thread_name is not None:
                self.set_data(SPANDATA.THREAD_NAME, thread_name)

    def set_profiler_id(self, profiler_id: "Optional[str]") -> None:
        if profiler_id is not None:
            self.set_data(SPANDATA.PROFILER_ID, profiler_id)

    def set_http_status(self, http_status: int) -> None:
        self.set_tag(
            "http.status_code", str(http_status)
        )  # TODO-neel remove in major, we keep this for backwards compatibility
        self.set_data(SPANDATA.HTTP_STATUS_CODE, http_status)
        self.set_status(get_span_status_from_http_code(http_status))

    def is_success(self) -> bool:
        return self.status == "ok"

    def finish(
        self,
        scope: "Optional[sentry_sdk.Scope]" = None,
        end_timestamp: "Optional[Union[float, datetime]]" = None,
    ) -> "Optional[str]":
        """
        Sets the end timestamp of the span.

        Additionally it also creates a breadcrumb from the span,
        if the span represents a database or HTTP request.

        :param scope: The scope to use for this transaction.
            If not provided, the current scope will be used.
        :param end_timestamp: Optional timestamp that should
            be used as timestamp instead of the current time.

        :return: Always ``None``. The type is ``Optional[str]`` to match
            the return value of :py:meth:`sentry_sdk.tracing.Transaction.finish`.
        """
        if self.timestamp is not None:
            # This span is already finished, ignore.
            return None

        try:
            if end_timestamp:
                if isinstance(end_timestamp, float):
                    end_timestamp = datetime.fromtimestamp(end_timestamp, timezone.utc)
                self.timestamp = end_timestamp
            else:
                elapsed = nanosecond_time() - self._start_timestamp_monotonic_ns
                self.timestamp = self.start_timestamp + timedelta(
                    microseconds=elapsed / 1000
                )
        except AttributeError:
            self.timestamp = datetime.now(timezone.utc)

        scope = scope or sentry_sdk.get_current_scope()

        # Copy conversation_id from scope to span data if this is an AI span
        conversation_id = scope.get_conversation_id()
        if conversation_id:
            has_ai_op = SPANDATA.GEN_AI_OPERATION_NAME in self._data
            is_ai_span_op = self.op is not None and (
                self.op.startswith("ai.") or self.op.startswith("gen_ai.")
            )
            if has_ai_op or is_ai_span_op:
                self.set_data("gen_ai.conversation.id", conversation_id)

        maybe_create_breadcrumbs_from_span(scope, self)

        return None

    def to_json(self) -> "Dict[str, Any]":
        """Returns a JSON-compatible representation of the span."""

        rv: "Dict[str, Any]" = {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "same_process_as_parent": self.same_process_as_parent,
            "op": self.op,
            "description": self.description,
            "start_timestamp": self.start_timestamp,
            "timestamp": self.timestamp,
            "origin": self.origin,
        }

        if self.status:
            rv["status"] = self.status
            # TODO-neel remove redundant tag in major
            self._tags["status"] = self.status

        if len(self._measurements) > 0:
            rv["measurements"] = self._measurements

        tags = self._tags
        if tags:
            rv["tags"] = tags

        data = {}
        data.update(self._flags)
        data.update(self._data)
        if data:
            rv["data"] = data

        return rv

    def get_trace_context(self) -> "Any":
        rv: "Dict[str, Any]" = {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "op": self.op,
            "description": self.description,
            "origin": self.origin,
        }
        if self.status:
            rv["status"] = self.status

        if self.containing_transaction:
            rv["dynamic_sampling_context"] = (
                self.containing_transaction.get_baggage().dynamic_sampling_context()
            )

        data = {}

        thread_id = self._data.get(SPANDATA.THREAD_ID)
        if thread_id is not None:
            data["thread.id"] = thread_id

        thread_name = self._data.get(SPANDATA.THREAD_NAME)
        if thread_name is not None:
            data["thread.name"] = thread_name

        if data:
            rv["data"] = data

        return rv

    def get_profile_context(self) -> "Optional[ProfileContext]":
        profiler_id = self._data.get(SPANDATA.PROFILER_ID)
        if profiler_id is None:
            return None

        return {
            "profiler_id": profiler_id,
        }

    def update_active_thread(self) -> None:
        thread_id, thread_name = get_current_thread_meta()
        self.set_thread(thread_id, thread_name)


class Transaction(Span):
    """The Transaction is the root element that holds all the spans
    for Sentry performance instrumentation.

    :param name: Identifier of the transaction.
        Will show up in the Sentry UI.
    :param parent_sampled: Whether the parent transaction was sampled.
        If True this transaction will be kept, if False it will be discarded.
    :param baggage: The W3C baggage header value.
        (see https://www.w3.org/TR/baggage/)
    :param source: A string describing the source of the transaction name.
        This will be used to determine the transaction's type.
        See https://develop.sentry.dev/sdk/event-payloads/transaction/#transaction-annotations
        for more information. Default "custom".
    :param kwargs: Additional arguments to be passed to the Span constructor.
        See :py:class:`sentry_sdk.tracing.Span` for available arguments.
    """

    __slots__ = (
        "name",
        "source",
        "parent_sampled",
        # used to create baggage value for head SDKs in dynamic sampling
        "sample_rate",
        "_measurements",
        "_contexts",
        "_profile",
        "_continuous_profile",
        "_baggage",
        "_sample_rand",
    )

    def __init__(  # type: ignore[misc]
        self,
        name: str = "",
        parent_sampled: "Optional[bool]" = None,
        baggage: "Optional[Baggage]" = None,
        source: str = TransactionSource.CUSTOM,
        **kwargs: "Unpack[SpanKwargs]",
    ) -> None:
        super().__init__(**kwargs)

        self.name = name
        self.source = source
        self.sample_rate: "Optional[float]" = None
        self.parent_sampled = parent_sampled
        self._measurements: "Dict[str, MeasurementValue]" = {}
        self._contexts: "Dict[str, Any]" = {}
        self._profile: "Optional[Profile]" = None
        self._continuous_profile: "Optional[ContinuousProfile]" = None
        self._baggage = baggage

        baggage_sample_rand = (
            None if self._baggage is None else self._baggage._sample_rand()
        )
        if baggage_sample_rand is not None:
            self._sample_rand = baggage_sample_rand
        else:
            self._sample_rand = _generate_sample_rand(self.trace_id)

    def __repr__(self) -> str:
        return (
            "<%s(name=%r, op=%r, trace_id=%r, span_id=%r, parent_span_id=%r, sampled=%r, source=%r, origin=%r)>"
            % (
                self.__class__.__name__,
                self.name,
                self.op,
                self.trace_id,
                self.span_id,
                self.parent_span_id,
                self.sampled,
                self.source,
                self.origin,
            )
        )

    def _possibly_started(self) -> bool:
        """Returns whether the transaction might have been started.

        If this returns False, we know that the transaction was not started
        with sentry_sdk.start_transaction, and therefore the transaction will
        be discarded.
        """

        # We must explicitly check self.sampled is False since self.sampled can be None
        return self._span_recorder is not None or self.sampled is False

    def __enter__(self) -> "Transaction":
        if not self._possibly_started():
            logger.debug(
                "Transaction was entered without being started with sentry_sdk.start_transaction."
                "The transaction will not be sent to Sentry. To fix, start the transaction by"
                "passing it to sentry_sdk.start_transaction."
            )

        super().__enter__()

        if self._profile is not None:
            self._profile.__enter__()

        return self

    def __exit__(
        self, ty: "Optional[Any]", value: "Optional[Any]", tb: "Optional[Any]"
    ) -> None:
        if self._profile is not None:
            self._profile.__exit__(ty, value, tb)

        if self._continuous_profile is not None:
            self._continuous_profile.stop()

        super().__exit__(ty, value, tb)

    @property
    def containing_transaction(self) -> "Transaction":
        """The root element of the span tree.
        In the case of a transaction it is the transaction itself.
        """

        # Transactions (as spans) belong to themselves (as transactions). This
        # is a getter rather than a regular attribute to avoid having a circular
        # reference.
        return self

    def _get_scope_from_finish_args(
        self,
        scope_arg: "Optional[Union[sentry_sdk.Scope, sentry_sdk.Hub]]",
        hub_arg: "Optional[Union[sentry_sdk.Scope, sentry_sdk.Hub]]",
    ) -> "Optional[sentry_sdk.Scope]":
        """
        Logic to get the scope from the arguments passed to finish. This
        function exists for backwards compatibility with the old finish.

        TODO: Remove this function in the next major version.
        """
        scope_or_hub = scope_arg
        if hub_arg is not None:
            warnings.warn(
                "The `hub` parameter is deprecated. Please use the `scope` parameter, instead.",
                DeprecationWarning,
                stacklevel=3,
            )

            scope_or_hub = hub_arg

        if isinstance(scope_or_hub, sentry_sdk.Hub):
            warnings.warn(
                "Passing a Hub to finish is deprecated. Please pass a Scope, instead.",
                DeprecationWarning,
                stacklevel=3,
            )

            return scope_or_hub.scope

        return scope_or_hub

    def _get_log_representation(self) -> str:
        return "{op}transaction <{name}>".format(
            op=("<" + self.op + "> " if self.op else ""), name=self.name
        )

    def finish(
        self,
        scope: "Optional[sentry_sdk.Scope]" = None,
        end_timestamp: "Optional[Union[float, datetime]]" = None,
        *,
        hub: "Optional[sentry_sdk.Hub]" = None,
    ) -> "Optional[str]":
        """Finishes the transaction and sends it to Sentry.
        All finished spans in the transaction will also be sent to Sentry.

        :param scope: The Scope to use for this transaction.
            If not provided, the current Scope will be used.
        :param end_timestamp: Optional timestamp that should
            be used as timestamp instead of the current time.
        :param hub: The hub to use for this transaction.
            This argument is DEPRECATED. Please use the `scope`
            parameter, instead.

        :return: The event ID if the transaction was sent to Sentry,
            otherwise None.
        """
        if self.timestamp is not None:
            # This transaction is already finished, ignore.
            return None

        # For backwards compatibility, we must handle the case where `scope`
        # or `hub` could both either be a `Scope` or a `Hub`.
        scope: "Optional[sentry_sdk.Scope]" = self._get_scope_from_finish_args(
            scope, hub
        )

        scope = scope or self.scope or sentry_sdk.get_current_scope()
        client = sentry_sdk.get_client()

        if not client.is_active():
            # We have no active client and therefore nowhere to send this transaction.
            return None

        if self._span_recorder is None:
            # Explicit check against False needed because self.sampled might be None
            if self.sampled is False:
                logger.debug("Discarding transaction because sampled = False")
            else:
                logger.debug(
                    "Discarding transaction because it was not started with sentry_sdk.start_transaction"
                )

            # This is not entirely accurate because discards here are not
            # exclusively based on sample rate but also traces sampler, but
            # we handle this the same here.
            if client.transport and has_tracing_enabled(client.options):
                if client.monitor and client.monitor.downsample_factor > 0:
                    reason = "backpressure"
                else:
                    reason = "sample_rate"

                client.transport.record_lost_event(reason, data_category="transaction")

                # Only one span (the transaction itself) is discarded, since we did not record any spans here.
                client.transport.record_lost_event(reason, data_category="span")
            return None

        if not self.name:
            logger.warning(
                "Transaction has no name, falling back to `<unlabeled transaction>`."
            )
            self.name = "<unlabeled transaction>"

        super().finish(scope, end_timestamp)

        status_code = self._data.get(SPANDATA.HTTP_STATUS_CODE)
        if (
            status_code is not None
            and status_code in client.options["trace_ignore_status_codes"]
        ):
            logger.debug(
                "[Tracing] Discarding {transaction_description} because the HTTP status code {status_code} is matched by trace_ignore_status_codes: {trace_ignore_status_codes}".format(
                    transaction_description=self._get_log_representation(),
                    status_code=self._data[SPANDATA.HTTP_STATUS_CODE],
                    trace_ignore_status_codes=client.options[
                        "trace_ignore_status_codes"
                    ],
                )
            )
            if client.transport:
                client.transport.record_lost_event(
                    "event_processor", data_category="transaction"
                )

                num_spans = len(self._span_recorder.spans) + 1
                client.transport.record_lost_event(
                    "event_processor", data_category="span", quantity=num_spans
                )

            self.sampled = False

        if not self.sampled:
            # At this point a `sampled = None` should have already been resolved
            # to a concrete decision.
            if self.sampled is None:
                logger.warning("Discarding transaction without sampling decision.")

            return None

        finished_spans = [
            span.to_json()
            for span in self._span_recorder.spans
            if span.timestamp is not None
        ]

        len_diff = len(self._span_recorder.spans) - len(finished_spans)
        dropped_spans = len_diff + self._span_recorder.dropped_spans

        # we do this to break the circular reference of transaction -> span
        # recorder -> span -> containing transaction (which is where we started)
        # before either the spans or the transaction goes out of scope and has
        # to be garbage collected
        self._span_recorder = None

        contexts = {}
        contexts.update(self._contexts)
        contexts.update({"trace": self.get_trace_context()})
        profile_context = self.get_profile_context()
        if profile_context is not None:
            contexts.update({"profile": profile_context})

        event: "Event" = {
            "type": "transaction",
            "transaction": self.name,
            "transaction_info": {"source": self.source},
            "contexts": contexts,
            "tags": self._tags,
            "timestamp": self.timestamp,
            "start_timestamp": self.start_timestamp,
            "spans": finished_spans,
        }

        if dropped_spans > 0:
            event["_dropped_spans"] = dropped_spans

        if self._profile is not None and self._profile.valid():
            event["profile"] = self._profile
            self._profile = None

        event["measurements"] = self._measurements

        return scope.capture_event(event)

    def set_measurement(
        self, name: str, value: float, unit: "MeasurementUnit" = ""
    ) -> None:
        """
        .. deprecated:: 2.28.0
            This function is deprecated and will be removed in the next major release.
        """

        warnings.warn(
            "`set_measurement()` is deprecated and will be removed in the next major version. Please use `set_data()` instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        self._measurements[name] = {"value": value, "unit": unit}

    def set_context(self, key: str, value: "dict[str, Any]") -> None:
        """Sets a context. Transactions can have multiple contexts
        and they should follow the format described in the "Contexts Interface"
        documentation.

        :param key: The name of the context.
        :param value: The information about the context.
        """
        self._contexts[key] = value

    def set_http_status(self, http_status: int) -> None:
        """Sets the status of the Transaction according to the given HTTP status.

        :param http_status: The HTTP status code."""
        super().set_http_status(http_status)
        self.set_context("response", {"status_code": http_status})

    def to_json(self) -> "Dict[str, Any]":
        """Returns a JSON-compatible representation of the transaction."""
        rv = super().to_json()

        rv["name"] = self.name
        rv["source"] = self.source
        rv["sampled"] = self.sampled

        return rv

    def get_trace_context(self) -> "Any":
        trace_context = super().get_trace_context()

        if self._data:
            trace_context["data"] = self._data

        return trace_context

    def get_baggage(self) -> "Baggage":
        """Returns the :py:class:`~sentry_sdk.tracing_utils.Baggage`
        associated with the Transaction.

        The first time a new baggage with Sentry items is made,
        it will be frozen."""
        if not self._baggage or self._baggage.mutable:
            self._baggage = Baggage.populate_from_transaction(self)

        return self._baggage

    def _set_initial_sampling_decision(
        self, sampling_context: "SamplingContext"
    ) -> None:
        """
        Sets the transaction's sampling decision, according to the following
        precedence rules:

        1. If a sampling decision is passed to `start_transaction`
        (`start_transaction(name: "my transaction", sampled: True)`), that
        decision will be used, regardless of anything else

        2. If `traces_sampler` is defined, its decision will be used. It can
        choose to keep or ignore any parent sampling decision, or use the
        sampling context data to make its own decision or to choose a sample
        rate for the transaction.

        3. If `traces_sampler` is not defined, but there's a parent sampling
        decision, the parent sampling decision will be used.

        4. If `traces_sampler` is not defined and there's no parent sampling
        decision, `traces_sample_rate` will be used.
        """
        client = sentry_sdk.get_client()

        transaction_description = self._get_log_representation()

        # nothing to do if tracing is disabled
        if not has_tracing_enabled(client.options):
            self.sampled = False
            return

        # if the user has forced a sampling decision by passing a `sampled`
        # value when starting the transaction, go with that
        if self.sampled is not None:
            self.sample_rate = float(self.sampled)
            return

        # we would have bailed already if neither `traces_sampler` nor
        # `traces_sample_rate` were defined, so one of these should work; prefer
        # the hook if so
        sample_rate = (
            client.options["traces_sampler"](sampling_context)
            if callable(client.options.get("traces_sampler"))
            # default inheritance behavior
            else (
                sampling_context["parent_sampled"]
                if sampling_context["parent_sampled"] is not None
                else client.options["traces_sample_rate"]
            )
        )

        # Since this is coming from the user (or from a function provided by the
        # user), who knows what we might get. (The only valid values are
        # booleans or numbers between 0 and 1.)
        if not is_valid_sample_rate(sample_rate, source="Tracing"):
            logger.warning(
                "[Tracing] Discarding {transaction_description} because of invalid sample rate.".format(
                    transaction_description=transaction_description,
                )
            )
            self.sampled = False
            return

        self.sample_rate = float(sample_rate)

        if client.monitor:
            self.sample_rate /= 2**client.monitor.downsample_factor

        # if the function returned 0 (or false), or if `traces_sample_rate` is
        # 0, it's a sign the transaction should be dropped
        if not self.sample_rate:
            logger.debug(
                "[Tracing] Discarding {transaction_description} because {reason}".format(
                    transaction_description=transaction_description,
                    reason=(
                        "traces_sampler returned 0 or False"
                        if callable(client.options.get("traces_sampler"))
                        else "traces_sample_rate is set to 0"
                    ),
                )
            )
            self.sampled = False
            return

        # Now we roll the dice.
        self.sampled = self._sample_rand < self.sample_rate

        if self.sampled:
            logger.debug(
                "[Tracing] Starting {transaction_description}".format(
                    transaction_description=transaction_description,
                )
            )
        else:
            logger.debug(
                "[Tracing] Discarding {transaction_description} because it's not included in the random sample (sampling rate = {sample_rate})".format(
                    transaction_description=transaction_description,
                    sample_rate=self.sample_rate,
                )
            )


class NoOpSpan(Span):
    def __repr__(self) -> str:
        return "<%s>" % self.__class__.__name__

    @property
    def containing_transaction(self) -> "Optional[Transaction]":
        return None

    def start_child(
        self, instrumenter: str = INSTRUMENTER.SENTRY, **kwargs: "Any"
    ) -> "NoOpSpan":
        return NoOpSpan()

    def to_traceparent(self) -> str:
        return ""

    def to_baggage(self) -> "Optional[Baggage]":
        return None

    def get_baggage(self) -> "Optional[Baggage]":
        return None

    def iter_headers(self) -> "Iterator[Tuple[str, str]]":
        return iter(())

    def set_tag(self, key: str, value: "Any") -> None:
        pass

    def set_data(self, key: str, value: "Any") -> None:
        pass

    def update_data(self, data: "Dict[str, Any]") -> None:
        pass

    def set_status(self, value: str) -> None:
        pass

    def set_http_status(self, http_status: int) -> None:
        pass

    def is_success(self) -> bool:
        return True

    def to_json(self) -> "Dict[str, Any]":
        return {}

    def get_trace_context(self) -> "Any":
        return {}

    def get_profile_context(self) -> "Any":
        return {}

    def finish(
        self,
        scope: "Optional[sentry_sdk.Scope]" = None,
        end_timestamp: "Optional[Union[float, datetime]]" = None,
        *,
        hub: "Optional[sentry_sdk.Hub]" = None,
    ) -> "Optional[str]":
        """
        The `hub` parameter is deprecated. Please use the `scope` parameter, instead.
        """
        pass

    def set_measurement(
        self, name: str, value: float, unit: "MeasurementUnit" = ""
    ) -> None:
        pass

    def set_context(self, key: str, value: "dict[str, Any]") -> None:
        pass

    def init_span_recorder(self, maxlen: int) -> None:
        pass

    def _set_initial_sampling_decision(
        self, sampling_context: "SamplingContext"
    ) -> None:
        pass


if TYPE_CHECKING:

    @overload
    def trace(
        func: None = None,
        *,
        op: "Optional[str]" = None,
        name: "Optional[str]" = None,
        attributes: "Optional[dict[str, Any]]" = None,
        template: "SPANTEMPLATE" = SPANTEMPLATE.DEFAULT,
    ) -> "Callable[[Callable[P, R]], Callable[P, R]]":
        # Handles: @trace() and @trace(op="custom")
        pass

    @overload
    def trace(func: "Callable[P, R]") -> "Callable[P, R]":
        # Handles: @trace
        pass


def trace(
    func: "Optional[Callable[P, R]]" = None,
    *,
    op: "Optional[str]" = None,
    name: "Optional[str]" = None,
    attributes: "Optional[dict[str, Any]]" = None,
    template: "SPANTEMPLATE" = SPANTEMPLATE.DEFAULT,
) -> "Union[Callable[P, R], Callable[[Callable[P, R]], Callable[P, R]]]":
    """
    Decorator to start a child span around a function call.

    This decorator automatically creates a new span when the decorated function
    is called, and finishes the span when the function returns or raises an exception.

    :param func: The function to trace. When used as a decorator without parentheses,
        this is the function being decorated. When used with parameters (e.g.,
        ``@trace(op="custom")``, this should be None.
    :type func: Callable or None

    :param op: The operation name for the span. This is a high-level description
        of what the span represents (e.g., "http.client", "db.query").
        You can use predefined constants from :py:class:`sentry_sdk.consts.OP`
        or provide your own string. If not provided, a default operation will
        be assigned based on the template.
    :type op: str or None

    :param name: The human-readable name/description for the span. If not provided,
        defaults to the function name. This provides more specific details about
        what the span represents (e.g., "GET /api/users", "process_user_data").
    :type name: str or None

    :param attributes: A dictionary of key-value pairs to add as attributes to the span.
        Attribute values must be strings, integers, floats, or booleans. These
        attributes provide additional context about the span's execution.
    :type attributes: dict[str, Any] or None

    :param template: The type of span to create. This determines what kind of
        span instrumentation and data collection will be applied. Use predefined
        constants from :py:class:`sentry_sdk.consts.SPANTEMPLATE`.
        The default is `SPANTEMPLATE.DEFAULT` which is the right choice for most
        use cases.
    :type template: :py:class:`sentry_sdk.consts.SPANTEMPLATE`

    :returns: When used as ``@trace``, returns the decorated function. When used as
        ``@trace(...)`` with parameters, returns a decorator function.
    :rtype: Callable or decorator function

    Example::

        import sentry_sdk
        from sentry_sdk.consts import OP, SPANTEMPLATE

        # Simple usage with default values
        @sentry_sdk.trace
        def process_data():
            # Function implementation
            pass

        # With custom parameters
        @sentry_sdk.trace(
            op=OP.DB_QUERY,
            name="Get user data",
            attributes={"postgres": True}
        )
        def make_db_query(sql):
            # Function implementation
            pass

        # With a custom template
        @sentry_sdk.trace(template=SPANTEMPLATE.AI_TOOL)
        def calculate_interest_rate(amount, rate, years):
            # Function implementation
            pass
    """
    from sentry_sdk.tracing_utils import create_span_decorator

    decorator = create_span_decorator(
        op=op,
        name=name,
        attributes=attributes,
        template=template,
    )

    if func:
        return decorator(func)
    else:
        return decorator


# Circular imports

from sentry_sdk.tracing_utils import (
    Baggage,
    EnvironHeaders,
    _generate_sample_rand,
    extract_sentrytrace_data,
    has_tracing_enabled,
    maybe_create_breadcrumbs_from_span,
)
