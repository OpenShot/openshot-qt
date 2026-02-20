"""
TTS (text-to-speech) tools for Flowcut agents.

These tools are designed to be run on the Qt main thread (like ai_openshot_tools),
but they offload network work to a QThread.
"""

from __future__ import annotations

import os
import tempfile
import uuid as uuid_module
from concurrent.futures import ThreadPoolExecutor, as_completed

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


def _output_path_for_generated_audio(ext: str = ".mp3") -> str:
    """Return an absolute path for saving a generated audio file. Call from main thread."""
    ext = ext if ext.startswith(".") else f".{ext}"
    app = _get_app()
    project_path = getattr(app.project, "current_filepath", None) or ""
    if project_path and os.path.isabs(project_path):
        base_dir = os.path.dirname(project_path)
        out_dir = os.path.join(base_dir, "Generated")
        try:
            os.makedirs(out_dir, exist_ok=True)
            return os.path.join(out_dir, f"generated_tts_{uuid_module.uuid4().hex[:12]}{ext}")
        except OSError:
            pass

    return os.path.join(tempfile.gettempdir(), f"flowcut_generated_tts_{uuid_module.uuid4().hex[:12]}{ext}")


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


class _TTSGenerationThread(QThread if QThread else object):
    """Worker thread: calls OpenAI TTS API, handles chunking, concatenates audio."""

    if pyqtSignal is not None:
        finished_with_result = pyqtSignal(str, str)  # path_or_empty, error_or_empty
        progress_update = pyqtSignal(str)  # status_message

    def __init__(
        self,
        api_key: str,
        text: str,
        voice: str,
        model: str,
        speed: float,
        output_path: str,
        timeout_seconds: float,
    ):
        if QThread is not None:
            super().__init__()
        self._api_key = api_key
        self._text = text
        self._voice = voice
        self._model = model
        self._speed = speed
        self._output_path = output_path
        self._timeout_seconds = timeout_seconds

    def run(self):
        from classes.tts_generation.openai_tts_client import (
            TTSError,
            chunk_text_for_tts,
            concatenate_audio_ffmpeg,
            openai_tts_generate,
        )

        try:
            # Emit initial progress
            if hasattr(self, "progress_update"):
                self.progress_update.emit("Preparing text for speech generation...")

            # Check if we need to chunk the text
            chunks = chunk_text_for_tts(self._text, max_chars=3500)  # Buffer below 4096 limit

            if len(chunks) == 1:
                # Single chunk - generate directly
                if hasattr(self, "progress_update"):
                    self.progress_update.emit("Generating speech...")

                openai_tts_generate(
                    api_key=self._api_key,
                    text=chunks[0],
                    voice=self._voice,
                    model=self._model,
                    speed=self._speed,
                    output_path=self._output_path,
                    timeout_seconds=self._timeout_seconds,
                )

                if pyqtSignal is not None and hasattr(self, "finished_with_result"):
                    self.finished_with_result.emit(self._output_path, "")

            else:
                # Multiple chunks - generate in parallel and concatenate
                if hasattr(self, "progress_update"):
                    self.progress_update.emit(f"Generating speech in {len(chunks)} chunks...")

                # Create temp directory for chunks
                temp_dir = tempfile.mkdtemp(prefix="flowcut_tts_")
                chunk_paths = []

                try:
                    # Define function for parallel execution
                    def generate_chunk(chunk_data):
                        chunk_text, chunk_index = chunk_data
                        chunk_path = os.path.join(temp_dir, f"chunk_{chunk_index:04d}.mp3")

                        openai_tts_generate(
                            api_key=self._api_key,
                            text=chunk_text,
                            voice=self._voice,
                            model=self._model,
                            speed=self._speed,
                            output_path=chunk_path,
                            timeout_seconds=self._timeout_seconds,
                        )

                        return chunk_index, chunk_path

                    # Generate chunks in parallel (max 3 workers to respect rate limits)
                    with ThreadPoolExecutor(max_workers=3) as executor:
                        futures = []
                        for i, chunk in enumerate(chunks):
                            futures.append(executor.submit(generate_chunk, (chunk, i)))

                        # Wait for all chunks to complete
                        completed_chunks = {}
                        for future in as_completed(futures):
                            chunk_idx, chunk_path = future.result()
                            completed_chunks[chunk_idx] = chunk_path

                            if hasattr(self, "progress_update"):
                                self.progress_update.emit(
                                    f"Generated chunk {len(completed_chunks)}/{len(chunks)}..."
                                )

                    # Sort chunks by index
                    chunk_paths = [completed_chunks[i] for i in sorted(completed_chunks.keys())]

                    # Concatenate all chunks
                    if hasattr(self, "progress_update"):
                        self.progress_update.emit("Combining audio chunks...")

                    success, error = concatenate_audio_ffmpeg(chunk_paths, self._output_path)

                    if not success:
                        raise TTSError(f"Failed to concatenate audio chunks: {error}")

                    if pyqtSignal is not None and hasattr(self, "finished_with_result"):
                        self.finished_with_result.emit(self._output_path, "")

                finally:
                    # Clean up temp files
                    for chunk_path in chunk_paths:
                        try:
                            if os.path.isfile(chunk_path):
                                os.remove(chunk_path)
                        except Exception:
                            pass

                    try:
                        if os.path.isdir(temp_dir):
                            os.rmdir(temp_dir)
                    except Exception:
                        pass

        except TTSError as exc:
            log.error("TTS generation failed: %s", exc)
            if pyqtSignal is not None and hasattr(self, "finished_with_result"):
                self.finished_with_result.emit("", str(exc))
        except Exception as exc:
            log.error("TTS generation failed: %s", exc, exc_info=True)
            if pyqtSignal is not None and hasattr(self, "finished_with_result"):
                self.finished_with_result.emit("", str(exc))


