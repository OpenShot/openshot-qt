"""
Suno TreeHacks 2026 (hackathons) API client.

This module is logic-only (no Qt). Call it from worker threads.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from classes.logger import log

DEFAULT_BASE_URL = "https://studio-api.prod.suno.com/api/v2/external/hackathons/"


@dataclass(frozen=True)
class SunoError(Exception):
    """Structured error for Suno API failures."""

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


def _auth_headers(token: str) -> Dict[str, str]:
    tok = (token or "").strip()
    if not tok:
        raise SunoError("Missing Suno token.")
    return {"Authorization": f"Bearer {tok}"}


def _parse_json_response(resp) -> Any:
    try:
        return resp.json()
    except Exception:
        # Fallback: show small slice of raw text for debugging
        text = getattr(resp, "text", "") or ""
        raise SunoError("Failed to parse JSON response.", status_code=getattr(resp, "status_code", None), detail=text[:500])


def _raise_for_status(resp) -> None:
    if 200 <= int(resp.status_code) < 300:
        return
    
    status = int(resp.status_code)
    data = None
    detail = None
    try:
        data = _parse_json_response(resp)
        if isinstance(data, dict) and "detail" in data:
            detail = str(data.get("detail") or "")
    except Exception:
        # ignore parse failures; will fall back to resp.text
        pass
    if not detail:
        detail = (getattr(resp, "text", "") or "")[:500]
    
    # Provide helpful error messages for common status codes
    if status == 401:
        raise SunoError("Authentication failed. Check your Suno TreeHacks token in Preferences > AI.", status_code=status, detail=detail)
    elif status == 403:
        raise SunoError("Access denied. Your token may not have TreeHacks hackathon access.", status_code=status, detail=detail)
    elif status == 429:
        raise SunoError("Rate limit exceeded. Please wait before generating another song.", status_code=status, detail=detail)
    elif status == 400:
        raise SunoError("Bad request. Check your parameters (topic/tags/prompt).", status_code=status, detail=detail)
    else:
        raise SunoError("Suno API request failed.", status_code=status, detail=detail)


def suno_generate(
    *,
    token: str,
    topic: str = "",
    tags: str = "",
    negative_tags: str = "",
    prompt: str = "",
    make_instrumental: Optional[bool] = None,
    cover_clip_id: str = "",
    base_url: str = DEFAULT_BASE_URL,
    timeout_seconds: float = 60.0,
) -> Dict[str, Any]:
    """
    POST /generate

    Returns the generated clip object (single object).
    """
    payload: Dict[str, Any] = {}
    if (topic or "").strip():
        payload["topic"] = str(topic)
    if (tags or "").strip():
        payload["tags"] = str(tags)
    if (negative_tags or "").strip():
        payload["negative_tags"] = str(negative_tags)
    if (prompt or "").strip():
        payload["prompt"] = str(prompt)
    if make_instrumental is not None:
        payload["make_instrumental"] = bool(make_instrumental)
    if (cover_clip_id or "").strip():
        payload["cover_clip_id"] = str(cover_clip_id).strip()

    if not payload:
        raise SunoError("Must provide at least one of: topic, tags, prompt, cover_clip_id.")

    try:
        import requests
    except ImportError as exc:  # pragma: no cover
        raise SunoError("requests library is required.") from exc

    url = _norm_base_url(base_url) + "generate"
    headers = _auth_headers(token)
    headers["Content-Type"] = "application/json"

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=float(timeout_seconds))
    except requests.RequestException as exc:
        raise SunoError(f"Suno API request failed: {exc}") from exc

    _raise_for_status(resp)
    data = _parse_json_response(resp)
    if not isinstance(data, dict) or not data.get("id"):
        raise SunoError("Unexpected generate response format.", status_code=int(resp.status_code), detail=str(data)[:500])
    return data


def suno_get_clips(
    *,
    token: str,
    ids: Sequence[str],
    base_url: str = DEFAULT_BASE_URL,
    timeout_seconds: float = 30.0,
) -> List[Dict[str, Any]]:
    """
    GET /clips?ids=...

    Returns an array of clip objects.
    """
    clip_ids = [str(i).strip() for i in (ids or []) if str(i).strip()]
    if not clip_ids:
        raise SunoError("ids is required for /clips.")

    try:
        import requests
    except ImportError as exc:  # pragma: no cover
        raise SunoError("requests library is required.") from exc

    url = _norm_base_url(base_url) + "clips"
    headers = _auth_headers(token)
    params = {"ids": ",".join(clip_ids)}

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=float(timeout_seconds))
    except requests.RequestException as exc:
        raise SunoError(f"Suno API request failed: {exc}") from exc

    _raise_for_status(resp)
    data = _parse_json_response(resp)
    if not isinstance(data, list):
        raise SunoError("Unexpected clips response format.", status_code=int(resp.status_code), detail=str(data)[:500])
    # Filter to dicts
    return [c for c in data if isinstance(c, dict)]


def suno_wait_for_clip(
    *,
    token: str,
    clip_id: str,
    base_url: str = DEFAULT_BASE_URL,
    timeout_seconds: float = 180.0,
    poll_seconds: float = 5.0,
    target_statuses: Iterable[str] = ("complete",),
    allow_streaming: bool = True,
) -> Dict[str, Any]:
    """
    Poll /clips until a clip reaches a target status (default: complete).

    If allow_streaming is True and the clip becomes 'streaming', the returned object
    will contain an audio_url suitable for previewing; but callers that need a stable
    downloadable MP3 should still wait for 'complete'.
    """
    cid = (clip_id or "").strip()
    if not cid:
        raise SunoError("clip_id is required.")

    targets = {str(s).strip().lower() for s in (target_statuses or []) if str(s).strip()}
    if not targets:
        targets = {"complete"}

    poll = max(1.0, float(poll_seconds))
    deadline = time.time() + max(1.0, float(timeout_seconds))

    last: Dict[str, Any] = {}
    while time.time() < deadline:
        clips = suno_get_clips(token=token, ids=[cid], base_url=base_url, timeout_seconds=30.0)
        if not clips:
            last = {}
        else:
            last = clips[0]

        status = str((last.get("status") or "")).strip().lower()
        if status in targets:
            return last
        if allow_streaming and status == "streaming" and "streaming" in targets:
            return last
        if status == "error":
            # Some errors may be in metadata
            md = last.get("metadata") or {}
            err_type = (md.get("error_type") or "") if isinstance(md, dict) else ""
            err_msg = (md.get("error_message") or "") if isinstance(md, dict) else ""
            extra = " ".join([p for p in [str(err_type).strip(), str(err_msg).strip()] if p])
            raise SunoError("Suno generation failed.", detail=extra or "status=error")

        time.sleep(poll)

    raise SunoError("Timed out waiting for Suno clip.", detail=f"clip_id={cid}")


def suno_stem(
    *,
    token: str,
    clip_id: str,
    base_url: str = DEFAULT_BASE_URL,
    timeout_seconds: float = 60.0,
) -> List[Dict[str, Any]]:
    """
    POST /stem

    Returns an array of 12 clip objects (submitted initially).
    """
    cid = (clip_id or "").strip()
    if not cid:
        raise SunoError("clip_id is required for /stem.")

    try:
        import requests
    except ImportError as exc:  # pragma: no cover
        raise SunoError("requests library is required.") from exc

    url = _norm_base_url(base_url) + "stem"
    headers = _auth_headers(token)
    headers["Content-Type"] = "application/json"
    payload = {"clip_id": cid}

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=float(timeout_seconds))
    except requests.RequestException as exc:
        raise SunoError(f"Suno API request failed: {exc}") from exc

    _raise_for_status(resp)
    data = _parse_json_response(resp)
    if not isinstance(data, list):
        raise SunoError("Unexpected stem response format.", status_code=int(resp.status_code), detail=str(data)[:500])
    return [c for c in data if isinstance(c, dict)]


def download_mp3(
    *,
    audio_url: str,
    dest_path: str,
    timeout_seconds: float = 180.0,
) -> Tuple[bool, Optional[str]]:
    """
    Download an MP3 from a URL to dest_path.

    Returns: (ok, error_message)
    """
    url = (audio_url or "").strip()
    path = (dest_path or "").strip()
    if not url or not path:
        return False, "Missing audio_url or dest_path."

    try:
        import requests
    except ImportError:  # pragma: no cover
        return False, "requests library is required."

    try:
        r = requests.get(url, timeout=float(timeout_seconds), stream=True)
        _raise_for_status(r)
        with open(path, "wb") as f:
            for chunk in r.iter_content(chunk_size=65536):
                if chunk:
                    f.write(chunk)
        return True, None
    except SunoError as exc:
        log.error("Suno download failed: %s", exc)
        return False, str(exc)
    except requests.RequestException as exc:
        log.error("Suno download failed: %s", exc)
        return False, f"Download failed: {exc}."
    except OSError as exc:
        log.error("Suno download write failed: %s", exc)
        return False, f"Could not write file: {exc}."


def generate_wait_download_mp3(
    *,
    token: str,
    topic: str = "",
    tags: str = "",
    negative_tags: str = "",
    prompt: str = "",
    make_instrumental: Optional[bool] = None,
    cover_clip_id: str = "",
    base_url: str = DEFAULT_BASE_URL,
    timeout_seconds: float = 240.0,
    poll_seconds: float = 5.0,
    dest_path: str,
) -> Dict[str, Any]:
    """
    Convenience: generate → poll until complete → download final MP3.

    Returns the final clip object (status=complete) with audio_url.
    Raises SunoError on failures.
    """
    clip = suno_generate(
        token=token,
        topic=topic,
        tags=tags,
        negative_tags=negative_tags,
        prompt=prompt,
        make_instrumental=make_instrumental,
        cover_clip_id=cover_clip_id,
        base_url=base_url,
        timeout_seconds=60.0,
    )
    cid = str(clip.get("id") or "").strip()
    final_clip = suno_wait_for_clip(
        token=token,
        clip_id=cid,
        base_url=base_url,
        timeout_seconds=float(timeout_seconds),
        poll_seconds=float(poll_seconds),
        target_statuses=("complete",),
        allow_streaming=True,
    )
    audio_url = str(final_clip.get("audio_url") or "").strip()
    if not audio_url:
        raise SunoError("Suno clip completed but audio_url is missing.", detail=f"clip_id={cid}")
    ok, err = download_mp3(audio_url=audio_url, dest_path=dest_path, timeout_seconds=180.0)
    if not ok:
        raise SunoError("Failed to download MP3.", detail=err or "")
    return final_clip

