"""
Anthropic provider: builds LangChain ChatAnthropic from app settings.
"""

from classes.logger import log


def is_available(model_id, settings):
    """Return True if Anthropic is configured (API key set) and model_id is for this provider."""
    if not model_id.startswith("anthropic/"):
        return False
    key = (settings.get("anthropic-api-key") or "").strip()
    return bool(key)


def build_chat_model(model_id, settings):
    """Build ChatAnthropic for the given model_id. Requires anthropic-api-key in settings."""
    try:
        from langchain_anthropic import ChatAnthropic
    except ImportError:
        log.warning("langchain-anthropic not installed")
        return None

    api_key = (settings.get("anthropic-api-key") or "").strip()
    if not api_key:
        return None

    model_name = model_id.split("/", 1)[-1] if "/" in model_id else model_id

    return ChatAnthropic(
        model=model_name,
        api_key=api_key,
        temperature=0.2,
    )
