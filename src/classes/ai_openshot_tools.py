"""
OpenShot tools for the LangChain agent. All tools assume they are run on the Qt main thread
(dispatched by the agent runner). They call get_app().project, get_app().updates, get_app().window.
"""

import base64
import copy
import json
import os
import subprocess
import tempfile
import uuid as uuid_module
from classes.logger import log
from classes.ai_metadata_utils import adjust_scene_descriptions_for_subclip
from classes.scene_description_search import search_scene_descriptions
from classes.twelvelabs_indexer import (
    build_project_index_name,
    index_video_blocking,
    is_configured as twelvelabs_is_configured,
)

try:
    from PyQt5.QtCore import QObject, QThread, pyqtSignal, pyqtSlot, QEventLoop
except ImportError:
    QObject = object
    QThread = None
    pyqtSignal = None
    pyqtSlot = lambda x: x
    QEventLoop = None


def _pause_player():
    """Pause the video preview player to prevent background threads from
    calling Timeline::GetFrame while we mutate the native timeline.
    Returns True if the player was playing (so the caller can resume later)."""
    import time as _time
    try:
        app = _get_app()
        player = app.window.preview_thread.player
        import openshot
        was_playing = player.Mode() == openshot.PLAYBACK_PLAY
        player.Pause()  # sets mode + Speed(0); C++ thread-safe
        # Give the player/cache threads a moment to finish any in-progress
        # GetFrame call before we start mutating the timeline.
        _time.sleep(0.05)
        return was_playing
    except Exception:
        return False


def _resume_player(was_playing):
    """Resume the video player if it was playing before we paused it."""
    try:
        if was_playing:
            app = _get_app()
            app.window.preview_thread.player.Play()
    except Exception:
        pass


def _load_dotenv_if_available() -> None:
    """Best-effort .env loading for API keys."""
    try:
        from dotenv import load_dotenv  # type: ignore
    except Exception:
        return

    try:
        # Prefer repo-root .env, fallback to cwd
        root_env = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env")
        cwd_env = os.path.join(os.getcwd(), ".env")
        if os.path.exists(root_env):
            load_dotenv(dotenv_path=root_env, override=False)
        elif os.path.exists(cwd_env):
            load_dotenv(dotenv_path=cwd_env, override=False)
    except Exception:
        return


def _get_app():
    """Get app; must be called from main thread."""
    from classes.app import get_app
    return get_app()


def _get_selected_timeline_clip_and_window():
    """Return (clip_obj, window) for current selection, or (None, window)."""
    try:
        from classes.query import Clip
        app = _get_app()
        win = app.window
        selected_clip_ids = getattr(win, "selected_clips", []) or []
        if not selected_clip_ids:
            # Selection can be cleared when focus moves to the chat UI; use cached selection.
            selected_clip_ids = getattr(win, "ai_last_selected_clips", []) or []
        if selected_clip_ids:
            clip_obj = Clip.get(id=str(selected_clip_ids[0]))
            return clip_obj, win
        return None, win
    except Exception:
        return None, getattr(_get_app(), "window", None)


def _get_source_file_for_clip(clip_obj):
    try:
        from classes.query import File
        data = clip_obj.data if hasattr(clip_obj, "data") and isinstance(clip_obj.data, dict) else {}
        file_id = data.get("file_id")
        if file_id:
            f = File.get(id=str(file_id))
            if f:
                return f
        reader = data.get("reader") if isinstance(data.get("reader"), dict) else {}
        path = reader.get("path")
        if path:
            return File.get(path=path)
    except Exception:
        return None
    return None


def _fmt_mmss(seconds: float) -> str:
    try:
        seconds = float(seconds)
    except Exception:
        seconds = 0.0
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m}:{s:02d}"


def _twelvelabs_search_in_window(index_id: str, query_text: str, *, page_limit: int = 30, video_id: str = ""):
    """Run TwelveLabs search.query and return list[SearchItem]."""
    try:
        from twelvelabs.client import TwelveLabs  # type: ignore
    except Exception:
        return [], "TwelveLabs SDK not installed"

    # Client creation is done inside index_video_blocking; repeat minimal logic here.
    import os
    api_key = os.getenv("TWELVELABS_API_KEY")
    if not api_key:
        return [], "TWELVELABS_API_KEY not configured"

    try:
        client = TwelveLabs(api_key=api_key)
        # Use all modalities in search when possible.
        pager = client.search.query(
            index_id=index_id,
            search_options=["visual", "audio", "transcription"],
            query_text=query_text,
            group_by="clip",
            page_limit=page_limit,
        )
        items = list(pager)
        if video_id:
            items = [it for it in items if str(getattr(it, "video_id", "")) == str(video_id)]
        return items, None
    except Exception as e:
        return [], str(e)


def search_selected_clip_scenes(query: str, top_k: int = 5, use_openai_rerank: bool = True) -> str:
    """Search within the currently selected timeline clip's time window.

    Prefers TwelveLabs when indexed; falls back to local scene_descriptions search.
    """
    try:
        from classes.query import Clip

        clip_obj, win = _get_selected_timeline_clip_and_window()
        if not clip_obj:
            return "Error: No timeline clip selected. Select a clip and try again."

        clip_data = clip_obj.data if isinstance(clip_obj.data, dict) else {}
        clip_start = float(clip_data.get("start", 0.0) or 0.0)
        clip_end = float(clip_data.get("end", 0.0) or 0.0)
        clip_name = clip_data.get("title") or clip_data.get("label") or "Selected Clip"

        # Prefer per-clip ai_metadata if present (already adjusted to clip window)
        per_clip_ai = clip_data.get("ai_metadata") if isinstance(clip_data.get("ai_metadata"), dict) else None

        source_file = _get_source_file_for_clip(clip_obj)
        source_ai = None
        if source_file and isinstance(source_file.data, dict):
            source_ai = source_file.data.get("ai_metadata") if isinstance(source_file.data.get("ai_metadata"), dict) else None

        # Attempt TwelveLabs search against source file index
        if source_ai and twelvelabs_is_configured():
            tw = source_ai.get("twelvelabs") if isinstance(source_ai.get("twelvelabs"), dict) else {}
            status = (tw.get("status") or "").lower() if isinstance(tw, dict) else ""
            index_id = tw.get("index_id") if isinstance(tw, dict) else None
            video_id = tw.get("video_id") if isinstance(tw, dict) else ""

            if status != "ready" or not index_id:
                # Queue indexing lazily if needed (automatic indexing should usually already do this)
                if source_file and source_file.absolute_path() and twelvelabs_is_configured():
                    try:
                        app = _get_app()
                        proj_settings = app.project.get("settings") if getattr(app, "project", None) else {}
                        proj_settings = proj_settings if isinstance(proj_settings, dict) else {}
                        proj_tw = proj_settings.get("ai_twelvelabs") if isinstance(proj_settings.get("ai_twelvelabs"), dict) else {}
                        proj_index_id = proj_tw.get("index_id") if isinstance(proj_tw, dict) else None
                        proj_id = str(app.project.get("id") or "")
                        proj_index_name = build_project_index_name(proj_id or "project")

                        ai_meta = source_file.data.get("ai_metadata") if isinstance(source_file.data, dict) else {}
                        if not isinstance(ai_meta, dict):
                            ai_meta = {}
                        ai_meta["twelvelabs"] = {
                            "status": "queued",
                            "index_name": proj_index_name,
                            "filename": os.path.basename(source_file.absolute_path()),
                        }
                        source_file.data["ai_metadata"] = ai_meta
                        source_file.save()
                        app.task_queue.submit(
                            "twelvelabs",
                            f"twelvelabs_index:{source_file.id}",
                            index_video_blocking,
                            file_path=source_file.absolute_path(),
                            index_name=proj_index_name,
                            filename=os.path.basename(source_file.absolute_path()),
                            existing_index_id=proj_index_id,
                        )
                    except Exception:
                        pass
                # Continue to fallback
            else:
                items, err = _twelvelabs_search_in_window(str(index_id), query, page_limit=max(30, top_k * 10), video_id=str(video_id or ""))
                if not err and items:
                    # Filter to sub-clip window in source time
                    matches = []
                    for it in items:
                        s = float(getattr(it, "start", 0.0) or 0.0)
                        e = float(getattr(it, "end", 0.0) or 0.0)
                        if e < clip_start or s > clip_end:
                            continue
                        rs = max(s, clip_start) - clip_start
                        re = min(e, clip_end) - clip_start
                        matches.append({
                            "rel_start": rs,
                            "rel_end": re,
                            "src_start": s,
                            "src_end": e,
                            "score": float(getattr(it, "score", 0.0) or 0.0),
                            "thumbnail_url": getattr(it, "thumbnail_url", "") or "",
                            "transcription": getattr(it, "transcription", "") or "",
                        })

                    matches.sort(key=lambda x: x["score"], reverse=True)
                    matches = matches[: max(1, int(top_k))]

                    lines = [f"TwelveLabs matches in '{clip_name}' window ({_fmt_mmss(clip_start)} - {_fmt_mmss(clip_end)} source time):"]
                    for m in matches:
                        lines.append(
                            f"- [{_fmt_mmss(m['rel_start'])} - {_fmt_mmss(m['rel_end'])}] score={m['score']:.3f}"
                        )
                        if m.get("transcription"):
                            lines.append(f"  transcript: {str(m['transcription']).strip()[:180]}")
                        if m.get("thumbnail_url"):
                            lines.append(f"  thumb: {m['thumbnail_url']}")
                    return "\n".join(lines)

        # Local fallback (scene_descriptions)
        local_ai = per_clip_ai
        if local_ai is None and source_ai is not None:
            # Adjust source metadata into this clip window for searching
            local_ai = adjust_scene_descriptions_for_subclip(source_ai, clip_start, clip_end)

        results = search_scene_descriptions(local_ai or {}, query, top_k=top_k, use_openai_rerank=use_openai_rerank)
        if not results:
            return "No matches found in scene descriptions (and TwelveLabs not ready)."

        lines = [f"Scene-description matches in '{clip_name}':"]
        for r in results:
            lines.append(f"- [{_fmt_mmss(r['time'])}] score={r.get('score', 0.0):.3f} ({r.get('source','local')}): {r.get('description','')}")
        return "\n".join(lines)

    except Exception as e:
        log.error("search_selected_clip_scenes: %s", e, exc_info=True)
        return f"Error: {e}"


