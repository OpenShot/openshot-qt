import copy
import json
import inspect
from functools import wraps
from .consts import ORIGIN, TOOL_ATTRIBUTES_MAP, GEN_AI_SYSTEM
from sentry_sdk._types import BLOB_DATA_SUBSTITUTE
from typing import (
    cast,
    TYPE_CHECKING,
    Iterable,
    Any,
    Callable,
    List,
    Optional,
    Union,
    TypedDict,
    Dict,
)

import sentry_sdk
from sentry_sdk.ai.utils import (
    set_data_normalized,
    truncate_and_annotate_messages,
    normalize_message_roles,
    redact_blob_message_parts,
    transform_google_content_part,
    get_modality_from_mime_type,
)
from sentry_sdk.consts import OP, SPANDATA
from sentry_sdk.scope import should_send_default_pii
from sentry_sdk.utils import (
    capture_internal_exceptions,
    event_from_exception,
    safe_serialize,
)
from google.genai.types import GenerateContentConfig, Part, Content
from itertools import chain

if TYPE_CHECKING:
    from sentry_sdk.tracing import Span
    from sentry_sdk._types import TextPart
    from google.genai.types import (
        GenerateContentResponse,
        ContentListUnion,
        ContentUnionDict,
        Tool,
        Model,
        EmbedContentResponse,
        ContentUnion,
    )


class UsageData(TypedDict):
    """Structure for token usage data."""

    input_tokens: int
    input_tokens_cached: int
    output_tokens: int
    output_tokens_reasoning: int
    total_tokens: int


def extract_usage_data(
    response: "Union[GenerateContentResponse, dict[str, Any]]",
) -> "UsageData":
    """Extract usage data from response into a structured format.

    Args:
        response: The GenerateContentResponse object or dictionary containing usage metadata

    Returns:
        UsageData: Dictionary with input_tokens, input_tokens_cached,
                   output_tokens, and output_tokens_reasoning fields
    """
    usage_data = UsageData(
        input_tokens=0,
        input_tokens_cached=0,
        output_tokens=0,
        output_tokens_reasoning=0,
        total_tokens=0,
    )

    # Handle dictionary response (from streaming)
    if isinstance(response, dict):
        usage = response.get("usage_metadata", {})
        if not usage:
            return usage_data

        prompt_tokens = usage.get("prompt_token_count", 0) or 0
        tool_use_prompt_tokens = usage.get("tool_use_prompt_token_count", 0) or 0
        usage_data["input_tokens"] = prompt_tokens + tool_use_prompt_tokens

        cached_tokens = usage.get("cached_content_token_count", 0) or 0
        usage_data["input_tokens_cached"] = cached_tokens

        reasoning_tokens = usage.get("thoughts_token_count", 0) or 0
        usage_data["output_tokens_reasoning"] = reasoning_tokens

        candidates_tokens = usage.get("candidates_token_count", 0) or 0
        # python-genai reports output and reasoning tokens separately
        # reasoning should be sub-category of output tokens
        usage_data["output_tokens"] = candidates_tokens + reasoning_tokens

        total_tokens = usage.get("total_token_count", 0) or 0
        usage_data["total_tokens"] = total_tokens

        return usage_data

    if not hasattr(response, "usage_metadata"):
        return usage_data

    usage = response.usage_metadata

    # Input tokens include both prompt and tool use prompt tokens
    prompt_tokens = getattr(usage, "prompt_token_count", 0) or 0
    tool_use_prompt_tokens = getattr(usage, "tool_use_prompt_token_count", 0) or 0
    usage_data["input_tokens"] = prompt_tokens + tool_use_prompt_tokens

    # Cached input tokens
    cached_tokens = getattr(usage, "cached_content_token_count", 0) or 0
    usage_data["input_tokens_cached"] = cached_tokens

    # Reasoning tokens
    reasoning_tokens = getattr(usage, "thoughts_token_count", 0) or 0
    usage_data["output_tokens_reasoning"] = reasoning_tokens

    # output_tokens = candidates_tokens + reasoning_tokens
    # google-genai reports output and reasoning tokens separately
    candidates_tokens = getattr(usage, "candidates_token_count", 0) or 0
    usage_data["output_tokens"] = candidates_tokens + reasoning_tokens

    total_tokens = getattr(usage, "total_token_count", 0) or 0
    usage_data["total_tokens"] = total_tokens

    return usage_data


