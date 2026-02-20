import json

import sentry_sdk
from sentry_sdk._types import BLOB_DATA_SUBSTITUTE
from sentry_sdk.ai.utils import (
    normalize_message_roles,
    set_data_normalized,
    truncate_and_annotate_messages,
    get_modality_from_mime_type,
)
from sentry_sdk.consts import OP, SPANDATA
from sentry_sdk.utils import safe_serialize

from ..consts import SPAN_ORIGIN
from ..utils import (
    _set_agent_data,
    _set_available_tools,
    _set_model_data,
    _should_send_prompts,
    _get_model_name,
    get_current_agent,
    get_is_streaming,
)
from .utils import _set_usage_data

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any, List, Dict
    from pydantic_ai.usage import RequestUsage  # type: ignore
    from pydantic_ai.messages import ModelMessage, SystemPromptPart  # type: ignore
    from sentry_sdk._types import TextPart as SentryTextPart

try:
    from pydantic_ai.messages import (
        BaseToolCallPart,
        BaseToolReturnPart,
        SystemPromptPart,
        UserPromptPart,
        TextPart,
        ThinkingPart,
        BinaryContent,
    )
except ImportError:
    # Fallback if these classes are not available
    BaseToolCallPart = None
    BaseToolReturnPart = None
    SystemPromptPart = None
    UserPromptPart = None
    TextPart = None
    ThinkingPart = None
    BinaryContent = None


def _transform_system_instructions(
    permanent_instructions: "list[SystemPromptPart]",
    current_instructions: "list[str]",
) -> "list[SentryTextPart]":
    text_parts: "list[SentryTextPart]" = [
        {
            "type": "text",
            "content": instruction.content,
        }
        for instruction in permanent_instructions
    ]

    text_parts.extend(
        {
            "type": "text",
            "content": instruction,
        }
        for instruction in current_instructions
    )

    return text_parts


def _get_system_instructions(
    messages: "list[ModelMessage]",
) -> "tuple[list[SystemPromptPart], list[str]]":
    permanent_instructions = []
    current_instructions = []

    for msg in messages:
        if hasattr(msg, "parts"):
            for part in msg.parts:
                if SystemPromptPart and isinstance(part, SystemPromptPart):
                    permanent_instructions.append(part)

        if hasattr(msg, "instructions") and msg.instructions is not None:
            current_instructions.append(msg.instructions)

    return permanent_instructions, current_instructions


def _set_input_messages(span: "sentry_sdk.tracing.Span", messages: "Any") -> None:
    """Set input messages data on a span."""
    if not _should_send_prompts():
        return

    if not messages:
        return

    permanent_instructions, current_instructions = _get_system_instructions(messages)
    if len(permanent_instructions) > 0 or len(current_instructions) > 0:
        span.set_data(
            SPANDATA.GEN_AI_SYSTEM_INSTRUCTIONS,
            json.dumps(
                _transform_system_instructions(
                    permanent_instructions, current_instructions
                )
            ),
        )

    try:
        formatted_messages = []

        for msg in messages:
            if hasattr(msg, "parts"):
                for part in msg.parts:
                    role = "user"
                    # Use isinstance checks with proper base classes
                    if SystemPromptPart and isinstance(part, SystemPromptPart):
                        continue
                    elif (
                        (TextPart and isinstance(part, TextPart))
                        or (ThinkingPart and isinstance(part, ThinkingPart))
                        or (BaseToolCallPart and isinstance(part, BaseToolCallPart))
                    ):
                        role = "assistant"
                    elif BaseToolReturnPart and isinstance(part, BaseToolReturnPart):
                        role = "tool"

                    content: "List[Dict[str, Any] | str]" = []
                    tool_calls = None
                    tool_call_id = None

                    # Handle ToolCallPart (assistant requesting tool use)
                    if BaseToolCallPart and isinstance(part, BaseToolCallPart):
                        tool_call_data = {}
                        if hasattr(part, "tool_name"):
                            tool_call_data["name"] = part.tool_name
                        if hasattr(part, "args"):
                            tool_call_data["arguments"] = safe_serialize(part.args)
                        if tool_call_data:
                            tool_calls = [tool_call_data]
                    # Handle ToolReturnPart (tool result)
                    elif BaseToolReturnPart and isinstance(part, BaseToolReturnPart):
                        if hasattr(part, "tool_name"):
                            tool_call_id = part.tool_name
                        if hasattr(part, "content"):
                            content.append({"type": "text", "text": str(part.content)})
                    # Handle regular content
                    elif hasattr(part, "content"):
                        if isinstance(part.content, str):
                            content.append({"type": "text", "text": part.content})
                        elif isinstance(part.content, list):
                            for item in part.content:
                                if isinstance(item, str):
                                    content.append({"type": "text", "text": item})
                                elif BinaryContent and isinstance(item, BinaryContent):
                                    content.append(
                                        {
                                            "type": "blob",
                                            "modality": get_modality_from_mime_type(
                                                item.media_type
                                            ),
                                            "mime_type": item.media_type,
                                            "content": BLOB_DATA_SUBSTITUTE,
                                        }
                                    )
                                else:
                                    content.append(safe_serialize(item))
                        else:
                            content.append({"type": "text", "text": str(part.content)})

                    # Add message if we have content or tool calls
                    if content or tool_calls:
                        message: "Dict[str, Any]" = {"role": role}
                        if content:
                            message["content"] = content
                        if tool_calls:
                            message["tool_calls"] = tool_calls
                        if tool_call_id:
                            message["tool_call_id"] = tool_call_id
                        formatted_messages.append(message)

        if formatted_messages:
            normalized_messages = normalize_message_roles(formatted_messages)
            scope = sentry_sdk.get_current_scope()
            messages_data = truncate_and_annotate_messages(
                normalized_messages, span, scope
            )
            set_data_normalized(
                span, SPANDATA.GEN_AI_REQUEST_MESSAGES, messages_data, unpack=False
            )
    except Exception:
        # If we fail to format messages, just skip it
        pass


