"""Designer: concept origination.

The Designer's denial of vision.extract and library.read_binary is
deliberate and load-bearing: abstraction happens in the Custodian; the
Designer receives attribute JSON only and has no code path to an image.
That is what makes P1 structural rather than aspirational.
"""

from bsos.agents.base import Agent
from bsos.kernel.grants import GrantSet

DESIGNER = Agent(
    name="designer",
    role="Original concept origination from abstracted attributes; text-only generation.",
    grant=GrantSet.of(
        allow=["generate.image", "concept.*", "originality.gate", "brain.search"],
        deny=[
            "vision.extract", "library.read_binary", "library.*",
            "graph.*", "export.*", "asset.*",
        ],
    ),
    prompt_file="designer.md",
)
