import json

import sentry_sdk
from sentry_sdk.ai.utils import (
    GEN_AI_ALLOWED_MESSAGE_ROLES,
    normalize_message_roles,
    set_data_normalized,
    normalize_message_role,
    truncate_and_annotate_messages,
)
from sentry_sdk.consts import SPANDATA, SPANSTATUS, OP
from sentry_sdk.integrations import DidNotEnable
from sentry_sdk.scope import should_send_default_pii
from sentry_sdk.tracing_utils import set_span_errored
from sentry_sdk.utils import event_from_exception, safe_serialize
from sentry_sdk.ai._openai_completions_api import _transform_system_instructions
from sentry_sdk.ai._openai_responses_api import (
    _is_system_instruction,
    _get_system_instructions,
)

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any
    from agents import Usage, TResponseInputItem

    from sentry_sdk.tracing import Span
    from sentry_sdk._types import TextPart

try:
    import agents

except ImportError:
    raise DidNotEnable("OpenAI Agents not installed")


def _capture_exception(exc: "Any") -> None:
    set_span_errored()

    event, hint = event_from_exception(
        exc,
        client_options=sentry_sdk.get_client().options,
        mechanism={"type": "openai_agents", "handled": False},
    )
    sentry_sdk.capture_event(event, hint=hint)


def _record_exception_on_span(span: "Span", error: Exception) -> "Any":
    set_span_errored(span)
    span.set_data("span.status", "error")

    # Optionally capture the error details if we have them
    if hasattr(error, "__class__"):
        span.set_data("error.type", error.__class__.__name__)
    if hasattr(error, "__str__"):
        error_message = str(error)
        if error_message:
            span.set_data("error.message", error_message)


def _set_agent_data(span: "sentry_sdk.tracing.Span", agent: "agents.Agent") -> None:
    span.set_data(
        SPANDATA.GEN_AI_SYSTEM, "openai"
    )  # See footnote for  https://opentelemetry.io/docs/specs/semconv/registry/attributes/gen-ai/#gen-ai-system for explanation why.

    span.set_data(SPANDATA.GEN_AI_AGENT_NAME, agent.name)

    if agent.model_settings.max_tokens:
        span.set_data(
            SPANDATA.GEN_AI_REQUEST_MAX_TOKENS, agent.model_settings.max_tokens
        )

    # Get model name from agent.model or fall back to request model (for when agent.model is None/default)
    model_name = None
    if agent.model:
        model_name = agent.model.model if hasattr(agent.model, "model") else agent.model
    elif hasattr(agent, "_sentry_request_model"):
        model_name = agent._sentry_request_model

    if model_name:
        span.set_data(SPANDATA.GEN_AI_REQUEST_MODEL, model_name)

    if agent.model_settings.presence_penalty:
        span.set_data(
            SPANDATA.GEN_AI_REQUEST_PRESENCE_PENALTY,
            agent.model_settings.presence_penalty,
        )

    if agent.model_settings.temperature:
        span.set_data(
            SPANDATA.GEN_AI_REQUEST_TEMPERATURE, agent.model_settings.temperature
        )

    if agent.model_settings.top_p:
        span.set_data(SPANDATA.GEN_AI_REQUEST_TOP_P, agent.model_settings.top_p)

    if agent.model_settings.frequency_penalty:
        span.set_data(
            SPANDATA.GEN_AI_REQUEST_FREQUENCY_PENALTY,
            agent.model_settings.frequency_penalty,
        )

    if len(agent.tools) > 0:
        span.set_data(
            SPANDATA.GEN_AI_REQUEST_AVAILABLE_TOOLS,
            safe_serialize([vars(tool) for tool in agent.tools]),
        )


def _set_usage_data(span: "sentry_sdk.tracing.Span", usage: "Usage") -> None:
    span.set_data(SPANDATA.GEN_AI_USAGE_INPUT_TOKENS, usage.input_tokens)
    span.set_data(
        SPANDATA.GEN_AI_USAGE_INPUT_TOKENS_CACHED,
        usage.input_tokens_details.cached_tokens,
    )
    span.set_data(SPANDATA.GEN_AI_USAGE_OUTPUT_TOKENS, usage.output_tokens)
    span.set_data(
        SPANDATA.GEN_AI_USAGE_OUTPUT_TOKENS_REASONING,
        usage.output_tokens_details.reasoning_tokens,
    )
    span.set_data(SPANDATA.GEN_AI_USAGE_TOTAL_TOKENS, usage.total_tokens)