def generate_tts_and_add_to_timeline(
    *,
    text: str,
    voice: str = "",
    speed: str = "",
    model: str = "",
    position_seconds: str = "",
    track: str = "",
) -> str:
    """
    Generate TTS audio, download MP3, import into project, add to a new track.

    Args:
        text: Text to convert to speech (required)
        voice: One of: alloy, echo, fable, onyx, nova, shimmer (default from settings)
        speed: 0.25 to 4.0 (default from settings)
        model: tts-1 or tts-1-hd (default from settings)
        position_seconds: Timeline position (empty = playhead, 0 = start)
        track: Track number (empty = create new track)

    Returns:
        Success message or error string
    """
    if QThread is None or QEventLoop is None:
        return "Error: TTS generation requires PyQt5."

    app = _get_app()
    settings = app.get_settings()

    # Get API key
    api_key = (settings.get("openai-api-key") or "").strip()
    if not api_key:
        return "OpenAI API key is NOT configured. Please add your OpenAI API key in Preferences > AI (OpenAI API Key)."

    # Validate text
    text_cleaned = (text or "").strip()
    if not text_cleaned:
        return "Error: Text is required for TTS generation."

    # Get voice (use setting as default)
    voice_val = (voice or "").strip().lower()
    if not voice_val:
        voice_val = (settings.get("openai-tts-voice") or "alloy").strip().lower()

    # Get model (use setting as default)
    model_val = (model or "").strip().lower()
    if not model_val:
        model_val = (settings.get("openai-tts-model") or "tts-1").strip().lower()

    # Get speed (use setting as default)
    speed_val = 1.0
    if (speed or "").strip():
        try:
            speed_val = float(speed)
        except Exception:
            speed_val = 1.0
    else:
        try:
            speed_val = float(settings.get("openai-tts-speed") or 1.0)
        except Exception:
            speed_val = 1.0

    log.info("TTS generation: text_length=%d, voice=%s, model=%s, speed=%s", len(text_cleaned), voice_val, model_val, speed_val)

    output_path = _output_path_for_generated_audio(".mp3")

    # If we need to create a new track, capture layer list before/after
    layers_before = list(app.project.get("layers") or [])
    layer_nums_before = {
        int(L.get("number")) for L in layers_before if isinstance(L, dict) and str(L.get("number", "")).isdigit()
    }

    result_holder = [None, None]  # [path, error]
    loop_holder = [None]

    class _DoneReceiver(QObject if QObject is not object else object):
        def on_done(self, path, error):
            result_holder[0] = path
            result_holder[1] = error
            if loop_holder[0]:
                loop_holder[0].quit()

        def on_progress(self, message):
            status_bar = getattr(app.window, "statusBar", None)
            if status_bar is not None:
                status_bar.showMessage(message, 0)

    receiver = _DoneReceiver()
    thread = _TTSGenerationThread(
        api_key=api_key,
        text=text_cleaned,
        voice=voice_val,
        model=model_val,
        speed=speed_val,
        output_path=output_path,
        timeout_seconds=60.0,
    )
    thread.finished_with_result.connect(receiver.on_done)
    if hasattr(thread, "progress_update"):
        thread.progress_update.connect(receiver.on_progress)

    loop_holder[0] = QEventLoop(app)
    status_bar = getattr(app.window, "statusBar", None)
    try:
        if status_bar is not None:
            status_bar.showMessage("Generating speech...", 0)
        thread.start()
        loop_holder[0].exec_()
    finally:
        if status_bar is not None:
            status_bar.clearMessage()

    thread.quit()
    thread.wait(10000)
    try:
        thread.finished_with_result.disconnect(receiver.on_done)
        if hasattr(thread, "progress_update"):
            thread.progress_update.disconnect(receiver.on_progress)
    except Exception:
        pass

    path, error = result_holder[0], result_holder[1]
    if error:
        log.error("TTS generation error: %s", error)
        return f"Error generating speech: {error}"
    if not path or not os.path.isfile(path):
        return "Error: Generated audio file not found."

    # Import the MP3 into project files
    try:
        app.window.files_model.add_files([path])
    except Exception as exc:
        log.error("Failed to import generated MP3: %s", exc, exc_info=True)
        return f"Error: Audio was generated but could not be added to the project: {exc}"

    file_id = _try_get_file_id_for_path(path)
    if not file_id:
        return "Error: Audio was generated but could not be resolved as a project file."

    # Try to create a new track (graceful: continue if it fails)
    new_track_num = (track or "").strip()
    if not new_track_num:
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
            layer_nums_after = {
                int(L.get("number")) for L in layers_after if isinstance(L, dict) and str(L.get("number", "")).isdigit()
            }
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