def slice_selected_clip_at_best_match(query: str) -> str:
    """Slice the selected timeline clip at the best TwelveLabs match inside the clip window.

    Requires TwelveLabs to be configured and the source video to be indexed.
    """
    try:
        clip_obj, win = _get_selected_timeline_clip_and_window()
        if not clip_obj:
            return "Error: No timeline clip selected."

        if not twelvelabs_is_configured():
            return "Error: TwelveLabs is not configured. Set TWELVELABS_API_KEY and re-try."

        clip_data = clip_obj.data if isinstance(clip_obj.data, dict) else {}
        clip_start = float(clip_data.get("start", 0.0) or 0.0)
        clip_end = float(clip_data.get("end", 0.0) or 0.0)
        clip_pos = float(clip_data.get("position", 0.0) or 0.0)

        source_file = _get_source_file_for_clip(clip_obj)
        source_ai = (
            source_file.data.get("ai_metadata")
            if source_file and isinstance(source_file.data, dict) and isinstance(source_file.data.get("ai_metadata"), dict)
            else None
        )
        if not source_file or not source_ai:
            return "Error: Could not find the source file metadata for the selected clip."

        tw = source_ai.get("twelvelabs") if isinstance(source_ai.get("twelvelabs"), dict) else {}
        status = (tw.get("status") or "").lower() if isinstance(tw, dict) else ""
        index_id = tw.get("index_id") if isinstance(tw, dict) else None

        if status != "ready" or not index_id:
            # Best-effort: queue indexing (import normally does this, but handle misses)
            try:
                if source_file.absolute_path():
                    app = _get_app()
                    proj_settings = app.project.get("settings") if getattr(app, "project", None) else {}
                    proj_settings = proj_settings if isinstance(proj_settings, dict) else {}
                    proj_tw = proj_settings.get("ai_twelvelabs") if isinstance(proj_settings.get("ai_twelvelabs"), dict) else {}
                    proj_index_id = proj_tw.get("index_id") if isinstance(proj_tw, dict) else None
                    proj_id = str(app.project.get("id") or "")
                    proj_index_name = build_project_index_name(proj_id or "project")

                    ai_meta = source_file.data.get("ai_metadata") if isinstance(source_file.data, dict) else {}
                    if not isinstance(ai_meta, dict):
                        ai_meta = {}
                    ai_meta["twelvelabs"] = {
                        "status": "queued",
                        "index_name": proj_index_name,
                        "filename": os.path.basename(source_file.absolute_path()),
                    }
                    source_file.data["ai_metadata"] = ai_meta
                    source_file.save()
                    app.task_queue.submit(
                        "twelvelabs",
                        f"twelvelabs_index:{source_file.id}",
                        index_video_blocking,
                        file_path=source_file.absolute_path(),
                        index_name=proj_index_name,
                        filename=os.path.basename(source_file.absolute_path()),
                        existing_index_id=proj_index_id,
                    )
            except Exception:
                pass
            return "TwelveLabs indexing is not ready yet for this source video. Indexing has been queued; try again in a moment."

        items, err = _twelvelabs_search_in_window(str(index_id), query, page_limit=30, video_id=str(tw.get("video_id") or ""))
        if err:
            return f"Error: TwelveLabs search failed: {err}"
        if not items:
            return "No TwelveLabs matches found inside the selected clip window."

        best_mid = None
        best_score = -1.0
        for it in items:
            s = float(getattr(it, "start", 0.0) or 0.0)
            e = float(getattr(it, "end", 0.0) or 0.0)
            if e < clip_start or s > clip_end:
                continue
            mid = (max(s, clip_start) + min(e, clip_end)) / 2.0
            score = float(getattr(it, "score", 0.0) or 0.0)
            if score > best_score:
                best_score = score
                best_mid = mid

        if best_mid is None:
            return "No TwelveLabs matches overlapped the selected clip window."

        slice_pos = clip_pos + (best_mid - clip_start)
        from windows.views.timeline import MenuSlice  # lazy import
        _get_app().window.timeline.Slice_Triggered(MenuSlice.KEEP_BOTH, [str(clip_obj.id)], [], slice_pos)
        return f"Sliced selected clip at {_fmt_mmss(best_mid - clip_start)} (best TwelveLabs match)."
    except Exception as e:
        log.error("slice_selected_clip_at_best_match: %s", e, exc_info=True)
        return f"Error: {e}"


def _is_extreme_for_4_seconds(prompt: str) -> tuple[bool, str]:
    """Return (is_too_extreme, reason). Heuristic guardrail for 4s inserts."""
    text = (prompt or "").strip().lower()
    if len(text) < 2:
        return True, "Prompt is too short."

    # Too many sequential actions / multi-scene narratives.
    multi_markers = [
        "then ",
        "after that",
        "afterwards",
        "meanwhile",
        "next ",
        "cut to",
        "scene change",
        "montage",
        "several",
        "multiple",
        "a series of",
        "over the course of",
        "gradually",
        "time-lapse",
        "timelapse",
    ]
    if sum(1 for m in multi_markers if m in text) >= 2:
        return True, "Request describes multiple steps/scenes; keep it to one simple action for a 4s insert."

    # Big unrealistic transformations for a short insert.
    extreme_markers = [
        "explode",
        "nuke",
        "earthquake",
        "tsunami",
        "apocalypse",
        "destroy the city",
        "teleport",
        "time travel",
        "turn into",
        "transform into",
        "grow wings",
        "summon",
        "giant",
        "entire crowd",
        "army",
        "hundreds of",
        "thousands of",
    ]
    if any(m in text for m in extreme_markers):
        return True, "Request is too large/extreme to fit plausibly into a 4s insert."

    # Very long prompts tend to imply too many constraints.
    if len(text) > 240:
        return True, "Prompt is too detailed for a 4s insert; simplify to the single key change."

    return False, ""


def _ffmpeg_run(args: list[str]) -> tuple[bool, str]:
    try:
        p = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
        if p.returncode != 0:
            return False, (p.stderr or p.stdout or "ffmpeg failed")
        return True, ""
    except FileNotFoundError:
        return False, "ffmpeg not found. Install ffmpeg to enable AI video-to-video inserts."
    except Exception as e:
        return False, str(e)


def _file_to_data_uri(path: str, media_type: str) -> tuple[str | None, str | None]:
    try:
        with open(path, "rb") as f:
            raw = f.read()
        if len(raw) > 50 * 1024 * 1024:
            return None, "Seed media is too large to send as base64. Try a smaller resolution or shorter segment."
        b64 = base64.b64encode(raw).decode("ascii")
        return f"data:{media_type};base64,{b64}", None
    except OSError as e:
        return None, f"Failed to read media: {e}"


def _ffprobe_has_audio(path: str) -> bool:
    """Return True if the media file has at least one audio stream (best-effort)."""
    try:
        p = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "a",
                "-show_entries",
                "stream=index",
                "-of",
                "csv=p=0",
                path,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        out = (p.stdout or "").strip()
        return bool(out)
    except Exception:
        return False


def _create_dissolve_transition(layer: int, position: float, duration: float, *, transaction_id: str | None = None) -> tuple[bool, str]:
    """Create a Mask dissolve transition using fade.svg at the given overlap position."""
    try:
        import openshot
        from classes import info

        app = _get_app()
        fps = app.project.get("fps")
        fps_float = float(fps["num"]) / float(fps["den"]) if fps else 24.0

        transition_reader = openshot.QtImageReader(
            os.path.join(info.PATH, "transitions", "common", "fade.svg")
        )
        transition_object = openshot.Mask()
        brightness = transition_object.brightness
        brightness.AddPoint(1, 1.0, openshot.BEZIER)
        brightness.AddPoint(round(float(duration) * fps_float) + 1, -1.0, openshot.BEZIER)
        contrast = openshot.Keyframe(3.0)

        transitions_data = {
            "id": app.project.generate_id(),
            "layer": int(layer),
            "title": "Transition",
            "type": "Mask",
            "position": float(position),
            "start": 0,
            "end": float(duration),
            "brightness": json.loads(brightness.Json()),
            "contrast": json.loads(contrast.Json()),
            "reader": json.loads(transition_reader.Json()),
            "replace_image": False,
        }
        app.window.timeline.update_transition_data(transitions_data, only_basic_props=False, ignore_refresh=False, transaction_id=transaction_id)
        return True, ""
    except Exception as e:
        return False, str(e)


