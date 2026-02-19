"""
Tool handlers — execute OpenShot tool calls received from the backend.

When the backend's LangChain agent calls a tool that needs the running Qt
application (project state, playback, timeline manipulation), the backend
delegates the call to the frontend via WebSocket.  This module maps tool
names to the actual functions that interact with the live Qt application.

Usage (from ai_chat_ui.py):
    from classes.tool_handlers import execute_tool
    result = execute_tool(tool_name, tool_args)
"""

import base64
import copy
import json
import os
import subprocess
import tempfile
import uuid as uuid_module

from classes.logger import log

try:
    from PyQt5.QtCore import QObject, QThread, pyqtSignal, pyqtSlot, QEventLoop, QPointF
except ImportError:
    QObject = object
    QThread = None
    pyqtSignal = None
    pyqtSlot = lambda x: x
    QEventLoop = None
    QPointF = None


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _get_app():
    from classes.app import get_app
    return get_app()


def _pause_player():
    import time as _time
    try:
        app = _get_app()
        player = app.window.preview_thread.player
        import openshot
        was_playing = player.Mode() == openshot.PLAYBACK_PLAY
        player.Pause()
        _time.sleep(0.05)
        return was_playing
    except Exception:
        return False


def _resume_player(was_playing):
    try:
        if was_playing:
            _get_app().window.preview_thread.player.Play()
    except Exception:
        pass


def _get_selected_timeline_clip_and_window():
    try:
        from classes.query import Clip
        app = _get_app()
        win = app.window
        selected_clip_ids = getattr(win, "selected_clips", []) or []
        if not selected_clip_ids:
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


def _ffmpeg_run(args):
    try:
        p = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
        if p.returncode != 0:
            return False, (p.stderr or p.stdout or "ffmpeg failed")
        return True, ""
    except FileNotFoundError:
        return False, "ffmpeg not found."
    except Exception as e:
        return False, str(e)


def _file_to_data_uri(path, media_type):
    try:
        with open(path, "rb") as f:
            raw = f.read()
        if len(raw) > 50 * 1024 * 1024:
            return None, "File too large for base64."
        b64 = base64.b64encode(raw).decode("ascii")
        return f"data:{media_type};base64,{b64}", None
    except OSError as e:
        return None, f"Failed to read: {e}"


def _ffprobe_has_audio(path):
    try:
        p = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "a",
             "-show_entries", "stream=index", "-of", "csv=p=0", path],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False,
        )
        return bool((p.stdout or "").strip())
    except Exception:
        return False


def _is_extreme_for_4_seconds(prompt):
    text = (prompt or "").strip().lower()
    if len(text) < 2:
        return True, "Prompt is too short."
    multi_markers = [
        "then ", "after that", "afterwards", "meanwhile", "next ",
        "cut to", "scene change", "montage", "several", "multiple",
        "a series of", "over the course of", "gradually",
        "time-lapse", "timelapse",
    ]
    if sum(1 for m in multi_markers if m in text) >= 2:
        return True, "Multiple steps/scenes."
    extreme_markers = [
        "explode", "nuke", "earthquake", "tsunami", "apocalypse",
        "destroy the city", "teleport", "time travel", "turn into",
        "transform into", "grow wings", "summon", "giant",
        "entire crowd", "army", "hundreds of", "thousands of",
    ]
    if any(m in text for m in extreme_markers):
        return True, "Too extreme for 4s."
    if len(text) > 240:
        return True, "Prompt too detailed for 4s."
    return False, ""


def _twelvelabs_search_in_window(index_id, query_text, *, page_limit=30, video_id=""):
    try:
        from classes.api_client import get_backend_client
        client = get_backend_client()
        resp = client.search(query=query_text, index_id=index_id, video_id=video_id, page_limit=page_limit)
        if isinstance(resp, dict) and resp.get("error"):
            return [], resp["error"]
        results = resp.get("results", []) if isinstance(resp, dict) else []
        items = [type("SearchItem", (), r)() for r in results]
        if video_id:
            items = [it for it in items if str(getattr(it, "video_id", "")) == str(video_id)]
        return items, None
    except Exception as e:
        return [], str(e)