def _capture_exception(exc: "Any") -> None:
    """Capture exception with Google GenAI mechanism."""
    event, hint = event_from_exception(
        exc,
        client_options=sentry_sdk.get_client().options,
        mechanism={"type": "google_genai", "handled": False},
    )
    sentry_sdk.capture_event(event, hint=hint)


def get_model_name(model: "Union[str, Model]") -> str:
    """Extract model name from model parameter."""
    if isinstance(model, str):
        return model
    # Handle case where model might be an object with a name attribute
    if hasattr(model, "name"):
        return str(model.name)
    return str(model)


def extract_contents_messages(contents: "ContentListUnion") -> "List[Dict[str, Any]]":
    """Extract messages from contents parameter which can have various formats.

    Returns a list of message dictionaries in the format:
    - System: {"role": "system", "content": "string"}
    - User/Assistant: {"role": "user"|"assistant", "content": [{"text": "...", "type": "text"}, ...]}
    """
    if contents is None:
        return []

    messages = []

    # Handle string case
    if isinstance(contents, str):
        return [{"role": "user", "content": contents}]

    # Handle list case - process each item (non-recursive, flatten at top level)
    if isinstance(contents, list):
        for item in contents:
            item_messages = extract_contents_messages(item)
            messages.extend(item_messages)
        return messages

    # Handle dictionary case (ContentDict)
    if isinstance(contents, dict):
        role = contents.get("role", "user")
        parts = contents.get("parts")

        if parts:
            content_parts = []
            tool_messages = []

            for part in parts:
                part_result = _extract_part_content(part)
                if part_result is None:
                    continue

                if isinstance(part_result, dict) and part_result.get("role") == "tool":
                    # Tool message - add separately
                    tool_messages.append(part_result)
                else:
                    # Regular content part
                    content_parts.append(part_result)

            # Add main message if we have content parts
            if content_parts:
                # Normalize role: "model" -> "assistant"
                normalized_role = "assistant" if role == "model" else role or "user"
                messages.append({"role": normalized_role, "content": content_parts})

            # Add tool messages
            messages.extend(tool_messages)
        elif "text" in contents:
            # Simple text in dict
            messages.append(
                {
                    "role": role or "user",
                    "content": [{"text": contents["text"], "type": "text"}],
                }
            )

        return messages

    # Handle Content object
    if hasattr(contents, "parts") and contents.parts:
        role = getattr(contents, "role", None) or "user"
        content_parts = []
        tool_messages = []

        for part in contents.parts:
            part_result = _extract_part_content(part)
            if part_result is None:
                continue

            if isinstance(part_result, dict) and part_result.get("role") == "tool":
                tool_messages.append(part_result)
            else:
                content_parts.append(part_result)

        if content_parts:
            normalized_role = "assistant" if role == "model" else role
            messages.append({"role": normalized_role, "content": content_parts})

        messages.extend(tool_messages)
        return messages

    # Handle Part object directly
    part_result = _extract_part_content(contents)
    if part_result:
        if isinstance(part_result, dict) and part_result.get("role") == "tool":
            return [part_result]
        else:
            return [{"role": "user", "content": [part_result]}]

    # Handle PIL.Image.Image
    try:
        from PIL import Image as PILImage  # type: ignore[import-not-found]

        if isinstance(contents, PILImage.Image):
            blob_part = _extract_pil_image(contents)
            if blob_part:
                return [{"role": "user", "content": [blob_part]}]
    except ImportError:
        pass

    # Handle File object
    if hasattr(contents, "uri") and hasattr(contents, "mime_type"):
        # File object
        file_uri = getattr(contents, "uri", None)
        mime_type = getattr(contents, "mime_type", None)
        # Process if we have file_uri, even if mime_type is missing
        if file_uri is not None:
            # Default to empty string if mime_type is None
            if mime_type is None:
                mime_type = ""

            blob_part = {
                "type": "uri",
                "modality": get_modality_from_mime_type(mime_type),
                "mime_type": mime_type,
                "uri": file_uri,
            }
            return [{"role": "user", "content": [blob_part]}]

    # Handle direct text attribute
    if hasattr(contents, "text") and contents.text:
        return [
            {"role": "user", "content": [{"text": str(contents.text), "type": "text"}]}
        ]

    return []


