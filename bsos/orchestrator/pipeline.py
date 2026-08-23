"""Pipeline orchestration: the single source of truth for the flow.

API routes stay thin — they translate HTTP to these calls. The planner's
canonical step list is consumed here (``next_actions``), so the plan, the
state machine, and what actually executes cannot drift apart.
"""

from __future__ import annotations

from typing import Any

from bsos.agents import DESIGNER
from bsos.kernel.contracts import PolicyDenied
from bsos.memory.domain import Brief, Run
from bsos.orchestrator.planner import PlannedStep, plan_concept_run
from bsos.orchestrator.state_machine import StateMachine


class PipelineOrchestrator:
    def __init__(self, kernel):
        self.kernel = kernel

    # ------------------------------------------------------------------
    def promote_brief(self, brief_id: int) -> dict[str, Any]:
        """Promote a brief; on P3 denial apply the drop-and-review contract."""
        with self.kernel.db_factory() as db:
            brief = db.get(Brief, brief_id)
            if brief is None:
                raise ValueError(f"brief '{brief_id}' not found")
            attributes = brief.attributes
        try:
            return DESIGNER.act(self.kernel, "concept.brief_promote",
                                {"brief_id": brief_id, "attributes": attributes})
        except PolicyDenied as exc:
            p3 = next((d for d in exc.decisions
                       if d.policy_id == "P3" and d.action == "deny"), None)
            if p3 is None:
                raise
            dropped = DESIGNER.act(self.kernel, "concept.brief_drop_insufficient", {
                "brief_id": brief_id,
                "offending": p3.detail["insufficient_provenance"],
            })
            return {"promoted": False, "p3": p3.__dict__, **dropped}

    def generate_and_gate(self, brief_id: int, model: str, style_notes: str = "",
                          run_id: int | None = None) -> dict[str, Any]:
        """prompt_assemble → generate → gate; gate rejections recorded on the run."""
        prompt = DESIGNER.act(self.kernel, "concept.prompt_assemble",
                              {"brief_id": brief_id, "style_notes": style_notes})["prompt"]
        generated = DESIGNER.act(self.kernel, "generate.image",
                                 {"prompt": prompt, "model": model, "brief_id": brief_id})
        gate = DESIGNER.act(self.kernel, "originality.gate",
                            {"concept_id": generated["concept_id"]})
        if run_id is not None and not gate.get("passed", False):
            with self.kernel.db_factory() as db:
                StateMachine(db).record_gate_rejection(run_id, gate)
        return {**generated, "gate": gate}

    # ------------------------------------------------------------------
    def next_actions(self, run_id: int, title: str = "", seed_values: list[str] | None = None,
                     model: str = "local-dev") -> dict[str, Any]:
        """Planned tool calls for the run's current stage, from the canonical plan."""
        with self.kernel.db_factory() as db:
            run = db.get(Run, run_id)
            if run is None:
                raise ValueError(f"run '{run_id}' not found")
            state = run.state
        plan = plan_concept_run(seed_values or [], title or f"run-{run_id}", model)
        steps = [self._step_dict(s) for s in plan if s.stage == state]
        return {"run_id": run_id, "state": state, "next_actions": steps,
                "human_gate": next((s.human_gate for s in plan
                                    if s.stage == state and s.human_gate), None)}

    @staticmethod
    def _step_dict(step: PlannedStep) -> dict[str, Any]:
        return {"stage": step.stage, "tool": step.tool,
                "payload_template": step.payload, "human_gate": step.human_gate}
