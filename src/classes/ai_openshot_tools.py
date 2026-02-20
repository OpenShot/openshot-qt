"""
OpenShot tools for the LangChain agent. All tools assume they are run on the Qt main thread
(dispatched by the agent runner). They call get_app().project, get_app().updates, get_app().window.
"""

import copy
import json
import os
import uuid as uuid_module
from classes.logger import log
from classes.ai_metadata_utils import adjust_scene_descriptions_for_subclip

try:
    from PyQt5.QtCore import QObject, QThread, pyqtSignal, pyqtSlot, QEventLoop
except ImportError:
    QObject = object
    QThread = None
    pyqtSignal = None
    pyqtSlot = lambda x: x
    QEventLoop = None


def _get_app():
    """Get app; must be called from main thread."""
    from classes.app import get_app
    return get_app()


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
        _get_app().updates.ignore_history = True
        app.updates.update(["export_overrides"], overrides)
        _get_app().updates.ignore_history = False
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
        win.timeline.addClip(file_id, pos, track_num)
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


class _RemotionGenerationThread(QThread if QThread else object):
    """Subclass of QThread for Remotion video generation: run() is always executed in the worker thread."""
    if pyqtSignal is not None:
        finished_with_result = pyqtSignal(str, str)  # path_or_empty, error_or_empty
        progress_update = pyqtSignal(int, str)  # progress (0-100), status message

    def __init__(self, api_key, prompt, base_url, output_path, duration_seconds=None):
        if QThread is not None:
            super().__init__()
        self._api_key = api_key
        self._prompt = prompt
        self._base_url = base_url
        self._output_path = output_path
        self._duration_seconds = duration_seconds

    def run(self):
        """Execute Remotion video generation in worker thread"""
        from classes.video_generation.remotion_client import (
            RemotionError,
            render_from_repo,
            download_video,
        )

        try:
            # Progress callback
            def on_progress(progress: int, status: str):
                if pyqtSignal is not None and hasattr(self, "progress_update"):
                    self.progress_update.emit(progress, status)
                log.info(f"Remotion progress: {progress}% - {status}")

            # For now, we'll use repo-based rendering with a generic template
            # In the future, this could be expanded to support Sonar data rendering
            # Using "product-launch" template as it's versatile for general video content
            result = render_from_repo(
                api_key=self._api_key,
                repo_url="https://github.com/remotion-dev/template-still",
                template="product-launch",  # Use product-launch template (available on local server)
                user_input=self._prompt,
                codec="h264",
                base_url=self._base_url,
                timeout_seconds=300,
                poll_callback=on_progress,
            )

            # Download the video
            job_id = result.get('jobId')
            if not job_id:
                if pyqtSignal is not None and hasattr(self, "finished_with_result"):
                    self.finished_with_result.emit("", "No job ID returned from Remotion")
                return

            success, error = download_video(
                api_key=self._api_key,
                job_id=job_id,
                dest_path=self._output_path,
                base_url=self._base_url,
                timeout_seconds=300,
            )

            if pyqtSignal is not None and hasattr(self, "finished_with_result"):
                if success:
                    self.finished_with_result.emit(self._output_path, "")
                else:
                    self.finished_with_result.emit("", error or "Download failed")

        except RemotionError as e:
            log.error(f"Remotion generation failed: {e}")
            if pyqtSignal is not None and hasattr(self, "finished_with_result"):
                self.finished_with_result.emit("", str(e))
        except Exception as e:
            log.error(f"Unexpected error in Remotion generation: {e}")
            if pyqtSignal is not None and hasattr(self, "finished_with_result"):
                self.finished_with_result.emit("", f"Unexpected error: {str(e)}")


class _ObjectReplacementThread(QThread if QThread else object):
    """Subclass of QThread: run() is always executed in the worker thread."""
    if pyqtSignal is not None:
        finished_with_result = pyqtSignal(dict)  # result dict from replace_object_in_video

    def __init__(self, video_path, object_desc, replacement_desc, start, end):
        if QThread is not None:
            super().__init__()
        self._video_path = video_path
        self._object_desc = object_desc
        self._replacement_desc = replacement_desc
        self._start = start
        self._end = end

    def run(self):
        # QThread.run() is always executed in the worker thread.
        try:
            from classes.ai_object_replacer import replace_object_in_video
            result = replace_object_in_video(
                video_path=self._video_path,
                object_description=self._object_desc,
                replacement_description=self._replacement_desc,
                start_sec=self._start,
                end_sec=self._end,
                keyframe_interval=0.5,
            )
            if pyqtSignal is not None and hasattr(self, "finished_with_result"):
                self.finished_with_result.emit(result)
        except Exception as e:
            # Fallback error result
            err_res = {
                "success": False,
                "error": str(e),
                "output_path": None,
                "frames_processed": 0,
                "frames_with_object": 0
            }
            if pyqtSignal is not None and hasattr(self, "finished_with_result"):
                self.finished_with_result.emit(err_res)


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
    import tempfile
    return os.path.join(tempfile.gettempdir(), "flowcut_generated_{}.mp4".format(uuid_module.uuid4().hex[:12]))


