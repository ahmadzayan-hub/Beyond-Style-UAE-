"""Custodian: licensed asset custody."""

from bsos.agents.base import Agent
from bsos.kernel.grants import GrantSet

CUSTODIAN = Agent(
    name="custodian",
    role="Licensed asset custody: ingest, licence management, flagging, sidecars.",
    grant=GrantSet.of(
        allow=["graph.*", "library.*", "licence.*", "vision.extract", "vision.extract_video"],
        deny=["generate.*", "export.catalogue"],
    ),
    prompt_file="custodian.md",
)
