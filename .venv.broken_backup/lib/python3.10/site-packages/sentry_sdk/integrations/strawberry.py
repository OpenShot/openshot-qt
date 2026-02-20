import functools
import hashlib
import warnings
from inspect import isawaitable

import sentry_sdk
from sentry_sdk.consts import OP
from sentry_sdk.integrations import _check_minimum_version, Integration, DidNotEnable
from sentry_sdk.integrations.logging import ignore_logger
from sentry_sdk.scope import should_send_default_pii
from sentry_sdk.tracing import TransactionSource
from sentry_sdk.utils import (
    capture_internal_exceptions,
    ensure_integration_enabled,
    event_from_exception,
    logger,
    package_version,
    _get_installed_modules,
)

try:
    from functools import cached_property
except ImportError:
    # The strawberry integration requires Python 3.8+. functools.cached_property
    # was added in 3.8, so this check is technically not needed, but since this
    # is an auto-enabling integration, we might get to executing this import in
    # lower Python versions, so we need to deal with it.
    raise DidNotEnable("strawberry-graphql integration requires Python 3.8 or newer")

try:
    from strawberry import Schema
    from strawberry.extensions import SchemaExtension
    from strawberry.extensions.tracing.utils import (
        should_skip_tracing as strawberry_should_skip_tracing,
    )
    from strawberry.http import async_base_view, sync_base_view
except ImportError:
    raise DidNotEnable("strawberry-graphql is not installed")

try:
    from strawberry.extensions.tracing import (
        SentryTracingExtension as StrawberrySentryAsyncExtension,
        SentryTracingExtensionSync as StrawberrySentrySyncExtension,
    )
except ImportError:
    StrawberrySentryAsyncExtension = None
    StrawberrySentrySyncExtension = None

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any, Callable, Generator, List, Optional
    from graphql import GraphQLError, GraphQLResolveInfo
    from strawberry.http import GraphQLHTTPResponse
    from strawberry.types import ExecutionContext
    from sentry_sdk._types import Event, EventProcessor


ignore_logger("strawberry.execution")


class StrawberryIntegration(Integration):
    identifier = "strawberry"
    origin = f"auto.graphql.{identifier}"

    def __init__(self, async_execution: "Optional[bool]" = None) -> None:
        if async_execution not in (None, False, True):
            raise ValueError(
                'Invalid value for async_execution: "{}" (must be bool)'.format(
                    async_execution
                )
            )
        self.async_execution = async_execution

    @staticmethod
    def setup_once() -> None:
        version = package_version("strawberry-graphql")
        _check_minimum_version(StrawberryIntegration, version, "strawberry-graphql")

        _patch_schema_init()
        _patch_views()


def _patch_schema_init() -> None:
    old_schema_init = Schema.__init__

    @functools.wraps(old_schema_init)
    def _sentry_patched_schema_init(
        self: "Schema", *args: "Any", **kwargs: "Any"
    ) -> None:
        integration = sentry_sdk.get_client().get_integration(StrawberryIntegration)
        if integration is None:
            return old_schema_init(self, *args, **kwargs)

        extensions = kwargs.get("extensions") or []

        should_use_async_extension: "Optional[bool]" = None
        if integration.async_execution is not None:
            should_use_async_extension = integration.async_execution
        else:
            # try to figure it out ourselves
            should_use_async_extension = _guess_if_using_async(extensions)

            if should_use_async_extension is None:
                warnings.warn(
                    "Assuming strawberry is running sync. If not, initialize the integration as StrawberryIntegration(async_execution=True).",
                    stacklevel=2,
                )
                should_use_async_extension = False

        # remove the built in strawberry sentry extension, if present
        extensions = [
            extension
            for extension in extensions
            if extension
            not in (StrawberrySentryAsyncExtension, StrawberrySentrySyncExtension)
        ]

        # add our extension
        extensions.append(
            SentryAsyncExtension if should_use_async_extension else SentrySyncExtension
        )

        kwargs["extensions"] = extensions

        return old_schema_init(self, *args, **kwargs)

    Schema.__init__ = _sentry_patched_schema_init  # type: ignore[method-assign]