class _ViduV2VInsertThread(QThread if QThread else object):
    """Worker thread to build seed video, generate the 4s insert via Runware, then bake an updated clip."""
    if pyqtSignal is not None:
        finished_with_result = pyqtSignal(str, str)  # path_or_empty, error_or_empty

    def __init__(
        self,
        api_key: str,
        source_video_path: str,
        center_time_seconds: float,
        clip_window_start: float,
        clip_window_end: float,
        user_prompt: str,
        output_path: str,
        *,
        model: str,
        width: int,
        height: int,
        duration_seconds: float,
        strength: float,
        fade_seconds: float,
    ):
        if QThread is not None:
            super().__init__()
        self._api_key = api_key
        self._source_video_path = source_video_path
        self._center_time = float(center_time_seconds)
        self._clip_window_start = float(clip_window_start)
        self._clip_window_end = float(clip_window_end)
        self._user_prompt = user_prompt
        self._output_path = output_path
        self._model = model
        self._width = int(width)
        self._height = int(height)
        self._duration = float(duration_seconds)
        self._strength = float(strength)
        self._fade_s = float(fade_seconds)

    def _emit(self, path: str, err: str):
        if pyqtSignal is not None and hasattr(self, "finished_with_result"):
            self.finished_with_result.emit(path or "", err or "")

    def run(self):
        # Guardrail: keep prompt feasible for 4s
        too_extreme, reason = _is_extreme_for_4_seconds(self._user_prompt)
        if too_extreme:
            self._emit("", f"Please simplify the request: {reason}")
            return

        from classes.video_generation.runware_client import (
            runware_generate_video,
            download_video_to_path,
        )

        try:
            tmpdir = tempfile.mkdtemp(prefix="zenvi_vidu_seed_")
        except Exception as e:
            self._emit("", f"Failed to create temp dir: {e}")
            return

        try:
            seg1 = os.path.join(tmpdir, "seg1.mp4")
            seg2 = os.path.join(tmpdir, "seg2.mp4")
            concat_list = os.path.join(tmpdir, "list.txt")
            seed_mp4 = os.path.join(tmpdir, "seed.mp4")
            first_jpg = os.path.join(tmpdir, "first.jpg")
            last_jpg = os.path.join(tmpdir, "last.jpg")
            insert_mp4 = os.path.join(tmpdir, "insert.mp4")

            start1 = max(0.0, self._center_time - 2.0)
            start2 = max(0.0, self._center_time)
            # Extract two 2s segments at 720p to keep size manageable.
            vf = (
                f"scale={self._width}:{self._height}:force_original_aspect_ratio=decrease,"
                f"pad={self._width}:{self._height}:(ow-iw)/2:(oh-ih)/2,setsar=1"
            )
            cmd1 = [
                "ffmpeg", "-y",
                "-ss", str(start1), "-i", self._source_video_path,
                "-t", "2.0",
                "-vf", vf,
                "-r", "24",
                "-an",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                seg1,
            ]
            ok, err = _ffmpeg_run(cmd1)
            if not ok:
                self._emit("", f"Failed to build seed segment 1: {err}")
                return

            cmd2 = [
                "ffmpeg", "-y",
                "-ss", str(start2), "-i", self._source_video_path,
                "-t", "2.0",
                "-vf", vf,
                "-r", "24",
                "-an",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                seg2,
            ]
            ok, err = _ffmpeg_run(cmd2)
            if not ok:
                self._emit("", f"Failed to build seed segment 2: {err}")
                return

            with open(concat_list, "w", encoding="utf-8") as f:
                f.write(f"file '{seg1}'\n")
                f.write(f"file '{seg2}'\n")
            ok, err = _ffmpeg_run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_list, "-c", "copy", seed_mp4])
            if not ok:
                # Fallback: re-encode concat if container copy fails
                ok2, err2 = _ffmpeg_run([
                    "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_list,
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                    "-an", seed_mp4,
                ])
                if not ok2:
                    self._emit("", f"Failed to concat seed segments: {err}; {err2}")
                    return

            ok, err = _ffmpeg_run(["ffmpeg", "-y", "-i", seed_mp4, "-frames:v", "1", first_jpg])
            if not ok:
                self._emit("", f"Failed to extract first frame: {err}")
                return
            ok, err = _ffmpeg_run(["ffmpeg", "-y", "-sseof", "-0.05", "-i", seed_mp4, "-frames:v", "1", last_jpg])
            if not ok:
                self._emit("", f"Failed to extract last frame: {err}")
                return

            seed_uri, err = _file_to_data_uri(seed_mp4, "video/mp4")
            if err:
                self._emit("", err)
                return
            first_uri, err = _file_to_data_uri(first_jpg, "image/jpeg")
            if err:
                self._emit("", err)
                return
            last_uri, err = _file_to_data_uri(last_jpg, "image/jpeg")
            if err:
                self._emit("", err)
                return

            # Encourage seamless endpoints.
            prompt = (
                f"{self._user_prompt.strip()}\n\n"
                "Constraints: the first frame must closely match the provided first frame, "
                "and the last frame must closely match the provided last frame. Keep it realistic for 4 seconds."
            )
            frame_images = [
                {"inputImage": first_uri, "frame": "first"},
                {"inputImage": last_uri, "frame": "last"},
            ]

            video_url, gen_err = runware_generate_video(
                self._api_key,
                prompt,
                duration_seconds=self._duration,
                model=self._model,
                width=self._width,
                height=self._height,
                fps=24,
                seed_video=seed_uri,
                strength=self._strength,
                frame_images=frame_images,
                provider_settings=None,
            )
            if gen_err:
                self._emit("", gen_err)
                return
            ok, dl_err = download_video_to_path(video_url, insert_mp4)
            if not ok:
                self._emit("", dl_err or "Download failed")
                return

            # Bake an updated clip: [clip_start..center] + insert + [center..clip_end], with internal crossfades.
            clip_start = float(self._clip_window_start)
            clip_end = float(self._clip_window_end)
            center = float(self._center_time)
            dur_a = max(0.0, center - clip_start)
            dur_c = max(0.0, clip_end - center)
            insert_dur = float(self._duration)

            # Clamp fade so xfade offsets are valid.
            fade = float(self._fade_s)
            fade = min(fade, 0.49)
            fade = min(fade, max(0.01, dur_a / 2.0) if dur_a > 0 else 0.01)
            fade = min(fade, max(0.01, dur_c / 2.0) if dur_c > 0 else 0.01)
            fade = min(fade, max(0.01, insert_dur / 2.0) if insert_dur > 0 else 0.01)
            fade = max(0.01, fade)

            vf = (
                f"scale={self._width}:{self._height}:force_original_aspect_ratio=decrease,"
                f"pad={self._width}:{self._height}:(ow-iw)/2:(oh-ih)/2,setsar=1,format=yuv420p,fps=24"
            )

            has_audio = _ffprobe_has_audio(self._source_video_path)
            # xfade offsets
            off1 = max(0.0, dur_a - fade)
            off2 = max(0.0, dur_a + insert_dur - (2.0 * fade))

            if has_audio:
                # Build audio with fades and silence during the inserted section.
                # Note: We intentionally don't attempt to synthesize audio for the generated insert.
                filter_complex = (
                    f"[0:v]trim=start={clip_start}:end={center},setpts=PTS-STARTPTS,{vf}[va];"
                    f"[1:v]setpts=PTS-STARTPTS,{vf}[vb];"
                    f"[0:v]trim=start={center}:end={clip_end},setpts=PTS-STARTPTS,{vf}[vc];"
                    f"[va][vb]xfade=transition=fade:duration={fade}:offset={off1}[vab];"
                    f"[vab][vc]xfade=transition=fade:duration={fade}:offset={off2}[vout];"
                    f"[0:a]atrim=start={clip_start}:end={center},asetpts=PTS-STARTPTS,afade=t=out:st={max(0.0, dur_a - fade)}:d={fade}[aa];"
                    f"anullsrc=channel_layout=stereo:sample_rate=48000,atrim=start=0:end={insert_dur}[ab];"
                    f"[0:a]atrim=start={center}:end={clip_end},asetpts=PTS-STARTPTS,afade=t=in:st=0:d={fade}[ac];"
                    f"[aa][ab][ac]concat=n=3:v=0:a=1[aout]"
                )
                cmd = [
                    "ffmpeg",
                    "-y",
                    "-i",
                    self._source_video_path,
                    "-i",
                    insert_mp4,
                    "-filter_complex",
                    filter_complex,
                    "-map",
                    "[vout]",
                    "-map",
                    "[aout]",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "veryfast",
                    "-crf",
                    "20",
                    "-c:a",
                    "aac",
                    "-b:a",
                    "192k",
                    self._output_path,
                ]
            else:
                filter_complex = (
                    f"[0:v]trim=start={clip_start}:end={center},setpts=PTS-STARTPTS,{vf}[va];"
                    f"[1:v]setpts=PTS-STARTPTS,{vf}[vb];"
                    f"[0:v]trim=start={center}:end={clip_end},setpts=PTS-STARTPTS,{vf}[vc];"
                    f"[va][vb]xfade=transition=fade:duration={fade}:offset={off1}[vab];"
                    f"[vab][vc]xfade=transition=fade:duration={fade}:offset={off2}[vout]"
                )
                cmd = [
                    "ffmpeg",
                    "-y",
                    "-i",
                    self._source_video_path,
                    "-i",
                    insert_mp4,
                    "-filter_complex",
                    filter_complex,
                    "-map",
                    "[vout]",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "veryfast",
                    "-crf",
                    "20",
                    "-an",
                    self._output_path,
                ]

            ok, bake_err = _ffmpeg_run(cmd)
            if not ok:
                self._emit("", f"Failed to bake updated clip: {bake_err}")
                return

            self._emit(self._output_path, "")
        finally:
            try:
                # Best-effort cleanup
                import shutil
                shutil.rmtree(tmpdir, ignore_errors=True)
            except Exception:
                pass


