"""
Manim-related tools for the AI agent: generate educational video code,
render scenes, concatenate with ffmpeg, add to timeline.
"""

import os
import re
import subprocess
import tempfile
from classes.logger import log

try:
    from PyQt5.QtCore import QThread, pyqtSignal, QEventLoop
except ImportError:
    QThread = None
    pyqtSignal = None
    QEventLoop = None


def get_manim_scenes(script_path: str) -> list:
    """
    Parse a Manim Python script and return scene class names.
    Returns a list of strings (e.g. ["Intro", "Theorem"]).
    """
    if not script_path or not os.path.isfile(script_path):
        return []
    try:
        with open(script_path, "r", encoding="utf-8") as f:
            content = f.read()
        # Match "class SceneName(Scene):" or "class SceneName( ... Scene ... ):"
        pattern = r"class\s+(\w+)\s*\([^)]*Scene[^)]*\)"
        return list(dict.fromkeys(re.findall(pattern, content)))
    except Exception as e:
        log.error("get_manim_scenes: %s", e, exc_info=True)
        return []


def render_manim_scene(script_path: str, scene_name: str, quality: str = "l", output_dir: str = None) -> tuple:
    """
    Run manim render for one scene. quality: "l" (low), "m", "h".
    Returns (output_video_path or None, error_string or None).
    """
    if not script_path or not os.path.isfile(script_path):
        return None, "Script file not found: %s" % script_path
    
    # Use python -m manim to ensure we use the venv's manim
    import sys
    cmd = [sys.executable, "-m", "manim", "-q" + quality, script_path, scene_name]
    env = os.environ.copy()
    if output_dir:
        env["MEDIA_DIR"] = output_dir
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding='utf-8',  # Explicitly use UTF-8 to handle Unicode in manim output
            errors='replace',  # Replace decode errors instead of crashing
            timeout=300,
            cwd=os.path.dirname(os.path.abspath(script_path)) or ".",
            env=env,
        )
        if result.returncode != 0:
            return None, (result.stderr or result.stdout or "manim failed")
        
        # Manim CE writes to media/videos/script_name/quality/SceneName.mp4
        base = os.path.dirname(os.path.abspath(script_path))
        script_name = os.path.splitext(os.path.basename(script_path))[0]
        if output_dir:
            search_dir = output_dir
        else:
            search_dir = os.path.join(base, "media", "videos", script_name)
        
        for root, _, files in os.walk(search_dir):
            for f in files:
                if f.endswith(".mp4") and scene_name in f:
                    return os.path.join(root, f), None
        return None, "Rendered video not found for scene %s" % scene_name
    except subprocess.TimeoutExpired:
        return None, "Manim render timed out"
    except FileNotFoundError:
        return None, "manim command not found. Install with: pip install manim"
    except Exception as e:
        log.error("render_manim_scene: %s", e, exc_info=True)
        return None, str(e)


def concatenate_videos_ffmpeg(video_paths: list, output_path: str) -> tuple:
    """
    Concatenate video files with ffmpeg (concat demuxer). Requires a file list.
    Returns (True, None) on success, (False, error_string) on failure.
    """
    if not video_paths or not output_path:
        return False, "No inputs or output path"
    list_dir = os.path.dirname(output_path)
    list_path = os.path.join(list_dir, "concat_list_%s.txt" % os.getpid())
    try:
        with open(list_path, "w", encoding="utf-8") as f:
            for p in video_paths:
                p_abs = os.path.abspath(p)
                f.write("file '%s'\n" % p_abs.replace("'", "'\\''"))
        result = subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_path, "-c", "copy", output_path],
            capture_output=True,
            text=True,
            timeout=600,
        )
        if result.returncode != 0:
            return False, (result.stderr or result.stdout or "ffmpeg failed")
        return True, None
    except subprocess.TimeoutExpired:
        return False, "ffmpeg timed out"
    except FileNotFoundError:
        return False, "ffmpeg not found"
    except Exception as e:
        log.error("concatenate_videos_ffmpeg: %s", e, exc_info=True)
        return False, str(e)
    finally:
        if os.path.isfile(list_path):
            try:
                os.remove(list_path)
            except Exception:
                pass