def _output_path_for_generated_video():
    app = _get_app()
    project_path = getattr(app.project, "current_filepath", None) or ""
    if project_path and os.path.isabs(project_path):
        out_dir = os.path.join(os.path.dirname(project_path), "Generated")
        try:
            os.makedirs(out_dir, exist_ok=True)
            return os.path.join(out_dir, f"generated_{uuid_module.uuid4().hex[:12]}.mp4")
        except OSError:
            pass
    try:
        from classes import info
        out_dir = os.path.join(info.USER_PATH, "Generated")
        os.makedirs(out_dir, exist_ok=True)
        return os.path.join(out_dir, f"generated_{uuid_module.uuid4().hex[:12]}.mp4")
    except Exception:
        pass
    return os.path.join(tempfile.gettempdir(), f"zenvi_generated_{uuid_module.uuid4().hex[:12]}.mp4")


# Context for add_clip_to_timeline (remembers last split file id)
_last_split_file_id = None


# ---------------------------------------------------------------------------
# Project tools
# ---------------------------------------------------------------------------

def get_project_info(**_kw) -> str:
    try:
        app = _get_app()
        proj = app.project
        profile = proj.get("profile") or "unknown"
        fps = proj.get("fps") or {}
        fps_str = "{}/{}".format(fps.get("num", ""), fps.get("den", 1))
        duration = proj.get("duration") or 0
        scale = proj.get("scale") or 0
        return f"Project: profile={profile}, fps={fps_str}, duration={duration}, scale={scale}"
    except Exception as e:
        return f"Error: {e}"


def list_files(**_kw) -> str:
    try:
        from classes.query import File
        files = File.filter()
        if not files:
            return "No files in project."
        lines = [f"  id={f.data.get('id','')} path={f.data.get('path','')}" for f in files]
        return f"Files ({len(files)}):\n" + "\n".join(lines)
    except Exception as e:
        return f"Error: {e}"


def list_clips(layer="", **_kw) -> str:
    try:
        from classes.query import Clip
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
            d = c.data
            lines.append(f"  id={d.get('id','')} layer={d.get('layer','')} position={d.get('position',0)} start={d.get('start',0)} end={d.get('end',0)}")
        return f"Clips ({len(clips)}):\n" + "\n".join(lines)
    except Exception as e:
        return f"Error: {e}"


def list_layers(**_kw) -> str:
    try:
        layers = _get_app().project.get("layers") or []
        if not layers:
            return "No layers in project."
        lines = [f"  number={L.get('number','')} name={L.get('name','')} lock={L.get('lock',False)}" for L in layers]
        return f"Layers ({len(layers)}):\n" + "\n".join(lines)
    except Exception as e:
        return f"Error: {e}"


def list_markers(**_kw) -> str:
    try:
        from classes.query import Marker
        markers = Marker.filter()
        if not markers:
            return "No markers in project."
        lines = [f"  id={m.data.get('id','')} position={m.data.get('position',0)} name={m.data.get('name','')}" for m in markers]
        return f"Markers ({len(markers)}):\n" + "\n".join(lines)
    except Exception as e:
        return f"Error: {e}"


def new_project(**_kw) -> str:
    try:
        app = _get_app()
        app.project.new()
        app.updates.load(app.project._data, reset_history=True)
        return "New project created."
    except Exception as e:
        return f"Error: {e}"


def save_project(file_path="", **_kw) -> str:
    from classes import info
    if not file_path or not isinstance(file_path, str):
        return "Error: file_path is required."
    file_path = file_path.strip()
    if not file_path.endswith(info.PROJECT_EXT):
        file_path += info.PROJECT_EXT
    try:
        _get_app().window.save_project(file_path)
        return f"Project saved to {file_path}."
    except Exception as e:
        return f"Error: {e}"


def open_project(file_path="", **_kw) -> str:
    if not file_path:
        return "Error: file_path is required."
    try:
        _get_app().window.OpenProjectSignal.emit(file_path.strip())
        return f"Open project requested: {file_path}."
    except Exception as e:
        return f"Error: {e}"


# ---------------------------------------------------------------------------
# Playback & history
# ---------------------------------------------------------------------------

