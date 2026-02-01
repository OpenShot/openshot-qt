import copy
import time
from functools import wraps

from sentry_sdk.integrations import DidNotEnable

from ..spans import ai_client_span, update_ai_client_span

import sentry_sdk
from sentry_sdk.consts import SPANDATA
from sentry_sdk.utils import logger
from sentry_sdk.tracing import BAGGAGE_HEADER_NAME
from sentry_sdk.tracing_utils import (
    should_propagate_trace,
    add_sentry_baggage_to_headers,
)

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any, Callable, Optional
    from sentry_sdk.tracing import Span

try:
    import agents
    from agents.tool import HostedMCPTool
except ImportError:
    raise DidNotEnable("OpenAI Agents not installed")


def _set_response_model_on_agent_span(
    agent: "agents.Agent", response_model: "Optional[str]"
) -> None:
    """Set the response model on the agent's invoke_agent span if available."""
    if response_model:
        agent_span = getattr(agent, "_sentry_agent_span", None)
        if agent_span:
            agent_span.set_data(SPANDATA.GEN_AI_RESPONSE_MODEL, response_model)


def _inject_trace_propagation_headers(
    hosted_tool: "HostedMCPTool", span: "Span"
) -> None:
    headers = hosted_tool.tool_config.get("headers")
    if headers is None:
        headers = {}
        hosted_tool.tool_config["headers"] = headers

    mcp_url = hosted_tool.tool_config.get("server_url")
    if not mcp_url:
        return

    if should_propagate_trace(sentry_sdk.get_client(), mcp_url):
        for (
            key,
            value,
        ) in sentry_sdk.get_current_scope().iter_trace_propagation_headers(span=span):
            logger.debug(
                "[Tracing] Adding `{key}` header {value} to outgoing request to {mcp_url}.".format(
                    key=key, value=value, mcp_url=mcp_url
                )
            )
            if key == BAGGAGE_HEADER_NAME:
                add_sentry_baggage_to_headers(headers, value)
            else:
                headers[key] = value


def _create_get_model_wrapper(
    original_get_model: "Callable[..., Any]",
) -> "Callable[..., Any]":
    """
    Wraps the agents.Runner._get_model method to wrap the get_response method of the model to create a AI client span.
    """

    @wraps(
        original_get_model.__func__
        if hasattr(original_get_model, "__func__")
        else original_get_model
    )
    def wrapped_get_model(
        cls: "agents.Runner", agent: "agents.Agent", run_config: "agents.RunConfig"
    ) -> "agents.Model":
        # copy the model to double patching its methods. We use copy on purpose here (instead of deepcopy)
        # because we only patch its direct methods, all underlying data can remain unchanged.
        model = copy.copy(original_get_model(agent, run_config))

        # Capture the request model name for spans (agent.model can be None when using defaults)
        request_model_name = model.model if hasattr(model, "model") else str(model)
        agent._sentry_request_model = request_model_name

        # Wrap _fetch_response if it exists (for OpenAI models) to capture response model
        if hasattr(model, "_fetch_response"):
            original_fetch_response = model._fetch_response

            @wraps(original_fetch_response)
            async def wrapped_fetch_response(*args: "Any", **kwargs: "Any") -> "Any":
                response = await original_fetch_response(*args, **kwargs)
                if hasattr(response, "model") and response.model:
                    agent._sentry_response_model = str(response.model)
                return response

            model._fetch_response = wrapped_fetch_response

        original_get_response = model.get_response

        @wraps(original_get_response)
        async def wrapped_get_response(*args: "Any", **kwargs: "Any") -> "Any":
            mcp_tools = kwargs.get("tools")
            hosted_tools = []
            if mcp_tools is not None:
                hosted_tools = [
                    tool for tool in mcp_tools if isinstance(tool, HostedMCPTool)
                ]

            with ai_client_span(agent, kwargs) as span:
                for hosted_tool in hosted_tools:
                    _inject_trace_propagation_headers(hosted_tool, span=span)

                result = await original_get_response(*args, **kwargs)

                # Get response model captured from _fetch_response and clean up
                response_model = getattr(agent, "_sentry_response_model", None)
                if response_model:
                    delattr(agent, "_sentry_response_model")

                _set_response_model_on_agent_span(agent, response_model)
                update_ai_client_span(span, result, response_model)

            return result

        model.get_response = wrapped_get_response

        # Also wrap stream_response for streaming support
        if hasattr(model, "stream_response"):
            original_stream_response = model.stream_response

            @wraps(original_stream_response)
            async def wrapped_stream_response(*args: "Any", **kwargs: "Any") -> "Any":
                # Uses explicit try/finally instead of context manager to ensure cleanup
                # even if the consumer abandons the stream (GeneratorExit).
                span_kwargs = dict(kwargs)
                if len(args) > 0:
                    span_kwargs["system_instructions"] = args[0]
                if len(args) > 1:
                    span_kwargs["input"] = args[1]

                with ai_client_span(agent, span_kwargs) as span:
                    span.set_data(SPANDATA.GEN_AI_RESPONSE_STREAMING, True)

                    streaming_response = None
                    ttft_recorded = False
                    # Capture start time locally to avoid race conditions with concurrent requests
                    start_time = time.perf_counter()

                    async for event in original_stream_response(*args, **kwargs):
                        # Detect first content token (text delta event)
                        if not ttft_recorded and hasattr(event, "delta"):
                            ttft = time.perf_counter() - start_time
                            span.set_data(
                                SPANDATA.GEN_AI_RESPONSE_TIME_TO_FIRST_TOKEN, ttft
                            )
                            ttft_recorded = True

                        # Capture the full response from ResponseCompletedEvent
                        if hasattr(event, "response"):
                            streaming_response = event.response
                        yield event

                    # Update span with response data (usage, output, model)
                    if streaming_response:
                        response_model = (
                            str(streaming_response.model)
                            if hasattr(streaming_response, "model")
                            and streaming_response.model
                            else None
                        )
                        _set_response_model_on_agent_span(agent, response_model)
                        update_ai_client_span(span, streaming_response)

            model.stream_response = wrapped_stream_response

        return model

    return wrapped_get_model
