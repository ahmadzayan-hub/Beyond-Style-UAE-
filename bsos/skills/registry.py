"""Skill registry.

Skills are pure, single-purpose functions registered with a declared
signature, side-effect profile, required grant, and policy tags. The kernel
guard is the only caller: it resolves a tool name here *after* the grant
check and policy evaluation. Skills receive a ``ToolContext`` and never
import adapters directly (enforced by tests/test_import_graph.py).
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any, Callable

from bsos.kernel.contracts import ToolContext


@dataclass(frozen=True)
class SkillDef:
    name: str
    func: Callable[..., Any]
    required_grant: str
    tags: tuple[str, ...] = ()
    side_effects: str = "none"  # none | fs | db | fs+db | network | network+fs+db
    description: str = ""

    @property
    def signature(self) -> str:
        return str(inspect.signature(self.func))


class SkillRegistry:
    def __init__(self) -> None:
        self._skills: dict[str, SkillDef] = {}

    def register(
        self,
        name: str,
        required_grant: str,
        tags: tuple[str, ...] = (),
        side_effects: str = "none",
        description: str = "",
    ) -> Callable[[Callable], Callable]:
        def deco(func: Callable) -> Callable:
            if name in self._skills:
                raise ValueError(f"skill '{name}' already registered")
            params = list(inspect.signature(func).parameters)
            if not params or params[0] != "ctx":
                raise TypeError(f"skill '{name}' must take ToolContext as first parameter 'ctx'")
            self._skills[name] = SkillDef(
                name=name, func=func, required_grant=required_grant,
                tags=tuple(tags), side_effects=side_effects,
                description=description or (func.__doc__ or "").strip().split("\n")[0],
            )
            return func
        return deco

    def get(self, name: str) -> SkillDef | None:
        return self._skills.get(name)

    def all(self) -> dict[str, SkillDef]:
        return dict(self._skills)

    def dispatch(self, name: str, ctx: ToolContext) -> Any:
        skill = self._skills[name]
        return skill.func(ctx, **ctx.payload)


# The process-wide registry. Skill modules register into this at import time;
# bsos.skills.__init__ imports every skill module so a single
# `from bsos.skills.registry import registry` yields the full set.
registry = SkillRegistry()
