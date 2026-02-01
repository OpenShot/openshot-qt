import inspect
import warnings
from contextlib import contextmanager

from sentry_sdk import tracing_utils, Client
from sentry_sdk._init_implementation import init
from sentry_sdk.consts import INSTRUMENTER
from sentry_sdk.scope import Scope, _ScopeManager, new_scope, isolation_scope
from sentry_sdk.tracing import NoOpSpan, Transaction, trace
from sentry_sdk.crons import monitor

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

    from typing import Any
    from typing import Dict
    from typing import Generator
    from typing import Optional
    from typing import overload
    from typing import Callable
    from typing import TypeVar
    from typing import ContextManager
    from typing import Union

    from typing_extensions import Unpack

    from sentry_sdk.client import BaseClient
    from sentry_sdk._types import (
        Event,
        Hint,
        Breadcrumb,
        BreadcrumbHint,
        ExcInfo,
        MeasurementUnit,
        LogLevelStr,
        SamplingContext,
    )
    from sentry_sdk.tracing import Span, TransactionKwargs

    T = TypeVar("T")
    F = TypeVar("F", bound=Callable[..., Any])
else:

    def overload(x: "T") -> "T":
        return x


# When changing this, update __all__ in __init__.py too
__all__ = [
    "init",
    "add_attachment",
    "add_breadcrumb",
    "capture_event",
    "capture_exception",
    "capture_message",
    "configure_scope",
    "continue_trace",
    "flush",
    "get_baggage",
    "get_client",
    "get_global_scope",
    "get_isolation_scope",
    "get_current_scope",
    "get_current_span",
    "get_traceparent",
    "is_initialized",
    "isolation_scope",
    "last_event_id",
    "new_scope",
    "push_scope",
    "set_context",
    "set_extra",
    "set_level",
    "set_measurement",
    "set_tag",
    "set_tags",
    "set_user",
    "start_span",
    "start_transaction",
    "trace",
    "monitor",
    "start_session",
    "end_session",
    "set_transaction_name",
    "update_current_span",
]


def scopemethod(f: "F") -> "F":
    f.__doc__ = "%s\n\n%s" % (
        "Alias for :py:meth:`sentry_sdk.Scope.%s`" % f.__name__,
        inspect.getdoc(getattr(Scope, f.__name__)),
    )
    return f


def clientmethod(f: "F") -> "F":
    f.__doc__ = "%s\n\n%s" % (
        "Alias for :py:meth:`sentry_sdk.Client.%s`" % f.__name__,
        inspect.getdoc(getattr(Client, f.__name__)),
    )
    return f


@scopemethod
def get_client() -> "BaseClient":
    return Scope.get_client()


def is_initialized() -> bool:
    """
    .. versionadded:: 2.0.0

    Returns whether Sentry has been initialized or not.

    If a client is available and the client is active
    (meaning it is configured to send data) then
    Sentry is initialized.
    """
    return get_client().is_active()


@scopemethod
def get_global_scope() -> "Scope":
    return Scope.get_global_scope()


@scopemethod
def get_isolation_scope() -> "Scope":
    return Scope.get_isolation_scope()


@scopemethod
def get_current_scope() -> "Scope":
    return Scope.get_current_scope()


@scopemethod
def last_event_id() -> "Optional[str]":
    """
    See :py:meth:`sentry_sdk.Scope.last_event_id` documentation regarding
    this method's limitations.
    """
    return Scope.last_event_id()


@scopemethod
def capture_event(
    event: "Event",
    hint: "Optional[Hint]" = None,
    scope: "Optional[Any]" = None,
    **scope_kwargs: "Any",
) -> "Optional[str]":
    return get_current_scope().capture_event(event, hint, scope=scope, **scope_kwargs)


@scopemethod
def capture_message(
    message: str,
    level: "Optional[LogLevelStr]" = None,
    scope: "Optional[Any]" = None,
    **scope_kwargs: "Any",
) -> "Optional[str]":
    return get_current_scope().capture_message(
        message, level, scope=scope, **scope_kwargs
    )


@scopemethod
def capture_exception(
    error: "Optional[Union[BaseException, ExcInfo]]" = None,
    scope: "Optional[Any]" = None,
    **scope_kwargs: "Any",
) -> "Optional[str]":
    return get_current_scope().capture_exception(error, scope=scope, **scope_kwargs)


@scopemethod
def add_attachment(
    bytes: "Union[None, bytes, Callable[[], bytes]]" = None,
    filename: "Optional[str]" = None,
    path: "Optional[str]" = None,
    content_type: "Optional[str]" = None,
    add_to_transactions: bool = False,
) -> None:
    return get_isolation_scope().add_attachment(
        bytes, filename, path, content_type, add_to_transactions
    )


