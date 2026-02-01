"""
OpenAI provider: builds LangChain ChatOpenAI from app settings.
"""

from classes.logger import log


def is_available(model_id, settings):
    """Return True if OpenAI is configured (API key set) and model_id is for this provider."""
    if not model_id.startswith("openai/"):
        return False
    key = (settings.get("openai-api-key") or "").strip()
    return bool(key)


def build_chat_model(model_id, settings):
    """Build ChatOpenAI for the given model_id. Requires openai-api-key in settings."""
    try:
        from langchain_openai import ChatOpenAI
    except ImportError:
        log.warning("langchain-openai not installed")
        return None

    api_key = (settings.get("openai-api-key") or "").strip()
    if not api_key:
        return None

    # model_id is e.g. "openai/gpt-4o-mini" -> model name "gpt-4o-mini"
    model_name = model_id.split("/", 1)[-1] if "/" in model_id else model_id

    return ChatOpenAI(
        model=model_name,
        api_key=api_key,
        temperature=0.2,
    )
