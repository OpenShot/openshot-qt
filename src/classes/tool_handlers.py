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

import copy
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import uuid as uuid_module
from typing import Optional

from classes.logger import log
from classes.track_display import (
    format_track_label_for_llm,
    layer_number_to_display_index,
    layers_sorted_by_number,
    normalize_track_or_layer_arg,
)

try:
    from PyQt5.QtCore import (
        QObject, QThread, pyqtSignal, pyqtSlot,
        QEventLoop, QPointF, QTimer,
    )
except ImportError:
    QObject = object
    QThread = None
    pyqtSignal = None
    pyqtSlot = lambda x: x
    QEventLoop = None
    QPointF = None
    QTimer = None

try:
    from PyQt5.QtWidgets import QApplication
except ImportError:
    QApplication = None


# ---------------------------------------------------------------------------
# Main-thread dispatcher (signal-based)
# ---------------------------------------------------------------------------
# QTimer.singleShot(0, fn) called from a *background* thread creates the
# timer on that thread's event loop — if the thread is blocked (as the AI-
# chat WebSocket loop is), the callback never fires and the caller times
# out.  Instead we use a QObject that lives on the main thread and deliver
# the callable via a cross-thread signal which Qt routes through the main
# event loop.

class _MainThreadDispatcher(QObject):
    """Singleton helper that runs callables on the Qt main (GUI) thread."""

    _dispatch = pyqtSignal(object)

    def __init__(self):
        super().__init__()
        self._dispatch.connect(self._on_dispatch)

    @pyqtSlot(object)
    def _on_dispatch(self, payload):
        func, args, result_box, error_box, done = payload
        try:
            result_box[0] = func(*args)
        except Exception as exc:
            error_box[0] = exc
        finally:
            done.set()


_dispatcher = None
_dispatcher_lock = threading.Lock()


def _get_dispatcher():
    """Return (and lazily create) the singleton main-thread dispatcher."""
    global _dispatcher
    if _dispatcher is not None:
        return _dispatcher
    with _dispatcher_lock:
        if _dispatcher is not None:
            return _dispatcher
        d = _MainThreadDispatcher()
        # Ensure the dispatcher lives on the main thread so that signals
        # emitted from background threads are delivered via QueuedConnection.
        app = QApplication.instance() if QApplication is not None else None
        if app is not None:
            d.moveToThread(app.thread())
        _dispatcher = d
        return d


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


def _run_on_main_thread(func, *args, timeout=30):
    """Schedule *func(*args)* on the Qt main thread and block until it
    finishes.  Returns the value returned by *func*.

    Slice_Triggered (and other timeline-mutating code) relies on Qt signals
    being delivered **synchronously** (direct connection) — specifically the
    IgnoreUpdates signal that prevents partial UI refreshes mid-transaction.
    When those signals are emitted from a background thread they become
    **queued** connections and arrive too late, leading to stale cached
    frames and visual glitches.  By routing the work through the main
    thread's event loop we get the same behaviour as a manual keyboard /
    mouse-driven slice.
    """
    if QThread is None:
        # Fallback: no Qt — just call directly (unit-test scenario)
        return func(*args)

    # If we are already on the main thread, run directly
    app = _get_app()
    if QThread.currentThread() is app.thread():
        return func(*args)

    result_box = [None]
    error_box = [None]
    done = threading.Event()

    dispatcher = _get_dispatcher()
    dispatcher._dispatch.emit((func, args, result_box, error_box, done))

    if not done.wait(timeout=timeout):
        raise TimeoutError(
            f"Main-thread operation did not complete within {timeout}s"
        )

    if error_box[0] is not None:
        raise error_box[0]
    return result_box[0]


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


def _ffprobe_video_duration(path) -> float:
    """Return the video duration in seconds, or 0.0 on error."""
    try:
        p = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False,
        )
        val = (p.stdout or "").strip()
        if val and val != "N/A":
            return float(val)
        # Fallback: use format duration
        p2 = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False,
        )
        val2 = (p2.stdout or "").strip()
        return float(val2) if val2 and val2 != "N/A" else 0.0
    except Exception:
        return 0.0


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


# Context for add_clip_to_timeline (remembers last split file id per chat session)
_last_split_file_id_by_chat_session = {}


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

        app = _get_app()
        layers_raw = app.project.get("layers") or []
        kwargs = {}
        if layer and str(layer).strip():
            resolved, err = normalize_track_or_layer_arg(str(layer).strip(), layers_raw)
            if err:
                return err
            kwargs["layer"] = resolved
        clips = Clip.filter(**kwargs)
        if not clips:
            return "No clips in project."
        lines = []
        for c in clips:
            d = c.data
            lid = d.get("layer", "")
            try:
                lid_int = int(lid) if lid != "" and lid is not None else None
            except (TypeError, ValueError):
                lid_int = None
            ui = layer_number_to_display_index(lid_int, layers_raw) if lid_int is not None else None
            ui_part = f" ui_track={ui}" if ui is not None else ""
            tids = (
                [
                    str(L.get("id", ""))
                    for L in layers_raw
                    if int(L.get("number") or 0) == lid_int
                ]
                if lid_int is not None
                else []
            )
            tid_part = f" track_id={tids[0]}" if tids and tids[0] else ""
            lines.append(
                f"  id={d.get('id','')} layer_number={lid_int if lid_int is not None else lid}{ui_part}{tid_part} "
                f"position={d.get('position',0)} start={d.get('start',0)} end={d.get('end',0)}"
            )
        return f"Clips ({len(clips)}):\n" + "\n".join(lines)
    except Exception as e:
        return f"Error: {e}"


def list_layers(**_kw) -> str:
    try:
        layers = _get_app().project.get("layers") or []
        if not layers:
            return "No layers in project."
        asc = layers_sorted_by_number(layers)
        lines = []
        for ui_track, L in enumerate(asc, start=1):
            label = (L.get("label") or L.get("name") or "").strip()
            lines.append(
                f"  id={L.get('id','')} number={L.get('number','')} ui_track={ui_track} "
                f"label={label!r} lock={L.get('lock', False)}"
            )
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
    if not file_path.endswith(info.ALL_PROJECT_EXTS):
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


def delete_clips_on_track(track: str = "", include_transitions: bool = True, **_kw) -> str:
    """
    Delete all clips on a UI track (Track 1..N bottom=1) or storage layer_number.
    Optionally also deletes timeline transitions/effects that sit on the same layer.

    Important: this is implemented as ONE atomic UpdateManager transaction so that
    a single undo restores the entire operation.
    """
    try:
        from classes.query import Clip, Transition

        app = _get_app()
        win = app.window

        layers = app.project.get("layers") or []
        if track is None or (isinstance(track, str) and not track.strip()):
            return "Error: track is required."

        layer_num, err = normalize_track_or_layer_arg(str(track).strip(), layers)
        if err:
            return err
        if layer_num is None:
            return "Error: Unknown track or layer."

        layer_num = int(layer_num)
        layers_out = app.project.get("layers") or []
        track_lbl = format_track_label_for_llm(layer_num, layers_out)

        # Respect locked tracks.
        for L in layers_out:
            try:
                if int(L.get("number") or 0) == layer_num and bool(L.get("lock", False)):
                    return f"Error: Track {track_lbl} is locked."
            except Exception:
                continue

        # One shared transaction id makes undo/redo atomic.
        tid = str(uuid_module.uuid4())
        app.updates.transaction_id = tid
        try:
            # Avoid stale selections pointing at soon-to-be-deleted objects.
            if hasattr(win, "clearSelections"):
                win.clearSelections()

            clips = Clip.filter(layer=layer_num)
            transitions = Transition.filter(layer=layer_num) if include_transitions else []

            # Delete transitions first (they may reference clip time ranges).
            for t in transitions:
                # Clear selection to reduce UI churn (doesn't affect history).
                try:
                    if hasattr(win, "removeSelection"):
                        win.removeSelection(t.id, "transition")
                except Exception:
                    pass
                t.delete()

            for c in clips:
                try:
                    if hasattr(win, "removeSelection"):
                        win.removeSelection(c.id, "clip")
                except Exception:
                    pass
                c.delete()

        finally:
            app.updates.transaction_id = None

        # Refresh preview frame to reflect the new timeline immediately.
        try:
            app.window.refreshFrameSignal.emit()
        except Exception:
            pass

        return (
            f"Deleted {len(clips)} clips and {len(transitions)} transitions on track {track_lbl} "
            f"(atomic undo)."
        )
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
    try:
        from classes.query import File
        from classes import time_parts
        from classes.ai_metadata_utils import adjust_scene_descriptions_for_subclip

        chat_session_id = str(_kw.get("chat_session_id", "") or "default")

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
        # Mark as agent-created subclip so it's hidden from the project files panel
        new_file.data["zenvi_subclip"] = True
        new_file.save()
        _last_split_file_id_by_chat_session[chat_session_id] = new_file.id
        clip_name = new_file.data.get("name", "")
        return (
            f'Subclip created: "{clip_name}" (file_id={new_file.id}) '
            f'from frames {start_frame}–{end_frame}. '
            f'Call add_clip_to_timeline_tool(file_id="{new_file.id}") to place it on the timeline.'
        )
    except Exception as e:
        return f"Error: {e}"


def add_clip_to_timeline(file_id="", position_seconds="", track="", **_kw) -> str:
    try:
        from classes.query import File, Track

        chat_session_id = str(_kw.get("chat_session_id", "") or "default")

        if not file_id or (isinstance(file_id, str) and not file_id.strip()):
            file_id = _last_split_file_id_by_chat_session.get(chat_session_id)
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

        # Detect audio-only files (mp3, wav, ogg, etc. or media_type=="audio")
        file_data = f.data
        _ext = (file_data.get("path") or "").rsplit(".", 1)[-1].lower()
        _audio_exts = {"mp3", "wav", "ogg", "flac", "aac", "m4a", "wma"}
        _is_audio_only = (
            file_data.get("media_type", "") == "audio"
            or _ext in _audio_exts
            or (not file_data.get("has_video", True) and file_data.get("has_audio", False))
        )

        # Determine track FIRST so we can compute position relative to that layer
        if not track or (isinstance(track, str) and not track.strip()):
            layers = app.project.get("layers") or []
            if _is_audio_only:
                # Audio: use the lowest-numbered layer (bottom track)
                track_num = int(min(layers, key=lambda l: l.get("number", 0)).get("number", 1)) if layers else 1
            else:
                selected = getattr(win, "selected_tracks", []) or []
                if selected:
                    t = Track.get(id=selected[0])
                    track_num = int(t.data.get("number", 1)) if t else 1
                else:
                    # Video: use the highest-numbered layer (top track)
                    track_num = int(max(layers, key=lambda l: l.get("number", 0)).get("number", 1)) if layers else 1
        else:
            layers_for_track = app.project.get("layers") or []
            resolved, err = normalize_track_or_layer_arg(str(track).strip(), layers_for_track)
            if err:
                return err
            track_num = resolved

        if not position_seconds or (isinstance(position_seconds, str) and not position_seconds.strip()):
            if _is_audio_only:
                # Audio: always start at position 0 so music covers the whole timeline
                pos_sec = 0.0
            else:
                # Video: append after the last clip on THIS SAME LAYER to avoid cross-track interference
                from classes.query import Clip as _Clip
                same_layer = [c for c in _Clip.filter() if c.data.get("layer", 0) == track_num]
                # 1-frame buffer to prevent adjacent clips from touching (snap-to-grid rounding
                # can otherwise cause the new clip to slightly overlap the previous one)
                _one_frame = 1.0 / max(fps_float, 1.0)
                if same_layer:
                    last_end = max(
                        c.data.get("position", 0) + (c.data.get("end", 0) - c.data.get("start", 0))
                        for c in same_layer
                    )
                    pos_sec = last_end + _one_frame
                else:
                    pos_sec = 0.0
        else:
            pos_sec = float(position_seconds)

        if QPointF is None:
            from PyQt5.QtCore import QPointF as _QPointF
            pos = _QPointF(pos_sec, 0.0)
        else:
            pos = QPointF(pos_sec, 0.0)

        def _do_add():
            win.timeline.addClip(file_id, pos, track_num)

        _run_on_main_thread(_do_add)

        _last_split_file_id_by_chat_session.pop(chat_session_id, None)
        layers_out = app.project.get("layers") or []
        track_lbl = format_track_label_for_llm(int(track_num), layers_out)
        return f"Added clip to timeline at position {pos_sec}s on track {track_lbl}."
    except Exception as e:
        return f"Error: {e}"


