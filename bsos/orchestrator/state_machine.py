"""Run state machine. No skipping.

    intake → abstraction → synthesis → brief → generation
           → originality_gate → workshop_spec → prototype
           → photograph → catalogue_ready

Human decision gates halt the run and surface a decision card:
  - brief → generation (provenance counts per attribute)
  - any originality_gate rejection (nearest three + scores, max two rerolls)
  - workshop_spec → prototype (open questions listed)
  - photograph → catalogue_ready (uploaded workshop photograph required)

The transition to catalogue_ready re-checks origin=workshop_photograph here,
in the machine, not only in the UI — and the actual export is additionally
guarded by P5 in the kernel.
"""

from __future__ import annotations

from typing import Any

from bsos.memory.domain import Asset, Run, utcnow

STATES = (
    "intake", "abstraction", "synthesis", "brief", "generation",
    "originality_gate", "workshop_spec", "prototype", "photograph",
    "catalogue_ready",
)

# Transitions that require an explicit human decision recorded in `approvals`.
HUMAN_GATES = {
    ("brief", "generation"): "brief_approved",
    ("workshop_spec", "prototype"): "spec_approved",
    ("photograph", "catalogue_ready"): "photograph_confirmed",
}


class TransitionError(Exception):
    pass


class StateMachine:
    def __init__(self, db):
        self.db = db

    def create_run(self) -> Run:
        run = Run(state="intake", history=[{"state": "intake", "at": str(utcnow())}])
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        return run

    def advance(self, run_id: int, to_state: str,
                approvals: dict[str, Any] | None = None,
                payload: dict[str, Any] | None = None) -> Run:
        approvals = approvals or {}
        payload = payload or {}
        run = self.db.get(Run, run_id)
        if run is None:
            raise TransitionError(f"run '{run_id}' not found")
        if to_state not in STATES:
            raise TransitionError(f"unknown state '{to_state}'")
        current_idx, target_idx = STATES.index(run.state), STATES.index(to_state)
        if target_idx != current_idx + 1:
            raise TransitionError(
                f"illegal transition {run.state} → {to_state}: states advance one "
                "step at a time and never skip"
            )

        gate = HUMAN_GATES.get((run.state, to_state))
        if gate and not approvals.get(gate):
            raise TransitionError(
                f"transition {run.state} → {to_state} requires human approval '{gate}'"
            )

        if to_state == "catalogue_ready":
            self._require_workshop_photograph(run, payload)

        for key in ("brief_id", "concept_id", "spec_id"):
            if key in payload:
                setattr(run, key, payload[key])
        run.state = to_state
        run.history = [*run.history, {
            "state": to_state, "at": str(utcnow()),
            "approvals": {k: bool(v) for k, v in approvals.items()},
        }]
        run.updated_at = utcnow()
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        return run

    def record_gate_rejection(self, run_id: int, gate_result: dict[str, Any]) -> Run:
        """A gate rejection keeps the run at originality_gate and counts rerolls."""
        run = self.db.get(Run, run_id)
        if run is None:
            raise TransitionError(f"run '{run_id}' not found")
        rerolls = sum(1 for h in run.history if h.get("event") == "gate_rejected")
        run.history = [*run.history, {
            "event": "gate_rejected", "at": str(utcnow()),
            "max_similarity": gate_result.get("max_similarity"),
            "nearest": gate_result.get("nearest", []),
            "reroll_number": rerolls + 1,
        }]
        run.updated_at = utcnow()
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        return run

    def rerolls_used(self, run_id: int) -> int:
        run = self.db.get(Run, run_id)
        return sum(1 for h in (run.history if run else []) if h.get("event") == "gate_rejected")

    def _require_workshop_photograph(self, run: Run, payload: dict[str, Any]) -> None:
        photo_asset_id = payload.get("photo_asset_id")
        if not photo_asset_id:
            raise TransitionError(
                "catalogue_ready requires an uploaded photograph of the manufactured "
                "piece (photo_asset_id missing)"
            )
        asset = self.db.get(Asset, photo_asset_id)
        if asset is None:
            raise TransitionError(f"photograph asset '{photo_asset_id}' not found")
        if asset.origin != "workshop_photograph":
            raise TransitionError(
                f"asset '{photo_asset_id}' has origin '{asset.origin}'; "
                "catalogue_ready requires origin=workshop_photograph (P5)"
            )
