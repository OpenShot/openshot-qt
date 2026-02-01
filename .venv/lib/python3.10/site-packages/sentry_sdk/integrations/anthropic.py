import sys
import json
from collections.abc import Iterable
from functools import wraps
from typing import TYPE_CHECKING

import sentry_sdk
from sentry_sdk.ai.monitoring import record_token_usage
from sentry_sdk.ai.utils import (
    GEN_AI_ALLOWED_MESSAGE_ROLES,
    set_data_normalized,
    normalize_message_roles,
    truncate_and_annotate_messages,
    get_start_span_function,
    transform_anthropic_content_part,
)
from sentry_sdk.consts import OP, SPANDATA, SPANSTATUS
from sentry_sdk.integrations import _check_minimum_version, DidNotEnable, Integration
from sentry_sdk.scope import should_send_default_pii
from sentry_sdk.tracing_utils import set_span_errored
from sentry_sdk.utils import (
    capture_internal_exceptions,
    event_from_exception,
    package_version,
    safe_serialize,
    reraise,
)

try:
    try:
        from anthropic import NotGiven
    except ImportError:
        NotGiven = None

    try:
        from anthropic import Omit
    except ImportError:
        Omit = None

    from anthropic.resources import AsyncMessages, Messages

    if TYPE_CHECKING:
        from anthropic.types import MessageStreamEvent, TextBlockParam
except ImportError:
    raise DidNotEnable("Anthropic not installed")

if TYPE_CHECKING:
    from typing import Any, AsyncIterator, Iterator, List, Optional, Union
    from sentry_sdk.tracing import Span
    from sentry_sdk._types import TextPart


class AnthropicIntegration(Integration):
    identifier = "anthropic"
    origin = f"auto.ai.{identifier}"

    def __init__(self: "AnthropicIntegration", include_prompts: bool = True) -> None:
        self.include_prompts = include_prompts

    @staticmethod
    def setup_once() -> None:
        version = package_version("anthropic")
        _check_minimum_version(AnthropicIntegration, version)

        Messages.create = _wrap_message_create(Messages.create)
        AsyncMessages.create = _wrap_message_create_async(AsyncMessages.create)


def _capture_exception(exc: "Any") -> None:
    set_span_errored()

    event, hint = event_from_exception(
        exc,
        client_options=sentry_sdk.get_client().options,
        mechanism={"type": "anthropic", "handled": False},
    )
    sentry_sdk.capture_event(event, hint=hint)


def _get_token_usage(result: "Messages") -> "tuple[int, int, int, int]":
    """
    Get token usage from the Anthropic response.
    Returns: (input_tokens, output_tokens, cache_read_input_tokens, cache_write_input_tokens)
    """
    input_tokens = 0
    output_tokens = 0
    cache_read_input_tokens = 0
    cache_write_input_tokens = 0
    if hasattr(result, "usage"):
        usage = result.usage
        if hasattr(usage, "input_tokens") and isinstance(usage.input_tokens, int):
            input_tokens = usage.input_tokens
        if hasattr(usage, "output_tokens") and isinstance(usage.output_tokens, int):
            output_tokens = usage.output_tokens
        if hasattr(usage, "cache_read_input_tokens") and isinstance(
            usage.cache_read_input_tokens, int
        ):
            cache_read_input_tokens = usage.cache_read_input_tokens
        if hasattr(usage, "cache_creation_input_tokens") and isinstance(
            usage.cache_creation_input_tokens, int
        ):
            cache_write_input_tokens = usage.cache_creation_input_tokens

    return (
        input_tokens,
        output_tokens,
        cache_read_input_tokens,
        cache_write_input_tokens,
    )


def _collect_ai_data(
    event: "MessageStreamEvent",
    model: "str | None",
    input_tokens: int,
    output_tokens: int,
    cache_read_input_tokens: int,
    cache_write_input_tokens: int,
    content_blocks: "list[str]",
) -> "tuple[str | None, int, int, int, int, list[str]]":
    """
    Collect model information, token usage, and collect content blocks from the AI streaming response.
    """
    with capture_internal_exceptions():
        if hasattr(event, "type"):
            if event.type == "message_start":
                usage = event.message.usage
                input_tokens += usage.input_tokens
                output_tokens += usage.output_tokens
                if hasattr(usage, "cache_read_input_tokens") and isinstance(
                    usage.cache_read_input_tokens, int
                ):
                    cache_read_input_tokens += usage.cache_read_input_tokens
                if hasattr(usage, "cache_creation_input_tokens") and isinstance(
                    usage.cache_creation_input_tokens, int
                ):
                    cache_write_input_tokens += usage.cache_creation_input_tokens
                model = event.message.model or model
            elif event.type == "content_block_start":
                pass
            elif event.type == "content_block_delta":
                if hasattr(event.delta, "text"):
                    content_blocks.append(event.delta.text)
                elif hasattr(event.delta, "partial_json"):
                    content_blocks.append(event.delta.partial_json)
            elif event.type == "content_block_stop":
                pass
            elif event.type == "message_delta":
                output_tokens += event.usage.output_tokens

    return (
        model,
        input_tokens,
        output_tokens,
        cache_read_input_tokens,
        cache_write_input_tokens,
        content_blocks,
    )


