import copy
from typing import TYPE_CHECKING

import sentry_sdk
from sentry_sdk import consts
from sentry_sdk.ai.monitoring import record_token_usage
from sentry_sdk.ai.utils import (
    get_start_span_function,
    set_data_normalized,
    truncate_and_annotate_messages,
    transform_openai_content_part,
    truncate_and_annotate_embedding_inputs,
)
from sentry_sdk.consts import SPANDATA
from sentry_sdk.integrations import DidNotEnable, Integration
from sentry_sdk.scope import should_send_default_pii
from sentry_sdk.utils import event_from_exception

if TYPE_CHECKING:
    from typing import Any, Dict, List
    from datetime import datetime

try:
    import litellm  # type: ignore[import-not-found]
    from litellm import input_callback, success_callback, failure_callback
except ImportError:
    raise DidNotEnable("LiteLLM not installed")


def _get_metadata_dict(kwargs: "Dict[str, Any]") -> "Dict[str, Any]":
    """Get the metadata dictionary from the kwargs."""
    litellm_params = kwargs.setdefault("litellm_params", {})

    # we need this weird little dance, as metadata might be set but may be None initially
    metadata = litellm_params.get("metadata")
    if metadata is None:
        metadata = {}
        litellm_params["metadata"] = metadata
    return metadata


def _convert_message_parts(messages: "List[Dict[str, Any]]") -> "List[Dict[str, Any]]":
    """
    Convert the message parts from OpenAI format to the `gen_ai.request.messages` format
    using the OpenAI-specific transformer (LiteLLM uses OpenAI's message format).

    Deep copies messages to avoid mutating original kwargs.
    """
    # Deep copy to avoid mutating original messages from kwargs
    messages = copy.deepcopy(messages)

    for message in messages:
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if isinstance(content, (list, tuple)):
            transformed = []
            for item in content:
                if isinstance(item, dict):
                    result = transform_openai_content_part(item)
                    # If transformation succeeded, use the result; otherwise keep original
                    transformed.append(result if result is not None else item)
                else:
                    transformed.append(item)
            message["content"] = transformed
    return messages


def _input_callback(kwargs: "Dict[str, Any]") -> None:
    """Handle the start of a request."""
    integration = sentry_sdk.get_client().get_integration(LiteLLMIntegration)

    if integration is None:
        return

    # Get key parameters
    full_model = kwargs.get("model", "")
    try:
        model, provider, _, _ = litellm.get_llm_provider(full_model)
    except Exception:
        model = full_model
        provider = "unknown"

    call_type = kwargs.get("call_type", None)
    if call_type == "embedding":
        operation = "embeddings"
    else:
        operation = "chat"

    # Start a new span/transaction
    span = get_start_span_function()(
        op=(
            consts.OP.GEN_AI_CHAT
            if operation == "chat"
            else consts.OP.GEN_AI_EMBEDDINGS
        ),
        name=f"{operation} {model}",
        origin=LiteLLMIntegration.origin,
    )
    span.__enter__()

    # Store span for later
    _get_metadata_dict(kwargs)["_sentry_span"] = span

    # Set basic data
    set_data_normalized(span, SPANDATA.GEN_AI_SYSTEM, provider)
    set_data_normalized(span, SPANDATA.GEN_AI_OPERATION_NAME, operation)

    # Record input/messages if allowed
    if should_send_default_pii() and integration.include_prompts:
        if operation == "embeddings":
            # For embeddings, look for the 'input' parameter
            embedding_input = kwargs.get("input")
            if embedding_input:
                scope = sentry_sdk.get_current_scope()
                # Normalize to list format
                input_list = (
                    embedding_input
                    if isinstance(embedding_input, list)
                    else [embedding_input]
                )
                messages_data = truncate_and_annotate_embedding_inputs(
                    input_list, span, scope
                )
                if messages_data is not None:
                    set_data_normalized(
                        span,
                        SPANDATA.GEN_AI_EMBEDDINGS_INPUT,
                        messages_data,
                        unpack=False,
                    )
        else:
            # For chat, look for the 'messages' parameter
            messages = kwargs.get("messages", [])
            if messages:
                scope = sentry_sdk.get_current_scope()
                messages = _convert_message_parts(messages)
                messages_data = truncate_and_annotate_messages(messages, span, scope)
                if messages_data is not None:
                    set_data_normalized(
                        span,
                        SPANDATA.GEN_AI_REQUEST_MESSAGES,
                        messages_data,
                        unpack=False,
                    )

    # Record other parameters
    params = {
        "model": SPANDATA.GEN_AI_REQUEST_MODEL,
        "stream": SPANDATA.GEN_AI_RESPONSE_STREAMING,
        "max_tokens": SPANDATA.GEN_AI_REQUEST_MAX_TOKENS,
        "presence_penalty": SPANDATA.GEN_AI_REQUEST_PRESENCE_PENALTY,
        "frequency_penalty": SPANDATA.GEN_AI_REQUEST_FREQUENCY_PENALTY,
        "temperature": SPANDATA.GEN_AI_REQUEST_TEMPERATURE,
        "top_p": SPANDATA.GEN_AI_REQUEST_TOP_P,
    }
    for key, attribute in params.items():
        value = kwargs.get(key)
        if value is not None:
            set_data_normalized(span, attribute, value)

    # Record LiteLLM-specific parameters
    litellm_params = {
        "api_base": kwargs.get("api_base"),
        "api_version": kwargs.get("api_version"),
        "custom_llm_provider": kwargs.get("custom_llm_provider"),
    }
    for key, value in litellm_params.items():
        if value is not None:
            set_data_normalized(span, f"gen_ai.litellm.{key}", value)


