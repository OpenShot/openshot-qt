"""
Sub-agents: Video (timeline/editing), Manim (educational video), Voice/Music (stubs), Music (Suno), Transitions.
Each returns a string result for the root agent to aggregate.
"""

from classes.logger import log


def run_video_agent(model_id, task_or_messages, main_thread_runner):
    """
    Run the Video/Timeline agent with the given task or message list.
    task_or_messages: either a string (single user message) or list of dicts (role/content).
    Returns the agent response string.
    """
    from classes.ai_agent_runner import run_agent_with_tools
    from classes.ai_openshot_tools import get_openshot_tools_for_langchain

    if isinstance(task_or_messages, str):
        messages = [{"role": "user", "content": task_or_messages}]
    else:
        messages = list(task_or_messages)
    tools = get_openshot_tools_for_langchain()
    return run_agent_with_tools(
        model_id=model_id,
        messages=messages,
        tools=tools,
        main_thread_runner=main_thread_runner,
        system_prompt=(
            "You are the Flowcut video/timeline agent. You help with project state, clips, "
            "timeline, export, video generation, and AI object replacement (removing or swapping items in video). "
            "Use the provided tools. Respond concisely."
        ),
    )


MANIM_SYSTEM_PROMPT = (
    "You are the Flowcut Manim agent. You create educational and mathematical "
    "animation videos using Manim (manim.community).\n\n"
    "IMPORTANT: When the user requests a Manim video, you MUST call generate_manim_video_tool immediately. "
    "DO NOT ask the user if they want the code. DO NOT provide code manually. "
    "ALWAYS call the tool with the user's description.\n\n"
    "The tool will:\n"
    "1. Generate Manim Python code automatically\n"
    "2. Render all scenes\n"
    "3. Add the videos to the timeline\n\n"
    "If add_as_single_clip is True (default), all scenes are combined into one clip. "
    "If False, each scene becomes a separate clip on the timeline.\n\n"
    "After calling the tool, confirm what was added to the timeline."
)


def run_manim_agent(model_id, task_or_messages, main_thread_runner):
    """
    Run the Manim (educational video) agent with Manim tools.
    Returns the agent response string.
    """
    try:
        from classes.ai_agent_runner import run_agent_with_tools
        from classes.ai_manim_tools import get_manim_tools_for_langchain
    except ImportError as e:
        log.debug("Manim tools not available: %s", e)
        return (
            "Manim agent is not available. Install manim (pip install manim) and try again, "
            "or use the video agent for general editing."
        )
    if isinstance(task_or_messages, str):
        messages = [{"role": "user", "content": task_or_messages}]
    else:
        messages = list(task_or_messages)
    tools = get_manim_tools_for_langchain()
    return run_agent_with_tools(
        model_id=model_id,
        messages=messages,
        tools=tools,
        main_thread_runner=main_thread_runner,
        system_prompt=MANIM_SYSTEM_PROMPT,
    )


VOICE_MUSIC_SYSTEM_PROMPT = (
    "You are the Flowcut voice and music agent. You help with narration, text-to-speech (TTS), "
    "voice overlays, video tagging, and background music.\n\n"
    "IMPORTANT: When the user requests TTS, narration, or voice over, call generate_tts_and_add_to_timeline_tool immediately. "
    "First check if OpenAI is configured with test_openai_tts_api_key_tool. If not configured, instruct the user to add their "
    "OpenAI API key in Preferences > AI (OpenAI API Key).\n\n"
    "The TTS tool will generate natural speech, handle long scripts automatically (splits into chunks), "
    "and add the audio to a new track on the timeline.\n\n"
    "Available voices: alloy (neutral), echo (male), fable (expressive), onyx (deep male), nova (female), shimmer (soft female). "
    "Use tts-1 model for speed, tts-1-hd for quality."
)


def run_voice_music_agent(model_id, task_or_messages, main_thread_runner):
    """
    Run the Voice/Music agent with voice/music + TTS tools.
    Returns the agent response string.
    """
    try:
        from classes.ai_agent_runner import run_agent_with_tools
        from classes.ai_voice_music_tools import get_voice_music_tools_for_langchain
        from classes.ai_tts_tools import get_tts_tools_for_langchain
    except ImportError as e:
        log.debug("Voice/music or TTS tools not available: %s", e)
        return "Voice and music agent is not available. Use the video agent for timeline and export."

    if isinstance(task_or_messages, str):
        messages = [{"role": "user", "content": task_or_messages}]
    else:
        messages = list(task_or_messages)

    # Combine stub tools + TTS tools
    tools = list(get_voice_music_tools_for_langchain()) + list(get_tts_tools_for_langchain())

    return run_agent_with_tools(
        model_id=model_id,
        messages=messages,
        tools=tools,
        main_thread_runner=main_thread_runner,
        system_prompt=VOICE_MUSIC_SYSTEM_PROMPT,
    )


