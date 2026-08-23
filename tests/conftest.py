"""Shared fixtures: a fully wired kernel on a temp root with offline adapters."""

from __future__ import annotations

import hashlib
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from bsos.adapters import AdapterRegistry  # noqa: E402
from bsos.adapters.imagegen import LocalDevProvider  # noqa: E402
from bsos.adapters.vision import DevPixelEmbedder, validate_attributes  # noqa: E402
from bsos.agents import ALL_AGENTS  # noqa: E402
from bsos.kernel.bus import EventBus  # noqa: E402
from bsos.kernel.contracts import Paths  # noqa: E402
from bsos.kernel.grants import GrantRegistry  # noqa: E402
from bsos.kernel.guard import Kernel  # noqa: E402
from bsos.kernel.ledger import Ledger  # noqa: E402
from bsos.kernel.policy import PolicyEngine  # noqa: E402
from bsos.memory.domain import make_engine, session_factory  # noqa: E402
from bsos.memory.provenance import ProvenanceStore  # noqa: E402
from bsos.memory.vector import VectorStore  # noqa: E402
from bsos.skills import registry  # noqa: E402

POLICY_CONFIG = REPO_ROOT / "bsos" / "kernel" / "policies.yaml"

# Deterministic attribute pools so a fake corpus has realistic diversity.
_POOLS = {
    "form.silhouette": ["pendant drop", "cuff", "bar", "hoop", "charm cluster"],
    "form.dominant_geometry": ["circle", "teardrop", "rectangle", "organic curve"],
    "motif.primary": ["arabic name", "palm frond", "falcon", "wave line", "initial letter"],
    "motif.cultural_register": ["khaleeji", "contemporary", "classic", "minimal"],
    "material_finish.apparent_metal": ["yellow gold tone", "silver tone", "rose gold tone"],
    "material_finish.finish": ["high polish", "brushed", "matte"],
    "construction.apparent_technique": ["laser cut", "cast", "wire formed"],
    "commercial.occasion": ["birthday", "wedding", "eid", "graduation"],
    "commercial.perceived_tier": ["accessible", "mid", "premium"],
    "commercial.target_segment": ["young women", "mothers", "men", "kids"],
}


class FakeVisionExtractor:
    """Deterministic attribute extraction keyed on file bytes (offline tests)."""

    def extract_attributes(self, image_path: Path) -> dict:
        digest = hashlib.sha256(Path(image_path).read_bytes()).digest()
        data: dict = {}
        for i, (path, pool) in enumerate(_POOLS.items()):
            section, key = path.split(".")
            data.setdefault(section, {})[key] = pool[digest[i] % len(pool)]
        data.setdefault("typography", {})["present"] = bool(digest[15] % 2)
        data.setdefault("material_finish", {})["colour_palette"] = ["warm neutral"]
        return validate_attributes(data)


def make_test_kernel(tmp_path: Path) -> Kernel:
    from bsos.adapters.vision import sample_video_frames
    from bsos.memory.brain import SecondBrain

    paths = Paths.from_root(tmp_path)
    ledger = Ledger(paths.var / "ledger.jsonl")
    engine = make_engine(str(paths.var / "bsos.db"))
    adapters = AdapterRegistry(
        vector_store=VectorStore(paths.var / "vectors.db"),
        provenance=ProvenanceStore(paths.var / "provenance"),
        embedder=DevPixelEmbedder(),
        imagegen=LocalDevProvider(),
        vision=FakeVisionExtractor(),
        brain=SecondBrain(paths.var / "brain.db"),
        video_sampler=sample_video_frames,
    )
    kernel = Kernel(
        registry, PolicyEngine(POLICY_CONFIG, ledger=ledger), ledger, EventBus(),
        GrantRegistry(), paths, db_factory=session_factory(engine), adapters=adapters,
    )
    for agent in ALL_AGENTS:
        agent.register(kernel)
    return kernel


@pytest.fixture
def kernel(tmp_path):
    return make_test_kernel(tmp_path)


def make_licence(kernel: Kernel, licence_id: str = "LIC-TEST-001",
                 days_valid: int = 365, scope: str = "ingest,derive,export") -> str:
    doc = kernel.paths.var / f"{licence_id}.pdf"
    doc.write_bytes(b"%PDF-1.4 signed permission letter (test)")
    kernel.invoke("custodian", "licence.create", {
        "licence_id": licence_id, "licensor": "Test Supplier LLC", "scope": scope,
        "signed_doc_path": str(doc),
        "valid_from": (datetime.utcnow() - timedelta(days=1)).isoformat(),
        "valid_to": (datetime.utcnow() + timedelta(days=days_valid)).isoformat(),
    })
    return licence_id


def make_pattern_image(path: Path, index: int, size: int = 640) -> Path:
    """Distinct geometric pattern per index: stable phash separation."""
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (size, size), (245, 243, 239))
    draw = ImageDraw.Draw(img)
    step = 12 + (index % 7) * 9
    for offset in range(-size, size * 2, step):
        if index % 3 == 0:
            draw.line([(offset, 0), (offset + size // 2, size)], fill=(40 + index * 5 % 180, 60, 90), width=4)
        elif index % 3 == 1:
            draw.ellipse([offset % size - 40, (offset * 2) % size - 40,
                          offset % size + 40, (offset * 2) % size + 40],
                         outline=(90, 40 + index * 7 % 160, 70), width=3)
        else:
            draw.rectangle([offset % size, (offset // 2) % size,
                            offset % size + step, (offset // 2) % size + step],
                           outline=(70, 80, 40 + index * 11 % 150), width=3)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "PNG")
    return path


def ingest_asset(kernel: Kernel, index: int, licence_id: str,
                 source_handle: str = "", category: str = "necklaces",
                 origin: str = "manual_inbox") -> dict:
    name = f"asset_{index:03d}.png"
    make_pattern_image(kernel.paths.library_inbox / name, index)
    return kernel.invoke("custodian", "library.ingest", {
        "file_path": name, "licence_id": licence_id, "origin": origin,
        "source_handle": source_handle or f"supplier_{index % 14}",
        "category": category,
    })


def build_corpus(kernel: Kernel, licence_id: str, count: int = 42) -> list[str]:
    """Ingest `count` distinct assets and abstract them into the corpus."""
    asset_ids = []
    for i in range(count):
        result = ingest_asset(kernel, i, licence_id)
        aid = result["asset_id"]
        asset_ids.append(aid)
        extraction = kernel.invoke("custodian", "vision.extract", {"asset_id": aid})
        kernel.invoke("analyst", "corpus.add", {
            "source_id": aid, "source_handle": f"supplier_{i % 14}",
            "attributes": extraction["attributes"], "url": f"local://asset/{aid}",
        })
    return asset_ids
