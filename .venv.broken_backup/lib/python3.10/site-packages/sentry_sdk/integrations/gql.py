import sentry_sdk
from sentry_sdk.utils import (
    event_from_exception,
    ensure_integration_enabled,
    parse_version,
)

from sentry_sdk.integrations import _check_minimum_version, DidNotEnable, Integration
from sentry_sdk.scope import should_send_default_pii

try:
    import gql  # type: ignore[import-not-found]
    from graphql import (
        print_ast,
        get_operation_ast,
        DocumentNode,
        VariableDefinitionNode,
    )
    from gql.transport import Transport, AsyncTransport  # type: ignore[import-not-found]
    from gql.transport.exceptions import TransportQueryError  # type: ignore[import-not-found]

    try:
        # gql 4.0+
        from gql import GraphQLRequest
    except ImportError:
        GraphQLRequest = None

except ImportError:
    raise DidNotEnable("gql is not installed")

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any, Dict, Tuple, Union
    from sentry_sdk._types import Event, EventProcessor

    EventDataType = Dict[str, Union[str, Tuple[VariableDefinitionNode, ...]]]


class GQLIntegration(Integration):
    identifier = "gql"

    @staticmethod
    def setup_once() -> None:
        gql_version = parse_version(gql.__version__)
        _check_minimum_version(GQLIntegration, gql_version)

        _patch_execute()


def _data_from_document(document: "DocumentNode") -> "EventDataType":
    try:
        operation_ast = get_operation_ast(document)
        data: "EventDataType" = {"query": print_ast(document)}

        if operation_ast is not None:
            data["variables"] = operation_ast.variable_definitions
            if operation_ast.name is not None:
                data["operationName"] = operation_ast.name.value

        return data
    except (AttributeError, TypeError):
        return dict()


def _transport_method(transport: "Union[Transport, AsyncTransport]") -> str:
    """
    The RequestsHTTPTransport allows defining the HTTP method; all
    other transports use POST.
    """
    try:
        return transport.method
    except AttributeError:
        return "POST"


def _request_info_from_transport(
    transport: "Union[Transport, AsyncTransport, None]",
) -> "Dict[str, str]":
    if transport is None:
        return {}

    request_info = {
        "method": _transport_method(transport),
    }

    try:
        request_info["url"] = transport.url
    except AttributeError:
        pass

    return request_info


def _patch_execute() -> None:
    real_execute = gql.Client.execute

    # Maintain signature for backwards compatibility.
    # gql.Client.execute() accepts a positional-only "request"
    # parameter with version 4.0.0.
    @ensure_integration_enabled(GQLIntegration, real_execute)
    def sentry_patched_execute(
        self: "gql.Client",
        document: "DocumentNode",
        *args: "Any",
        **kwargs: "Any",
    ) -> "Any":
        scope = sentry_sdk.get_isolation_scope()
        # document is a gql.GraphQLRequest with gql v4.0.0.
        scope.add_event_processor(_make_gql_event_processor(self, document))

        try:
            # document is a gql.GraphQLRequest with gql v4.0.0.
            return real_execute(self, document, *args, **kwargs)
        except TransportQueryError as e:
            event, hint = event_from_exception(
                e,
                client_options=sentry_sdk.get_client().options,
                mechanism={"type": "gql", "handled": False},
            )

            sentry_sdk.capture_event(event, hint)
            raise e

    gql.Client.execute = sentry_patched_execute


def _make_gql_event_processor(
    client: "gql.Client", document_or_request: "Union[DocumentNode, gql.GraphQLRequest]"
) -> "EventProcessor":
    def processor(event: "Event", hint: "dict[str, Any]") -> "Event":
        try:
            errors = hint["exc_info"][1].errors
        except (AttributeError, KeyError):
            errors = None

        request = event.setdefault("request", {})
        request.update(
            {
                "api_target": "graphql",
                **_request_info_from_transport(client.transport),
            }
        )

        if should_send_default_pii():
            if GraphQLRequest is not None and isinstance(
                document_or_request, GraphQLRequest
            ):
                # In v4.0.0, gql moved to using GraphQLRequest instead of
                # DocumentNode in execute
                # https://github.com/graphql-python/gql/pull/556
                document = document_or_request.document
            else:
                document = document_or_request

            request["data"] = _data_from_document(document)
            contexts = event.setdefault("contexts", {})
            response = contexts.setdefault("response", {})
            response.update(
                {
                    "data": {"errors": errors},
                    "type": response,
                }
            )

        return event

    return processor
