"""
AI Morph Transition Generator.

Creates a smooth morph/transition video between two clips using Kling (via Runware).

Pipeline:
  1. Extract the last frame of clip A
  2. Extract the first frame of clip B
  3. Upload both frames to temporary hosting
  4. Send to Runware (Kling) with frameImages[first, last] to generate a morph video
  5. Download the result and return the path
"""

import os
import subprocess
import tempfile
import uuid
from typing import Optional, Tuple

from classes.logger import log
from classes.video_editor import upload_to_temp_hosting
from classes.video_generation.runware_client import (
    runware_generate_morph_video,
    download_video_to_path,
)


def _extract_frame(video_path: str, time_sec: float, output_path: str) -> bool:
    """Extract a single frame from a video at the given time using ffmpeg."""
    cmd = [
        "ffmpeg", "-y",
        "-ss", str(time_sec),
        "-i", video_path,
        "-frames:v", "1",
        "-q:v", "2",  # high quality JPEG
        output_path,
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        return os.path.isfile(output_path) and os.path.getsize(output_path) > 0
    except subprocess.CalledProcessError as e:
        log.error("Frame extraction failed: %s", e.stderr if hasattr(e, 'stderr') else e)
        return False


def _get_video_duration(video_path: str) -> float:
    """Get video duration in seconds using ffprobe."""
    try:
        cmd = [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", video_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(result.stdout.strip())
    except Exception:
        return 0.0


def generate_morph_transition(
    video_a_path: str,
    video_b_path: str,
    output_path: str,
    prompt: str = "",
    duration_seconds: float = 5.0,
    api_key: str = "",
    model: str = "klingai:kling@o1",
    time_a: Optional[float] = None,
    time_b: Optional[float] = None,
) -> Tuple[bool, Optional[str]]:
    """
    Generate a morph transition video between two clips.

    Extracts the last frame of video A and first frame of video B,
    then uses Kling (via Runware) to generate a smooth morph between them.

    Args:
        video_a_path: Path to the first video (transition starts from its last frame)
        video_b_path: Path to the second video (transition ends at its first frame)
        output_path: Where to save the generated morph video
        prompt: Descriptive prompt for the transition (auto-generated if empty)
        duration_seconds: Duration of the morph video (3-10, default 5)
        api_key: Runware API key
        model: Kling model to use
        time_a: Time in seconds to extract frame from video A (None = last frame)
        time_b: Time in seconds to extract frame from video B (None = first frame, 0.0)

    Returns:
        (True, None) on success, (False, error_message) on failure.
    """
    # Validate inputs
    if not os.path.isfile(video_a_path):
        return False, f"Video A not found: {video_a_path}"
    if not os.path.isfile(video_b_path):
        return False, f"Video B not found: {video_b_path}"

    # Resolve API key
    rw_key = api_key.strip() if api_key else ""
    if not rw_key:
        rw_key = os.getenv("RUNWARE_API_KEY", "").strip()
    if not rw_key:
        try:
            from classes.app import get_app
            settings = get_app().get_settings()
            rw_key = (settings.get("runware-api-key") or "").strip()
        except Exception:
            pass
    if not rw_key:
        return False, "Runware API key not configured. Add it in Preferences."

    # Clamp duration to API limits (Kling: 1-10s, min 3 for good morphs)
    duration_seconds = float(max(3, min(10, duration_seconds)))

    work_dir = tempfile.mkdtemp(prefix="ai_morph_")
    try:
        # 1. Extract last frame of clip A
        if time_a is None:
            dur_a = _get_video_duration(video_a_path)
            time_a = max(0.0, dur_a - 0.1) if dur_a > 0 else 0.0
        frame_a_path = os.path.join(work_dir, "frame_a.jpg")
        log.info("Morph: extracting frame from clip A at t=%.2fs", time_a)
        if not _extract_frame(video_a_path, time_a, frame_a_path):
            return False, "Failed to extract last frame from clip A."

        # 2. Extract first frame of clip B
        if time_b is None:
            time_b = 0.0
        frame_b_path = os.path.join(work_dir, "frame_b.jpg")
        log.info("Morph: extracting frame from clip B at t=%.2fs", time_b)
        if not _extract_frame(video_b_path, time_b, frame_b_path):
            return False, "Failed to extract first frame from clip B."

        # 3. Upload both frames to temporary hosting
        log.info("Morph: uploading start frame...")
        start_url = upload_to_temp_hosting(frame_a_path)
        log.info("Morph: uploading end frame...")
        end_url = upload_to_temp_hosting(frame_b_path)

        # 4. Build prompt
        if not prompt.strip():
            prompt = (
                "Smooth cinematic morph transition between two scenes. "
                "The camera smoothly transitions from the first scene to the second scene. "
                "Natural motion, seamless blend, high quality."
            )

        # 5. Detect frame dimensions for best Kling resolution pick
        frame_w, frame_h = None, None
        try:
            probe_cmd = [
                "ffprobe", "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height",
                "-of", "csv=p=0:s=x",
                frame_a_path,
            ]
            probe_out = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
            parts = probe_out.stdout.strip().split("x")
            if len(parts) == 2:
                frame_w, frame_h = int(parts[0]), int(parts[1])
                log.info("Morph: source frame dimensions %dx%d", frame_w, frame_h)
        except Exception:
            pass

        # 6. Generate morph video via Kling
        log.info("Morph: generating via Kling (duration=%.1fs)...", duration_seconds)
        video_url, error = runware_generate_morph_video(
            api_key=rw_key,
            prompt=prompt,
            start_image_url=start_url,
            end_image_url=end_url,
            duration_seconds=duration_seconds,
            model=model,
            width=frame_w,
            height=frame_h,
        )

        if error:
            return False, f"Morph generation failed: {error}"
        if not video_url:
            return False, "Morph generation returned no URL."

        # 6. Download result
        log.info("Morph: downloading result...")
        success, dl_error = download_video_to_path(video_url, output_path)
        if not success:
            return False, f"Failed to download morph video: {dl_error}"

        log.info("Morph transition saved to %s", output_path)
        return True, None

    except Exception as e:
        log.error("Morph transition failed: %s", e, exc_info=True)
        return False, f"Morph transition error: {str(e)}"
    finally:
        # Clean up temp frames
        import shutil
        shutil.rmtree(work_dir, ignore_errors=True)
