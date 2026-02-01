"""
AI LLM provider adapters. Each provider builds a LangChain BaseChatModel from app settings.
Lazy-import to avoid breaking the app when optional deps are missing.
"""

from classes.logger import log

# Registry: list of (model_id, display_name, provider_module_name)
PROVIDER_LIST = [
    ("openai/gpt-4o-mini", "OpenAI GPT-4o mini", "openai_provider"),
    ("openai/gpt-4o", "OpenAI GPT-4o", "openai_provider"),
    ("anthropic/claude-3-5-sonnet", "Anthropic Claude 3.5 Sonnet", "anthropic_provider"),
    ("anthropic/claude-3-haiku", "Anthropic Claude 3 Haiku", "anthropic_provider"),
    ("ollama/llama3.2", "Ollama Llama 3.2 (local)", "ollama_provider"),
    ("ollama/llama3.1", "Ollama Llama 3.1 (local)", "ollama_provider"),
]


def get_provider_module(provider_name):
    """Lazy-import provider module by name."""
    if provider_name == "openai_provider":
        from classes.ai_providers import openai_provider
        return openai_provider
    if provider_name == "anthropic_provider":
        from classes.ai_providers import anthropic_provider
        return anthropic_provider
    if provider_name == "ollama_provider":
        from classes.ai_providers import ollama_provider
        return ollama_provider
    return None


def build_model(model_id, settings):
    """
    Build a LangChain ChatModel for the given model_id using app settings.
    Returns the model instance or None if provider unavailable or misconfigured.
    """
    for mid, _display_name, provider_name in PROVIDER_LIST:
        if mid == model_id:
            mod = get_provider_module(provider_name)
            if mod and hasattr(mod, "build_chat_model"):
                try:
                    return mod.build_chat_model(model_id, settings)
                except Exception as e:
                    log.warning("AI provider %s build failed for %s: %s", provider_name, model_id, e)
                    return None
            return None
    return None


def list_available_models(settings):
    """
    Return list of (model_id, display_name) for models that can be built with current settings.
    """
    result = []
    for model_id, display_name, provider_name in PROVIDER_LIST:
        mod = get_provider_module(provider_name)
        if mod and hasattr(mod, "is_available") and mod.is_available(model_id, settings):
            result.append((model_id, display_name))
    return result