def insert_vidu_v2v_clip_into_selected_clip(query: str, *, fade_ms: int = 400) -> str:
    """Find best match in selected clip (TwelveLabs), generate a 4s v2v insert, bake an updated longer clip, and add it to the imported clips section.

    The baked clip is tagged with Gemini and indexed with TwelveLabs before being
    imported into the project. The original clip on the timeline is left unchanged.
    """
    if QThread is None or QEventLoop is None:
        return "Error: This feature requires PyQt5."

    clip_obj, win = _get_selected_timeline_clip_and_window()
    if not clip_obj:
        return "Error: No timeline clip selected. Select a clip and try again."

    app = _get_app()
    settings = app.get_settings()
    _load_dotenv_if_available()
    api_key = (os.getenv("RUNWARE_API_KEY") or "").strip() or (settings.get("runware-api-key") or "").strip()
    if not api_key:
        return "Error: Runware API key is not configured. Set RUNWARE_API_KEY in your .env (or add it in Preferences)."

    query = (query or "").strip()
    too_extreme, reason = _is_extreme_for_4_seconds(query)
    if too_extreme:
        return f"Error: Please simplify your request: {reason}"

    clip_data = clip_obj.data if isinstance(clip_obj.data, dict) else {}
    clip_start = float(clip_data.get("start", 0.0) or 0.0)
    clip_end = float(clip_data.get("end", 0.0) or 0.0)

    source_file = _get_source_file_for_clip(clip_obj)
    source_ai = (
        source_file.data.get("ai_metadata")
        if source_file and isinstance(source_file.data, dict) and isinstance(source_file.data.get("ai_metadata"), dict)
        else None
    )
    if not source_file or not getattr(source_file, "absolute_path", None) or not source_file.absolute_path():
        return "Error: Could not find the source video for the selected clip."

    tw = source_ai.get("twelvelabs") if isinstance(source_ai.get("twelvelabs"), dict) else {}
    status = (tw.get("status") or "").lower() if isinstance(tw, dict) else ""
    index_id = tw.get("index_id") if isinstance(tw, dict) else None

    best_mid = None
    best_score = -1.0

    # Strategy 1: TwelveLabs search (highest quality, needs indexing to be ready).
    if status == "ready" and index_id:
        items, err = _twelvelabs_search_in_window(str(index_id), query, page_limit=30, video_id=str(tw.get("video_id") or ""))
        if err:
            log.warning("TwelveLabs search failed, will try scene descriptions: %s", err)
        elif items:
            for it in items:
                s = float(getattr(it, "start", 0.0) or 0.0)
                e = float(getattr(it, "end", 0.0) or 0.0)
                if e < clip_start or s > clip_end:
                    continue
                mid = (max(s, clip_start) + min(e, clip_end)) / 2.0
                score = float(getattr(it, "score", 0.0) or 0.0)
                if score > best_score:
                    best_score = score
                    best_mid = mid

    # Strategy 2: Gemini scene description search (available if the file was tagged).
    if best_mid is None and source_ai:
        try:
            scene_results = search_scene_descriptions(source_ai, query, top_k=5, use_openai_rerank=False)
            for sr in (scene_results or []):
                t = float(sr.get("time", 0.0) or 0.0)
                sc = float(sr.get("score", 0.0) or 0.0)
                if clip_start <= t <= clip_end and sc > best_score:
                    best_score = sc
                    best_mid = t
        except Exception as exc:
            log.debug("Scene description search fallback failed: %s", exc)

    # Strategy 3: fall back to the midpoint of the clip.
    if best_mid is None:
        best_mid = (clip_start + clip_end) / 2.0
        log.info("insert_vidu_v2v: no search results, using clip midpoint %.2fs", best_mid)

    fade_s = max(0.05, min(0.49, float(fade_ms) / 1000.0))

    # Generate the insert clip and bake the updated clip in a worker thread.
    output_path = _output_path_for_generated_video()
    model = (settings.get("video-insert-v2v-model") or "vidu:2@0").strip() or "vidu:2@0"
    strength_val = 0.6
    try:
        strength_val = float(settings.get("video-generation-v2v-strength") or 0.6)
    except Exception:
        strength_val = 0.6

    result_holder = [None, None]
    loop_holder = [None]

    class _DoneReceiver(QObject if QObject is not object else object):
        def on_done(self, path, error):
            result_holder[0] = path
            result_holder[1] = error
            if loop_holder[0]:
                loop_holder[0].quit()

    receiver = _DoneReceiver()
    thread = _ViduV2VInsertThread(
        api_key,
        source_file.absolute_path(),
        float(best_mid),
        float(clip_start),
        float(clip_end),
        query,
        output_path,
        model=model,
        width=1280,
        height=720,
        duration_seconds=4.0,
        strength=strength_val,
        fade_seconds=float(fade_s),
    )
    thread.finished_with_result.connect(receiver.on_done)
    loop_holder[0] = QEventLoop(app)
    status_bar = getattr(app.window, "statusBar", None)
    try:
        if status_bar is not None:
            status_bar.showMessage("Generating 4s insert clip (Vidu v2v)...", 0)
        thread.start()
        loop_holder[0].exec_()
    finally:
        if status_bar is not None:
            status_bar.clearMessage()
    thread.quit()
    thread.wait(10000)
    try:
        thread.finished_with_result.disconnect(receiver.on_done)
    except Exception:
        pass

    path, error = result_holder[0], result_holder[1]
    if error:
        return f"Error: {error}"
    if not path or not os.path.isfile(path):
        return "Error: Generated video file not found."

    # Import baked file into the project's imported clips section.
    # The old clip on the timeline is intentionally left intact.
    try:
        # skip_tagging=True avoids nested QEventLoops (DeferredDelete
        # flushing, processEvents) that cause re-entrancy and SIGSEGV
        # when called from a BlockingQueuedConnection AI tool callback.
        app.window.files_model.add_files([path], skip_tagging=True)
        from classes.query import File
        f = File.get(path=path)
        if not f:
            f = File.get(path=os.path.normpath(path))
        if not f:
            f = File.get(path=os.path.realpath(path))
        if not f:
            # Brute-force: match by absolute_path() which resolves symlinks/relative.
            for candidate in File.filter():
                try:
                    if getattr(candidate, "absolute_path", None) and candidate.absolute_path() == path:
                        f = candidate
                        break
                except Exception:
                    continue
        if not f:
            log.warning("insert_vidu_v2v: File.get failed for path=%s, but add_files succeeded; file is in the project.", path)
            return (
                f"The combined clip (with a 4s AI insert at {_fmt_mmss(best_mid - clip_start)}, "
                f"baked with {int(fade_s * 1000)}ms crossfades) has been added to the imported clips section. "
                "The original clip on the timeline was left unchanged."
            )

        return (
            f"The combined clip (with a 4s AI insert at {_fmt_mmss(best_mid - clip_start)}, "
            f"baked with {int(fade_s * 1000)}ms crossfades) has been added to the imported clips section. "
            "The original clip on the timeline was left unchanged."
        )
    except Exception as e:
        log.error("insert_vidu_v2v_clip_into_selected_clip: %s", e, exc_info=True)
        return f"Error: {e}"


# ---- Read-only: project state ----


def get_project_info() -> str:
    """Get current project info: profile, fps, duration, scale. No arguments."""
    try:
        app = _get_app()
        proj = app.project
        profile = proj.get("profile") or "unknown"
        fps = proj.get("fps") or {}
        fps_str = "{}/{}".format(fps.get("num", ""), fps.get("den", 1)) if fps else "unknown"
        duration = proj.get("duration") or 0
        scale = proj.get("scale") or 0
        return (
            "Project: profile={}, fps={}, duration={}, scale={}".format(
                profile, fps_str, duration, scale
            )
        )
    except Exception as e:
        log.error("get_project_info: %s", e, exc_info=True)
        return "Error: {}".format(e)