def play(**_kw) -> str:
    try:
        _get_app().window.actionPlay_trigger()
        return "Playback toggled."
    except Exception as e:
        return f"Error: {e}"


def go_to_start(**_kw) -> str:
    try:
        _get_app().window.actionJumpStart_trigger()
        return "Seeked to start."
    except Exception as e:
        return f"Error: {e}"


def go_to_end(**_kw) -> str:
    try:
        _get_app().window.actionJumpEnd_trigger()
        return "Seeked to end."
    except Exception as e:
        return f"Error: {e}"


def undo(**_kw) -> str:
    try:
        _get_app().updates.undo()
        return "Undo performed."
    except Exception as e:
        return f"Error: {e}"


def redo(**_kw) -> str:
    try:
        _get_app().updates.redo()
        return "Redo performed."
    except Exception as e:
        return f"Error: {e}"


# ---------------------------------------------------------------------------
# Timeline / view
# ---------------------------------------------------------------------------

def add_track(**_kw) -> str:
    try:
        _get_app().window.actionAddTrackBelow_trigger()
        return "Track added."
    except Exception as e:
        return f"Error: {e}"


def add_marker(**_kw) -> str:
    try:
        _get_app().window.actionAddMarker_trigger()
        return "Marker added."
    except Exception as e:
        return f"Error: {e}"


def remove_clip(**_kw) -> str:
    try:
        _get_app().window.actionRemoveClip_trigger()
        return "Selected clip(s) removed."
    except Exception as e:
        return f"Error: {e}"


def zoom_in(**_kw) -> str:
    try:
        _get_app().window.actionTimelineZoomIn_trigger()
        return "Timeline zoomed in."
    except Exception as e:
        return f"Error: {e}"


def zoom_out(**_kw) -> str:
    try:
        _get_app().window.actionTimelineZoomOut_trigger()
        return "Timeline zoomed out."
    except Exception as e:
        return f"Error: {e}"


def center_on_playhead(**_kw) -> str:
    try:
        _get_app().window.actionCenterOnPlayhead_trigger()
        return "Centered on playhead."
    except Exception as e:
        return f"Error: {e}"


def import_files(**_kw) -> str:
    try:
        _get_app().window.actionImportFiles_trigger()
        return "Import files dialog opened."
    except Exception as e:
        return f"Error: {e}"


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

def export_video(**_kw) -> str:
    try:
        _get_app().window.actionExportVideo_trigger()
        return "Export video dialog opened."
    except Exception as e:
        return f"Error: {e}"


def get_export_settings(**_kw) -> str:
    try:
        from windows.export import get_default_export_settings
        app = _get_app()
        video_settings, audio_settings, export_type, default_path = get_default_export_settings()
        lines = [
            f"Export type: {export_type}",
            f"Default path: {default_path}",
            "Video: {}x{}, {}/{} fps, codec {}, format {}, bitrate {}".format(
                video_settings.get("width"), video_settings.get("height"),
                video_settings.get("fps", {}).get("num"), video_settings.get("fps", {}).get("den"),
                video_settings.get("vcodec"), video_settings.get("vformat"),
                video_settings.get("video_bitrate")),
            "Audio: codec {}, {} Hz, {} channels, bitrate {}".format(
                audio_settings.get("acodec"), audio_settings.get("sample_rate"),
                audio_settings.get("channels"), audio_settings.get("audio_bitrate")),
            "Frame range: {} - {}".format(video_settings.get("start_frame"), video_settings.get("end_frame")),
        ]
        overrides = app.project.get("export_overrides") or {}
        if overrides:
            lines.append(f"Overrides: {overrides}")
        return "\n".join(lines)
    except Exception as e:
        return f"Error: {e}"


def set_export_setting(key="", value="", **_kw) -> str:
    try:
        app = _get_app()
        overrides = dict(app.project.get("export_overrides") or {})
        kl = key.lower().strip()
        if kl in ("width", "height", "fps_num", "fps_den", "start_frame", "end_frame", "sample_rate", "channels"):
            overrides[kl] = int(value.strip())
        elif kl in ("video_codec", "vcodec"):
            overrides["video_codec"] = value.strip()
        elif kl in ("audio_codec", "acodec"):
            overrides["audio_codec"] = value.strip()
        elif kl in ("output_path", "path"):
            overrides["output_path"] = value.strip()
        elif kl in ("vformat", "format"):
            overrides["vformat"] = value.strip()
        else:
            overrides[kl] = value.strip()
        from classes.app import get_app
        get_app().updates.ignore_history = True
        app.updates.update(["export_overrides"], overrides)
        get_app().updates.ignore_history = False
        return f"Set {kl} = {value}."
    except Exception as e:
        return f"Error: {e}"


