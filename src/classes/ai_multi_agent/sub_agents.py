"""
Sub-agents: Video (timeline/editing), Manim (educational video), Voice/Music (stubs).
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
            "You are the Zenvi video/timeline agent. You help with project state, clips, "
            "timeline, export, and video generation. Use the provided tools. Respond concisely."
        ),
    )


MANIM_SYSTEM_PROMPT = (
    "You are the Zenvi Manim agent. You create educational and mathematical "
    "animation videos using Manim (manim.community). Use generate_manim_video_tool "
    "with the user's description to generate code, render, and add to the timeline. "
    "Respond concisely."
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
    "You are the Zenvi voice and music agent. You help with tagging videos (Azure API), "
    "generating storylines from tags, voice overlays (TTS), and background music. "
    "Use the provided tools. If a feature is not configured, say so and suggest using the video agent for other tasks."
)


def run_voice_music_agent(model_id, task_or_messages, main_thread_runner):
    """
    Run the Voice/Music agent with stub tools (tagging, storyline, voice, music).
    Returns the agent response string.
    """
    try:
        from classes.ai_agent_runner import run_agent_with_tools
        from classes.ai_voice_music_tools import get_voice_music_tools_for_langchain
    except ImportError as e:
        log.debug("Voice/music tools not available: %s", e)
        return "Voice and music agent is not available. Use the video agent for timeline and export."
    if isinstance(task_or_messages, str):
        messages = [{"role": "user", "content": task_or_messages}]
    else:
        messages = list(task_or_messages)
    tools = get_voice_music_tools_for_langchain()
    return run_agent_with_tools(
        model_id=model_id,
        messages=messages,
        tools=tools,
        main_thread_runner=main_thread_runner,
        system_prompt=VOICE_MUSIC_SYSTEM_PROMPT,
    )
