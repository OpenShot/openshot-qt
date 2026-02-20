import sentry_sdk
from sentry_sdk.consts import OP, SPANDATA

from ..consts import SPAN_ORIGIN
from ..utils import (
    _set_agent_data,
    _set_input_data,
    _set_output_data,
    _set_usage_data,
    _create_mcp_execute_tool_spans,
)

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agents import Agent
    from typing import Any, Optional


def ai_client_span(
    agent: "Agent", get_response_kwargs: "dict[str, Any]"
) -> "sentry_sdk.tracing.Span":
    # TODO-anton: implement other types of operations. Now "chat" is hardcoded.
    # Get model name from agent.model or fall back to request model (for when agent.model is None/default)
    model_name = None
    if agent.model:
        model_name = agent.model.model if hasattr(agent.model, "model") else agent.model
    elif hasattr(agent, "_sentry_request_model"):
        model_name = agent._sentry_request_model

    span = sentry_sdk.start_span(
        op=OP.GEN_AI_CHAT,
        description=f"chat {model_name}",
        origin=SPAN_ORIGIN,
    )
    # TODO-anton: remove hardcoded stuff and replace something that also works for embedding and so on
    span.set_data(SPANDATA.GEN_AI_OPERATION_NAME, "chat")

    _set_agent_data(span, agent)
    _set_input_data(span, get_response_kwargs)

    return span


def update_ai_client_span(
    span: "sentry_sdk.tracing.Span",
    response: "Any",
    response_model: "Optional[str]" = None,
) -> None:
    """Update AI client span with response data (works for streaming and non-streaming)."""
    if hasattr(response, "usage") and response.usage:
        _set_usage_data(span, response.usage)

    if hasattr(response, "output") and response.output:
        _set_output_data(span, response)
        _create_mcp_execute_tool_spans(span, response)

    if response_model is not None:
        span.set_data(SPANDATA.GEN_AI_RESPONSE_MODEL, response_model)
    elif hasattr(response, "model") and response.model:
        span.set_data(SPANDATA.GEN_AI_RESPONSE_MODEL, str(response.model))
