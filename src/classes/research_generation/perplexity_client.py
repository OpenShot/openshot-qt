"""
Perplexity Sonar API client.

This module is logic-only (no Qt). Call it from worker threads.
"""

from __future__ import annotations

import os
import re
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from classes.logger import log

DEFAULT_BASE_URL = "https://api.perplexity.ai/"
DEFAULT_MODEL = "sonar-pro"


@dataclass(frozen=True)
class PerplexityError(Exception):
    """Structured error for Perplexity API failures."""

    message: str
    status_code: Optional[int] = None
    detail: Optional[str] = None

    def __str__(self) -> str:  # pragma: no cover - trivial
        bits = [self.message]
        if self.status_code is not None:
            bits.append(f"(status={self.status_code})")
        if self.detail:
            bits.append(self.detail)
        return " ".join(bits)


def _norm_base_url(base_url: str) -> str:
    base = (base_url or "").strip() or DEFAULT_BASE_URL
    if not base.endswith("/"):
        base += "/"
    return base


def _auth_headers(api_key: str) -> Dict[str, str]:
    key = (api_key or "").strip()
    if not key:
        raise PerplexityError("Missing Perplexity API key.")
    return {"Authorization": f"Bearer {key}"}


def _parse_json_response(resp) -> Any:
    try:
        return resp.json()
    except Exception:
        # Fallback: show small slice of raw text for debugging
        text = getattr(resp, "text", "") or ""
        raise PerplexityError(
            "Failed to parse JSON response.",
            status_code=getattr(resp, "status_code", None),
            detail=text[:500]
        )


def _raise_for_status(resp) -> None:
    if 200 <= int(resp.status_code) < 300:
        return

    status = int(resp.status_code)
    data = None
    detail = None
    try:
        data = _parse_json_response(resp)
        if isinstance(data, dict):
            # Check for error message in response
            if "error" in data:
                error_info = data["error"]
                if isinstance(error_info, dict):
                    detail = error_info.get("message") or str(error_info)
                else:
                    detail = str(error_info)
            elif "detail" in data:
                detail = str(data.get("detail") or "")
    except Exception:
        # ignore parse failures; will fall back to resp.text
        pass

    if not detail:
        detail = (getattr(resp, "text", "") or "")[:500]

    # Provide helpful error messages for common status codes
    if status == 401:
        raise PerplexityError(
            "Authentication failed. Check your Perplexity API key in Preferences > AI.",
            status_code=status,
            detail=detail
        )
    elif status == 403:
        raise PerplexityError(
            "Access denied. Your API key may not have required permissions.",
            status_code=status,
            detail=detail
        )
    elif status == 429:
        raise PerplexityError(
            "Rate limit exceeded. Please wait before making another search.",
            status_code=status,
            detail=detail
        )
    elif status == 400:
        raise PerplexityError(
            "Bad request. Check your search query parameters.",
            status_code=status,
            detail=detail
        )
    else:
        raise PerplexityError(
            "Perplexity API request failed.",
            status_code=status,
            detail=detail
        )


