import sys
from functools import wraps

import sentry_sdk
from sentry_sdk.integrations import DidNotEnable
from sentry_sdk.utils import capture_internal_exceptions, reraise

from ..spans import invoke_agent_span, update_invoke_agent_span
from ..utils import _capture_exception, pop_agent, push_agent

from typing import TYPE_CHECKING

try:
    from pydantic_ai.agent import Agent  # type: ignore
except ImportError:
    raise DidNotEnable("pydantic-ai not installed")

if TYPE_CHECKING:
    from typing import Any, Callable, Optional


class _StreamingContextManagerWrapper:
    """Wrapper for streaming methods that return async context managers."""

    def __init__(
        self,
        agent: "Any",
        original_ctx_manager: "Any",
        user_prompt: "Any",
        model: "Any",
        model_settings: "Any",
        is_streaming: bool = True,
    ) -> None:
        self.agent = agent
        self.original_ctx_manager = original_ctx_manager
        self.user_prompt = user_prompt
        self.model = model
        self.model_settings = model_settings
        self.is_streaming = is_streaming
        self._isolation_scope: "Any" = None
        self._span: "Optional[sentry_sdk.tracing.Span]" = None
        self._result: "Any" = None

    async def __aenter__(self) -> "Any":
        # Set up isolation scope and invoke_agent span
        self._isolation_scope = sentry_sdk.isolation_scope()
        self._isolation_scope.__enter__()

        # Create invoke_agent span (will be closed in __aexit__)
        self._span = invoke_agent_span(
            self.user_prompt,
            self.agent,
            self.model,
            self.model_settings,
            self.is_streaming,
        )
        self._span.__enter__()

        # Push agent to contextvar stack after span is successfully created and entered
        # This ensures proper pairing with pop_agent() in __aexit__ even if exceptions occur
        push_agent(self.agent, self.is_streaming)

        # Enter the original context manager
        result = await self.original_ctx_manager.__aenter__()
        self._result = result
        return result

    async def __aexit__(self, exc_type: "Any", exc_val: "Any", exc_tb: "Any") -> None:
        try:
            # Exit the original context manager first
            await self.original_ctx_manager.__aexit__(exc_type, exc_val, exc_tb)

            # Update span with result if successful
            if exc_type is None and self._result and self._span is not None:
                update_invoke_agent_span(self._span, self._result)
        finally:
            # Pop agent from contextvar stack
            pop_agent()

            # Clean up invoke span
            if self._span:
                self._span.__exit__(exc_type, exc_val, exc_tb)

            # Clean up isolation scope
            if self._isolation_scope:
                self._isolation_scope.__exit__(exc_type, exc_val, exc_tb)


def _create_run_wrapper(
    original_func: "Callable[..., Any]", is_streaming: bool = False
) -> "Callable[..., Any]":
    """
    Wraps the Agent.run method to create an invoke_agent span.

    Args:
        original_func: The original run method
        is_streaming: Whether this is a streaming method (for future use)
    """

    @wraps(original_func)
    async def wrapper(self: "Any", *args: "Any", **kwargs: "Any") -> "Any":
        # Isolate each workflow so that when agents are run in asyncio tasks they
        # don't touch each other's scopes
        with sentry_sdk.isolation_scope():
            # Extract parameters for the span
            user_prompt = kwargs.get("user_prompt") or (args[0] if args else None)
            model = kwargs.get("model")
            model_settings = kwargs.get("model_settings")

            # Create invoke_agent span
            with invoke_agent_span(
                user_prompt, self, model, model_settings, is_streaming
            ) as span:
                # Push agent to contextvar stack after span is successfully created and entered
                # This ensures proper pairing with pop_agent() in finally even if exceptions occur
                push_agent(self, is_streaming)

                try:
                    result = await original_func(self, *args, **kwargs)

                    # Update span with result
                    update_invoke_agent_span(span, result)

                    return result
                except Exception as exc:
                    exc_info = sys.exc_info()
                    with capture_internal_exceptions():
                        _capture_exception(exc)
                    reraise(*exc_info)
                finally:
                    # Pop agent from contextvar stack
                    pop_agent()

    return wrapper


def _create_streaming_wrapper(
    original_func: "Callable[..., Any]",
) -> "Callable[..., Any]":
    """
    Wraps run_stream method that returns an async context manager.
    """

    @wraps(original_func)
    def wrapper(self: "Any", *args: "Any", **kwargs: "Any") -> "Any":
        # Extract parameters for the span
        user_prompt = kwargs.get("user_prompt") or (args[0] if args else None)
        model = kwargs.get("model")
        model_settings = kwargs.get("model_settings")

        # Call original function to get the context manager
        original_ctx_manager = original_func(self, *args, **kwargs)

        # Wrap it with our instrumentation
        return _StreamingContextManagerWrapper(
            agent=self,
            original_ctx_manager=original_ctx_manager,
            user_prompt=user_prompt,
            model=model,
            model_settings=model_settings,
            is_streaming=True,
        )

    return wrapper


def _create_streaming_events_wrapper(
    original_func: "Callable[..., Any]",
) -> "Callable[..., Any]":
    """
    Wraps run_stream_events method - no span needed as it delegates to run().

    Note: run_stream_events internally calls self.run() with an event_stream_handler,
    so the invoke_agent span will be created by the run() wrapper.
    """

    @wraps(original_func)
    async def wrapper(self: "Any", *args: "Any", **kwargs: "Any") -> "Any":
        # Just call the original generator - it will call run() which has the instrumentation
        try:
            async for event in original_func(self, *args, **kwargs):
                yield event
        except Exception as exc:
            exc_info = sys.exc_info()
            with capture_internal_exceptions():
                _capture_exception(exc)
            reraise(*exc_info)

    return wrapper


def _patch_agent_run() -> None:
    """
    Patches the Agent run methods to create spans for agent execution.

    This patches both non-streaming (run, run_sync) and streaming
    (run_stream, run_stream_events) methods.
    """

    # Store original methods
    original_run = Agent.run
    original_run_stream = Agent.run_stream
    original_run_stream_events = Agent.run_stream_events

    # Wrap and apply patches for non-streaming methods
    Agent.run = _create_run_wrapper(original_run, is_streaming=False)

    # Wrap and apply patches for streaming methods
    Agent.run_stream = _create_streaming_wrapper(original_run_stream)
    Agent.run_stream_events = _create_streaming_events_wrapper(
        original_run_stream_events
    )
