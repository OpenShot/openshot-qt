"""
NVIDIA Edge video generation client.
Calls the FlowCut Edge API (Cosmos model) for text-to-video, image-to-video,
and morph transitions — replacing Runware/Kling for on-device generation.
"""

import os
import logging
import requests
from typing import Optional, Tuple

log = logging.getLogger("flowcut-edge-client")


def _get_edge_base_url(settings=None) -> str:
    """Get the edge API base URL from settings or default."""
    if settings:
        url = settings.get("nvidia-edge-api-url", "").strip()
        if url:
            # Strip /v1 suffix if present — we add it per endpoint
            return url.rstrip("/").removesuffix("/v1")
    return "http://10.19.183.5:8000"


def edge_generate_video(
    prompt: str,
    duration_seconds: float = 4.0,
    width: int = 1024,
    height: int = 576,
    input_video_url: Optional[str] = None,
    settings=None,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Generate video via NVIDIA Cosmos on the edge device.
    Returns (local_video_path, None) on success, or (None, error_message) on failure.
    """
    base_url = _get_edge_base_url(settings)

    if input_video_url:
        # Image-to-video (object replacement uses a frame from the video)
        endpoint = f"{base_url}/v1/video/generate/image"
        payload = {
            "image_url": input_video_url,
            "prompt": prompt,
            "duration_seconds": duration_seconds,
            "width": width,
            "height": height,
        }
    else:
        # Text-to-video
        endpoint = f"{base_url}/v1/video/generate/text"
        payload = {
            "prompt": prompt,
            "duration_seconds": duration_seconds,
            "width": width,
            "height": height,
        }

    try:
        log.info("Edge video request: %s -> %s", endpoint, prompt[:60])
        resp = requests.post(endpoint, json=payload, timeout=600)
        resp.raise_for_status()
        data = resp.json()

        if not data.get("success"):
            return None, data.get("error", "Unknown error from edge service")

        # Download the video from edge device
        video_url = data.get("video_url")
        if video_url:
            download_url = f"{base_url}{video_url}"
            return _download_edge_video(download_url)

        # If video_path is returned (shouldn't happen remotely, but handle it)
        video_path = data.get("video_path")
        if video_path:
            return video_path, None

        return None, "No video URL in response"

    except requests.exceptions.ConnectionError:
        return None, f"Cannot connect to edge device at {base_url}. Is the GX10 server running?"
    except requests.exceptions.Timeout:
        return None, "Edge video generation timed out (>10 min)"
    except Exception as e:
        return None, f"Edge video generation failed: {e}"


def edge_generate_morph_video(
    start_image_url: str,
    end_image_url: str,
    prompt: str = "",
    duration_seconds: float = 4.0,
    width: int = 1024,
    height: int = 576,
    settings=None,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Generate morph transition between two frames via NVIDIA Cosmos.
    Returns (local_video_path, None) on success, or (None, error_message) on failure.
    """
    base_url = _get_edge_base_url(settings)
    endpoint = f"{base_url}/v1/video/generate/morph"

    payload = {
        "start_image_url": start_image_url,
        "end_image_url": end_image_url,
        "prompt": prompt or "Smooth cinematic morphing transition between two scenes",
        "duration_seconds": duration_seconds,
        "width": width,
        "height": height,
    }

    try:
        log.info("Edge morph request: %s, duration=%.1fs", endpoint, duration_seconds)
        resp = requests.post(endpoint, json=payload, timeout=600)
        resp.raise_for_status()
        data = resp.json()

        if not data.get("success"):
            return None, data.get("error", "Unknown error from edge service")

        video_url = data.get("video_url")
        if video_url:
            download_url = f"{base_url}{video_url}"
            return _download_edge_video(download_url)

        return None, "No video URL in morph response"

    except requests.exceptions.ConnectionError:
        return None, f"Cannot connect to edge device at {base_url}. Is the GX10 server running?"
    except requests.exceptions.Timeout:
        return None, "Edge morph generation timed out (>10 min)"
    except Exception as e:
        return None, f"Edge morph generation failed: {e}"


def _download_edge_video(url: str) -> Tuple[Optional[str], Optional[str]]:
    """Download video from edge device to a local temp file."""
    import tempfile

    try:
        resp = requests.get(url, stream=True, timeout=120)
        resp.raise_for_status()

        suffix = ".mp4"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False, prefix="edge_video_") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
            local_path = f.name

        log.info("Edge video downloaded: %s -> %s", url, local_path)
        return local_path, None

    except Exception as e:
        return None, f"Failed to download edge video: {e}"


def is_edge_available(settings=None) -> bool:
    """Check if the edge video service is reachable."""
    base_url = _get_edge_base_url(settings)
    try:
        resp = requests.get(f"{base_url}/health", timeout=5)
        data = resp.json()
        return data.get("status") == "ok"
    except Exception:
        return False