def _extract_part_content(part: "Any") -> "Optional[dict[str, Any]]":
    """Extract content from a Part object or dict.

    Returns:
        - dict for content part (text/blob) or tool message
        - None if part should be skipped
    """
    if part is None:
        return None

    # Handle dict Part
    if isinstance(part, dict):
        # Check for function_response first (tool message)
        if "function_response" in part:
            return _extract_tool_message_from_part(part)

        if part.get("text"):
            return {"text": part["text"], "type": "text"}

        # Try using Google-specific transform for dict formats (inline_data, file_data)
        result = transform_google_content_part(part)
        if result is not None:
            # For inline_data with bytes data, substitute the content
            if "inline_data" in part:
                inline_data = part["inline_data"]
                if isinstance(inline_data, dict) and isinstance(
                    inline_data.get("data"), bytes
                ):
                    result["content"] = BLOB_DATA_SUBSTITUTE
            return result

        return None

    # Handle Part object
    # Check for function_response (tool message)
    if hasattr(part, "function_response") and part.function_response:
        return _extract_tool_message_from_part(part)

    # Handle text
    if hasattr(part, "text") and part.text:
        return {"text": part.text, "type": "text"}

    # Handle file_data
    if hasattr(part, "file_data") and part.file_data:
        file_data = part.file_data
        file_uri = getattr(file_data, "file_uri", None)
        mime_type = getattr(file_data, "mime_type", None)
        # Process if we have file_uri, even if mime_type is missing (consistent with dict handling)
        if file_uri is not None:
            # Default to empty string if mime_type is None (consistent with transform_google_content_part)
            if mime_type is None:
                mime_type = ""

            return {
                "type": "uri",
                "modality": get_modality_from_mime_type(mime_type),
                "mime_type": mime_type,
                "uri": file_uri,
            }

    # Handle inline_data
    if hasattr(part, "inline_data") and part.inline_data:
        inline_data = part.inline_data
        data = getattr(inline_data, "data", None)
        mime_type = getattr(inline_data, "mime_type", None)
        # Process if we have data, even if mime_type is missing/empty (consistent with dict handling)
        if data is not None:
            # Default to empty string if mime_type is None (consistent with transform_google_content_part)
            if mime_type is None:
                mime_type = ""

            # Handle both bytes (binary data) and str (base64-encoded data)
            if isinstance(data, bytes):
                content = BLOB_DATA_SUBSTITUTE
            else:
                # For non-bytes data (e.g., base64 strings), use as-is
                content = data

            return {
                "type": "blob",
                "modality": get_modality_from_mime_type(mime_type),
                "mime_type": mime_type,
                "content": content,
            }

    return None


def _extract_tool_message_from_part(part: "Any") -> "Optional[dict[str, Any]]":
    """Extract tool message from a Part with function_response.

    Returns:
        {"role": "tool", "content": {"toolCallId": "...", "toolName": "...", "output": "..."}}
        or None if not a valid tool message
    """
    function_response = None

    if isinstance(part, dict):
        function_response = part.get("function_response")
    elif hasattr(part, "function_response"):
        function_response = part.function_response

    if not function_response:
        return None

    # Extract fields from function_response
    tool_call_id = None
    tool_name = None
    output = None

    if isinstance(function_response, dict):
        tool_call_id = function_response.get("id")
        tool_name = function_response.get("name")
        response_dict = function_response.get("response", {})
        # Prefer "output" key if present, otherwise use entire response
        output = response_dict.get("output", response_dict)
    else:
        # FunctionResponse object
        tool_call_id = getattr(function_response, "id", None)
        tool_name = getattr(function_response, "name", None)
        response_obj = getattr(function_response, "response", None)
        if response_obj is None:
            response_obj = {}
        if isinstance(response_obj, dict):
            output = response_obj.get("output", response_obj)
        else:
            output = response_obj

    if not tool_name:
        return None

    return {
        "role": "tool",
        "content": {
            "toolCallId": str(tool_call_id) if tool_call_id else None,
            "toolName": str(tool_name),
            "output": safe_serialize(output) if output is not None else None,
        },
    }


def _extract_pil_image(image: "Any") -> "Optional[dict[str, Any]]":
    """Extract blob part from PIL.Image.Image."""
    try:
        from PIL import Image as PILImage

        if not isinstance(image, PILImage.Image):
            return None

        # Get format, default to JPEG
        format_str = image.format or "JPEG"
        suffix = format_str.lower()
        mime_type = f"image/{suffix}"

        return {
            "type": "blob",
            "modality": get_modality_from_mime_type(mime_type),
            "mime_type": mime_type,
            "content": BLOB_DATA_SUBSTITUTE,
        }
    except Exception:
        return None