def _success_callback(
    kwargs: "Dict[str, Any]",
    completion_response: "Any",
    start_time: "datetime",
    end_time: "datetime",
) -> None:
    """Handle successful completion."""

    span = _get_metadata_dict(kwargs).get("_sentry_span")
    if span is None:
        return

    integration = sentry_sdk.get_client().get_integration(LiteLLMIntegration)
    if integration is None:
        return

    try:
        # Record model information
        if hasattr(completion_response, "model"):
            set_data_normalized(
                span, SPANDATA.GEN_AI_RESPONSE_MODEL, completion_response.model
            )

        # Record response content if allowed
        if should_send_default_pii() and integration.include_prompts:
            if hasattr(completion_response, "choices"):
                response_messages = []
                for choice in completion_response.choices:
                    if hasattr(choice, "message"):
                        if hasattr(choice.message, "model_dump"):
                            response_messages.append(choice.message.model_dump())
                        elif hasattr(choice.message, "dict"):
                            response_messages.append(choice.message.dict())
                        else:
                            # Fallback for basic message objects
                            msg = {}
                            if hasattr(choice.message, "role"):
                                msg["role"] = choice.message.role
                            if hasattr(choice.message, "content"):
                                msg["content"] = choice.message.content
                            if hasattr(choice.message, "tool_calls"):
                                msg["tool_calls"] = choice.message.tool_calls
                            response_messages.append(msg)

                if response_messages:
                    set_data_normalized(
                        span, SPANDATA.GEN_AI_RESPONSE_TEXT, response_messages
                    )

        # Record token usage
        if hasattr(completion_response, "usage"):
            usage = completion_response.usage
            record_token_usage(
                span,
                input_tokens=getattr(usage, "prompt_tokens", None),
                output_tokens=getattr(usage, "completion_tokens", None),
                total_tokens=getattr(usage, "total_tokens", None),
            )

    finally:
        # Always finish the span and clean up
        span.__exit__(None, None, None)


def _failure_callback(
    kwargs: "Dict[str, Any]",
    exception: Exception,
    start_time: "datetime",
    end_time: "datetime",
) -> None:
    """Handle request failure."""
    span = _get_metadata_dict(kwargs).get("_sentry_span")
    if span is None:
        return

    try:
        # Capture the exception
        event, hint = event_from_exception(
            exception,
            client_options=sentry_sdk.get_client().options,
            mechanism={"type": "litellm", "handled": False},
        )
        sentry_sdk.capture_event(event, hint=hint)
    finally:
        # Always finish the span and clean up
        span.__exit__(type(exception), exception, None)


class LiteLLMIntegration(Integration):
    """
    LiteLLM integration for Sentry.

    This integration automatically captures LiteLLM API calls and sends them to Sentry
    for monitoring and error tracking. It supports all 100+ LLM providers that LiteLLM
    supports, including OpenAI, Anthropic, Google, Cohere, and many others.

    Features:
    - Automatic exception capture for all LiteLLM calls
    - Token usage tracking across all providers
    - Provider detection and attribution
    - Input/output message capture (configurable)
    - Streaming response support
    - Cost tracking integration

    Usage:

    ```python
    import litellm
    import sentry_sdk

    # Initialize Sentry with the LiteLLM integration
    sentry_sdk.init(
        dsn="your-dsn",
        send_default_pii=True
        integrations=[
            sentry_sdk.integrations.LiteLLMIntegration(
                include_prompts=True  # Set to False to exclude message content
            )
        ]
    )

    # All LiteLLM calls will now be monitored
    response = litellm.completion(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": "Hello!"}]
    )
    ```

    Configuration:
    - include_prompts (bool): Whether to include prompts and responses in spans.
      Defaults to True. Set to False to exclude potentially sensitive data.
    """

    identifier = "litellm"
    origin = f"auto.ai.{identifier}"

    def __init__(self: "LiteLLMIntegration", include_prompts: bool = True) -> None:
        self.include_prompts = include_prompts

    @staticmethod
    def setup_once() -> None:
        """Set up LiteLLM callbacks for monitoring."""
        litellm.input_callback = input_callback or []
        if _input_callback not in litellm.input_callback:
            litellm.input_callback.append(_input_callback)

        litellm.success_callback = success_callback or []
        if _success_callback not in litellm.success_callback:
            litellm.success_callback.append(_success_callback)

        litellm.failure_callback = failure_callback or []
        if _failure_callback not in litellm.failure_callback:
            litellm.failure_callback.append(_failure_callback)