def test_openai_tts_api_key() -> str:
    """Test if the OpenAI API key is configured by checking settings."""
    app = _get_app()
    settings = app.get_settings()

    api_key = (settings.get("openai-api-key") or "").strip()

    if not api_key:
        return "OpenAI API key is NOT configured. Please add your OpenAI API key in Preferences > AI (OpenAI API Key)."

    if not api_key.startswith("sk-"):
        return f"OpenAI API key format looks invalid (should start with 'sk-'). Please check your key in Preferences > AI."

    return f"OpenAI API key is configured (length: {len(api_key)} chars). Ready for TTS!"


def get_tts_tools_for_langchain():
    """Return a list of LangChain Tool objects for TTS generation."""
    from langchain_core.tools import tool

    @tool
    def test_openai_tts_api_key_tool() -> str:
        """Check if OpenAI TTS is configured and the API key is set. Use this first if TTS generation fails."""
        return test_openai_tts_api_key()

    @tool
    def generate_tts_and_add_to_timeline_tool(
        text: str,
        voice: str = "",
        speed: str = "",
        model: str = "",
        position_seconds: str = "",
    ) -> str:
        """
        Generate text-to-speech narration and add to timeline.

        Use this when user asks for: narration, voice over, TTS, spoken audio, or "add voice".

        Args:
            text: Script to convert to speech (required). Can be any length - long scripts are automatically chunked.
            voice: Voice to use. Options: alloy (neutral), echo (male), fable (expressive), onyx (deep male), nova (female), shimmer (soft female). Leave empty to use default from settings.
            speed: Speech speed from 0.25 to 4.0. Default is 1.0 (normal). Leave empty to use setting.
            model: TTS model. Options: tts-1 (fast), tts-1-hd (high quality). Leave empty to use setting.
            position_seconds: Timeline position in seconds. Leave empty to use playhead position.

        Returns:
            Success message with clip details, or error message starting with "Error:"
        """
        return generate_tts_and_add_to_timeline(
            text=text,
            voice=voice,
            speed=speed,
            model=model,
            position_seconds=position_seconds,
        )

    return [test_openai_tts_api_key_tool, generate_tts_and_add_to_timeline_tool]
