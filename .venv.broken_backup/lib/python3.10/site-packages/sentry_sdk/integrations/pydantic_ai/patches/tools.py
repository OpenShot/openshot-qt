import sys
from functools import wraps

from sentry_sdk.integrations import DidNotEnable
import sentry_sdk
from sentry_sdk.utils import capture_internal_exceptions, reraise

from ..spans import execute_tool_span, update_execute_tool_span
from ..utils import _capture_exception, get_current_agent

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any

try:
    from pydantic_ai.mcp import MCPServer  # type: ignore

    HAS_MCP = True
except ImportError:
    HAS_MCP = False

try:
    from pydantic_ai._tool_manager import ToolManager  # type: ignore
    from pydantic_ai.exceptions import ToolRetryError  # type: ignore
except ImportError:
    raise DidNotEnable("pydantic-ai not installed")


def _patch_tool_execution() -> None:
    """
    Patch ToolManager._call_tool to create execute_tool spans.

    This is the single point where ALL tool calls flow through in pydantic_ai,
    regardless of toolset type (function, MCP, combined, wrapper, etc.).

    By patching here, we avoid:
    - Patching multiple toolset classes
    - Dealing with signature mismatches from instrumented MCP servers
    - Complex nested toolset handling
    """

    original_call_tool = ToolManager._call_tool

    @wraps(original_call_tool)
    async def wrapped_call_tool(
        self: "Any", call: "Any", *args: "Any", **kwargs: "Any"
    ) -> "Any":
        # Extract tool info before calling original
        name = call.tool_name
        tool = self.tools.get(name) if self.tools else None

        # Determine tool type by checking tool.toolset
        tool_type = "function"  # default
        if tool and HAS_MCP and isinstance(tool.toolset, MCPServer):
            tool_type = "mcp"

        # Get agent from contextvar
        agent = get_current_agent()

        if agent and tool:
            try:
                args_dict = call.args_as_dict()
            except Exception:
                args_dict = call.args if isinstance(call.args, dict) else {}

            # Create execute_tool span
            # Nesting is handled by isolation_scope() to ensure proper parent-child relationships
            with sentry_sdk.isolation_scope():
                with execute_tool_span(
                    name,
                    args_dict,
                    agent,
                    tool_type=tool_type,
                ) as span:
                    try:
                        result = await original_call_tool(
                            self,
                            call,
                            *args,
                            **kwargs,
                        )
                        update_execute_tool_span(span, result)
                        return result
                    except ToolRetryError as exc:
                        exc_info = sys.exc_info()
                        with capture_internal_exceptions():
                            # Avoid circular import due to multi-file integration structure
                            from sentry_sdk.integrations.pydantic_ai import (
                                PydanticAIIntegration,
                            )

                            integration = sentry_sdk.get_client().get_integration(
                                PydanticAIIntegration
                            )
                            if (
                                integration is not None
                                and integration.handled_tool_call_exceptions
                            ):
                                _capture_exception(exc, handled=True)
                        reraise(*exc_info)

        # No span context - just call original
        return await original_call_tool(
            self,
            call,
            *args,
            **kwargs,
        )

    ToolManager._call_tool = wrapped_call_tool