def extract_contents_text(contents: "ContentListUnion") -> "Optional[str]":
    """Extract text from contents parameter which can have various formats.

    This is a compatibility function that extracts text from messages.
    For new code, use extract_contents_messages instead.
    """
    messages = extract_contents_messages(contents)
    if not messages:
        return None

    texts = []
    for message in messages:
        content = message.get("content")
        if isinstance(content, str):
            texts.append(content)
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    texts.append(part.get("text", ""))

    return " ".join(texts) if texts else None


def _format_tools_for_span(
    tools: "Iterable[Tool | Callable[..., Any]]",
) -> "Optional[List[dict[str, Any]]]":
    """Format tools parameter for span data."""
    formatted_tools = []
    for tool in tools:
        if callable(tool):
            # Handle callable functions passed directly
            formatted_tools.append(
                {
                    "name": getattr(tool, "__name__", "unknown"),
                    "description": getattr(tool, "__doc__", None),
                }
            )
        elif (
            hasattr(tool, "function_declarations")
            and tool.function_declarations is not None
        ):
            # Tool object with function declarations
            for func_decl in tool.function_declarations:
                formatted_tools.append(
                    {
                        "name": getattr(func_decl, "name", None),
                        "description": getattr(func_decl, "description", None),
                    }
                )
        else:
            # Check for predefined tool attributes - each of these tools
            # is an attribute of the tool object, by default set to None
            for attr_name, description in TOOL_ATTRIBUTES_MAP.items():
                if getattr(tool, attr_name, None):
                    formatted_tools.append(
                        {
                            "name": attr_name,
                            "description": description,
                        }
                    )
                    break

    return formatted_tools if formatted_tools else None


def extract_tool_calls(
    response: "GenerateContentResponse",
) -> "Optional[List[dict[str, Any]]]":
    """Extract tool/function calls from response candidates and automatic function calling history."""

    tool_calls = []

    # Extract from candidates, sometimes tool calls are nested under the content.parts object
    if getattr(response, "candidates", []):
        for candidate in response.candidates:
            if not hasattr(candidate, "content") or not getattr(
                candidate.content, "parts", []
            ):
                continue

            for part in candidate.content.parts:
                if getattr(part, "function_call", None):
                    function_call = part.function_call
                    tool_call = {
                        "name": getattr(function_call, "name", None),
                        "type": "function_call",
                    }

                    # Extract arguments if available
                    if getattr(function_call, "args", None):
                        tool_call["arguments"] = safe_serialize(function_call.args)

                    tool_calls.append(tool_call)

    # Extract from automatic_function_calling_history
    # This is the history of tool calls made by the model
    if getattr(response, "automatic_function_calling_history", None):
        for content in response.automatic_function_calling_history:
            if not getattr(content, "parts", None):
                continue

            for part in getattr(content, "parts", []):
                if getattr(part, "function_call", None):
                    function_call = part.function_call
                    tool_call = {
                        "name": getattr(function_call, "name", None),
                        "type": "function_call",
                    }

                    # Extract arguments if available
                    if hasattr(function_call, "args"):
                        tool_call["arguments"] = safe_serialize(function_call.args)

                    tool_calls.append(tool_call)

    return tool_calls if tool_calls else None


def _capture_tool_input(
    args: "tuple[Any, ...]", kwargs: "dict[str, Any]", tool: "Tool"
) -> "dict[str, Any]":
    """Capture tool input from args and kwargs."""
    tool_input = kwargs.copy() if kwargs else {}

    # If we have positional args, try to map them to the function signature
    if args:
        try:
            sig = inspect.signature(tool)
            param_names = list(sig.parameters.keys())
            for i, arg in enumerate(args):
                if i < len(param_names):
                    tool_input[param_names[i]] = arg
        except Exception:
            # Fallback if we can't get the signature
            tool_input["args"] = args

    return tool_input


def _create_tool_span(tool_name: str, tool_doc: "Optional[str]") -> "Span":
    """Create a span for tool execution."""
    span = sentry_sdk.start_span(
        op=OP.GEN_AI_EXECUTE_TOOL,
        name=f"execute_tool {tool_name}",
        origin=ORIGIN,
    )
    span.set_data(SPANDATA.GEN_AI_TOOL_NAME, tool_name)
    span.set_data(SPANDATA.GEN_AI_TOOL_TYPE, "function")
    if tool_doc:
        span.set_data(SPANDATA.GEN_AI_TOOL_DESCRIPTION, tool_doc)
    return span


