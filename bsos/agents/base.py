"""Agent contract.

An agent is a name, a capability grant, and a role prompt. Compliance rules
do NOT live in the prompt — the kernel enforces them on the tool-call path.
An agent acts only through ``Kernel.invoke``, which rejects anything outside
its grant before a skill is reached.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from bsos.kernel.grants import GrantSet

PROMPTS_DIR = Path(__file__).parent / "prompts"


@dataclass(frozen=True)
class Agent:
    name: str
    role: str
    grant: GrantSet
    prompt_file: str

    def system_prompt(self) -> str:
        return (PROMPTS_DIR / self.prompt_file).read_text(encoding="utf-8")

    def register(self, kernel) -> None:
        kernel.grants.register(self.name, self.grant)

    def act(self, kernel, tool: str, payload: dict[str, Any] | None = None,
            metadata: dict[str, Any] | None = None) -> Any:
        """The single entry point for agent action: through the guard."""
        return kernel.invoke(self.name, tool, payload or {}, metadata)
