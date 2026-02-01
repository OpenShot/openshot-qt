import inspect
import sys
from functools import wraps

from sentry_sdk.consts import SPANDATA
import sentry_sdk.utils
from sentry_sdk import start_span
from sentry_sdk.tracing import Span
from sentry_sdk.utils import ContextVar, reraise, capture_internal_exceptions

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Optional, Callable, Awaitable, Any, Union, TypeVar

    F = TypeVar("F", bound=Union[Callable[..., Any], Callable[..., Awaitable[Any]]])

_ai_pipeline_name = ContextVar("ai_pipeline_name", default=None)


def set_ai_pipeline_name(name: "Optional[str]") -> None:
    _ai_pipeline_name.set(name)


def get_ai_pipeline_name() -> "Optional[str]":
    return _ai_pipeline_name.get()


def ai_track(description: str, **span_kwargs: "Any") -> "Callable[[F], F]":
    def decorator(f: "F") -> "F":
        def sync_wrapped(*args: "Any", **kwargs: "Any") -> "Any":
            curr_pipeline = _ai_pipeline_name.get()
            op = span_kwargs.pop("op", "ai.run" if curr_pipeline else "ai.pipeline")

            with start_span(name=description, op=op, **span_kwargs) as span:
                for k, v in kwargs.pop("sentry_tags", {}).items():
                    span.set_tag(k, v)
                for k, v in kwargs.pop("sentry_data", {}).items():
                    span.set_data(k, v)
                if curr_pipeline:
                    span.set_data(SPANDATA.GEN_AI_PIPELINE_NAME, curr_pipeline)
                    return f(*args, **kwargs)
                else:
                    _ai_pipeline_name.set(description)
                    try:
                        res = f(*args, **kwargs)
                    except Exception as e:
                        exc_info = sys.exc_info()
                        with capture_internal_exceptions():
                            event, hint = sentry_sdk.utils.event_from_exception(
                                e,
                                client_options=sentry_sdk.get_client().options,
                                mechanism={"type": "ai_monitoring", "handled": False},
                            )
                            sentry_sdk.capture_event(event, hint=hint)
                        reraise(*exc_info)
                    finally:
                        _ai_pipeline_name.set(None)
                    return res

        async def async_wrapped(*args: "Any", **kwargs: "Any") -> "Any":
            curr_pipeline = _ai_pipeline_name.get()
            op = span_kwargs.pop("op", "ai.run" if curr_pipeline else "ai.pipeline")

            with start_span(name=description, op=op, **span_kwargs) as span:
                for k, v in kwargs.pop("sentry_tags", {}).items():
                    span.set_tag(k, v)
                for k, v in kwargs.pop("sentry_data", {}).items():
                    span.set_data(k, v)
                if curr_pipeline:
                    span.set_data(SPANDATA.GEN_AI_PIPELINE_NAME, curr_pipeline)
                    return await f(*args, **kwargs)
                else:
                    _ai_pipeline_name.set(description)
                    try:
                        res = await f(*args, **kwargs)
                    except Exception as e:
                        exc_info = sys.exc_info()
                        with capture_internal_exceptions():
                            event, hint = sentry_sdk.utils.event_from_exception(
                                e,
                                client_options=sentry_sdk.get_client().options,
                                mechanism={"type": "ai_monitoring", "handled": False},
                            )
                            sentry_sdk.capture_event(event, hint=hint)
                        reraise(*exc_info)
                    finally:
                        _ai_pipeline_name.set(None)
                    return res

        if inspect.iscoroutinefunction(f):
            return wraps(f)(async_wrapped)  # type: ignore
        else:
            return wraps(f)(sync_wrapped)  # type: ignore

    return decorator


def record_token_usage(
    span: "Span",
    input_tokens: "Optional[int]" = None,
    input_tokens_cached: "Optional[int]" = None,
    input_tokens_cache_write: "Optional[int]" = None,
    output_tokens: "Optional[int]" = None,
    output_tokens_reasoning: "Optional[int]" = None,
    total_tokens: "Optional[int]" = None,
) -> None:
    # TODO: move pipeline name elsewhere
    ai_pipeline_name = get_ai_pipeline_name()
    if ai_pipeline_name:
        span.set_data(SPANDATA.GEN_AI_PIPELINE_NAME, ai_pipeline_name)

    if input_tokens is not None:
        span.set_data(SPANDATA.GEN_AI_USAGE_INPUT_TOKENS, input_tokens)

    if input_tokens_cached is not None:
        span.set_data(
            SPANDATA.GEN_AI_USAGE_INPUT_TOKENS_CACHED,
            input_tokens_cached,
        )

    if input_tokens_cache_write is not None:
        span.set_data(
            SPANDATA.GEN_AI_USAGE_INPUT_TOKENS_CACHE_WRITE,
            input_tokens_cache_write,
        )

    if output_tokens is not None:
        span.set_data(SPANDATA.GEN_AI_USAGE_OUTPUT_TOKENS, output_tokens)

    if output_tokens_reasoning is not None:
        span.set_data(
            SPANDATA.GEN_AI_USAGE_OUTPUT_TOKENS_REASONING,
            output_tokens_reasoning,
        )

    if total_tokens is None and input_tokens is not None and output_tokens is not None:
        total_tokens = input_tokens + output_tokens

    if total_tokens is not None:
        span.set_data(SPANDATA.GEN_AI_USAGE_TOTAL_TOKENS, total_tokens)