def _transform_anthropic_content_block(
    content_block: "dict[str, Any]",
) -> "dict[str, Any]":
    """
    Transform an Anthropic content block using the Anthropic-specific transformer,
    with special handling for Anthropic's text-type documents.
    """
    # Handle Anthropic's text-type documents specially (not covered by shared function)
    if content_block.get("type") == "document":
        source = content_block.get("source")
        if isinstance(source, dict) and source.get("type") == "text":
            return {
                "type": "text",
                "text": source.get("data", ""),
            }

    # Use Anthropic-specific transformation
    result = transform_anthropic_content_part(content_block)
    return result if result is not None else content_block


def _transform_system_instructions(
    system_instructions: "Union[str, Iterable[TextBlockParam]]",
) -> "list[TextPart]":
    if isinstance(system_instructions, str):
        return [
            {
                "type": "text",
                "content": system_instructions,
            }
        ]

    return [
        {
            "type": "text",
            "content": instruction["text"],
        }
        for instruction in system_instructions
        if isinstance(instruction, dict) and "text" in instruction
    ]


def _set_input_data(
    span: "Span", kwargs: "dict[str, Any]", integration: "AnthropicIntegration"
) -> None:
    """
    Set input data for the span based on the provided keyword arguments for the anthropic message creation.
    """
    set_data_normalized(span, SPANDATA.GEN_AI_OPERATION_NAME, "chat")
    system_instructions: "Union[str, Iterable[TextBlockParam]]" = kwargs.get("system")  # type: ignore
    messages = kwargs.get("messages")
    if (
        messages is not None
        and len(messages) > 0
        and should_send_default_pii()
        and integration.include_prompts
    ):
        if isinstance(system_instructions, str) or isinstance(
            system_instructions, Iterable
        ):
            span.set_data(
                SPANDATA.GEN_AI_SYSTEM_INSTRUCTIONS,
                json.dumps(_transform_system_instructions(system_instructions)),
            )

        normalized_messages = []
        for message in messages:
            if (
                message.get("role") == GEN_AI_ALLOWED_MESSAGE_ROLES.USER
                and "content" in message
                and isinstance(message["content"], (list, tuple))
            ):
                transformed_content = []
                for item in message["content"]:
                    # Skip tool_result items - they can contain images/documents
                    # with nested structures that are difficult to redact properly
                    if isinstance(item, dict) and item.get("type") == "tool_result":
                        continue

                    # Transform content blocks (images, documents, etc.)
                    transformed_content.append(
                        _transform_anthropic_content_block(item)
                        if isinstance(item, dict)
                        else item
                    )

                # If there are non-tool-result items, add them as a message
                if transformed_content:
                    normalized_messages.append(
                        {
                            "role": message.get("role"),
                            "content": transformed_content,
                        }
                    )
            else:
                # Transform content for non-list messages or assistant messages
                transformed_message = message.copy()
                if "content" in transformed_message:
                    content = transformed_message["content"]
                    if isinstance(content, (list, tuple)):
                        transformed_message["content"] = [
                            _transform_anthropic_content_block(item)
                            if isinstance(item, dict)
                            else item
                            for item in content
                        ]
                normalized_messages.append(transformed_message)

        role_normalized_messages = normalize_message_roles(normalized_messages)
        scope = sentry_sdk.get_current_scope()
        messages_data = truncate_and_annotate_messages(
            role_normalized_messages, span, scope
        )
        if messages_data is not None:
            set_data_normalized(
                span, SPANDATA.GEN_AI_REQUEST_MESSAGES, messages_data, unpack=False
            )

    set_data_normalized(
        span, SPANDATA.GEN_AI_RESPONSE_STREAMING, kwargs.get("stream", False)
    )

    kwargs_keys_to_attributes = {
        "max_tokens": SPANDATA.GEN_AI_REQUEST_MAX_TOKENS,
        "model": SPANDATA.GEN_AI_REQUEST_MODEL,
        "temperature": SPANDATA.GEN_AI_REQUEST_TEMPERATURE,
        "top_k": SPANDATA.GEN_AI_REQUEST_TOP_K,
        "top_p": SPANDATA.GEN_AI_REQUEST_TOP_P,
    }
    for key, attribute in kwargs_keys_to_attributes.items():
        value = kwargs.get(key)

        if value is not None and _is_given(value):
            set_data_normalized(span, attribute, value)

    # Input attributes: Tools
    tools = kwargs.get("tools")
    if tools is not None and _is_given(tools) and len(tools) > 0:
        set_data_normalized(
            span, SPANDATA.GEN_AI_REQUEST_AVAILABLE_TOOLS, safe_serialize(tools)
        )


