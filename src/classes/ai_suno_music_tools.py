"""
Suno music tools for Flowcut agents.

These tools are designed to be run on the Qt main thread (like ai_openshot_tools),
but they offload network + download work to a QThread.
"""

from __future__ import annotations

import os
import uuid as uuid_module

from classes.logger import log

try:
    from PyQt5.QtCore import QObject, QThread, pyqtSignal, QEventLoop
except ImportError:
    QObject = object
    QThread = None
    pyqtSignal = None
    QEventLoop = None


def _get_app():
    """Get app; must be called from main thread."""
    from classes.app import get_app

    return get_app()


def _output_path_for_generated_music(ext: str = ".mp3") -> str:
    """Return an absolute path for saving a generated audio file. Call from main thread."""
    ext = ext if ext.startswith(".") else f".{ext}"
    app = _get_app()
    project_path = getattr(app.project, "current_filepath", None) or ""
    if project_path and os.path.isabs(project_path):
        base_dir = os.path.dirname(project_path)
        out_dir = os.path.join(base_dir, "Generated")
        try:
            os.makedirs(out_dir, exist_ok=True)
            return os.path.join(out_dir, f"generated_music_{uuid_module.uuid4().hex[:12]}{ext}")
        except OSError:
            pass
    import tempfile

    return os.path.join(tempfile.gettempdir(), f"flowcut_generated_music_{uuid_module.uuid4().hex[:12]}{ext}")


def _try_get_file_id_for_path(path: str):
    """Try to resolve a File id after adding a path to the files model."""
    from classes.query import File

    f = File.get(path=path)
    if not f:
        f = File.get(path=os.path.normpath(path))
    if not f:
        for candidate in File.filter():
            if getattr(candidate, "absolute_path", None) and candidate.absolute_path() == path:
                f = candidate
                break
    return getattr(f, "id", None)


class _MusicGenerationThread(QThread if QThread else object):
    """Worker thread: calls Suno API, waits for completion, downloads MP3."""

    if pyqtSignal is not None:
        finished_with_result = pyqtSignal(str, str)  # path_or_empty, error_or_empty

    def __init__(
        self,
        token: str,
        base_url: str,
        topic: str,
        tags: str,
        negative_tags: str,
        prompt: str,
        make_instrumental,
        cover_clip_id: str,
        output_path: str,
        timeout_seconds: float,
        poll_seconds: float,
    ):
        if QThread is not None:
            super().__init__()
        self._token = token
        self._base_url = base_url
        self._topic = topic
        self._tags = tags
        self._negative_tags = negative_tags
        self._prompt = prompt
        self._make_instrumental = make_instrumental
        self._cover_clip_id = cover_clip_id
        self._output_path = output_path
        self._timeout_seconds = timeout_seconds
        self._poll_seconds = poll_seconds

    def run(self):
        from classes.music_generation.suno_client import SunoError, generate_wait_download_mp3

        try:
            generate_wait_download_mp3(
                token=self._token,
                base_url=self._base_url,
                topic=self._topic,
                tags=self._tags,
                negative_tags=self._negative_tags,
                prompt=self._prompt,
                make_instrumental=self._make_instrumental,
                cover_clip_id=self._cover_clip_id,
                timeout_seconds=self._timeout_seconds,
                poll_seconds=self._poll_seconds,
                dest_path=self._output_path,
            )
            if pyqtSignal is not None and hasattr(self, "finished_with_result"):
                self.finished_with_result.emit(self._output_path, "")
        except SunoError as exc:
            if pyqtSignal is not None and hasattr(self, "finished_with_result"):
                self.finished_with_result.emit("", str(exc))
        except Exception as exc:
            log.error("Suno music generation failed: %s", exc, exc_info=True)
            if pyqtSignal is not None and hasattr(self, "finished_with_result"):
                self.finished_with_result.emit("", str(exc))