class _ManimGenerationThread(QThread if QThread else object):
    """
    Worker thread: generates Manim code, renders all scenes, concatenates videos.
    Runs in background to prevent UI freezing.
    """

    if pyqtSignal is not None:
        finished_with_result = pyqtSignal(list, str)  # video_paths_list, error_or_empty
        progress_update = pyqtSignal(str)  # status_message

    def __init__(
        self,
        prompt: str,
        add_as_single_clip: bool,
        model_id: str,
    ):
        if QThread is not None:
            super().__init__()
        self._prompt = prompt
        self._add_as_single_clip = add_as_single_clip
        self._model_id = model_id

    def run(self):
        """Run the entire Manim generation process in background thread."""
        try:
            from classes.ai_llm_registry import get_model
            from langchain_core.messages import HumanMessage, SystemMessage

            # Emit progress
            if pyqtSignal and hasattr(self, "progress_update"):
                self.progress_update.emit("Generating Manim code with AI...")

            # Get LLM
            llm = get_model(self._model_id)
            if not llm:
                raise Exception("No AI model configured. Set API key in Preferences > AI.")

            # Generate Manim code with LLM
            system = (
                "You are a Manim (manim.community) expert. Generate a complete, working Python script.\n\n"
                "Requirements:\n"
                "1. Import: Start with 'from manim import *'\n"
                "2. Define multiple Scene classes (e.g., Intro, MainContent, Conclusion)\n"
                "3. Each class must inherit from Scene and implement construct(self)\n"
                "4. Use only manim community edition API (NOT manim 3b1b)\n"
                "5. Make animations educational and visually clear\n"
                "6. Keep the script self-contained (no external files)\n"
                "7. NO LaTeX dependency: DO NOT use Tex, MathTex, SingleStringMathTex, TexTemplate, or any LaTeX-based mobject.\n"
                "   - Do not use LaTeX commands (e.g. \\\\frac, \\\\Delta) in Tex/MathTex.\n"
                "   - If you need equations, render them using Text() or MarkupText() as plain ASCII/Unicode strings,\n"
                "     or use DecimalNumber()/Integer()/Variable() and arrange with VGroup.\n"
                "   - Prefer simple typography like: Text('a = (v_f - v_i) / t') instead of MathTex.\n"
                "8. Avoid external fonts/assets; use default fonts and built-in Manim primitives only.\n"
                "9. Return ONLY the Python code, no markdown, no explanation, no comments outside the code\n\n"
                "Example structure:\n"
                "```python\n"
                "from manim import *\n\n"
                "class Intro(Scene):\n"
                "    def construct(self):\n"
                "        text = Text('Title')\n"
                "        self.play(Write(text))\n"
                "        self.wait(1)\n"
                "```"
            )

            response = llm.invoke([SystemMessage(content=system), HumanMessage(content=self._prompt)])
            code = getattr(response, "content", None) or str(response)

            # Strip markdown code block if present
            if "```" in code:
                parts = code.split("```")
                for p in parts:
                    if "class " in p and "Scene" in p:
                        code = p.strip()
                        if code.startswith("python"):
                            code = code[6:].strip()
                        break

            def _contains_latex_objects(code_str: str) -> bool:
                # Guard against LaTeX-based Manim objects which require a system LaTeX install.
                banned_tokens = [
                    "MathTex",
                    "SingleStringMathTex",
                    "TexTemplate",
                    "Tex(",   # common constructor usage
                    "Tex)",   # edge cases / formatting
                ]
                return any(tok in code_str for tok in banned_tokens)

            # If the model violated the no-LaTeX requirement, try once more with a stricter instruction.
            if _contains_latex_objects(code):
                if pyqtSignal and hasattr(self, "progress_update"):
                    self.progress_update.emit("Regenerating Manim code (removing LaTeX/Tex/MathTex)...")
                strict = system + (
                    "\n\nCRITICAL FIX:\n"
                    "- Your previous output used LaTeX objects (Tex/MathTex). Rewrite the entire script without them.\n"
                    "- Use ONLY Text/MarkupText/DecimalNumber/Integer/Variable for math.\n"
                    "- If you cannot avoid Tex/MathTex, output a simpler animation that does not need equations.\n"
                )
                response2 = llm.invoke([SystemMessage(content=strict), HumanMessage(content=self._prompt)])
                code2 = getattr(response2, "content", None) or str(response2)
                if "```" in code2:
                    parts = code2.split("```")
                    for p in parts:
                        if "class " in p and "Scene" in p:
                            code2 = p.strip()
                            if code2.startswith("python"):
                                code2 = code2[6:].strip()
                            break
                code = code2
                if _contains_latex_objects(code):
                    raise Exception(
                        "Generated Manim code still uses LaTeX-based objects (Tex/MathTex). "
                        "Please rephrase your request to avoid LaTeX, or install a LaTeX distribution."
                    )

            log.info(f"Generated Manim code ({len(code)} chars)")

            # Write script to temp file
            tmpdir = tempfile.mkdtemp(prefix="flowcut_manim_")
            script_path = os.path.join(tmpdir, "manim_scene.py")
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(code)
            log.info(f"Saved Manim script to: {script_path}")

            # Find scenes
            scenes = get_manim_scenes(script_path)
            if not scenes:
                raise Exception(f"No Scene classes found in generated code.\n\nCode:\n{code[:500]}...")

            log.info(f"Found {len(scenes)} scene(s): {', '.join(scenes)}")

            # Render each scene
            if pyqtSignal and hasattr(self, "progress_update"):
                self.progress_update.emit(f"Rendering {len(scenes)} scene(s)...")

            output_dir = os.path.join(tmpdir, "media")
            os.makedirs(output_dir, exist_ok=True)
            video_paths = []
            errors = []

            for i, scene_name in enumerate(scenes, 1):
                if pyqtSignal and hasattr(self, "progress_update"):
                    self.progress_update.emit(f"Rendering scene {i}/{len(scenes)}: {scene_name}...")

                path, err = render_manim_scene(script_path, scene_name, quality="l", output_dir=output_dir)
                if err:
                    errors.append(f"Scene '{scene_name}': {err}")
                    log.error(f"Manim render failed for {scene_name}: {err}")
                elif path:
                    video_paths.append(path)
                    log.info(f"Successfully rendered scene: {scene_name} -> {path}")

            # Check if any scenes succeeded
            if errors and not video_paths:
                error_msg = "All scenes failed to render:\n" + "\n".join(errors)
                raise Exception(error_msg)
            elif errors:
                log.warning(f"Some scenes failed: {errors}, but {len(video_paths)} succeeded")

            if not video_paths:
                raise Exception("No videos were rendered.")

            # Concatenate if requested
            if self._add_as_single_clip and len(video_paths) > 1:
                if pyqtSignal and hasattr(self, "progress_update"):
                    self.progress_update.emit("Combining scenes...")

                combined_path = os.path.join(tmpdir, "combined.mp4")
                ok, err = concatenate_videos_ffmpeg(video_paths, combined_path)
                if not ok:
                    raise Exception(f"Error concatenating: {err}")
                paths_to_return = [combined_path]
            else:
                paths_to_return = video_paths

            # Success!
            if pyqtSignal and hasattr(self, "finished_with_result"):
                self.finished_with_result.emit(paths_to_return, "")

        except Exception as e:
            log.error("Manim generation failed: %s", e, exc_info=True)
            if pyqtSignal and hasattr(self, "finished_with_result"):
                self.finished_with_result.emit([], str(e))


