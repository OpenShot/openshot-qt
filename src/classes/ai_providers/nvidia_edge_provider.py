"""
NVIDIA Edge provider: connects to FlowCut Edge service running on NVIDIA Jetson.
Uses OpenAI-compatible API (ChatOpenAI) pointed at the edge device.
Supports both text (Nemotron-Mini) and vision (VILA-2) models.
"""

from classes.logger import log


def is_available(model_id, settings):
    """Return True if model_id is for nvidia-edge and the URL is configured."""
    if not model_id.startswith("nvidia-edge/"):
        return False
    url = (settings.get("nvidia-edge-api-url") or "").strip()
    return bool(url)


def build_chat_model(model_id, settings):
    """Build ChatOpenAI pointing at the FlowCut Edge API on Jetson."""
    try:
        from langchain_openai import ChatOpenAI
    except ImportError:
        log.warning("langchain-openai not installed")
        return None

    base_url = (settings.get("nvidia-edge-api-url") or "http://192.168.55.1:8000/v1").strip()

    # Map our model_id to the edge service model name
    model_name = model_id.split("/", 1)[-1] if "/" in model_id else model_id

    return ChatOpenAI(
        model=model_name,
        api_key="not-needed",          # Edge service doesn't require auth
        base_url=base_url,
        temperature=0.2,
        max_tokens=4096,
    )
