"""
Runware API client for video generation (Vidu). Thread-safe: no Qt, for use from worker thread only.
"""

import base64
import json
import time
import uuid
from classes.logger import log

# #region agent log
def _debug_log(location, message, data, hypothesis_id):
    try:
        import os
        _path = "/home/vboxuser/Projects/Zenvi/.cursor/debug.log"
        os.makedirs(os.path.dirname(_path), exist_ok=True)
        with open(_path, "a") as f:
            f.write(json.dumps({"location": location, "message": message, "data": data, "hypothesisId": hypothesis_id, "timestamp": time.time()}) + "\n")
    except Exception:
        pass
# #endregion

RUNWARE_API_BASE = "https://api.runware.ai/v1"
POLL_INTERVAL_INITIAL = 2.0
POLL_INTERVAL_MAX = 15.0
POLL_TIMEOUT_SECONDS = 300  # 5 minutes


def _model_supports_fps(model: str) -> bool:
    """Best-effort: some models (e.g. vidu:2@0) reject the fps parameter."""
    m = (model or "").strip().lower()
    if not m:
        return True
    # Known: vidu:2@0 (and likely other vidu:2 versions) can reject fps.
    if m.startswith("vidu:2@"):  # e.g. vidu:2@0
        return False
    return True


def _model_supports_seed_video(model: str) -> bool:
    """Best-effort: some models (e.g. vidu:2@0) reject seedVideo/strength."""
    m = (model or "").strip().lower()
    if not m:
        return True
    # Vidu 2.x models are documented as image-to-video/reference-to-video and can reject seedVideo.
    if m.startswith("vidu:2@"):  # e.g. vidu:2@0
        return False
    return True


def _model_supports_reference_videos(model: str) -> bool:
    """Best-effort: some models (e.g. vidu:2@0) reject top-level referenceVideos."""
    m = (model or "").strip().lower()
    if not m:
        return True
    # Based on observed Runware 400 errors for vidu:2@0.
    if m.startswith("vidu:2@"):  # e.g. vidu:2@0
        return False
    return True


def _build_inputs_video_guidance(seed_video: str | None, reference_videos: list | None) -> dict | None:
    """Build the Runware `inputs` object for video guidance."""
    inputs = {}
    if seed_video:
        inputs["video"] = seed_video
    if reference_videos:
        inputs["referenceVideos"] = reference_videos
    return inputs or None


def _try_parse_runware_error(body_text: str) -> dict:
    try:
        return json.loads(body_text) if body_text else {}
    except Exception:
        return {}


def _as_data_uri(media_type: str, raw_bytes: bytes) -> str:
    b64 = base64.b64encode(raw_bytes).decode("ascii")
    return f"data:{media_type};base64,{b64}"


def _poll_runware_task_rest(api_key: str, task_uuid: str, *, timeout_seconds: float = POLL_TIMEOUT_SECONDS):
    """Poll getResponse until success/error/timeout. Returns (video_url, error_message)."""
    try:
        import requests
    except ImportError:
        return None, "requests library is required."

    headers = {"Content-Type": "application/json"}
    start = time.time()
    interval = float(POLL_INTERVAL_INITIAL)
    last_status = "processing"
    while True:
        if time.time() - start > float(timeout_seconds or POLL_TIMEOUT_SECONDS):
            return None, f"Video generation timed out (last status: {last_status})."

        payload = [
            {"taskType": "authentication", "apiKey": api_key},
            {"taskType": "getResponse", "taskUUID": str(task_uuid)},
        ]
        try:
            r = requests.post(RUNWARE_API_BASE, headers=headers, json=payload, timeout=120)
            r.raise_for_status()
            data = r.json() if r.content else {}
        except requests.RequestException as e:
            return None, f"Runware polling failed: {e}."

        errors = data.get("errors") or []
        if errors:
            err0 = errors[0]
            msg = err0.get("message") if isinstance(err0, dict) else str(err0)
            return None, f"Runware error: {msg}."

        items = data.get("data") or []
        # Find the response for our task
        item = None
        for it in items:
            if isinstance(it, dict) and str(it.get("taskUUID")) == str(task_uuid):
                item = it
                break
        if not item and items:
            # Some responses may omit taskUUID in partial lists; fall back to first
            item = items[0] if isinstance(items[0], dict) else None

        if item:
            last_status = (item.get("status") or last_status) if isinstance(item, dict) else last_status
            if str(last_status).lower() == "success":
                url = item.get("videoURL") if isinstance(item, dict) else None
                if url:
                    return url, None
                return None, "Runware returned success but no videoURL."
            if str(last_status).lower() in ("error", "failed", "canceled", "cancelled"):
                return None, "Runware task failed."

        time.sleep(interval)
        interval = min(float(POLL_INTERVAL_MAX), interval * 1.4)