def list_files() -> str:
    """List all files in the project. No arguments."""
    try:
        from classes.query import File
        app = _get_app()
        files = File.filter()
        if not files:
            return "No files in project."
        lines = []
        for f in files:
            path = f.data.get("path") or f.data.get("name", "")
            fid = f.data.get("id", "")
            lines.append("  id={} path={}".format(fid, path))
        return "Files ({}):\n{}".format(len(files), "\n".join(lines))
    except Exception as e:
        log.error("list_files: %s", e, exc_info=True)
        return "Error: {}".format(e)


def list_clips(layer: str = "") -> str:
    """List clips in the project. Optional: layer (layer number) to filter by layer."""
    try:
        from classes.query import Clip
        app = _get_app()
        kwargs = {}
        if layer:
            try:
                kwargs["layer"] = int(layer)
            except ValueError:
                pass
        clips = Clip.filter(**kwargs)
        if not clips:
            return "No clips in project."
        lines = []
        for c in clips:
            lid = c.data.get("layer", "")
            pos = c.data.get("position", 0)
            start = c.data.get("start", 0)
            end = c.data.get("end", 0)
            cid = c.data.get("id", "")
            lines.append("  id={} layer={} position={} start={} end={}".format(cid, lid, pos, start, end))
        return "Clips ({}):\n{}".format(len(clips), "\n".join(lines))
    except Exception as e:
        log.error("list_clips: %s", e, exc_info=True)
        return "Error: {}".format(e)


def list_layers() -> str:
    """List all layers (tracks) in the project. No arguments."""
    try:
        app = _get_app()
        layers = app.project.get("layers") or []
        if not layers:
            return "No layers in project."
        lines = []
        for L in layers:
            num = L.get("number", "")
            name = L.get("name", "")
            lock = L.get("lock", False)
            lines.append("  number={} name={} lock={}".format(num, name, lock))
        return "Layers ({}):\n{}".format(len(layers), "\n".join(lines))
    except Exception as e:
        log.error("list_layers: %s", e, exc_info=True)
        return "Error: {}".format(e)


def list_markers() -> str:
    """List all markers in the project. No arguments."""
    try:
        from classes.query import Marker
        markers = Marker.filter()
        if not markers:
            return "No markers in project."
        lines = []
        for m in markers:
            mid = m.data.get("id", "")
            pos = m.data.get("position", 0)
            name = m.data.get("name", "")
            lines.append("  id={} position={} name={}".format(mid, pos, name))
        return "Markers ({}):\n{}".format(len(markers), "\n".join(lines))
    except Exception as e:
        log.error("list_markers: %s", e, exc_info=True)
        return "Error: {}".format(e)


# ---- Project lifecycle ----


def new_project() -> str:
    """Create a new empty project (load default). No arguments."""
    try:
        app = _get_app()
        app.project.new()
        app.updates.load(app.project._data, reset_history=True)
        return "New project created."
    except Exception as e:
        log.error("new_project: %s", e, exc_info=True)
        return "Error: {}".format(e)


def save_project(file_path: str) -> str:
    """Save the project to the given file path. Argument: file_path (string, e.g. /path/to/project.zvn)."""
    from classes import info
    if not file_path or not isinstance(file_path, str):
        return "Error: file_path is required (string)."
    file_path = file_path.strip()
    if not file_path.endswith(info.PROJECT_EXT):
        file_path = file_path + info.PROJECT_EXT
    try:
        app = _get_app()
        app.window.save_project(file_path)
        return "Project saved to {}.".format(file_path)
    except Exception as e:
        log.error("save_project: %s", e, exc_info=True)
        return "Error: {}".format(e)


def open_project(file_path: str) -> str:
    """Open a project from the given file path. Argument: file_path (string)."""
    if not file_path or not isinstance(file_path, str):
        return "Error: file_path is required (string)."
    file_path = file_path.strip()
    try:
        app = _get_app()
        app.window.OpenProjectSignal.emit(file_path)
        return "Open project requested: {}.".format(file_path)
    except Exception as e:
        log.error("open_project: %s", e, exc_info=True)
        return "Error: {}".format(e)


# ---- Playback ----


def play() -> str:
    """Start or toggle playback. No arguments."""
    try:
        app = _get_app()
        app.window.actionPlay_trigger()
        return "Playback toggled."
    except Exception as e:
        log.error("play: %s", e, exc_info=True)
        return "Error: {}".format(e)


def go_to_start() -> str:
    """Seek to the start of the timeline. No arguments."""
    try:
        app = _get_app()
        app.window.actionJumpStart_trigger()
        return "Seeked to start."
    except Exception as e:
        log.error("go_to_start: %s", e, exc_info=True)
        return "Error: {}".format(e)


def go_to_end() -> str:
    """Seek to the end of the timeline. No arguments."""
    try:
        app = _get_app()
        app.window.actionJumpEnd_trigger()
        return "Seeked to end."
    except Exception as e:
        log.error("go_to_end: %s", e, exc_info=True)
        return "Error: {}".format(e)


# ---- History ----


def undo() -> str:
    """Undo the last action. No arguments."""
    try:
        app = _get_app()
        app.updates.undo()
        return "Undo performed."
    except Exception as e:
        log.error("undo: %s", e, exc_info=True)
        return "Error: {}".format(e)


def redo() -> str:
    """Redo the last undone action. No arguments."""
    try:
        app = _get_app()
        app.updates.redo()
        return "Redo performed."
    except Exception as e:
        log.error("redo: %s", e, exc_info=True)
        return "Error: {}".format(e)


# ---- Timeline / view ----


def add_track() -> str:
    """Add a new track (layer) below the selected track. No arguments."""
    try:
        app = _get_app()
        app.window.actionAddTrackBelow_trigger()
        return "Track added."
    except Exception as e:
        log.error("add_track: %s", e, exc_info=True)
        return "Error: {}".format(e)


def add_marker() -> str:
    """Add a marker at the current playhead position. No arguments."""
    try:
        app = _get_app()
        app.window.actionAddMarker_trigger()
        return "Marker added."
    except Exception as e:
        log.error("add_marker: %s", e, exc_info=True)
        return "Error: {}".format(e)


def remove_clip() -> str:
    """Remove the currently selected clip(s) from the timeline. No arguments."""
    try:
        app = _get_app()
        app.window.actionRemoveClip_trigger()
        return "Selected clip(s) removed."
    except Exception as e:
        log.error("remove_clip: %s", e, exc_info=True)
        return "Error: {}".format(e)


def zoom_in() -> str:
    """Zoom in the timeline. No arguments."""
    try:
        app = _get_app()
        app.window.actionTimelineZoomIn_trigger()
        return "Timeline zoomed in."
    except Exception as e:
        log.error("zoom_in: %s", e, exc_info=True)
        return "Error: {}".format(e)


def zoom_out() -> str:
    """Zoom out the timeline. No arguments."""
    try:
        app = _get_app()
        app.window.actionTimelineZoomOut_trigger()
        return "Timeline zoomed out."
    except Exception as e:
        log.error("zoom_out: %s", e, exc_info=True)
        return "Error: {}".format(e)


def center_on_playhead() -> str:
    """Center the timeline view on the playhead. No arguments."""
    try:
        app = _get_app()
        app.window.actionCenterOnPlayhead_trigger()
        return "Centered on playhead."
    except Exception as e:
        log.error("center_on_playhead: %s", e, exc_info=True)
        return "Error: {}".format(e)


def export_video() -> str:
    """Open the export video dialog. Use when the user wants to see or use the full export dialog."""
    try:
        app = _get_app()
        app.window.actionExportVideo_trigger()
        return "Export video dialog opened."
    except Exception as e:
        log.error("export_video: %s", e, exc_info=True)
        return "Error: {}".format(e)


def get_export_settings() -> str:
    """Return a readable summary of current/default export settings (resolution, fps, codecs, format, path, start/end frame)."""
    try:
        from windows.export import get_default_export_settings
        app = _get_app()
        video_settings, audio_settings, export_type, default_path = get_default_export_settings()
        overrides = app.project.get("export_overrides") or {}
        lines = [
            "Export type: %s" % export_type,
            "Default path: %s" % default_path,
            "Video: %sx%s, %s/%s fps, codec %s, format %s, bitrate %s" % (
                video_settings.get("width"), video_settings.get("height"),
                video_settings.get("fps", {}).get("num"), video_settings.get("fps", {}).get("den"),
                video_settings.get("vcodec"), video_settings.get("vformat"),
                video_settings.get("video_bitrate")),
            "Audio: codec %s, %s Hz, %s channels, bitrate %s" % (
                audio_settings.get("acodec"), audio_settings.get("sample_rate"),
                audio_settings.get("channels"), audio_settings.get("audio_bitrate")),
            "Frame range: %s - %s" % (video_settings.get("start_frame"), video_settings.get("end_frame")),
        ]
        if overrides:
            lines.append("Overrides: %s" % overrides)
        return "\n".join(lines)
    except Exception as e:
        log.error("get_export_settings: %s", e, exc_info=True)
        return "Error: %s" % e