def slice_clip_at_playhead(**_kw) -> str:
    try:
        from windows.views.timeline_backend.enums import MenuSlice

        # Read state and perform the slice entirely on the main thread
        result_box = [None]

        def _do_slice():
            from classes.query import Clip, Transition
            app = _get_app()
            win = app.window
            fps = app.project.get("fps") or {}
            fps_float = float(fps.get("num", 30)) / float(fps.get("den", 1) or 1)
            playhead_position = float(win.preview_thread.current_frame - 1) / fps_float
            intersecting_clips = Clip.filter(intersect=playhead_position)
            intersecting_trans = Transition.filter(intersect=playhead_position)
            if not intersecting_clips and not intersecting_trans:
                result_box[0] = "No clip or transition at the playhead."
                return
            win.slice_clips(MenuSlice.KEEP_BOTH)
            n = len(intersecting_clips) + len(intersecting_trans)
            result_box[0] = f"Sliced {n} item(s) at the playhead; both sides kept."

        _run_on_main_thread(_do_slice)

        return result_box[0] or "Slice completed."
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
        if client.is_indexing_configured():
            tw = (source_ai or {}).get("twelvelabs") if isinstance((source_ai or {}).get("twelvelabs"), dict) else {}
            status = (tw.get("status") or "").lower()
            index_id = tw.get("index_id") or ""
            video_id = tw.get("video_id") or ""

            # Fallback: even if twelvelabs metadata is missing (old import),
            # try searching with an empty index_id — the backend will use the
            # first available TwelveLabs index.
            if (status == "ready" and index_id) or not index_id:
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
                        mid = (m['rel_start'] + m['rel_end']) / 2.0
                        lines.append(
                            f"- timestamp {_fmt_mmss(mid)}"
                            f" (segment {_fmt_mmss(m['rel_start'])}-{_fmt_mmss(m['rel_end'])})"
                            f" score={m['score']:.3f}"
                        )
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


_ORDINAL_MAP = {
    "first": 1, "1st": 1, "one": 1,
    "second": 2, "2nd": 2, "two": 2,
    "third": 3, "3rd": 3, "three": 3,
    "fourth": 4, "4th": 4, "four": 4,
    "fifth": 5, "5th": 5, "five": 5,
}


def _parse_occurrence(occurrence_str: str, query: str) -> int:
    """Return 1-based occurrence index (0 = best-score). Checks explicit param first, then query text."""
    try:
        n = int(float(str(occurrence_str).strip()))
        if n > 0:
            return n
    except Exception:
        pass
    q_lower = (query or "").lower()
    for word, n in _ORDINAL_MAP.items():
        if word in q_lower.split():
            return n
    return 0


def _parse_mmss_or_hhmmss_token(tok: str):
    """Return seconds for 'SS', 'M:SS', or 'H:M:SS' tokens, else None."""
    if not tok or not isinstance(tok, str):
        return None
    tok = tok.strip()
    if not tok:
        return None
    if ":" not in tok:
        try:
            return float(tok)
        except ValueError:
            return None
    parts = tok.split(":")
    if len(parts) > 3:
        return None
    try:
        nums = [float(p) for p in parts]
    except ValueError:
        return None
    if len(parts) == 2:
        return nums[0] * 60.0 + nums[1]
    return nums[0] * 3600.0 + nums[1] * 60.0 + nums[2]


def _parse_explicit_source_time_range_sec(query: str):
    """If *query* names a concrete time range in source seconds, return (t0, t1).

    t0/t1 are absolute times in the same frame as timeline clip start/end (source media).
    Returns None when no explicit numeric range is detected (caller uses semantic search).
    """
    if not query or not isinstance(query, str):
        return None
    s = query.strip()
    m = re.search(
        r"(\d+(?:\.\d+)?)\s*(?:seconds?|secs?)\s+to\s+(\d+(?:\.\d+)?)\s*(?:seconds?|secs?)\b",
        s,
        re.IGNORECASE,
    )
    if m:
        t0, t1 = float(m.group(1)), float(m.group(2))
        if t1 > t0:
            return (t0, t1)
    m = re.search(
        r"from\s+(\d+(?:\.\d+)?)\s+to\s+(\d+(?:\.\d+)?)\s*(?:seconds?|secs?)\b",
        s,
        re.IGNORECASE,
    )
    if m:
        t0, t1 = float(m.group(1)), float(m.group(2))
        if t1 > t0:
            return (t0, t1)
    m = re.search(
        r"(\d+(?:\.\d+)?)\s*s\b\s+to\s+(\d+(?:\.\d+)?)\s*s\b",
        s,
        re.IGNORECASE,
    )
    if m:
        t0, t1 = float(m.group(1)), float(m.group(2))
        if t1 > t0:
            return (t0, t1)
    m = re.search(
        r"(\d+:\d{2}(?::\d{2})?)\s+to\s+(\d+:\d{2}(?::\d{2})?)",
        s,
        re.IGNORECASE,
    )
    if m:
        t0 = _parse_mmss_or_hhmmss_token(m.group(1))
        t1 = _parse_mmss_or_hhmmss_token(m.group(2))
        if t0 is not None and t1 is not None and t1 > t0:
            return (t0, t1)
    if re.search(r"\bsec", s, re.IGNORECASE):
        m = re.search(
            r"from\s+(\d+(?:\.\d+)?)\s+to\s+(\d+(?:\.\d+)?)\b",
            s,
            re.IGNORECASE,
        )
        if m:
            t0, t1 = float(m.group(1)), float(m.group(2))
            if t1 > t0:
                return (t0, t1)
    return None


def _slice_timeline_clip_at_source_times(
    clip_id_str: str,
    clip_start: float,
    clip_end: float,
    clip_pos: float,
    layer_num: int,
    file_id_str: str,
    t0: float,
    t1: float,
) -> str:
    """Slice once or twice so the middle segment is approximately source [t0, t1]."""
    from windows.views.timeline_backend.enums import MenuSlice
    from classes.query import Clip

    app = _get_app()
    win = app.window
    fps = app.project.get("fps") or {}
    fps_num = float(fps.get("num", 30))
    fps_den = float(fps.get("den", 1)) or 1.0

    def snap(pos: float) -> float:
        return float(round((float(pos) * fps_num) / fps_den) * fps_den) / fps_num

    eps = 1e-3
    clip_tl_end = clip_pos + (clip_end - clip_start)

    def _find_right_segment(after_pos: float, src_start: float) -> Optional[str]:
        best_id, best_score = None, 1e9
        for c in Clip.filter():
            try:
                c_ly = int(float(c.data.get("layer", 0) or 0))
            except (TypeError, ValueError):
                continue
            if c_ly != int(layer_num):
                continue
            try:
                p = float(c.data.get("position", 0))
                st = float(c.data.get("start", 0))
            except (TypeError, ValueError):
                continue
            if file_id_str and str(c.data.get("file_id") or "") != file_id_str:
                continue
            score = abs(p - after_pos) + abs(st - src_start)
            if score < best_score:
                best_score = score
                best_id = str(c.id)
        if best_id is not None and best_score < 0.25:
            return best_id
        return None

    # Degenerate: full clip
    if t0 <= clip_start + eps and t1 >= clip_end - eps:
        return "Nothing to slice: the requested range spans the whole clip."

    # Only upper boundary inside clip
    if t0 <= clip_start + eps:
        pos2 = snap(clip_pos + (t1 - clip_start))
        if pos2 <= clip_pos + eps or pos2 >= clip_tl_end - eps:
            return (
                f"Error: End time maps outside the clip "
                f"(clip source {clip_start:.3f}s–{clip_end:.3f}s on timeline)."
            )
        win.timeline.Slice_Triggered(MenuSlice.KEEP_BOTH, [clip_id_str], [], pos2)
        return f"Sliced at {_fmt_mmss(t1 - clip_start)} from clip start; middle+right kept."

    # Only lower boundary inside clip
    if t1 >= clip_end - eps:
        pos1 = snap(clip_pos + (t0 - clip_start))
        if pos1 <= clip_pos + eps or pos1 >= clip_tl_end - eps:
            return (
                f"Error: Start time maps outside the clip "
                f"(clip source {clip_start:.3f}s–{clip_end:.3f}s on timeline)."
            )
        win.timeline.Slice_Triggered(MenuSlice.KEEP_BOTH, [clip_id_str], [], pos1)
        return f"Sliced at {_fmt_mmss(t0 - clip_start)} from clip start; left+middle kept."

    pos1 = snap(clip_pos + (t0 - clip_start))
    pos2_abs = snap(clip_pos + (t1 - clip_start))
    if pos1 <= clip_pos + eps or pos1 >= clip_tl_end - eps:
        return "Error: First slice position is outside the clip on the timeline."
    if pos2_abs <= pos1 + eps or pos2_abs >= clip_tl_end - eps:
        return "Error: Second slice position is outside the clip on the timeline."

    win.timeline.Slice_Triggered(MenuSlice.KEEP_BOTH, [clip_id_str], [], pos1)
    right_id = _find_right_segment(pos1, t0)
    if not right_id:
        return (
            "First slice succeeded but the app could not find the new segment "
            "for the second cut. Try slicing once at the playhead, then again."
        )

    pos2 = snap(pos1 + (t1 - t0))
    right_tl_end = pos1 + (clip_end - t0)
    if pos2 <= pos1 + eps or pos2 >= right_tl_end - eps:
        return "Error: Second slice maps outside the trimmed segment."

    win.timeline.Slice_Triggered(MenuSlice.KEEP_BOTH, [right_id], [], pos2)
    return (
        f"Sliced at {_fmt_mmss(t0 - clip_start)} and {_fmt_mmss(t1 - clip_start)} "
        f"(source). Three segments: before, selected range, after."
    )