def runware_generate_video(
    api_key,
    prompt,
    duration_seconds=4,
    model="vidu:3@2",
    width=640,
    height=352,
    *,
    negative_prompt: str | None = None,
    fps: int | None = 24,
    seed_video: str | None = None,
    strength: float | None = None,
    frame_images: list | None = None,
    reference_videos: list | None = None,
    provider_settings: dict | None = None,
):
    """
    Generate video via Runware. Prefers the official SDK (WebSocket); falls back to REST.
    Call from worker thread only.

    Returns:
        (video_url, None) on success, or (None, error_message) on failure.
    """
    if not api_key or not str(api_key).strip():
        return None, "Video generation is not configured. Add your Runware API key in Preferences."
    prompt = (prompt or "").strip()
    if len(prompt) < 2:
        return None, "Prompt must be at least 2 characters."
    api_key = api_key.strip()
    duration_int = int(max(1, min(10, duration_seconds)))

    # Model-specific schema:
    # - Some models reject seedVideo/strength (e.g. vidu:2@0)
    # - Some models reject top-level referenceVideos (e.g. vidu:2@0)
    # For these, we move guidance into `inputs`.
    inputs = None
    if (seed_video or reference_videos) and (not _model_supports_seed_video(model) or not _model_supports_reference_videos(model)):
        inputs = _build_inputs_video_guidance(seed_video, reference_videos)
        seed_video = None
        strength = None
        reference_videos = None
    elif not _model_supports_seed_video(model):
        seed_video = None
        strength = None

    # Prefer Runware SDK (WebSocket) when installed.
    try:
        from runware import Runware, IVideoInference
        from runware.types import IAsyncTaskResponse
        import asyncio
        # #region agent log
        _debug_log("runware_client:sdk_start", "using Runware SDK", {"model": model, "duration": duration_int}, "F")
        # #endregion
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        rw = None
        try:
            rw = Runware(api_key=api_key, timeout=POLL_TIMEOUT_SECONDS)
            loop.run_until_complete(rw.connect())
            req_kwargs = {
                "positivePrompt": prompt,
                "model": model,
                "duration": duration_int,
                "width": int(width),
                "height": int(height),
                "deliveryMethod": "async",
            }
            if negative_prompt:
                req_kwargs["negativePrompt"] = str(negative_prompt)
            if fps is not None and _model_supports_fps(model):
                req_kwargs["fps"] = int(fps)
            if seed_video:
                req_kwargs["seedVideo"] = seed_video
            if strength is not None:
                req_kwargs["strength"] = float(strength)
            if frame_images:
                req_kwargs["frameImages"] = frame_images
            if reference_videos:
                req_kwargs["referenceVideos"] = reference_videos
            if inputs:
                try:
                    from runware.types import IVideoInputs

                    req_kwargs["inputs"] = IVideoInputs(**inputs)
                except Exception:
                    # Older SDKs may not ship IVideoInputs; try raw dict.
                    req_kwargs["inputs"] = inputs
            if provider_settings:
                req_kwargs["providerSettings"] = provider_settings
            req = IVideoInference(**req_kwargs)
            try:
                result = loop.run_until_complete(rw.videoInference(requestVideo=req))
            except Exception as e:
                # Retry once without fps if the model rejects it.
                if "fps" in str(e).lower() and "unsupported" in str(e).lower() and "fps" in req_kwargs:
                    try:
                        req_kwargs.pop("fps", None)
                        req = IVideoInference(**req_kwargs)
                        result = loop.run_until_complete(rw.videoInference(requestVideo=req))
                    except Exception:
                        raise
                else:
                    raise
            # Async returns IAsyncTaskResponse immediately; then we poll for the video.
            task_uuid = None
            if isinstance(result, IAsyncTaskResponse):
                task_uuid = getattr(result, "taskUUID", None) or getattr(result, "task_uuid", None)
            if not task_uuid:
                return None, "Runware SDK did not return a task UUID."
            # Poll getResponse until we get a URL or timeout.
            poll_start = time.time()
            interval = float(POLL_INTERVAL_INITIAL)
            while time.time() - poll_start < float(POLL_TIMEOUT_SECONDS):
                videos = loop.run_until_complete(rw.getResponse(task_uuid, numberResults=1))
                if videos and len(videos) > 0 and getattr(videos[0], "videoURL", None):
                    url = videos[0].videoURL
                    _debug_log("runware_client:sdk_success", "SDK returned videoURL", {"has_url": bool(url)}, "F")
                    return url, None
                time.sleep(interval)
                interval = min(float(POLL_INTERVAL_MAX), interval * 1.4)
            return None, "Runware SDK polling timed out."
        finally:
            if rw is not None:
                try:
                    loop.run_until_complete(rw.disconnect())
                except Exception:
                    pass
            loop.close()
    except ImportError:
        pass
    except Exception as e:
        log.error("Runware SDK failed: %s", e, exc_info=True)
        # #region agent log
        _debug_log("runware_client:sdk_error", "SDK exception", {"error": str(e)}, "F")
        # #endregion
        # Fall back to REST: SDK errors can be schema-related and REST retry logic may recover.
        _debug_log("runware_client:sdk_error", "SDK failed; falling back to REST", {"error": str(e)}, "F")

    # REST async + polling (supports video-to-video inputs like seedVideo).
    try:
        import requests
    except ImportError:
        return None, "requests library is required."
    task_uuid = str(uuid.uuid4())
    headers = {"Content-Type": "application/json"}
    task = {
        "taskType": "videoInference",
        "taskUUID": task_uuid,
        "positivePrompt": prompt,
        "model": model,
        "duration": float(duration_int),
        "width": int(width),
        "height": int(height),
        "deliveryMethod": "async",
        "outputFormat": "MP4",
        "outputQuality": 95,
    }
    if fps is not None and _model_supports_fps(model):
        task["fps"] = int(fps)
    if negative_prompt:
        task["negativePrompt"] = str(negative_prompt)
    if seed_video:
        task["seedVideo"] = seed_video
    if strength is not None:
        task["strength"] = float(strength)
    if frame_images:
        task["frameImages"] = frame_images
    if reference_videos:
        task["referenceVideos"] = reference_videos
    if inputs:
        task["inputs"] = inputs
    if provider_settings:
        task["providerSettings"] = provider_settings
    def _post(payload_to_send):
        r = requests.post(RUNWARE_API_BASE, headers=headers, json=payload_to_send, timeout=120)
        return r

    payload = [{"taskType": "authentication", "apiKey": api_key}, task]
    # #region agent log
    _debug_log("runware_client:rest_fallback", "REST sync submit", {"task_uuid": task_uuid}, "F")
    # #endregion
    try:
        r = _post(payload)
        _debug_log("runware_client:submit_response", "submit response", {"status_code": r.status_code}, "F")
        r.raise_for_status()
        data = r.json()
    except requests.RequestException as e:
        resp = getattr(e, "response", None)
        status = getattr(resp, "status_code", None)
        err_body = getattr(resp, "text", None) or ""
        raw_content = getattr(resp, "content", None)
        _debug_log("runware_client:submit_error", "submit failed", {
            "body": err_body[:500], "body_len": len(err_body),
            "content_len": len(raw_content) if raw_content else 0,
            "reason": getattr(resp, "reason", None),
        }, "F")

        parsed = _try_parse_runware_error(err_body)

        # If model rejects seedVideo/strength/referenceVideos, retry by migrating guidance into `inputs`.
        try:
            if int(status or 0) == 400 and isinstance(parsed.get("errors"), list) and parsed.get("errors"):
                err0 = parsed.get("errors")[0] if parsed.get("errors") else {}
                if isinstance(err0, dict) and (err0.get("code") == "unsupportedParameter") and (err0.get("parameter") in ("seedVideo", "strength", "referenceVideos")):
                    alt_task = dict(task)
                    seed = alt_task.pop("seedVideo", None)
                    rv = alt_task.pop("referenceVideos", None)
                    alt_task.pop("strength", None)

                    inputs2 = alt_task.get("inputs")
                    inputs2 = dict(inputs2) if isinstance(inputs2, dict) else {}
                    if seed and "video" not in inputs2:
                        inputs2["video"] = seed
                    if rv and "referenceVideos" not in inputs2:
                        inputs2["referenceVideos"] = rv
                    if inputs2:
                        alt_task["inputs"] = inputs2
                    alt_payload = [payload[0], alt_task]
                    r2 = _post(alt_payload)
                    _debug_log("runware_client:submit_retry", "retry after migrating guidance to inputs", {"status_code": r2.status_code}, "F")
                    r2.raise_for_status()
                    data = r2.json() if r2.content else {}
                    errors = data.get("errors") or []
                    if errors:
                        err0b = errors[0]
                        msg = err0b.get("message") if isinstance(err0b, dict) else str(err0b)
                        return None, f"Runware error: {msg}."
                    task_list = data.get("data") or []
                    if task_list and isinstance(task_list[0], dict) and task_list[0].get("taskUUID") == task_uuid:
                        return _poll_runware_task_rest(api_key, task_uuid)
        except Exception:
            pass

        # If model rejects fps, retry once without fps.
        try:
            if int(status or 0) == 400 and isinstance(parsed.get("errors"), list) and parsed.get("errors"):
                err0 = parsed.get("errors")[0] if parsed.get("errors") else {}
                if isinstance(err0, dict) and (err0.get("code") == "unsupportedParameter") and (err0.get("parameter") == "fps"):
                    if "fps" in task:
                        alt_task = dict(task)
                        alt_task.pop("fps", None)
                        alt_payload = [payload[0], alt_task]
                        r2 = _post(alt_payload)
                        _debug_log("runware_client:submit_retry", "retry after removing fps", {"status_code": r2.status_code}, "F")
                        r2.raise_for_status()
                        data = r2.json() if r2.content else {}
                        errors = data.get("errors") or []
                        if errors:
                            err0b = errors[0]
                            msg = err0b.get("message") if isinstance(err0b, dict) else str(err0b)
                            return None, f"Runware error: {msg}."
                        task_list = data.get("data") or []
                        if task_list and task_list[0].get("taskUUID") == task_uuid:
                            return _poll_runware_task_rest(api_key, task_uuid)
        except Exception:
            pass

        # If we got a 400 and frameImages are present, try a best-effort schema fallback.
        try:
            if int(status or 0) == 400 and isinstance(task.get("frameImages"), list):
                alt_task = dict(task)
                alt_frames = []
                changed = False
                for fi in alt_task.get("frameImages") or []:
                    if isinstance(fi, dict):
                        if "inputImages" in fi and "inputImage" not in fi:
                            fi2 = dict(fi)
                            fi2["inputImage"] = fi2.pop("inputImages")
                            alt_frames.append(fi2)
                            changed = True
                            continue
                        if "inputImage" in fi and "inputImages" not in fi:
                            fi2 = dict(fi)
                            fi2["inputImages"] = fi2.pop("inputImage")
                            alt_frames.append(fi2)
                            changed = True
                            continue
                    else:
                        alt_frames.append(fi)
                if changed:
                    alt_task["frameImages"] = alt_frames
                    alt_payload = [payload[0], alt_task]
                    r2 = _post(alt_payload)
                    _debug_log("runware_client:submit_retry", "retry after frameImages schema tweak", {"status_code": r2.status_code}, "F")
                    r2.raise_for_status()
                    data = r2.json() if r2.content else {}
                    errors = data.get("errors") or []
                    if errors:
                        err0 = errors[0]
                        msg = err0.get("message") if isinstance(err0, dict) else str(err0)
                        return None, f"Runware error: {msg}."
                    # Continue normal flow below by setting task_uuid etc.
                    task_list = data.get("data") or []
                    if task_list and task_list[0].get("taskUUID") == task_uuid:
                        return _poll_runware_task_rest(api_key, task_uuid)
        except Exception:
            pass

        # Surface the server's error body if present; it often contains the actual schema error.
        msg = "Runware API request failed"
        if status:
            msg += f" ({status})"
        if err_body:
            # Keep concise; the UI can show details if needed.
            msg += f": {err_body[:800]}"
        else:
            msg += f": {str(e)}"
        return None, msg
    errors = data.get("errors") or []
    if errors:
        return None, "Runware error: {}.".format(errors[0].get("message", str(errors[0])))
    task_list = data.get("data") or []
    if not task_list or task_list[0].get("taskUUID") != task_uuid:
        return None, "Runware did not return task UUID."
    # We expect async ack; poll for results
    return _poll_runware_task_rest(api_key, task_uuid)


def download_video_to_path(video_url, local_path):
    """
    Download video from URL to local path. Call from worker thread only.

    Returns:
        (True, None) on success, (False, error_message) on failure.
    """
    if not video_url or not local_path:
        return False, "Missing URL or path."
    try:
        import requests
    except ImportError:
        return False, "requests library is required."

    try:
        r = requests.get(video_url, timeout=120, stream=True)
        r.raise_for_status()
        with open(local_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=65536):
                if chunk:
                    f.write(chunk)
        return True, None
    except requests.RequestException as e:
        log.error("Download failed: %s", e)
        return False, "Download failed: {}.".format(str(e))
    except OSError as e:
        log.error("Write failed: %s", e)
        return False, "Could not write file: {}.".format(str(e))