def generate_video_and_add_to_timeline(
    prompt,
    duration_seconds=None,
    position_seconds="",
    track="",
) -> str:
    """Generate a video from prompt via configured service (Runware or Remotion), then add it to the timeline. Runs API+download in worker thread."""
    if QThread is None or QEventLoop is None:
        return "Error: Video generation requires PyQt5."
    app = _get_app()
    settings = app.get_settings()

    # Check which video generation service is selected
    service = (settings.get("video-generation-service") or "runware").strip()

    prompt = (prompt or "").strip()
    if len(prompt) < 2:
        return "Error: Prompt must be at least 2 characters."

    duration = duration_seconds
    if duration is None:
        duration = int(settings.get("video-generation-duration") or 4)
    duration = max(1, min(10, int(duration)))

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

    # Route to appropriate service
    if service == "remotion":
        # Remotion service
        api_key = (settings.get("remotion-api-key") or "").strip()
        if not api_key:
            return "Remotion is not configured. Add your Remotion API key in Preferences > AI."
        base_url = (settings.get("remotion-base-url") or "http://localhost:4500/api/v1").strip()

        thread = _RemotionGenerationThread(
            api_key, prompt, base_url, output_path, duration
        )
        status_message = "Generating video with Remotion..."
    else:
        # Runware service (default)
        api_key = (settings.get("runware-api-key") or "").strip()
        if not api_key:
            return "Runware is not configured. Add your Runware API key in Preferences > AI, or switch to Remotion in Video Generation Service."
        model = (settings.get("video-generation-model") or "vidu:3@2").strip() or "vidu:3@2"
        width, height = 640, 352  # Vidu Q2 Turbo allowed 16:9 (640x352)

        thread = _VideoGenerationThread(
            api_key, prompt, duration, model, width, height, output_path
        )
        status_message = "Generating video with Runware..."

    thread.finished_with_result.connect(receiver.on_done)
    loop_holder[0] = QEventLoop(app)
    status_bar = getattr(app.window, "statusBar", None)
    try:
        if status_bar is not None:
            status_bar.showMessage(status_message, 0)
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
        app.window.files_model.add_files([path])
        from classes.query import File
        f = File.get(path=path)
        if not f:
            f = File.get(path=os.path.normpath(path))
        if not f:
            for candidate in File.filter():
                if getattr(candidate, "absolute_path", None) and candidate.absolute_path() == path:
                    f = candidate
                    break
        if not f:
            return "Error: Video was downloaded but could not be added to the project."
        file_id = f.id
        msg = add_clip_to_timeline(file_id=file_id, position_seconds=position_seconds or None, track=track or None)
        return msg
    except Exception as e:
        log.error("generate_video_and_add_to_timeline: %s", e, exc_info=True)
        return "Error: {}".format(e)


class _MorphTransitionThread(QThread if QThread else object):
    """Worker thread for morph transition generation."""
    if pyqtSignal is not None:
        finished_with_result = pyqtSignal(str, str)  # (output_path, error)

    def __init__(self, video_a_path, video_b_path, output_path, prompt, duration, api_key, model):
        if QThread is not None:
            super().__init__()
        self._video_a = video_a_path
        self._video_b = video_b_path
        self._output = output_path
        self._prompt = prompt
        self._duration = duration
        self._api_key = api_key
        self._model = model

    def run(self):
        try:
            from classes.ai_morph_transition import generate_morph_transition
            success, error = generate_morph_transition(
                video_a_path=self._video_a,
                video_b_path=self._video_b,
                output_path=self._output,
                prompt=self._prompt,
                duration_seconds=self._duration,
                api_key=self._api_key,
                model=self._model,
            )
            if success:
                self.finished_with_result.emit(self._output, "")
            else:
                self.finished_with_result.emit("", error or "Morph transition failed.")
        except Exception as e:
            self.finished_with_result.emit("", str(e))


