"""The guard: kernel middleware on every tool invocation.

There is exactly one path from an agent to a skill or adapter, and it runs
through ``Kernel.invoke``:

    resolve skill → grant check → policy evaluation (all logged, passes
    included) → escalation persistence → dispatch → outcome ledger entry

Nothing else constructs ``ToolContext.adapters``, so a skill reached any
other way has no adapter access at all.
"""

from __future__ import annotations

import time
import traceback
from typing import Any

from bsos.kernel.bus import EventBus
from bsos.kernel.contracts import (
    Decision,
    EscalationPending,
    GrantViolation,
    Paths,
    PolicyDenied,
    ToolContext,
)
from bsos.kernel.grants import GrantRegistry
from bsos.kernel.ledger import Ledger
from bsos.kernel.policy import PolicyEngine


class Kernel:
    def __init__(
        self,
        registry,  # SkillRegistry
        policy_engine: PolicyEngine,
        ledger: Ledger,
        bus: EventBus,
        grants: GrantRegistry,
        paths: Paths,
        db_factory=None,
        adapters=None,
    ):
        self.registry = registry
        self.policy_engine = policy_engine
        self.ledger = ledger
        self.bus = bus
        self.grants = grants
        self.paths = paths
        self.db_factory = db_factory
        self.adapters = adapters

    # ------------------------------------------------------------------
    def invoke(self, agent: str, tool: str, payload: dict[str, Any] | None = None,
               metadata: dict[str, Any] | None = None) -> Any:
        payload = payload or {}
        started = time.monotonic()
        skill = self.registry.get(tool)

        # 1. Unknown tool: reject before anything else.
        if skill is None:
            self._log_and_publish("tool_call", agent, tool, "rejected_unknown_tool", {})
            raise GrantViolation(agent, tool, f"unknown tool '{tool}'")

        # 2. Grant check: the agent's grant must permit the tool name AND the
        #    skill's own declared grant requirement.
        if not self.grants.permits(agent, tool) or not self.grants.permits(agent, skill.required_grant):
            self._log_and_publish(
                "grant_violation", agent, tool, "rejected",
                {"required_grant": skill.required_grant},
            )
            raise GrantViolation(agent, tool)

        db = self.db_factory() if self.db_factory else None
        try:
            ctx = ToolContext(
                agent=agent, tool=tool, payload=payload, paths=self.paths,
                db=db, adapters=self.adapters, kernel=self, metadata=metadata or {},
            )

            # 3. Policy evaluation — every applicable policy, passes included.
            decisions = self.policy_engine.evaluate(ctx, set(skill.tags))
            for d in decisions:
                self._log_and_publish(
                    "policy_evaluation", agent, tool, d.action,
                    {"policy_id": d.policy_id, "message": d.message, "detail": d.detail},
                )

            denies = [d for d in decisions if d.action == "deny"]
            if denies:
                self._log_and_publish(
                    "tool_call", agent, tool, "denied",
                    {"policies": [d.policy_id for d in denies],
                     "duration_ms": self._ms(started)},
                )
                raise PolicyDenied(decisions)

            escalations = [d for d in decisions if d.action == "escalate"]
            if escalations:
                esc_id = self._persist_escalation(db, escalations)
                self._log_and_publish(
                    "tool_call", agent, tool, "escalated",
                    {"policies": [d.policy_id for d in escalations],
                     "escalation_id": esc_id, "duration_ms": self._ms(started)},
                )
                raise EscalationPending(decisions, escalation_id=esc_id)

            # 4. Dispatch.
            try:
                result = skill.func(ctx, **payload)
            except (PolicyDenied, EscalationPending, GrantViolation):
                raise
            except TypeError as exc:
                # Typed signatures are part of enforcement (P1): reject, log, re-raise.
                self._log_and_publish(
                    "tool_call", agent, tool, "rejected_bad_signature",
                    {"error": str(exc), "duration_ms": self._ms(started)},
                )
                raise
            except Exception as exc:
                self._log_and_publish(
                    "tool_call", agent, tool, "error",
                    {"error": str(exc), "trace": traceback.format_exc(limit=4),
                     "duration_ms": self._ms(started)},
                )
                raise

            if db is not None:
                db.commit()
            self._log_and_publish(
                "tool_call", agent, tool, "ok",
                {"duration_ms": self._ms(started), "side_effects": skill.side_effects},
            )
            return result
        finally:
            if db is not None:
                db.close()

    # ------------------------------------------------------------------
    def _persist_escalation(self, db, decisions: list[Decision]) -> int | None:
        if db is None:
            return None
        from bsos.memory.domain import Escalation

        first = decisions[0]
        esc = Escalation(
            policy_id=first.policy_id, message=first.message,
            detail=first.detail, status="open",
        )
        db.add(esc)
        db.commit()
        db.refresh(esc)
        return esc.id

    def _log_and_publish(self, event_type: str, agent: str, tool: str,
                         outcome: str, data: dict[str, Any]) -> None:
        entry = self.ledger.append(
            event_type, actor=agent, outcome=outcome, data={"tool": tool, **data},
        )
        self.bus.publish(event_type, {
            "seq": entry["seq"], "ts": entry["ts"], "agent": agent,
            "tool": tool, "outcome": outcome, **data,
        })

    @staticmethod
    def _ms(started: float) -> int:
        return int((time.monotonic() - started) * 1000)