def set_export_setting(key: str, value: str) -> str:
    """Update a single export setting. Keys: width, height, fps_num, fps_den, video_codec, audio_codec, output_path, start_frame, end_frame, vformat. Value is a string (e.g. 1920, 30, libx264)."""
    try:
        app = _get_app()
        overrides = dict(app.project.get("export_overrides") or {})
        key_lower = key.lower().strip()
        if key_lower in ("width", "height", "fps_num", "fps_den", "start_frame", "end_frame", "sample_rate", "channels"):
            try:
                overrides[key_lower] = int(value.strip())
            except ValueError:
                return "Error: %s must be an integer." % key
        elif key_lower in ("video_codec", "vcodec"):
            overrides["video_codec"] = value.strip()
        elif key_lower in ("audio_codec", "acodec"):
            overrides["audio_codec"] = value.strip()
        elif key_lower in ("output_path", "path"):
            overrides["output_path"] = value.strip()
        elif key_lower in ("vformat", "format"):
            overrides["vformat"] = value.strip()
        else:
            overrides[key_lower] = value.strip()
        get_app().updates.ignore_history = True
        app.updates.update(["export_overrides"], overrides)
        get_app().updates.ignore_history = False
        return "Set %s = %s." % (key_lower, value)
    except Exception as e:
        log.error("set_export_setting: %s", e, exc_info=True)
        return "Error: %s" % e


def export_video_now(output_path: str = "") -> str:
    """Export the video with current/default settings without opening the dialog. Use when the user says 'export the video' or 'export with current settings'. Optional output_path; if empty, uses default path. Overwrites existing file if present."""
    try:
        from windows.export import export_video_headless, get_default_export_settings
        _, _, _, default_path = get_default_export_settings()
        path = (output_path or "").strip() or None
        err = export_video_headless(path, None, None, None)
        if err:
            return "Export failed: %s" % err
        used_path = path or default_path
        return "Exported to %s." % used_path
    except Exception as e:
        log.error("export_video_now: %s", e, exc_info=True)
        return "Error: %s" % e


def import_files() -> str:
    """Open the import files dialog. No arguments."""
    try:
        app = _get_app()
        app.window.actionImportFiles_trigger()
        return "Import files dialog opened."
    except Exception as e:
        log.error("import_files: %s", e, exc_info=True)
        return "Error: {}".format(e)


# ---- Clipping (split file): library-only, no dialog ----

# Context for the agent: last file id created by split_file_add_clip, so add_clip_to_timeline
# can be called with no arguments and never ask the user for a file ID.
_last_split_file_id = None


def slice_clip_at_playhead() -> str:
    """Slice (split) the clip(s) and transition(s) at the current playhead position on the timeline, keeping both sides. Use when the user wants to clip the existing clip at the playhead. No arguments. Fails if no clip is under the playhead."""
    try:
        from classes.query import Clip, Transition
        from windows.views.timeline_backend.enums import MenuSlice
        app = _get_app()
        win = app.window
        fps = app.project.get("fps") or {}
        fps_float = float(fps.get("num", 30)) / float(fps.get("den", 1) or 1)
        playhead_position = float(win.preview_thread.current_frame - 1) / fps_float
        intersecting_clips = Clip.filter(intersect=playhead_position)
        intersecting_trans = Transition.filter(intersect=playhead_position)
        if not intersecting_clips and not intersecting_trans:
            return "No clip or transition at the playhead. Move the playhead over a clip on the timeline first, then ask again."
        win.slice_clips(MenuSlice.KEEP_BOTH)
        n = len(intersecting_clips) + len(intersecting_trans)
        return "Sliced {} item(s) at the playhead; both sides kept.".format(n)
    except Exception as e:
        log.error("slice_clip_at_playhead: %s", e, exc_info=True)
        return "Error: {}".format(e)


def get_file_info(file_id: str) -> str:
    """Get metadata for a project file: fps, video_length, path. Use to validate frame ranges before split_file_add_clip. Argument: file_id (string id of the file)."""
    try:
        from classes.query import File
        if not file_id or not isinstance(file_id, str):
            return "Error: file_id is required (string)."
        f = File.get(id=file_id.strip())
        if not f:
            return "Error: File not found for id={}.".format(file_id)
        path = f.data.get("path") or f.data.get("name", "")
        fps_data = f.data.get("fps") or {}
        fps_num = int(fps_data.get("num", 30))
        fps_den = int(fps_data.get("den", 1))
        fps = float(fps_num) / float(fps_den) if fps_den else 0.0
        video_length = int(f.data.get("video_length", 0))
        return "file_id={} path={} fps={}/{} video_length={} (frames, 1-based).".format(
            file_id, path or "(none)", fps_num, fps_den, video_length
        )
    except Exception as e:
        log.error("get_file_info: %s", e, exc_info=True)
        return "Error: {}".format(e)


def split_file_add_clip(file_id: str, start_frame: int, end_frame: int, name: str = "") -> str:
    """Add a new clip (file segment) to the project from an existing file, by frame range. No dialog. Arguments: file_id (string), start_frame (int, 1-based), end_frame (int, 1-based), name (optional string)."""
    try:
        from classes.query import File
        from classes import time_parts
        if not file_id or not isinstance(file_id, str):
            return "Error: file_id is required (string)."
        file_id = file_id.strip()
        try:
            start_frame = int(start_frame)
            end_frame = int(end_frame)
        except (TypeError, ValueError):
            return "Error: start_frame and end_frame must be integers."
        file = File.get(id=file_id)
        if not file:
            return "Error: File not found for id={}.".format(file_id)
        fps_data = file.data.get("fps") or {}
        fps_num = int(fps_data.get("num", 30))
        fps_den = int(fps_data.get("den", 1))
        fps = float(fps_num) / float(fps_den) if fps_den else 0.0
        if fps <= 0:
            return "Error: File has invalid fps."
        video_length = int(file.data.get("video_length", 0))
        if video_length <= 0:
            return "Error: File has no video_length."
        if start_frame < 1 or end_frame < 1:
            return "Error: Frames are 1-based; start_frame and end_frame must be >= 1."
        if start_frame >= end_frame:
            return "Error: start_frame must be less than end_frame."
        if end_frame > video_length:
            return "Error: end_frame {} exceeds video_length {}.".format(end_frame, video_length)
        previous_start = float(file.data.get("start", 0.0))
        start_sec = previous_start + (start_frame - 1) / fps
        end_sec = previous_start + end_frame / fps
        new_file = File()
        new_file.data = copy.deepcopy(file.data)
        new_file.data.pop("name", None)
        new_file.id = None
        new_file.key = None
        new_file.type = "insert"
        new_file.data["start"] = start_sec
        new_file.data["end"] = end_sec
        
        # Handle ai_metadata translation for sub-clips
        if 'ai_metadata' in new_file.data and new_file.data['ai_metadata'].get('analyzed'):
            new_file.data['ai_metadata'] = adjust_scene_descriptions_for_subclip(
                new_file.data['ai_metadata'], start_sec, end_sec
            )
        
        if name and isinstance(name, str) and name.strip():
            new_file.data["name"] = name.strip()
        else:
            global_frame = round(previous_start * fps) + start_frame
            t = time_parts.secondsToTime((global_frame - 1) / fps, fps_num, fps_den)
            timestamp = "%s:%s:%s:%s" % (t["hour"], t["min"], t["sec"], t["frame"])
            base = os.path.splitext(os.path.basename(file.data.get("path") or file.data.get("name", "clip")))[0]
            new_file.data["name"] = "{} ({})".format(base, timestamp)
        new_file.save()
        global _last_split_file_id
        _last_split_file_id = new_file.id
        clip_name = new_file.data.get("name", "")
        return "Added clip from frame {} to {} (name: {}). Ask: \"Would you like this clip added to the timeline at the playhead?\" If they say yes, call add_clip_to_timeline_tool with no arguments.".format(
            start_frame, end_frame, clip_name
        )
    except Exception as e:
        log.error("split_file_add_clip: %s", e, exc_info=True)
        return "Error: {}".format(e)


def add_clip_to_timeline(file_id: str = "", position_seconds: str = "", track: str = "") -> str:
    """Add a project file as a clip on the timeline. When used right after split_file_add_clip and the user said yes, call with no arguments (uses the clip just created). Optional: file_id for a specific file; position_seconds (empty for playhead); track (empty for selected or first track)."""
    global _last_split_file_id
    try:
        from classes.query import File, Track
        if not file_id or (isinstance(file_id, str) and not file_id.strip()):
            file_id = _last_split_file_id
            if not file_id:
                return "Error: No clip was just created. Split a file first with split_file_add_clip_tool, then when the user says yes to adding to the timeline, call add_clip_to_timeline_tool with no arguments."
        else:
            file_id = file_id.strip() if isinstance(file_id, str) else str(file_id)
        f = File.get(id=file_id)
        if not f:
            return "Error: File not found for id={}.".format(file_id)
        app = _get_app()
        win = app.window
        fps = app.project.get("fps") or {}
        fps_float = float(fps.get("num", 30)) / float(fps.get("den", 1) or 1)
        if position_seconds is None or (isinstance(position_seconds, str) and not position_seconds.strip()):
            pos_sec = float(win.preview_thread.current_frame - 1) / fps_float
        else:
            try:
                pos_sec = float(position_seconds)
            except (TypeError, ValueError):
                return "Error: position_seconds must be a number or empty for playhead."
        if track is None or (isinstance(track, str) and not track.strip()):
            selected = getattr(win, "selected_tracks", []) or []
            if selected:
                t = Track.get(id=selected[0])
                track_num = int(t.data.get("number", 1)) if t else 1
            else:
                layers = app.project.get("layers") or []
                track_num = int(layers[0].get("number", 1)) if layers else 1
        else:
            try:
                track_num = int(track)
            except (TypeError, ValueError):
                return "Error: track must be a layer number or empty."
        from PyQt5.QtCore import QPointF
        pos = QPointF(pos_sec, 0.0)
        was_playing = _pause_player()
        try:
            win.timeline.addClip(file_id, pos, track_num)
        finally:
            _resume_player(was_playing)
        _last_split_file_id = None  # clear so next no-arg call does not reuse
        return "Added clip to timeline at position {}s on track {}.".format(pos_sec, track_num)
    except Exception as e:
        log.error("add_clip_to_timeline: %s", e, exc_info=True)
        return "Error: {}".format(e)