def _set_output_data(
    span: "Span",
    integration: "AnthropicIntegration",
    model: "str | None",
    input_tokens: "int | None",
    output_tokens: "int | None",
    cache_read_input_tokens: "int | None",
    cache_write_input_tokens: "int | None",
    content_blocks: "list[Any]",
    finish_span: bool = False,
) -> None:
    """
    Set output data for the span based on the AI response."""
    span.set_data(SPANDATA.GEN_AI_RESPONSE_MODEL, model)
    if should_send_default_pii() and integration.include_prompts:
        output_messages: "dict[str, list[Any]]" = {
            "response": [],
            "tool": [],
        }

        for output in content_blocks:
            if output["type"] == "text":
                output_messages["response"].append(output["text"])
            elif output["type"] == "tool_use":
                output_messages["tool"].append(output)

        if len(output_messages["tool"]) > 0:
            set_data_normalized(
                span,
                SPANDATA.GEN_AI_RESPONSE_TOOL_CALLS,
                output_messages["tool"],
                unpack=False,
            )

        if len(output_messages["response"]) > 0:
            set_data_normalized(
                span, SPANDATA.GEN_AI_RESPONSE_TEXT, output_messages["response"]
            )

    record_token_usage(
        span,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        input_tokens_cached=cache_read_input_tokens,
        input_tokens_cache_write=cache_write_input_tokens,
    )

    if finish_span:
        span.__exit__(None, None, None)


def _sentry_patched_create_common(f: "Any", *args: "Any", **kwargs: "Any") -> "Any":
    integration = kwargs.pop("integration")
    if integration is None:
        return f(*args, **kwargs)

    if "messages" not in kwargs:
        return f(*args, **kwargs)

    try:
        iter(kwargs["messages"])
    except TypeError:
        return f(*args, **kwargs)

    model = kwargs.get("model", "")

    span = get_start_span_function()(
        op=OP.GEN_AI_CHAT,
        name=f"chat {model}".strip(),
        origin=AnthropicIntegration.origin,
    )
    span.__enter__()

    _set_input_data(span, kwargs, integration)

    result = yield f, args, kwargs

    with capture_internal_exceptions():
        if hasattr(result, "content"):
            (
                input_tokens,
                output_tokens,
                cache_read_input_tokens,
                cache_write_input_tokens,
            ) = _get_token_usage(result)

            content_blocks = []
            for content_block in result.content:
                if hasattr(content_block, "to_dict"):
                    content_blocks.append(content_block.to_dict())
                elif hasattr(content_block, "model_dump"):
                    content_blocks.append(content_block.model_dump())
                elif hasattr(content_block, "text"):
                    content_blocks.append({"type": "text", "text": content_block.text})

            _set_output_data(
                span=span,
                integration=integration,
                model=getattr(result, "model", None),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cache_read_input_tokens=cache_read_input_tokens,
                cache_write_input_tokens=cache_write_input_tokens,
                content_blocks=content_blocks,
                finish_span=True,
            )

        # Streaming response
        elif hasattr(result, "_iterator"):
            old_iterator = result._iterator

            def new_iterator() -> "Iterator[MessageStreamEvent]":
                model = None
                input_tokens = 0
                output_tokens = 0
                cache_read_input_tokens = 0
                cache_write_input_tokens = 0
                content_blocks: "list[str]" = []

                for event in old_iterator:
                    (
                        model,
                        input_tokens,
                        output_tokens,
                        cache_read_input_tokens,
                        cache_write_input_tokens,
                        content_blocks,
                    ) = _collect_ai_data(
                        event,
                        model,
                        input_tokens,
                        output_tokens,
                        cache_read_input_tokens,
                        cache_write_input_tokens,
                        content_blocks,
                    )
                    yield event

                _set_output_data(
                    span=span,
                    integration=integration,
                    model=model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cache_read_input_tokens=cache_read_input_tokens,
                    cache_write_input_tokens=cache_write_input_tokens,
                    content_blocks=[{"text": "".join(content_blocks), "type": "text"}],
                    finish_span=True,
                )

            async def new_iterator_async() -> "AsyncIterator[MessageStreamEvent]":
                model = None
                input_tokens = 0
                output_tokens = 0
                cache_read_input_tokens = 0
                cache_write_input_tokens = 0
                content_blocks: "list[str]" = []

                async for event in old_iterator:
                    (
                        model,
                        input_tokens,
                        output_tokens,
                        cache_read_input_tokens,
                        cache_write_input_tokens,
                        content_blocks,
                    ) = _collect_ai_data(
                        event,
                        model,
                        input_tokens,
                        output_tokens,
                        cache_read_input_tokens,
                        cache_write_input_tokens,
                        content_blocks,
                    )
                    yield event

                _set_output_data(
                    span=span,
                    integration=integration,
                    model=model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cache_read_input_tokens=cache_read_input_tokens,
                    cache_write_input_tokens=cache_write_input_tokens,
                    content_blocks=[{"text": "".join(content_blocks), "type": "text"}],
                    finish_span=True,
                )

            if str(type(result._iterator)) == "<class 'async_generator'>":
                result._iterator = new_iterator_async()
            else:
                result._iterator = new_iterator()

        else:
            span.set_data("unknown_response", True)
            span.__exit__(None, None, None)

    return result