def slice_selected_clip_at_best_match(query="", occurrence="0", **_kw) -> str:
    try:
        from classes.api_client import get_backend_client

        # ── 1. Read clip/file metadata on the MAIN thread so we see the
        #       latest project state (avoids stale-cache problems when
        #       reading from the background AI-chat thread).
        clip_info_box = [None]   # (... , tw_status, tw_error)
        error_box_pre = [None]

        def _read_clip_info():
            try:
                obj, _win = _get_selected_timeline_clip_and_window()
                if not obj:
                    error_box_pre[0] = "Error: No timeline clip selected."
                    return
                d = obj.data if isinstance(obj.data, dict) else {}
                cs = float(d.get("start", 0.0) or 0.0)
                ce = float(d.get("end", 0.0) or 0.0)
                cp = float(d.get("position", 0.0) or 0.0)
                ly = d.get("layer", 1)
                try:
                    layer_num = int(ly) if ly is not None else 1
                except (TypeError, ValueError):
                    layer_num = 1
                fid = str(d.get("file_id") or "")
                sf = _get_source_file_for_clip(obj)
                sa = (
                    sf.data.get("ai_metadata")
                    if sf and isinstance(sf.data, dict)
                    and isinstance(sf.data.get("ai_metadata"), dict)
                    else None
                )
                # Extract TwelveLabs info (may be absent for old imports)
                tw = (sa or {}).get("twelvelabs") if isinstance((sa or {}).get("twelvelabs"), dict) else {}
                tw_status = (tw.get("status") or "").lower()
                iid = tw.get("index_id") or ""
                vid = tw.get("video_id") or ""
                if not iid:
                    log.warning(
                        "TwelveLabs metadata missing for source file; "
                        "falling back to default index lookup."
                    )
                tw_err = str(tw.get("error") or "").strip()
                clip_info_box[0] = (
                    str(obj.id), cs, ce, cp, str(iid), str(vid), layer_num, fid, tw_status, tw_err
                )
            except Exception as exc:
                error_box_pre[0] = f"Error: {exc}"

        _run_on_main_thread(_read_clip_info)

        if error_box_pre[0]:
            return error_box_pre[0]
        if not clip_info_box[0]:
            return "Error: Could not read clip metadata."

        clip_id_str, clip_start, clip_end, clip_pos, index_id, video_id, layer_num, file_id_str, tw_status, tw_error = clip_info_box[0]

        time_rng = _parse_explicit_source_time_range_sec(query or "")
        if time_rng is not None:
            t0, t1 = time_rng
            eps = 1e-3
            if t0 < clip_start - eps or t1 > clip_end + eps:
                return (
                    f"Error: Requested range [{t0:.2f}s–{t1:.2f}s] is outside this clip's "
                    f"source window [{clip_start:.2f}s–{clip_end:.2f}s]."
                )

            def _do_time_slice():
                return _slice_timeline_clip_at_source_times(
                    clip_id_str,
                    clip_start,
                    clip_end,
                    clip_pos,
                    layer_num,
                    file_id_str,
                    t0,
                    t1,
                )

            try:
                return _run_on_main_thread(_do_time_slice)
            except Exception as exc:
                log.error("time-based slice failed: %s", exc, exc_info=True)
                return f"Error: {exc}"

        if tw_status == "failed":
            detail = f" ({tw_error})" if tw_error else ""
            return (
                "TwelveLabs indexing failed for this video"
                + detail
                + ". Common cause: the cloud API backend cannot open paths on your computer "
                "(indexing runs on the server). Use a local Zenvi backend, or index via a "
                "server-visible path. You can still slice by explicit times, e.g. "
                "'from 4 seconds to 10 seconds'."
            )
        if tw_status == "indexing":
            return (
                "TwelveLabs is still indexing this video. "
                "Please wait for indexing to finish and try again."
            )

        # ── 2. Check backend connectivity (can run on any thread)
        client = get_backend_client()
        if not client.is_indexing_configured():
            return "Error: TwelveLabs is not configured."

        # ── 3. TwelveLabs search (REST call – fine from background thread)
        items, err = _twelvelabs_search_in_window(
            index_id, query, page_limit=30, video_id=video_id,
        )
        if err:
            return f"Error: {err}"
        if not items:
            return "No matches found."

        # ── 4. Collect overlapping matches
        matches = []
        for it in items:
            s = float(getattr(it, "start", 0.0) or 0.0)
            e = float(getattr(it, "end", 0.0) or 0.0)
            if e < clip_start or s > clip_end:
                continue
            mid = (max(s, clip_start) + min(e, clip_end)) / 2.0
            score = float(getattr(it, "score", 0.0) or 0.0)
            matches.append({"mid": mid, "score": score, "start": s})

        if not matches:
            return "No matches overlapped the clip window."

        # ── 5. Determine which match to use
        nth = _parse_occurrence(occurrence, query)
        if nth > 0:
            matches.sort(key=lambda x: x["start"])
            idx = min(nth - 1, len(matches) - 1)
            chosen = matches[idx]
            ordinal_label = f"occurrence #{nth}"
        else:
            matches.sort(key=lambda x: x["score"], reverse=True)
            chosen = matches[0]
            ordinal_label = "best match"

        slice_pos = clip_pos + (chosen["mid"] - clip_start)

        log.info(
            "slice_selected_clip_at_best_match: clip_id=%s clip_start=%.3f "
            "clip_end=%.3f clip_pos=%.3f chosen_mid=%.3f → slice_pos=%.3f",
            clip_id_str, clip_start, clip_end, clip_pos, chosen["mid"], slice_pos,
        )

        # ── 6. Validate: slice_pos must fall inside the clip on the timeline
        clip_timeline_end = clip_pos + (clip_end - clip_start)
        if slice_pos <= clip_pos or slice_pos >= clip_timeline_end:
            return (
                f"Error: Computed slice position ({slice_pos:.3f}s) is outside "
                f"the clip range [{clip_pos:.3f}s – {clip_timeline_end:.3f}s]."
            )

        # ── 7. Perform the slice on the Qt main thread
        from windows.views.timeline_backend.enums import MenuSlice

        slice_error_box = [None]

        def _do_slice():
            try:
                _get_app().window.timeline.Slice_Triggered(
                    MenuSlice.KEEP_BOTH, [clip_id_str], [], slice_pos,
                )
            except Exception as exc:
                slice_error_box[0] = str(exc)

        _run_on_main_thread(_do_slice)

        if slice_error_box[0]:
            return f"Error during slice: {slice_error_box[0]}"

        return f"Sliced at {_fmt_mmss(chosen['mid'] - clip_start)} ({ordinal_label})."
    except Exception as e:
        log.error("slice_selected_clip_at_best_match failed: %s", e, exc_info=True)
        return f"Error: {e}"


# ---------------------------------------------------------------------------
# Video generation
# ---------------------------------------------------------------------------

def _pause_auto_save():
    """Pause auto-save timer to prevent backup interference during generation."""
    try:
        app = _get_app()
        app._generation_in_progress = True
        timer = getattr(app.window, "auto_save_timer", None)
        if timer and timer.isActive():
            timer.stop()
            return True
    except Exception:
        pass
    return False


def _resume_auto_save(was_active):
    """Resume auto-save timer if it was previously active."""
    try:
        app = _get_app()
        app._generation_in_progress = False
    except Exception:
        pass
    if not was_active:
        return
    try:
        app = _get_app()
        timer = getattr(app.window, "auto_save_timer", None)
        if timer:
            timer.start()
    except Exception:
        pass


def _reencode_for_openshot(input_path, output_path=None, width=1920, height=1080):
    """Re-encode a video with a clean container so libopenshot can read it.

    AI-generated downloads often have missing/corrupt moov atoms, wrong
    timebases, or missing audio streams.  A quick re-encode with libx264
    + aac fixes all of that.

    Returns (output_path, None) on success, (None, error) on failure.
    """
    if output_path is None:
        base, ext = os.path.splitext(input_path)
        output_path = f"{base}_clean{ext}"

    vf = (
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,format=yuv420p"
    )
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-vf", vf,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k", "-ac", "2", "-ar", "48000",
        "-movflags", "+faststart",
        "-pix_fmt", "yuv420p",
        output_path,
    ]
    ok, err = _ffmpeg_run(cmd)
    if not ok:
        # Try without audio (source may have no audio stream)
        cmd_no_audio = [
            "ffmpeg", "-y", "-i", input_path,
            "-vf", vf,
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-an",
            "-movflags", "+faststart",
            "-pix_fmt", "yuv420p",
            output_path,
        ]
        ok, err = _ffmpeg_run(cmd_no_audio)
        if not ok:
            return None, f"Re-encode failed: {err}"
    return output_path, None


def _import_generated_video(video_path):
    """Import a generated video into the project with clean metadata.

    Re-encodes the video first to a permanent location (via
    _output_path_for_generated_video), then adds it using skip_tagging=True
    to avoid nested event loops and metadata corruption.

    Returns (File object, None) on success, (None, error_string) on failure.
    """
    from classes.query import File

    # Re-encode for libopenshot compatibility, writing to a permanent path
    # so the file survives tmpdir cleanup after the caller returns.
    perm_path = _output_path_for_generated_video()
    clean_path, err = _reencode_for_openshot(video_path, output_path=perm_path)
    if err:
        log.warning("Re-encode failed, using original: %s", err)
        clean_path = video_path

    final_path = clean_path

    # Import into project on the main thread
    def _do_import():
        _get_app().window.files_model.add_files([final_path], skip_tagging=True)
    _run_on_main_thread(_do_import, timeout=30)

    # Look up the File object
    f = File.get(path=final_path)
    if not f:
        f = File.get(path=os.path.normpath(final_path))
    if not f:
        f = File.get(path=os.path.realpath(final_path))
    if not f:
        for candidate in File.filter():
            try:
                if getattr(candidate, "absolute_path", None) and candidate.absolute_path() == final_path:
                    f = candidate
                    break
            except Exception:
                continue
    return f, None


