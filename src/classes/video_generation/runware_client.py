"""
Runware API client for video generation (Vidu). Thread-safe: no Qt, for use from worker thread only.
"""

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


def runware_generate_video(
    api_key,
    prompt,
    duration_seconds=4,
    model="vidu:3@2",
    width=640,
    height=352,
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

    # Prefer Runware SDK (WebSocket). Use async delivery + getResponse polling to avoid
    # "Connection lost while waiting for video response" (sync holds one WebSocket wait for minutes).
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
            req = IVideoInference(
                positivePrompt=prompt,
                model=model,
                duration=duration_int,
                width=int(width),
                height=int(height),
                deliveryMethod="async",
            )
            result = loop.run_until_complete(rw.videoInference(requestVideo=req))
            # Async returns IAsyncTaskResponse immediately; then we poll for the video.
            task_uuid = None
            if isinstance(result, IAsyncTaskResponse):
                task_uuid = getattr(result, "taskUUID", None) or getattr(result, "task_uuid", None)
            if not task_uuid:
                return None, "Runware SDK did not return a task UUID."
            videos = loop.run_until_complete(rw.getResponse(task_uuid, numberResults=1))
            if videos and len(videos) > 0 and getattr(videos[0], "videoURL", None):
                url = videos[0].videoURL
                # #region agent log
                _debug_log("runware_client:sdk_success", "SDK returned videoURL", {"has_url": bool(url)}, "F")
                # #endregion
                return url, None
            return None, "Runware SDK returned no video URL."
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
        return None, "Runware failed: {}.".format(str(e))

    # Fallback: REST (sync) - often returns 400; kept for when SDK not installed.
    try:
        import requests
    except ImportError:
        return None, "Install the runware package for video generation: pip install runware"
    task_uuid = str(uuid.uuid4())
    headers = {"Content-Type": "application/json"}
    payload = [
        {"taskType": "authentication", "apiKey": api_key},
        {
            "taskType": "videoInference",
            "taskUUID": task_uuid,
            "positivePrompt": prompt,
            "model": model,
            "duration": duration_int,
            "width": int(width),
            "height": int(height),
            "deliveryMethod": "sync",
            "outputFormat": "MP4",
        },
    ]
    # #region agent log
    _debug_log("runware_client:rest_fallback", "REST sync submit", {"task_uuid": task_uuid}, "F")
    # #endregion
    try:
        r = requests.post(RUNWARE_API_BASE, headers=headers, json=payload, timeout=POLL_TIMEOUT_SECONDS)
        _debug_log("runware_client:submit_response", "submit response", {"status_code": r.status_code}, "F")
        r.raise_for_status()
        data = r.json()
    except requests.RequestException as e:
        resp = getattr(e, "response", None)
        err_body = getattr(resp, "text", None) or ""
        raw_content = getattr(resp, "content", None)
        _debug_log("runware_client:submit_error", "submit failed", {
            "body": err_body[:500], "body_len": len(err_body),
            "content_len": len(raw_content) if raw_content else 0,
            "reason": getattr(resp, "reason", None),
        }, "F")
        return None, "Runware API request failed: {}.".format(str(e))
    errors = data.get("errors") or []
    if errors:
        return None, "Runware error: {}.".format(errors[0].get("message", str(errors[0])))
    task_list = data.get("data") or []
    if not task_list or task_list[0].get("taskUUID") != task_uuid:
        return None, "Runware did not return task UUID."
    item = task_list[0]
    url = item.get("videoURL")
    if item.get("status") == "success" and url:
        return url, None
    if url:
        return url, None
    return None, "Video generation did not complete in time."


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
