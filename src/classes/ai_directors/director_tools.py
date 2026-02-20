"""
Director Analysis Tools

Read-only tools for directors to analyze video projects.
These tools don't modify the project - they only query and analyze.
"""

from classes.logger import log


def _get_app():
    """Get app; must be called from main thread."""
    from classes.app import get_app
    return get_app()


# ---- Analysis Tools (Read-Only) ----


def analyze_timeline_structure() -> str:
    """
    Get overview of timeline structure: tracks, clips, transitions.

    Returns detailed information about the project timeline structure
    including number of layers, clips per layer, transitions, and effects.
    """
    try:
        from classes.query import Clip, Track
        app = _get_app()
        proj = app.project

        # Get clips
        clips = Clip.filter()
        layers = {}
        for clip in clips:
            layer = clip.data.get("layer", 0)
            if layer not in layers:
                layers[layer] = []
            layers[layer].append(clip)

        # Build summary
        lines = [f"Timeline Structure:"]
        lines.append(f"  Total clips: {len(clips)}")
        lines.append(f"  Total layers: {len(layers)}")

        for layer_num in sorted(layers.keys()):
            layer_clips = layers[layer_num]
            lines.append(f"  Layer {layer_num}: {len(layer_clips)} clips")

        # Get transitions
        transitions = proj.get("transitions") or []
        lines.append(f"  Total transitions: {len(transitions)}")

        # Get effects
        effects = proj.get("effects") or []
        lines.append(f"  Total effects: {len(effects)}")

        return "\n".join(lines)

    except Exception as e:
        log.error(f"analyze_timeline_structure: {e}", exc_info=True)
        return f"Error: {e}"


def analyze_pacing() -> str:
    """
    Analyze video pacing: cut frequency, scene durations, rhythm.

    Returns analysis of how fast-paced the video is, average clip duration,
    and pacing patterns.
    """
    try:
        from classes.query import Clip
        app = _get_app()
        proj = app.project

        clips = Clip.filter()
        if not clips:
            return "No clips to analyze"

        # Calculate durations
        fps = proj.get("fps", {})
        fps_num = fps.get("num", 30)
        fps_den = fps.get("den", 1)
        fps_value = fps_num / fps_den if fps_den else 30

        durations = []
        for clip in clips:
            start = clip.data.get("start", 0)
            end = clip.data.get("end", 0)
            duration_frames = end - start
            duration_seconds = duration_frames / fps_value
            durations.append(duration_seconds)

        if not durations:
            return "No clip durations available"

        avg_duration = sum(durations) / len(durations)
        min_duration = min(durations)
        max_duration = max(durations)

        # Categorize pacing
        if avg_duration < 2:
            pacing_category = "Very fast-paced"
        elif avg_duration < 4:
            pacing_category = "Fast-paced"
        elif avg_duration < 6:
            pacing_category = "Moderate"
        elif avg_duration < 10:
            pacing_category = "Slow-paced"
        else:
            pacing_category = "Very slow-paced"

        lines = [
            f"Pacing Analysis:",
            f"  Total clips: {len(clips)}",
            f"  Average clip duration: {avg_duration:.2f}s",
            f"  Shortest clip: {min_duration:.2f}s",
            f"  Longest clip: {max_duration:.2f}s",
            f"  Pacing category: {pacing_category}",
            f"  Cuts per minute: {60 / avg_duration:.1f}" if avg_duration > 0 else "  Cuts per minute: N/A",
        ]

        return "\n".join(lines)

    except Exception as e:
        log.error(f"analyze_pacing: {e}", exc_info=True)
        return f"Error: {e}"


def analyze_audio_levels() -> str:
    """
    Analyze audio levels: volume, mixing, silence detection.

    Returns information about audio tracks and their levels.
    """
    try:
        from classes.query import Clip
        app = _get_app()

        clips = Clip.filter()
        audio_clips = [c for c in clips if c.data.get("reader", {}).get("has_audio", False)]

        lines = [
            f"Audio Analysis:",
            f"  Total audio clips: {len(audio_clips)}",
            f"  Audio analysis not yet implemented (requires libopenshot integration)",
        ]

        return "\n".join(lines)

    except Exception as e:
        log.error(f"analyze_audio_levels: {e}", exc_info=True)
        return f"Error: {e}"


