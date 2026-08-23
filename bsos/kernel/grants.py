"""Capability scoping.

An agent registers with a ``GrantSet``: a list of allow patterns and a list of
explicit deny patterns over dotted tool names. Deny always wins. The guard
rejects any call whose tool name is not covered by the calling agent's grant
before the skill is ever reached — this, not prompt text, is the security
model.

Patterns: exact names (``originality.gate``) or trailing wildcards
(``graph.*``). A bare ``*`` is intentionally not supported: every agent must
enumerate what it can do.
"""

from __future__ import annotations

from dataclasses import dataclass, field


def _matches(pattern: str, tool: str) -> bool:
    if pattern == tool:
        return True
    if pattern.endswith(".*"):
        prefix = pattern[:-2]
        return tool == prefix or tool.startswith(prefix + ".")
    return False


@dataclass(frozen=True)
class GrantSet:
    allow: tuple[str, ...] = ()
    deny: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for pat in (*self.allow, *self.deny):
            if pat == "*":
                raise ValueError("bare '*' grants are forbidden; enumerate capabilities")

    def permits(self, tool: str) -> bool:
        if any(_matches(p, tool) for p in self.deny):
            return False
        return any(_matches(p, tool) for p in self.allow)

    @classmethod
    def of(cls, allow: list[str], deny: list[str] | None = None) -> "GrantSet":
        return cls(allow=tuple(allow), deny=tuple(deny or ()))


@dataclass
class GrantRegistry:
    """Agent name → GrantSet. Registration is one-shot; grants are immutable."""

    _grants: dict[str, GrantSet] = field(default_factory=dict)

    def register(self, agent: str, grant: GrantSet) -> None:
        if agent in self._grants:
            raise ValueError(f"agent '{agent}' already registered; grants are immutable")
        self._grants[agent] = grant

    def get(self, agent: str) -> GrantSet | None:
        return self._grants.get(agent)

    def permits(self, agent: str, tool: str) -> bool:
        grant = self._grants.get(agent)
        return grant is not None and grant.permits(tool)

    def all(self) -> dict[str, GrantSet]:
        return dict(self._grants)