# ---- Video generation: heavy work in a real worker thread ----
# We use a QThread subclass so run() is guaranteed to execute in the worker thread
# (QThread.run() is always invoked in that thread). moveToThread + slot can be
# ambiguous; this pattern keeps the main thread responsive during generation.


class _VideoGenerationThread(QThread if QThread else object):
    """Subclass of QThread: run() is always executed in the worker thread."""
    if pyqtSignal is not None:
        finished_with_result = pyqtSignal(str, str)  # path_or_empty, error_or_empty

    def __init__(self, api_key, prompt, duration_seconds, model, width, height, output_path):
        if QThread is not None:
            super().__init__()
        self._api_key = api_key
        self._prompt = prompt
        self._duration_seconds = duration_seconds
        self._model = model
        self._width = width
        self._height = height
        self._output_path = output_path

    def run(self):
        # QThread.run() is always executed in the worker thread — no moveToThread needed.
        from classes.video_generation.runware_client import (
            runware_generate_video,
            download_video_to_path,
        )
        video_url, err = runware_generate_video(
            self._api_key,
            self._prompt,
            duration_seconds=self._duration_seconds,
            model=self._model,
            width=self._width,
            height=self._height,
        )
        if err:
            if pyqtSignal is not None and hasattr(self, "finished_with_result"):
                self.finished_with_result.emit("", err)
            return
        ok, download_err = download_video_to_path(video_url, self._output_path)
        if pyqtSignal is not None and hasattr(self, "finished_with_result"):
            if ok:
                self.finished_with_result.emit(self._output_path, "")
            else:
                self.finished_with_result.emit("", download_err or "Download failed.")


def _output_path_for_generated_video():
    """Return an absolute path for saving a generated video. Call from main thread."""
    app = _get_app()
    project_path = getattr(app.project, "current_filepath", None) or ""
    if project_path and os.path.isabs(project_path):
        base_dir = os.path.dirname(project_path)
        out_dir = os.path.join(base_dir, "Generated")
        try:
            os.makedirs(out_dir, exist_ok=True)
            return os.path.join(out_dir, "generated_{}.mp4".format(uuid_module.uuid4().hex[:12]))
        except OSError:
            pass

    # Unsaved projects: avoid /tmp. Some environments clean /tmp aggressively and
    # partially-written files can trigger native crashes when thumbnailed.
    try:
        from classes import info

        out_dir = os.path.join(info.USER_PATH, "Generated")
        os.makedirs(out_dir, exist_ok=True)
        return os.path.join(out_dir, "generated_{}.mp4".format(uuid_module.uuid4().hex[:12]))
    except Exception:
        pass

    import tempfile
    return os.path.join(tempfile.gettempdir(), "zenvi_generated_{}.mp4".format(uuid_module.uuid4().hex[:12]))


def generate_video_and_add_to_timeline(
    prompt,
    duration_seconds=None,
    position_seconds="",
    track="",
) -> str:
    """Generate a video from prompt via Runware (Vidu), then add it to the timeline. Runs API+download in worker thread."""
    if QThread is None or QEventLoop is None:
        return "Error: Video generation requires PyQt5."
    app = _get_app()
    settings = app.get_settings()
    api_key = (settings.get("runware-api-key") or "").strip()
    if not api_key:
        return "Video generation is not configured. Add your Runware API key in Preferences."
    prompt = (prompt or "").strip()
    if len(prompt) < 2:
        return "Error: Prompt must be at least 2 characters."
    duration = duration_seconds
    if duration is None:
        duration = int(settings.get("video-generation-duration") or 4)
    duration = max(1, min(10, int(duration)))
    # Keep legacy text-to-video defaults unchanged.
    model = (settings.get("video-generation-model") or "vidu:3@2").strip() or "vidu:3@2"
    width, height = 640, 352  # legacy Vidu text-video default
    output_path = _output_path_for_generated_video()

    result_holder = [None, None]  # [path, error]
    loop_holder = [None]

    # Receiver on main thread so the slot runs on main thread and can quit the loop safely.
    class _DoneReceiver(QObject if QObject is not object else object):
        if pyqtSignal is not None:
            pass  # no signal; we use a slot only

        def on_done(self, path, error):
            result_holder[0] = path
            result_holder[1] = error
            if loop_holder[0]:
                loop_holder[0].quit()

    receiver = _DoneReceiver()
    # _VideoGenerationThread.run() runs in the worker thread; signal is delivered to main thread.
    thread = _VideoGenerationThread(
        api_key, prompt, duration, model, width, height, output_path
    )
    thread.finished_with_result.connect(receiver.on_done)
    loop_holder[0] = QEventLoop(app)
    status_bar = getattr(app.window, "statusBar", None)
    try:
        if status_bar is not None:
            status_bar.showMessage("Generating video...", 0)
        thread.start()
        loop_holder[0].exec_()
    finally:
        if status_bar is not None:
            status_bar.clearMessage()
    thread.quit()
    thread.wait(10000)
    try:
        thread.finished_with_result.disconnect(receiver.on_done)
    except Exception:
        pass

    path, error = result_holder[0], result_holder[1]
    if error:
        return "Error: {}".format(error)
    if not path or not os.path.isfile(path):
        return "Error: Generated video file not found."

    try:
        # skip_tagging=True avoids nested QEventLoops (Gemini tagging, TwelveLabs)
        # that cause re-entrancy and SIGSEGV when called from a
        # BlockingQueuedConnection AI tool callback.
        log.info("generate_video_and_add_to_timeline: calling add_files for %s", path)
        app.window.files_model.add_files([path], skip_tagging=True)
        log.info("generate_video_and_add_to_timeline: add_files returned, looking up File")
        from classes.query import File
        f = File.get(path=path)
        if not f:
            f = File.get(path=os.path.normpath(path))
        if not f:
            f = File.get(path=os.path.realpath(path))
        if not f:
            for candidate in File.filter():
                try:
                    if getattr(candidate, "absolute_path", None) and candidate.absolute_path() == path:
                        f = candidate
                        break
                except Exception:
                    continue
        if not f:
            log.warning("generate_video_and_add_to_timeline: File.get failed for path=%s, but add_files succeeded", path)
            return "Video was generated and added to the project files."
        file_id = f.id
        log.info("generate_video_and_add_to_timeline: about to add_clip_to_timeline, file_id=%s", file_id)
        was_playing = _pause_player()
        try:
            msg = add_clip_to_timeline(file_id=file_id, position_seconds=position_seconds or None, track=track or None)
        finally:
            _resume_player(was_playing)
        log.info("generate_video_and_add_to_timeline: add_clip_to_timeline returned: %s", msg)
        return msg
    except Exception as e:
        log.error("generate_video_and_add_to_timeline: %s", e, exc_info=True)
        return "Error: {}".format(e)


def generate_transition_clip(clip_a_id: str, clip_b_id: str, prompt_hint: str = "") -> str:
    """Generate a short transition video between two clips (e.g. same room, camera move) and insert it between them. Uses Runware/Vidu."""
    from classes.query import Clip

    app = _get_app()
    clip_a = Clip.get(id=clip_a_id) if clip_a_id else None
    clip_b = Clip.get(id=clip_b_id) if clip_b_id else None
    if not clip_a or not clip_b:
        return "Error: Could not find both clips. Use list_clips_tool to get clip IDs."
    pos_a = float(clip_a.data.get("position", 0))
    start_a = float(clip_a.data.get("start", 0))
    end_a = float(clip_a.data.get("end", 0))
    duration_a = end_a - start_a
    end_position_a = pos_a + duration_a
    layer = clip_a.data.get("layer")
    track = str(layer) if layer is not None else ""
    hint = (prompt_hint or "").strip()
    prompt = hint if hint else (
        "Smooth transition, same scene, cinematic, 2 seconds, seamless blend between two shots"
    )
    return generate_video_and_add_to_timeline(
        prompt=prompt,
        duration_seconds=2,
        position_seconds=str(end_position_a),
        track=track,
    )