def wrapped_tool(tool: "Tool | Callable[..., Any]") -> "Tool | Callable[..., Any]":
    """Wrap a tool to emit execute_tool spans when called."""
    if not callable(tool):
        # Not a callable function, return as-is (predefined tools)
        return tool

    tool_name = getattr(tool, "__name__", "unknown")
    tool_doc = tool.__doc__

    if inspect.iscoroutinefunction(tool):
        # Async function
        @wraps(tool)
        async def async_wrapped(*args: "Any", **kwargs: "Any") -> "Any":
            with _create_tool_span(tool_name, tool_doc) as span:
                # Capture tool input
                tool_input = _capture_tool_input(args, kwargs, tool)
                with capture_internal_exceptions():
                    span.set_data(
                        SPANDATA.GEN_AI_TOOL_INPUT, safe_serialize(tool_input)
                    )

                try:
                    result = await tool(*args, **kwargs)

                    # Capture tool output
                    with capture_internal_exceptions():
                        span.set_data(
                            SPANDATA.GEN_AI_TOOL_OUTPUT, safe_serialize(result)
                        )

                    return result
                except Exception as exc:
                    _capture_exception(exc)
                    raise

        return async_wrapped
    else:
        # Sync function
        @wraps(tool)
        def sync_wrapped(*args: "Any", **kwargs: "Any") -> "Any":
            with _create_tool_span(tool_name, tool_doc) as span:
                # Capture tool input
                tool_input = _capture_tool_input(args, kwargs, tool)
                with capture_internal_exceptions():
                    span.set_data(
                        SPANDATA.GEN_AI_TOOL_INPUT, safe_serialize(tool_input)
                    )

                try:
                    result = tool(*args, **kwargs)

                    # Capture tool output
                    with capture_internal_exceptions():
                        span.set_data(
                            SPANDATA.GEN_AI_TOOL_OUTPUT, safe_serialize(result)
                        )

                    return result
                except Exception as exc:
                    _capture_exception(exc)
                    raise

        return sync_wrapped


def wrapped_config_with_tools(
    config: "GenerateContentConfig",
) -> "GenerateContentConfig":
    """Wrap tools in config to emit execute_tool spans. Tools are sometimes passed directly as
    callable functions as a part of the config object."""

    if not config or not getattr(config, "tools", None):
        return config

    result = copy.copy(config)
    result.tools = [wrapped_tool(tool) for tool in config.tools]

    return result


def _extract_response_text(
    response: "GenerateContentResponse",
) -> "Optional[List[str]]":
    """Extract text from response candidates."""

    if not response or not getattr(response, "candidates", []):
        return None

    texts = []
    for candidate in response.candidates:
        if not hasattr(candidate, "content") or not hasattr(candidate.content, "parts"):
            continue

        for part in candidate.content.parts:
            if getattr(part, "text", None):
                texts.append(part.text)

    return texts if texts else None


def extract_finish_reasons(
    response: "GenerateContentResponse",
) -> "Optional[List[str]]":
    """Extract finish reasons from response candidates."""
    if not response or not getattr(response, "candidates", []):
        return None

    finish_reasons = []
    for candidate in response.candidates:
        if getattr(candidate, "finish_reason", None):
            # Convert enum value to string if necessary
            reason = str(candidate.finish_reason)
            # Remove enum prefix if present (e.g., "FinishReason.STOP" -> "STOP")
            if "." in reason:
                reason = reason.split(".")[-1]
            finish_reasons.append(reason)

    return finish_reasons if finish_reasons else None


def _transform_system_instruction_one_level(
    system_instructions: "Union[ContentUnionDict, ContentUnion]",
    can_be_content: bool,
) -> "list[TextPart]":
    text_parts: "list[TextPart]" = []

    if isinstance(system_instructions, str):
        return [{"type": "text", "content": system_instructions}]

    if isinstance(system_instructions, Part) and system_instructions.text:
        return [{"type": "text", "content": system_instructions.text}]

    if can_be_content and isinstance(system_instructions, Content):
        if isinstance(system_instructions.parts, list):
            for part in system_instructions.parts:
                if isinstance(part.text, str):
                    text_parts.append({"type": "text", "content": part.text})
        return text_parts

    if isinstance(system_instructions, dict) and system_instructions.get("text"):
        return [{"type": "text", "content": system_instructions["text"]}]

    elif can_be_content and isinstance(system_instructions, dict):
        parts = system_instructions.get("parts", [])
        for part in parts:
            if isinstance(part, Part) and isinstance(part.text, str):
                text_parts.append({"type": "text", "content": part.text})
            elif isinstance(part, dict) and isinstance(part.get("text"), str):
                text_parts.append({"type": "text", "content": part["text"]})
        return text_parts

    return text_parts