def export_video_now(output_path="", **_kw) -> str:
    try:
        from windows.export import export_video_headless, get_default_export_settings
        _, _, _, default_path = get_default_export_settings()
        path = (output_path or "").strip() or None
        err = export_video_headless(path, None, None, None)
        if err:
            return f"Export failed: {err}"
        return f"Exported to {path or default_path}."
    except Exception as e:
        return f"Error: {e}"


# ---------------------------------------------------------------------------
# Clipping (split, slice, add to timeline)
# ---------------------------------------------------------------------------

def get_file_info(file_id="", **_kw) -> str:
    try:
        from classes.query import File
        if not file_id:
            return "Error: file_id is required."
        f = File.get(id=file_id.strip())
        if not f:
            return f"Error: File not found for id={file_id}."
        fps_data = f.data.get("fps") or {}
        fps_num = int(fps_data.get("num", 30))
        fps_den = int(fps_data.get("den", 1))
        video_length = int(f.data.get("video_length", 0))
        return f"file_id={file_id} path={f.data.get('path','')} fps={fps_num}/{fps_den} video_length={video_length}"
    except Exception as e:
        return f"Error: {e}"


def split_file_add_clip(file_id="", start_frame=0, end_frame=0, name="", **_kw) -> str:
    global _last_split_file_id
    try:
        from classes.query import File
        from classes import time_parts
        from classes.ai_metadata_utils import adjust_scene_descriptions_for_subclip

        if not file_id:
            return "Error: file_id is required."
        file_id = str(file_id).strip()
        start_frame = int(start_frame)
        end_frame = int(end_frame)
        f = File.get(id=file_id)
        if not f:
            return f"Error: File not found for id={file_id}."
        fps_data = f.data.get("fps") or {}
        fps_num = int(fps_data.get("num", 30))
        fps_den = int(fps_data.get("den", 1))
        fps = float(fps_num) / float(fps_den) if fps_den else 0.0
        if fps <= 0:
            return "Error: Invalid fps."
        video_length = int(f.data.get("video_length", 0))
        if start_frame < 1 or end_frame < 1:
            return "Error: Frames are 1-based."
        if start_frame >= end_frame:
            return "Error: start_frame must be < end_frame."
        if end_frame > video_length:
            return f"Error: end_frame {end_frame} > video_length {video_length}."

        previous_start = float(f.data.get("start", 0.0))
        start_sec = previous_start + (start_frame - 1) / fps
        end_sec = previous_start + end_frame / fps
        new_file = File()
        new_file.data = copy.deepcopy(f.data)
        new_file.data.pop("name", None)
        new_file.id = None
        new_file.key = None
        new_file.type = "insert"
        new_file.data["start"] = start_sec
        new_file.data["end"] = end_sec

        if "ai_metadata" in new_file.data and new_file.data["ai_metadata"].get("analyzed"):
            new_file.data["ai_metadata"] = adjust_scene_descriptions_for_subclip(
                new_file.data["ai_metadata"], start_sec, end_sec
            )

        if name and isinstance(name, str) and name.strip():
            new_file.data["name"] = name.strip()
        else:
            global_frame = round(previous_start * fps) + start_frame
            t = time_parts.secondsToTime((global_frame - 1) / fps, fps_num, fps_den)
            timestamp = "{}:{}:{}:{}".format(t["hour"], t["min"], t["sec"], t["frame"])
            base = os.path.splitext(os.path.basename(f.data.get("path") or f.data.get("name", "clip")))[0]
            new_file.data["name"] = f"{base} ({timestamp})"
        new_file.save()
        _last_split_file_id = new_file.id
        clip_name = new_file.data.get("name", "")
        return f'Added clip from frame {start_frame} to {end_frame} (name: {clip_name}). Ask: "Would you like this clip added to the timeline at the playhead?" If they say yes, call add_clip_to_timeline_tool with no arguments.'
    except Exception as e:
        return f"Error: {e}"


