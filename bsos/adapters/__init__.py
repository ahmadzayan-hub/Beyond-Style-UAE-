"""Adapters: the only code that talks to the outside world.

Skills never import this package (enforced by tests/test_import_graph.py).
The kernel guard injects an ``AdapterRegistry`` into ``ToolContext.adapters``;
that injection is the sole route from a skill to an adapter.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class AdapterRegistry:
    llm: Any = None
    vision: Any = None
    imagegen: Any = None
    graph: Any = None
    mcp: Any = None
    embedder: Any = None
    vector_store: Any = None  # memory.vector.VectorStore, kernel-injected
    provenance: Any = None  # memory.provenance.ProvenanceStore, kernel-injected
    brain: Any = None  # memory.brain.SecondBrain, kernel-injected
    video_sampler: Any = None  # vision.sample_video_frames or equivalent

    def require(self, name: str) -> Any:
        adapter = getattr(self, name, None)
        if adapter is None:
            raise RuntimeError(
                f"adapter '{name}' is not configured — see SETUP.md for the required keys"
            )
        return adapter
