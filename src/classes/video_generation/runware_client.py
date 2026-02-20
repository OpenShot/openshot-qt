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
        _path = "/home/vboxuser/Projects/Flowcut/.cursor/debug.log"
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
    duration_seconds=5,
    model="klingai:kling@o1",
    width=1280,
    height=720,
    input_video_url=None,
):
    """
    Generate video via Runware. Prefers the official SDK (WebSocket); falls back to REST.
    Call from worker thread only.

    Args:
        input_video_url (str): Optional URL of an input video for video-to-video generation.
                               If provided, the model should support it (e.g. Kling).
    Returns:
        (video_url, None) on success, or (None, error_message) on failure.
    """
    if not api_key or not str(api_key).strip():
        return None, "Video generation is not configured. Add your Runware API key in Preferences."
    prompt = (prompt or "").strip()
    if len(prompt) < 2:
        return None, "Prompt must be at least 2 characters."

    # ── NVIDIA Edge (Cosmos) disabled — OOM issues on GX10 ────────
    # try:
    #     from classes.video_generation.edge_video_client import edge_generate_video, is_edge_available
    #     if is_edge_available():
    #         log.info("Using NVIDIA Edge (Cosmos) for video generation")
    #         path, err = edge_generate_video(
    #             prompt=prompt,
    #             duration_seconds=float(duration_seconds),
    #             width=width or 1024,
    #             height=height or 576,
    #             input_video_url=input_video_url,
    #         )
    #         if path and not err:
    #             return path, None
    #         log.warning("Edge video gen failed (%s), falling back to Runware", err)
    # except Exception as e:
    #     log.debug("Edge not available: %s, using Runware", e)

    # ── Fall back to Runware cloud ──────────────────────────────────
    api_key = api_key.strip()
    duration_int = float(max(1, min(10, duration_seconds)))

    # Prefer Runware SDK (WebSocket). Use async delivery + getResponse polling to avoid
    # "Connection lost while waiting for video response" (sync holds one WebSocket wait for minutes).
    try:
        from runware import Runware, IVideoInference
        from runware.types import IAsyncTaskResponse, IVideoInputs
        import asyncio
        # #region agent log
        _debug_log("runware_client:sdk_start", "using Runware SDK", {"model": model, "duration": duration_int, "video_input": bool(input_video_url)}, "F")
        # #endregion
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        rw = None
        try:
            rw = Runware(api_key=api_key, timeout=POLL_TIMEOUT_SECONDS)
            loop.run_until_complete(rw.connect())
            
            # Construct request
            req_kwargs = dict(
                positivePrompt=prompt,
                model=model,
                deliveryMethod="async",
            )
            # Kling O1 video-edit: duration is inferred from input video
            if not input_video_url:
                req_kwargs["duration"] = duration_int
            if width is not None:
                req_kwargs["width"] = int(width)
            if height is not None:
                req_kwargs["height"] = int(height)
            req = IVideoInference(**req_kwargs)
            
            # Add input video for video-to-video generation (Kling O1 video-edit workflow)
            if input_video_url:
                req.inputs = IVideoInputs(video=input_video_url)

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
            "deliveryMethod": "sync",
            "outputFormat": "MP4",
        },
    ]
    if not input_video_url:
        payload[1]["duration"] = duration_int
    if width is not None:
        payload[1]["width"] = int(width)
    if height is not None:
        payload[1]["height"] = int(height)
    if input_video_url:
        payload[1]["inputs"] = {"video": input_video_url}
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


