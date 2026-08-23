"""Dispatcher: maps pipeline stages to the agent that owns them.

The dispatcher never calls a skill directly — it asks the owning agent to
act, and the agent acts through the kernel guard. Stage ownership mirrors
the grant table; dispatching a stage to the wrong agent fails on grants.
"""

from __future__ import annotations

from typing import Any

from bsos.agents import ANALYST, CUSTODIAN, DESIGNER, PRODUCER, PUBLISHER

STAGE_OWNERS = {
    "intake": CUSTODIAN,
    "abstraction": CUSTODIAN,
    "synthesis": ANALYST,
    "brief": DESIGNER,
    "generation": DESIGNER,
    "originality_gate": DESIGNER,
    "workshop_spec": PRODUCER,
    "prototype": PRODUCER,
    "photograph": CUSTODIAN,
    "catalogue_ready": PUBLISHER,
}


class Dispatcher:
    def __init__(self, kernel):
        self.kernel = kernel

    def dispatch(self, stage: str, tool: str, payload: dict[str, Any] | None = None,
                 metadata: dict[str, Any] | None = None) -> Any:
        agent = STAGE_OWNERS.get(stage)
        if agent is None:
            raise ValueError(f"unknown stage '{stage}'")
        return agent.act(self.kernel, tool, payload, metadata)