def add_clip_to_timeline(file_id="", position_seconds="", track="", **_kw) -> str:
    global _last_split_file_id
    try:
        from classes.query import File, Track

        if not file_id or (isinstance(file_id, str) and not file_id.strip()):
            file_id = _last_split_file_id
            if not file_id:
                return "Error: No clip was just created."
        else:
            file_id = str(file_id).strip()
        f = File.get(id=file_id)
        if not f:
            return f"Error: File not found for id={file_id}."
        app = _get_app()
        win = app.window
        fps = app.project.get("fps") or {}
        fps_float = float(fps.get("num", 30)) / float(fps.get("den", 1) or 1)

        if not position_seconds or (isinstance(position_seconds, str) and not position_seconds.strip()):
            pos_sec = float(win.preview_thread.current_frame - 1) / fps_float
        else:
            pos_sec = float(position_seconds)

        if not track or (isinstance(track, str) and not track.strip()):
            selected = getattr(win, "selected_tracks", []) or []
            if selected:
                t = Track.get(id=selected[0])
                track_num = int(t.data.get("number", 1)) if t else 1
            else:
                layers = app.project.get("layers") or []
                track_num = int(layers[0].get("number", 1)) if layers else 1
        else:
            track_num = int(track)

        if QPointF is None:
            from PyQt5.QtCore import QPointF as _QPointF
            pos = _QPointF(pos_sec, 0.0)
        else:
            pos = QPointF(pos_sec, 0.0)

        was_playing = _pause_player()
        try:
            win.timeline.addClip(file_id, pos, track_num)
        finally:
            _resume_player(was_playing)
        _last_split_file_id = None
        return f"Added clip to timeline at position {pos_sec}s on track {track_num}."
    except Exception as e:
        return f"Error: {e}"


def slice_clip_at_playhead(**_kw) -> str:
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
            return "No clip or transition at the playhead."
        win.slice_clips(MenuSlice.KEEP_BOTH)
        n = len(intersecting_clips) + len(intersecting_trans)
        return f"Sliced {n} item(s) at the playhead; both sides kept."
    except Exception as e:
        return f"Error: {e}"


# ---------------------------------------------------------------------------
# Search (selected clip scenes)
# ---------------------------------------------------------------------------

