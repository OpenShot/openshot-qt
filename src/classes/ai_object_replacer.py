"""
AI Object Replacement Engine (Vision-Guided).
Uses Phi-3.5 Vision on the NVIDIA GX10 to detect which frames contain
the target object, then replaces only those segments via Runware.

Pipeline:
  1. Sample frames from the video at regular intervals
  2. Send each frame to Phi-3.5 Vision → "Does this contain {object}?"
  3. Group consecutive detections into time ranges
  4. For each range: extract segment → Runware (Kling) regeneration
  5. Splice regenerated segments back into the original video
"""

import asyncio
import base64
import json
import os
import shutil
import subprocess
import tempfile
import uuid
from typing import Any, Dict, List, Optional, Tuple

from classes.logger import log


# ── Helpers ──────────────────────────────────────────────────────────

def _get_video_duration(video_path: str) -> float:
    """Get video duration using ffprobe."""
    try:
        cmd = [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", video_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(result.stdout.strip())
    except Exception as e:
        log.warning("Failed to get duration via ffprobe: %s", e)
        return 0.0


def _extract_frame(video_path: str, time_sec: float, output_path: str) -> bool:
    """Extract a single frame at the given timestamp."""
    try:
        cmd = [
            "ffmpeg", "-y", "-ss", str(time_sec), "-i", video_path,
            "-frames:v", "1", "-q:v", "2", output_path
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        return os.path.isfile(output_path)
    except Exception as e:
        log.warning("Failed to extract frame at %.2fs: %s", time_sec, e)
        return False


def _encode_image_b64(image_path: str) -> str:
    """Encode an image file to base64."""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


# ── Vision-based frame detection ────────────────────────────────────

def _ask_vision_model(image_b64: str, object_description: str, edge_url: str) -> dict:
    """
    Ask Phi-3.5 Vision on the GX10 whether a frame contains the target object.
    Returns {"found": bool, "confidence": float}.
    """
    import requests

    prompt = (
        f'Look at this image carefully. Does it contain: "{object_description}"?\n\n'
        'Answer with ONLY valid JSON: {"found": true/false, "confidence": 0.0-1.0}\n'
        'Set "found" to true ONLY if the described object is clearly visible.'
    )

    payload = {
        "model": "llava",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_b64}"
                        }
                    }
                ]
            }
        ],
        "max_tokens": 100,
        "temperature": 0.1,
    }

    try:
        url = f"{edge_url.rstrip('/')}/chat/completions"
        resp = requests.post(url, json=payload, timeout=30)
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]

        # Parse JSON from response (handle markdown fences)
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        data = json.loads(content)
        return {
            "found": bool(data.get("found", False)),
            "confidence": float(data.get("confidence", 0.0)),
        }
    except json.JSONDecodeError:
        # Try to extract a yes/no from plain text
        lower = content.lower() if 'content' in dir() else ""
        found = any(word in lower for word in ["true", "yes", "found", "visible", "present"])
        return {"found": found, "confidence": 0.5 if found else 0.2}
    except Exception as e:
        log.warning("Vision API call failed: %s", e)
        return {"found": False, "confidence": 0.0}


def detect_object_frames(
    video_path: str,
    object_description: str,
    sample_interval: float = 0.5,
    confidence_threshold: float = 0.5,
    edge_url: str = "http://10.19.183.5:8000/v1",
) -> List[Dict[str, Any]]:
    """
    Scan video frames to detect which ones contain the target object.

    Args:
        video_path: Path to the video file
        object_description: What object to look for (e.g. "water bottle")
        sample_interval: Seconds between frame samples (default 0.5s)
        confidence_threshold: Minimum confidence to consider "found" (default 0.5)
        edge_url: URL of the GX10 edge API

    Returns:
        List of dicts: [{"time_sec": float, "found": bool, "confidence": float}, ...]
    """
    duration = _get_video_duration(video_path)
    if duration <= 0:
        log.error("Cannot detect objects: invalid video duration")
        return []

    work_dir = tempfile.mkdtemp(prefix="detect_frames_")
    detections = []

    try:
        # Sample frames at regular intervals
        time_sec = 0.0
        frame_idx = 0
        while time_sec < duration:
            frame_path = os.path.join(work_dir, f"frame_{frame_idx:04d}.jpg")
            if _extract_frame(video_path, time_sec, frame_path):
                image_b64 = _encode_image_b64(frame_path)
                result = _ask_vision_model(image_b64, object_description, edge_url)

                detection = {
                    "time_sec": round(time_sec, 2),
                    "found": result["found"] and result["confidence"] >= confidence_threshold,
                    "confidence": result["confidence"],
                }
                detections.append(detection)
                log.info(
                    "Frame %.2fs: %s (confidence=%.2f)",
                    time_sec,
                    "FOUND" if detection["found"] else "not found",
                    result["confidence"],
                )
            else:
                detections.append({
                    "time_sec": round(time_sec, 2),
                    "found": False,
                    "confidence": 0.0,
                })

            time_sec += sample_interval
            frame_idx += 1
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)

    return detections