class SentryAsyncExtension(SchemaExtension):
    def __init__(
        self: "Any",
        *,
        execution_context: "Optional[ExecutionContext]" = None,
    ) -> None:
        if execution_context:
            self.execution_context = execution_context

    @cached_property
    def _resource_name(self) -> str:
        query_hash = self.hash_query(self.execution_context.query)  # type: ignore

        if self.execution_context.operation_name:
            return "{}:{}".format(self.execution_context.operation_name, query_hash)

        return query_hash

    def hash_query(self, query: str) -> str:
        return hashlib.md5(query.encode("utf-8")).hexdigest()

    def on_operation(self) -> "Generator[None, None, None]":
        self._operation_name = self.execution_context.operation_name

        operation_type = "query"
        op = OP.GRAPHQL_QUERY

        if self.execution_context.query is None:
            self.execution_context.query = ""

        if self.execution_context.query.strip().startswith("mutation"):
            operation_type = "mutation"
            op = OP.GRAPHQL_MUTATION
        elif self.execution_context.query.strip().startswith("subscription"):
            operation_type = "subscription"
            op = OP.GRAPHQL_SUBSCRIPTION

        description = operation_type
        if self._operation_name:
            description += " {}".format(self._operation_name)

        sentry_sdk.add_breadcrumb(
            category="graphql.operation",
            data={
                "operation_name": self._operation_name,
                "operation_type": operation_type,
            },
        )

        scope = sentry_sdk.get_isolation_scope()
        event_processor = _make_request_event_processor(self.execution_context)
        scope.add_event_processor(event_processor)

        span = sentry_sdk.get_current_span()
        if span:
            self.graphql_span = span.start_child(
                op=op,
                name=description,
                origin=StrawberryIntegration.origin,
            )
        else:
            self.graphql_span = sentry_sdk.start_span(
                op=op,
                name=description,
                origin=StrawberryIntegration.origin,
            )

        self.graphql_span.set_data("graphql.operation.type", operation_type)
        self.graphql_span.set_data("graphql.operation.name", self._operation_name)
        self.graphql_span.set_data("graphql.document", self.execution_context.query)
        self.graphql_span.set_data("graphql.resource_name", self._resource_name)

        yield

        transaction = self.graphql_span.containing_transaction
        if transaction and self.execution_context.operation_name:
            transaction.name = self.execution_context.operation_name
            transaction.source = TransactionSource.COMPONENT
            transaction.op = op

        self.graphql_span.finish()

    def on_validate(self) -> "Generator[None, None, None]":
        self.validation_span = self.graphql_span.start_child(
            op=OP.GRAPHQL_VALIDATE,
            name="validation",
            origin=StrawberryIntegration.origin,
        )

        yield

        self.validation_span.finish()

    def on_parse(self) -> "Generator[None, None, None]":
        self.parsing_span = self.graphql_span.start_child(
            op=OP.GRAPHQL_PARSE,
            name="parsing",
            origin=StrawberryIntegration.origin,
        )

        yield

        self.parsing_span.finish()

    def should_skip_tracing(
        self,
        _next: "Callable[[Any, GraphQLResolveInfo, Any, Any], Any]",
        info: "GraphQLResolveInfo",
    ) -> bool:
        return strawberry_should_skip_tracing(_next, info)

    async def _resolve(
        self,
        _next: "Callable[[Any, GraphQLResolveInfo, Any, Any], Any]",
        root: "Any",
        info: "GraphQLResolveInfo",
        *args: str,
        **kwargs: "Any",
    ) -> "Any":
        result = _next(root, info, *args, **kwargs)

        if isawaitable(result):
            result = await result

        return result

    async def resolve(
        self,
        _next: "Callable[[Any, GraphQLResolveInfo, Any, Any], Any]",
        root: "Any",
        info: "GraphQLResolveInfo",
        *args: str,
        **kwargs: "Any",
    ) -> "Any":
        if self.should_skip_tracing(_next, info):
            return await self._resolve(_next, root, info, *args, **kwargs)

        field_path = "{}.{}".format(info.parent_type, info.field_name)

        with self.graphql_span.start_child(
            op=OP.GRAPHQL_RESOLVE,
            name="resolving {}".format(field_path),
            origin=StrawberryIntegration.origin,
        ) as span:
            span.set_data("graphql.field_name", info.field_name)
            span.set_data("graphql.parent_type", info.parent_type.name)
            span.set_data("graphql.field_path", field_path)
            span.set_data("graphql.path", ".".join(map(str, info.path.as_list())))

            return await self._resolve(_next, root, info, *args, **kwargs)


