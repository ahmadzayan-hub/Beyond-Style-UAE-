"""Agent reasoning runtime.

One LLM loop per agent: the agent's role prompt plus its *granted* tool list
compile into a system prompt; the model proposes one JSON action per step;
every action executes through ``Kernel.invoke`` so grants and policies apply
to reasoned actions exactly as they do to scripted ones. A denial or grant
violation is fed back to the model as an observation, never bypassed —
the security model is unchanged by making agents think.

Protocol (model output, one JSON object per step):
    {"action": "tool", "tool": "<name>", "payload": {...}, "why": "..."}
    {"action": "final", "answer": "...", "data": {...}}
"""

from __future__ import annotations

import json
from typing import Any

from bsos.kernel.contracts import EscalationPending, GrantViolation, PolicyDenied


class AgentRuntime:
    def __init__(self, kernel, agent, llm, max_steps: int = 8):
        self.kernel = kernel
        self.agent = agent
        self.llm = llm
        self.max_steps = max_steps

    # ------------------------------------------------------------------
    def _granted_tools(self) -> list[dict[str, str]]:
        tools = []
        for name, skill in sorted(self.kernel.registry.all().items()):
            if self.agent.grant.permits(name) and self.agent.grant.permits(skill.required_grant):
                tools.append({"tool": name, "signature": skill.signature,
                              "description": skill.description})
        return tools

    def _system_prompt(self) -> str:
        tools = self._granted_tools()
        return (
            self.agent.system_prompt()
            + "\n\n## Tools you hold a grant for (the kernel rejects anything else)\n"
            + "\n".join(f"- {t['tool']}{t['signature']} — {t['description']}" for t in tools)
            + "\n\n## Protocol\nRespond with exactly one JSON object per turn:\n"
              '{"action":"tool","tool":"<name>","payload":{...},"why":"..."} to act, or\n'
              '{"action":"final","answer":"...","data":{...}} when done.\n'
              "Payloads must not contain file bytes, base64, data URIs or URLs to images.\n"
              "If a tool call is denied by policy, read the denial message and adapt."
        )

    @staticmethod
    def _parse(raw: str) -> dict[str, Any]:
        try:
            return json.loads(raw[raw.index("{"): raw.rindex("}") + 1])
        except (ValueError, json.JSONDecodeError):
            return {"action": "final", "answer": raw.strip()[:2000], "data": {"parse_error": True}}

    # ------------------------------------------------------------------
    def run(self, goal: str) -> dict[str, Any]:
        system = self._system_prompt()
        transcript: list[dict[str, Any]] = []
        observation = f"Goal: {goal}"
        self.kernel.ledger.append("agent_task", actor=self.agent.name,
                                  outcome="started", data={"goal": goal})
        for step in range(1, self.max_steps + 1):
            prompt = (
                system + "\n\n## Transcript so far\n"
                + json.dumps(transcript[-6:], ensure_ascii=False, default=str)
                + f"\n\n## Latest observation\n{observation}\n\nYour JSON:"
            )
            action = self._parse(self.llm.complete(prompt))

            if action.get("action") == "final":
                self.kernel.ledger.append("agent_task", actor=self.agent.name,
                                          outcome="final", data={"steps": step - 1})
                return {"agent": self.agent.name, "goal": goal, "steps": step - 1,
                        "answer": action.get("answer", ""), "data": action.get("data", {}),
                        "transcript": transcript}

            tool = str(action.get("tool", ""))
            payload = action.get("payload") or {}
            entry: dict[str, Any] = {"step": step, "tool": tool, "why": action.get("why", "")}
            try:
                result = self.kernel.invoke(self.agent.name, tool, payload)
                entry["result"] = result
                observation = json.dumps(result, ensure_ascii=False, default=str)[:4000]
            except (PolicyDenied, GrantViolation) as exc:
                entry["denied"] = str(exc)
                observation = f"DENIED: {exc}"
            except EscalationPending as exc:
                entry["escalated"] = str(exc)
                self.kernel.ledger.append("agent_task", actor=self.agent.name,
                                          outcome="paused_escalation",
                                          data={"escalation_id": exc.escalation_id})
                return {"agent": self.agent.name, "goal": goal, "steps": step,
                        "answer": f"paused: {exc}", "escalation_id": exc.escalation_id,
                        "transcript": [*transcript, entry]}
            except (ValueError, FileNotFoundError, TypeError) as exc:
                entry["error"] = str(exc)
                observation = f"ERROR: {exc}"
            transcript.append(entry)

        self.kernel.ledger.append("agent_task", actor=self.agent.name,
                                  outcome="max_steps", data={"goal": goal})
        return {"agent": self.agent.name, "goal": goal, "steps": self.max_steps,
                "answer": "stopped: max steps reached", "transcript": transcript}