def _group_detections_into_ranges(
    detections: List[Dict[str, Any]],
    sample_interval: float = 0.5,
    merge_gap: float = 1.0,
) -> List[Tuple[float, float]]:
    """
    Group consecutive positive detections into (start_sec, end_sec) ranges.
    Merges ranges that are closer than `merge_gap` seconds.
    """
    if not detections:
        return []

    # Find runs of consecutive "found" detections
    ranges = []
    in_range = False
    range_start = 0.0

    for det in detections:
        if det["found"] and not in_range:
            range_start = det["time_sec"]
            in_range = True
        elif not det["found"] and in_range:
            # End of range — extend by one interval to capture the full segment
            ranges.append((range_start, det["time_sec"]))
            in_range = False

    # Close final range if still open
    if in_range:
        ranges.append((range_start, detections[-1]["time_sec"] + sample_interval))

    if not ranges:
        return []

    # Merge ranges that are close together
    merged = [ranges[0]]
    for start, end in ranges[1:]:
        prev_start, prev_end = merged[-1]
        if start - prev_end <= merge_gap:
            merged[-1] = (prev_start, end)
        else:
            merged.append((start, end))

    return merged


# ── Edge URL helper ──────────────────────────────────────────────────

def _get_edge_url() -> str:
    """Get the NVIDIA Edge API URL from settings or default."""
    try:
        from classes.app import get_app
        settings = get_app().get_settings()
        url = (settings.get("nvidia-edge-api-url") or "").strip()
        if url:
            return url
    except Exception:
        pass
    return "http://10.19.183.5:8000/v1"


# ── Main replacement function ───────────────────────────────────────

