import sys
import inspect
from functools import wraps

import sentry_sdk
from sentry_sdk.ai.monitoring import record_token_usage
from sentry_sdk.ai.utils import set_data_normalized
from sentry_sdk.consts import OP, SPANDATA
from sentry_sdk.integrations import DidNotEnable, Integration
from sentry_sdk.scope import should_send_default_pii
from sentry_sdk.tracing_utils import set_span_errored
from sentry_sdk.utils import (
    capture_internal_exceptions,
    event_from_exception,
    reraise,
)

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any, Callable, Iterable

try:
    import huggingface_hub.inference._client
except ImportError:
    raise DidNotEnable("Huggingface not installed")


class HuggingfaceHubIntegration(Integration):
    identifier = "huggingface_hub"
    origin = f"auto.ai.{identifier}"

    def __init__(
        self: "HuggingfaceHubIntegration", include_prompts: bool = True
    ) -> None:
        self.include_prompts = include_prompts

    @staticmethod
    def setup_once() -> None:
        # Other tasks that can be called: https://huggingface.co/docs/huggingface_hub/guides/inference#supported-providers-and-tasks
        huggingface_hub.inference._client.InferenceClient.text_generation = (
            _wrap_huggingface_task(
                huggingface_hub.inference._client.InferenceClient.text_generation,
                OP.GEN_AI_GENERATE_TEXT,
            )
        )
        huggingface_hub.inference._client.InferenceClient.chat_completion = (
            _wrap_huggingface_task(
                huggingface_hub.inference._client.InferenceClient.chat_completion,
                OP.GEN_AI_CHAT,
            )
        )


def _capture_exception(exc: "Any") -> None:
    set_span_errored()

    event, hint = event_from_exception(
        exc,
        client_options=sentry_sdk.get_client().options,
        mechanism={"type": "huggingface_hub", "handled": False},
    )
    sentry_sdk.capture_event(event, hint=hint)


