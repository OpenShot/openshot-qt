from contextlib import asynccontextmanager
from functools import wraps

import sentry_sdk
from sentry_sdk.integrations import DidNotEnable

from ..spans import (
    ai_client_span,
    update_ai_client_span,
)

try:
    from pydantic_ai._agent_graph import ModelRequestNode  # type: ignore
except ImportError:
    raise DidNotEnable("pydantic-ai not installed")

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any, Callable


def _extract_span_data(node: "Any", ctx: "Any") -> "tuple[list[Any], Any, Any]":
    """Extract common data needed for creating chat spans.

    Returns:
        Tuple of (messages, model, model_settings)
    """
    # Extract model and settings from context
    model = None
    model_settings = None
    if hasattr(ctx, "deps"):
        model = getattr(ctx.deps, "model", None)
        model_settings = getattr(ctx.deps, "model_settings", None)

    # Build full message list: history + current request
    messages = []
    if hasattr(ctx, "state") and hasattr(ctx.state, "message_history"):
        messages.extend(ctx.state.message_history)

    current_request = getattr(node, "request", None)
    if current_request:
        messages.append(current_request)

    return messages, model, model_settings


def _patch_graph_nodes() -> None:
    """
    Patches the graph node execution to create appropriate spans.

    ModelRequestNode -> Creates ai_client span for model requests
    CallToolsNode -> Handles tool calls (spans created in tool patching)
    """

    # Patch ModelRequestNode to create ai_client spans
    original_model_request_run = ModelRequestNode.run

    @wraps(original_model_request_run)
    async def wrapped_model_request_run(self: "Any", ctx: "Any") -> "Any":
        messages, model, model_settings = _extract_span_data(self, ctx)

        with ai_client_span(messages, None, model, model_settings) as span:
            result = await original_model_request_run(self, ctx)

            # Extract response from result if available
            model_response = None
            if hasattr(result, "model_response"):
                model_response = result.model_response

            update_ai_client_span(span, model_response)
            return result

    ModelRequestNode.run = wrapped_model_request_run

    # Patch ModelRequestNode.stream for streaming requests
    original_model_request_stream = ModelRequestNode.stream

    def create_wrapped_stream(
        original_stream_method: "Callable[..., Any]",
    ) -> "Callable[..., Any]":
        """Create a wrapper for ModelRequestNode.stream that creates chat spans."""

        @asynccontextmanager
        @wraps(original_stream_method)
        async def wrapped_model_request_stream(self: "Any", ctx: "Any") -> "Any":
            messages, model, model_settings = _extract_span_data(self, ctx)

            # Create chat span for streaming request
            with ai_client_span(messages, None, model, model_settings) as span:
                # Call the original stream method
                async with original_stream_method(self, ctx) as stream:
                    yield stream

                # After streaming completes, update span with response data
                # The ModelRequestNode stores the final response in _result
                model_response = None
                if hasattr(self, "_result") and self._result is not None:
                    # _result is a NextNode containing the model_response
                    if hasattr(self._result, "model_response"):
                        model_response = self._result.model_response

                update_ai_client_span(span, model_response)

        return wrapped_model_request_stream

    ModelRequestNode.stream = create_wrapped_stream(original_model_request_stream)