def replace_object_in_video(
    video_path: str,
    object_description: str,
    replacement_description: str,
    start_sec: float = 0.0,
    end_sec: float = -1.0,
    keyframe_interval: float = 0.5,
    gemini_api_key: Optional[str] = None,
    runware_api_key: Optional[str] = None,
    runware_model: str = "runway:1@2",
) -> Dict[str, Any]:
    """
    Replace an object in a video using vision-guided detection + AI regeneration.

    1. Scans frames with Phi-3.5 Vision to find where the object appears
    2. Groups detections into time ranges
    3. Regenerates each range via Runware (Kling/Runway)
    4. Splices everything back together

    Args:
        video_path: Path to source video
        object_description: What to find (e.g. "the water bottle on the table")
        replacement_description: What to replace it with (e.g. "a Red Bull can")
        start_sec: Start time to search (default 0)
        end_sec: End time to search (default -1 for end of video)
        runware_api_key: API key for Runware

    Returns:
        Dict with success, output_path, error, frames_scanned, frames_with_object, segments_replaced
    """
    from classes.video_editor import edit_segment

    result = {
        "success": False,
        "output_path": None,
        "error": None,
        "frames_scanned": 0,
        "frames_with_object": 0,
        "segments_replaced": 0,
    }

    if not os.path.isfile(video_path):
        result["error"] = f"Video file not found: {video_path}"
        return result

    # Resolve Runware API key
    rw_key = runware_api_key or os.getenv("RUNWARE_API_KEY", "").strip()
    if not rw_key:
        try:
            from classes.app import get_app
            settings = get_app().get_settings()
            rw_key = (settings.get("runware-api-key") or "").strip()
        except Exception:
            pass
    if not rw_key:
        result["error"] = "Runware API key not found. Please configure it in settings."
        return result

    total_duration = _get_video_duration(video_path)
    if total_duration <= 0:
        result["error"] = "Could not determine video duration."
        return result

    if end_sec < 0 or end_sec > total_duration:
        end_sec = total_duration

    edge_url = _get_edge_url()

    # ── Step 1: Detect frames containing the object ──────────────
    log.info(
        "Scanning frames for '%s' in video (%.1fs–%.1fs)...",
        object_description, start_sec, end_sec,
    )

    # Extract the segment to scan if not scanning the full video
    scan_path = video_path
    scan_offset = 0.0
    work_dir = tempfile.mkdtemp(prefix="ai_replace_")

    try:
        if start_sec > 0.1 or end_sec < total_duration - 0.1:
            scan_segment = os.path.join(work_dir, "scan_segment.mp4")
            cmd = [
                "ffmpeg", "-y", "-i", video_path,
                "-ss", str(start_sec), "-t", str(end_sec - start_sec),
                "-c:v", "libx264", "-c:a", "aac", scan_segment,
            ]
            subprocess.run(cmd, check=True, capture_output=True)
            scan_path = scan_segment
            scan_offset = start_sec

        detections = detect_object_frames(
            scan_path,
            object_description,
            sample_interval=keyframe_interval,
            edge_url=edge_url,
        )

        result["frames_scanned"] = len(detections)
        result["frames_with_object"] = sum(1 for d in detections if d["found"])

        if result["frames_with_object"] == 0:
            result["error"] = (
                f"Object '{object_description}' was not found in any of the "
                f"{result['frames_scanned']} frames scanned. "
                "Try a different description or check that the object is visible."
            )
            return result

        log.info(
            "Found '%s' in %d/%d frames",
            object_description,
            result["frames_with_object"],
            result["frames_scanned"],
        )

        # ── Step 2: Group into time ranges ───────────────────────
        ranges = _group_detections_into_ranges(
            detections,
            sample_interval=keyframe_interval,
            merge_gap=1.5,
        )

        # Adjust ranges back to original video timestamps
        ranges = [(r[0] + scan_offset, r[1] + scan_offset) for r in ranges]

        # Clamp ranges
        ranges = [
            (max(0, r[0]), min(total_duration, r[1]))
            for r in ranges
            if r[1] - r[0] >= 0.5  # skip very short ranges
        ]

        if not ranges:
            result["error"] = "Detected object but segments were too short to replace."
            return result

        log.info("Replacement ranges: %s", ranges)

        # ── Step 3: Replace each range ───────────────────────────
        # Strategy: process ranges from last to first so timestamps
        # don't shift as we splice.
        current_video = video_path
        segments_replaced = 0

        for seg_start, seg_end in reversed(ranges):
            duration = seg_end - seg_start
            if duration < 0.5:
                continue

            segment_dir = os.path.join(work_dir, f"seg_{segments_replaced}")
            os.makedirs(segment_dir, exist_ok=True)

            target_segment = os.path.join(segment_dir, "target.mp4")
            edited_segment = os.path.join(segment_dir, "edited.mp4")

            # Extract segment
            cmd_extract = [
                "ffmpeg", "-y", "-i", current_video,
                "-ss", str(seg_start), "-t", str(duration),
                "-c:v", "libx264", "-c:a", "aac", target_segment,
            ]
            subprocess.run(cmd_extract, check=True, capture_output=True)

            # Pad if needed (Runware minimum 3s)
            seg_duration = _get_video_duration(target_segment)
            MIN_INPUT_DURATION = 3.0
            if 0 < seg_duration < MIN_INPUT_DURATION:
                padded = os.path.join(segment_dir, "padded.mp4")
                pad_time = MIN_INPUT_DURATION - seg_duration
                cmd_pad = [
                    "ffmpeg", "-y", "-i", target_segment,
                    "-vf", f"tpad=stop_mode=clone:stop_duration={pad_time:.3f}",
                    "-c:v", "libx264", "-c:a", "aac", padded,
                ]
                subprocess.run(cmd_pad, check=True, capture_output=True)
                os.replace(padded, target_segment)

            # Upscale if needed (Kling minimum 720px)
            try:
                probe_cmd = [
                    "ffprobe", "-v", "error", "-select_streams", "v:0",
                    "-show_entries", "stream=width,height",
                    "-of", "csv=p=0", target_segment,
                ]
                dims = subprocess.run(probe_cmd, capture_output=True, text=True, check=True).stdout.strip()
                src_w, src_h = (int(x) for x in dims.split(","))
                min_dim = 720
                if src_w < min_dim or src_h < min_dim:
                    scale_factor = max(min_dim / src_w, min_dim / src_h)
                    new_w = int(src_w * scale_factor)
                    new_h = int(src_h * scale_factor)
                    new_w += new_w % 2
                    new_h += new_h % 2
                    upscaled = os.path.join(segment_dir, "upscaled.mp4")
                    cmd_scale = [
                        "ffmpeg", "-y", "-i", target_segment,
                        "-vf", f"scale={new_w}:{new_h}",
                        "-c:v", "libx264", "-c:a", "aac", upscaled,
                    ]
                    subprocess.run(cmd_scale, check=True, capture_output=True)
                    os.replace(upscaled, target_segment)
            except Exception as e:
                log.warning("Could not check/upscale dimensions: %s", e)

            # Send to Runware
            prompt = (
                f"A high quality video where {object_description} "
                f"is replaced with {replacement_description}"
            )
            log.info(
                "Replacing segment %.1f–%.1fs via Runware: %s",
                seg_start, seg_end, prompt,
            )
            try:
                edit_segment(
                    input_video_path=target_segment,
                    output_video_path=edited_segment,
                    prompt=prompt,
                    api_key=rw_key,
                    duration_seconds=5.0,
                )
            except Exception as e:
                log.error("Runware failed for segment %.1f–%.1fs: %s", seg_start, seg_end, e)
                continue  # Skip this segment, try others

            # Trim edited segment to match original duration
            edited_dur = _get_video_duration(edited_segment)
            if edited_dur > duration + 0.5:
                trimmed = os.path.join(segment_dir, "trimmed.mp4")
                cmd_trim = [
                    "ffmpeg", "-y", "-i", edited_segment,
                    "-t", str(duration),
                    "-c:v", "libx264", "-c:a", "aac", trimmed,
                ]
                subprocess.run(cmd_trim, check=True, capture_output=True)
                os.replace(trimmed, edited_segment)

            # Splice back into current_video
            spliced = os.path.join(segment_dir, f"spliced_{segments_replaced}.mp4")
            _splice_segment(current_video, edited_segment, seg_start, seg_end, spliced, segment_dir)

            if os.path.isfile(spliced):
                current_video = spliced
                segments_replaced += 1

        if segments_replaced == 0:
            result["error"] = "All segment replacements failed."
            return result

        # Copy final result to output
        final_output = os.path.join(
            os.path.dirname(video_path),
            f"replaced_{uuid.uuid4().hex[:8]}.mp4",
        )
        shutil.copy2(current_video, final_output)

        result["success"] = True
        result["output_path"] = final_output
        result["segments_replaced"] = segments_replaced

    except subprocess.CalledProcessError as e:
        result["error"] = f"FFmpeg error: {e.stderr if hasattr(e, 'stderr') else str(e)}"
        log.error("FFmpeg failed: %s", e, exc_info=True)
    except Exception as e:
        result["error"] = f"Object replacement failed: {str(e)}"
        log.error("Object replacement failed: %s", e, exc_info=True)
    finally:
        if 'work_dir' in locals() and os.path.exists(work_dir):
            shutil.rmtree(work_dir, ignore_errors=True)

    return result


