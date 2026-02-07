"""
Manim-related tools for the AI agent: generate educational video code,
render scenes, concatenate with ffmpeg, add to timeline.
"""

import os
import re
import subprocess
import tempfile
from classes.logger import log


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
    cmd = ["manim", "-q" + quality, script_path, scene_name]
    env = os.environ.copy()
    if output_dir:
        env["MEDIA_DIR"] = output_dir
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
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


def generate_manim_video_and_add_to_timeline(
    prompt: str,
    add_as_single_clip: bool = True,
    model_id: str = None,
) -> str:
    """
    Generate Manim Python code from the prompt (via LLM), render scenes,
    concatenate, and add to project. If add_as_single_clip is False, add each scene as a separate clip.
    Returns a human-readable result string.
    """
    from classes.app import get_app
    from classes.ai_llm_registry import get_model, get_default_model_id

    app = get_app()
    mid = model_id or get_default_model_id()
    llm = get_model(mid) if mid else None
    if not llm:
        return "Error: No AI model configured. Set API key in Preferences > AI."

    # Generate Manim code with LLM
    system = (
        "You are a Manim (manim.community) expert. Generate a single Python script that defines "
        "multiple Scene classes. Each class must inherit from Scene and implement construct(). "
        "Use only manim community API (e.g. from manim import *). Keep the script self-contained. "
        "Return only the Python code, no markdown or explanation."
    )
    try:
        from langchain_core.messages import HumanMessage, SystemMessage
        response = llm.invoke([SystemMessage(content=system), HumanMessage(content=prompt)])
        code = getattr(response, "content", None) or str(response)
    except Exception as e:
        log.error("Manim code generation failed: %s", e, exc_info=True)
        return "Error: Failed to generate Manim code: %s" % e

    # Strip markdown code block if present
    if "```" in code:
        parts = code.split("```")
        for p in parts:
            if "class " in p and "Scene" in p:
                code = p.strip()
                if code.startswith("python"):
                    code = code[6:].strip()
                break

    tmpdir = tempfile.mkdtemp(prefix="zenvi_manim_")
    script_path = os.path.join(tmpdir, "manim_scene.py")
    try:
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(code)
    except Exception as e:
        return "Error: Could not write script: %s" % e

    scenes = get_manim_scenes(script_path)
    if not scenes:
        return "Error: No Scene classes found in generated code."

    output_dir = os.path.join(tmpdir, "media")
    os.makedirs(output_dir, exist_ok=True)
    video_paths = []
    for scene_name in scenes:
        path, err = render_manim_scene(script_path, scene_name, quality="l", output_dir=output_dir)
        if err:
            return "Error rendering %s: %s" % (scene_name, err)
        if path:
            video_paths.append(path)

    if not video_paths:
        return "Error: No videos were rendered."

    if add_as_single_clip and len(video_paths) > 1:
        combined_path = os.path.join(tmpdir, "combined.mp4")
        ok, err = concatenate_videos_ffmpeg(video_paths, combined_path)
        if not ok:
            return "Error concatenating: %s" % err
        paths_to_add = [combined_path]
    else:
        paths_to_add = video_paths

    try:
        app.window.files_model.add_files(paths_to_add)
    except Exception as e:
        log.error("add_files failed: %s", e, exc_info=True)
        return "Error adding to project: %s" % e

    from classes.query import File
    from classes.ai_openshot_tools import add_clip_to_timeline

    for path in paths_to_add:
        path_norm = os.path.normpath(path)
        f = File.get(path=path) or File.get(path=path_norm)
        if not f:
            for c in File.filter():
                if getattr(c, "absolute_path", None) and c.absolute_path() == path:
                    f = c
                    break
        if f:
            add_clip_to_timeline(file_id=str(f.id), position_seconds=None, track=None)

    return "Added %d clip(s) to the timeline." % len(paths_to_add)


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
        """Generate an educational/manim video from a text prompt. The AI generates Manim code, renders it, and adds the result to the timeline. prompt: describe the video (e.g. 'Pythagoras theorem'). add_as_single_clip: if True, combine all scenes into one clip; if False, add each scene as a separate clip."""
        return generate_manim_video_and_add_to_timeline(
            prompt=prompt,
            add_as_single_clip=add_as_single_clip,
        )

    return [get_manim_scenes_tool, generate_manim_video_tool]
