"""
LLM registry: resolve model_id to a LangChain ChatModel using app settings.
"""

from classes.logger import log
from classes.ai_providers import (
    PROVIDER_LIST,
    build_model as _build_model,
    list_available_models as _list_available,
    list_all_models as _list_all_models,
)


def get_settings():
    """Get app settings without importing get_app at module load (avoid circular/early init)."""
    try:
        from classes.app import get_app
        app = get_app()
        if app and hasattr(app, "get_settings"):
            return app.get_settings()
    except Exception:
        pass
    return None


def get_model(model_id):
    """
    Return a LangChain BaseChatModel for the given model_id, or None.
    Uses app settings for API keys and base URLs.
    """
    settings = get_settings()
    if not settings:
        return None
    return _build_model(model_id, settings)


def list_models():
    """
    Return list of (model_id, display_name) for models available with current settings.
    """
    settings = get_settings()
    if not settings:
        return []
    return _list_available(settings)


def list_all_models():
    """
    Return list of (model_id, display_name) for all chat models (no API key check).
    Use for model dropdown so user can see OpenAI, Anthropic, Ollama; key is checked when sending.
    """
    return _list_all_models()


def get_default_model_id():
    """Return the default model id from settings, or first available."""
    models = list_models()
    settings = get_settings()
    if settings:
        default = settings.get("ai-default-model")
        if default and any(mid == default for mid, _ in models):
            return default
    if models:
        return models[0][0]
    if PROVIDER_LIST:
        return PROVIDER_LIST[0][0]
    return "openai/gpt-4o-mini"
