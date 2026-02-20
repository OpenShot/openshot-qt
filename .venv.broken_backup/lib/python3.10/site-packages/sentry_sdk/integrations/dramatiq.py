import json

import sentry_sdk
from sentry_sdk.consts import OP, SPANSTATUS
from sentry_sdk.api import continue_trace, get_baggage, get_traceparent
from sentry_sdk.integrations import Integration, DidNotEnable
from sentry_sdk.integrations._wsgi_common import request_body_within_bounds
from sentry_sdk.tracing import (
    BAGGAGE_HEADER_NAME,
    SENTRY_TRACE_HEADER_NAME,
    TransactionSource,
)
from sentry_sdk.utils import (
    AnnotatedValue,
    capture_internal_exceptions,
    event_from_exception,
)
from typing import TypeVar

R = TypeVar("R")

try:
    from dramatiq.broker import Broker
    from dramatiq.middleware import Middleware, default_middleware
    from dramatiq.errors import Retry
    from dramatiq.message import Message
except ImportError:
    raise DidNotEnable("Dramatiq is not installed")

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any, Callable, Dict, Optional, Union
    from sentry_sdk._types import Event, Hint


class DramatiqIntegration(Integration):
    """
    Dramatiq integration for Sentry

    Please make sure that you call `sentry_sdk.init` *before* initializing
    your broker, as it monkey patches `Broker.__init__`.

    This integration was originally developed and maintained
    by https://github.com/jacobsvante and later donated to the Sentry
    project.
    """

    identifier = "dramatiq"
    origin = f"auto.queue.{identifier}"

    @staticmethod
    def setup_once() -> None:
        _patch_dramatiq_broker()


def _patch_dramatiq_broker() -> None:
    original_broker__init__ = Broker.__init__

    def sentry_patched_broker__init__(
        self: "Broker", *args: "Any", **kw: "Any"
    ) -> None:
        integration = sentry_sdk.get_client().get_integration(DramatiqIntegration)

        try:
            middleware = kw.pop("middleware")
        except KeyError:
            # Unfortunately Broker and StubBroker allows middleware to be
            # passed in as positional arguments, whilst RabbitmqBroker and
            # RedisBroker does not.
            if len(args) == 1:
                middleware = args[0]
                args = []  # type: ignore
            else:
                middleware = None

        if middleware is None:
            middleware = list(m() for m in default_middleware)
        else:
            middleware = list(middleware)

        if integration is not None:
            middleware = [m for m in middleware if not isinstance(m, SentryMiddleware)]
            middleware.insert(0, SentryMiddleware())

        kw["middleware"] = middleware
        original_broker__init__(self, *args, **kw)

    Broker.__init__ = sentry_patched_broker__init__


class SentryMiddleware(Middleware):  # type: ignore[misc]
    """
    A Dramatiq middleware that automatically captures and sends
    exceptions to Sentry.

    This is automatically added to every instantiated broker via the
    DramatiqIntegration.
    """

    SENTRY_HEADERS_NAME = "_sentry_headers"

    def before_enqueue(
        self, broker: "Broker", message: "Message[R]", delay: int
    ) -> None:
        integration = sentry_sdk.get_client().get_integration(DramatiqIntegration)
        if integration is None:
            return

        message.options[self.SENTRY_HEADERS_NAME] = {
            BAGGAGE_HEADER_NAME: get_baggage(),
            SENTRY_TRACE_HEADER_NAME: get_traceparent(),
        }

    def before_process_message(self, broker: "Broker", message: "Message[R]") -> None:
        integration = sentry_sdk.get_client().get_integration(DramatiqIntegration)
        if integration is None:
            return

        message._scope_manager = sentry_sdk.isolation_scope()
        scope = message._scope_manager.__enter__()
        scope.clear_breadcrumbs()
        scope.set_extra("dramatiq_message_id", message.message_id)
        scope.add_event_processor(_make_message_event_processor(message, integration))

        sentry_headers = message.options.get(self.SENTRY_HEADERS_NAME) or {}
        if "retries" in message.options:
            # start new trace in case of retrying
            sentry_headers = {}

        transaction = continue_trace(
            sentry_headers,
            name=message.actor_name,
            op=OP.QUEUE_TASK_DRAMATIQ,
            source=TransactionSource.TASK,
            origin=DramatiqIntegration.origin,
        )
        transaction.set_status(SPANSTATUS.OK)
        sentry_sdk.start_transaction(
            transaction,
            name=message.actor_name,
            op=OP.QUEUE_TASK_DRAMATIQ,
            source=TransactionSource.TASK,
        )
        transaction.__enter__()

    def after_process_message(
        self,
        broker: "Broker",
        message: "Message[R]",
        *,
        result: "Optional[Any]" = None,
        exception: "Optional[Exception]" = None,
    ) -> None:
        integration = sentry_sdk.get_client().get_integration(DramatiqIntegration)
        if integration is None:
            return

        actor = broker.get_actor(message.actor_name)
        throws = message.options.get("throws") or actor.options.get("throws")

        scope_manager = message._scope_manager
        transaction = sentry_sdk.get_current_scope().transaction
        if not transaction:
            return None

        is_event_capture_required = (
            exception is not None
            and not (throws and isinstance(exception, throws))
            and not isinstance(exception, Retry)
        )
        if not is_event_capture_required:
            # normal transaction finish
            transaction.__exit__(None, None, None)
            scope_manager.__exit__(None, None, None)
            return

        event, hint = event_from_exception(
            exception,  # type: ignore[arg-type]
            client_options=sentry_sdk.get_client().options,
            mechanism={
                "type": DramatiqIntegration.identifier,
                "handled": False,
            },
        )
        sentry_sdk.capture_event(event, hint=hint)
        # transaction error
        transaction.__exit__(type(exception), exception, None)
        scope_manager.__exit__(type(exception), exception, None)


def _make_message_event_processor(
    message: "Message[R]", integration: "DramatiqIntegration"
) -> "Callable[[Event, Hint], Optional[Event]]":
    def inner(event: "Event", hint: "Hint") -> "Optional[Event]":
        with capture_internal_exceptions():
            DramatiqMessageExtractor(message).extract_into_event(event)

        return event

    return inner


class DramatiqMessageExtractor:
    def __init__(self, message: "Message[R]") -> None:
        self.message_data = dict(message.asdict())

    def content_length(self) -> int:
        return len(json.dumps(self.message_data))

    def extract_into_event(self, event: "Event") -> None:
        client = sentry_sdk.get_client()
        if not client.is_active():
            return

        contexts = event.setdefault("contexts", {})
        request_info = contexts.setdefault("dramatiq", {})
        request_info["type"] = "dramatiq"

        data: "Optional[Union[AnnotatedValue, Dict[str, Any]]]" = None
        if not request_body_within_bounds(client, self.content_length()):
            data = AnnotatedValue.removed_because_over_size_limit()
        else:
            data = self.message_data

        request_info["data"] = data
