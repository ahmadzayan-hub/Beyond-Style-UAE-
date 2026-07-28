"""Planner: expands a goal into the fixed stage sequence with per-stage tools.

The pipeline order is not negotiable (see state_machine.STATES); the planner
only decides which tool calls occur inside each stage and carries their
payload templates. It performs no tool calls itself.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from bsos.orchestrator.state_machine import STATES


@dataclass
class PlannedStep:
    stage: str
    tool: str
    payload: dict[str, Any] = field(default_factory=dict)
    human_gate: str | None = None


def plan_concept_run(seed_values: list[str], title: str, model: str) -> list[PlannedStep]:
    """The canonical signal-to-catalogue plan for one concept."""
    steps = [
        PlannedStep("synthesis", "corpus.whitespace"),
        PlannedStep("brief", "concept.brief_compose",
                    {"title": title, "seed_values": seed_values}),
        PlannedStep("brief", "concept.brief_provenance_check", {}),
        PlannedStep("brief", "concept.brief_promote", {}, human_gate="brief_approved"),
        PlannedStep("generation", "concept.prompt_assemble", {}),
        PlannedStep("generation", "generate.image", {"model": model}),
        PlannedStep("originality_gate", "originality.gate", {}),
        PlannedStep("workshop_spec", "spec.compose", {}, human_gate="spec_approved"),
        PlannedStep("workshop_spec", "spec.open_questions", {}),
        PlannedStep("photograph", "library.ingest", {"origin": "workshop_photograph"},
                    human_gate="photograph_confirmed"),
        PlannedStep("catalogue_ready", "export.flat", {}),
    ]
    known = set(STATES)
    for step in steps:
        if step.stage not in known:
            raise ValueError(f"planned stage '{step.stage}' is not a pipeline state")
    return steps