class SentrySyncExtension(SentryAsyncExtension):
    def resolve(
        self,
        _next: "Callable[[Any, Any, Any, Any], Any]",
        root: "Any",
        info: "GraphQLResolveInfo",
        *args: str,
        **kwargs: "Any",
    ) -> "Any":
        if self.should_skip_tracing(_next, info):
            return _next(root, info, *args, **kwargs)

        field_path = "{}.{}".format(info.parent_type, info.field_name)

        with self.graphql_span.start_child(
            op=OP.GRAPHQL_RESOLVE,
            name="resolving {}".format(field_path),
            origin=StrawberryIntegration.origin,
        ) as span:
            span.set_data("graphql.field_name", info.field_name)
            span.set_data("graphql.parent_type", info.parent_type.name)
            span.set_data("graphql.field_path", field_path)
            span.set_data("graphql.path", ".".join(map(str, info.path.as_list())))

            return _next(root, info, *args, **kwargs)


def _patch_views() -> None:
    old_async_view_handle_errors = async_base_view.AsyncBaseHTTPView._handle_errors
    old_sync_view_handle_errors = sync_base_view.SyncBaseHTTPView._handle_errors

    def _sentry_patched_async_view_handle_errors(
        self: "Any", errors: "List[GraphQLError]", response_data: "GraphQLHTTPResponse"
    ) -> None:
        old_async_view_handle_errors(self, errors, response_data)
        _sentry_patched_handle_errors(self, errors, response_data)

    def _sentry_patched_sync_view_handle_errors(
        self: "Any", errors: "List[GraphQLError]", response_data: "GraphQLHTTPResponse"
    ) -> None:
        old_sync_view_handle_errors(self, errors, response_data)
        _sentry_patched_handle_errors(self, errors, response_data)

    @ensure_integration_enabled(StrawberryIntegration)
    def _sentry_patched_handle_errors(
        self: "Any", errors: "List[GraphQLError]", response_data: "GraphQLHTTPResponse"
    ) -> None:
        if not errors:
            return

        scope = sentry_sdk.get_isolation_scope()
        event_processor = _make_response_event_processor(response_data)
        scope.add_event_processor(event_processor)

        with capture_internal_exceptions():
            for error in errors:
                event, hint = event_from_exception(
                    error,
                    client_options=sentry_sdk.get_client().options,
                    mechanism={
                        "type": StrawberryIntegration.identifier,
                        "handled": False,
                    },
                )
                sentry_sdk.capture_event(event, hint=hint)

    async_base_view.AsyncBaseHTTPView._handle_errors = (  # type: ignore[method-assign]
        _sentry_patched_async_view_handle_errors
    )
    sync_base_view.SyncBaseHTTPView._handle_errors = (  # type: ignore[method-assign]
        _sentry_patched_sync_view_handle_errors
    )


def _make_request_event_processor(
    execution_context: "ExecutionContext",
) -> "EventProcessor":
    def inner(event: "Event", hint: "dict[str, Any]") -> "Event":
        with capture_internal_exceptions():
            if should_send_default_pii():
                request_data = event.setdefault("request", {})
                request_data["api_target"] = "graphql"

                if not request_data.get("data"):
                    data: "dict[str, Any]" = {"query": execution_context.query}
                    if execution_context.variables:
                        data["variables"] = execution_context.variables
                    if execution_context.operation_name:
                        data["operationName"] = execution_context.operation_name

                    request_data["data"] = data

            else:
                try:
                    del event["request"]["data"]
                except (KeyError, TypeError):
                    pass

        return event

    return inner


def _make_response_event_processor(
    response_data: "GraphQLHTTPResponse",
) -> "EventProcessor":
    def inner(event: "Event", hint: "dict[str, Any]") -> "Event":
        with capture_internal_exceptions():
            if should_send_default_pii():
                contexts = event.setdefault("contexts", {})
                contexts["response"] = {"data": response_data}

        return event

    return inner


def _guess_if_using_async(extensions: "List[SchemaExtension]") -> "Optional[bool]":
    if StrawberrySentryAsyncExtension in extensions:
        return True
    elif StrawberrySentrySyncExtension in extensions:
        return False

    return None