MUSIC_SYSTEM_PROMPT = (
    "You are the Flowcut music agent. You generate and add background music that fits the user's video. "
    "First, understand the project: call get_project_info_tool, list_clips_tool (and list_layers_tool if needed). "
    "Then decide a Suno request: use topic+tags for simple mode, or prompt+tags for custom lyrics mode. "
    "Prefer instrumental background music unless the user explicitly wants vocals or provides lyrics. "
    "Decide where the music should start: if the user gives a timestamp, use it; otherwise use the playhead "
    "(by leaving position_seconds empty). If placement fails, fall back to 0 seconds. "
    "Finally, call generate_music_and_add_to_timeline_tool to generate/download/import the MP3 and place it on a new track. "
    "If music generation fails, call test_suno_token_tool to diagnose the issue. "
    "If Suno is not configured, instruct the user to set the Suno TreeHacks token in Preferences > AI (Suno TreeHacks Token)."
)


def run_music_agent(model_id, task_or_messages, main_thread_runner):
    """
    Run the Music agent (Suno) with OpenShot timeline tools + Suno music tool(s).
    Returns the agent response string.
    """
    from classes.ai_agent_runner import run_agent_with_tools
    from classes.ai_openshot_tools import get_openshot_tools_for_langchain
    from classes.ai_suno_music_tools import get_suno_music_tools_for_langchain

    if isinstance(task_or_messages, str):
        messages = [{"role": "user", "content": task_or_messages}]
    else:
        messages = list(task_or_messages)

    tools = list(get_openshot_tools_for_langchain()) + list(get_suno_music_tools_for_langchain())
    return run_agent_with_tools(
        model_id=model_id,
        messages=messages,
        tools=tools,
        main_thread_runner=main_thread_runner,
        system_prompt=MUSIC_SYSTEM_PROMPT,
    )


TRANSITIONS_SYSTEM_PROMPT = (
    "You are the Flowcut transitions agent. You help users apply professional transitions and effects to their videos.\n\n"
    "You have access to 412+ OpenShot transitions including:\n"
    "- Common transitions: fade, circle in/out, wipe (left/right/top/bottom)\n"
    "- Extra transitions: ripples, blurs, blinds, boards, crosses, and many more artistic effects\n\n"
    "WORKFLOW:\n"
    "1. First, use list_clips_tool to see what clips are available\n"
    "2. Use search_transitions_tool to find appropriate transitions (e.g., search 'fade', 'wipe', 'circle')\n"
    "3. Apply transitions using:\n"
    "   - add_transition_between_clips_tool: For smooth transitions between two clips\n"
    "   - add_transition_to_clip_tool: For fade in/out effects on a single clip\n\n"
    "TIPS:\n"
    "- For fade effects, use position='start' for fade in, position='end' for fade out\n"
    "- Duration is typically 0.5-2.0 seconds (1.0 is standard)\n"
    "- Always check clip IDs with list_clips_tool before applying transitions\n"
    "- If user asks for specific style, use search_transitions_tool to find matching effects\n\n"
    "Respond concisely and confirm what transitions were added."
)


def run_transitions_agent(model_id, task_or_messages, main_thread_runner):
    """
    Run the Transitions agent with transitions tools + clip listing tools.
    Returns the agent response string.
    """
    from classes.ai_agent_runner import run_agent_with_tools
    from classes.ai_transitions_tools import get_transitions_tools_for_langchain
    from classes.ai_openshot_tools import get_openshot_tools_for_langchain

    if isinstance(task_or_messages, str):
        messages = [{"role": "user", "content": task_or_messages}]
    else:
        messages = list(task_or_messages)

    # Combine transitions tools with basic OpenShot tools (for listing clips)
    tools = list(get_transitions_tools_for_langchain()) + list(get_openshot_tools_for_langchain())

    return run_agent_with_tools(
        model_id=model_id,
        messages=messages,
        tools=tools,
        main_thread_runner=main_thread_runner,
        system_prompt=TRANSITIONS_SYSTEM_PROMPT,
    )