def generate_manim_video_and_add_to_timeline(
    prompt: str,
    add_as_single_clip: bool = True,
    model_id: str = None,
) -> str:
    """
    Generate Manim Python code from the prompt (via LLM), render scenes,
    concatenate, and add to project. If add_as_single_clip is False, add each scene as a separate clip.

    This function runs in a BACKGROUND THREAD to prevent UI freezing.

    Returns a human-readable result string.
    """
    from classes.app import get_app
    from classes.ai_llm_registry import get_default_model_id
    import shutil

    # Check if manim is installed - try importing first (works in venv), then check PATH
    manim_available = False
    
    # Try importing manim (best method for venv)
    try:
        import manim as _manim_test
        manim_available = True
    except ImportError:
        # Fall back to shutil.which for system install
        manim_available = shutil.which("manim") is not None
    
    if not manim_available:
        return (
            "Error: Manim is not installed. Please install it first:\n"
            "pip install manim\n\n"
            "For more info: https://docs.manim.community/"
        )

    app = get_app()
    mid = model_id or get_default_model_id()

    # Result holder for thread callback
    result_holder = [None, None]  # [video_paths, error]
    loop_holder = [None]

    class ResultReceiver:
        def on_done(self, paths, error):
            result_holder[0] = paths
            result_holder[1] = error
            if loop_holder[0]:
                loop_holder[0].quit()

    receiver = ResultReceiver()

    # Create and start background thread
    thread = _ManimGenerationThread(
        prompt=prompt,
        add_as_single_clip=add_as_single_clip,
        model_id=mid,
    )
    thread.finished_with_result.connect(receiver.on_done)

    # Show progress updates in status bar
    status_bar = getattr(app.window, "statusBar", None)

    def on_progress(msg):
        if status_bar:
            status_bar.showMessage(msg, 0)

    if hasattr(thread, "progress_update"):
        thread.progress_update.connect(on_progress)

    # Run thread with event loop (non-blocking for Qt)
    loop_holder[0] = QEventLoop(app)
    try:
        if status_bar:
            status_bar.showMessage("Starting Manim generation...", 0)
        thread.start()
        loop_holder[0].exec_()  # This keeps Qt responsive while thread runs
    finally:
        if status_bar:
            status_bar.clearMessage()

    # Wait for thread to finish
    thread.quit()
    thread.wait(10000)

    # Disconnect signals
    try:
        thread.finished_with_result.disconnect(receiver.on_done)
        if hasattr(thread, "progress_update"):
            thread.progress_update.disconnect(on_progress)
    except Exception:
        pass

    # Check results
    video_paths, error = result_holder[0], result_holder[1]
    if error:
        log.error("Manim generation error: %s", error)
        return f"Error: {error}"

    if not video_paths:
        return "Error: No videos were generated."

    # Now add files to project (this runs on main thread)
    try:
        log.info(f"Adding {len(video_paths)} video(s) to project...")
        app.window.files_model.add_files(video_paths)
    except Exception as e:
        log.error("add_files failed: %s", e, exc_info=True)
        return "Error adding to project: %s" % e

    # Add clips to timeline
    from classes.query import File
    from classes.ai_openshot_tools import add_clip_to_timeline

    clips_added = 0
    for path in video_paths:
        path_norm = os.path.normpath(path)
        f = File.get(path=path) or File.get(path=path_norm)
        if not f:
            for c in File.filter():
                if getattr(c, "absolute_path", None) and c.absolute_path() == path:
                    f = c
                    break
        if f:
            add_clip_to_timeline(file_id=str(f.id), position_seconds=None, track=None)
            clips_added += 1

    if clips_added == 0:
        return "Videos generated but could not be added to timeline."

    return f"✅ Successfully rendered and added {clips_added} Manim clip(s) to the timeline!"


