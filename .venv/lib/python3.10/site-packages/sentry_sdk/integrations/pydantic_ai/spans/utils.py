"""Utility functions for PydanticAI span instrumentation."""

import sentry_sdk
from sentry_sdk.consts import SPANDATA

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Union, Dict, Any, List
    from pydantic_ai.usage import RequestUsage, RunUsage  # type: ignore


def _set_usage_data(
    span: "sentry_sdk.tracing.Span", usage: "Union[RequestUsage, RunUsage]"
) -> None:
    """Set token usage data on a span.

    This function works with both RequestUsage (single request) and
    RunUsage (agent run) objects from pydantic_ai.

    Args:
        span: The Sentry span to set data on.
        usage: RequestUsage or RunUsage object containing token usage information.
    """
    if usage is None:
        return

    if hasattr(usage, "input_tokens") and usage.input_tokens is not None:
        span.set_data(SPANDATA.GEN_AI_USAGE_INPUT_TOKENS, usage.input_tokens)

    # Pydantic AI uses cache_read_tokens (not input_tokens_cached)
    if hasattr(usage, "cache_read_tokens") and usage.cache_read_tokens is not None:
        span.set_data(
            SPANDATA.GEN_AI_USAGE_INPUT_TOKENS_CACHED, usage.cache_read_tokens
        )

    # Pydantic AI uses cache_write_tokens (not input_tokens_cache_write)
    if hasattr(usage, "cache_write_tokens") and usage.cache_write_tokens is not None:
        span.set_data(
            SPANDATA.GEN_AI_USAGE_INPUT_TOKENS_CACHE_WRITE,
            usage.cache_write_tokens,
        )

    if hasattr(usage, "output_tokens") and usage.output_tokens is not None:
        span.set_data(SPANDATA.GEN_AI_USAGE_OUTPUT_TOKENS, usage.output_tokens)

    if hasattr(usage, "total_tokens") and usage.total_tokens is not None:
        span.set_data(SPANDATA.GEN_AI_USAGE_TOTAL_TOKENS, usage.total_tokens)
