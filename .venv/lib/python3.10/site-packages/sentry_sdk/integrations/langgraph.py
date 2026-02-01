from functools import wraps
from typing import Any, Callable, List, Optional

import sentry_sdk
from sentry_sdk.ai.utils import (
    set_data_normalized,
    normalize_message_roles,
    truncate_and_annotate_messages,
)
from sentry_sdk.consts import OP, SPANDATA
from sentry_sdk.integrations import DidNotEnable, Integration
from sentry_sdk.scope import should_send_default_pii
from sentry_sdk.utils import safe_serialize


try:
    from langgraph.graph import StateGraph
    from langgraph.pregel import Pregel
except ImportError:
    raise DidNotEnable("langgraph not installed")


class LanggraphIntegration(Integration):
    identifier = "langgraph"
    origin = f"auto.ai.{identifier}"

    def __init__(self: "LanggraphIntegration", include_prompts: bool = True) -> None:
        self.include_prompts = include_prompts

    @staticmethod
    def setup_once() -> None:
        # LangGraph lets users create agents using a StateGraph or the Functional API.
        # StateGraphs are then compiled to a CompiledStateGraph. Both CompiledStateGraph and
        # the functional API execute on a Pregel instance. Pregel is the runtime for the graph
        # and the invocation happens on Pregel, so patching the invoke methods takes care of both.
        # The streaming methods are not patched, because due to some internal reasons, LangGraph
        # will automatically patch the streaming methods to run through invoke, and by doing this
        # we prevent duplicate spans for invocations.
        StateGraph.compile = _wrap_state_graph_compile(StateGraph.compile)
        if hasattr(Pregel, "invoke"):
            Pregel.invoke = _wrap_pregel_invoke(Pregel.invoke)
        if hasattr(Pregel, "ainvoke"):
            Pregel.ainvoke = _wrap_pregel_ainvoke(Pregel.ainvoke)


def _get_graph_name(graph_obj: "Any") -> "Optional[str]":
    for attr in ["name", "graph_name", "__name__", "_name"]:
        if hasattr(graph_obj, attr):
            name = getattr(graph_obj, attr)
            if name and isinstance(name, str):
                return name
    return None


def _normalize_langgraph_message(message: "Any") -> "Any":
    if not hasattr(message, "content"):
        return None

    parsed = {"role": getattr(message, "type", None), "content": message.content}

    for attr in [
        "name",
        "tool_calls",
        "function_call",
        "tool_call_id",
        "response_metadata",
    ]:
        if hasattr(message, attr):
            value = getattr(message, attr)
            if value is not None:
                parsed[attr] = value

    return parsed


def _parse_langgraph_messages(state: "Any") -> "Optional[List[Any]]":
    if not state:
        return None

    messages = None

    if isinstance(state, dict):
        messages = state.get("messages")
    elif hasattr(state, "messages"):
        messages = state.messages
    elif hasattr(state, "get") and callable(state.get):
        try:
            messages = state.get("messages")
        except Exception:
            pass

    if not messages or not isinstance(messages, (list, tuple)):
        return None

    normalized_messages = []
    for message in messages:
        try:
            normalized = _normalize_langgraph_message(message)
            if normalized:
                normalized_messages.append(normalized)
        except Exception:
            continue

    return normalized_messages if normalized_messages else None


