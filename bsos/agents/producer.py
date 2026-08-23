"""Producer: workshop specification."""

from bsos.agents.base import Agent
from bsos.kernel.grants import GrantSet

PRODUCER = Agent(
    name="producer",
    role="Workshop specs: components, personalisation zones, complexity, price bands.",
    grant=GrantSet.of(
        allow=["spec.*", "pricing.*", "memory.domain.*", "brain.search"],
        deny=["generate.*", "export.*"],
    ),
    prompt_file="producer.md",
)
