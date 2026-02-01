"""
Ollama provider: builds LangChain ChatOllama for local models.
"""

from classes.logger import log


def is_available(model_id, settings):
    """Return True if model_id is for Ollama (no API key required)."""
    return model_id.startswith("ollama/")


def build_chat_model(model_id, settings):
    """Build ChatOllama for the given model_id. Uses ollama-base-url from settings if set."""
    try:
        from langchain_ollama import ChatOllama
    except ImportError:
        log.warning("langchain-ollama not installed")
        return None

    base_url = (settings.get("ollama-base-url") or "http://localhost:11434").strip()
    model_name = model_id.split("/", 1)[-1] if "/" in model_id else model_id

    return ChatOllama(
        model=model_name,
        base_url=base_url,
        temperature=0.2,
    )
