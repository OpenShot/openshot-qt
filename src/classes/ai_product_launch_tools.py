"""
Product Launch Video Generation Tools.

Integrates GitHub data extraction with Remotion (primary) and Manim (fallback)
scene generation to create compelling product launch videos.

This module is designed for use with the Product Launch Agent.
"""

from __future__ import annotations

import json
import os
import tempfile
from typing import Dict, Any, List

from classes.logger import log
from classes.github_client import get_repo_data_from_url, GitHubError, parse_github_url
from classes.ai_manim_tools import render_manim_scene, concatenate_videos_ffmpeg, get_manim_scenes


def generate_product_launch_manim_code(repo_data: Dict[str, Any]) -> str:
    """
    Generate Manim Python code for a product launch video.

    Args:
        repo_data: Dictionary containing:
            - repo_info: GitHub repo metadata (name, stars, description, etc.)
            - readme: README content
            - owner: Repo owner
            - repo: Repo name

    Returns:
        Complete Manim Python code with multiple scenes
    """
    repo_info = repo_data.get("repo_info", {})
    readme = repo_data.get("readme", "")
    owner = repo_data.get("owner", "")
    repo = repo_data.get("repo", "")

    # Extract key information
    name = repo_info.get("name", repo)
    description = repo_info.get("description", "")
    stars = repo_info.get("stargazers_count", 0)
    forks = repo_info.get("forks_count", 0)
    watchers = repo_info.get("watchers_count", 0)
    language = repo_info.get("language", "")
    topics = repo_info.get("topics", [])
    homepage = repo_info.get("homepage", "")

    # Format stats
    def format_number(num):
        if num >= 1000000:
            return f"{num/1000000:.1f}M"
        elif num >= 1000:
            return f"{num/1000:.1f}K"
        return str(num)

    stars_str = format_number(stars)
    forks_str = format_number(forks)

    # Extract key features from README (simple extraction)
    features = []
    if readme:
        lines = readme.split('\n')
        for line in lines[:50]:  # Only look at first 50 lines
            # Look for bullet points or numbered lists
            stripped = line.strip()
            if stripped.startswith(('- ', '* ', '+ ')) and len(stripped) > 5 and len(stripped) < 100:
                feature = stripped[2:].strip()
                if feature and not feature.lower().startswith(('http', 'see ', 'read ', '[', '!')):
                    features.append(feature)
                    if len(features) >= 3:
                        break

    # Truncate description if too long
    if len(description) > 80:
        description = description[:77] + "..."

    # Escape strings for Python code - robust handling of all control characters
    def escape_str(s):
        """Escape string for safe embedding in Python code."""
        if not s:
            return ""
        # Replace backslash first (order matters!)
        s = s.replace('\\', '\\\\')
        # Replace quotes
        s = s.replace('"', '\\"')
        s = s.replace("'", "\\'")
        # Replace common control characters
        s = s.replace('\n', '\\n')
        s = s.replace('\r', '\\r')
        s = s.replace('\t', '\\t')
        s = s.replace('\b', '\\b')
        s = s.replace('\f', '\\f')
        # Remove or replace other control characters (0x00-0x1F, 0x7F)
        import re
        s = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', s)
        # Limit length to prevent extremely long strings
        if len(s) > 200:
            s = s[:197] + "..."
        return s

    name_esc = escape_str(name)
    desc_esc = escape_str(description)
    features_esc = [escape_str(f) for f in features[:3]]  # Max 3 features

    # Generate Manim code - OPTIMIZED for faster rendering
    code = f'''from manim import *

class IntroScene(Scene):
    """Animated introduction with repo name and description."""
    def construct(self):
        # Title
        title = Text("{name_esc}", font_size=60, weight=BOLD)
        title.set_color(BLUE)

        # Description
        desc = Text("{desc_esc}", font_size=28)
        desc.next_to(title, DOWN, buff=0.5)
        desc.set_color(GRAY)

        # GitHub URL
        github_text = Text("github.com/{escape_str(owner)}/{escape_str(repo)}", font_size=22)
        github_text.next_to(desc, DOWN, buff=0.6)
        github_text.set_color(GREEN)

        # FAST animations - reduced run_time for speed
        self.play(FadeIn(title), run_time=0.5)
        self.play(FadeIn(desc), run_time=0.4)
        self.play(FadeIn(github_text), run_time=0.3)
        self.wait(1)
        self.play(FadeOut(title), FadeOut(desc), FadeOut(github_text), run_time=0.5)


class StatsScene(Scene):
    """Animated statistics with counters."""
    def construct(self):
        # Title
        stats_title = Text("Repository Stats", font_size=48, weight=BOLD)
        stats_title.to_edge(UP, buff=0.8)
        stats_title.set_color(YELLOW)

        # Stars
        star_icon = Text("⭐", font_size=48)
        star_label = Text("Stars", font_size=32)
        star_value = Text("{stars_str}", font_size=48, weight=BOLD)
        star_value.set_color(YELLOW)

        star_group = VGroup(star_icon, star_label, star_value).arrange(DOWN, buff=0.3)
        star_group.shift(LEFT * 3)

        # Forks
        fork_icon = Text("🔀", font_size=48)
        fork_label = Text("Forks", font_size=32)
        fork_value = Text("{forks_str}", font_size=48, weight=BOLD)
        fork_value.set_color(BLUE)

        fork_group = VGroup(fork_icon, fork_label, fork_value).arrange(DOWN, buff=0.3)
        fork_group.shift(RIGHT * 0)
'''

    # Add language if available
    if language:
        code += f'''
        # Language
        lang_icon = Text("💻", font_size=48)
        lang_label = Text("Language", font_size=32)
        lang_value = Text("{escape_str(language)}", font_size=36, weight=BOLD)
        lang_value.set_color(GREEN)

        lang_group = VGroup(lang_icon, lang_label, lang_value).arrange(DOWN, buff=0.3)
        lang_group.shift(RIGHT * 3)

        all_stats = VGroup(star_group, fork_group, lang_group)
'''
    else:
        code += '''
        all_stats = VGroup(star_group, fork_group)
'''

    code += '''
        # FAST animations - optimized for speed
        self.play(FadeIn(stats_title), run_time=0.4)
        self.play(
            LaggedStart(
                *[FadeIn(group, shift=UP) for group in all_stats],
                lag_ratio=0.2
            ),
            run_time=1
        )
        self.wait(1)
        self.play(FadeOut(stats_title), FadeOut(all_stats), run_time=0.5)
'''

    # Features scene (only if we have features)
    if features_esc:
        code += '''

class FeaturesScene(Scene):
    """Key features presentation."""
    def construct(self):
        # Title
        features_title = Text("Key Features", font_size=48, weight=BOLD)
        features_title.to_edge(UP, buff=0.8)
        features_title.set_color(TEAL)

        self.play(FadeIn(features_title), run_time=0.4)

        # Features list
'''
        for i, feature in enumerate(features_esc):
            code += f'''        feature_{i+1} = Text("• {feature}", font_size=28)
'''

        code += f'''        features_group = VGroup({", ".join([f"feature_{i+1}" for i in range(len(features_esc))])}).arrange(DOWN, aligned_edge=LEFT, buff=0.4)
        features_group.next_to(features_title, DOWN, buff=0.8)

        # FAST animation - show all features at once
        self.play(FadeIn(features_group, shift=RIGHT), run_time=0.8)
        self.wait(1)

        # Fade out
        self.play(FadeOut(features_title), FadeOut(features_group), run_time=0.5)
'''

    # Outro scene
    code += f'''

class OutroScene(Scene):
    """Call-to-action outro."""
    def construct(self):
        # Main CTA
        cta = Text("Check it out!", font_size=64, weight=BOLD)
        cta.set_color_by_gradient(BLUE, GREEN)

        # GitHub URL
        url = Text("github.com/{escape_str(owner)}/{escape_str(repo)}", font_size=36)
        url.next_to(cta, DOWN, buff=0.8)
        url.set_color(WHITE)
'''

    if homepage:
        code += f'''
        # Homepage (if available)
        homepage_text = Text("{escape_str(homepage)}", font_size=28)
        homepage_text.next_to(url, DOWN, buff=0.5)
        homepage_text.set_color(GRAY)
'''

    code += '''
        # FAST animations
        self.play(FadeIn(cta), run_time=0.5)
        self.play(FadeIn(url), run_time=0.4)
'''

    if homepage:
        code += '''        self.play(FadeIn(homepage_text), run_time=0.3)
'''

    code += '''        self.wait(1)

        # Fade out
'''
    if homepage:
        code += '''        self.play(FadeOut(cta), FadeOut(url), FadeOut(homepage_text), run_time=0.5)
'''
    else:
        code += '''        self.play(FadeOut(cta), FadeOut(url), run_time=0.5)
'''

    return code


