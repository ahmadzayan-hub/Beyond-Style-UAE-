"""Publisher: export and publication guard."""

from bsos.agents.base import Agent
from bsos.kernel.grants import GrantSet

PUBLISHER = Agent(
    name="publisher",
    role="Catalogue export, manifests, provenance PDFs. P5 evaluates on every export.",
    grant=GrantSet.of(
        allow=["export.*", "manifest.*", "ledger.append"],
        deny=["generate.*", "library.ingest"],
    ),
    prompt_file="publisher.md",
)
