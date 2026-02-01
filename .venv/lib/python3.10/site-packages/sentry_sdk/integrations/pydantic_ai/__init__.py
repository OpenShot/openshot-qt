from sentry_sdk.integrations import DidNotEnable, Integration


try:
    import pydantic_ai  # type: ignore
except ImportError:
    raise DidNotEnable("pydantic-ai not installed")


from .patches import (
    _patch_agent_run,
    _patch_graph_nodes,
    _patch_model_request,
    _patch_tool_execution,
)


class PydanticAIIntegration(Integration):
    identifier = "pydantic_ai"
    origin = f"auto.ai.{identifier}"

    def __init__(
        self, include_prompts: bool = True, handled_tool_call_exceptions: bool = True
    ) -> None:
        """
        Initialize the Pydantic AI integration.

        Args:
            include_prompts: Whether to include prompts and messages in span data.
                Requires send_default_pii=True. Defaults to True.
            handled_tool_exceptions: Capture tool call exceptions that Pydantic AI
                internally prevents from bubbling up.
        """
        self.include_prompts = include_prompts
        self.handled_tool_call_exceptions = handled_tool_call_exceptions

    @staticmethod
    def setup_once() -> None:
        """
        Set up the pydantic-ai integration.

        This patches the key methods in pydantic-ai to create Sentry spans for:
        - Agent invocations (Agent.run methods)
        - Model requests (AI client calls)
        - Tool executions
        """
        _patch_agent_run()
        _patch_graph_nodes()
        _patch_model_request()
        _patch_tool_execution()