def runware_generate_morph_video(
    api_key,
    prompt,
    start_image_url,
    end_image_url,
    duration_seconds=5,
    model="klingai:kling@o1",
    width=1280,
    height=720,
):
    """
    Generate a morph/transition video using Kling with start and end frame images.
    The model generates a video that smoothly transitions from start_image to end_image.
    Call from worker thread only.

    Args:
        api_key: Runware API key
        prompt: Text prompt describing the transition
        start_image_url: Public URL of the first frame (start of transition)
        end_image_url: Public URL of the last frame (end of transition)
        duration_seconds: Duration of the generated video (float, 1-10)
        model: Kling model identifier
        width: Output width (None to let model decide)
        height: Output height (None to let model decide)

    Returns:
        (video_url, None) on success, or (None, error_message) on failure.
    """
    if not api_key or not str(api_key).strip():
        return None, "Runware API key not configured."
    if not start_image_url or not end_image_url:
        return None, "Both start and end image URLs are required for morph transition."
    prompt = (prompt or "").strip()
    if len(prompt) < 2:
        return None, "Prompt must be at least 2 characters."

    # ── NVIDIA Edge (Cosmos) disabled — OOM issues on GX10 ────────
    # try:
    #     from classes.video_generation.edge_video_client import edge_generate_morph_video, is_edge_available
    #     if is_edge_available():
    #         log.info("Using NVIDIA Edge (Cosmos) for morph transition")
    #         path, err = edge_generate_morph_video(
    #             start_image_url=start_image_url,
    #             end_image_url=end_image_url,
    #             prompt=prompt,
    #             duration_seconds=float(duration_seconds),
    #             width=width or 1024,
    #             height=height or 576,
    #         )
    #         if path and not err:
    #             return path, None
    #         log.warning("Edge morph failed (%s), falling back to Runware", err)
    # except Exception as e:
    #     log.debug("Edge not available for morph: %s, using Runware", e)

    # ── Fall back to Runware cloud ──────────────────────────────────
    api_key = api_key.strip()
    duration_val = int(max(1, min(10, duration_seconds)))

    try:
        from runware import Runware, IVideoInference
        from runware.types import IAsyncTaskResponse, IVideoInputs, IInputFrame
        import asyncio

        log.info("Morph transition: model=%s duration=%d start=%s end=%s",
                 model, duration_val, start_image_url[:60], end_image_url[:60])

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        rw = None
        try:
            rw = Runware(api_key=api_key, timeout=POLL_TIMEOUT_SECONDS)
            loop.run_until_complete(rw.connect())

            # Kling O1 only supports specific resolutions
            SUPPORTED_DIMS = [(1920, 1080), (1080, 1920), (1440, 1440)]

            def _pick_best_resolution(w, h):
                """Pick the closest supported resolution based on aspect ratio."""
                if w is None or h is None:
                    return 1920, 1080  # default landscape
                aspect = w / max(h, 1)
                if aspect > 1.2:
                    return 1920, 1080   # landscape
                elif aspect < 0.8:
                    return 1080, 1920   # portrait
                else:
                    return 1440, 1440   # square-ish

            res_w, res_h = _pick_best_resolution(width, height)
            log.info("Morph: using resolution %dx%d", res_w, res_h)

            # Kling O1 requires frame images via inputs.frameImages (not top-level)
            # Dimensions are inferred from the input images — width/height not supported
            inputs_obj = IVideoInputs(
                frameImages=[
                    IInputFrame(image=start_image_url, frame="first"),
                    IInputFrame(image=end_image_url, frame="last"),
                ],
            )

            req_kwargs = dict(
                positivePrompt=prompt,
                model=model,
                duration=duration_val,
                deliveryMethod="async",
                inputs=inputs_obj,
            )

            req = IVideoInference(**req_kwargs)
            result = loop.run_until_complete(rw.videoInference(requestVideo=req))

            task_uuid = None
            if isinstance(result, IAsyncTaskResponse):
                task_uuid = getattr(result, "taskUUID", None) or getattr(result, "task_uuid", None)
            if not task_uuid:
                return None, "Runware SDK did not return a task UUID for morph."

            videos = loop.run_until_complete(rw.getResponse(task_uuid, numberResults=1))
            if videos and len(videos) > 0 and getattr(videos[0], "videoURL", None):
                url = videos[0].videoURL
                log.info("Morph transition video generated: %s", url[:80] if url else None)
                return url, None
            return None, "Runware SDK returned no video URL for morph."
        finally:
            if rw is not None:
                try:
                    loop.run_until_complete(rw.disconnect())
                except Exception:
                    pass
            loop.close()
    except ImportError:
        return None, "Runware SDK is required for morph transitions. Install with: pip install runware"
    except Exception as e:
        log.error("Morph transition failed: %s", e, exc_info=True)
        return None, "Morph transition failed: {}.".format(str(e))


def download_video_to_path(video_url, local_path):
    """
    Download video from URL to local path, or copy if it's already a local file.
    Call from worker thread only.

    Returns:
        (True, None) on success, (False, error_message) on failure.
    """
    if not video_url or not local_path:
        return False, "Missing URL or path."

    # Handle local file paths (from NVIDIA Edge / Cosmos)
    import os
    if os.path.isfile(video_url):
        try:
            import shutil
            shutil.copy2(video_url, local_path)
            return True, None
        except OSError as e:
            return False, f"Failed to copy local video: {e}"

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
