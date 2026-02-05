"""
Agent runner: builds a LangChain agent with the selected LLM and Zenvi tools,
runs it in a worker thread, and dispatches tool execution to the Qt main thread.
"""

import json
import threading
import time
from classes.logger import log


def _debug_log(location, message, data, hypothesis_id):
    # #region agent log
    try:
        import os
        _path = "/home/vboxuser/Projects/Zenvi/.cursor/debug.log"
        os.makedirs(os.path.dirname(_path), exist_ok=True)
        with open(_path, "a") as f:
            f.write(json.dumps({"location": location, "message": message, "data": data, "hypothesisId": hypothesis_id, "timestamp": time.time()}) + "\n")
    except Exception:
        pass
    # #endregion


try:
    from PyQt5.QtCore import QObject, QMetaObject, Qt, Q_ARG, pyqtSignal, pyqtSlot
except ImportError:
    QObject = object
    QMetaObject = None
    Qt = None
    Q_ARG = None
    pyqtSignal = None
    pyqtSlot = lambda x: x


SYSTEM_PROMPT = """You are an AI assistant for Zenvi. You help users with video editing, effects, transitions, and general editing tasks. You can query project state and perform editing actions using the provided tools. When you use a tool, confirm briefly what you did. Respond concisely and practically.

When the user asks to "clip" or "split" without clearly choosing, ask: "Do you want to (1) clip the existing clip on the timeline at the playhead (split it into two), or (2) create a new clip from a file (by choosing a file and frame range)?" If they choose (1) or say "clip the current clip", "at the playhead", or "the one on the timeline": use slice_clip_at_playhead_tool. If they choose (2) or "create a new video/clip": use list_files_tool then split_file_add_clip_tool with file_id and start_frame, end_frame.

After using split_file_add_clip_tool, always ask: "Would you like this clip added to the timeline at the playhead?" If the user says yes, call add_clip_to_timeline_tool with no arguments. Never ask the user for a file ID or show file IDs in your reply; the app keeps context of the clip just created.

When the user asks to generate a video, create a video, make a video and add it to the timeline, or similar, use generate_video_and_add_to_timeline_tool with the user's description as the prompt. If they specify a position (e.g. "at 30 seconds") or track, pass position_seconds and/or track; otherwise leave them empty for playhead and default track."""


class MainThreadToolRunner(QObject if QObject is not object else object):
    """
    Lives on the Qt main thread. Holds Zenvi tools and runs them when run_tool is invoked.
    Used by the worker thread via BlockingQueuedConnection to run tools on the main thread.
    """
    if pyqtSignal is not None:
        tool_completed = pyqtSignal(str, str)  # tool_name, result

    def __init__(self):
        if QObject is not object:
            super().__init__()
        self._tools = {}
        self.last_tool_result = None

    def register_tools(self, tools_list):
        """Register a list of LangChain tools by name."""
        for t in tools_list:
            name = getattr(t, "name", None) or getattr(t, "__name__", str(t))
            self._tools[name] = t
        log.debug("Registered %d tools on main thread runner", len(self._tools))

    if QMetaObject is not None:
        @pyqtSlot(str, str, result=str)
        def run_tool(self, name, args_json):
            """Run a tool by name with JSON-serialized args. Called from worker via BlockingQueuedConnection."""
            try:
                tool = self._tools.get(name)
                if not tool:
                    self.last_tool_result = "Error: unknown tool {}".format(name)
                    if pyqtSignal is not None and hasattr(self, "tool_completed"):
                        self.tool_completed.emit(name, self.last_tool_result)
                    return self.last_tool_result
                args = json.loads(args_json) if args_json else {}
                result = tool.invoke(args)
                self.last_tool_result = result if isinstance(result, str) else str(result)
                if pyqtSignal is not None and hasattr(self, "tool_completed"):
                    self.tool_completed.emit(name, self.last_tool_result)
                return self.last_tool_result
            except Exception as e:
                log.error("MainThreadToolRunner.run_tool %s: %s", name, e, exc_info=True)
                self.last_tool_result = "Error: {}".format(e)
                if pyqtSignal is not None and hasattr(self, "tool_completed"):
                    self.tool_completed.emit(name, self.last_tool_result)
                return self.last_tool_result


def _wrap_tool_for_main_thread(raw_tool, runner):
    """Wrap a LangChain tool so that invoke() runs on the main thread via runner."""
    from langchain_core.tools import StructuredTool
    name = getattr(raw_tool, "name", None) or getattr(raw_tool, "__name__", "tool")
    desc = getattr(raw_tool, "description", "") or ""
    args_schema = getattr(raw_tool, "args_schema", None)

    def invoke_from_main_thread(*args, **kwargs):
        # LangChain may call with invoke(args_dict) or invoke(**kwargs); accept both.
        if args and len(args) == 1 and isinstance(args[0], dict):
            args_dict = dict(args[0])
        else:
            args_dict = {}
        args_dict.update(kwargs)
        if QMetaObject is None or Qt is None or runner is None:
            return raw_tool.invoke(args_dict)
        args_json = json.dumps(args_dict) if args_dict else "{}"
        QMetaObject.invokeMethod(
            runner,
            "run_tool",
            Qt.BlockingQueuedConnection,
            Q_ARG(str, name),
            Q_ARG(str, args_json),
        )
        return getattr(runner, "last_tool_result", "Error: no result")

    return StructuredTool.from_function(
        func=invoke_from_main_thread,
        name=name,
        description=desc,
        args_schema=args_schema,
    )


