"""
Agent runner: builds a LangChain agent with the selected LLM and Flowcut tools,
runs it in a worker thread, and dispatches tool execution to the Qt main thread.
"""

import json
import threading
import time
from classes.logger import log


try:
    from PyQt5.QtCore import QObject, QMetaObject, Qt, Q_ARG, pyqtSignal, pyqtSlot
except ImportError:
    QObject = object
    QMetaObject = None
    Qt = None
    Q_ARG = None
    pyqtSignal = None
    pyqtSlot = lambda x: x


SYSTEM_PROMPT = """You are an AI assistant for Flowcut. You help users with video editing, effects, transitions, and general editing tasks. You can query project state and perform editing actions using the provided tools. When you use a tool, confirm briefly what you did. Respond concisely and practically.

When the user asks to "clip" or "split" without clearly choosing, ask: "Do you want to (1) clip the existing clip on the timeline at the playhead (split it into two), or (2) create a new clip from a file (by choosing a file and frame range)?" If they choose (1) or say "clip the current clip", "at the playhead", or "the one on the timeline": use slice_clip_at_playhead_tool. If they choose (2) or "create a new video/clip": use list_files_tool then split_file_add_clip_tool with file_id and start_frame, end_frame.

After using split_file_add_clip_tool, always ask: "Would you like this clip added to the timeline at the playhead?" If the user says yes, call add_clip_to_timeline_tool with no arguments. Never ask the user for a file ID or show file IDs in your reply; the app keeps context of the clip just created.

When the user asks to generate a video, create a video, make a video and add it to the timeline, or similar, use generate_video_and_add_to_timeline_tool with the user's description as the prompt. This tool supports multiple video generation services including Runware and Remotion - the service is configured in user Preferences > AI settings. When users mention "Remotion", "remotion", or ask to use Remotion specifically, still use this same tool as it will automatically use the configured service. If they specify a position (e.g. "at 30 seconds") or track, pass position_seconds and/or track; otherwise leave them empty for playhead and default track."""


