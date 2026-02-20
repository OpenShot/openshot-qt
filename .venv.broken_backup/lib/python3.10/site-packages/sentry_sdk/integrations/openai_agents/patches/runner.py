import sys
from functools import wraps

import sentry_sdk
from sentry_sdk.integrations import DidNotEnable
from sentry_sdk.utils import capture_internal_exceptions, reraise

from ..spans import agent_workflow_span, end_invoke_agent_span
from ..utils import _capture_exception, _record_exception_on_span

try:
    from agents.exceptions import AgentsException
except ImportError:
    raise DidNotEnable("OpenAI Agents not installed")

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any, AsyncIterator, Callable


def _create_run_wrapper(original_func: "Callable[..., Any]") -> "Callable[..., Any]":
    """
    Wraps the agents.Runner.run methods to create a root span for the agent workflow runs.

    Note agents.Runner.run_sync() is a wrapper around agents.Runner.run(),
    so it does not need to be wrapped separately.
    """

    @wraps(original_func)
    async def wrapper(*args: "Any", **kwargs: "Any") -> "Any":
        # Isolate each workflow so that when agents are run in asyncio tasks they
        # don't touch each other's scopes
        with sentry_sdk.isolation_scope():
            # Clone agent because agent invocation spans are attached per run.
            agent = args[0].clone()
            with agent_workflow_span(agent):
                args = (agent, *args[1:])
                try:
                    run_result = await original_func(*args, **kwargs)
                except AgentsException as exc:
                    exc_info = sys.exc_info()
                    with capture_internal_exceptions():
                        _capture_exception(exc)

                        context_wrapper = getattr(exc.run_data, "context_wrapper", None)
                        if context_wrapper is not None:
                            invoke_agent_span = getattr(
                                context_wrapper, "_sentry_agent_span", None
                            )

                            if (
                                invoke_agent_span is not None
                                and invoke_agent_span.timestamp is None
                            ):
                                _record_exception_on_span(invoke_agent_span, exc)
                                end_invoke_agent_span(context_wrapper, agent)
                    reraise(*exc_info)
                except Exception as exc:
                    exc_info = sys.exc_info()
                    with capture_internal_exceptions():
                        # Invoke agent span is not finished in this case.
                        # This is much less likely to occur than other cases because
                        # AgentRunner.run() is "just" a while loop around _run_single_turn.
                        _capture_exception(exc)
                    reraise(*exc_info)

                end_invoke_agent_span(run_result.context_wrapper, agent)
                return run_result

    return wrapper


def _create_run_streamed_wrapper(
    original_func: "Callable[..., Any]",
) -> "Callable[..., Any]":
    """
    Wraps the agents.Runner.run_streamed method to create a root span for streaming agent workflow runs.

    Unlike run(), run_streamed() returns immediately with a RunResultStreaming object
    while execution continues in a background task. The workflow span must stay open
    throughout the streaming operation and close when streaming completes or is abandoned.

    Note: We don't use isolation_scope() here because it uses context variables that
    cannot span async boundaries (the __enter__ and __exit__ would be called from
    different async contexts, causing ValueError).
    """

    @wraps(original_func)
    def wrapper(*args: "Any", **kwargs: "Any") -> "Any":
        # Clone agent because agent invocation spans are attached per run.
        agent = args[0].clone()

        # Start workflow span immediately (before run_streamed returns)
        workflow_span = agent_workflow_span(agent)
        workflow_span.__enter__()

        # Store span on agent for cleanup
        agent._sentry_workflow_span = workflow_span

        args = (agent, *args[1:])

        try:
            # Call original function to get RunResultStreaming
            run_result = original_func(*args, **kwargs)
        except Exception as exc:
            # If run_streamed itself fails (not the background task), clean up immediately
            workflow_span.__exit__(*sys.exc_info())
            _capture_exception(exc)
            raise

        def _close_workflow_span() -> None:
            if hasattr(agent, "_sentry_workflow_span"):
                workflow_span.__exit__(*sys.exc_info())
                delattr(agent, "_sentry_workflow_span")

        if hasattr(run_result, "stream_events"):
            original_stream_events = run_result.stream_events

            @wraps(original_stream_events)
            async def wrapped_stream_events(
                *stream_args: "Any", **stream_kwargs: "Any"
            ) -> "AsyncIterator[Any]":
                try:
                    async for event in original_stream_events(
                        *stream_args, **stream_kwargs
                    ):
                        yield event
                finally:
                    _close_workflow_span()

            run_result.stream_events = wrapped_stream_events

        if hasattr(run_result, "cancel"):
            original_cancel = run_result.cancel

            @wraps(original_cancel)
            def wrapped_cancel(*cancel_args: "Any", **cancel_kwargs: "Any") -> "Any":
                try:
                    return original_cancel(*cancel_args, **cancel_kwargs)
                finally:
                    _close_workflow_span()

            run_result.cancel = wrapped_cancel

        return run_result

    return wrapper