@scopemethod
def add_breadcrumb(
    crumb: "Optional[Breadcrumb]" = None,
    hint: "Optional[BreadcrumbHint]" = None,
    **kwargs: "Any",
) -> None:
    return get_isolation_scope().add_breadcrumb(crumb, hint, **kwargs)


@overload
def configure_scope() -> "ContextManager[Scope]":
    pass


@overload
def configure_scope(  # noqa: F811
    callback: "Callable[[Scope], None]",
) -> None:
    pass


def configure_scope(  # noqa: F811
    callback: "Optional[Callable[[Scope], None]]" = None,
) -> "Optional[ContextManager[Scope]]":
    """
    Reconfigures the scope.

    :param callback: If provided, call the callback with the current scope.

    :returns: If no callback is provided, returns a context manager that returns the scope.
    """
    warnings.warn(
        "sentry_sdk.configure_scope is deprecated and will be removed in the next major version. "
        "Please consult our migration guide to learn how to migrate to the new API: "
        "https://docs.sentry.io/platforms/python/migration/1.x-to-2.x#scope-configuring",
        DeprecationWarning,
        stacklevel=2,
    )

    scope = get_isolation_scope()
    scope.generate_propagation_context()

    if callback is not None:
        # TODO: used to return None when client is None. Check if this changes behavior.
        callback(scope)

        return None

    @contextmanager
    def inner() -> "Generator[Scope, None, None]":
        yield scope

    return inner()


@overload
def push_scope() -> "ContextManager[Scope]":
    pass


@overload
def push_scope(  # noqa: F811
    callback: "Callable[[Scope], None]",
) -> None:
    pass


def push_scope(  # noqa: F811
    callback: "Optional[Callable[[Scope], None]]" = None,
) -> "Optional[ContextManager[Scope]]":
    """
    Pushes a new layer on the scope stack.

    :param callback: If provided, this method pushes a scope, calls
        `callback`, and pops the scope again.

    :returns: If no `callback` is provided, a context manager that should
        be used to pop the scope again.
    """
    warnings.warn(
        "sentry_sdk.push_scope is deprecated and will be removed in the next major version. "
        "Please consult our migration guide to learn how to migrate to the new API: "
        "https://docs.sentry.io/platforms/python/migration/1.x-to-2.x#scope-pushing",
        DeprecationWarning,
        stacklevel=2,
    )

    if callback is not None:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            with push_scope() as scope:
                callback(scope)
        return None

    return _ScopeManager()


@scopemethod
def set_tag(key: str, value: "Any") -> None:
    return get_isolation_scope().set_tag(key, value)


@scopemethod
def set_tags(tags: "Mapping[str, object]") -> None:
    return get_isolation_scope().set_tags(tags)


@scopemethod
def set_context(key: str, value: "Dict[str, Any]") -> None:
    return get_isolation_scope().set_context(key, value)


@scopemethod
def set_extra(key: str, value: "Any") -> None:
    return get_isolation_scope().set_extra(key, value)


@scopemethod
def set_user(value: "Optional[Dict[str, Any]]") -> None:
    return get_isolation_scope().set_user(value)


@scopemethod
def set_level(value: "LogLevelStr") -> None:
    return get_isolation_scope().set_level(value)


@clientmethod
def flush(
    timeout: "Optional[float]" = None,
    callback: "Optional[Callable[[int, float], None]]" = None,
) -> None:
    return get_client().flush(timeout=timeout, callback=callback)


@scopemethod
def start_span(
    **kwargs: "Any",
) -> "Span":
    return get_current_scope().start_span(**kwargs)


@scopemethod
def start_transaction(
    transaction: "Optional[Transaction]" = None,
    instrumenter: str = INSTRUMENTER.SENTRY,
    custom_sampling_context: "Optional[SamplingContext]" = None,
    **kwargs: "Unpack[TransactionKwargs]",
) -> "Union[Transaction, NoOpSpan]":
    """
    Start and return a transaction on the current scope.

    Start an existing transaction if given, otherwise create and start a new
    transaction with kwargs.

    This is the entry point to manual tracing instrumentation.

    A tree structure can be built by adding child spans to the transaction,
    and child spans to other spans. To start a new child span within the
    transaction or any span, call the respective `.start_child()` method.

    Every child span must be finished before the transaction is finished,
    otherwise the unfinished spans are discarded.

    When used as context managers, spans and transactions are automatically
    finished at the end of the `with` block. If not using context managers,
    call the `.finish()` method.

    When the transaction is finished, it will be sent to Sentry with all its
    finished child spans.

    :param transaction: The transaction to start. If omitted, we create and
        start a new transaction.
    :param instrumenter: This parameter is meant for internal use only. It
        will be removed in the next major version.
    :param custom_sampling_context: The transaction's custom sampling context.
    :param kwargs: Optional keyword arguments to be passed to the Transaction
        constructor. See :py:class:`sentry_sdk.tracing.Transaction` for
        available arguments.
    """
    return get_current_scope().start_transaction(
        transaction, instrumenter, custom_sampling_context, **kwargs
    )