def perplexity_search(
    *,
    api_key: str,
    query: str,
    model: str = DEFAULT_MODEL,
    return_images: bool = True,
    return_related_questions: bool = True,
    search_domain_filter: Optional[List[str]] = None,
    search_recency_filter: str = "",
    base_url: str = DEFAULT_BASE_URL,
    timeout_seconds: float = 60.0,
) -> Dict[str, Any]:
    """
    Search using Perplexity Sonar API.

    Args:
        api_key: Perplexity API key
        query: Search query string
        model: Model to use (default: sonar-pro)
        return_images: Whether to include images in response
        return_related_questions: Whether to include related questions
        search_domain_filter: List of domains to filter search (e.g., ["wikipedia.org"])
        search_recency_filter: Filter by recency ("month", "week", "day", or "")
        base_url: API base URL
        timeout_seconds: Request timeout

    Returns:
        {
            "content": "AI-generated answer with citations",
            "citations": ["url1", "url2", ...],
            "images": [{"url": "...", "description": "..."}, ...],
            "related_questions": ["question1", ...],
        }
    """
    if not (query or "").strip():
        raise PerplexityError("Query is required for search.")

    try:
        import requests
    except ImportError as exc:  # pragma: no cover
        raise PerplexityError("requests library is required.") from exc

    # Build request payload
    messages = [{"role": "user", "content": str(query).strip()}]

    payload: Dict[str, Any] = {
        "model": str(model).strip() or DEFAULT_MODEL,
        "messages": messages,
    }

    # Add optional parameters
    if return_images:
        payload["return_images"] = True

    if return_related_questions:
        payload["return_related_questions"] = True

    # Build search_domain_filter if provided
    if search_domain_filter:
        domains = [d.strip() for d in search_domain_filter if (d or "").strip()]
        if domains:
            payload["search_domain_filter"] = domains

    # Add search_recency_filter if provided
    if (search_recency_filter or "").strip():
        recency = str(search_recency_filter).strip().lower()
        if recency in ["month", "week", "day"]:
            payload["search_recency_filter"] = recency

    url = _norm_base_url(base_url) + "chat/completions"
    headers = _auth_headers(api_key)
    headers["Content-Type"] = "application/json"

    try:
        resp = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=float(timeout_seconds)
        )
    except requests.RequestException as exc:
        raise PerplexityError(f"Perplexity API request failed: {exc}") from exc

    _raise_for_status(resp)
    data = _parse_json_response(resp)

    # Parse Perplexity response format
    # Expected structure: {choices: [{message: {content: "..."}}], citations: [...], images: [...]}
    if not isinstance(data, dict):
        raise PerplexityError(
            "Unexpected response format.",
            status_code=int(resp.status_code),
            detail=str(data)[:500]
        )

    # Extract content from choices
    content = ""
    choices = data.get("choices", [])
    if choices and isinstance(choices, list) and len(choices) > 0:
        first_choice = choices[0]
        if isinstance(first_choice, dict):
            message = first_choice.get("message", {})
            if isinstance(message, dict):
                content = message.get("content", "")

    # Extract citations
    citations = data.get("citations", [])
    if not isinstance(citations, list):
        citations = []

    # Extract images
    images = data.get("images", [])
    if not isinstance(images, list):
        images = []

    # Extract related questions
    related_questions = data.get("related_questions", [])
    if not isinstance(related_questions, list):
        related_questions = []

    return {
        "content": str(content).strip(),
        "citations": [str(c).strip() for c in citations if (c or "").strip()],
        "images": [
            {
                "url": str(img.get("url", "")).strip(),
                "description": str(img.get("description", "")).strip(),
            }
            for img in images
            if isinstance(img, dict) and (img.get("url") or "").strip()
        ],
        "related_questions": [
            str(q).strip() for q in related_questions if (q or "").strip()
        ],
    }


def download_image(
    *,
    image_url: str,
    dest_path: str,
    timeout_seconds: float = 60.0,
) -> Tuple[bool, Optional[str]]:
    """
    Download an image from a URL to dest_path.

    Args:
        image_url: URL of the image to download
        dest_path: Local file path to save image
        timeout_seconds: Request timeout

    Returns:
        (success, error_message_or_none)
    """
    url = (image_url or "").strip()
    path = (dest_path or "").strip()
    if not url or not path:
        return False, "Missing image_url or dest_path."

    try:
        import requests
    except ImportError:  # pragma: no cover
        return False, "requests library is required."

    try:
        r = requests.get(url, timeout=float(timeout_seconds), stream=True)
        r.raise_for_status()  # Use standard raise_for_status for image downloads

        # Ensure destination directory exists
        dest_dir = os.path.dirname(path)
        if dest_dir and not os.path.exists(dest_dir):
            os.makedirs(dest_dir, exist_ok=True)

        with open(path, "wb") as f:
            for chunk in r.iter_content(chunk_size=65536):
                if chunk:
                    f.write(chunk)
        return True, None
    except requests.RequestException as exc:
        log.error("Image download failed: %s", exc)
        return False, f"Download failed: {exc}."
    except OSError as exc:
        log.error("Image write failed: %s", exc)
        return False, f"Could not write file: {exc}."


