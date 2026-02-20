import sentry_sdk
from sentry_sdk.ai.utils import get_start_span_function

from ..consts import SPAN_ORIGIN

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import agents


def agent_workflow_span(agent: "agents.Agent") -> "sentry_sdk.tracing.Span":
    # Create a transaction or a span if an transaction is already active
    span = get_start_span_function()(
        name=f"{agent.name} workflow",
        origin=SPAN_ORIGIN,
    )

    return span
