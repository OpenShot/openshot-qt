import sys
from functools import wraps

from sentry_sdk.consts import SPANDATA
from sentry_sdk.integrations import DidNotEnable
from sentry_sdk.utils import capture_internal_exceptions, reraise
from ..spans import (
    invoke_agent_span,
    end_invoke_agent_span,
    handoff_span,
)
from ..utils import _record_exception_on_span

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any, Optional

    from sentry_sdk.tracing import Span

try:
    import agents
except ImportError:
    raise DidNotEnable("OpenAI Agents not installed")


def _patch_agent_run() -> None:
    """
    Patches AgentRunner methods to create agent invocation spans.
    This directly patches the execution flow to track when agents start and stop.
    """

    # Store original methods
    original_run_single_turn = agents.run.AgentRunner._run_single_turn
    original_run_single_turn_streamed = agents.run.AgentRunner._run_single_turn_streamed
    original_execute_handoffs = agents._run_impl.RunImpl.execute_handoffs
    original_execute_final_output = agents._run_impl.RunImpl.execute_final_output

    def _has_active_agent_span(context_wrapper: "agents.RunContextWrapper") -> bool:
        """Check if there's an active agent span for this context"""
        return getattr(context_wrapper, "_sentry_current_agent", None) is not None

    def _get_current_agent(
        context_wrapper: "agents.RunContextWrapper",
    ) -> "Optional[agents.Agent]":
        """Get the current agent from context wrapper"""
        return getattr(context_wrapper, "_sentry_current_agent", None)

    def _close_streaming_workflow_span(agent: "Optional[agents.Agent]") -> None:
        """Close the workflow span for streaming executions if it exists."""
        if agent and hasattr(agent, "_sentry_workflow_span"):
            workflow_span = agent._sentry_workflow_span
            workflow_span.__exit__(*sys.exc_info())
            delattr(agent, "_sentry_workflow_span")

    def _maybe_start_agent_span(
        context_wrapper: "agents.RunContextWrapper",
        agent: "agents.Agent",
        should_run_agent_start_hooks: bool,
        span_kwargs: "dict[str, Any]",
        is_streaming: bool = False,
    ) -> "Optional[Span]":
        """
        Start an agent invocation span if conditions are met.
        Handles ending any existing span for a different agent.

        Returns the new span if started, or the existing span if conditions aren't met.
        """
        if not (should_run_agent_start_hooks and agent and context_wrapper):
            return getattr(context_wrapper, "_sentry_agent_span", None)

        # End any existing span for a different agent
        if _has_active_agent_span(context_wrapper):
            current_agent = _get_current_agent(context_wrapper)
            if current_agent and current_agent != agent:
                end_invoke_agent_span(context_wrapper, current_agent)

        # Store the agent on the context wrapper so we can access it later
        context_wrapper._sentry_current_agent = agent
        span = invoke_agent_span(context_wrapper, agent, span_kwargs)
        context_wrapper._sentry_agent_span = span
        agent._sentry_agent_span = span

        if is_streaming:
            span.set_data(SPANDATA.GEN_AI_RESPONSE_STREAMING, True)

        return span

    @wraps(
        original_run_single_turn.__func__
        if hasattr(original_run_single_turn, "__func__")
        else original_run_single_turn
    )
    async def patched_run_single_turn(
        cls: "agents.Runner", *args: "Any", **kwargs: "Any"
    ) -> "Any":
        """Patched _run_single_turn that creates agent invocation spans"""
        agent = kwargs.get("agent")
        context_wrapper = kwargs.get("context_wrapper")
        should_run_agent_start_hooks = kwargs.get("should_run_agent_start_hooks", False)

        span = _maybe_start_agent_span(
            context_wrapper, agent, should_run_agent_start_hooks, kwargs
        )

        try:
            result = await original_run_single_turn(*args, **kwargs)
        except Exception as exc:
            if span is not None and span.timestamp is None:
                _record_exception_on_span(span, exc)
                end_invoke_agent_span(context_wrapper, agent)
            reraise(*sys.exc_info())

        return result

    @wraps(
        original_execute_handoffs.__func__
        if hasattr(original_execute_handoffs, "__func__")
        else original_execute_handoffs
    )
    async def patched_execute_handoffs(
        cls: "agents.Runner", *args: "Any", **kwargs: "Any"
    ) -> "Any":
        """Patched execute_handoffs that creates handoff spans and ends agent span for handoffs"""

        context_wrapper = kwargs.get("context_wrapper")
        run_handoffs = kwargs.get("run_handoffs")
        agent = kwargs.get("agent")

        # Create Sentry handoff span for the first handoff (agents library only processes the first one)
        if run_handoffs:
            first_handoff = run_handoffs[0]
            handoff_agent_name = first_handoff.handoff.agent_name
            handoff_span(context_wrapper, agent, handoff_agent_name)

        # Call original method with all parameters
        try:
            result = await original_execute_handoffs(*args, **kwargs)
        except Exception:
            exc_info = sys.exc_info()
            with capture_internal_exceptions():
                _close_streaming_workflow_span(agent)
            reraise(*exc_info)
        finally:
            # End span for current agent after handoff processing is complete
            if agent and context_wrapper and _has_active_agent_span(context_wrapper):
                end_invoke_agent_span(context_wrapper, agent)

        return result

    @wraps(
        original_execute_final_output.__func__
        if hasattr(original_execute_final_output, "__func__")
        else original_execute_final_output
    )
    async def patched_execute_final_output(
        cls: "agents.Runner", *args: "Any", **kwargs: "Any"
    ) -> "Any":
        """Patched execute_final_output that ends agent span for final outputs"""

        agent = kwargs.get("agent")
        context_wrapper = kwargs.get("context_wrapper")
        final_output = kwargs.get("final_output")

        try:
            result = await original_execute_final_output(*args, **kwargs)
        finally:
            with capture_internal_exceptions():
                if (
                    agent
                    and context_wrapper
                    and _has_active_agent_span(context_wrapper)
                ):
                    end_invoke_agent_span(context_wrapper, agent, final_output)
                # For streaming, close the workflow span (non-streaming uses context manager in _create_run_wrapper)
                _close_streaming_workflow_span(agent)

        return result

    @wraps(
        original_run_single_turn_streamed.__func__
        if hasattr(original_run_single_turn_streamed, "__func__")
        else original_run_single_turn_streamed
    )
    async def patched_run_single_turn_streamed(
        cls: "agents.Runner", *args: "Any", **kwargs: "Any"
    ) -> "Any":
        """Patched _run_single_turn_streamed that creates agent invocation spans for streaming.

        Note: Unlike _run_single_turn which uses keyword-only arguments (*,),
        _run_single_turn_streamed uses positional arguments. The call signature is:
        _run_single_turn_streamed(
            streamed_result,              # args[0]
            agent,                        # args[1]
            hooks,                        # args[2]
            context_wrapper,              # args[3]
            run_config,                   # args[4]
            should_run_agent_start_hooks, # args[5]
            tool_use_tracker,             # args[6]
            all_tools,                    # args[7]
            server_conversation_tracker,  # args[8] (optional)
        )
        """
        streamed_result = args[0] if len(args) > 0 else kwargs.get("streamed_result")
        agent = args[1] if len(args) > 1 else kwargs.get("agent")
        context_wrapper = args[3] if len(args) > 3 else kwargs.get("context_wrapper")
        should_run_agent_start_hooks = bool(
            args[5]
            if len(args) > 5
            else kwargs.get("should_run_agent_start_hooks", False)
        )

        span_kwargs: "dict[str, Any]" = {}
        if streamed_result and hasattr(streamed_result, "input"):
            span_kwargs["original_input"] = streamed_result.input

        span = _maybe_start_agent_span(
            context_wrapper,
            agent,
            should_run_agent_start_hooks,
            span_kwargs,
            is_streaming=True,
        )

        try:
            result = await original_run_single_turn_streamed(*args, **kwargs)
        except Exception as exc:
            exc_info = sys.exc_info()
            with capture_internal_exceptions():
                if span is not None and span.timestamp is None:
                    _record_exception_on_span(span, exc)
                    end_invoke_agent_span(context_wrapper, agent)
                _close_streaming_workflow_span(agent)
            reraise(*exc_info)

        return result

    # Apply patches
    agents.run.AgentRunner._run_single_turn = classmethod(patched_run_single_turn)
    agents.run.AgentRunner._run_single_turn_streamed = classmethod(
        patched_run_single_turn_streamed
    )
    agents._run_impl.RunImpl.execute_handoffs = classmethod(patched_execute_handoffs)
    agents._run_impl.RunImpl.execute_final_output = classmethod(
        patched_execute_final_output
    )
