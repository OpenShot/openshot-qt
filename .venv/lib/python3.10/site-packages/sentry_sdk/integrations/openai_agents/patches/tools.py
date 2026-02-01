from functools import wraps

from sentry_sdk.integrations import DidNotEnable

from ..spans import execute_tool_span, update_execute_tool_span

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any, Callable

try:
    import agents
except ImportError:
    raise DidNotEnable("OpenAI Agents not installed")


def _create_get_all_tools_wrapper(
    original_get_all_tools: "Callable[..., Any]",
) -> "Callable[..., Any]":
    """
    Wraps the agents.Runner._get_all_tools method of the Runner class to wrap all function tools with Sentry instrumentation.
    """

    @wraps(
        original_get_all_tools.__func__
        if hasattr(original_get_all_tools, "__func__")
        else original_get_all_tools
    )
    async def wrapped_get_all_tools(
        cls: "agents.Runner",
        agent: "agents.Agent",
        context_wrapper: "agents.RunContextWrapper",
    ) -> "list[agents.Tool]":
        # Get the original tools
        tools = await original_get_all_tools(agent, context_wrapper)

        wrapped_tools = []
        for tool in tools:
            # Wrap only the function tools (for now)
            if tool.__class__.__name__ != "FunctionTool":
                wrapped_tools.append(tool)
                continue

            # Create a new FunctionTool with our wrapped invoke method
            original_on_invoke = tool.on_invoke_tool

            def create_wrapped_invoke(
                current_tool: "agents.Tool", current_on_invoke: "Callable[..., Any]"
            ) -> "Callable[..., Any]":
                @wraps(current_on_invoke)
                async def sentry_wrapped_on_invoke_tool(
                    *args: "Any", **kwargs: "Any"
                ) -> "Any":
                    with execute_tool_span(current_tool, *args, **kwargs) as span:
                        # We can not capture exceptions in tool execution here because
                        # `_on_invoke_tool` is swallowing the exception here:
                        # https://github.com/openai/openai-agents-python/blob/main/src/agents/tool.py#L409-L422
                        # And because function_tool is a decorator with `default_tool_error_function` set as a default parameter
                        # I was unable to monkey patch it because those are evaluated at module import time
                        # and the SDK is too late to patch it. I was also unable to patch `_on_invoke_tool_impl`
                        # because it is nested inside this import time code. As if they made it hard to patch on purpose...
                        result = await current_on_invoke(*args, **kwargs)
                        update_execute_tool_span(span, agent, current_tool, result)

                    return result

                return sentry_wrapped_on_invoke_tool

            wrapped_tool = agents.FunctionTool(
                name=tool.name,
                description=tool.description,
                params_json_schema=tool.params_json_schema,
                on_invoke_tool=create_wrapped_invoke(tool, original_on_invoke),
                strict_json_schema=tool.strict_json_schema,
                is_enabled=tool.is_enabled,
            )
            wrapped_tools.append(wrapped_tool)

        return wrapped_tools

    return wrapped_get_all_tools
