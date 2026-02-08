"""
AI LLM provider adapters (LangChain chat) and base classes for media analysis.
Lazy-import to avoid breaking the app when optional deps are missing.
"""

from classes.logger import log

# Registry: list of (model_id, display_name, provider_module_name, context_limit) for LangChain chat
# context_limit is the maximum input-token window size for the model.
PROVIDER_LIST = [
    ("openai/gpt-4o-mini", "OpenAI GPT-4o mini", "openai_provider", 128_000),
    ("openai/gpt-4o", "OpenAI GPT-4o", "openai_provider", 128_000),
    ("anthropic/claude-3-5-sonnet", "Anthropic Claude 3.5 Sonnet", "anthropic_provider", 200_000),
    ("anthropic/claude-3-haiku", "Anthropic Claude 3 Haiku", "anthropic_provider", 200_000),
    ("ollama/llama3.2", "Ollama Llama 3.2 (local)", "ollama_provider", 128_000),
    ("ollama/llama3.1", "Ollama Llama 3.1 (local)", "ollama_provider", 128_000),
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
    for mid, _display_name, provider_name, _ctx in PROVIDER_LIST:
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
    for model_id, display_name, provider_name, _ctx in PROVIDER_LIST:
        mod = get_provider_module(provider_name)
        if mod and hasattr(mod, "is_available") and mod.is_available(model_id, settings):
            result.append((model_id, display_name))
    return result


def list_all_models():
    """
    Return list of (model_id, display_name) for all registered chat models (no API key check).
    Use this so the UI can show OpenAI, Anthropic, and Ollama; API key is checked when sending.
    """
    return [(model_id, display_name) for model_id, display_name, _, _ in PROVIDER_LIST]


def get_context_limit(model_id):
    """Return the context-window token limit for *model_id*, or 128000 as default."""
    for mid, _dn, _pn, ctx in PROVIDER_LIST:
        if mid == model_id:
            return ctx
    return 128_000


# --- Media analysis base classes (from nilay branch) ---
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from enum import Enum


class ProviderType(Enum):
    """Enum for AI provider types (media analysis)."""
    OPENAI = "openai"
    GOOGLE = "google"
    AWS = "aws"
    HYBRID = "hybrid"


class AnalysisResult:
    """Standardized result from AI analysis."""

    def __init__(self):
        self.objects: List[str] = []
        self.scenes: List[str] = []
        self.activities: List[str] = []
        self.mood: List[str] = []
        self.colors: Dict[str, Any] = {}
        self.faces: List[Dict[str, Any]] = []
        self.quality_scores: Dict[str, float] = {}
        self.description: str = ""
        self.raw_response: Dict[str, Any] = {}
        self.provider: str = ""
        self.confidence: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert analysis result to dictionary."""
        return {
            "objects": self.objects,
            "scenes": self.scenes,
            "activities": self.activities,
            "mood": self.mood,
            "colors": self.colors,
            "faces": self.faces,
            "quality_scores": self.quality_scores,
            "description": self.description,
            "provider": self.provider,
            "confidence": self.confidence
        }


class BaseAIProvider(ABC):
    """Abstract base class for AI providers (media analysis)."""

    def __init__(self, api_key: Optional[str] = None, **kwargs):
        self.api_key = api_key
        self.config = kwargs
        self.is_configured = False
        self._validate_configuration()

    @abstractmethod
    def _validate_configuration(self) -> bool:
        pass

    @abstractmethod
    async def analyze_image(self, image_path: str, **kwargs) -> AnalysisResult:
        pass

    @abstractmethod
    async def analyze_video_frames(self, frame_paths: List[str], **kwargs) -> AnalysisResult:
        pass

    @abstractmethod
    async def detect_faces(self, image_path: str) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    async def parse_search_query(self, query: str) -> Dict[str, Any]:
        pass

    def get_provider_name(self) -> str:
        return self.__class__.__name__

    def is_available(self) -> bool:
        return self.is_configured


class ProviderFactory:
    """Factory for creating AI provider instances (media analysis)."""

    _providers = {}

    @classmethod
    def register_provider(cls, provider_type: ProviderType, provider_class):
        cls._providers[provider_type] = provider_class
        log.debug("Registered AI provider: %s", provider_type.value)

    @classmethod
    def create_provider(cls, provider_type: ProviderType, **kwargs) -> Optional[BaseAIProvider]:
        provider_class = cls._providers.get(provider_type)
        if provider_class:
            try:
                provider = provider_class(**kwargs)
                log.info("Created AI provider: %s", provider_type.value)
                return provider
            except Exception as e:
                log.error("Failed to create provider %s: %s", provider_type.value, e)
                return None
        log.error("Provider type %s not registered", provider_type.value)
        return None

    @classmethod
    def get_available_providers(cls) -> List[ProviderType]:
        return list(cls._providers.keys())
