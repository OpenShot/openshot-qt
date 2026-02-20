import sentry_sdk
from sentry_sdk.consts import OP, SPANDATA

from ..consts import SPAN_ORIGIN

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import agents


def handoff_span(
    context: "agents.RunContextWrapper", from_agent: "agents.Agent", to_agent_name: str
) -> None:
    with sentry_sdk.start_span(
        op=OP.GEN_AI_HANDOFF,
        name=f"handoff from {from_agent.name} to {to_agent_name}",
        origin=SPAN_ORIGIN,
    ) as span:
        span.set_data(SPANDATA.GEN_AI_OPERATION_NAME, "handoff")
