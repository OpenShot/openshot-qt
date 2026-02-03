"""
OpenShot tools for the LangChain agent. All tools assume they are run on the Qt main thread
(dispatched by the agent runner). They call get_app().project, get_app().updates, get_app().window.
"""

import json
from classes.logger import log


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
    ]