def generate_transition_clip(clip_a_id: str, clip_b_id: str, duration_seconds: str = "5") -> str:
    """Generate a morph transition video between two clips using Kling (start/end frame images) and insert it between them on the timeline."""
    if QThread is None or QEventLoop is None:
        return "Error: Morph transition requires PyQt5."

    from classes.query import Clip, File

    app = _get_app()
    settings = app.get_settings()
    api_key = (settings.get("runware-api-key") or "").strip()
    if not api_key:
        return "Error: Runware API key not configured. Add it in Preferences."

    clip_a = Clip.get(id=clip_a_id) if clip_a_id else None
    clip_b = Clip.get(id=clip_b_id) if clip_b_id else None
    if not clip_a or not clip_b:
        return "Error: Could not find both clips. Use list_clips_tool to get clip IDs."

    # Get file paths for both clips
    file_a_id = clip_a.data.get("file_id", "")
    file_b_id = clip_b.data.get("file_id", "")
    file_a = File.get(id=file_a_id) if file_a_id else None
    file_b = File.get(id=file_b_id) if file_b_id else None
    if not file_a or not file_b:
        return "Error: Could not find source files for the clips."
    path_a = file_a.absolute_path() if hasattr(file_a, 'absolute_path') else file_a.data.get('path', '')
    path_b = file_b.absolute_path() if hasattr(file_b, 'absolute_path') else file_b.data.get('path', '')
    if not path_a or not os.path.isfile(path_a):
        return "Error: Source video for clip A not found: {}".format(path_a)
    if not path_b or not os.path.isfile(path_b):
        return "Error: Source video for clip B not found: {}".format(path_b)

    # Timeline positions
    pos_a = float(clip_a.data.get("position", 0))
    start_a = float(clip_a.data.get("start", 0))
    end_a = float(clip_a.data.get("end", 0))
    duration_a = end_a - start_a
    end_position_a = pos_a + duration_a

    pos_b = float(clip_b.data.get("position", 0))
    layer = clip_a.data.get("layer")
    track = str(layer) if layer is not None else ""

    # Duration
    try:
        morph_duration = float(duration_seconds)
    except (TypeError, ValueError):
        morph_duration = 5.0
    morph_duration = max(3, min(10, morph_duration))

    # Prompt — instruct the model to morph start frame into end frame
    prompt = (
        "Gradually evolve the opening scene into the closing scene through a fluid, "
        "continuous motion. Preserve the appearance and identity of all people and key "
        "objects while naturally transitioning the pose, setting, and lighting from "
        "the first frame to the last. The movement should feel organic and cinematic, "
        "with no abrupt cuts or unrelated imagery."
    )

    model = "klingai:kling@o1"
    output_path = _output_path_for_generated_video()

    # Run morph in worker thread
    result_holder = [None, None]  # [path, error]
    loop_holder = [None]

    class _DoneReceiver(QObject if QObject is not object else object):
        def on_done(self, path, error):
            result_holder[0] = path
            result_holder[1] = error
            if loop_holder[0]:
                loop_holder[0].quit()

    receiver = _DoneReceiver()
    thread = _MorphTransitionThread(
        video_a_path=path_a,
        video_b_path=path_b,
        output_path=output_path,
        prompt=prompt,
        duration=morph_duration,
        api_key=api_key,
        model=model,
    )
    thread.finished_with_result.connect(receiver.on_done)
    loop_holder[0] = QEventLoop(app)
    status_bar = getattr(app.window, "statusBar", None)
    try:
        if status_bar is not None:
            status_bar.showMessage("Generating morph transition...", 0)
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
        return "Error: Morph transition video file not found."

    # Add to project and timeline
    try:
        app.window.files_model.add_files([path])
        f = File.get(path=path)
        if not f:
            f = File.get(path=os.path.normpath(path))
        if not f:
            for candidate in File.filter():
                if getattr(candidate, "absolute_path", None) and candidate.absolute_path() == path:
                    f = candidate
                    break
        if not f:
            return "Error: Morph video generated but could not be added to project."

        # Shift clip B (and all clips after it) right to make room for the morph
        from classes.query import Clip as ClipQuery
        all_clips = list(ClipQuery.filter())
        for c in all_clips:
            c_pos = float(c.data.get("position", 0))
            c_layer = c.data.get("layer")
            if c_pos >= end_position_a and c.id != clip_a_id:
                c.data["position"] = c_pos + morph_duration
                c.save()

        # Insert the morph clip at the end of clip A
        msg = add_clip_to_timeline(
            file_id=f.id,
            position_seconds=str(end_position_a),
            track=track,
        )
        return (
            "Morph transition created! A {:.0f}s AI morph video was generated using Kling "
            "(last frame of clip A → first frame of clip B) and inserted between the clips. {}"
        ).format(morph_duration, msg)
    except Exception as e:
        log.error("generate_transition_clip: %s", e, exc_info=True)
        return "Error: {}".format(e)


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
        """Generate a video from a text prompt using AI video generation (supports Runware/Vidu or Remotion, configured in user settings) and add it to the timeline. Use when the user asks to generate, create, or make a video with any service including Remotion. The video generation service is selected in Preferences > AI settings. Argument: prompt (required, describe the video). Optional: duration_seconds (default from settings, e.g. 4); position_seconds (empty for playhead); track (empty for selected or first track)."""
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
    def generate_transition_clip_tool(clip_a_id: str, clip_b_id: str, duration_seconds: str = "5") -> str:
        """Generate an AI morph transition video between two clips and insert it between them on the timeline. This automatically extracts the last frame of clip A and the first frame of clip B, then uses Kling AI to generate a smooth morph/transition video that seamlessly connects the two scenes. No description of the transition is needed — the AI figures out the motion from the two frames. The morph video is inserted between the clips and clip B is shifted right to make room. Use list_clips_tool first to get clip IDs. Arguments: clip_a_id (ID of the first clip), clip_b_id (ID of the second clip). Optional: duration_seconds (3-10, default 5). Use when the user asks for a morph transition, smooth transition, or AI transition between two clips."""
        return generate_transition_clip(clip_a_id=clip_a_id, clip_b_id=clip_b_id, duration_seconds=duration_seconds)

    @tool
    def replace_object_in_video_tool(
        file_id: str,
        object_description: str,
        replacement_description: str,
        start_time: str = "0",
        end_time: str = "-1",
    ) -> str:
        """Replace an object in a video file with something else using AI. The AI detects the object in video frames, creates a mask, and inpaints the replacement. Use when the user asks to replace, swap, or change an object in a video. Arguments: file_id (string, use list_files_tool to find it), object_description (what to find, e.g. 'the water bottle the man is holding'), replacement_description (what to replace it with, e.g. 'a Red Bull can'). Optional: start_time (seconds, default 0), end_time (seconds, default -1 for end of video)."""
        try:
            from classes.query import File
            from classes.ai_object_replacer import replace_object_in_video
            if not file_id or not isinstance(file_id, str):
                return "Error: file_id is required. Use list_files_tool to find file IDs."
            f = File.get(id=file_id.strip())
            if not f:
                return "Error: File not found for id={}. Use list_files_tool.".format(file_id)
            video_path = f.absolute_path() if hasattr(f, 'absolute_path') else f.data.get('path', '')
            if not video_path or not os.path.isfile(video_path):
                return "Error: Video file not found at path: {}".format(video_path)

            start_f = float(start_time) if start_time else 0.0
            end_f = float(end_time) if end_time else -1.0

            if QThread is None or QEventLoop is None:
                return "Error: Object replacement requires PyQt5."

            # Threaded execution to avoid freezing main thread
            result_holder = [{}]
            loop_holder = [None]

            class _ObjReplDoneReceiver(QObject if QObject is not object else object):
                if pyqtSignal is not None:
                    pass
                def on_done(self, result):
                    result_holder[0] = result
                    if loop_holder[0]:
                        loop_holder[0].quit()

            receiver = _ObjReplDoneReceiver()
            thread = _ObjectReplacementThread(
                video_path=video_path,
                object_desc=object_description.strip(),
                replacement_desc=replacement_description.strip(),
                start=start_f,
                end=end_f
            )
            thread.finished_with_result.connect(receiver.on_done)
            
            loop_holder[0] = QEventLoop(_get_app())
            status_bar = getattr(_get_app().window, "statusBar", None)
            
            try:
                if status_bar is not None:
                    status_bar.showMessage("Replacing object via AI...", 0)
                thread.start()
                loop_holder[0].exec_()
            finally:
                if status_bar is not None:
                    status_bar.clearMessage()
            
            thread.quit()
            thread.wait(5000)
            try:
                thread.finished_with_result.disconnect(receiver.on_done)
            except Exception:
                pass

            result = result_holder[0]

            if result.get("success"):
                # Import the new video into the project
                output_path = result["output_path"]
                app = _get_app()
                app.window.files_model.add_files([output_path])
                return (
                    "Object replacement complete! "
                    "Scanned {} frames with Phi-3.5 Vision — found '{}' in {} frames. "
                    "Replaced {} segment(s) with '{}'. "
                    "New video added to project: {}. "
                    "Use add_clip_to_timeline_tool to add it to the timeline."
                ).format(
                    result.get("frames_scanned", 0),
                    object_description,
                    result.get("frames_with_object", 0),
                    result.get("segments_replaced", 0),
                    replacement_description,
                    os.path.basename(output_path),
                )
            else:
                return "Object replacement failed: {}".format(result.get("error", "Unknown error"))
        except Exception as e:
            log.error("replace_object_in_video_tool: %s", e, exc_info=True)
            return "Error: {}".format(e)

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
        generate_transition_clip_tool,
        replace_object_in_video_tool,
    ]