class MainThreadToolRunner(QObject if QObject is not object else object):
    """
    Lives on the Qt main thread. Holds Flowcut tools and runs them when run_tool is invoked.
    Used by the worker thread via BlockingQueuedConnection to run tools on the main thread.

    Supports version context for isolated state execution in parallel tasks.
    """
    if pyqtSignal is not None:
        tool_completed = pyqtSignal(str, str)  # tool_name, result
        tool_started = pyqtSignal(str, str)    # tool_name, args_json
        plan_updated = pyqtSignal(str)         # plan JSON string for plan graph UI

    def __init__(self):
        if QObject is not object:
            super().__init__()
        self._tools = {}
        self.last_tool_result = None
        # Version context: version_id -> project_snapshot dict
        self._version_contexts = {}
        self._current_version_id = None

    def register_tools(self, tools_list):
        """Register a list of LangChain tools by name."""
        for t in tools_list:
            name = getattr(t, "name", None) or getattr(t, "__name__", str(t))
            self._tools[name] = t
        log.debug("Registered %d tools on main thread runner", len(self._tools))

    def set_version_context(self, version_id, project_snapshot):
        """
        Set version context for isolated state execution.

        Args:
            version_id: ID of the version
            project_snapshot: Deep copy of project state for this version
        """
        import copy
        self._version_contexts[version_id] = copy.deepcopy(project_snapshot)
        self._current_version_id = version_id
        log.debug(f"Set version context: {version_id}")

    def clear_version_context(self):
        """Clear the current version context."""
        self._current_version_id = None

    def get_version_state(self, version_id):
        """
        Get the current project state for a version.

        Args:
            version_id: ID of the version

        Returns:
            Deep copy of version's project state, or None if not found
        """
        import copy
        state = self._version_contexts.get(version_id)
        return copy.deepcopy(state) if state else None

    if QMetaObject is not None:
        @pyqtSlot(str, str, result=str)
        def run_tool(self, name, args_json):
            """Run a tool by name with JSON-serialized args. Called from worker via BlockingQueuedConnection."""
            if pyqtSignal is not None and hasattr(self, "tool_started"):
                self.tool_started.emit(name, args_json or "{}")

            import copy
            from classes.app import get_app
            app = get_app()

            # Version context: temporarily swap project state if in version context
            original_state = None
            if self._current_version_id and self._current_version_id in self._version_contexts:
                # Save original global state
                original_state = copy.deepcopy(app.project._data)
                # Load version's isolated state
                app.project._data = copy.deepcopy(self._version_contexts[self._current_version_id])
                log.debug(f"Swapped to version context: {self._current_version_id}")

            try:
                if hasattr(app, "updates") and hasattr(app.updates, "set_agent_context"):
                    app.updates.set_agent_context(True)
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
                    try:
                        from plan_graph import get_plan_builder
                        pb = get_plan_builder()
                        pb.add_step(name, args_json or "{}", self.last_tool_result)
                        if pyqtSignal is not None and hasattr(self, "plan_updated"):
                            self.plan_updated.emit(pb.get_plan_json_string())
                    except Exception:
                        pass
                    if pyqtSignal is not None and hasattr(self, "tool_completed"):
                        self.tool_completed.emit(name, self.last_tool_result)
                    return self.last_tool_result
                finally:
                    if hasattr(app, "updates") and hasattr(app.updates, "set_agent_context"):
                        app.updates.set_agent_context(False)

                    # Version context: save modified state back and restore global state
                    if original_state is not None:
                        # Save modified version state
                        self._version_contexts[self._current_version_id] = copy.deepcopy(app.project._data)
                        # Restore original global state
                        app.project._data = original_state
                        log.debug(f"Restored original state from version context: {self._current_version_id}")
            except Exception as e:
                log.error("MainThreadToolRunner.run_tool %s: %s", name, e, exc_info=True)
                self.last_tool_result = "Error: {}".format(e)
                if pyqtSignal is not None and hasattr(self, "tool_completed"):
                    self.tool_completed.emit(name, self.last_tool_result)

                # Restore original state on error
                if original_state is not None:
                    app.project._data = original_state
                    log.debug(f"Restored original state after error in version context: {self._current_version_id}")

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
        try:
            QMetaObject.invokeMethod(
                runner,
                "run_tool",
                Qt.BlockingQueuedConnection,
                Q_ARG(str, name),
                Q_ARG(str, args_json),
            )
            return getattr(runner, "last_tool_result", "Error: no result")
        except Exception as e:
            # Provide a clearer, actionable error than the Qt overload trace.
            try:
                runner_type = type(runner).__name__
            except Exception:
                runner_type = "<unknown>"
            msg = f"Error: tool dispatch failed ({runner_type}). {e}"
            log.error(msg, exc_info=True)
            return msg

    return StructuredTool.from_function(
        func=invoke_from_main_thread,
        name=name,
        description=desc,
        args_schema=args_schema,
    )


def run_agent_with_tools(
    model_id,
    messages,
    tools,
    main_thread_runner,
    system_prompt,
    max_iterations=15,
):
    """
    Run a LangChain agent with the given tools and system prompt.
    tools: list of LangChain tools (raw); they will be wrapped for main thread if main_thread_runner is set.
    Returns the final response text or an error string.
    """
    try:
        from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
    except ImportError as e:
        log.error("LangChain import failed: %s", e)
        return "Error: LangChain not available. Install langchain and langchain-openai (or other providers)."

    try:
        from classes.ai_llm_registry import get_model
    except ImportError as e:
        log.error("AI modules import failed: %s", e)
        return "Error: {}".format(e)

    llm = get_model(model_id)
    if not llm:
        return "Error: Could not load model '{}'. Check API keys in Preferences > AI.".format(model_id)

    if main_thread_runner:
        wrapped_tools = [_wrap_tool_for_main_thread(t, main_thread_runner) for t in tools]
    else:
        wrapped_tools = tools
    tools_by_name = {getattr(t, "name", str(t)): t for t in wrapped_tools}

    lc_messages = [SystemMessage(content=system_prompt)]
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
        llm_with_tools = llm.bind_tools(wrapped_tools)
        critical_error = None  # Track critical errors to return directly
        for iteration in range(max_iterations):
            response = llm_with_tools.invoke(lc_messages)
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
                    try:
                        result = tool.invoke(args)
                    except Exception as e:
                        log.error("Tool %s failed: %s", name, e)
                        result = "Error: {}".format(e)
                    
                    # Detect critical errors (installation/setup issues) and return them directly
                    result_str = str(result)
                    if result_str.startswith("Error:") and any(keyword in result_str for keyword in ["not installed", "Install", "install", "pip install", "npm install"]):
                        critical_error = result_str
                
                lc_messages.append(ToolMessage(content=str(result), tool_call_id=tid))
        
        # If we detected a critical error, return it directly without LLM rephrasing
        if critical_error:
            return critical_error
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