def analyze_transitions() -> str:
    """
    Analyze transitions: types, timing, effectiveness.

    Returns information about transitions used in the project.
    """
    try:
        app = _get_app()
        proj = app.project

        transitions = proj.get("transitions") or []

        if not transitions:
            return "No transitions in project"

        # Count transition types
        transition_types = {}
        for trans in transitions:
            trans_type = trans.get("type", "unknown")
            transition_types[trans_type] = transition_types.get(trans_type, 0) + 1

        lines = [
            f"Transition Analysis:",
            f"  Total transitions: {len(transitions)}",
            f"  Transition types:",
        ]

        for trans_type, count in transition_types.items():
            lines.append(f"    {trans_type}: {count}")

        return "\n".join(lines)

    except Exception as e:
        log.error(f"analyze_transitions: {e}", exc_info=True)
        return f"Error: {e}"


def analyze_clip_content() -> str:
    """
    Analyze visual content of clips using metadata.

    Returns information about clip content, scene descriptions, and AI analysis.
    """
    try:
        from classes.query import File
        app = _get_app()

        files = File.filter()

        lines = [
            f"Content Analysis:",
            f"  Total files: {len(files)}",
        ]

        # Check for AI metadata
        files_with_metadata = 0
        for file in files:
            metadata = file.data.get("ai_metadata", {})
            if metadata:
                files_with_metadata += 1

        lines.append(f"  Files with AI analysis: {files_with_metadata}")

        return "\n".join(lines)

    except Exception as e:
        log.error(f"analyze_clip_content: {e}", exc_info=True)
        return f"Error: {e}"


def analyze_music_sync() -> str:
    """
    Analyze music beat alignment with cuts.

    Returns information about how well music syncs with video cuts.
    """
    try:
        lines = [
            f"Music Sync Analysis:",
            f"  Music sync analysis not yet implemented",
            f"  Would require beat detection and cut timing correlation",
        ]

        return "\n".join(lines)

    except Exception as e:
        log.error(f"analyze_music_sync: {e}", exc_info=True)
        return f"Error: {e}"


def get_project_metadata() -> str:
    """
    Get overall project metadata: duration, resolution, fps, format.

    Returns basic project information.
    """
    try:
        app = _get_app()
        proj = app.project

        profile = proj.get("profile") or "unknown"
        fps = proj.get("fps") or {}
        fps_str = f"{fps.get('num', '')}/{fps.get('den', 1)}" if fps else "unknown"
        duration = proj.get("duration") or 0
        width = proj.get("width") or 0
        height = proj.get("height") or 0

        lines = [
            f"Project Metadata:",
            f"  Profile: {profile}",
            f"  Resolution: {width}x{height}",
            f"  FPS: {fps_str}",
            f"  Duration: {duration} seconds",
        ]

        return "\n".join(lines)

    except Exception as e:
        log.error(f"get_project_metadata: {e}", exc_info=True)
        return f"Error: {e}"


