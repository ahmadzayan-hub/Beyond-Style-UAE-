"""Composition root: the one place adapters meet the kernel.

Everything else reaches adapters only through ``ToolContext.adapters``,
injected by the guard. Configuration comes from the environment (.env).
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

from bsos.adapters import AdapterRegistry
from bsos.agents import ALL_AGENTS
from bsos.kernel.bus import EventBus
from bsos.kernel.contracts import Paths
from bsos.kernel.guard import Kernel
from bsos.kernel.grants import GrantRegistry
from bsos.kernel.ledger import Ledger
from bsos.kernel.policy import PolicyEngine
from bsos.memory.domain import make_engine, session_factory
from bsos.memory.provenance import ProvenanceStore
from bsos.memory.vector import VectorStore
from bsos.skills import registry


def build_kernel(root: Path | None = None) -> Kernel:
    load_dotenv()
    root = Path(root or os.environ.get("BSOS_ROOT", ".")).resolve()
    paths = Paths.from_root(root)

    ledger = Ledger(paths.var / "ledger.jsonl")
    bus = EventBus()
    policy_engine = PolicyEngine(
        Path(__file__).resolve().parent.parent / "kernel" / "policies.yaml",
        ledger=ledger,
    )

    engine = make_engine(str(paths.var / "bsos.db"))
    db_factory = session_factory(engine)

    from bsos.memory.brain import SecondBrain

    adapters = AdapterRegistry(
        vector_store=VectorStore(paths.var / "vectors.db"),
        provenance=ProvenanceStore(paths.var / "provenance"),
        brain=SecondBrain(paths.var / "brain.db"),
    )

    from bsos.adapters.vision import sample_video_frames

    adapters.video_sampler = sample_video_frames

    # LLM: provider selection — `anthropic` (API key) or `ollama` (local).
    # Subscription chat plans have no programmatic API and cannot back this.
    provider = os.environ.get("BSOS_LLM_PROVIDER", "auto")
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if provider == "ollama" or (provider == "auto" and not anthropic_key
                                and os.environ.get("OLLAMA_MODEL")):
        from bsos.adapters.llm import OllamaLLM

        adapters.llm = OllamaLLM(
            base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"),
            model=os.environ.get("OLLAMA_MODEL", "llama3.2"),
        )
    elif anthropic_key:
        from bsos.adapters.llm import AnthropicLLM

        adapters.llm = AnthropicLLM(anthropic_key,
                                    model=os.environ.get("BSOS_LLM_MODEL", "claude-sonnet-5"))
    if adapters.llm is not None:
        from bsos.adapters.vision import LLMVisionExtractor

        adapters.vision = LLMVisionExtractor(adapters.llm)

    # Embedder for the originality gate: CLIP in production, dev fallback otherwise.
    try:
        from bsos.adapters.vision import ClipEmbedder

        adapters.embedder = ClipEmbedder()
    except Exception:
        from bsos.adapters.vision import DevPixelEmbedder

        adapters.embedder = DevPixelEmbedder()

    # Image generation: Nano Banana with a key; loud local-dev placeholder without.
    google_key = os.environ.get("GOOGLE_API_KEY", "")
    if google_key:
        from bsos.adapters.imagegen import NanoBananaProvider

        models = [m.strip() for m in os.environ.get("BSOS_IMAGEGEN_MODELS", "").split(",") if m.strip()]
        adapters.imagegen = NanoBananaProvider(google_key, allowed_models=models or None)
    else:
        from bsos.adapters.imagegen import LocalDevProvider

        adapters.imagegen = LocalDevProvider()

    # Graph API (P7's only lawful Instagram path).
    meta_token = os.environ.get("META_ACCESS_TOKEN", "")
    ig_user_id = os.environ.get("META_IG_USER_ID", "")
    if meta_token and ig_user_id:
        from bsos.adapters.graph_api import GraphClient, TokenBucket

        adapters.graph = GraphClient(
            meta_token, ig_user_id,
            bucket=TokenBucket(capacity=int(policy_engine.thresholds["graph_rate_limit_per_hour"])),
        )

    from bsos.kernel import metrics

    metrics.attach_to_bus(bus)

    grants = GrantRegistry()
    kernel = Kernel(registry, policy_engine, ledger, bus, grants, paths,
                    db_factory=db_factory, adapters=adapters)
    for agent in ALL_AGENTS:
        agent.register(kernel)

    ledger.append("kernel_start", actor="system", outcome="ok", data={
        "agents": [a.name for a in ALL_AGENTS],
        "skills": sorted(registry.all()),
        "embedder": adapters.embedder.describe(),
        "imagegen": type(adapters.imagegen).__name__,
        "graph_configured": adapters.graph is not None,
        "vision_configured": adapters.vision is not None,
    })
    return kernel
