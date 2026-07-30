"""Calligrapher: the Design Studio's typography-first agent.

Spelling accuracy is never delegated to an image model — the Calligrapher
works exclusively through deterministic shaping, composition, and geometry
skills. It deliberately holds no generation, library, or export-catalogue
grants: concept imagery and publication belong to other agents, and the
studio's workshop files come only from the verified vector path.
"""

from bsos.agents.base import Agent
from bsos.kernel.grants import GrantSet

CALLIGRAPHER = Agent(
    name="calligrapher",
    role="Deterministic Arabic/Latin typography, Diwani-inspired composition, "
         "manufacturing validation and workshop file preparation.",
    grant=GrantSet.of(
        allow=["design.*", "brain.search"],
        deny=[
            "generate.image", "vision.extract", "library.*",
            "graph.*", "export.*", "asset.*",
        ],
    ),
    prompt_file="calligrapher.md",
)