def fetch_remotion_video_from_supabase(supabase_url="", supabase_path="", **_kw) -> str:
    """Download a rendered Remotion video from its Supabase public URL,
    import it into the project files panel, then delete it from Supabase storage.

    Called by the agent after render_remotion_product_launch_tool succeeds.
    """
    import tempfile
    import json
    import urllib.request

    supabase_url = (supabase_url or "").strip()
    if not supabase_url:
        return "Error: supabase_url is required."

    try:
        # Derive a clean filename from the URL path
        url_path = supabase_url.split("?")[0].rstrip("/")
        raw_name = url_path.split("/")[-1] or "remotion_product_launch.mp4"
        if not raw_name.lower().endswith(".mp4"):
            raw_name += ".mp4"

        tmp_dir = tempfile.mkdtemp(prefix="zenvi_remotion_")
        dest_path = os.path.join(tmp_dir, raw_name)

        log.info("Downloading Remotion video from Supabase: %s → %s", supabase_url, dest_path)

        # Download with a 5-minute timeout
        req = urllib.request.Request(supabase_url, headers={"User-Agent": "ZenviApp/1.0"})
        with urllib.request.urlopen(req, timeout=300) as response, open(dest_path, "wb") as out:
            while True:
                chunk = response.read(65536)
                if not chunk:
                    break
                out.write(chunk)

        size_mb = os.path.getsize(dest_path) / (1024 * 1024)
        log.info("Download complete: %s (%.1f MB)", dest_path, size_mb)

        # Import into project files (re-encodes for libopenshot compatibility)
        f, err = _import_generated_video(dest_path)
        if err:
            return f"Error importing video: {err}"

        file_id = f.id if f else ""

        # Delete from Supabase now that the file is safely imported
        if supabase_path:
            pl_url = os.environ.get("REMOTION_PRODUCT_LAUNCH_URL", "http://localhost:3100")
            try:
                body = json.dumps({"supabase_path": supabase_path}).encode()
                cleanup_req = urllib.request.Request(
                    f"{pl_url}/api/cleanup",
                    data=body,
                    method="DELETE",
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(cleanup_req, timeout=30):
                    log.info("Deleted Supabase file after import: %s", supabase_path)
            except Exception as cleanup_err:
                log.warning("Supabase cleanup failed (non-critical): %s", cleanup_err)

        return (
            f"✅ Remotion product-launch video imported into project files (file_id: {file_id}, "
            f"size: {size_mb:.1f} MB).\n"
            "Use add_clip_to_timeline_tool to add it to the timeline."
        )

    except Exception as e:
        log.error("fetch_remotion_video_from_supabase failed: %s", e, exc_info=True)
        return f"Error downloading video from Supabase: {e}"


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

    # Pause auto-save during generation to prevent backup interference
    auto_save_was_active = _pause_auto_save()
    try:
        from classes.api_client import get_backend_client
        client = get_backend_client()
        result = client.generate_video(prompt, duration_seconds=duration)
        video_url = result.get("video_url", "")
        local_path = result.get("local_path", "")
        err = result.get("error", "")
        if err:
            return f"Error: {err}"

        # Prefer local_path from backend; fall back to downloading
        if local_path and os.path.isfile(local_path):
            output_path = local_path
        elif video_url:
            try:
                import requests as _req
                resp = _req.get(video_url, timeout=120)
                resp.raise_for_status()
                with open(output_path, "wb") as f:
                    f.write(resp.content)
            except Exception as dl_exc:
                return f"Error: Download failed: {dl_exc}"
        else:
            return "Error: No video URL or local path returned."

        try:
            f, import_err = _import_generated_video(output_path)
            if not f:
                return "Video generated and added to project files."

            # When inserting at a specific position, ripple downstream clips
            # forward so the generated clip doesn't overlap them.
            _pos = None
            if position_seconds and str(position_seconds).strip():
                try:
                    _pos = float(position_seconds)
                except Exception:
                    _pos = None

            if _pos is not None:
                # Compute the generated clip's duration from the file metadata
                _gen_dur = float(f.data.get("duration") or duration)

                from classes.query import Clip as _Clip
                _app_ref = app
                _snap_tol = 0.001

                # Determine which layer to ripple: prefer the explicit track arg,
                # then detect from which clips are actually sitting at position >= _pos.
                # Using max(layers) was unreliable — the highest-numbered layer may not
                # be the one the plan agent placed clips on.
                _ripple_layer = None
                if track and str(track).strip():
                    _layers_ripple = _app_ref.project.get("layers") or []
                    _resolved_r, _err_r = normalize_track_or_layer_arg(
                        str(track).strip(), _layers_ripple
                    )
                    if not _err_r and _resolved_r is not None:
                        _ripple_layer = _resolved_r
                if _ripple_layer is None:
                    _clips_at_pos = [
                        c for c in list(_Clip.filter())
                        if float(c.data.get("position", 0)) >= _pos - _snap_tol
                        and c.data.get("id")
                    ]
                    if _clips_at_pos:
                        closest = min(_clips_at_pos,
                                      key=lambda c: float(c.data.get("position", 0)))
                        _ripple_layer = closest.data.get("layer", None)

                def _do_ripple_insert():
                    for c in list(_Clip.filter()):
                        c_pos = float(c.data.get("position", 0))
                        c_layer = c.data.get("layer", 0)
                        cid = c.data.get("id")
                        if (cid
                                and c_pos >= _pos - _snap_tol
                                and (_ripple_layer is None or c_layer == _ripple_layer)):
                            _app_ref.updates.update(
                                ["clips", {"id": cid}], {"position": c_pos + _gen_dur}
                            )

                _run_on_main_thread(_do_ripple_insert)

            was_playing = _pause_player()
            try:
                msg = add_clip_to_timeline(file_id=f.id, position_seconds=position_seconds or "", track=track or "")
            finally:
                _resume_player(was_playing)
            return msg
        except Exception as e:
            return f"Error: {e}"
    finally:
        _resume_auto_save(auto_save_was_active)


def insert_kling_v2v_clip_into_selected_clip(query="", fade_ms="400", **_kw) -> str:
    """Find best match in selected clip, generate a V2V insert via Kling,
    bake an updated clip with crossfades, and import it.

    Pipeline (ported from core/src/classes/ai_openshot_tools.py):
      1. Find the best insertion point via TwelveLabs / scene descriptions / midpoint
      2. Extract a seed video (two segments around the insertion point)
      3. Extract first/last frames for frame-constrained generation
      4. Generate V2V clip via Runware/Kling with seed video + frame constraints
      5. Bake the generated insert into the original clip with crossfades
      6. Re-encode and import with clean metadata
    """
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
    fade_s = max(0.05, min(0.49, float(fm) / 1000.0))

    clip_data = clip_obj.data if isinstance(clip_obj.data, dict) else {}
    clip_start = float(clip_data.get("start", 0.0) or 0.0)
    clip_end = float(clip_data.get("end", 0.0) or 0.0)

    source_file = _get_source_file_for_clip(clip_obj)
    if not source_file or not getattr(source_file, "absolute_path", None) or not source_file.absolute_path():
        return "Error: Could not find source video."
    source_path = source_file.absolute_path()

    source_ai = (
        source_file.data.get("ai_metadata")
        if isinstance(source_file.data, dict) and isinstance(source_file.data.get("ai_metadata"), dict)
        else None
    )

    best_mid, best_score = None, -1.0

    # Strategy 1: TwelveLabs — results are already sorted rank-1-first by the API.
    # Use the END of the rank-1 window so the insert follows after the scene ends.
    if source_ai:
        tw = source_ai.get("twelvelabs") if isinstance(source_ai.get("twelvelabs"), dict) else {}
        status = (tw.get("status") or "").lower()
        index_id = tw.get("index_id") or ""
        video_id = tw.get("video_id") or ""
        if (status == "ready" and index_id) or not index_id:
            items, err = _twelvelabs_search_in_window(str(index_id), query, page_limit=30, video_id=str(video_id))
            if not err and items:
                for it in items:
                    s = float(getattr(it, "start", 0.0) or 0.0)
                    e = float(getattr(it, "end", 0.0) or 0.0)
                    if e < clip_start or s > clip_end:
                        continue
                    # Use the end of the scene window, clamped to the clip bounds.
                    insertion = min(e, clip_end)
                    # Need at least 1 s of original content after insertion for a
                    # meaningful crossfade back; pull the point back if too close to the end.
                    if insertion > clip_end - 1.0:
                        insertion = max(clip_start, clip_end - 1.0)
                    best_mid = insertion
                    log.info(
                        "insert_v2v: rank-1 match [%.2f, %.2f] → insertion at %.2f",
                        s, e, best_mid,
                    )
                    break  # rank-1 result found — stop here

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

    # Strategy 3: fallback — 80% through the clip (biased toward the end)
    if best_mid is None:
        best_mid = clip_start + (clip_end - clip_start) * 0.8
        log.info("insert_v2v: no search results, using 80%% fallback point %.2fs", best_mid)

    # Get video dimensions — clamp to Kling O1 video-edit range [720, 2160]
    vid_width = int(source_file.data.get("width", 1920))
    vid_height = int(source_file.data.get("height", 1080))
    # Kling O1 requires input video width & height ∈ [720, 2160].
    # Scale up proportionally if either dimension is below 720.
    _min_dim = 720
    if vid_width < _min_dim or vid_height < _min_dim:
        scale_factor = max(_min_dim / max(vid_width, 1), _min_dim / max(vid_height, 1))
        vid_width = int(vid_width * scale_factor)
        vid_height = int(vid_height * scale_factor)
    # Ensure even dimensions (required by libx264)
    vid_width = vid_width + (vid_width % 2)
    vid_height = vid_height + (vid_height % 2)
    # Cap at 2160
    if vid_width > 2160 or vid_height > 2160:
        scale_down = min(2160 / max(vid_width, 1), 2160 / max(vid_height, 1))
        vid_width = int(vid_width * scale_down)
        vid_height = int(vid_height * scale_down)
        vid_width = vid_width + (vid_width % 2)
        vid_height = vid_height + (vid_height % 2)
    log.info("insert_v2v: target dims %dx%d", vid_width, vid_height)
    gen_duration = 5  # Kling O1 min supported duration; sent explicitly in I2V mode

    # Pause auto-save during the generation pipeline
    auto_save_was_active = _pause_auto_save()
    try:
        tmpdir = tempfile.mkdtemp(prefix="zenvi_v2v_")
        try:
            # ---- Step 1: Extract 3 s of footage before the insertion point as V2V seed ----
            # Sending Kling a reference video keeps the generated insert visually consistent
            # with the original clip (same scene, lighting, style).
            seed_mp4 = os.path.join(tmpdir, "seed.mp4")
            first_jpg = os.path.join(tmpdir, "first.jpg")
            insert_mp4 = os.path.join(tmpdir, "insert.mp4")

            ref_dur = min(3.0, best_mid - clip_start)
            ref_start = max(0.0, best_mid - ref_dur)
            vf = (
                f"scale={vid_width}:{vid_height}:force_original_aspect_ratio=decrease,"
                f"pad={vid_width}:{vid_height}:(ow-iw)/2:(oh-ih)/2,setsar=1"
            )
            ok, err = _ffmpeg_run([
                "ffmpeg", "-y", "-ss", str(ref_start), "-i", source_path,
                "-t", str(ref_dur), "-vf", vf, "-r", "24", "-an",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", seed_mp4,
            ])
            if not ok:
                return f"Error: Failed to extract seed video: {err}"

            # ---- Step 2: Extract the frame at the insertion point ----
            # Used as the 'first' frame constraint so the generated clip picks up
            # exactly where the original pauses.  No 'last' constraint — Kling
            # generates freely after that, which gives natural-looking motion.
            ok, err = _ffmpeg_run([
                "ffmpeg", "-y", "-ss", str(best_mid), "-i", source_path,
                "-frames:v", "1", "-q:v", "2", first_jpg,
            ])
            if not ok:
                return f"Error: Failed to extract insertion frame: {err}"

            # ---- Step 3: Generate V2V insert ----
            # seed_video_path → V2V mode: Kling uses the reference clip for visual style.
            # duration is sent as a *hint* only; in V2V mode the API may infer the output
            # length from the seed. We probe the actual duration after download (Step 4b).
            prompt = (
                f"{query}\n\n"
                "Constraints: the first frame must exactly match the provided first frame. "
                "Continue the scene naturally for the full duration."
            )
            frame_images_paths = [{"path": first_jpg, "frame": "first"}]

            from classes.api_client import get_backend_client
            client = get_backend_client()
            result = client.generate_video(
                prompt,
                duration_seconds=gen_duration,
                seed_video_path=seed_mp4,
                frame_images_paths=frame_images_paths,
                width=vid_width,
                height=vid_height,
            )
            video_url = result.get("video_url", "")
            local_path = result.get("local_path", "")
            gen_err = result.get("error", "")
            if gen_err:
                return f"Error: {gen_err}"

            # Download the generated insert clip
            if local_path and os.path.isfile(local_path):
                shutil.copy2(local_path, insert_mp4)
            elif video_url:
                try:
                    import requests as _req
                    resp = _req.get(video_url, timeout=120)
                    resp.raise_for_status()
                    with open(insert_mp4, "wb") as f:
                        f.write(resp.content)
                except Exception as dl_exc:
                    return f"Error: Download failed: {dl_exc}"
            else:
                return "Error: No video URL or local path returned."

            # ---- Step 4: Bake updated clip with crossfades ----
            output_path = _output_path_for_generated_video()
            dur_a = max(0.0, best_mid - clip_start)
            dur_c = max(0.0, clip_end - best_mid)
            # Probe the actual duration of the generated clip — do NOT assume it equals
            # gen_duration.  Even a 1-second mismatch makes xfade offsets wrong → corruption.
            insert_dur = _ffprobe_video_duration(insert_mp4)
            if insert_dur < 0.5:
                insert_dur = float(gen_duration)
                log.warning("insert_v2v: could not probe insert duration, using %s", insert_dur)

            # Clamp fade so xfade offsets are valid
            fade = float(fade_s)
            fade = min(fade, 0.49)
            fade = min(fade, max(0.01, dur_a / 2.0) if dur_a > 0 else 0.01)
            fade = min(fade, max(0.01, dur_c / 2.0) if dur_c > 0 else 0.01)
            fade = min(fade, max(0.01, insert_dur / 2.0) if insert_dur > 0 else 0.01)
            fade = max(0.01, fade)

            vf_bake = (
                f"scale={vid_width}:{vid_height}:force_original_aspect_ratio=decrease,"
                f"pad={vid_width}:{vid_height}:(ow-iw)/2:(oh-ih)/2,setsar=1,format=yuv420p,fps=24"
            )
            off1 = max(0.0, dur_a - fade)
            off2 = max(0.0, dur_a + insert_dur - (2.0 * fade))

            has_audio = _ffprobe_has_audio(source_path)
            if has_audio:
                filter_complex = (
                    f"[0:v]trim=start={clip_start}:end={best_mid},setpts=PTS-STARTPTS,{vf_bake}[va];"
                    f"[1:v]setpts=PTS-STARTPTS,{vf_bake}[vb];"
                    f"[0:v]trim=start={best_mid}:end={clip_end},setpts=PTS-STARTPTS,{vf_bake}[vc];"
                    f"[va][vb]xfade=transition=fade:duration={fade}:offset={off1}[vab];"
                    f"[vab][vc]xfade=transition=fade:duration={fade}:offset={off2}[vout];"
                    f"[0:a]atrim=start={clip_start}:end={best_mid},asetpts=PTS-STARTPTS,"
                    f"afade=t=out:st={max(0.0, dur_a - fade)}:d={fade}[aa];"
                    f"anullsrc=channel_layout=stereo:sample_rate=48000,atrim=start=0:end={insert_dur}[ab];"
                    f"[0:a]atrim=start={best_mid}:end={clip_end},asetpts=PTS-STARTPTS,"
                    f"afade=t=in:st=0:d={fade}[ac];"
                    f"[aa][ab][ac]concat=n=3:v=0:a=1[aout]"
                )
                bake_cmd = [
                    "ffmpeg", "-y", "-i", source_path, "-i", insert_mp4,
                    "-filter_complex", filter_complex,
                    "-map", "[vout]", "-map", "[aout]",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                    "-c:a", "aac", "-b:a", "192k",
                    "-movflags", "+faststart",
                    output_path,
                ]
            else:
                filter_complex = (
                    f"[0:v]trim=start={clip_start}:end={best_mid},setpts=PTS-STARTPTS,{vf_bake}[va];"
                    f"[1:v]setpts=PTS-STARTPTS,{vf_bake}[vb];"
                    f"[0:v]trim=start={best_mid}:end={clip_end},setpts=PTS-STARTPTS,{vf_bake}[vc];"
                    f"[va][vb]xfade=transition=fade:duration={fade}:offset={off1}[vab];"
                    f"[vab][vc]xfade=transition=fade:duration={fade}:offset={off2}[vout]"
                )
                bake_cmd = [
                    "ffmpeg", "-y", "-i", source_path, "-i", insert_mp4,
                    "-filter_complex", filter_complex,
                    "-map", "[vout]",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                    "-an",
                    "-movflags", "+faststart",
                    output_path,
                ]

            ok, bake_err = _ffmpeg_run(bake_cmd)
            if not ok:
                return f"Error: Failed to bake updated clip: {bake_err}"

            # ---- Step 5: Import the baked clip ----
            f, import_err = _import_generated_video(output_path)
            if not f:
                log.warning("insert_v2v: File.get failed but add_files succeeded")
            return (
                f"The combined clip (with a {insert_dur:.1f}s AI insert at "
                f"{_fmt_mmss(best_mid - clip_start)}, baked with {int(fade * 1000)}ms "
                f"crossfades) has been added to the imported clips section. "
                "The original clip on the timeline was left unchanged."
            )
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
    except Exception as e:
        log.error("insert_v2v_clip: %s", e, exc_info=True)
        return f"Error: {e}"
    finally:
        _resume_auto_save(auto_save_was_active)


def replace_object_in_selected_clip(description="", duration_seconds="", **_kw) -> str:
    """Replace or update an object/visual element in the selected clip using Kling V2V.

    Pipeline:
      1. Extract the selected clip segment as a reference video (up to 10 s)
      2. Extract first/last frames for frame constraints (maintains continuity)
      3. Generate V2V via Runware/Kling with the clip as visual reference
      4. Import the generated video into the project files panel
    """
    if QThread is None or QEventLoop is None:
        return "Error: Requires PyQt5."

    clip_obj, _win = _get_selected_timeline_clip_and_window()
    if not clip_obj:
        return "Error: No timeline clip selected."

    description = (description or "").strip()
    if not description:
        return "Error: A description of what to replace/update is required."

    clip_data = clip_obj.data if isinstance(clip_obj.data, dict) else {}
    clip_start = float(clip_data.get("start", 0.0) or 0.0)
    clip_end = float(clip_data.get("end", 0.0) or 0.0)
    clip_duration = max(0.1, clip_end - clip_start)

    source_file = _get_source_file_for_clip(clip_obj)
    if not source_file or not getattr(source_file, "absolute_path", None) or not source_file.absolute_path():
        return "Error: Could not find source video for selected clip."
    source_path = source_file.absolute_path()

    # Hard cap at 10 s (Kling O1 max) to avoid credit exhaustion on long clips.
    # Snap to the nearest Kling-supported duration: 5 s or 10 s.
    raw_dur = min(float(duration_seconds), 10.0) if str(duration_seconds).strip() else min(clip_duration, 10.0)
    gen_duration = 10 if raw_dur >= 7.5 else 5

    # Clamp video dimensions to Kling O1 video-edit range [720, 2160]
    vid_width = int(source_file.data.get("width", 1920))
    vid_height = int(source_file.data.get("height", 1080))
    _min_dim = 720
    if vid_width < _min_dim or vid_height < _min_dim:
        scale_f = max(_min_dim / max(vid_width, 1), _min_dim / max(vid_height, 1))
        vid_width = int(vid_width * scale_f)
        vid_height = int(vid_height * scale_f)
    vid_width += vid_width % 2
    vid_height += vid_height % 2
    if vid_width > 2160 or vid_height > 2160:
        scale_d = min(2160 / max(vid_width, 1), 2160 / max(vid_height, 1))
        vid_width = int(vid_width * scale_d)
        vid_height = int(vid_height * scale_d)
        vid_width += vid_width % 2
        vid_height += vid_height % 2

    auto_save_was_active = _pause_auto_save()
    try:
        tmpdir = tempfile.mkdtemp(prefix="zenvi_replace_")
        try:
            ref_mp4 = os.path.join(tmpdir, "ref.mp4")
            first_jpg = os.path.join(tmpdir, "first.jpg")
            last_jpg = os.path.join(tmpdir, "last.jpg")

            vf = (
                f"scale={vid_width}:{vid_height}:force_original_aspect_ratio=decrease,"
                f"pad={vid_width}:{vid_height}:(ow-iw)/2:(oh-ih)/2,setsar=1"
            )

            # Extract the clip segment as the reference video (cap at 10 s)
            extract_dur = min(clip_duration, 10.0)
            ok, err = _ffmpeg_run([
                "ffmpeg", "-y", "-ss", str(clip_start), "-i", source_path,
                "-t", str(extract_dur), "-vf", vf, "-r", "24", "-an",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", ref_mp4,
            ])
            if not ok:
                return f"Error: Failed to extract reference clip: {err}"

            # Extract first and last frames for frame continuity constraints
            ok, _ = _ffmpeg_run(["ffmpeg", "-y", "-i", ref_mp4, "-frames:v", "1", "-q:v", "2", first_jpg])
            if not ok:
                return "Error: Failed to extract first frame from reference clip."
            ok, _ = _ffmpeg_run(["ffmpeg", "-y", "-sseof", "-0.1", "-i", ref_mp4,
                                  "-frames:v", "1", "-q:v", "2", last_jpg])
            if not ok:
                return "Error: Failed to extract last frame from reference clip."

            prompt = (
                f"{description}\n\n"
                "Apply the change throughout the entire video while preserving the original "
                "camera motion, scene composition, and lighting. The first and last frames "
                "must match the provided frame constraints."
            )
            frame_images_paths = [
                {"path": first_jpg, "frame": "first"},
                {"path": last_jpg, "frame": "last"},
            ]

            from classes.api_client import get_backend_client
            client = get_backend_client()
            result = client.generate_video(
                prompt,
                duration_seconds=gen_duration,
                seed_video_path=ref_mp4,
                frame_images_paths=frame_images_paths,
                width=vid_width,
                height=vid_height,
            )
            video_url = result.get("video_url", "")
            local_path = result.get("local_path", "")
            gen_err = result.get("error", "")
            if gen_err:
                return f"Error: {gen_err}"

            output_path = _output_path_for_generated_video()
            if local_path and os.path.isfile(local_path):
                shutil.copy2(local_path, output_path)
            elif video_url:
                try:
                    import requests as _req
                    resp = _req.get(video_url, timeout=120)
                    resp.raise_for_status()
                    with open(output_path, "wb") as fh:
                        fh.write(resp.content)
                except Exception as dl_exc:
                    return f"Error: Download failed: {dl_exc}"
            else:
                return "Error: No video URL or local path returned from generation."

            f, _import_err = _import_generated_video(output_path)
            if not f:
                log.warning("replace_object: File.get failed but add_files succeeded")
            return (
                f"Object replacement complete. A {gen_duration}s AI video with '{description}' "
                "applied has been added to the imported clips panel. "
                "Drag it to the timeline to replace the original clip."
            )
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
    except Exception as e:
        log.error("replace_object_in_selected_clip: %s", e, exc_info=True)
        return f"Error: {e}"
    finally:
        _resume_auto_save(auto_save_was_active)


def generate_transition_clip(clip_a_id="", clip_b_id="", prompt_hint="", **_kw) -> str:
    """Generate a transition video between two clips using Kling V2V with video reference.

    Pipeline:
      1. Extract the last 3 s of clip A as a reference video (gives Kling visual context)
      2. Extract the last frame of clip A and first frame of clip B as frame constraints
      3. Generate via Kling V2V: reference video + first/last frame constraints
         → the result matches clip A's visual style and bridges naturally to clip B
      4. Import the transition clip and insert it between the two clips on the timeline
    """
    from classes.query import Clip, File
    _get_app()

    clip_a = Clip.get(id=clip_a_id) if clip_a_id else None
    clip_b = Clip.get(id=clip_b_id) if clip_b_id else None
    if not clip_a or not clip_b:
        return "Error: Could not find both clips. Use list_clips_tool to get clip IDs."

    # Get source file paths
    file_a_id = clip_a.data.get("file_id", "")
    file_b_id = clip_b.data.get("file_id", "")
    file_a = File.get(id=file_a_id) if file_a_id else None
    file_b = File.get(id=file_b_id) if file_b_id else None
    if not file_a or not file_b:
        return "Error: Could not find source files for the clips."

    path_a = file_a.absolute_path() if hasattr(file_a, 'absolute_path') else file_a.data.get('path', '')
    path_b = file_b.absolute_path() if hasattr(file_b, 'absolute_path') else file_b.data.get('path', '')
    if not path_a or not os.path.isfile(path_a):
        return f"Error: Source video for clip A not found: {path_a}"
    if not path_b or not os.path.isfile(path_b):
        return f"Error: Source video for clip B not found: {path_b}"

    # Timeline positions
    pos_a = float(clip_a.data.get("position", 0))
    start_a = float(clip_a.data.get("start", 0))
    end_a = float(clip_a.data.get("end", 0))
    duration_a = end_a - start_a
    end_position_a = pos_a + duration_a

    layer = clip_a.data.get("layer")
    track = str(layer) if layer is not None else ""

    morph_duration = 5.0
    prompt = (prompt_hint or "").strip()
    if not prompt:
        prompt = (
            "Gradually evolve the opening scene into the closing scene through a fluid, "
            "continuous motion. Preserve the appearance and identity of all people and key "
            "objects while naturally transitioning the pose, setting, and lighting from "
            "the first frame to the last. The movement should feel organic and cinematic, "
            "with no abrupt cuts or unrelated imagery."
        )

    # Clamp clip A dimensions to Kling O1 video-edit range [720, 2160]
    vid_w = int(file_a.data.get("width", 1920))
    vid_h = int(file_a.data.get("height", 1080))
    _min_dim = 720
    if vid_w < _min_dim or vid_h < _min_dim:
        _sf = max(_min_dim / max(vid_w, 1), _min_dim / max(vid_h, 1))
        vid_w = int(vid_w * _sf)
        vid_h = int(vid_h * _sf)
    vid_w += vid_w % 2
    vid_h += vid_h % 2
    if vid_w > 2160 or vid_h > 2160:
        _sd = min(2160 / max(vid_w, 1), 2160 / max(vid_h, 1))
        vid_w = int(vid_w * _sd)
        vid_h = int(vid_h * _sd)
        vid_w += vid_w % 2
        vid_h += vid_h % 2

    # Pause auto-save during the generation pipeline
    auto_save_was_active = _pause_auto_save()
    try:
        tmpdir = tempfile.mkdtemp(prefix="zenvi_morph_")
        try:
            ref_mp4 = os.path.join(tmpdir, "ref_a.mp4")
            frame_a_path = os.path.join(tmpdir, "frame_a.jpg")
            frame_b_path = os.path.join(tmpdir, "frame_b.jpg")

            # Extract last 3 s of clip A as the V2V reference video.
            # This gives Kling the visual style/content of clip A so the
            # generated transition matches it rather than generating arbitrary content.
            ref_dur = min(3.0, duration_a)
            ref_start = max(start_a, end_a - ref_dur)
            vf = (
                f"scale={vid_w}:{vid_h}:force_original_aspect_ratio=decrease,"
                f"pad={vid_w}:{vid_h}:(ow-iw)/2:(oh-ih)/2,setsar=1"
            )
            ok, err = _ffmpeg_run([
                "ffmpeg", "-y", "-ss", str(ref_start), "-i", path_a,
                "-t", str(ref_dur), "-vf", vf, "-r", "24", "-an",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", ref_mp4,
            ])
            if not ok:
                log.warning("generate_transition: could not extract ref video: %s", err)
                ref_mp4 = None  # fall back to frame-only mode

            # Extract last frame of clip A
            time_a = max(0.0, end_a - 0.1) if end_a > 0 else 0.0
            ok, err = _ffmpeg_run([
                "ffmpeg", "-y", "-ss", str(time_a), "-i", path_a,
                "-frames:v", "1", "-q:v", "2", frame_a_path,
            ])
            if not ok:
                return f"Error: Failed to extract last frame from clip A: {err}"

            # Extract first frame of clip B
            start_b = float(clip_b.data.get("start", 0))
            ok, err = _ffmpeg_run([
                "ffmpeg", "-y", "-ss", str(start_b), "-i", path_b,
                "-frames:v", "1", "-q:v", "2", frame_b_path,
            ])
            if not ok:
                return f"Error: Failed to extract first frame from clip B: {err}"

            frame_images_paths = [
                {"path": frame_a_path, "frame": "first"},
                {"path": frame_b_path, "frame": "last"},
            ]

            from classes.api_client import get_backend_client
            client = get_backend_client()

            if ref_mp4 and os.path.isfile(ref_mp4):
                # V2V + frame constraints: reference video gives visual context,
                # frame constraints pin the start/end to match both clips exactly.
                log.info("generate_transition: using V2V reference + frame constraints")
                result = client.generate_video(
                    prompt,
                    duration_seconds=int(morph_duration),
                    seed_video_path=ref_mp4,
                    frame_images_paths=frame_images_paths,
                    width=vid_w,
                    height=vid_h,
                )
            else:
                # Fallback: frame-only morph (original behaviour)
                log.info("generate_transition: falling back to frame-only morph")
                result = client.generate_morph_video(
                    first_image_url="",
                    last_image_url="",
                    start_image_path=frame_a_path,
                    end_image_path=frame_b_path,
                    prompt=prompt,
                    duration_seconds=int(morph_duration),
                    width=vid_w,
                    height=vid_h,
                )

            video_url = result.get("video_url", "")
            local_path = result.get("local_path", "")
            gen_err = result.get("error", "")
            if gen_err:
                return f"Error: {gen_err}"

            # Download the transition video
            morph_path = os.path.join(tmpdir, "morph_video.mp4")
            if local_path and os.path.isfile(local_path):
                shutil.copy2(local_path, morph_path)
            elif video_url:
                try:
                    import requests as _req
                    resp = _req.get(video_url, timeout=120)
                    resp.raise_for_status()
                    with open(morph_path, "wb") as f:
                        f.write(resp.content)
                except Exception as dl_exc:
                    return f"Error: Download failed: {dl_exc}"
            else:
                return "Error: No video URL or local path returned."

            # Import the transition video
            f, import_err = _import_generated_video(morph_path)
            if not f:
                return "Error: Transition video generated but could not be added to project."

            # Probe actual duration from the re-encoded file that was imported
            # (not morph_path — _import_generated_video re-encodes to a new file
            # whose duration may differ slightly from the original download).
            clean_path = f.absolute_path() if hasattr(f, "absolute_path") else None
            actual_dur = _ffprobe_video_duration(clean_path) if clean_path else 0.0
            if actual_dur < 0.5:
                actual_dur = float(morph_duration)
                log.warning("generate_transition: could not probe morph duration, using %s", actual_dur)
            else:
                log.info("generate_transition: probed morph duration=%.3fs", actual_dur)

            # Shift clip B (and all clips after it) right to make room for the
            # transition clip.  This MUST run on the main thread — Clip.save()
            # triggers Qt signals that must fire as direct (synchronous)
            # connections. When called from a background thread they become
            # queued connections and arrive after subsequent timeline mutations,
            # leaving clips in corrupted / overlapping positions.
            #
            # Two precision buffers are applied:
            #  • _snap_tol  — condition tolerance: catches clip B when float drift
            #                 from a prior snap-to-grid leaves its position a
            #                 sub-frame behind end_position_a.
            #  • _pad       — shift padding: shift clip B one frame further than
            #                 actual_dur so that independent snap-to-grid rounding
            #                 on the transition clip and on clip B can never
            #                 produce a sub-frame overlap on the timeline.
            try:
                _fps = _get_app().project.get("fps") or {}
                _fps_float = float(_fps.get("num", 30)) / float(_fps.get("den", 1) or 1)
            except Exception:
                _fps_float = 30.0
            _one_frame = 1.0 / max(_fps_float, 1.0)

            _clip_a_id = clip_a_id
            _end_pos = end_position_a
            _snap_tol = _one_frame          # look back up to 1 frame for clip B
            _shift = actual_dur + _one_frame  # push clip B 1 frame beyond the transition end

            # Determine clip A's layer so we only ripple same-layer clips
            _clip_a_layer = clip_a.data.get("layer", 0)
            _app_ref = _get_app()

            def _shift_clips():
                for c in list(Clip.filter()):
                    c_pos = float(c.data.get("position", 0))
                    c_layer = c.data.get("layer", 0)
                    if (c_pos >= _end_pos - _snap_tol
                            and c.id != _clip_a_id
                            and c_layer == _clip_a_layer):
                        cid = c.data.get("id")
                        if cid:
                            _app_ref.updates.update(
                                ["clips", {"id": cid}], {"position": c_pos + _shift}
                            )

            _run_on_main_thread(_shift_clips)

            # Insert the transition clip at the end of clip A
            was_playing = _pause_player()
            try:
                msg = add_clip_to_timeline(
                    file_id=f.id,
                    position_seconds=str(end_position_a),
                    track=track,
                )
            finally:
                _resume_player(was_playing)

            return (
                f"Transition clip created! A {actual_dur:.2f}s AI transition video was "
                f"generated using Kling (video reference from clip A + frame constraints) "
                f"and inserted between the clips. {msg}"
            )
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
    except Exception as e:
        log.error("generate_transition_clip: %s", e, exc_info=True)
        return f"Error: {e}"
    finally:
        _resume_auto_save(auto_save_was_active)


# ---------------------------------------------------------------------------
# Transitions tools
# ---------------------------------------------------------------------------

def list_transitions(category="all", **_kw) -> str:
    """List all available transitions in OpenShot."""
    try:
        from classes import info
        transitions_dir = os.path.join(info.PATH, "transitions")
        common_dir = os.path.join(transitions_dir, "common")
        extra_dir = os.path.join(transitions_dir, "extra")

        transitions = []

        def process_dir(dir_path, category_name):
            if not os.path.exists(dir_path):
                return
            for filename in sorted(os.listdir(dir_path)):
                if filename.startswith(".") or "thumbs.db" in filename.lower():
                    continue
                path = os.path.join(dir_path, filename)
                file_base_name = os.path.splitext(filename)[0]
                trans_name = file_base_name.replace("_", " ").capitalize()
                transitions.append({
                    "name": trans_name, "filename": filename,
                    "category": category_name, "path": path,
                })

        if category in ("all", "common"):
            process_dir(common_dir, "common")
        if category in ("all", "extra"):
            process_dir(extra_dir, "extra")

        if not transitions:
            return "No transitions found."

        data = {
            "total": len(transitions),
            "transitions": transitions[:50] if len(transitions) > 50 else transitions,
        }
        if len(transitions) > 50:
            data["note"] = f"Showing first 50 of {len(transitions)} transitions."
        return json.dumps(data, indent=2)
    except Exception as e:
        log.error("list_transitions: %s", e, exc_info=True)
        return f"Error: {e}"


def search_transitions(query="", **_kw) -> str:
    """Search for transitions by name."""
    try:
        from classes import info
        transitions_dir = os.path.join(info.PATH, "transitions")
        common_dir = os.path.join(transitions_dir, "common")
        extra_dir = os.path.join(transitions_dir, "extra")

        query_lower = (query or "").lower()
        matches = []

        def search_dir(dir_path, category_name):
            if not os.path.exists(dir_path):
                return
            for filename in os.listdir(dir_path):
                if filename.startswith(".") or "thumbs.db" in filename.lower():
                    continue
                file_base = os.path.splitext(filename)[0]
                trans_name = file_base.replace("_", " ").capitalize()
                if query_lower in trans_name.lower() or query_lower in file_base.lower():
                    matches.append({
                        "name": trans_name, "filename": filename,
                        "category": category_name,
                        "path": os.path.join(dir_path, filename),
                    })

        search_dir(common_dir, "common")
        search_dir(extra_dir, "extra")

        if not matches:
            return f"No transitions found matching '{query}'."

        return json.dumps({"query": query, "matches": len(matches), "transitions": matches}, indent=2)
    except Exception as e:
        log.error("search_transitions: %s", e, exc_info=True)
        return f"Error: {e}"


def add_transition_between_clips(clip1_id="", clip2_id="", transition_name="", duration="1.0", **_kw) -> str:
    """Add a transition between two clips."""
    try:
        from classes.query import Clip
        from classes import info

        app = _get_app()
        win = app.window
        clip1 = Clip.get(id=clip1_id)
        clip2 = Clip.get(id=clip2_id)
        if not clip1:
            return f"Error: Clip '{clip1_id}' not found."
        if not clip2:
            return f"Error: Clip '{clip2_id}' not found."

        # Find transition file
        transitions_dir = os.path.join(info.PATH, "transitions")
        transition_path = None
        search_name = (transition_name or "").lower().replace(" ", "_")
        for cat in ["common", "extra"]:
            cat_dir = os.path.join(transitions_dir, cat)
            if os.path.exists(cat_dir):
                for fn in os.listdir(cat_dir):
                    fb = os.path.splitext(fn)[0]
                    if search_name in fb.lower() or fb.lower() in search_name:
                        transition_path = os.path.join(cat_dir, fn)
                        break
            if transition_path:
                break
        if not transition_path:
            return f"Error: Transition '{transition_name}' not found. Use search_transitions_tool."

        clip1_end = clip1.data.get("position", 0) + (clip1.data.get("end", 0) - clip1.data.get("start", 0))
        try:
            dur = float(duration)
        except ValueError:
            dur = 1.0

        layer1 = clip1.data.get("layer", 0)
        layer2 = clip2.data.get("layer", 0)
        target_layer_for_trans = max(layer1, layer2)
        transition_title = os.path.splitext(os.path.basename(transition_path))[0]

        # OpenShot Mask transitions require clips to OVERLAP to cross-dissolve.
        # Move clip2 backward by `dur` to create the overlap region, then place
        # the Mask at the overlap start.  Only clip2 is moved — downstream clips
        # are NOT rippled.
        clip2_pos = float(clip2.data.get("position", 0))
        clip2_id_val = clip2.data.get("id", clip2_id)
        new_clip2_pos = max(clip2_pos - dur, 0)

        # ALL Qt/openshot calls MUST run on the Qt main thread
        result_box = [None]

        def _do_transition():
            import openshot as _os

            # Build proper keyframe objects (required by OpenShot's Mask renderer)
            fps_data = app.project.get("fps") or {}
            fps_f = float(fps_data.get("num", 30)) / float(fps_data.get("den", 1) or 1)
            snap = lambda t: round(t * fps_f) / fps_f
            snapped_dur = snap(dur)
            snapped_c2_pos = snap(new_clip2_pos)

            # Step 1: Move clip2 backward to create overlap with clip1
            app.updates.update(["clips", {"id": clip2_id_val}], {"position": snapped_c2_pos})

            # Step 2: Place Mask transition in the overlap region
            brightness = _os.Keyframe()
            brightness.AddPoint(1, 1.0, _os.BEZIER)
            brightness.AddPoint(round(snapped_dur * fps_f) + 1, -1.0, _os.BEZIER)
            contrast = _os.Keyframe(3.0)
            trans_reader = _os.QtImageReader(transition_path)

            tid = str(uuid_module.uuid4())
            transition_data = {
                "id": tid,
                "layer": target_layer_for_trans,
                "position": snapped_c2_pos,   # start of the overlap region
                "start": 0.0,
                "end": snapped_dur,
                "brightness": json.loads(brightness.Json()),
                "contrast": json.loads(contrast.Json()),
                "reader": json.loads(trans_reader.Json()),
                "replace_image": False,
                "type": "Mask",
                "title": transition_title,
            }
            win.timeline.update_transition_data(transition_data, only_basic_props=False)
            result_box[0] = (tid, snapped_dur, snapped_c2_pos)

        _run_on_main_thread(_do_transition)
        tid, actual_dur, actual_pos = result_box[0] if result_box[0] else ("?", dur, new_clip2_pos)
        return (
            f"Added '{transition_name}' transition between clips (overlap: {actual_dur:.2f}s).\n"
            f"Clip2 moved to {actual_pos:.2f}s. Transition ID: {tid}"
        )
    except Exception as e:
        log.error("add_transition_between_clips: %s", e, exc_info=True)
        return f"Error: {e}"


def add_transition_to_clip(clip_id="", transition_name="", position="start", duration="1.0", **_kw) -> str:
    """Add a transition (fade in/out) to a single clip."""
    try:
        from classes.query import Clip
        from classes import info

        app = _get_app()
        clip = Clip.get(id=clip_id)
        if not clip:
            return f"Error: Clip '{clip_id}' not found."

        transitions_dir = os.path.join(info.PATH, "transitions")
        transition_path = None
        search_name = (transition_name or "").lower().replace(" ", "_")
        for cat in ["common", "extra"]:
            cat_dir = os.path.join(transitions_dir, cat)
            if os.path.exists(cat_dir):
                for fn in os.listdir(cat_dir):
                    fb = os.path.splitext(fn)[0]
                    if search_name in fb.lower() or fb.lower() in search_name:
                        transition_path = os.path.join(cat_dir, fn)
                        break
            if transition_path:
                break
        if not transition_path:
            return f"Error: Transition '{transition_name}' not found. Use search_transitions_tool."

        clip_position = clip.data.get("position", 0)
        clip_start = clip.data.get("start", 0)
        clip_end = clip.data.get("end", 0)
        clip_duration = clip_end - clip_start
        clip_layer = clip.data.get("layer", 0)
        win = app.window
        transition_title = os.path.splitext(os.path.basename(transition_path))[0]

        try:
            dur = float(duration)
        except ValueError:
            dur = 1.0

        if (position or "").lower() == "end":
            trans_position = clip_position + clip_duration - dur
        else:
            trans_position = clip_position

        result_box = [None]

        # Must run on Qt main thread — openshot.QtImageReader and update_transition_data
        # both touch Qt objects and dispatch to Qt listeners (properties_model, timeline, etc.)
        _is_fade_out = (position or "").lower() == "end"

        def _do_insert():
            import openshot as _os
            fps_data = app.project.get("fps") or {}
            fps_f = float(fps_data.get("num", 30)) / float(fps_data.get("den", 1) or 1)
            snap = lambda t: round(t * fps_f) / fps_f
            snapped_dur = snap(dur)

            brightness = _os.Keyframe()
            if _is_fade_out:
                # Fade OUT: clip starts visible (-1.0) and goes hidden (1.0)
                brightness.AddPoint(1, -1.0, _os.BEZIER)
                brightness.AddPoint(round(snapped_dur * fps_f) + 1, 1.0, _os.BEZIER)
            else:
                # Fade IN: clip starts hidden (1.0) and becomes visible (-1.0)
                brightness.AddPoint(1, 1.0, _os.BEZIER)
                brightness.AddPoint(round(snapped_dur * fps_f) + 1, -1.0, _os.BEZIER)
            contrast = _os.Keyframe(3.0)
            trans_reader = _os.QtImageReader(transition_path)

            tid = str(uuid_module.uuid4())
            transition_data = {
                "id": tid,
                "layer": clip_layer,
                "position": snap(trans_position),
                "start": 0.0,
                "end": snapped_dur,
                "brightness": json.loads(brightness.Json()),
                "contrast": json.loads(contrast.Json()),
                "reader": json.loads(trans_reader.Json()),
                "replace_image": False,
                "type": "Mask",
                "title": transition_title,
            }
            win.timeline.update_transition_data(transition_data, only_basic_props=False)
            result_box[0] = (tid, snapped_dur, snap(trans_position))

        _run_on_main_thread(_do_insert)
        tid, actual_dur, actual_pos = result_box[0] if result_box[0] else ("?", dur, trans_position)
        return (
            f"Added '{transition_name}' transition at {position} of clip.\n"
            f"ID: {tid}, Duration: {actual_dur:.2f}s, Position: {actual_pos:.2f}s"
        )
    except Exception as e:
        log.error("add_transition_to_clip: %s", e, exc_info=True)
        return f"Error: {e}"


# ---------------------------------------------------------------------------
# TTS tools (frontend-delegated: timeline insertion for generated speech)
# ---------------------------------------------------------------------------


def add_tts_audio_to_timeline(audio_path="", track=0, position=0.0, **kwargs) -> str:
    """Add a generated TTS audio file to the timeline."""
    try:
        from classes.query import File, Clip
        app = _get_app()

        if not audio_path or not os.path.isfile(audio_path):
            return f"Error: Audio file not found: {audio_path}"

        file_data = {
            "path": audio_path,
            "id": str(uuid_module.uuid4()),
        }
        clip_data = {
            "id": str(uuid_module.uuid4()),
            "file_id": file_data["id"],
            "layer": int(track),
            "position": float(position),
            "start": 0,
            "end": 0,
            "reader": {"path": audio_path, "has_audio": True, "has_video": False},
        }

        # Must run on Qt main thread — app.updates dispatches to Qt listeners
        def _do_insert():
            app.updates.insert(["files"], file_data)
            app.updates.insert(["clips"], clip_data)

        _run_on_main_thread(_do_insert)

        return f"Added TTS audio to timeline at position {position}s on track {track}."
    except Exception as e:
        log.error("add_tts_audio_to_timeline: %s", e, exc_info=True)
        return f"Error: {e}"


# ---------------------------------------------------------------------------
# Director analysis tools (frontend-delegated: read project state for directors)
# ---------------------------------------------------------------------------


def analyze_timeline_structure(**kwargs) -> str:
    """Get overview of timeline structure: tracks, clips, transitions."""
    try:
        from classes.query import Clip, Track
        app = _get_app()
        proj = app.project
        clips = Clip.filter()
        layers = {}
        for clip in clips:
            layer = clip.data.get("layer", 0)
            layers.setdefault(layer, []).append(clip)
        lines = [f"Timeline Structure:"]
        lines.append(f"  Total clips: {len(clips)}")
        lines.append(f"  Total layers: {len(layers)}")
        for layer_num in sorted(layers.keys()):
            lines.append(f"  Layer {layer_num}: {len(layers[layer_num])} clips")
        transitions = proj.get("transitions") or []
        lines.append(f"  Total transitions: {len(transitions)}")
        effects = proj.get("effects") or []
        lines.append(f"  Total effects: {len(effects)}")
        return "\n".join(lines)
    except Exception as e:
        log.error("analyze_timeline_structure: %s", e, exc_info=True)
        return f"Error: {e}"


def analyze_pacing(**kwargs) -> str:
    """Analyze video pacing: cut frequency, scene durations, rhythm."""
    try:
        from classes.query import Clip
        app = _get_app()
        proj = app.project
        clips = Clip.filter()
        if not clips:
            return "No clips to analyze"
        fps = proj.get("fps", {})
        fps_num = fps.get("num", 30)
        fps_den = fps.get("den", 1)
        fps_value = fps_num / fps_den if fps_den else 30
        durations = []
        for clip in clips:
            start = clip.data.get("start", 0)
            end = clip.data.get("end", 0)
            duration_seconds = (end - start) / fps_value
            durations.append(duration_seconds)
        if not durations:
            return "No clip durations available"
        avg_dur = sum(durations) / len(durations)
        if avg_dur < 2: cat = "Very fast-paced"
        elif avg_dur < 4: cat = "Fast-paced"
        elif avg_dur < 6: cat = "Moderate"
        elif avg_dur < 10: cat = "Slow-paced"
        else: cat = "Very slow-paced"
        lines = [
            f"Pacing Analysis:",
            f"  Total clips: {len(clips)}",
            f"  Average clip duration: {avg_dur:.2f}s",
            f"  Shortest: {min(durations):.2f}s",
            f"  Longest: {max(durations):.2f}s",
            f"  Pacing: {cat}",
            f"  Cuts/min: {60/avg_dur:.1f}" if avg_dur > 0 else "  Cuts/min: N/A",
        ]
        return "\n".join(lines)
    except Exception as e:
        log.error("analyze_pacing: %s", e, exc_info=True)
        return f"Error: {e}"


def analyze_audio_levels(**kwargs) -> str:
    """Analyze audio levels."""
    try:
        from classes.query import Clip
        clips = Clip.filter()
        audio_clips = [c for c in clips if c.data.get("reader", {}).get("has_audio", False)]
        return f"Audio Analysis:\n  Total audio clips: {len(audio_clips)}\n  Detailed audio analysis requires libopenshot integration."
    except Exception as e:
        log.error("analyze_audio_levels: %s", e, exc_info=True)
        return f"Error: {e}"


def analyze_transitions_structure(**kwargs) -> str:
    """Analyze transitions: types, timing, effectiveness."""
    try:
        app = _get_app()
        proj = app.project
        transitions = proj.get("transitions") or []
        if not transitions:
            return "No transitions in project"
        types = {}
        for t in transitions:
            tt = t.get("type", "unknown")
            types[tt] = types.get(tt, 0) + 1
        lines = [f"Transition Analysis:", f"  Total: {len(transitions)}", "  Types:"]
        for tt, count in types.items():
            lines.append(f"    {tt}: {count}")
        return "\n".join(lines)
    except Exception as e:
        log.error("analyze_transitions_structure: %s", e, exc_info=True)
        return f"Error: {e}"


def analyze_clip_content(**kwargs) -> str:
    """Analyze visual content of clips using metadata."""
    try:
        from classes.query import File
        files = File.filter()
        files_with_meta = sum(1 for f in files if f.data.get("ai_metadata"))
        return f"Content Analysis:\n  Total files: {len(files)}\n  Files with AI analysis: {files_with_meta}"
    except Exception as e:
        log.error("analyze_clip_content: %s", e, exc_info=True)
        return f"Error: {e}"


def analyze_music_sync(**kwargs) -> str:
    """Analyze music beat alignment with cuts."""
    return "Music Sync Analysis:\n  Music sync analysis not yet implemented.\n  Requires beat detection and cut timing correlation."


def get_project_metadata_info(**kwargs) -> str:
    """Get project metadata: duration, resolution, fps, format."""
    try:
        app = _get_app()
        proj = app.project
        profile = proj.get("profile") or "unknown"
        fps = proj.get("fps") or {}
        fps_str = f"{fps.get('num', '')}/{fps.get('den', 1)}" if fps else "unknown"
        return (
            f"Project Metadata:\n"
            f"  Profile: {profile}\n"
            f"  Resolution: {proj.get('width', 0)}x{proj.get('height', 0)}\n"
            f"  FPS: {fps_str}\n"
            f"  Duration: {proj.get('duration', 0)} seconds"
        )
    except Exception as e:
        log.error("get_project_metadata_info: %s", e, exc_info=True)
        return f"Error: {e}"


def analyze_clip_visual_content(clip_id=None, **kwargs) -> str:
    """Analyze visual content using AI vision models."""
    try:
        from classes.query import Clip
        clips = [Clip.get(id=clip_id)] if clip_id else Clip.filter()
        clips = [c for c in clips if c]
        if not clips:
            return "No clips found to analyze"
        lines = [f"Visual Content Analysis:", f"  Total clips: {len(clips)}"]
        for clip in clips:
            meta = clip.data.get("ai_metadata", {})
            if meta:
                desc = meta.get("description", "N/A")
                if len(desc) > 100:
                    desc = desc[:97] + "..."
                lines.append(f"\n  Clip {clip.id}:")
                lines.append(f"    Description: {desc}")
        return "\n".join(lines)
    except Exception as e:
        log.error("analyze_clip_visual_content: %s", e, exc_info=True)
        return f"Error: {e}"


# ---------------------------------------------------------------------------
# Stock media / retag / reindex / planning handlers
# ---------------------------------------------------------------------------

def add_stock_media_to_project(local_path: str = "", **kwargs) -> str:
    """Import a downloaded stock file into Project Files."""
    try:
        if not local_path:
            return "Error: local_path is required."
        import os
        if not os.path.isfile(local_path):
            return f"Error: File not found: {local_path}"
        app = _get_app()
        files_model = app.window.files_model
        from classes.query import File
        existing = File.get(path=local_path)
        if existing:
            return f"File already in project (id={existing.id}): {local_path}"

        # MUST run on main thread — files_model.add_files touches Qt objects
        def _do_add():
            files_model.add_files([local_path])

        _run_on_main_thread(_do_add, timeout=30)

        # Look up the File object so we can return the file_id to the agent
        f = File.get(path=local_path)
        if not f:
            f = File.get(path=os.path.normpath(local_path))
        if not f:
            f = File.get(path=os.path.realpath(local_path))
        if not f:
            for candidate in File.filter():
                try:
                    if getattr(candidate, "absolute_path", None) and candidate.absolute_path() == local_path:
                        f = candidate
                        break
                except Exception:
                    continue

        if f:
            log.info("Stock media added to project: %s (id=%s)", local_path, f.id)
            return (
                f"Added to project: {local_path} (file_id={f.id}). "
                f"IMPORTANT: Call add_clip_to_timeline_tool with file_id='{f.id}' to place it on the timeline."
            )
        log.info("Stock media added to project: %s (id not yet available)", local_path)
        return (
            f"Added to project: {local_path}. "
            f"Use list_files_tool to find the file_id, then call add_clip_to_timeline_tool."
        )
    except Exception as e:
        log.error("add_stock_media_to_project: %s", e, exc_info=True)
        return f"Error: {e}"


def retag_project_file(file_id: str = "", **kwargs) -> str:
    """Re-run AI tagging for an existing project file."""
    try:
        if not file_id:
            return "Error: file_id is required."
        from classes.query import File
        file_obj = File.get(id=file_id)
        if not file_obj:
            return f"Error: File not found (id={file_id})."
        file_path = file_obj.data.get("path", "")
        duration = file_obj.data.get("duration", 0) or 0

        MAX_SECONDS = 30 * 60
        if duration > MAX_SECONDS:
            return (
                f"Error: Clip is {duration / 60:.1f} min — exceeds the "
                f"30-minute re-tagging limit."
            )
        app = _get_app()
        files_model = app.window.files_model
        files_model._tag_file_async(file_id)
        return f"Re-tagging started for file {file_id} ({file_path})."
    except Exception as e:
        log.error("retag_project_file: %s", e, exc_info=True)
        return f"Error: {e}"


def reindex_project_file(file_id: str = "", **kwargs) -> str:
    """Re-index an existing project file in TwelveLabs."""
    try:
        if not file_id:
            return "Error: file_id is required."
        from classes.query import File
        file_obj = File.get(id=file_id)
        if not file_obj:
            return f"Error: File not found (id={file_id})."
        file_path = file_obj.data.get("path", "")
        duration = file_obj.data.get("duration", 0) or 0

        MAX_SECONDS = 30 * 60
        if duration > MAX_SECONDS:
            return (
                f"Error: Clip is {duration / 60:.1f} min — exceeds the "
                f"30-minute re-indexing limit."
            )

        from classes.api_client import get_backend_client
        client = get_backend_client()
        if not client.is_indexing_configured():
            return "TwelveLabs is not configured — re-indexing unavailable."

        project_id = ""
        try:
            project_id = _get_app().project.get("id") or ""
        except Exception:
            pass
        index_name = f"zenvi-{project_id}" if project_id else "zenvi-videos"

        result = client.index_video(file_path, index_name, async_mode=False)
        if isinstance(result, dict) and result.get("index_id"):
            return (
                f"Re-indexing complete for file {file_id}. "
                f"index_id={result['index_id']}  video_id={result.get('video_id', '')}"
            )
        return f"Re-indexing failed: {result.get('error', result.get('message', 'unknown'))}"
    except Exception as e:
        log.error("reindex_project_file: %s", e, exc_info=True)
        return f"Error: {e}"


def get_clips_with_full_metadata(**kwargs) -> str:
    """Return all project files with full AI metadata for planning complex edits."""
    try:
        from classes.query import File
        files = File.filter()
        if not files:
            return "No files in project."
        lines = ["Project files with full metadata:"]
        for f in files:
            d = f.data
            dur = d.get("duration", 0) or 0
            m, s = divmod(int(dur), 60)
            media_type = d.get("media_type", "?")
            name = d.get("name") or d.get("path", "?").split("/")[-1]
            ai = d.get("ai_metadata") or {}
            tags = ai.get("tags", {})
            analyzed = ai.get("analyzed", False)
            tl = ai.get("twelvelabs", {}) or {}
            indexed = bool(tl.get("index_id"))
            scene_count = len(ai.get("scene_descriptions") or [])
            objects = ", ".join((tags.get("objects") or [])[:5])
            scenes = ", ".join((tags.get("scenes") or [])[:3])
            desc = (ai.get("description") or "")[:120]
            lines.append(
                f"\n  id={f.id}  name={name}  type={media_type}  "
                f"duration={m}:{s:02d}\n"
                f"    analyzed={analyzed}  indexed={indexed}  scene_count={scene_count}\n"
                f"    objects=[{objects}]\n"
                f"    scenes=[{scenes}]\n"
                f"    description={desc}"
            )
        return "\n".join(lines)
    except Exception as e:
        log.error("get_clips_with_full_metadata: %s", e, exc_info=True)
        return f"Error: {e}"


# ---------------------------------------------------------------------------
# Tool name → handler mapping
# ---------------------------------------------------------------------------

def get_timeline_state(**_kw) -> str:
    """Return a structured snapshot of the current timeline: tracks, clips with positions, and effects."""
    try:
        from classes.query import Clip
        app = _get_app()

        layers = app.project.get("layers") or []

        clips = Clip.filter()
        effects_raw = app.project.get("effects") or []

        if not clips and not effects_raw:
            return "Timeline is empty — no clips or effects have been added yet."

        # Group clips by layer
        by_layer = {}
        for c in clips:
            d = c.data
            layer = d.get("layer", 0)
            by_layer.setdefault(layer, []).append(d)

        def _track_heading(layer_num):
            ui = layer_number_to_display_index(int(layer_num), layers)
            tid = ""
            label = ""
            for L in layers:
                if int(L.get("number") or 0) == int(layer_num):
                    tid = str(L.get("id", ""))
                    label = (L.get("label") or "").strip()
                    break
            parts = []
            if ui is not None:
                parts.append(f"UI Track {ui}")
            parts.append(f"layer_number={layer_num}")
            if tid:
                parts.append(f"track_id={tid}")
            if label:
                parts.append(f"label={label!r}")
            return " | ".join(parts) if parts else f"layer_number={layer_num}"

        # Sort each layer by position (high layer number first matches top-of-stack feel)
        lines = ["=== TIMELINE STATE ==="]
        for layer_num in sorted(by_layer.keys(), reverse=True):
            lines.append(f"\n{_track_heading(layer_num)}:")
            for d in sorted(by_layer[layer_num], key=lambda x: x.get("position", 0)):
                clip_dur = d.get("end", 0) - d.get("start", 0)
                clip_end = d.get("position", 0) + clip_dur
                # Get file name from file_id
                try:
                    from classes.query import File as _File
                    fobj = _File.get(id=d.get("file_id", ""))
                    fname = fobj.data.get("name", d.get("file_id", "?")) if fobj else d.get("file_id", "?")
                except Exception:
                    fname = d.get("file_id", "?")
                lines.append(
                    f"  clip id={d.get('id','')} file={fname!r}"
                    f" @ {d.get('position',0):.2f}s–{clip_end:.2f}s (dur={clip_dur:.2f}s)"
                )

        # Summarise effects/transitions
        if effects_raw:
            lines.append(f"\nEffects/Transitions ({len(effects_raw)}):")
            for e in effects_raw:
                lines.append(
                    f"  id={e.get('id','')} title={e.get('title','?')!r}"
                    f" layer={e.get('layer','')} @ {e.get('position',0):.2f}s end={e.get('end',0):.2f}s"
                )

        # Total timeline duration
        all_ends = [
            d.get("position", 0) + (d.get("end", 0) - d.get("start", 0))
            for c in clips for d in [c.data]
        ]
        if all_ends:
            lines.append(f"\nTotal timeline duration: {max(all_ends):.2f}s")

        return "\n".join(lines)
    except Exception as e:
        log.error("get_timeline_state: %s", e, exc_info=True)
        return f"Error: {e}"


def build_editor_snapshot_for_chat(max_chars: int = 3500) -> str:
    """Compact timeline + file count for LLM grounding. Call from Qt GUI thread."""
    try:
        from classes.query import File

        tl = get_timeline_state()
        nfiles = len(File.filter() or [])
        head = f"[Editor snapshot]\nProject files count: {nfiles}\n"
        body = tl.strip()
        out = f"{head}{body}\n" if body else f"{head}(timeline state unavailable)\n"
        if len(out) > max_chars:
            out = out[: max(0, max_chars - 24)].rstrip() + "\n... (truncated)\n"
        return out + "[/Editor snapshot]\n"
    except Exception as e:
        log.debug("build_editor_snapshot_for_chat: %s", e)
        return ""


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
    "delete_clips_on_track_tool": delete_clips_on_track,
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
    # Remotion
    "fetch_remotion_video_from_supabase_tool": fetch_remotion_video_from_supabase,
    # Video generation
    "generate_video_and_add_to_timeline_tool": generate_video_and_add_to_timeline,
    "insert_kling_v2v_clip_into_selected_clip_tool": insert_kling_v2v_clip_into_selected_clip,
    "replace_object_in_selected_clip_tool": replace_object_in_selected_clip,
    "generate_transition_clip_tool": generate_transition_clip,
    # Transitions
    "list_transitions_tool": list_transitions,
    "search_transitions_tool": search_transitions,
    "add_transition_between_clips_tool": add_transition_between_clips,
    "add_transition_to_clip_tool": add_transition_to_clip,
    # TTS (timeline insertion)
    "add_tts_audio_to_timeline_tool": add_tts_audio_to_timeline,
    # Director analysis (read-only project state access)
    "analyze_timeline_structure_tool": analyze_timeline_structure,
    "analyze_pacing_tool": analyze_pacing,
    "analyze_audio_levels_tool": analyze_audio_levels,
    "analyze_transitions_tool": analyze_transitions_structure,
    "analyze_clip_content_tool": analyze_clip_content,
    "analyze_music_sync_tool": analyze_music_sync,
    "get_project_metadata_tool": get_project_metadata_info,
    "analyze_clip_visual_content_tool": analyze_clip_visual_content,
    # Stock media / retag / reindex / planning
    "add_stock_media_to_project_tool": add_stock_media_to_project,
    "retag_project_file_tool": retag_project_file,
    "reindex_project_file_tool": reindex_project_file,
    "get_clips_with_full_metadata_tool": get_clips_with_full_metadata,
    "get_timeline_state_tool": get_timeline_state,
}


def execute_tool(tool_name: str, tool_args: dict) -> str:
    """Execute a tool by name with the given arguments. Returns the result string."""
    handler = TOOL_HANDLERS.get(tool_name)
    if not handler:
        return f"Error: Unknown tool '{tool_name}'."

    # chat_session_id is used for tool state isolation (e.g. split/add clip chains).
    # Only pass it through to the relevant handlers.
    if isinstance(tool_args, dict) and "chat_session_id" in tool_args:
        if tool_name not in ("split_file_add_clip_tool", "add_clip_to_timeline_tool"):
            tool_args = dict(tool_args)
            tool_args.pop("chat_session_id", None)

    def _invoke():
        try:
            return handler(**tool_args)
        except Exception as e:
            log.error("Tool %s execution failed: %s", tool_name, e, exc_info=True)
            return f"Error: {e}"

    try:
        if QThread is None:
            return _invoke()
        app = _get_app()
        if QThread.currentThread() is app.thread():
            return _invoke()
        return _run_on_main_thread(_invoke)
    except Exception as e:
        log.error("Tool %s dispatch failed: %s", tool_name, e, exc_info=True)
        return f"Error: {e}"