def _set_output_data(span: "sentry_sdk.tracing.Span", response: "Any") -> None:
    """Set output data on a span."""
    if not _should_send_prompts():
        return

    if not response:
        return

    set_data_normalized(span, SPANDATA.GEN_AI_RESPONSE_MODEL, response.model_name)
    try:
        # Extract text from ModelResponse
        if hasattr(response, "parts"):
            texts = []
            tool_calls = []

            for part in response.parts:
                if TextPart and isinstance(part, TextPart) and hasattr(part, "content"):
                    texts.append(part.content)
                elif BaseToolCallPart and isinstance(part, BaseToolCallPart):
                    tool_call_data = {
                        "type": "function",
                    }
                    if hasattr(part, "tool_name"):
                        tool_call_data["name"] = part.tool_name
                    if hasattr(part, "args"):
                        tool_call_data["arguments"] = safe_serialize(part.args)
                    tool_calls.append(tool_call_data)

            if texts:
                set_data_normalized(span, SPANDATA.GEN_AI_RESPONSE_TEXT, texts)

            if tool_calls:
                span.set_data(
                    SPANDATA.GEN_AI_RESPONSE_TOOL_CALLS, safe_serialize(tool_calls)
                )

    except Exception:
        # If we fail to format output, just skip it
        pass


def ai_client_span(
    messages: "Any", agent: "Any", model: "Any", model_settings: "Any"
) -> "sentry_sdk.tracing.Span":
    """Create a span for an AI client call (model request).

    Args:
        messages: Full conversation history (list of messages)
        agent: Agent object
        model: Model object
        model_settings: Model settings
    """
    # Determine model name for span name
    model_obj = model
    if agent and hasattr(agent, "model"):
        model_obj = agent.model

    model_name = _get_model_name(model_obj) or "unknown"

    span = sentry_sdk.start_span(
        op=OP.GEN_AI_CHAT,
        name=f"chat {model_name}",
        origin=SPAN_ORIGIN,
    )

    span.set_data(SPANDATA.GEN_AI_OPERATION_NAME, "chat")

    _set_agent_data(span, agent)
    _set_model_data(span, model, model_settings)

    # Set streaming flag from contextvar
    span.set_data(SPANDATA.GEN_AI_RESPONSE_STREAMING, get_is_streaming())

    # Add available tools if agent is available
    agent_obj = agent or get_current_agent()
    _set_available_tools(span, agent_obj)

    # Set input messages (full conversation history)
    if messages:
        _set_input_messages(span, messages)

    return span


def update_ai_client_span(
    span: "sentry_sdk.tracing.Span", model_response: "Any"
) -> None:
    """Update the AI client span with response data."""
    if not span:
        return

    # Set usage data if available
    if model_response and hasattr(model_response, "usage"):
        _set_usage_data(span, model_response.usage)

    # Set output data
    _set_output_data(span, model_response)