def _transform_system_instructions(
    system_instructions: "Union[ContentUnionDict, ContentUnion]",
) -> "list[TextPart]":
    text_parts: "list[TextPart]" = []

    if isinstance(system_instructions, list):
        text_parts = list(
            chain.from_iterable(
                _transform_system_instruction_one_level(
                    instructions, can_be_content=False
                )
                for instructions in system_instructions
            )
        )

        return text_parts

    return _transform_system_instruction_one_level(
        system_instructions, can_be_content=True
    )


def set_span_data_for_request(
    span: "Span",
    integration: "Any",
    model: str,
    contents: "ContentListUnion",
    kwargs: "dict[str, Any]",
) -> None:
    """Set span data for the request."""
    span.set_data(SPANDATA.GEN_AI_SYSTEM, GEN_AI_SYSTEM)
    span.set_data(SPANDATA.GEN_AI_REQUEST_MODEL, model)

    if kwargs.get("stream", False):
        span.set_data(SPANDATA.GEN_AI_RESPONSE_STREAMING, True)

    config: "Optional[GenerateContentConfig]" = kwargs.get("config")

    # Set input messages/prompts if PII is allowed
    if should_send_default_pii() and integration.include_prompts:
        messages = []

        # Add system instruction if present
        system_instructions = None
        if config and hasattr(config, "system_instruction"):
            system_instructions = config.system_instruction
        elif isinstance(config, dict) and "system_instruction" in config:
            system_instructions = config.get("system_instruction")

        if system_instructions is not None:
            span.set_data(
                SPANDATA.GEN_AI_SYSTEM_INSTRUCTIONS,
                json.dumps(_transform_system_instructions(system_instructions)),
            )

        # Extract messages from contents
        contents_messages = extract_contents_messages(contents)
        messages.extend(contents_messages)

        if messages:
            normalized_messages = normalize_message_roles(messages)
            scope = sentry_sdk.get_current_scope()
            messages_data = truncate_and_annotate_messages(
                normalized_messages, span, scope
            )
            if messages_data is not None:
                set_data_normalized(
                    span,
                    SPANDATA.GEN_AI_REQUEST_MESSAGES,
                    messages_data,
                    unpack=False,
                )

    # Extract parameters directly from config (not nested under generation_config)
    for param, span_key in [
        ("temperature", SPANDATA.GEN_AI_REQUEST_TEMPERATURE),
        ("top_p", SPANDATA.GEN_AI_REQUEST_TOP_P),
        ("top_k", SPANDATA.GEN_AI_REQUEST_TOP_K),
        ("max_output_tokens", SPANDATA.GEN_AI_REQUEST_MAX_TOKENS),
        ("presence_penalty", SPANDATA.GEN_AI_REQUEST_PRESENCE_PENALTY),
        ("frequency_penalty", SPANDATA.GEN_AI_REQUEST_FREQUENCY_PENALTY),
        ("seed", SPANDATA.GEN_AI_REQUEST_SEED),
    ]:
        if hasattr(config, param):
            value = getattr(config, param)
            if value is not None:
                span.set_data(span_key, value)

    # Set tools if available
    if config is not None and hasattr(config, "tools"):
        tools = config.tools
        if tools:
            formatted_tools = _format_tools_for_span(tools)
            if formatted_tools:
                set_data_normalized(
                    span,
                    SPANDATA.GEN_AI_REQUEST_AVAILABLE_TOOLS,
                    formatted_tools,
                    unpack=False,
                )