def generate_music_and_add_to_timeline(
    *,
    topic: str = "",
    tags: str = "",
    negative_tags: str = "",
    prompt: str = "",
    make_instrumental: str = "",
    cover_clip_id: str = "",
    position_seconds: str = "",
    timeout_seconds: str = "240",
    poll_seconds: str = "5",
) -> str:
    """
    Generate music via Suno, download MP3, import into project, add to a new track.

    - If position_seconds is empty: try playhead; if that fails, fall back to 0.
    - If position_seconds provided: use that; if it fails, fall back to 0.

    make_instrumental is passed as:
    - "" (empty) => leave unset (Suno default)
    - "true"/"false" => explicit boolean
    """
    if QThread is None or QEventLoop is None:
        return "Error: Music generation requires PyQt5."

    app = _get_app()
    settings = app.get_settings()

    token = (settings.get("suno-treehacks-token") or "").strip()
    if not token:
        return "Suno is not configured. Add your Suno TreeHacks token in Preferences > AI (Suno TreeHacks Token)."

    base_url = (settings.get("suno-hackathons-base-url") or "").strip() or "https://studio-api.prod.suno.com/api/v2/external/hackathons/"

    log.info("Suno music generation: token length=%d, base_url=%s", len(token), base_url)

    # Parse booleans/nums from strings (LangChain tools pass strings often)
    mi = (make_instrumental or "").strip().lower()
    make_inst_val = None
    if mi in ("true", "1", "yes", "y", "on"):
        make_inst_val = True
    elif mi in ("false", "0", "no", "n", "off"):
        make_inst_val = False

    try:
        timeout_f = float(timeout_seconds) if str(timeout_seconds).strip() else 240.0
    except Exception:
        timeout_f = 240.0
    try:
        poll_f = float(poll_seconds) if str(poll_seconds).strip() else 5.0
    except Exception:
        poll_f = 5.0

    output_path = _output_path_for_generated_music(".mp3")

    # If we need to create a new track, capture layer list before/after.
    layers_before = list(app.project.get("layers") or [])
    layer_nums_before = {int(L.get("number")) for L in layers_before if isinstance(L, dict) and str(L.get("number", "")).isdigit()}

    result_holder = [None, None]  # [path, error]
    loop_holder = [None]

    class _DoneReceiver(QObject if QObject is not object else object):
        def on_done(self, path, error):
            result_holder[0] = path
            result_holder[1] = error
            if loop_holder[0]:
                loop_holder[0].quit()

    receiver = _DoneReceiver()
    thread = _MusicGenerationThread(
        token=token,
        base_url=base_url,
        topic=topic or "",
        tags=tags or "",
        negative_tags=negative_tags or "",
        prompt=prompt or "",
        make_instrumental=make_inst_val,
        cover_clip_id=cover_clip_id or "",
        output_path=output_path,
        timeout_seconds=timeout_f,
        poll_seconds=poll_f,
    )
    thread.finished_with_result.connect(receiver.on_done)

    loop_holder[0] = QEventLoop(app)
    status_bar = getattr(app.window, "statusBar", None)
    try:
        if status_bar is not None:
            status_bar.showMessage("Generating music...", 0)
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
        log.error("Suno music generation error: %s", error)
        return f"Error generating music: {error}"
    if not path or not os.path.isfile(path):
        return "Error: Generated music file not found."

    # Import the MP3 into project files
    try:
        app.window.files_model.add_files([path])
    except Exception as exc:
        log.error("Failed to import generated MP3: %s", exc, exc_info=True)
        return f"Error: Music was downloaded but could not be added to the project: {exc}"

    file_id = _try_get_file_id_for_path(path)
    if not file_id:
        return "Error: Music was downloaded but could not be resolved as a project file."

    # Try to create a new track (graceful: continue if it fails)
    new_track_num = ""
    try:
        # Ensure at least one track is selected so actionAddTrackBelow works
        if not getattr(app.window, "selected_tracks", None):
            # No selection: select first track if available
            layers = list(app.project.get("layers") or [])
            if layers:
                first_layer_num = layers[0].get("number")
                if first_layer_num is not None:
                    app.window.selected_tracks = [first_layer_num]
        
        app.window.actionAddTrackBelow_trigger()
        
        # Identify the new track
        layers_after = list(app.project.get("layers") or [])
        layer_nums_after = {int(L.get("number")) for L in layers_after if isinstance(L, dict) and str(L.get("number", "")).isdigit()}
        new_layers = sorted(layer_nums_after - layer_nums_before)
        if new_layers:
            new_track_num = str(new_layers[-1])
    except Exception as exc:
        log.warning("Could not create new track (will use existing): %s", exc)
        # Continue anyway; we'll add to whatever is selected/first track.

    # Add clip to timeline (prefer requested position; else playhead)
    from classes.ai_openshot_tools import add_clip_to_timeline

    desired_pos = (position_seconds or "").strip()
    msg = add_clip_to_timeline(file_id=str(file_id), position_seconds=desired_pos, track=new_track_num)
    if isinstance(msg, str) and msg.startswith("Error:"):
        # Fallback: 0s on the same track
        msg2 = add_clip_to_timeline(file_id=str(file_id), position_seconds="0", track=new_track_num)
        if isinstance(msg2, str) and not msg2.startswith("Error:"):
            return msg2
        return msg

    return msg


def test_suno_token() -> str:
    """Test if the Suno token is configured and valid by checking settings."""
    app = _get_app()
    settings = app.get_settings()

    token = (settings.get("suno-treehacks-token") or "").strip()
    base_url = (settings.get("suno-hackathons-base-url") or "").strip() or "https://studio-api.prod.suno.com/api/v2/external/hackathons/"

    if not token:
        return "Suno token is NOT configured. Please add your Suno TreeHacks token in Preferences > AI (Suno TreeHacks Token)."

    # Quick validation: token should be a hex string
    if len(token) < 20:
        return f"Suno token looks invalid (too short: {len(token)} chars). Please check your token in Preferences > AI."

    return f"Suno token is configured (length: {len(token)} chars, base URL: {base_url}). Ready to generate music!"


def get_suno_music_tools_for_langchain():
    """Return a list of LangChain Tool objects for Suno music generation."""
    from langchain_core.tools import tool

    @tool
    def test_suno_token_tool() -> str:
        """Check if Suno is configured and the token is set. Use this first if music generation fails."""
        return test_suno_token()

    @tool
    def generate_music_and_add_to_timeline_tool(
        topic: str = "",
        tags: str = "",
        negative_tags: str = "",
        prompt: str = "",
        make_instrumental: str = "",
        cover_clip_id: str = "",
        position_seconds: str = "",
        timeout_seconds: str = "240",
        poll_seconds: str = "5",
    ) -> str:
        """
        Generate background music via Suno, download MP3, import into project, and add to timeline.

        - Provide either topic+tags (simple mode) or prompt+tags (custom lyrics mode).
        - position_seconds: empty uses playhead; otherwise a number (seconds). Fallback is 0.
        - make_instrumental: \"true\"/\"false\" to force, or empty to leave default.
        """
        return generate_music_and_add_to_timeline(
            topic=topic,
            tags=tags,
            negative_tags=negative_tags,
            prompt=prompt,
            make_instrumental=make_instrumental,
            cover_clip_id=cover_clip_id,
            position_seconds=position_seconds,
            timeout_seconds=timeout_seconds,
            poll_seconds=poll_seconds,
        )

    return [test_suno_token_tool, generate_music_and_add_to_timeline_tool]