def search_selected_clip_scenes(query="", top_k="5", use_openai_rerank="true", **_kw) -> str:
    try:
        k = int(float(top_k)) if str(top_k).strip() else 5
    except Exception:
        k = 5
    uo = str(use_openai_rerank).strip().lower() not in ("0", "false", "no", "off")

    try:
        from classes.query import Clip
        from classes.ai_metadata_utils import adjust_scene_descriptions_for_subclip
        from classes.api_client import get_backend_client

        clip_obj, win = _get_selected_timeline_clip_and_window()
        if not clip_obj:
            return "Error: No timeline clip selected."

        clip_data = clip_obj.data if isinstance(clip_obj.data, dict) else {}
        clip_start = float(clip_data.get("start", 0.0) or 0.0)
        clip_end = float(clip_data.get("end", 0.0) or 0.0)
        clip_name = clip_data.get("title") or clip_data.get("label") or "Selected Clip"

        per_clip_ai = clip_data.get("ai_metadata") if isinstance(clip_data.get("ai_metadata"), dict) else None
        source_file = _get_source_file_for_clip(clip_obj)
        source_ai = None
        if source_file and isinstance(source_file.data, dict):
            source_ai = source_file.data.get("ai_metadata") if isinstance(source_file.data.get("ai_metadata"), dict) else None

        client = get_backend_client()

        # TwelveLabs search
        if source_ai and client.is_indexing_configured():
            tw = source_ai.get("twelvelabs") if isinstance(source_ai.get("twelvelabs"), dict) else {}
            status = (tw.get("status") or "").lower()
            index_id = tw.get("index_id")
            video_id = tw.get("video_id") or ""

            if status == "ready" and index_id:
                items, err = _twelvelabs_search_in_window(str(index_id), query, page_limit=max(30, k * 10), video_id=str(video_id))
                if not err and items:
                    matches = []
                    for it in items:
                        s = float(getattr(it, "start", 0.0) or 0.0)
                        e = float(getattr(it, "end", 0.0) or 0.0)
                        if e < clip_start or s > clip_end:
                            continue
                        matches.append({
                            "rel_start": max(s, clip_start) - clip_start,
                            "rel_end": min(e, clip_end) - clip_start,
                            "score": float(getattr(it, "score", 0.0) or 0.0),
                            "transcription": getattr(it, "transcription", "") or "",
                        })
                    matches.sort(key=lambda x: x["score"], reverse=True)
                    matches = matches[:max(1, k)]
                    lines = [f"TwelveLabs matches in '{clip_name}' ({_fmt_mmss(clip_start)} - {_fmt_mmss(clip_end)}):"]
                    for m in matches:
                        lines.append(f"- [{_fmt_mmss(m['rel_start'])} - {_fmt_mmss(m['rel_end'])}] score={m['score']:.3f}")
                        if m.get("transcription"):
                            lines.append(f"  transcript: {str(m['transcription']).strip()[:180]}")
                    return "\n".join(lines)

        # Local scene descriptions fallback
        local_ai = per_clip_ai
        if local_ai is None and source_ai is not None:
            local_ai = adjust_scene_descriptions_for_subclip(source_ai, clip_start, clip_end)

        # Simple local search (no langchain dependency)
        scenes = (local_ai or {}).get("scene_descriptions", [])
        if not scenes:
            return "No matches found."
        scored = []
        q_lower = query.lower()
        for s in scenes:
            if not isinstance(s, dict):
                continue
            desc = (s.get("description") or "").strip()
            if not desc:
                continue
            score = 0.0
            if q_lower in desc.lower():
                score = 10.0
            else:
                q_words = set(q_lower.split())
                d_words = set(desc.lower().split())
                overlap = len(q_words & d_words)
                if overlap:
                    score = overlap / (len(q_words) ** 0.5 * len(d_words) ** 0.5)
            if score > 0:
                scored.append({"time": float(s.get("time", 0.0)), "description": desc, "score": score})
        scored.sort(key=lambda x: x["score"], reverse=True)
        results = scored[:k]
        if not results:
            return "No matches found."
        lines = [f"Scene-description matches in '{clip_name}':"]
        for r in results:
            lines.append(f"- [{_fmt_mmss(r['time'])}] score={r['score']:.3f}: {r['description']}")
        return "\n".join(lines)
    except Exception as e:
        log.error("search_selected_clip_scenes: %s", e, exc_info=True)
        return f"Error: {e}"


def slice_selected_clip_at_best_match(query="", **_kw) -> str:
    try:
        from classes.api_client import get_backend_client
        clip_obj, win = _get_selected_timeline_clip_and_window()
        if not clip_obj:
            return "Error: No timeline clip selected."

        client = get_backend_client()
        if not client.is_indexing_configured():
            return "Error: TwelveLabs is not configured."

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
        if not source_ai:
            return "Error: No metadata for source file."

        tw = source_ai.get("twelvelabs") if isinstance(source_ai.get("twelvelabs"), dict) else {}
        status = (tw.get("status") or "").lower()
        index_id = tw.get("index_id")
        if status != "ready" or not index_id:
            return "TwelveLabs not ready for this source video."

        items, err = _twelvelabs_search_in_window(str(index_id), query, page_limit=30, video_id=str(tw.get("video_id") or ""))
        if err:
            return f"Error: {err}"
        if not items:
            return "No matches found."

        best_mid, best_score = None, -1.0
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
            return "No matches overlapped the clip window."

        slice_pos = clip_pos + (best_mid - clip_start)
        from windows.views.timeline import MenuSlice
        _get_app().window.timeline.Slice_Triggered(MenuSlice.KEEP_BOTH, [str(clip_obj.id)], [], slice_pos)
        return f"Sliced at {_fmt_mmss(best_mid - clip_start)} (best match)."
    except Exception as e:
        return f"Error: {e}"