def _set_input_data(
    span: "sentry_sdk.tracing.Span", get_response_kwargs: "dict[str, Any]"
) -> None:
    if not should_send_default_pii():
        return
    request_messages = []

    messages: "str | list[TResponseInputItem]" = get_response_kwargs.get("input", [])

    instructions_text_parts: "list[TextPart]" = []
    explicit_instructions = get_response_kwargs.get("system_instructions")
    if explicit_instructions is not None:
        instructions_text_parts.append(
            {
                "type": "text",
                "content": explicit_instructions,
            }
        )

    system_instructions = _get_system_instructions(messages)

    # Deliberate use of function accepting completions API type because
    # of shared structure FOR THIS PURPOSE ONLY.
    instructions_text_parts += _transform_system_instructions(system_instructions)

    if len(instructions_text_parts) > 0:
        span.set_data(
            SPANDATA.GEN_AI_SYSTEM_INSTRUCTIONS,
            json.dumps(instructions_text_parts),
        )

    non_system_messages = [
        message for message in messages if not _is_system_instruction(message)
    ]
    for message in non_system_messages:
        if "role" in message:
            normalized_role = normalize_message_role(message.get("role"))  # type: ignore
            content = message.get("content")  # type: ignore
            request_messages.append(
                {
                    "role": normalized_role,
                    "content": (
                        [{"type": "text", "text": content}]
                        if isinstance(content, str)
                        else content
                    ),
                }
            )
        else:
            if message.get("type") == "function_call":  # type: ignore
                request_messages.append(
                    {
                        "role": GEN_AI_ALLOWED_MESSAGE_ROLES.ASSISTANT,
                        "content": [message],
                    }
                )
            elif message.get("type") == "function_call_output":  # type: ignore
                request_messages.append(
                    {
                        "role": GEN_AI_ALLOWED_MESSAGE_ROLES.TOOL,
                        "content": [message],
                    }
                )

    normalized_messages = normalize_message_roles(request_messages)
    scope = sentry_sdk.get_current_scope()
    messages_data = truncate_and_annotate_messages(normalized_messages, span, scope)
    if messages_data is not None:
        set_data_normalized(
            span,
            SPANDATA.GEN_AI_REQUEST_MESSAGES,
            messages_data,
            unpack=False,
        )


def _set_output_data(span: "sentry_sdk.tracing.Span", result: "Any") -> None:
    if not should_send_default_pii():
        return

    output_messages: "dict[str, list[Any]]" = {
        "response": [],
        "tool": [],
    }

    for output in result.output:
        if output.type == "function_call":
            output_messages["tool"].append(output.dict())
        elif output.type == "message":
            for output_message in output.content:
                try:
                    output_messages["response"].append(output_message.text)
                except AttributeError:
                    # Unknown output message type, just return the json
                    output_messages["response"].append(output_message.dict())

    if len(output_messages["tool"]) > 0:
        span.set_data(
            SPANDATA.GEN_AI_RESPONSE_TOOL_CALLS, safe_serialize(output_messages["tool"])
        )

    if len(output_messages["response"]) > 0:
        set_data_normalized(
            span, SPANDATA.GEN_AI_RESPONSE_TEXT, output_messages["response"]
        )


def _create_mcp_execute_tool_spans(
    span: "sentry_sdk.tracing.Span", result: "agents.Result"
) -> None:
    for output in result.output:
        if output.__class__.__name__ == "McpCall":
            with sentry_sdk.start_span(
                op=OP.GEN_AI_EXECUTE_TOOL,
                description=f"execute_tool {output.name}",
                start_timestamp=span.start_timestamp,
            ) as execute_tool_span:
                set_data_normalized(execute_tool_span, SPANDATA.GEN_AI_TOOL_TYPE, "mcp")
                set_data_normalized(
                    execute_tool_span, SPANDATA.GEN_AI_TOOL_NAME, output.name
                )
                if should_send_default_pii():
                    execute_tool_span.set_data(
                        SPANDATA.GEN_AI_TOOL_INPUT, output.arguments
                    )
                    execute_tool_span.set_data(
                        SPANDATA.GEN_AI_TOOL_OUTPUT, output.output
                    )
                if output.error:
                    execute_tool_span.set_status(SPANSTATUS.INTERNAL_ERROR)