def _wrap_message_create(f: "Any") -> "Any":
    def _execute_sync(f: "Any", *args: "Any", **kwargs: "Any") -> "Any":
        gen = _sentry_patched_create_common(f, *args, **kwargs)

        try:
            f, args, kwargs = next(gen)
        except StopIteration as e:
            return e.value

        try:
            try:
                result = f(*args, **kwargs)
            except Exception as exc:
                exc_info = sys.exc_info()
                with capture_internal_exceptions():
                    _capture_exception(exc)
                reraise(*exc_info)

            return gen.send(result)
        except StopIteration as e:
            return e.value

    @wraps(f)
    def _sentry_patched_create_sync(*args: "Any", **kwargs: "Any") -> "Any":
        integration = sentry_sdk.get_client().get_integration(AnthropicIntegration)
        kwargs["integration"] = integration

        try:
            return _execute_sync(f, *args, **kwargs)
        finally:
            span = sentry_sdk.get_current_span()
            if span is not None and span.status == SPANSTATUS.INTERNAL_ERROR:
                with capture_internal_exceptions():
                    span.__exit__(None, None, None)

    return _sentry_patched_create_sync


def _wrap_message_create_async(f: "Any") -> "Any":
    async def _execute_async(f: "Any", *args: "Any", **kwargs: "Any") -> "Any":
        gen = _sentry_patched_create_common(f, *args, **kwargs)

        try:
            f, args, kwargs = next(gen)
        except StopIteration as e:
            return await e.value

        try:
            try:
                result = await f(*args, **kwargs)
            except Exception as exc:
                exc_info = sys.exc_info()
                with capture_internal_exceptions():
                    _capture_exception(exc)
                reraise(*exc_info)

            return gen.send(result)
        except StopIteration as e:
            return e.value

    @wraps(f)
    async def _sentry_patched_create_async(*args: "Any", **kwargs: "Any") -> "Any":
        integration = sentry_sdk.get_client().get_integration(AnthropicIntegration)
        kwargs["integration"] = integration

        try:
            return await _execute_async(f, *args, **kwargs)
        finally:
            span = sentry_sdk.get_current_span()
            if span is not None and span.status == SPANSTATUS.INTERNAL_ERROR:
                with capture_internal_exceptions():
                    span.__exit__(None, None, None)

    return _sentry_patched_create_async


def _is_given(obj: "Any") -> bool:
    """
    Check for givenness safely across different anthropic versions.
    """
    if NotGiven is not None and isinstance(obj, NotGiven):
        return False
    if Omit is not None and isinstance(obj, Omit):
        return False
    return True