# ---------------------------------------------------------------------------
# Video generation
# ---------------------------------------------------------------------------

def generate_video_and_add_to_timeline(prompt="", duration_seconds="", position_seconds="", track="", **_kw) -> str:
    if QThread is None or QEventLoop is None:
        return "Error: Requires PyQt5."
    app = _get_app()
    prompt = (prompt or "").strip()
    if len(prompt) < 2:
        return "Error: Prompt must be at least 2 characters."

    duration = None
    if duration_seconds and str(duration_seconds).strip():
        try:
            duration = int(float(duration_seconds))
        except Exception:
            pass
    if duration is None:
        settings = app.get_settings()
        duration = int(settings.get("video-generation-duration") or 4)
    duration = max(1, min(10, duration))

    output_path = _output_path_for_generated_video()

    from classes.api_client import get_backend_client
    client = get_backend_client()
    result = client.generate_video(prompt, duration_seconds=duration)
    video_url = result.get("video_url", "")
    err = result.get("error", "")
    if err:
        return f"Error: {err}"
    if not video_url:
        return "Error: No video URL returned."

    try:
        import requests as _req
        resp = _req.get(video_url, timeout=120)
        resp.raise_for_status()
        with open(output_path, "wb") as f:
            f.write(resp.content)
    except Exception as dl_exc:
        return f"Error: Download failed: {dl_exc}"

    try:
        app.window.files_model.add_files([output_path], skip_tagging=True)
        from classes.query import File
        found = File.get(path=output_path) or File.get(path=os.path.normpath(output_path))
        if not found:
            return "Video generated and added to project files."
        was_playing = _pause_player()
        try:
            msg = add_clip_to_timeline(file_id=found.id, position_seconds=position_seconds or "", track=track or "")
        finally:
            _resume_player(was_playing)
        return msg
    except Exception as e:
        return f"Error: {e}"


def insert_vidu_v2v_clip_into_selected_clip(query="", fade_ms="400", **_kw) -> str:
    if QThread is None or QEventLoop is None:
        return "Error: Requires PyQt5."

    clip_obj, win = _get_selected_timeline_clip_and_window()
    if not clip_obj:
        return "Error: No timeline clip selected."

    query = (query or "").strip()
    too_extreme, reason = _is_extreme_for_4_seconds(query)
    if too_extreme:
        return f"Error: {reason}"

    try:
        fm = int(float(fade_ms)) if str(fade_ms).strip() else 400
    except Exception:
        fm = 400

    clip_data = clip_obj.data if isinstance(clip_obj.data, dict) else {}
    clip_start = float(clip_data.get("start", 0.0) or 0.0)
    clip_end = float(clip_data.get("end", 0.0) or 0.0)

    source_file = _get_source_file_for_clip(clip_obj)
    if not source_file or not getattr(source_file, "absolute_path", None) or not source_file.absolute_path():
        return "Error: Could not find source video."

    source_ai = (
        source_file.data.get("ai_metadata")
        if isinstance(source_file.data, dict) and isinstance(source_file.data.get("ai_metadata"), dict)
        else None
    )

    best_mid, best_score = None, -1.0

    # Strategy 1: TwelveLabs
    if source_ai:
        tw = source_ai.get("twelvelabs") if isinstance(source_ai.get("twelvelabs"), dict) else {}
        status = (tw.get("status") or "").lower()
        index_id = tw.get("index_id")
        if status == "ready" and index_id:
            items, err = _twelvelabs_search_in_window(str(index_id), query, page_limit=30, video_id=str(tw.get("video_id") or ""))
            if not err and items:
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

    # Strategy 2: Scene descriptions
    if best_mid is None and source_ai:
        scenes = source_ai.get("scene_descriptions", [])
        q_lower = query.lower()
        for sc in (scenes or []):
            if not isinstance(sc, dict):
                continue
            desc = (sc.get("description") or "").lower()
            t = float(sc.get("time", 0.0) or 0.0)
            if q_lower in desc and clip_start <= t <= clip_end and 0.0 > best_score:
                best_score = 1.0
                best_mid = t

    # Strategy 3: midpoint
    if best_mid is None:
        best_mid = (clip_start + clip_end) / 2.0

    from classes.api_client import get_backend_client
    client = get_backend_client()
    result = client.generate_video(query)
    video_url = result.get("video_url", "")
    err = result.get("error", "")
    if err:
        return f"Error: {err}"

    output_path = _output_path_for_generated_video()
    try:
        import requests as _req
        resp = _req.get(video_url, timeout=120)
        resp.raise_for_status()
        with open(output_path, "wb") as f:
            f.write(resp.content)
    except Exception as dl_exc:
        return f"Error: Download failed: {dl_exc}"

    try:
        app = _get_app()
        app.window.files_model.add_files([output_path], skip_tagging=True)
        return (
            f"AI insert at {_fmt_mmss(best_mid - clip_start)} added to imported clips. "
            "The original clip is unchanged."
        )
    except Exception as e:
        return f"Error: {e}"