def _splice_segment(
    original_video: str,
    edited_segment: str,
    seg_start: float,
    seg_end: float,
    output_path: str,
    work_dir: str,
):
    """Splice an edited segment back into the original video at the given time range."""
    total_duration = _get_video_duration(original_video)
    parts_file = os.path.join(work_dir, "parts.txt")
    parts = []

    # Head
    if seg_start > 0.1:
        head_path = os.path.join(work_dir, "head.mp4")
        cmd = [
            "ffmpeg", "-y", "-i", original_video,
            "-t", str(seg_start),
            "-c:v", "libx264", "-c:a", "aac", head_path,
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        parts.append(head_path)

    # Edited segment
    parts.append(edited_segment)

    # Tail
    if seg_end < total_duration - 0.1:
        tail_path = os.path.join(work_dir, "tail.mp4")
        cmd = [
            "ffmpeg", "-y", "-i", original_video,
            "-ss", str(seg_end),
            "-c:v", "libx264", "-c:a", "aac", tail_path,
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        parts.append(tail_path)

    # Concat
    with open(parts_file, "w") as f:
        for p in parts:
            f.write(f"file '{p}'\n")

    cmd_concat = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", parts_file,
        "-c", "copy", output_path,
    ]
    subprocess.run(cmd_concat, check=True, capture_output=True)