def _wrap_state_graph_compile(f: "Callable[..., Any]") -> "Callable[..., Any]":
    @wraps(f)
    def new_compile(self: "Any", *args: "Any", **kwargs: "Any") -> "Any":
        integration = sentry_sdk.get_client().get_integration(LanggraphIntegration)
        if integration is None:
            return f(self, *args, **kwargs)
        with sentry_sdk.start_span(
            op=OP.GEN_AI_CREATE_AGENT,
            origin=LanggraphIntegration.origin,
        ) as span:
            compiled_graph = f(self, *args, **kwargs)

            compiled_graph_name = getattr(compiled_graph, "name", None)
            span.set_data(SPANDATA.GEN_AI_OPERATION_NAME, "create_agent")
            span.set_data(SPANDATA.GEN_AI_AGENT_NAME, compiled_graph_name)

            if compiled_graph_name:
                span.description = f"create_agent {compiled_graph_name}"
            else:
                span.description = "create_agent"

            if kwargs.get("model", None) is not None:
                span.set_data(SPANDATA.GEN_AI_REQUEST_MODEL, kwargs.get("model"))

            tools = None
            get_graph = getattr(compiled_graph, "get_graph", None)
            if get_graph and callable(get_graph):
                graph_obj = compiled_graph.get_graph()
                nodes = getattr(graph_obj, "nodes", None)
                if nodes and isinstance(nodes, dict):
                    tools_node = nodes.get("tools")
                    if tools_node:
                        data = getattr(tools_node, "data", None)
                        if data and hasattr(data, "tools_by_name"):
                            tools = list(data.tools_by_name.keys())

            if tools is not None:
                span.set_data(SPANDATA.GEN_AI_REQUEST_AVAILABLE_TOOLS, tools)

            return compiled_graph

    return new_compile


def _wrap_pregel_invoke(f: "Callable[..., Any]") -> "Callable[..., Any]":
    @wraps(f)
    def new_invoke(self: "Any", *args: "Any", **kwargs: "Any") -> "Any":
        integration = sentry_sdk.get_client().get_integration(LanggraphIntegration)
        if integration is None:
            return f(self, *args, **kwargs)

        graph_name = _get_graph_name(self)
        span_name = (
            f"invoke_agent {graph_name}".strip() if graph_name else "invoke_agent"
        )

        with sentry_sdk.start_span(
            op=OP.GEN_AI_INVOKE_AGENT,
            name=span_name,
            origin=LanggraphIntegration.origin,
        ) as span:
            if graph_name:
                span.set_data(SPANDATA.GEN_AI_PIPELINE_NAME, graph_name)
                span.set_data(SPANDATA.GEN_AI_AGENT_NAME, graph_name)

            span.set_data(SPANDATA.GEN_AI_OPERATION_NAME, "invoke_agent")

            # Store input messages to later compare with output
            input_messages = None
            if (
                len(args) > 0
                and should_send_default_pii()
                and integration.include_prompts
            ):
                input_messages = _parse_langgraph_messages(args[0])
                if input_messages:
                    normalized_input_messages = normalize_message_roles(input_messages)
                    scope = sentry_sdk.get_current_scope()
                    messages_data = truncate_and_annotate_messages(
                        normalized_input_messages, span, scope
                    )
                    if messages_data is not None:
                        set_data_normalized(
                            span,
                            SPANDATA.GEN_AI_REQUEST_MESSAGES,
                            messages_data,
                            unpack=False,
                        )

            result = f(self, *args, **kwargs)

            _set_response_attributes(span, input_messages, result, integration)

            return result

    return new_invoke


def _wrap_pregel_ainvoke(f: "Callable[..., Any]") -> "Callable[..., Any]":
    @wraps(f)
    async def new_ainvoke(self: "Any", *args: "Any", **kwargs: "Any") -> "Any":
        integration = sentry_sdk.get_client().get_integration(LanggraphIntegration)
        if integration is None:
            return await f(self, *args, **kwargs)

        graph_name = _get_graph_name(self)
        span_name = (
            f"invoke_agent {graph_name}".strip() if graph_name else "invoke_agent"
        )

        with sentry_sdk.start_span(
            op=OP.GEN_AI_INVOKE_AGENT,
            name=span_name,
            origin=LanggraphIntegration.origin,
        ) as span:
            if graph_name:
                span.set_data(SPANDATA.GEN_AI_PIPELINE_NAME, graph_name)
                span.set_data(SPANDATA.GEN_AI_AGENT_NAME, graph_name)

            span.set_data(SPANDATA.GEN_AI_OPERATION_NAME, "invoke_agent")

            input_messages = None
            if (
                len(args) > 0
                and should_send_default_pii()
                and integration.include_prompts
            ):
                input_messages = _parse_langgraph_messages(args[0])
                if input_messages:
                    normalized_input_messages = normalize_message_roles(input_messages)
                    scope = sentry_sdk.get_current_scope()
                    messages_data = truncate_and_annotate_messages(
                        normalized_input_messages, span, scope
                    )
                    if messages_data is not None:
                        set_data_normalized(
                            span,
                            SPANDATA.GEN_AI_REQUEST_MESSAGES,
                            messages_data,
                            unpack=False,
                        )

            result = await f(self, *args, **kwargs)

            _set_response_attributes(span, input_messages, result, integration)

            return result

    return new_ainvoke


