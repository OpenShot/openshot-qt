from sentry_sdk.integrations import DidNotEnable, Integration

from .patches import (
    _create_get_model_wrapper,
    _create_get_all_tools_wrapper,
    _create_run_wrapper,
    _create_run_streamed_wrapper,
    _patch_agent_run,
    _patch_error_tracing,
)

try:
    # "agents" is too generic. If someone has an agents.py file in their project
    # or another package that's importable via "agents", no ImportError would
    # be thrown and the integration would enable itself even if openai-agents is
    # not installed. That's why we're adding the second, more specific import
    # after it, even if we don't use it.
    import agents
    from agents.run import DEFAULT_AGENT_RUNNER

except ImportError:
    raise DidNotEnable("OpenAI Agents not installed")


def _patch_runner() -> None:
    # Create the root span for one full agent run (including eventual handoffs)
    # Note agents.run.DEFAULT_AGENT_RUNNER.run_sync is a wrapper around
    # agents.run.DEFAULT_AGENT_RUNNER.run. It does not need to be wrapped separately.
    agents.run.DEFAULT_AGENT_RUNNER.run = _create_run_wrapper(
        agents.run.DEFAULT_AGENT_RUNNER.run
    )

    # Patch streaming runner
    agents.run.DEFAULT_AGENT_RUNNER.run_streamed = _create_run_streamed_wrapper(
        agents.run.DEFAULT_AGENT_RUNNER.run_streamed
    )

    # Creating the actual spans for each agent run (works for both streaming and non-streaming).
    _patch_agent_run()


def _patch_model() -> None:
    agents.run.AgentRunner._get_model = classmethod(
        _create_get_model_wrapper(agents.run.AgentRunner._get_model),
    )


def _patch_tools() -> None:
    agents.run.AgentRunner._get_all_tools = classmethod(
        _create_get_all_tools_wrapper(agents.run.AgentRunner._get_all_tools),
    )


class OpenAIAgentsIntegration(Integration):
    identifier = "openai_agents"

    @staticmethod
    def setup_once() -> None:
        _patch_error_tracing()
        _patch_tools()
        _patch_model()
        _patch_runner()
