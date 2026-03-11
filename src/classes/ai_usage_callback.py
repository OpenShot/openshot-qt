"""
LangChain callback handler that records token usage to UsageTracker after
every LLM call.  Injected once at the registry level — covers all providers.

Supports OpenAI and Anthropic token-usage formats.  Ollama/NVIDIA-edge calls
are also captured but their cost will be $0 (no pricing row for local models).
"""

import logging
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

from classes.usage_tracker import UsageTracker

log = logging.getLogger(__name__)


def _provider_from_model(model_name: str) -> str:
    """Infer provider from model name string."""
    name = (model_name or "").lower()
    if "gpt" in name or "openai" in name:
        return "openai"
    if "claude" in name or "anthropic" in name:
        return "anthropic"
    if "gemini" in name or "google" in name:
        return "google"
    if "llama" in name or "ollama" in name:
        return "ollama"
    if "nemotron" in name or "llava" in name or "nvidia" in name:
        return "nvidia-edge"
    return "unknown"


class ZenviUsageCallback(BaseCallbackHandler):
    """
    Captures token usage from LLM responses and logs them to UsageTracker.

    Usage:
        model = ChatOpenAI(...)
        model = model.with_config(callbacks=[ZenviUsageCallback()])
    """

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        try:
            llm_output = response.llm_output or {}

            # ── Model name ─────────────────────────────────────────────────────
            model_name = (
                llm_output.get("model_name")
                or llm_output.get("model")
                or kwargs.get("invocation_params", {}).get("model_name", "")
                or kwargs.get("invocation_params", {}).get("model", "")
                or "unknown"
            )

            # ── Token counts ───────────────────────────────────────────────────
            # OpenAI format: token_usage.{prompt_tokens, completion_tokens}
            # Anthropic format: usage.{input_tokens, output_tokens}
            usage = llm_output.get("token_usage") or llm_output.get("usage") or {}

            input_tokens = int(
                usage.get("prompt_tokens")
                or usage.get("input_tokens")
                or 0
            )
            output_tokens = int(
                usage.get("completion_tokens")
                or usage.get("output_tokens")
                or 0
            )

            # Skip if no meaningful usage to record
            if input_tokens == 0 and output_tokens == 0:
                return

            provider = _provider_from_model(model_name)

            UsageTracker.instance().record(
                provider=provider,
                model=model_name,
                operation="chat",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )

        except Exception as exc:
            # Never let tracking errors surface to the user
            log.debug("ZenviUsageCallback: failed to record usage: %s", exc)