def _wrap_huggingface_task(f: "Callable[..., Any]", op: str) -> "Callable[..., Any]":
    @wraps(f)
    def new_huggingface_task(*args: "Any", **kwargs: "Any") -> "Any":
        integration = sentry_sdk.get_client().get_integration(HuggingfaceHubIntegration)
        if integration is None:
            return f(*args, **kwargs)

        prompt = None
        if "prompt" in kwargs:
            prompt = kwargs["prompt"]
        elif "messages" in kwargs:
            prompt = kwargs["messages"]
        elif len(args) >= 2:
            if isinstance(args[1], str) or isinstance(args[1], list):
                prompt = args[1]

        if prompt is None:
            # invalid call, dont instrument, let it return error
            return f(*args, **kwargs)

        client = args[0]
        model = client.model or kwargs.get("model") or ""
        operation_name = op.split(".")[-1]

        span = sentry_sdk.start_span(
            op=op,
            name=f"{operation_name} {model}",
            origin=HuggingfaceHubIntegration.origin,
        )
        span.__enter__()

        span.set_data(SPANDATA.GEN_AI_OPERATION_NAME, operation_name)

        if model:
            span.set_data(SPANDATA.GEN_AI_REQUEST_MODEL, model)

        # Input attributes
        if should_send_default_pii() and integration.include_prompts:
            set_data_normalized(
                span, SPANDATA.GEN_AI_REQUEST_MESSAGES, prompt, unpack=False
            )

        attribute_mapping = {
            "tools": SPANDATA.GEN_AI_REQUEST_AVAILABLE_TOOLS,
            "frequency_penalty": SPANDATA.GEN_AI_REQUEST_FREQUENCY_PENALTY,
            "max_tokens": SPANDATA.GEN_AI_REQUEST_MAX_TOKENS,
            "presence_penalty": SPANDATA.GEN_AI_REQUEST_PRESENCE_PENALTY,
            "temperature": SPANDATA.GEN_AI_REQUEST_TEMPERATURE,
            "top_p": SPANDATA.GEN_AI_REQUEST_TOP_P,
            "top_k": SPANDATA.GEN_AI_REQUEST_TOP_K,
            "stream": SPANDATA.GEN_AI_RESPONSE_STREAMING,
        }

        for attribute, span_attribute in attribute_mapping.items():
            value = kwargs.get(attribute, None)
            if value is not None:
                if isinstance(value, (int, float, bool, str)):
                    span.set_data(span_attribute, value)
                else:
                    set_data_normalized(span, span_attribute, value, unpack=False)

        # LLM Execution
        try:
            res = f(*args, **kwargs)
        except Exception as e:
            exc_info = sys.exc_info()
            with capture_internal_exceptions():
                _capture_exception(e)
                span.__exit__(None, None, None)
            reraise(*exc_info)

        # Output attributes
        finish_reason = None
        response_model = None
        response_text_buffer: "list[str]" = []
        tokens_used = 0
        tool_calls = None
        usage = None

        with capture_internal_exceptions():
            if isinstance(res, str) and res is not None:
                response_text_buffer.append(res)

            if hasattr(res, "generated_text") and res.generated_text is not None:
                response_text_buffer.append(res.generated_text)

            if hasattr(res, "model") and res.model is not None:
                response_model = res.model

            if hasattr(res, "details") and hasattr(res.details, "finish_reason"):
                finish_reason = res.details.finish_reason

            if (
                hasattr(res, "details")
                and hasattr(res.details, "generated_tokens")
                and res.details.generated_tokens is not None
            ):
                tokens_used = res.details.generated_tokens

            if hasattr(res, "usage") and res.usage is not None:
                usage = res.usage

            if hasattr(res, "choices") and res.choices is not None:
                for choice in res.choices:
                    if hasattr(choice, "finish_reason"):
                        finish_reason = choice.finish_reason
                    if hasattr(choice, "message") and hasattr(
                        choice.message, "tool_calls"
                    ):
                        tool_calls = choice.message.tool_calls
                    if (
                        hasattr(choice, "message")
                        and hasattr(choice.message, "content")
                        and choice.message.content is not None
                    ):
                        response_text_buffer.append(choice.message.content)

            if response_model is not None:
                span.set_data(SPANDATA.GEN_AI_RESPONSE_MODEL, response_model)

            if finish_reason is not None:
                set_data_normalized(
                    span,
                    SPANDATA.GEN_AI_RESPONSE_FINISH_REASONS,
                    finish_reason,
                )

            if should_send_default_pii() and integration.include_prompts:
                if tool_calls is not None and len(tool_calls) > 0:
                    set_data_normalized(
                        span,
                        SPANDATA.GEN_AI_RESPONSE_TOOL_CALLS,
                        tool_calls,
                        unpack=False,
                    )

                if len(response_text_buffer) > 0:
                    text_response = "".join(response_text_buffer)
                    if text_response:
                        set_data_normalized(
                            span,
                            SPANDATA.GEN_AI_RESPONSE_TEXT,
                            text_response,
                        )

            if usage is not None:
                record_token_usage(
                    span,
                    input_tokens=usage.prompt_tokens,
                    output_tokens=usage.completion_tokens,
                    total_tokens=usage.total_tokens,
                )
            elif tokens_used > 0:
                record_token_usage(
                    span,
                    total_tokens=tokens_used,
                )

            # If the response is not a generator (meaning a streaming response)
            # we are done and can return the response
            if not inspect.isgenerator(res):
                span.__exit__(None, None, None)
                return res

            if kwargs.get("details", False):
                # text-generation stream output
                def new_details_iterator() -> "Iterable[Any]":
                    finish_reason = None
                    response_text_buffer: "list[str]" = []
                    tokens_used = 0

                    with capture_internal_exceptions():
                        for chunk in res:
                            if (
                                hasattr(chunk, "token")
                                and hasattr(chunk.token, "text")
                                and chunk.token.text is not None
                            ):
                                response_text_buffer.append(chunk.token.text)

                            if hasattr(chunk, "details") and hasattr(
                                chunk.details, "finish_reason"
                            ):
                                finish_reason = chunk.details.finish_reason

                            if (
                                hasattr(chunk, "details")
                                and hasattr(chunk.details, "generated_tokens")
                                and chunk.details.generated_tokens is not None
                            ):
                                tokens_used = chunk.details.generated_tokens

                            yield chunk

                        if finish_reason is not None:
                            set_data_normalized(
                                span,
                                SPANDATA.GEN_AI_RESPONSE_FINISH_REASONS,
                                finish_reason,
                            )

                        if should_send_default_pii() and integration.include_prompts:
                            if len(response_text_buffer) > 0:
                                text_response = "".join(response_text_buffer)
                                if text_response:
                                    set_data_normalized(
                                        span,
                                        SPANDATA.GEN_AI_RESPONSE_TEXT,
                                        text_response,
                                    )

                        if tokens_used > 0:
                            record_token_usage(
                                span,
                                total_tokens=tokens_used,
                            )

                    span.__exit__(None, None, None)

                return new_details_iterator()

            else:
                # chat-completion stream output
                def new_iterator() -> "Iterable[str]":
                    finish_reason = None
                    response_model = None
                    response_text_buffer: "list[str]" = []
                    tool_calls = None
                    usage = None

                    with capture_internal_exceptions():
                        for chunk in res:
                            if hasattr(chunk, "model") and chunk.model is not None:
                                response_model = chunk.model

                            if hasattr(chunk, "usage") and chunk.usage is not None:
                                usage = chunk.usage

                            if isinstance(chunk, str):
                                if chunk is not None:
                                    response_text_buffer.append(chunk)

                            if hasattr(chunk, "choices") and chunk.choices is not None:
                                for choice in chunk.choices:
                                    if (
                                        hasattr(choice, "delta")
                                        and hasattr(choice.delta, "content")
                                        and choice.delta.content is not None
                                    ):
                                        response_text_buffer.append(
                                            choice.delta.content
                                        )

                                    if (
                                        hasattr(choice, "finish_reason")
                                        and choice.finish_reason is not None
                                    ):
                                        finish_reason = choice.finish_reason

                                    if (
                                        hasattr(choice, "delta")
                                        and hasattr(choice.delta, "tool_calls")
                                        and choice.delta.tool_calls is not None
                                    ):
                                        tool_calls = choice.delta.tool_calls

                            yield chunk

                        if response_model is not None:
                            span.set_data(
                                SPANDATA.GEN_AI_RESPONSE_MODEL, response_model
                            )

                        if finish_reason is not None:
                            set_data_normalized(
                                span,
                                SPANDATA.GEN_AI_RESPONSE_FINISH_REASONS,
                                finish_reason,
                            )

                        if should_send_default_pii() and integration.include_prompts:
                            if tool_calls is not None and len(tool_calls) > 0:
                                set_data_normalized(
                                    span,
                                    SPANDATA.GEN_AI_RESPONSE_TOOL_CALLS,
                                    tool_calls,
                                    unpack=False,
                                )

                            if len(response_text_buffer) > 0:
                                text_response = "".join(response_text_buffer)
                                if text_response:
                                    set_data_normalized(
                                        span,
                                        SPANDATA.GEN_AI_RESPONSE_TEXT,
                                        text_response,
                                    )

                        if usage is not None:
                            record_token_usage(
                                span,
                                input_tokens=usage.prompt_tokens,
                                output_tokens=usage.completion_tokens,
                                total_tokens=usage.total_tokens,
                            )

                        span.__exit__(None, None, None)

                return new_iterator()

    return new_huggingface_task