def run_agent(model_id, messages, main_thread_runner, timeout_seconds=120):
    """
    Run the LangChain agent with the given model_id and conversation messages.
    Runs in the current thread (call from a worker thread). Tool execution is
    dispatched to main_thread_runner (MainThreadToolRunner on main thread).
    messages: list of dicts with "role" and "content" (and optionally "tool_calls").
    Returns the final response text or an error string.
    """
    # #region agent log
    _debug_log("ai_agent_runner.py:run_agent", "run_agent entered", {"model_id": model_id, "num_messages": len(messages) if messages else 0}, "H5")
    # #endregion
    try:
        from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
    except ImportError as e:
        log.error("LangChain import failed: %s", e)
        return "Error: LangChain not available. Install langchain and langchain-openai (or other providers)."

    try:
        from classes.ai_llm_registry import get_model
        from classes.ai_openshot_tools import get_openshot_tools_for_langchain
    except ImportError as e:
        log.error("AI modules import failed: %s", e)
        return "Error: {}".format(e)

    llm = get_model(model_id)
    if not llm:
        return "Error: Could not load model '{}'. Check API keys in Preferences > AI.".format(model_id)

    raw_tools = get_openshot_tools_for_langchain()
    if main_thread_runner:
        tools = [_wrap_tool_for_main_thread(t, main_thread_runner) for t in raw_tools]
    else:
        tools = raw_tools

    tools_by_name = {getattr(t, "name", str(t)): t for t in tools}

    # Build LC message list from conversation
    lc_messages = [SystemMessage(content=SYSTEM_PROMPT)]
    for m in messages:
        role = m.get("role") or m.get("type", "")
        content = m.get("content", "") or ""
        if isinstance(content, list):
            content = content[0].get("text", "") if content else ""
        if role == "user":
            lc_messages.append(HumanMessage(content=content))
        elif role == "assistant" and content:
            lc_messages.append(AIMessage(content=content))

    if not lc_messages or not any(isinstance(m, HumanMessage) for m in lc_messages):
        return "Error: No message to send."

    try:
        llm_with_tools = llm.bind_tools(tools)
        max_iterations = 15
        for iteration in range(max_iterations):
            # #region agent log
            _debug_log("ai_agent_runner.py:run_agent", "before llm.invoke", {"iteration": iteration}, "H5")
            # #endregion
            response = llm_with_tools.invoke(lc_messages)
            # #region agent log
            _debug_log("ai_agent_runner.py:run_agent", "after llm.invoke", {"iteration": iteration}, "H5")
            # #endregion
            lc_messages.append(response)
            tool_calls = getattr(response, "tool_calls", None) or getattr(response, "additional_kwargs", {}).get("tool_calls", [])
            if not tool_calls:
                break
            for tc in tool_calls:
                name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", None)
                args = tc.get("args", {}) if isinstance(tc, dict) else getattr(tc, "args", {}) or {}
                tid = tc.get("id") if isinstance(tc, dict) else getattr(tc, "id", "") or ""
                if not isinstance(args, dict):
                    args = {}
                tool = tools_by_name.get(name)
                if not tool:
                    result = "Error: unknown tool {}".format(name)
                else:
                    # #region agent log
                    _debug_log("ai_agent_runner.py:run_agent", "before tool.invoke (blocks until main thread runs it)", {"tool_name": name}, "H3")
                    # #endregion
                    try:
                        result = tool.invoke(args)
                    except Exception as e:
                        log.error("Tool %s failed: %s", name, e)
                        result = "Error: {}".format(e)
                    # #region agent log
                    _debug_log("ai_agent_runner.py:run_agent", "after tool.invoke", {"tool_name": name}, "H3")
                    # #endregion
                lc_messages.append(ToolMessage(content=str(result), tool_call_id=tid))
        # Final response text: last AIMessage content
        for m in reversed(lc_messages):
            if isinstance(m, AIMessage):
                content = getattr(m, "content", None)
                if content and isinstance(content, str):
                    return content
                if content:
                    return str(content)
        return "Done."
    except Exception as e:
        log.error("Agent execution failed: %s", e, exc_info=True)
        return "Error: {}".format(e)


_main_thread_runner_cache = None


def create_main_thread_runner():
    """Create and register a MainThreadToolRunner with all Zenvi tools. Call from main thread."""
    from classes.ai_openshot_tools import get_openshot_tools_for_langchain
    runner = MainThreadToolRunner()
    runner.register_tools(get_openshot_tools_for_langchain())
    return runner


def set_main_thread_runner(runner):
    """Set the runner used by the agent. Call from main thread before sending a request."""
    global _main_thread_runner_cache
    _main_thread_runner_cache = runner


def get_main_thread_runner():
    """Return the runner set by the main thread, or None."""
    return _main_thread_runner_cache