def _sanitize_filename(name: str) -> str:
    """Sanitize a string to be safe for use as a filename."""
    # Remove non-alphanumeric characters except dash, underscore, dot
    safe = re.sub(r"[^\w\-\.]", "_", name)
    # Limit length
    if len(safe) > 50:
        safe = safe[:50]
    return safe or "image"


def research_and_download_images(
    *,
    api_key: str,
    query: str,
    max_images: int = 5,
    dest_dir: str,
    model: str = DEFAULT_MODEL,
    search_domain_filter: Optional[List[str]] = None,
    search_recency_filter: str = "",
    base_url: str = DEFAULT_BASE_URL,
    timeout_seconds: float = 120.0,
) -> Dict[str, Any]:
    """
    Convenience: search → download top N images → return research summary.

    Args:
        api_key: Perplexity API key
        query: Search query
        max_images: Maximum number of images to download
        dest_dir: Directory to save downloaded images
        model: Model to use
        search_domain_filter: List of domains to filter
        search_recency_filter: Recency filter
        base_url: API base URL
        timeout_seconds: Total timeout for operation

    Returns:
        {
            "summary": "Research summary with citations",
            "citations": ["url1", ...],
            "image_paths": ["/path/to/img1.jpg", ...],
            "failed_images": [{"url": "...", "error": "..."}, ...],
            "related_questions": [...],
        }
    """
    # Search with images
    result = perplexity_search(
        api_key=api_key,
        query=query,
        model=model,
        return_images=True,
        return_related_questions=True,
        search_domain_filter=search_domain_filter,
        search_recency_filter=search_recency_filter,
        base_url=base_url,
        timeout_seconds=float(timeout_seconds) / 2,  # Reserve half time for downloads
    )

    # Ensure destination directory exists
    if not os.path.exists(dest_dir):
        os.makedirs(dest_dir, exist_ok=True)

    # Download images
    images = result.get("images", [])
    max_imgs = max(0, int(max_images))
    downloaded_images = []
    failed_images = []

    # Calculate per-image timeout
    image_timeout = min(30.0, float(timeout_seconds) / max(1, max_imgs) / 2)

    for i, img in enumerate(images[:max_imgs]):
        img_url = img.get("url", "")
        if not img_url:
            continue

        # Generate filename from URL or use index
        filename_base = _sanitize_filename(os.path.basename(img_url.split("?")[0]))
        if not filename_base or filename_base == "image":
            filename_base = f"image_{i+1}"

        # Add unique ID to avoid collisions
        unique_id = uuid.uuid4().hex[:8]
        filename = f"{filename_base}_{unique_id}.jpg"
        dest_path = os.path.join(dest_dir, filename)

        ok, err = download_image(
            image_url=img_url,
            dest_path=dest_path,
            timeout_seconds=image_timeout
        )

        if ok:
            downloaded_images.append({
                "path": dest_path,
                "url": img_url,
                "description": img.get("description", ""),
            })
        else:
            failed_images.append({
                "url": img_url,
                "error": err or "Unknown error",
            })
            log.warning("Failed to download image %s: %s", img_url, err)

    return {
        "summary": result.get("content", ""),
        "citations": result.get("citations", []),
        "image_paths": [img["path"] for img in downloaded_images],
        "downloaded_images": downloaded_images,
        "failed_images": failed_images,
        "related_questions": result.get("related_questions", []),
    }
