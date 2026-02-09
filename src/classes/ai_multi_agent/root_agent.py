"""
Root/supervisor agent: routes user requests to Video, Manim, or Voice/Music sub-agents.
Runs in the worker thread; sub-agent tool execution is dispatched to the main thread.
"""

from classes.ai_prompts import ROOT_SYSTEM_PROMPT


def run_root_agent(model_id, messages, main_thread_runner):
    """
    Run the root agent with invoke_* tools. Sub-agents run in this thread;
    their tools run on the main thread via main_thread_runner.
    Returns the final response string.
    """
    from classes.ai_agent_runner import run_agent_with_tools

    # Build invoke_* tools that pass model_id and main_thread_runner into sub-agents
    def make_invoke_with_model():
        from langchain_core.tools import tool
        from classes.ai_multi_agent import sub_agents
        mid = model_id
        runner = main_thread_runner

        @tool
        def invoke_video_agent(task: str) -> str:
            """Route to the video/timeline agent. Use for: list files, add clips, export, timeline editing, generate video, split clips."""
            return sub_agents.run_video_agent(mid, task, runner)

        @tool
        def invoke_manim_agent(task: str) -> str:
            """Route to the Manim agent for educational/math animation videos."""
            return sub_agents.run_manim_agent(mid, task, runner)

        @tool
        def invoke_voice_music_agent(task: str) -> str:
            """Route to the voice/music agent for narration and music."""
            return sub_agents.run_voice_music_agent(mid, task, runner)

        return [invoke_video_agent, invoke_manim_agent, invoke_voice_music_agent]

    root_tools = make_invoke_with_model()
    # Root tools run in worker thread (no main-thread wrap)
    return run_agent_with_tools(
        model_id=model_id,
        messages=messages,
        tools=root_tools,
        main_thread_runner=None,  # do not wrap; invoke_* run in worker thread
        system_prompt=ROOT_SYSTEM_PROMPT,
        max_iterations=10,
    )