def set_measurement(name: str, value: float, unit: "MeasurementUnit" = "") -> None:
    """
    .. deprecated:: 2.28.0
        This function is deprecated and will be removed in the next major release.
    """
    transaction = get_current_scope().transaction
    if transaction is not None:
        transaction.set_measurement(name, value, unit)


def get_current_span(scope: "Optional[Scope]" = None) -> "Optional[Span]":
    """
    Returns the currently active span if there is one running, otherwise `None`
    """
    return tracing_utils.get_current_span(scope)


def get_traceparent() -> "Optional[str]":
    """
    Returns the traceparent either from the active span or from the scope.
    """
    return get_current_scope().get_traceparent()


def get_baggage() -> "Optional[str]":
    """
    Returns Baggage either from the active span or from the scope.
    """
    baggage = get_current_scope().get_baggage()
    if baggage is not None:
        return baggage.serialize()

    return None


def continue_trace(
    environ_or_headers: "Dict[str, Any]",
    op: "Optional[str]" = None,
    name: "Optional[str]" = None,
    source: "Optional[str]" = None,
    origin: str = "manual",
) -> "Transaction":
    """
    Sets the propagation context from environment or headers and returns a transaction.
    """
    return get_isolation_scope().continue_trace(
        environ_or_headers, op, name, source, origin
    )


@scopemethod
def start_session(
    session_mode: str = "application",
) -> None:
    return get_isolation_scope().start_session(session_mode=session_mode)


@scopemethod
def end_session() -> None:
    return get_isolation_scope().end_session()


@scopemethod
def set_transaction_name(name: str, source: "Optional[str]" = None) -> None:
    return get_current_scope().set_transaction_name(name, source)


def update_current_span(
    op: "Optional[str]" = None,
    name: "Optional[str]" = None,
    attributes: "Optional[dict[str, Union[str, int, float, bool]]]" = None,
    data: "Optional[dict[str, Any]]" = None,
) -> None:
    """
    Update the current active span with the provided parameters.

    This function allows you to modify properties of the currently active span.
    If no span is currently active, this function will do nothing.

    :param op: The operation name for the span. This is a high-level description
        of what the span represents (e.g., "http.client", "db.query").
        You can use predefined constants from :py:class:`sentry_sdk.consts.OP`
        or provide your own string. If not provided, the span's operation will
        remain unchanged.
    :type op: str or None

    :param name: The human-readable name/description for the span. This provides
        more specific details about what the span represents (e.g., "GET /api/users",
        "SELECT * FROM users"). If not provided, the span's name will remain unchanged.
    :type name: str or None

    :param data: A dictionary of key-value pairs to add as data to the span. This
        data will be merged with any existing span data. If not provided,
        no data will be added.

        .. deprecated:: 2.35.0
            Use ``attributes`` instead. The ``data`` parameter will be removed
            in a future version.
    :type data: dict[str, Union[str, int, float, bool]] or None

    :param attributes: A dictionary of key-value pairs to add as attributes to the span.
        Attribute values must be strings, integers, floats, or booleans. These
        attributes will be merged with any existing span data. If not provided,
        no attributes will be added.
    :type attributes: dict[str, Union[str, int, float, bool]] or None

    :returns: None

    .. versionadded:: 2.35.0

    Example::

        import sentry_sdk
        from sentry_sdk.consts import OP

        sentry_sdk.update_current_span(
            op=OP.FUNCTION,
            name="process_user_data",
            attributes={"user_id": 123, "batch_size": 50}
        )
    """
    current_span = get_current_span()

    if current_span is None:
        return

    if op is not None:
        current_span.op = op

    if name is not None:
        # internally it is still description
        current_span.description = name

    if data is not None and attributes is not None:
        raise ValueError(
            "Cannot provide both `data` and `attributes`. Please use only `attributes`."
        )

    if data is not None:
        warnings.warn(
            "The `data` parameter is deprecated. Please use `attributes` instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        attributes = data

    if attributes is not None:
        current_span.update_data(attributes)
