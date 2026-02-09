"""
Agent runner: builds a LangChain agent with the selected LLM and Zenvi tools,
runs it in a worker thread, and dispatches tool execution to the Qt main thread.
"""

import json
import threading
import time
from classes.logger import log
from classes.ai_prompts import MAIN_SYSTEM_PROMPT


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


SYSTEM_PROMPT = MAIN_SYSTEM_PROMPT


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
                from classes.app import get_app
                app = get_app()
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
                    if pyqtSignal is not None and hasattr(self, "tool_completed"):
                        self.tool_completed.emit(name, self.last_tool_result)
                    return self.last_tool_result
                finally:
                    if hasattr(app, "updates") and hasattr(app.updates, "set_agent_context"):
                        app.updates.set_agent_context(False)
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

            # Guardrail: never ask for clip selection when selected-clip context is already attached.
            # Do this even if the model emitted tool calls, because some models include tool calls
            # but still respond with an (incorrect) request to select/provide a clip.
            try:
                last_user = None
                for mm in reversed(lc_messages):
                    if isinstance(mm, HumanMessage):
                        last_user = (mm.content or "") if hasattr(mm, "content") else ""
                        break
                assistant_text = (getattr(response, "content", "") or "") if response is not None else ""
                if isinstance(last_user, str) and isinstance(assistant_text, str):
                    user_l = last_user.lower()
                    has_clip_ctx = ("[selected timeline clip context]" in user_l) or ("@selected_clip" in user_l)
                    asst_l = assistant_text.lower()
                    asst_asks_for_clip = any(k in asst_l for k in [
                        "which clip",
                        "what clip",
                        "which video",
                        "what video",
                        "provide the clip",
                        "share the clip",
                        "upload the clip",
                        "attach the clip",
                        "select the clip",
                        "choose the clip",
                        "pick the clip",
                        "need you to select",
                        "please select",
                        "need the clip",
                        "need the video",
                        "send the clip",
                        "send the video",
                        "clip id",
                        "file path",
                    ])
                    if has_clip_ctx and asst_asks_for_clip:
                        cleaned = last_user
                        if "[Selected timeline clip context]" in cleaned and "[/Selected timeline clip context]" in cleaned:
                            start = cleaned.find("[Selected timeline clip context]")
                            end = cleaned.find("[/Selected timeline clip context]")
                            if start != -1 and end != -1 and end > start:
                                cleaned = (cleaned[:start] + cleaned[end + len("[/Selected timeline clip context]"):]).strip()
                        cleaned = cleaned.replace("@selected_clip", " ").replace("@Selected_clip", " ")
                        cl = cleaned.lower().strip()

                        if any(k in user_l for k in ["vidu", "runware", "v2v", "insert", "instert"]) or any(k in cl for k in ["insert", "instert", "add a moment", "add moment", "add an insert", "insert a moment"]):
                            insert_tool = tools_by_name.get("insert_vidu_v2v_clip_into_selected_clip_tool")
                            if insert_tool:
                                q = cleaned.strip(" .,:;\n\t") or last_user.strip()
                                result = insert_tool.invoke({"query": q, "fade_ms": "400"})
                                return result if isinstance(result, str) else str(result)
                        if any(k in user_l for k in ["slice", "split", "cut"]):
                            slice_tool = tools_by_name.get("slice_selected_clip_at_best_match_tool")
                            if slice_tool:
                                q = cleaned.strip(" .,:;\n\t") or last_user.strip()
                                result = slice_tool.invoke({"query": q})
                                return result if isinstance(result, str) else str(result)
                        if any(k in user_l for k in ["find", "search", "where", "when", "locate"]):
                            search_tool = tools_by_name.get("search_selected_clip_scenes_tool")
                            if search_tool:
                                q = cleaned.strip(" .,:;\n\t") or last_user.strip()
                                result = search_tool.invoke({"query": q, "top_k": 5})
                                return result if isinstance(result, str) else str(result)
            except Exception:
                pass

            if not tool_calls:
                # Guardrail for the root agent: if the user message is about a selected timeline clip,
                # the root must route to the video agent even if the LLM failed to call invoke_video_agent.
                try:
                    last_user = None
                    for mm in reversed(lc_messages):
                        if isinstance(mm, HumanMessage):
                            last_user = (mm.content or "") if hasattr(mm, "content") else ""
                            break
                    if isinstance(last_user, str):
                        user_l = last_user.lower()
                        has_clip_ctx = ("[selected timeline clip context]" in user_l) or ("@selected_clip" in user_l)
                        invoke_video = tools_by_name.get("invoke_video_agent")
                        if invoke_video and has_clip_ctx:
                            result = invoke_video.invoke({"task": last_user})
                            return result if isinstance(result, str) else str(result)
                except Exception:
                    pass

                # Low-reasoning guardrail: if user asked to slice/split the selected clip,
                # but the model asks for an exact time, force semantic slicing.
                try:
                    last_user = None
                    for mm in reversed(lc_messages):
                        if isinstance(mm, HumanMessage):
                            last_user = (mm.content or "") if hasattr(mm, "content") else ""
                            break
                    assistant_text = (getattr(response, "content", "") or "") if response is not None else ""
                    if isinstance(last_user, str) and isinstance(assistant_text, str):
                        user_l = last_user.lower()
                        asst_l = assistant_text.lower()
                        wants_slice = any(k in user_l for k in ["slice", "split", "cut in two", "cut into two"])
                        has_clip_ctx = ("[selected timeline clip context]" in user_l) or ("@selected_clip" in user_l)
                        asst_asks_for_clip = any(k in asst_l for k in [
                            "which clip",
                            "what clip",
                            "which video",
                            "what video",
                            "provide the clip",
                            "share the clip",
                            "upload the clip",
                            "attach the clip",
                            "select the clip",
                            "choose the clip",
                            "pick the clip",
                            "need you to select",
                            "please select",
                            "need the clip",
                            "need the video",
                            "send the clip",
                            "send the video",
                        ])
                        asst_asks_time = any(k in asst_l for k in [
                            "timestamp", "exact time", "specific time", "what time",
                            "exact moment", "in seconds", "at what", "provide the",
                            "need you to select", "select the clip", "confirm the selection",
                            "confirm that you want",
                        ])
                        tool = tools_by_name.get("slice_selected_clip_at_best_match_tool")
                        if tool and wants_slice and has_clip_ctx and asst_asks_time:
                            # Extract a semantic query from the user's request.
                            cleaned = last_user
                            if "[Selected timeline clip context]" in cleaned and "[/Selected timeline clip context]" in cleaned:
                                start = cleaned.find("[Selected timeline clip context]")
                                end = cleaned.find("[/Selected timeline clip context]")
                                if start != -1 and end != -1 and end > start:
                                    cleaned = (cleaned[:start] + cleaned[end + len("[/Selected timeline clip context]"):]).strip()
                            cleaned_l = cleaned.lower()
                            q = cleaned
                            if "when" in cleaned_l:
                                q = cleaned[cleaned_l.find("when") + len("when"):].strip()
                            elif "where" in cleaned_l:
                                q = cleaned[cleaned_l.find("where") + len("where"):].strip()
                            q = q.strip() or cleaned.strip()
                            result = tool.invoke({"query": q})
                            return result if isinstance(result, str) else str(result)

                        # Guardrail: if the assistant is asking the user to provide/select a clip,
                        # but the selected clip context is already attached, never ask again.
                        # Instead, run the most likely selected-clip tool based on intent.
                        if has_clip_ctx and asst_asks_for_clip:
                            cleaned = last_user
                            # Strip context blocks and tokens when extracting a semantic query.
                            if "[Selected timeline clip context]" in cleaned and "[/Selected timeline clip context]" in cleaned:
                                start = cleaned.find("[Selected timeline clip context]")
                                end = cleaned.find("[/Selected timeline clip context]")
                                if start != -1 and end != -1 and end > start:
                                    cleaned = (cleaned[:start] + cleaned[end + len("[/Selected timeline clip context]"):]).strip()
                            cleaned = cleaned.replace("@selected_clip", " ").replace("@Selected_clip", " ")
                            cl = cleaned.lower().strip()

                            # Pick tool by intent.
                            if any(k in user_l for k in ["vidu", "runware", "v2v", "insert", "instert"]) or any(k in cl for k in ["insert", "instert", "add a moment", "add moment", "add an insert", "insert a moment"]):
                                insert_tool = tools_by_name.get("insert_vidu_v2v_clip_into_selected_clip_tool")
                                if insert_tool:
                                    q = cleaned.strip(" .,:;\n\t") or last_user.strip()
                                    result = insert_tool.invoke({"query": q, "fade_ms": "400"})
                                    return result if isinstance(result, str) else str(result)
                            if any(k in user_l for k in ["slice", "split", "cut"]):
                                slice_tool = tools_by_name.get("slice_selected_clip_at_best_match_tool")
                                if slice_tool:
                                    q = cleaned.strip(" .,:;\n\t") or last_user.strip()
                                    result = slice_tool.invoke({"query": q})
                                    return result if isinstance(result, str) else str(result)
                            if any(k in user_l for k in ["find", "search", "where", "when", "locate"]):
                                search_tool = tools_by_name.get("search_selected_clip_scenes_tool")
                                if search_tool:
                                    q = cleaned.strip(" .,:;\n\t") or last_user.strip()
                                    result = search_tool.invoke({"query": q, "top_k": 5})
                                    return result if isinstance(result, str) else str(result)
                            return "Selected clip context is already attached. Tell me what you want to do within this clip (e.g., 'find where…', 'slice where…', or 'insert a 4s AI moment where…')."

                        # Guardrail: if user asked to insert/add an AI clip into @selected_clip,
                        # but the model didn't call tools (often due to typos like "instert"), force the v2v insert tool.
                        wants_insert = (
                            has_clip_ctx
                            and any(k in user_l for k in [
                                "insert",
                                "instert",
                                "insert clip",
                                "insert a clip",
                                "add a clip",
                                "add clip",
                                "add a moment",
                                "add moment",
                                "insert a moment",
                                "insert moment",
                            ])
                        )
                        insert_tool = tools_by_name.get("insert_vidu_v2v_clip_into_selected_clip_tool")
                        if insert_tool and wants_insert:
                            cleaned = last_user
                            if "[Selected timeline clip context]" in cleaned and "[/Selected timeline clip context]" in cleaned:
                                start = cleaned.find("[Selected timeline clip context]")
                                end = cleaned.find("[/Selected timeline clip context]")
                                if start != -1 and end != -1 and end > start:
                                    cleaned = (cleaned[:start] + cleaned[end + len("[/Selected timeline clip context]"):]).strip()
                            cleaned = cleaned.replace("@selected_clip", " ")
                            cleaned = cleaned.replace("@Selected_clip", " ")
                            cl = cleaned.lower().strip()
                            for lead in [
                                "instert a clip of",
                                "insert a clip of",
                                "insert a clip",
                                "instert a clip",
                                "insert a moment of",
                                "insert a moment",
                                "instert a moment",
                                "add a moment where",
                                "add moment where",
                                "insert clip of",
                                "instert clip of",
                                "add a clip where",
                                "add a clip of",
                                "add clip where",
                                "add clip of",
                                "add a clip",
                                "add clip",
                                "insert",
                                "instert",
                            ]:
                                if cl.startswith(lead):
                                    cleaned = cleaned[len(lead):].strip()
                                    cl = cleaned.lower().strip()
                                    break
                            if " where " in f" {cl} ":
                                idx = cl.find("where")
                                if idx != -1:
                                    cleaned = cleaned[idx + len("where"):].strip()
                            q = cleaned.strip(" .,:;\n\t")
                            if not q:
                                q = last_user.strip()
                            result = insert_tool.invoke({"query": q, "fade_ms": "400"})
                            return result if isinstance(result, str) else str(result)
                except Exception:
                    pass
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

                # Terminal tools: these perform heavy generation work and produce
                # a final user-facing result.  Return immediately instead of
                # letting the LLM loop again (which could re-invoke the tool and
                # create duplicate imports).
                _TERMINAL_TOOLS = {
                    "insert_vidu_v2v_clip_into_selected_clip_tool",
                    "generate_video_and_add_to_timeline_tool",
                    "generate_transition_clip_tool",
                    "generate_manim_video_tool",
                    # Root-level sub-agent invocations (prevent root from
                    # re-invoking the video agent after it already generated).
                    "invoke_video_agent",
                }
                if name in _TERMINAL_TOOLS and not str(result).startswith("Error:"):
                    return str(result)
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
