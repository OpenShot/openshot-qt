"""
OpenAI Text-to-Speech API client.

This module is logic-only (no Qt). Call it from worker threads.
"""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from typing import List, Optional, Tuple

from classes.logger import log


@dataclass(frozen=True)
class TTSError(Exception):
    """Structured error for TTS API failures."""

    message: str
    status_code: Optional[int] = None
    detail: Optional[str] = None

    def __str__(self) -> str:
        bits = [self.message]
        if self.status_code is not None:
            bits.append(f"(status={self.status_code})")
        if self.detail:
            bits.append(self.detail)
        return " ".join(bits)


def _auth_headers(api_key: str) -> dict:
    """Build authentication headers for OpenAI API."""
    key = (api_key or "").strip()
    if not key:
        raise TTSError("Missing OpenAI API key.")
    return {"Authorization": f"Bearer {key}"}


def openai_tts_generate(
    *,
    api_key: str,
    text: str,
    voice: str = "alloy",
    model: str = "tts-1",
    speed: float = 1.0,
    output_path: str,
    timeout_seconds: float = 60.0,
) -> None:
    """
    Generate speech from text using OpenAI TTS API.

    Args:
        api_key: OpenAI API key
        text: Text to convert to speech (max 4096 characters)
        voice: One of: alloy, echo, fable, onyx, nova, shimmer
        model: tts-1 (fast) or tts-1-hd (high quality)
        speed: 0.25 to 4.0 (default 1.0)
        output_path: Where to save the MP3 file
        timeout_seconds: Request timeout

    Raises:
        TTSError: On any failure
    """
    # Validate inputs
    text_cleaned = (text or "").strip()
    if not text_cleaned:
        raise TTSError("Text is required for TTS generation.")

    if len(text_cleaned) > 4096:
        raise TTSError(
            f"Text too long ({len(text_cleaned)} chars). Maximum is 4096 characters per request.",
            detail="Use chunk_text_for_tts() to split long text.",
        )

    voice = (voice or "alloy").strip().lower()
    valid_voices = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]
    if voice not in valid_voices:
        raise TTSError(
            f"Invalid voice '{voice}'. Must be one of: {', '.join(valid_voices)}",
        )

    model = (model or "tts-1").strip().lower()
    valid_models = ["tts-1", "tts-1-hd"]
    if model not in valid_models:
        raise TTSError(
            f"Invalid model '{model}'. Must be one of: {', '.join(valid_models)}",
        )

    speed = float(speed)
    if not (0.25 <= speed <= 4.0):
        raise TTSError(f"Invalid speed {speed}. Must be between 0.25 and 4.0.")

    path = (output_path or "").strip()
    if not path:
        raise TTSError("output_path is required.")

    # Import requests
    try:
        import requests
    except ImportError as exc:
        raise TTSError("requests library is required.") from exc

    # Build request
    url = "https://api.openai.com/v1/audio/speech"
    headers = _auth_headers(api_key)
    headers["Content-Type"] = "application/json"

    payload = {
        "model": model,
        "input": text_cleaned,
        "voice": voice,
        "speed": speed,
    }

    # Make request
    try:
        log.debug("OpenAI TTS request: %d chars, voice=%s, model=%s", len(text_cleaned), voice, model)
        resp = requests.post(url, headers=headers, json=payload, timeout=float(timeout_seconds))
    except requests.RequestException as exc:
        raise TTSError(f"OpenAI TTS request failed: {exc}") from exc

    # Check status code
    if resp.status_code == 401:
        raise TTSError(
            "Authentication failed. Check your OpenAI API key in Preferences > AI.",
            status_code=401,
        )
    elif resp.status_code == 429:
        raise TTSError(
            "Rate limit exceeded. Please wait before generating more audio.",
            status_code=429,
        )
    elif resp.status_code == 400:
        # Try to extract error message from response
        detail = ""
        try:
            error_data = resp.json()
            if isinstance(error_data, dict) and "error" in error_data:
                error_msg = error_data.get("error", {})
                if isinstance(error_msg, dict):
                    detail = error_msg.get("message", "")
                else:
                    detail = str(error_msg)
        except Exception:
            detail = (resp.text or "")[:500]

        raise TTSError(
            "Bad request. Check your parameters (text, voice, model).",
            status_code=400,
            detail=detail,
        )
    elif resp.status_code < 200 or resp.status_code >= 300:
        raise TTSError(
            "OpenAI TTS request failed.",
            status_code=resp.status_code,
            detail=(resp.text or "")[:500],
        )

    # Write binary audio data to file
    try:
        with open(path, "wb") as f:
            f.write(resp.content)
        log.info("OpenAI TTS generated: %s (%d bytes)", path, len(resp.content))
    except OSError as exc:
        raise TTSError(f"Could not write audio file: {exc}") from exc


