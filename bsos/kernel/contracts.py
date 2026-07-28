"""Shared kernel contracts.

Everything an agent, skill, or policy needs to interact with the kernel is
defined here. Skills never import adapters directly — they receive them via
``ToolContext.adapters``, which only the guard populates. That indirection is
what the import-graph test enforces.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

Action = Literal["allow", "deny", "escalate"]


@dataclass
class Paths:
    """Filesystem roots the kernel and skills operate on."""

    root: Path
    library: Path
    library_originals: Path
    library_meta: Path
    library_inbox: Path
    corpus: Path
    exports: Path
    exports_internal: Path
    exports_catalogue: Path
    var: Path

    @classmethod
    def from_root(cls, root: Path) -> "Paths":
        root = Path(root)
        p = cls(
            root=root,
            library=root / "library",
            library_originals=root / "library" / "originals",
            library_meta=root / "library" / "meta",
            library_inbox=root / "library" / "inbox",
            corpus=root / "corpus",
            exports=root / "exports",
            exports_internal=root / "exports" / "internal_concepts",
            exports_catalogue=root / "exports" / "catalogue",
            var=root / "var",
        )
        for attr in (
            "library_originals",
            "library_meta",
            "library_inbox",
            "corpus",
            "exports_internal",
            "exports_catalogue",
            "var",
        ):
            getattr(p, attr).mkdir(parents=True, exist_ok=True)
        return p


@dataclass
class ToolContext:
    """Passed by the guard into every skill invocation."""

    agent: str
    tool: str
    payload: dict[str, Any]
    paths: Paths
    db: Any = None  # sqlmodel Session
    adapters: Any = None  # AdapterRegistry — only the guard sets this
    kernel: Any = None  # for kernel-mediated sub-invocations
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Decision:
    """Outcome of one policy evaluation for one tool call."""

    policy_id: str
    action: Action
    message: str = ""
    detail: dict[str, Any] = field(default_factory=dict)


class KernelError(Exception):
    pass


class GrantViolation(KernelError):
    """Tool call outside the agent's capability grant."""

    def __init__(self, agent: str, tool: str, message: str = ""):
        self.agent = agent
        self.tool = tool
        super().__init__(message or f"grant violation: agent '{agent}' has no grant for tool '{tool}'")


class PolicyDenied(KernelError):
    """A kernel policy denied the tool call."""

    def __init__(self, decisions: list[Decision]):
        self.decisions = decisions
        denies = [d for d in decisions if d.action == "deny"]
        super().__init__("; ".join(f"[{d.policy_id}] {d.message}" for d in denies) or "policy denied")


class EscalationPending(KernelError):
    """A policy paused the run pending a human decision."""

    def __init__(self, decisions: list[Decision], escalation_id: int | None = None):
        self.decisions = decisions
        self.escalation_id = escalation_id
        escs = [d for d in decisions if d.action == "escalate"]
        super().__init__("; ".join(f"[{d.policy_id}] {d.message}" for d in escs) or "escalation pending")