def get_openshot_tools_for_langchain():
    """
    Return a list of LangChain Tool objects for the OpenShot agent.
    Each tool runs on the main thread when invoked (caller must ensure that).
    """
    from langchain_core.tools import tool

    @tool
    def get_project_info_tool() -> str:
        """Get current project info: profile, fps, duration, scale."""
        return get_project_info()

    @tool
    def list_files_tool() -> str:
        """List all files in the project."""
        return list_files()

    @tool
    def list_clips_tool(layer: str = "") -> str:
        """List clips in the project. Optional: layer (number) to filter by layer."""
        return list_clips(layer=layer)

    @tool
    def list_layers_tool() -> str:
        """List all layers (tracks) in the project."""
        return list_layers()

    @tool
    def list_markers_tool() -> str:
        """List all markers in the project."""
        return list_markers()

    @tool
    def new_project_tool() -> str:
        """Create a new empty project."""
        return new_project()

    @tool
    def save_project_tool(file_path: str) -> str:
        """Save the project to the given file path. Example: /home/user/my.zvn"""
        return save_project(file_path)

    @tool
    def open_project_tool(file_path: str) -> str:
        """Open a project from the given file path."""
        return open_project(file_path)

    @tool
    def play_tool() -> str:
        """Start or toggle playback."""
        return play()

    @tool
    def go_to_start_tool() -> str:
        """Seek to the start of the timeline."""
        return go_to_start()

    @tool
    def go_to_end_tool() -> str:
        """Seek to the end of the timeline."""
        return go_to_end()

    @tool
    def undo_tool() -> str:
        """Undo the last action."""
        return undo()

    @tool
    def redo_tool() -> str:
        """Redo the last undone action."""
        return redo()

    @tool
    def add_track_tool() -> str:
        """Add a new track below the selected track."""
        return add_track()

    @tool
    def add_marker_tool() -> str:
        """Add a marker at the current playhead position."""
        return add_marker()

    @tool
    def remove_clip_tool() -> str:
        """Remove the currently selected clip(s) from the timeline."""
        return remove_clip()

    @tool
    def zoom_in_tool() -> str:
        """Zoom in the timeline."""
        return zoom_in()

    @tool
    def zoom_out_tool() -> str:
        """Zoom out the timeline."""
        return zoom_out()

    @tool
    def center_on_playhead_tool() -> str:
        """Center the timeline view on the playhead."""
        return center_on_playhead()

    @tool
    def export_video_tool() -> str:
        """Open the export video dialog to choose settings and export. Use when the user wants to see or use the full export dialog."""
        return export_video()

    @tool
    def get_export_settings_tool() -> str:
        """Get current/default export settings (resolution, fps, codecs, format, path, frame range). Use when the user asks what their export settings are."""
        return get_export_settings()

    @tool
    def set_export_setting_tool(key: str, value: str) -> str:
        """Set a single export setting. Keys: width, height, fps_num, fps_den, video_codec, audio_codec, output_path, start_frame, end_frame, vformat. Value is a string (e.g. 1920, 30, libx264)."""
        return set_export_setting(key, value)

    @tool
    def export_video_now_tool(output_path: str = "") -> str:
        """Export the video with current/default settings without opening the dialog. Use when the user says 'export the video' or 'export with current settings'. Optional output_path; if empty, uses default path. Overwrites existing file if present."""
        return export_video_now(output_path)

    @tool
    def import_files_tool() -> str:
        """Open the import files dialog."""
        return import_files()

    @tool
    def get_file_info_tool(file_id: str) -> str:
        """Get file metadata: fps, video_length, path. Use before split_file_add_clip to validate frame range. Argument: file_id (string)."""
        return get_file_info(file_id)

    @tool
    def split_file_add_clip_tool(file_id: str, start_frame: int, end_frame: int, name: str = "") -> str:
        """Create a new clip from a file by frame range and add it to the project (no dialog). Use when the user wants to split a file or create a clip from frames. Arguments: file_id (string), start_frame (int, 1-based), end_frame (int, 1-based), name (optional string)."""
        return split_file_add_clip(file_id, start_frame, end_frame, name)

    @tool
    def add_clip_to_timeline_tool(file_id: str = "", position_seconds: str = "", track: str = "") -> str:
        """Add the clip just created by split_file_add_clip to the timeline at the playhead. Call with no arguments when the user says yes to adding the clip to the timeline (the app remembers which clip was just created). Do not ask the user for a file ID. Optional: file_id only if adding a different specific file; position_seconds (empty for playhead); track (empty for selected or first track)."""
        return add_clip_to_timeline(file_id, position_seconds, track)

    @tool
    def generate_video_and_add_to_timeline_tool(
        prompt: str,
        duration_seconds: str = "",
        position_seconds: str = "",
        track: str = "",
    ) -> str:
        """Generate a brand-new standalone video from a text prompt using AI (Runware/Vidu) and add it to the timeline. ONLY use this tool when the user wants to create an entirely new video from scratch (no existing clip involved). Do NOT use this tool when the user says 'insert into', 'add to', or 'modify' a selected clip — use insert_vidu_v2v_clip_into_selected_clip_tool for that instead. Argument: prompt (required, describe the video). Optional: duration_seconds (default from settings, e.g. 4); position_seconds (empty for playhead); track (empty for selected or first track)."""
        duration = None
        if duration_seconds and str(duration_seconds).strip():
            try:
                duration = int(float(duration_seconds))
            except (TypeError, ValueError):
                pass
        return generate_video_and_add_to_timeline(
            prompt=prompt,
            duration_seconds=duration,
            position_seconds=position_seconds.strip() if position_seconds else "",
            track=track.strip() if track else "",
        )

    @tool
    def slice_clip_at_playhead_tool() -> str:
        """Slice (split) the clip(s) and transition(s) at the current playhead position on the timeline, keeping both sides. Use when the user wants to clip the existing clip at the playhead. No arguments. Fails if no clip is under the playhead."""
        return slice_clip_at_playhead()

    @tool
    def search_selected_clip_scenes_tool(query: str, top_k: str = "5", use_openai_rerank: str = "true") -> str:
        """Search within the currently selected timeline clip's time window. Uses TwelveLabs when indexed; otherwise falls back to local scene_descriptions (optionally OpenAI rerank).

        Args:
            query: natural language query
            top_k: number of results (default 5)
            use_openai_rerank: 'true'/'false' (default true)
        """
        try:
            k = int(float(top_k)) if str(top_k).strip() else 5
        except Exception:
            k = 5
        uo = str(use_openai_rerank).strip().lower() not in ("0", "false", "no", "off")
        return search_selected_clip_scenes(query=query, top_k=k, use_openai_rerank=uo)

    @tool
    def slice_selected_clip_at_best_match_tool(query: str) -> str:
        """Slice the selected timeline clip at the best match inside its time window (TwelveLabs preferred, else scene_descriptions)."""
        return slice_selected_clip_at_best_match(query=query)

    @tool
    def insert_vidu_v2v_clip_into_selected_clip_tool(query: str, fade_ms: str = "400") -> str:
        """Insert an AI-generated 4s clip into the currently selected timeline clip. This is the ONLY tool to use when the user says 'insert', 'add into', 'modify', or 'change' the selected clip. It finds the best insertion point, generates a video-to-video clip, bakes it into the original with crossfades, and imports the combined clip into the project files panel. The original clip on the timeline is left unchanged. Do NOT also call generate_video_and_add_to_timeline_tool — this tool handles everything and only produces ONE imported file.

        Args:
            query: what to add/change (single simple action)
            fade_ms: crossfade duration in milliseconds (<500). Default 400.
        """
        try:
            fm = int(float(fade_ms)) if str(fade_ms).strip() else 400
        except Exception:
            fm = 400
        return insert_vidu_v2v_clip_into_selected_clip(query=query, fade_ms=fm)

    @tool
    def generate_transition_clip_tool(clip_a_id: str, clip_b_id: str, prompt_hint: str = "") -> str:
        """Generate a short transition clip between two clips and insert it between them. Arguments: clip_a_id, clip_b_id, prompt_hint (optional)."""
        return generate_transition_clip(clip_a_id=clip_a_id, clip_b_id=clip_b_id, prompt_hint=prompt_hint)

    return [
        get_project_info_tool,
        list_files_tool,
        list_clips_tool,
        list_layers_tool,
        list_markers_tool,
        new_project_tool,
        save_project_tool,
        open_project_tool,
        play_tool,
        go_to_start_tool,
        go_to_end_tool,
        undo_tool,
        redo_tool,
        add_track_tool,
        add_marker_tool,
        remove_clip_tool,
        zoom_in_tool,
        zoom_out_tool,
        center_on_playhead_tool,
        export_video_tool,
        get_export_settings_tool,
        set_export_setting_tool,
        export_video_now_tool,
        import_files_tool,
        get_file_info_tool,
        split_file_add_clip_tool,
        add_clip_to_timeline_tool,
        generate_video_and_add_to_timeline_tool,
        slice_clip_at_playhead_tool,
        search_selected_clip_scenes_tool,
        slice_selected_clip_at_best_match_tool,
        insert_vidu_v2v_clip_into_selected_clip_tool,
        generate_transition_clip_tool,
    ]