def analyze_clip_visual_content(clip_id: str = None) -> str:
    """
    Analyze visual content of clips using AI vision models.

    Args:
        clip_id: Optional clip ID to analyze specific clip. If not provided,
                analyzes all clips on timeline.

    Returns:
        Formatted analysis of visual content including:
        - Composition quality (framing, lighting, colors)
        - Scene content (objects, activities, settings)
        - Visual quality issues (blur, exposure, stability)
        - Aesthetic assessment (mood, style, visual appeal)
    """
    try:
        import asyncio
        from classes.vision_analysis_service import get_vision_service
        from classes.query import Clip

        service = get_vision_service()

        if not service.is_available():
            return "Vision analysis not available (disabled or not configured). Enable 'Vision Analysis for Directors' in AI Features settings."

        # Get clips to analyze
        clips = []
        if clip_id:
            clip = Clip.get(id=clip_id)
            if clip:
                clips = [clip]
        else:
            clips = Clip.filter()  # All clips

        if not clips:
            return "No clips found to analyze"

        lines = [f"Visual Content Analysis:"]
        lines.append(f"  Total clips: {len(clips)}")

        # Analyze each clip's visual content
        analyzed_count = 0
        for clip in clips:
            try:
                # Get or create vision analysis
                analysis = asyncio.run(service.analyze_clip_visual_content(clip.id))

                if analysis and analysis.get("analyzed"):
                    analyzed_count += 1

                    # Format results
                    lines.append(f"\n  Clip {clip.id}:")

                    # Description
                    description = analysis.get('description', 'N/A')
                    if description and len(description) > 100:
                        description = description[:97] + "..."
                    lines.append(f"    Description: {description}")

                    # Vision analysis scores
                    vision_analysis = analysis.get('vision_analysis', {})
                    if vision_analysis:
                        composition = vision_analysis.get('composition', {})
                        if composition:
                            framing = composition.get('framing_score', 0)
                            lighting = composition.get('lighting_score', 0)
                            if framing > 0 or lighting > 0:
                                lines.append(f"    Composition Score: {framing:.2f}")
                                lines.append(f"    Lighting Score: {lighting:.2f}")

                        visual_quality = vision_analysis.get('visual_quality', {})
                        if visual_quality:
                            issues = []
                            if visual_quality.get('blur_detected'):
                                issues.append("blur detected")
                            if visual_quality.get('exposure_issues'):
                                issues.append("exposure issues")
                            if issues:
                                lines.append(f"    Quality Issues: {', '.join(issues)}")
                            else:
                                lines.append(f"    Quality: {visual_quality.get('resolution_appearance', 'good')}")

                    # Tags
                    tags = analysis.get('tags', {})
                    if tags:
                        objects = tags.get('objects', [])
                        if objects:
                            lines.append(f"    Objects: {', '.join(objects[:5])}")

                        scenes = tags.get('scenes', [])
                        if scenes:
                            lines.append(f"    Scene Types: {', '.join(scenes)}")

                        activities = tags.get('activities', [])
                        if activities:
                            lines.append(f"    Activities: {', '.join(activities[:3])}")

                        mood = tags.get('mood', [])
                        if mood:
                            lines.append(f"    Mood: {', '.join(mood[:3])}")

                    # Confidence
                    confidence = analysis.get('confidence', 0)
                    if confidence > 0:
                        lines.append(f"    Confidence: {confidence:.2f}")

            except Exception as e:
                log.warning(f"Failed to analyze clip {clip.id}: {e}")
                lines.append(f"\n  Clip {clip.id}: Analysis failed - {e}")

        lines.append(f"\n  Clips with vision analysis: {analyzed_count}/{len(clips)}")

        return "\n".join(lines)

    except Exception as e:
        log.error(f"analyze_clip_visual_content: {e}", exc_info=True)
        return f"Error: {e}"


# ---- LangChain Tool Registration ----


def get_director_analysis_tools_for_langchain():
    """
    Get director analysis tools wrapped for LangChain.

    Returns list of LangChain tools that directors can use.
    """
    from langchain_core.tools import tool

    @tool
    def analyze_timeline_structure_tool() -> str:
        """Get overview of timeline structure: tracks, clips, transitions, effects."""
        return analyze_timeline_structure()

    @tool
    def analyze_pacing_tool() -> str:
        """Analyze video pacing: cut frequency, scene durations, average clip length."""
        return analyze_pacing()

    @tool
    def analyze_audio_levels_tool() -> str:
        """Analyze audio levels: volume, mixing, audio track information."""
        return analyze_audio_levels()

    @tool
    def analyze_transitions_tool() -> str:
        """Analyze transitions: types used, frequency, timing."""
        return analyze_transitions()

    @tool
    def analyze_clip_content_tool() -> str:
        """Analyze visual content of clips using AI metadata and scene descriptions."""
        return analyze_clip_content()

    @tool
    def analyze_music_sync_tool() -> str:
        """Analyze music beat alignment with video cuts."""
        return analyze_music_sync()

    @tool
    def get_project_metadata_tool() -> str:
        """Get project metadata: duration, resolution, fps, format."""
        return get_project_metadata()

    @tool
    def analyze_clip_visual_content_tool(clip_id: str = None) -> str:
        """Analyze visual content using AI vision: composition quality, objects, scenes, mood, visual quality issues. Requires vision analysis to be enabled in settings."""
        return analyze_clip_visual_content(clip_id)

    return [
        analyze_timeline_structure_tool,
        analyze_pacing_tool,
        analyze_audio_levels_tool,
        analyze_transitions_tool,
        analyze_clip_content_tool,
        analyze_music_sync_tool,
        get_project_metadata_tool,
        analyze_clip_visual_content_tool,
    ]