def _get_new_messages(
    input_messages: "Optional[List[Any]]", output_messages: "Optional[List[Any]]"
) -> "Optional[List[Any]]":
    """Extract only the new messages added during this invocation."""
    if not output_messages:
        return None

    if not input_messages:
        return output_messages

    # only return the new messages, aka the output messages that are not in the input messages
    input_count = len(input_messages)
    new_messages = (
        output_messages[input_count:] if len(output_messages) > input_count else []
    )

    return new_messages if new_messages else None


def _extract_llm_response_text(messages: "Optional[List[Any]]") -> "Optional[str]":
    if not messages:
        return None

    for message in reversed(messages):
        if isinstance(message, dict):
            role = message.get("role")
            if role in ["assistant", "ai"]:
                content = message.get("content")
                if content and isinstance(content, str):
                    return content

    return None


def _extract_tool_calls(messages: "Optional[List[Any]]") -> "Optional[List[Any]]":
    if not messages:
        return None

    tool_calls = []
    for message in messages:
        if isinstance(message, dict):
            msg_tool_calls = message.get("tool_calls")
            if msg_tool_calls and isinstance(msg_tool_calls, list):
                tool_calls.extend(msg_tool_calls)

    return tool_calls if tool_calls else None


def _set_usage_data(span: "sentry_sdk.tracing.Span", messages: "Any") -> None:
    input_tokens = 0
    output_tokens = 0
    total_tokens = 0

    for message in messages:
        response_metadata = message.get("response_metadata")
        if response_metadata is None:
            continue

        token_usage = response_metadata.get("token_usage")
        if not token_usage:
            continue

        input_tokens += int(token_usage.get("prompt_tokens", 0))
        output_tokens += int(token_usage.get("completion_tokens", 0))
        total_tokens += int(token_usage.get("total_tokens", 0))

    if input_tokens > 0:
        span.set_data(SPANDATA.GEN_AI_USAGE_INPUT_TOKENS, input_tokens)

    if output_tokens > 0:
        span.set_data(SPANDATA.GEN_AI_USAGE_OUTPUT_TOKENS, output_tokens)

    if total_tokens > 0:
        span.set_data(
            SPANDATA.GEN_AI_USAGE_TOTAL_TOKENS,
            total_tokens,
        )


def _set_response_model_name(span: "sentry_sdk.tracing.Span", messages: "Any") -> None:
    if len(messages) == 0:
        return

    last_message = messages[-1]
    response_metadata = last_message.get("response_metadata")
    if response_metadata is None:
        return

    model_name = response_metadata.get("model_name")
    if model_name is None:
        return

    set_data_normalized(span, SPANDATA.GEN_AI_RESPONSE_MODEL, model_name)


def _set_response_attributes(
    span: "Any",
    input_messages: "Optional[List[Any]]",
    result: "Any",
    integration: "LanggraphIntegration",
) -> None:
    parsed_response_messages = _parse_langgraph_messages(result)
    new_messages = _get_new_messages(input_messages, parsed_response_messages)

    if new_messages is None:
        return

    _set_usage_data(span, new_messages)
    _set_response_model_name(span, new_messages)

    if not (should_send_default_pii() and integration.include_prompts):
        return

    llm_response_text = _extract_llm_response_text(new_messages)
    if llm_response_text:
        set_data_normalized(span, SPANDATA.GEN_AI_RESPONSE_TEXT, llm_response_text)
    elif new_messages:
        set_data_normalized(span, SPANDATA.GEN_AI_RESPONSE_TEXT, new_messages)
    else:
        set_data_normalized(span, SPANDATA.GEN_AI_RESPONSE_TEXT, result)

    tool_calls = _extract_tool_calls(new_messages)
    if tool_calls:
        set_data_normalized(
            span,
            SPANDATA.GEN_AI_RESPONSE_TOOL_CALLS,
            safe_serialize(tool_calls),
            unpack=False,
        )