def get_manim_tools_for_langchain():
    """Return a list of LangChain Tool objects for the Manim agent."""
    from langchain_core.tools import tool

    @tool
    def get_manim_scenes_tool(script_path: str) -> str:
        """Parse a Manim Python script and return the list of scene class names. Argument: script_path (full path to .py file)."""
        scenes = get_manim_scenes(script_path)
        if not scenes:
            return "No Scene classes found in %s" % script_path
        return "Scenes: " + ", ".join(scenes)

    @tool
    def generate_manim_video_tool(
        prompt: str,
        add_as_single_clip: bool = True,
    ) -> str:
        """
        Generate and render a Manim educational animation video, then add it to the timeline.

        This tool does EVERYTHING automatically:
        - Generates Manim Python code from your description
        - Renders all scenes with manim
        - Combines or separates scenes as requested
        - Adds the video(s) to the project timeline

        Args:
            prompt: Detailed description of the animation (e.g., "Explain the second law of thermodynamics with entropy diagrams")
            add_as_single_clip: If True (default), combine all scenes into one clip. If False, add each scene as separate clips.

        Returns:
            Success message with number of clips added to timeline.
        """
        return generate_manim_video_and_add_to_timeline(
            prompt=prompt,
            add_as_single_clip=add_as_single_clip,
        )

    return [get_manim_scenes_tool, generate_manim_video_tool]