def chunk_text_for_tts(text: str, max_chars: int = 4096) -> List[str]:
    """
    Split text into chunks suitable for TTS API.

    Splits on sentence boundaries (. ! ?) to preserve natural speech.
    If a single sentence exceeds max_chars, splits on commas, then spaces.

    Args:
        text: Text to split
        max_chars: Maximum characters per chunk (default 4096 for OpenAI)

    Returns:
        List of text chunks, each <= max_chars
    """
    text_cleaned = (text or "").strip()
    if not text_cleaned:
        return []

    if len(text_cleaned) <= max_chars:
        return [text_cleaned]

    chunks = []

    # Split on sentence boundaries: . ! ?
    # Use regex to split while preserving the punctuation
    sentences = re.split(r'([.!?])\s+', text_cleaned)

    # Reconstruct sentences with their punctuation
    reconstructed = []
    for i in range(0, len(sentences), 2):
        if i + 1 < len(sentences):
            # Sentence + punctuation
            reconstructed.append(sentences[i] + sentences[i + 1])
        else:
            # Last fragment (no punctuation)
            if sentences[i].strip():
                reconstructed.append(sentences[i])

    current_chunk = ""

    for sentence in reconstructed:
        sentence = sentence.strip()
        if not sentence:
            continue

        # If this sentence alone exceeds the limit, we need to split it further
        if len(sentence) > max_chars:
            # Save current chunk if any
            if current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = ""

            # Split oversized sentence on commas
            parts = sentence.split(',')
            temp_part = ""

            for part in parts:
                part = part.strip()
                if not part:
                    continue

                if len(part) > max_chars:
                    # Even a single part is too long - split on spaces
                    if temp_part:
                        chunks.append(temp_part.strip())
                        temp_part = ""

                    words = part.split()
                    word_chunk = ""
                    for word in words:
                        if len(word_chunk) + len(word) + 1 <= max_chars:
                            word_chunk += (" " if word_chunk else "") + word
                        else:
                            if word_chunk:
                                chunks.append(word_chunk.strip())
                            word_chunk = word

                    if word_chunk:
                        temp_part = word_chunk

                elif len(temp_part) + len(part) + 2 <= max_chars:  # +2 for comma and space
                    temp_part += (", " if temp_part else "") + part
                else:
                    if temp_part:
                        chunks.append(temp_part.strip())
                    temp_part = part

            if temp_part:
                current_chunk = temp_part

            continue

        # Normal case: add sentence to current chunk
        potential_chunk = current_chunk + (" " if current_chunk else "") + sentence

        if len(potential_chunk) <= max_chars:
            current_chunk = potential_chunk
        else:
            # Current chunk is full, save it and start new chunk
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = sentence

    # Don't forget the last chunk
    if current_chunk:
        chunks.append(current_chunk.strip())

    log.info("Chunked text into %d chunks (max %d chars each)", len(chunks), max_chars)
    return chunks


def concatenate_audio_ffmpeg(audio_paths: List[str], output_path: str) -> Tuple[bool, Optional[str]]:
    """
    Concatenate audio files using ffmpeg (concat demuxer).

    Args:
        audio_paths: List of audio file paths to concatenate (in order)
        output_path: Where to save the concatenated audio

    Returns:
        (success, error_message_or_none)
    """
    if not audio_paths or not output_path:
        return False, "No inputs or output path"

    if len(audio_paths) == 1:
        # Only one file, just copy it
        try:
            import shutil
            shutil.copy(audio_paths[0], output_path)
            return True, None
        except Exception as e:
            return False, f"Failed to copy file: {e}"

    # Create a temporary file list for ffmpeg
    list_dir = os.path.dirname(output_path)
    list_path = os.path.join(list_dir, f"concat_list_{os.getpid()}.txt")

    try:
        # Write file list
        with open(list_path, "w", encoding="utf-8") as f:
            for p in audio_paths:
                p_abs = os.path.abspath(p)
                # Escape single quotes for ffmpeg
                p_escaped = p_abs.replace("'", "'\\''")
                f.write(f"file '{p_escaped}'\n")

        # Run ffmpeg
        result = subprocess.run(
            [
                "ffmpeg",
                "-y",  # Overwrite output file
                "-f", "concat",  # Use concat demuxer
                "-safe", "0",  # Allow absolute paths
                "-i", list_path,  # Input file list
                "-c", "copy",  # Copy codec (no re-encoding)
                output_path,
            ],
            capture_output=True,
            text=True,
            timeout=600,
        )

        if result.returncode != 0:
            error = result.stderr or result.stdout or "ffmpeg failed"
            log.error("ffmpeg concatenation failed: %s", error)
            return False, error

        log.info("Concatenated %d audio files to %s", len(audio_paths), output_path)
        return True, None

    except subprocess.TimeoutExpired:
        return False, "ffmpeg timed out"
    except FileNotFoundError:
        return False, "ffmpeg not found. Please install ffmpeg."
    except Exception as e:
        log.error("concatenate_audio_ffmpeg: %s", e, exc_info=True)
        return False, str(e)
    finally:
        # Clean up temporary file list
        if os.path.isfile(list_path):
            try:
                os.remove(list_path)
            except Exception:
                pass
