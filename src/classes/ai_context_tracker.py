"""
Context window tracker for AI chat sessions.

Provides per-model token limits, token counting (tiktoken for OpenAI,
approximation for others), and usage-fraction helpers used by the
context-progress ring in the chat UI.
"""

from typing import List, Dict, Any, Optional
from classes.logger import log

# ---------------------------------------------------------------------------
# Per-model context-window sizes (max input tokens)
# ---------------------------------------------------------------------------
MODEL_CONTEXT_LIMITS: Dict[str, int] = {
    "openai/gpt-4o-mini": 128_000,
    "openai/gpt-4o": 128_000,
    "anthropic/claude-3-5-sonnet": 200_000,
    "anthropic/claude-3-haiku": 200_000,
    "ollama/llama3.2": 128_000,
    "ollama/llama3.1": 128_000,
}

# When usage fraction reaches this value the UI shows a carry-forward prompt
CARRY_FORWARD_THRESHOLD: float = 0.85

# Fallback context limit for unknown models
DEFAULT_CONTEXT_LIMIT: int = 128_000

# Approximate chars-per-token for non-OpenAI models
_APPROX_CHARS_PER_TOKEN: float = 4.0

# ---------------------------------------------------------------------------
# tiktoken cache (lazy-loaded)
# ---------------------------------------------------------------------------
_tiktoken_encodings: Dict[str, Any] = {}


def _get_tiktoken_encoding(model_id: str):
    """Return a tiktoken encoding for an OpenAI model, or None."""
    if model_id in _tiktoken_encodings:
        return _tiktoken_encodings[model_id]
    try:
        import tiktoken
    except ImportError:
        _tiktoken_encodings[model_id] = None
        return None
    # Map model_id -> tiktoken model name
    tiktoken_model_map = {
        "openai/gpt-4o-mini": "gpt-4o-mini",
        "openai/gpt-4o": "gpt-4o",
    }
    tiktoken_name = tiktoken_model_map.get(model_id)
    if tiktoken_name is None:
        _tiktoken_encodings[model_id] = None
        return None
    try:
        enc = tiktoken.encoding_for_model(tiktoken_name)
        _tiktoken_encodings[model_id] = enc
        return enc
    except Exception as exc:
        log.debug("tiktoken encoding lookup failed for %s: %s", tiktoken_name, exc)
        _tiktoken_encodings[model_id] = None
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_limit(model_id: str) -> int:
    """Return the context-window token limit for *model_id*."""
    return MODEL_CONTEXT_LIMITS.get(model_id, DEFAULT_CONTEXT_LIMIT)


def count_tokens_for_text(model_id: str, text: str) -> int:
    """Count tokens in a single string of text."""
    enc = _get_tiktoken_encoding(model_id)
    if enc is not None:
        try:
            return len(enc.encode(text))
        except Exception:
            pass
    # Fallback: character-based approximation
    return max(1, int(len(text) / _APPROX_CHARS_PER_TOKEN))


def count_tokens(model_id: str, messages: List[Dict[str, Any]]) -> int:
    """
    Estimate total token count for a list of chat messages.

    Each message dict is expected to have at least a ``"content"`` key.
    An extra ~4 tokens per message is added to account for role/metadata
    overhead (matching the OpenAI chat-completion token-counting guide).
    """
    PER_MESSAGE_OVERHEAD = 4
    total = 0
    for msg in messages:
        content = msg.get("content", "") or ""
        if isinstance(content, list):
            # Multi-part content (e.g. vision messages)
            content = " ".join(
                part.get("text", "") for part in content if isinstance(part, dict)
            )
        total += count_tokens_for_text(model_id, content) + PER_MESSAGE_OVERHEAD
    # Add a small base overhead for the conversation envelope
    total += 3
    return total


def get_usage_fraction(model_id: str, messages: List[Dict[str, Any]]) -> float:
    """
    Return a value in [0.0, 1.0] representing how much of the model's
    context window is currently used by *messages*.
    """
    limit = get_limit(model_id)
    if limit <= 0:
        return 0.0
    used = count_tokens(model_id, messages)
    return min(1.0, used / limit)


def get_usage_info(model_id: str, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Return a dict with ``used``, ``total``, and ``fraction`` suitable
    for pushing to the frontend context-progress ring.
    """
    limit = get_limit(model_id)
    used = count_tokens(model_id, messages)
    fraction = min(1.0, used / limit) if limit > 0 else 0.0
    return {
        "used": used,
        "total": limit,
        "fraction": round(fraction, 4),
    }


def should_carry_forward(model_id: str, messages: List[Dict[str, Any]]) -> bool:
    """Return True when the conversation is at or above the carry-forward threshold."""
    return get_usage_fraction(model_id, messages) >= CARRY_FORWARD_THRESHOLD
