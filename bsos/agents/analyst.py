"""Analyst: corpus and trend synthesis."""

from bsos.agents.base import Agent
from bsos.kernel.grants import GrantSet

ANALYST = Agent(
    name="analyst",
    role="Corpus health, frequency, co-occurrence, whitespace, segments.",
    grant=GrantSet.of(
        allow=["corpus.*", "vector.*", "memory.domain.read"],
        deny=["library.ingest", "generate.*"],
    ),
    prompt_file="analyst.md",
)