RESEARCH_SYSTEM_PROMPT = (
    "You are the Flowcut research agent. You help users discover content and plan video aesthetics using web research.\n\n"
    "WORKFLOW:\n"
    "1. Check if Perplexity is configured: test_perplexity_api_key_tool\n"
    "2. General research: research_web_and_display_tool\n"
    "3. Theme/style planning: research_for_content_planning_tool\n\n"
    "CAPABILITIES:\n"
    "- Web search with AI-powered answers and citations\n"
    "- Image discovery and download\n"
    "- Content planning (colors, sounds, transitions, mood)\n"
    "- Theme research (e.g., 'Stranger Things aesthetic')\n\n"
    "CONTENT PLANNING EXAMPLE:\n"
    "User: \"Apply Stranger Things theme\"\n"
    "→ Call research_for_content_planning_tool(topic='Stranger Things', aspects='visuals,colors,sounds,transitions,mood')\n"
    "→ Present: visual style, color palette, sound suggestions, transition recommendations\n"
    "→ Suggest follow-up actions: \"Would you like me to add synthwave music?\" \"Should I apply fade transitions?\"\n\n"
    "WHEN TO ADD IMAGES TO TIMELINE:\n"
    "- Only set add_images_to_timeline='true' if user explicitly asks\n"
    "- Default: display in chat, let user decide\n"
    "- Position: empty uses playhead, or specify seconds\n\n"
    "OUTPUT FORMAT:\n"
    "- Present research clearly with citations\n"
    "- For content planning: give specific, actionable suggestions\n"
    "- Include image descriptions if images were downloaded\n"
    "- Suggest follow-up actions (add music, apply transitions, etc.)\n\n"
    "If Perplexity is not configured, instruct user to add API key in Preferences > AI (Perplexity API Key)."
)


def run_research_agent(model_id, task_or_messages, main_thread_runner):
    """
    Run the Research agent with Perplexity tools + basic OpenShot tools.
    Returns the agent response string.
    """
    from classes.ai_agent_runner import run_agent_with_tools
    from classes.ai_research_tools import get_research_tools_for_langchain
    from classes.ai_openshot_tools import get_openshot_tools_for_langchain

    if isinstance(task_or_messages, str):
        messages = [{"role": "user", "content": task_or_messages}]
    else:
        messages = list(task_or_messages)

    tools = list(get_research_tools_for_langchain()) + list(get_openshot_tools_for_langchain())
    return run_agent_with_tools(
        model_id=model_id,
        messages=messages,
        tools=tools,
        main_thread_runner=main_thread_runner,
        system_prompt=RESEARCH_SYSTEM_PROMPT,
    )


PRODUCT_LAUNCH_SYSTEM_PROMPT = (
    "You are the Flowcut product launch video agent. You create compelling product launch videos "
    "for GitHub repositories using animated visualizations.\n\n"
    "CRITICAL WORKFLOW - FOLLOW EXACTLY:\n"
    "1. Call fetch_github_repo_data with the GitHub URL\n"
    "2. IMMEDIATELY after receiving the data, call generate_product_launch_video_remotion with the JSON response "
    "(or generate_product_launch_video as fallback)\n"
    "3. Report the success message\n\n"
    "IMPORTANT RULES:\n"
    "- DO NOT ask the user questions\n"
    "- DO NOT explain what you're doing\n"
    "- DO NOT wait for confirmation\n"
    "- IMMEDIATELY call BOTH tools in sequence\n"
    "- The JSON from fetch_github_repo_data must be passed to generate_product_launch_video_remotion\n\n"
    "Example execution:\n"
    "User: 'Create video for facebook/react'\n"
    "1. fetch_github_repo_data('facebook/react') → receives JSON\n"
    "2. generate_product_launch_video_remotion(json_from_step_1) → video created\n"
    "3. Return: 'Video added to timeline!'\n\n"
    "The video automatically includes intro, stats, features, and outro scenes.\n"
    "All scenes are rendered and combined into a single timeline clip.\n\n"
    "DO NOT STOP until you have called BOTH tools and received a success message."
)


def run_product_launch_agent(model_id, task_or_messages, main_thread_runner):
    """
    Run the Product Launch agent with GitHub + Remotion/Manim tools.
    Returns the agent response string.
    """
    try:
        from classes.ai_agent_runner import run_agent_with_tools
        from classes.ai_product_launch_tools import get_product_launch_tools_for_langchain
    except ImportError as e:
        log.debug("Product launch tools not available: %s", e)
        return (
            "Product launch agent is not available. This may indicate missing dependencies. "
            "Please check that all required packages are installed."
        )

    if isinstance(task_or_messages, str):
        messages = [{"role": "user", "content": task_or_messages}]
    else:
        messages = list(task_or_messages)

    tools = get_product_launch_tools_for_langchain()
    return run_agent_with_tools(
        model_id=model_id,
        messages=messages,
        tools=tools,
        main_thread_runner=main_thread_runner,
        system_prompt=PRODUCT_LAUNCH_SYSTEM_PROMPT,
    )