def set_span_data_for_response(
    span: "Span", integration: "Any", response: "GenerateContentResponse"
) -> None:
    """Set span data for the response."""
    if not response:
        return

    if should_send_default_pii() and integration.include_prompts:
        response_texts = _extract_response_text(response)
        if response_texts:
            # Format as JSON string array as per documentation
            span.set_data(SPANDATA.GEN_AI_RESPONSE_TEXT, safe_serialize(response_texts))

    tool_calls = extract_tool_calls(response)
    if tool_calls:
        # Tool calls should be JSON serialized
        span.set_data(SPANDATA.GEN_AI_RESPONSE_TOOL_CALLS, safe_serialize(tool_calls))

    finish_reasons = extract_finish_reasons(response)
    if finish_reasons:
        set_data_normalized(
            span, SPANDATA.GEN_AI_RESPONSE_FINISH_REASONS, finish_reasons
        )

    if getattr(response, "response_id", None):
        span.set_data(SPANDATA.GEN_AI_RESPONSE_ID, response.response_id)

    if getattr(response, "model_version", None):
        span.set_data(SPANDATA.GEN_AI_RESPONSE_MODEL, response.model_version)

    usage_data = extract_usage_data(response)

    if usage_data["input_tokens"]:
        span.set_data(SPANDATA.GEN_AI_USAGE_INPUT_TOKENS, usage_data["input_tokens"])

    if usage_data["input_tokens_cached"]:
        span.set_data(
            SPANDATA.GEN_AI_USAGE_INPUT_TOKENS_CACHED,
            usage_data["input_tokens_cached"],
        )

    if usage_data["output_tokens"]:
        span.set_data(SPANDATA.GEN_AI_USAGE_OUTPUT_TOKENS, usage_data["output_tokens"])

    if usage_data["output_tokens_reasoning"]:
        span.set_data(
            SPANDATA.GEN_AI_USAGE_OUTPUT_TOKENS_REASONING,
            usage_data["output_tokens_reasoning"],
        )

    if usage_data["total_tokens"]:
        span.set_data(SPANDATA.GEN_AI_USAGE_TOTAL_TOKENS, usage_data["total_tokens"])


def prepare_generate_content_args(
    args: "tuple[Any, ...]", kwargs: "dict[str, Any]"
) -> "tuple[Any, Any, str]":
    """Extract and prepare common arguments for generate_content methods."""
    model = args[0] if args else kwargs.get("model", "unknown")
    contents = args[1] if len(args) > 1 else kwargs.get("contents")
    model_name = get_model_name(model)

    config = kwargs.get("config")
    wrapped_config = wrapped_config_with_tools(config)
    if wrapped_config is not config:
        kwargs["config"] = wrapped_config

    return model, contents, model_name


def prepare_embed_content_args(
    args: "tuple[Any, ...]", kwargs: "dict[str, Any]"
) -> "tuple[str, Any]":
    """Extract and prepare common arguments for embed_content methods.

    Returns:
        tuple: (model_name, contents)
    """
    model = kwargs.get("model", "unknown")
    contents = kwargs.get("contents")
    model_name = get_model_name(model)

    return model_name, contents


def set_span_data_for_embed_request(
    span: "Span", integration: "Any", contents: "Any", kwargs: "dict[str, Any]"
) -> None:
    """Set span data for embedding request."""
    # Include input contents if PII is allowed
    if should_send_default_pii() and integration.include_prompts:
        if contents:
            # For embeddings, contents is typically a list of strings/texts
            input_texts = []

            # Handle various content formats
            if isinstance(contents, str):
                input_texts = [contents]
            elif isinstance(contents, list):
                for item in contents:
                    text = extract_contents_text(item)
                    if text:
                        input_texts.append(text)
            else:
                text = extract_contents_text(contents)
                if text:
                    input_texts = [text]

            if input_texts:
                set_data_normalized(
                    span,
                    SPANDATA.GEN_AI_EMBEDDINGS_INPUT,
                    input_texts,
                    unpack=False,
                )


def set_span_data_for_embed_response(
    span: "Span", integration: "Any", response: "EmbedContentResponse"
) -> None:
    """Set span data for embedding response."""
    if not response:
        return

    # Extract token counts from embeddings statistics (Vertex AI only)
    # Each embedding has its own statistics with token_count
    if hasattr(response, "embeddings") and response.embeddings:
        total_tokens = 0

        for embedding in response.embeddings:
            if hasattr(embedding, "statistics") and embedding.statistics:
                token_count = getattr(embedding.statistics, "token_count", None)
                if token_count is not None:
                    total_tokens += int(token_count)

        # Set token count if we found any
        if total_tokens > 0:
            span.set_data(SPANDATA.GEN_AI_USAGE_INPUT_TOKENS, total_tokens)