def generate_transition_clip(clip_a_id="", clip_b_id="", prompt_hint="", **_kw) -> str:
    from classes.query import Clip
    app = _get_app()
    clip_a = Clip.get(id=clip_a_id) if clip_a_id else None
    clip_b = Clip.get(id=clip_b_id) if clip_b_id else None
    if not clip_a or not clip_b:
        return "Error: Could not find both clips."
    pos_a = float(clip_a.data.get("position", 0))
    end_a = float(clip_a.data.get("end", 0))
    start_a = float(clip_a.data.get("start", 0))
    end_position_a = pos_a + (end_a - start_a)
    layer = clip_a.data.get("layer")
    track = str(layer) if layer is not None else ""
    prompt = (prompt_hint or "").strip() or "Smooth transition, cinematic, 2 seconds, seamless blend"
    return generate_video_and_add_to_timeline(
        prompt=prompt, duration_seconds="2", position_seconds=str(end_position_a), track=track,
    )


# ---------------------------------------------------------------------------
# Tool name → handler mapping
# ---------------------------------------------------------------------------

TOOL_HANDLERS = {
    # Project
    "get_project_info_tool": get_project_info,
    "list_files_tool": list_files,
    "list_clips_tool": list_clips,
    "list_layers_tool": list_layers,
    "list_markers_tool": list_markers,
    "new_project_tool": new_project,
    "save_project_tool": save_project,
    "open_project_tool": open_project,
    # Playback
    "play_tool": play,
    "go_to_start_tool": go_to_start,
    "go_to_end_tool": go_to_end,
    "undo_tool": undo,
    "redo_tool": redo,
    # Timeline
    "add_track_tool": add_track,
    "add_marker_tool": add_marker,
    "remove_clip_tool": remove_clip,
    "zoom_in_tool": zoom_in,
    "zoom_out_tool": zoom_out,
    "center_on_playhead_tool": center_on_playhead,
    "import_files_tool": import_files,
    # Export
    "export_video_tool": export_video,
    "get_export_settings_tool": get_export_settings,
    "set_export_setting_tool": set_export_setting,
    "export_video_now_tool": export_video_now,
    # Clips
    "get_file_info_tool": get_file_info,
    "split_file_add_clip_tool": split_file_add_clip,
    "add_clip_to_timeline_tool": add_clip_to_timeline,
    "slice_clip_at_playhead_tool": slice_clip_at_playhead,
    # Search
    "search_selected_clip_scenes_tool": search_selected_clip_scenes,
    "slice_selected_clip_at_best_match_tool": slice_selected_clip_at_best_match,
    # Video generation
    "generate_video_and_add_to_timeline_tool": generate_video_and_add_to_timeline,
    "insert_vidu_v2v_clip_into_selected_clip_tool": insert_vidu_v2v_clip_into_selected_clip,
    "generate_transition_clip_tool": generate_transition_clip,
}


def execute_tool(tool_name: str, tool_args: dict) -> str:
    """Execute a tool by name with the given arguments. Returns the result string."""
    handler = TOOL_HANDLERS.get(tool_name)
    if not handler:
        return f"Error: Unknown tool '{tool_name}'."
    try:
        return handler(**tool_args)
    except Exception as e:
        log.error("Tool %s execution failed: %s", tool_name, e, exc_info=True)
        return f"Error: {e}"
