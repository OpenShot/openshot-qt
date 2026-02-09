"""
Utility for tagging imported video clips with Google's Gemma/Gemini (via google-genai).
Extracts frames every N seconds, uploads in small batches to avoid per-request limits,
parses structured tags, and returns ai_metadata compatible with the rest of the app.
"""

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import openshot  # type: ignore

from classes.logger import log

try:  # Optional env loader
    from dotenv import load_dotenv  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    load_dotenv = None

genai: Any = None
genai_types: Any = None


class GeminiVideoTagger:
    """Tag videos using Google's Gemma 3 vision capabilities."""

    @staticmethod
    def _load_env_file_simple(env_path: Path, override: bool = False) -> None:
        """Load a .env file without external deps (supports KEY=VALUE)."""
        try:
            if not env_path.exists() or not env_path.is_file():
                return

            for raw_line in env_path.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue

                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if not key:
                    continue

                if override or key not in os.environ:
                    os.environ[key] = value
        except Exception as exc:  # pragma: no cover
            log.debug(f"simple .env load failed for {env_path}: {exc}")

    def __init__(self, api_key: Optional[str] = None, frame_interval: int = 5, max_frames: int = 30,
                 max_files_per_request: int = 8):
        root_env = Path(__file__).resolve().parents[2] / ".env"
        cwd_env = Path.cwd() / ".env"

        # Load API keys from .env (preferred: python-dotenv; fallback: simple parser).
        if load_dotenv:
            try:
                if root_env.exists():
                    load_dotenv(dotenv_path=root_env, override=False)
                if cwd_env != root_env and cwd_env.exists():
                    load_dotenv(dotenv_path=cwd_env, override=False)
            except Exception as exc:  # pragma: no cover - optional log
                log.debug(f"dotenv load failed: {exc}")
        else:
            self._load_env_file_simple(root_env)
            if cwd_env != root_env:
                self._load_env_file_simple(cwd_env)

        resolved = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.api_key = (resolved or "").strip() or None
        self.frame_interval = frame_interval
        self.max_frames = max_frames
        # Gemini file API typically allows ~10 parts per request; stay under to be safe.
        self.max_files_per_request = max(1, min(max_files_per_request, 10))

    @staticmethod
    def empty_metadata() -> Dict[str, Any]:
        return {
            "analyzed": False,
            "analysis_version": "2.0",
            "analysis_date": datetime.now().isoformat(),
            "provider": "gemini",
            "scene_descriptions": [],  # List of {time: float, description: str}
            "tags": {
                "objects": [],
                "scenes": [],
                "activities": [],
                "mood": [],
                "quality": {}
            },
            "faces": [],
            "colors": {},
            "audio_analysis": {},
            "description": "",
            "confidence": 0.0
        }

    def analyze_video(self, video_path: str) -> Dict[str, Any]:
        if not self.api_key:
            log.warning(
                "Gemini API key not configured; skipping tagging (set GEMINI_API_KEY in .env or environment)"
            )
            return self.empty_metadata()

        if not self._ensure_google_genai_available():
            log.warning(
                "google-genai not installed in the runtime Python; skipping tagging (install into .venv)"
            )
            return self.empty_metadata()

        try:
            with tempfile.TemporaryDirectory(prefix="gemini_frames_") as temp_dir:
                frames_with_times = self._extract_frames(video_path, Path(temp_dir))
                if not frames_with_times:
                    log.warning("No frames extracted for Gemini tagging")
                    return self.empty_metadata()

                scene_descriptions = self._analyze_in_chunks(frames_with_times)

                return self._build_metadata(scene_descriptions)
        except Exception as exc:  # pragma: no cover - defensive
            log.error(f"Gemini tagging failed for {video_path}: {exc}")
            return self.empty_metadata()

    def _extract_frames(self, video_path: str, temp_dir: Path) -> List[tuple]:
        """Extract frames at regular intervals and return list of (frame_path, timestamp_seconds) tuples."""
        frame_data: List[tuple] = []
        reader = None
        try:
            clip = openshot.Clip(video_path)
            reader = clip.Reader()
            # Some builds require explicitly opening the reader
            try:
                reader.Open()
            except Exception:
                pass

            duration = reader.info.duration or 0.0
            fps = reader.info.fps.ToFloat() or 1.0
            total_frames = max(int(duration * fps), 1)

            # 1 frame every frame_interval seconds, capped at max_frames
            count = max(1, min(self.max_frames, int(duration / self.frame_interval) + 1))
            frame_numbers = {
                min(total_frames - 1, int(i * self.frame_interval * fps))
                for i in range(count)
            }
            if not frame_numbers:
                frame_numbers = {0}

            for idx, frame_num in enumerate(sorted(frame_numbers)):
                try:
                    frame = reader.GetFrame(frame_num)
                    frame_name = f"frame_{idx:03d}.jpg"
                    frame_path = temp_dir / frame_name
                    frame.Save(str(frame_path), 1.0, "JPG")
                    # Calculate timestamp in seconds
                    timestamp = frame_num / fps
                    frame_data.append((frame_path, timestamp))
                except Exception as exc:
                    log.warning(f"Failed to extract frame {frame_num}: {exc} for file {video_path}")
        except Exception as exc:
            log.error(f"Error extracting frames for Gemini tagging: {exc}")
        finally:
            try:
                if reader:
                    reader.Close()
            except Exception:
                pass

        return frame_data

    def _ensure_google_genai_available(self) -> bool:
        """Ensure google-genai is importable."""
        global genai, genai_types

        if genai is not None and genai_types is not None:
            return True

        try:
            from google import genai as imported_genai  # type: ignore
            from google.genai import types as imported_types  # type: ignore

            genai = imported_genai
            genai_types = imported_types
            return True
        except Exception as exc:
            log.debug(f"google-genai import failed: {exc}")
            genai = None
            genai_types = None
            return False

    def _analyze_in_chunks(self, frames_with_times: List[tuple]) -> List[Dict[str, Any]]:
        """Analyze frames in chunks and return scene descriptions with timestamps."""
        client = genai.Client(api_key=self.api_key)
        scene_descriptions: List[Dict[str, Any]] = []

        for chunk_start in range(0, len(frames_with_times), self.max_files_per_request):
            chunk = frames_with_times[chunk_start:chunk_start + self.max_files_per_request]
            uploaded = []
            try:
                # Upload frames and track their timestamps
                frame_timestamps = []
                for frame_path, timestamp in chunk:
                    uploaded_file = client.files.upload(file=str(frame_path))
                    uploaded.append(uploaded_file)
                    frame_timestamps.append(timestamp)

                contents = [
                    *[genai_types.Part.from_uri(file_uri=f.uri, mime_type=f.mime_type) for f in uploaded],
                    genai_types.Part.from_text(text=self._prompt())
                ]

                response = client.models.generate_content(
                    model="models/gemma-3-27b-it",
                    contents=contents,
                    config=genai_types.GenerateContentConfig(
                        temperature=0.1,
                        max_output_tokens=512
                    ),
                )

                text = getattr(response, "text", "") or ""
                descriptions = self._parse_response(text, frame_timestamps)
                scene_descriptions.extend(descriptions)
            except Exception as exc:
                log.error(f"Gemini request failed for chunk starting at {chunk_start}: {exc}")
            finally:
                for uploaded_file in uploaded:
                    try:
                        client.files.delete(name=uploaded_file.name)
                    except Exception:
                        pass

        return scene_descriptions

    def _parse_response(self, text: str, frame_timestamps: List[float]) -> List[Dict[str, Any]]:
        """Parse response and return list of scene descriptions with timestamps."""
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`\n")
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]
        
        scene_descriptions = []
        
        try:
            # Find JSON block if wrapped in extra text
            json_text = cleaned
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start != -1 and end != -1:
                json_text = cleaned[start:end + 1]
            data = json.loads(json_text)
            
            # Check if response contains per-frame descriptions
            if isinstance(data, dict) and "frames" in data:
                frames = data.get("frames", [])
                for i, frame_desc in enumerate(frames):
                    if i < len(frame_timestamps):
                        if isinstance(frame_desc, dict) and "description" in frame_desc:
                            desc = frame_desc["description"]
                        else:
                            desc = str(frame_desc)
                        scene_descriptions.append({
                            "time": frame_timestamps[i],
                            "description": desc
                        })
            # Fallback: single description for all frames
            elif isinstance(data, dict) and "description" in data:
                description = data.get("description", "")
                if description and frame_timestamps:
                    # Use the first timestamp for single description
                    scene_descriptions.append({
                        "time": frame_timestamps[0],
                        "description": description
                    })
        except Exception as e:
            log.warning(f"Failed to parse JSON response: {e}")
            # Best-effort fallback: use the raw text as a single description
            if cleaned and frame_timestamps:
                scene_descriptions.append({
                    "time": frame_timestamps[0],
                    "description": cleaned
                })

        return scene_descriptions

    def _prompt(self) -> str:
        return (
            "You are analyzing video frames sampled every 5 seconds. "
            "For EACH frame provided, describe what is happening in detail (2-3 sentences). "
            "Return a JSON object with a 'frames' array. Each element should have a 'description' field "
            "with a detailed description of that specific frame's scene. "
            "Format: {\"frames\": [{\"description\": \"...\"}, {\"description\": \"...\"}]}. "
            "Return JSON only, no additional text."
        )

    def _build_metadata(self, scene_descriptions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Build metadata with scene descriptions and timestamps."""
        # Create a simple combined description for backward compatibility
        combined_description = " ".join([sd["description"] for sd in scene_descriptions])
        
        return {
            "analyzed": True,
            "analysis_version": "2.0",
            "analysis_date": datetime.now().isoformat(),
            "provider": "gemma-3-27b-it",
            "scene_descriptions": scene_descriptions,
            "tags": {
                "objects": [],
                "scenes": [],
                "activities": [],
                "mood": [],
                "quality": {}
            },
            "faces": [],
            "colors": {},
            "audio_analysis": {},
            "description": combined_description,
            "confidence": 0.0
        }
