"""
Thread pool for running sub-agents in parallel when the root agent
invokes multiple invoke_* tools in one turn.
"""

import concurrent.futures
from classes.logger import log

# Shared executor for sub-agent invocations (I/O-bound LLM calls)
_executor = concurrent.futures.ThreadPoolExecutor(max_workers=4, thread_name_prefix="flowcut_subagent")


def submit_sub_agent(agent_name, model_id, messages, main_thread_runner):
    """
    Submit a sub-agent run to the thread pool.
    Returns a Future whose result is the agent response string.
    """
    from classes.ai_multi_agent import sub_agents

    runners = {
        "video": sub_agents.run_video_agent,
        "manim": sub_agents.run_manim_agent,
        "voice_music": sub_agents.run_voice_music_agent,
        "music": sub_agents.run_music_agent,
    }
    fn = runners.get(agent_name)
    if not fn:
        return _executor.submit(lambda: "Error: unknown agent {}".format(agent_name))
    return _executor.submit(fn, model_id, messages, main_thread_runner)


def run_sub_agents_parallel(calls):
    """
    Run multiple (agent_name, model_id, messages, main_thread_runner) in parallel.
    calls: list of (agent_name, model_id, messages, main_thread_runner).
    Returns list of (agent_name, result_string).
    """
    futures = []
    names = []
    for agent_name, model_id, messages, runner in calls:
        futures.append(submit_sub_agent(agent_name, model_id, messages, runner))
        names.append(agent_name)
    results = []
    for name, fut in zip(names, futures):
        try:
            results.append((name, fut.result(timeout=120)))
        except Exception as e:
            log.error("Sub-agent %s failed: %s", name, e, exc_info=True)
            results.append((name, "Error: {}".format(e)))
    return results