def get_product_launch_tools_for_langchain():
    """Return LangChain Tool objects for the Product Launch agent."""
    from langchain_core.tools import tool

    # Module-level cache to avoid passing large JSON through the LLM
    # The LLM mangles control characters in JSON strings (e.g. README newlines),
    # causing json.loads to fail with "Invalid control character"
    _repo_data_cache = {}

    @tool
    def fetch_github_repo_data(repo_url: str) -> str:
        """
        Fetch GitHub repository data. After calling this, you MUST immediately call generate_product_launch_video_remotion with the result.

        Args:
            repo_url: GitHub repository URL (any format: github.com/owner/repo or owner/repo)

        Returns:
            JSON string with repository information. IMMEDIATELY pass this entire JSON string to generate_product_launch_video_remotion.
        """
        try:
            # Parse URL first to validate
            owner, repo = parse_github_url(repo_url)
            if not owner or not repo:
                return json.dumps({
                    "error": f"Could not parse GitHub URL: {repo_url}",
                    "detail": "Expected format: github.com/owner/repo or owner/repo"
                })

            log.info(f"Fetching GitHub data for {owner}/{repo}...")
            data = get_repo_data_from_url(repo_url)

            # Extract key fields for the agent
            repo_info = data.get("repo_info", {})
            result = {
                "success": True,
                "owner": data.get("owner"),
                "repo": data.get("repo"),
                "name": repo_info.get("name"),
                "description": repo_info.get("description"),
                "stars": repo_info.get("stargazers_count", 0),
                "forks": repo_info.get("forks_count", 0),
                "watchers": repo_info.get("watchers_count", 0),
                "language": repo_info.get("language"),
                "topics": repo_info.get("topics", []),
                "homepage": repo_info.get("homepage"),
                "readme_preview": data.get("readme", "")[:500] + "..." if len(data.get("readme", "")) > 500 else data.get("readme", ""),
                "full_data": data  # Store full data for video generation
            }

            log.info(f"Successfully fetched data for {owner}/{repo} ({result['stars']} stars)")

            # Cache the parsed data so the video generation tool can use it directly
            # instead of relying on the LLM to faithfully pass the JSON string
            cache_key = f"{owner}/{repo}"
            _repo_data_cache[cache_key] = result
            _repo_data_cache["_latest"] = result
            log.info(f"Cached repo data under key '{cache_key}' and '_latest'")

            # Return a small JSON summary for the agent (avoid passing huge blobs through the LLM)
            summary = {
                "success": True,
                "owner": result["owner"],
                "repo": result["repo"],
                "name": result["name"],
                "description": result["description"],
                "stars": result["stars"],
                "forks": result["forks"],
                "language": result["language"],
                "topics": result["topics"],
                "cache_key": cache_key,
                "instruction": "Now call generate_product_launch_video_remotion with this JSON"
            }
            result_json = json.dumps(summary)

            print(f"[FETCH TOOL] Returning summary ({len(result_json)} chars), full data cached under '{cache_key}'")
            print(f"[FETCH TOOL] Agent should now call generate_product_launch_video_remotion with this JSON")

            return result_json

        except GitHubError as e:
            log.error(f"GitHub API error: {e}")
            return json.dumps({
                "error": str(e.message),
                "status_code": e.status_code,
                "detail": e.detail
            })
        except Exception as e:
            log.error(f"Unexpected error fetching GitHub data: {e}", exc_info=True)
            return json.dumps({
                "error": f"Failed to fetch GitHub data: {e}"
            })

    @tool
    def generate_product_launch_video_remotion(repo_data_json: str) -> str:
        """
        Generate a professional product launch video using Remotion (5-10 seconds).

        This tool creates a polished animated video with smooth transitions.
        The video is automatically added to the timeline.

        Args:
            repo_data_json: JSON string from fetch_github_repo_data

        Returns:
            Success message or error.
        """
        try:
            from classes.remotion_client import render_product_launch_video, check_remotion_service

            # Try to parse the JSON input, using strict=False to tolerate
            # control characters that the LLM may have unescaped
            data = None
            try:
                data = json.loads(repo_data_json, strict=False)
            except (json.JSONDecodeError, TypeError) as parse_err:
                log.warning(f"JSON parse failed ({parse_err}), falling back to cached data")

            # Look up full data from cache (preferred - avoids LLM mangling issues)
            cache_key = None
            if data and "cache_key" in data:
                cache_key = data["cache_key"]
            elif data and "owner" in data and "repo" in data:
                cache_key = f"{data['owner']}/{data['repo']}"

            cached = _repo_data_cache.get(cache_key) if cache_key else None
            if not cached:
                cached = _repo_data_cache.get("_latest")
                if cached:
                    log.info("Using '_latest' cached repo data")

            if cached:
                log.info(f"Using cached repo data (key={cache_key or '_latest'})")
                data = cached
            elif not data:
                return "Error: Could not parse repo data JSON and no cached data available. Please call fetch_github_repo_data first."

            if "error" in data:
                return f"Error: Cannot generate video - GitHub data fetch failed: {data['error']}"

            # Check Remotion service
            if not check_remotion_service():
                return ("Remotion service is not running!\n\n"
                       "Start it with:\n"
                       "  cd /home/lol/project/core/remotion-service\n"
                       "  npm run serve")

            # Extract data - use full_data from cache, or fall back to direct fields
            full_data = data.get("full_data", {})
            repo_info = full_data.get("repo_info", {}) if full_data else {}

            # Extract features from README
            features = []
            readme = full_data.get("readme", "")
            if readme:
                lines = readme.split('\n')
                for line in lines[:50]:
                    stripped = line.strip()
                    if stripped.startswith(('- ', '* ', '+ ')) and 5 < len(stripped) < 100:
                        feature = stripped[2:].strip()
                        if feature and not feature.lower().startswith(('http', 'see', 'read', '[', '!')):
                            features.append(feature)
                            if len(features) >= 3:
                                break

            # Render with Remotion
            repo_name_display = f"{data['owner']}/{data['repo']}"
            print(f"[REMOTION] Rendering video for {repo_name_display}...")

            success, output_path, error = render_product_launch_video(
                repo_name=repo_info.get("name", data["repo"]),
                description=repo_info.get("description", ""),
                stars=repo_info.get("stargazers_count", 0),
                forks=repo_info.get("forks_count", 0),
                language=repo_info.get("language", ""),
                features=features,
                github_url=f"github.com/{data['owner']}/{data['repo']}",
                homepage=repo_info.get("homepage"),
                timeout_seconds=60
            )

            if not success:
                return f"Remotion render failed: {error}"

            # Verify file exists
            if not os.path.exists(output_path):
                return f"Video file not found at: {output_path}"

            print(f"[REMOTION] Video rendered successfully: {output_path}")

            # Add to timeline
            from classes.app import get_app
            from classes.query import File
            from classes.ai_openshot_tools import add_clip_to_timeline
            import time

            app = get_app()

            # Add file to project
            print("[REMOTION] Adding to project...")
            app.window.files_model.add_files([output_path])

            # Find and add to timeline
            time.sleep(0.3)  # Brief pause for file registration

            f = File.get(path=output_path)
            if not f:
                # Search by absolute path
                for c in File.filter():
                    try:
                        if hasattr(c, 'absolute_path') and callable(c.absolute_path):
                            if c.absolute_path() == output_path:
                                f = c
                                break
                    except Exception:
                        pass

            if f:
                add_clip_to_timeline(file_id=str(f.id), position_seconds=None, track=None)
                display_name = data.get("name", "Unknown")
                return f"SUCCESS! Professional product launch video for '{display_name}' added to timeline! (Rendered with Remotion in ~5-10 seconds)"
            else:
                return f"Video generated at {output_path} but couldn't auto-add to timeline. Please add manually."

        except Exception as e:
            log.error(f"Remotion video generation failed: {e}", exc_info=True)
            return f"Error: {str(e)[:200]}"

    @tool
    def generate_product_launch_video(repo_data_json: str) -> str:
        """
        Generate a product launch video using Manim animations (fallback).

        Use generate_product_launch_video_remotion instead for faster, higher-quality results.
        This tool is a fallback if Remotion is not available.

        Args:
            repo_data_json: JSON string from fetch_github_repo_data (must include 'full_data' field)

        Returns:
            Success message with details, or error message.
        """
        try:
            # Try to parse the JSON input, using strict=False to tolerate
            # control characters that the LLM may have unescaped
            data = None
            try:
                data = json.loads(repo_data_json, strict=False)
            except (json.JSONDecodeError, TypeError) as parse_err:
                log.warning(f"JSON parse failed ({parse_err}), falling back to cached data")

            # Look up full data from cache (preferred - avoids LLM mangling issues)
            cache_key = None
            if data and "cache_key" in data:
                cache_key = data["cache_key"]
            elif data and "owner" in data and "repo" in data:
                cache_key = f"{data['owner']}/{data['repo']}"

            cached = _repo_data_cache.get(cache_key) if cache_key else None
            if not cached:
                cached = _repo_data_cache.get("_latest")
                if cached:
                    log.info("Using '_latest' cached repo data (manim fallback)")

            if cached:
                log.info(f"Using cached repo data for manim (key={cache_key or '_latest'})")
                data = cached
            elif not data:
                return "Error: Could not parse repo data JSON and no cached data available. Please call fetch_github_repo_data first."

            if "error" in data:
                return f"Error: Cannot generate video - GitHub data fetch failed: {data['error']}"

            full_data = data.get("full_data")
            if not full_data:
                return "Error: repo_data_json must include 'full_data' field from fetch_github_repo_data"

            # Check if manim is installed
            import shutil
            manim_available = False
            try:
                import manim as _manim_test
                manim_available = True
            except ImportError:
                manim_available = shutil.which("manim") is not None

            if not manim_available:
                return (
                    "Error: Manim is not installed. Please install it first:\n"
                    "pip install manim\n\n"
                    "For more info: https://docs.manim.community/"
                )

            repo_name = f"{data.get('owner')}/{data.get('repo')}"
            log.info(f"========== PRODUCT LAUNCH: Starting for {repo_name} ==========")

            # Status update
            status_msg = f"Starting video generation for {repo_name}..."
            log.info(status_msg)
            print(f"[PRODUCT LAUNCH] Step 1: Starting generation for {repo_name}")

            # Generate Manim code
            print("[PRODUCT LAUNCH] Step 2: Generating Manim code...")
            try:
                manim_code = generate_product_launch_manim_code(full_data)
                print(f"[PRODUCT LAUNCH] Step 2: Code generated ({len(manim_code)} chars)")
            except Exception as e:
                log.error(f"Code generation failed: {e}", exc_info=True)
                print(f"[PRODUCT LAUNCH] ERROR in Step 2: {e}")
                return f"Error generating Manim code: {str(e)[:200]}"

            # Write script to temp file
            print("[PRODUCT LAUNCH] Step 3: Writing script to temp file...")
            tmpdir = tempfile.mkdtemp(prefix="flowcut_product_launch_")
            script_path = os.path.join(tmpdir, "product_launch.py")
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(manim_code)
            log.info(f"Saved Manim script to: {script_path}")
            print(f"[PRODUCT LAUNCH] Step 3: Script saved to {script_path}")

            # Find scenes
            print("[PRODUCT LAUNCH] Step 4: Finding scenes in script...")
            scenes = get_manim_scenes(script_path)
            if not scenes:
                print("[PRODUCT LAUNCH] ERROR in Step 4: No scenes found!")
                return f"Error: No Scene classes found in generated code."

            log.info(f"Found {len(scenes)} scene(s): {', '.join(scenes)}")
            print(f"[PRODUCT LAUNCH] Step 4: Found {len(scenes)} scenes: {', '.join(scenes)}")

            # Render each scene
            print("[PRODUCT LAUNCH] Step 5: Starting scene rendering...")
            output_dir = os.path.join(tmpdir, "media")
            os.makedirs(output_dir, exist_ok=True)
            video_paths = []
            errors = []

            for i, scene_name in enumerate(scenes, 1):
                print(f"[PRODUCT LAUNCH] Step 5.{i}: Rendering {scene_name}... (this may take 5-10 seconds)")
                log.info(f"Rendering scene {i}/{len(scenes)}: {scene_name}...")
                path, err = render_manim_scene(script_path, scene_name, quality="l", output_dir=output_dir)
                print(f"[PRODUCT LAUNCH] Step 5.{i}: Render completed. Path={path}, Error={err}")
                if err:
                    errors.append(f"Scene '{scene_name}': {err}")
                    log.error(f"Manim render failed for {scene_name}: {err}")
                elif path:
                    video_paths.append(path)
                    log.info(f"Successfully rendered scene: {scene_name} -> {path}")

            # Check if any scenes succeeded
            print(f"[PRODUCT LAUNCH] Step 6: Render summary - {len(video_paths)} succeeded, {len(errors)} failed")
            if errors and not video_paths:
                error_msg = "All scenes failed to render:\n" + "\n".join(errors)
                print(f"[PRODUCT LAUNCH] ERROR in Step 5: {error_msg}")
                return f"Error: {error_msg}"
            elif errors:
                log.warning(f"Some scenes failed: {errors}, but {len(video_paths)} succeeded")
                print(f"[PRODUCT LAUNCH] WARNING: Some scenes failed but continuing")

            if not video_paths:
                print("[PRODUCT LAUNCH] ERROR: No videos were rendered")
                return "Error: No videos were rendered."

            # Concatenate all scenes into one video
            print(f"[PRODUCT LAUNCH] Step 7: Concatenating {len(video_paths)} videos...")
            combined_path = os.path.join(tmpdir, "product_launch_combined.mp4")
            ok, err = concatenate_videos_ffmpeg(video_paths, combined_path)
            print(f"[PRODUCT LAUNCH] Step 7: Concatenation {'succeeded' if ok else 'failed'}. Error={err}")
            if not ok:
                return f"Error concatenating scenes: {err}"

            log.info(f"Successfully combined {len(video_paths)} scenes into: {combined_path}")

            # Verify file exists
            print("[PRODUCT LAUNCH] Step 8: Verifying output file...")
            if not os.path.exists(combined_path):
                print(f"[PRODUCT LAUNCH] ERROR in Step 8: File not found at {combined_path}")
                return f"Error: Video file was not created at {combined_path}"

            file_size = os.path.getsize(combined_path) / 1024 / 1024  # MB
            log.info(f"Video file size: {file_size:.2f} MB")
            print(f"[PRODUCT LAUNCH] Step 8: File verified - {file_size:.2f} MB")

            # Add to project and timeline
            print("[PRODUCT LAUNCH] Step 9: Adding to project and timeline...")
            from classes.app import get_app
            from classes.query import File
            from classes.ai_openshot_tools import add_clip_to_timeline
            import time

            app = get_app()
            print("[PRODUCT LAUNCH] Step 9: Got app instance")

            # Add file to project (matches working Manim implementation)
            try:
                log.info("Adding product launch video to project...")
                print("[PRODUCT LAUNCH] Step 9a: Calling add_files()...")
                app.window.files_model.add_files([combined_path])
                print("[PRODUCT LAUNCH] Step 9a: add_files() completed")
            except Exception as e:
                log.error("add_files failed: %s", e, exc_info=True)
                return f"Error adding to project: {str(e)[:200]}\n\nVideo saved at: {combined_path}"

            # Add clip to timeline (exactly like working Manim code)
            print("[PRODUCT LAUNCH] Step 9b: Looking up file in database...")
            path_norm = os.path.normpath(combined_path)
            f = File.get(path=combined_path) or File.get(path=path_norm)
            if not f:
                print("[PRODUCT LAUNCH] Step 9b: Direct lookup failed, searching by absolute_path...")
                # Search by absolute_path (call as method, not property)
                for c in File.filter():
                    try:
                        if hasattr(c, 'absolute_path') and callable(c.absolute_path):
                            if c.absolute_path() == combined_path:
                                f = c
                                print(f"[PRODUCT LAUNCH] Step 9b: Found file by absolute_path: {c.id}")
                                break
                    except Exception:
                        pass

            if f:
                print(f"[PRODUCT LAUNCH] Step 9c: File found (id={f.id}), adding to timeline...")
                try:
                    add_clip_to_timeline(file_id=str(f.id), position_seconds=None, track=None)
                    print("[PRODUCT LAUNCH] Step 9c: Timeline add completed!")
                    repo_name = data.get("name", "Unknown")
                    print(f"[PRODUCT LAUNCH] ========== SUCCESS! Video for '{repo_name}' added to timeline ==========")
                    return f"Successfully created product launch video for '{repo_name}'! Added to timeline with {len(scenes)} scenes: {', '.join(scenes)}"
                except Exception as e:
                    log.error(f"Timeline add failed: {e}", exc_info=True)
                    print(f"[PRODUCT LAUNCH] ERROR in Step 9c: {e}")
                    return f"Video generated but timeline add failed: {str(e)[:200]}\n\nVideo at: {combined_path}"
            else:
                log.warning("Could not find file in database")
                print(f"[PRODUCT LAUNCH] ERROR in Step 9b: File not found in database")
                return f"Video generated but could not be added to timeline.\n\nVideo saved at: {combined_path}\n\nTry adding it manually from Project Files."

        except json.JSONDecodeError as e:
            log.error(f"JSON decode error: {e}")
            print(f"[PRODUCT LAUNCH] ERROR: JSON decode - {e}")
            error_msg = str(e)[:200]  # Truncate long errors
            return f"Error: Invalid JSON data received. {error_msg}"
        except Exception as e:
            log.error(f"Product launch video generation failed: {e}", exc_info=True)
            print(f"[PRODUCT LAUNCH] ERROR: Exception - {e}")
            error_msg = str(e)[:200]  # Truncate long errors
            return f"Error: Video generation failed - {error_msg}"

    return [fetch_github_repo_data, generate_product_launch_video_remotion, generate_product_launch_video]