def run_agent(model_id, messages, main_thread_runner, timeout_seconds=120):
    """
    Run the LangChain agent with the given model_id and conversation messages.
    Uses the multi-agent root when available; otherwise runs the video agent with all tools.
    """
    try:
        from classes.ai_multi_agent.root_agent import run_root_agent
        return run_root_agent(model_id, messages, main_thread_runner)
    except Exception as e:
        log.debug("Multi-agent root not used: %s; falling back to single agent", e)
    from classes.ai_openshot_tools import get_openshot_tools_for_langchain
    return run_agent_with_tools(
        model_id=model_id,
        messages=messages,
        tools=get_openshot_tools_for_langchain(),
        main_thread_runner=main_thread_runner,
        system_prompt=SYSTEM_PROMPT,
    )


_main_thread_runner_cache = None


def create_main_thread_runner():
    """Create and register a MainThreadToolRunner with all Flowcut tools. Call from main thread."""
    from classes.ai_openshot_tools import get_openshot_tools_for_langchain
    runner = MainThreadToolRunner()
    runner.register_tools(get_openshot_tools_for_langchain())
    
    # Register Voice/Music stub tools
    try:
        from classes.ai_voice_music_tools import get_voice_music_tools_for_langchain
        runner.register_tools(get_voice_music_tools_for_langchain())
    except ImportError as e:
        log.debug("Voice/music tools not available: %s", e)
    
    # Register Suno music tools (so Music Agent can use them)
    try:
        from classes.ai_suno_music_tools import get_suno_music_tools_for_langchain
        runner.register_tools(get_suno_music_tools_for_langchain())
    except ImportError as e:
        log.debug("Suno music tools not available: %s", e)
    
    # Register Manim tools (so Manim Agent can use them)
    try:
        from classes.ai_manim_tools import get_manim_tools_for_langchain
        runner.register_tools(get_manim_tools_for_langchain())
    except ImportError as e:
        log.debug("Manim tools not available: %s", e)

    # Register TTS tools (so Voice/Music Agent can use them)
    try:
        from classes.ai_tts_tools import get_tts_tools_for_langchain
        runner.register_tools(get_tts_tools_for_langchain())
    except ImportError as e:
        log.debug("TTS tools not available: %s", e)

    # Register Director analysis tools (read-only for directors to analyze projects)
    try:
        from classes.ai_directors.director_tools import get_director_analysis_tools_for_langchain
        runner.register_tools(get_director_analysis_tools_for_langchain())
    except ImportError as e:
        log.debug("Director analysis tools not available: %s", e)

    # Register Product Launch tools (GitHub + Manim for product launch videos)
    try:
        from classes.ai_product_launch_tools import get_product_launch_tools_for_langchain
        runner.register_tools(get_product_launch_tools_for_langchain())
    except ImportError as e:
        log.debug("Product launch tools not available: %s", e)

    return runner


def set_main_thread_runner(runner):
    """Set the runner used by the agent. Call from main thread before sending a request."""
    global _main_thread_runner_cache
    _main_thread_runner_cache = runner


def get_main_thread_runner():
    """Return the runner set by the main thread, or None."""
    return _main_thread_runner_cache
