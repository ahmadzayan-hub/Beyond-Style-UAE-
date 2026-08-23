"""Analyst skills: corpus building, health, and trend synthesis.

The Analyst works on attribute JSON only — it holds no grant that can touch
image bytes. Synthesis skills are tagged `synthesis`, so P4 (corpus floor)
blocks them until the corpus holds enough references across enough sources.
"""

from __future__ import annotations

import itertools
from collections import Counter, defaultdict
from typing import Any

from sqlmodel import select

from bsos.kernel.contracts import ToolContext
from bsos.memory.domain import CorpusRef
from bsos.skills.registry import registry

# Attribute paths that participate in trend statistics.
TREND_PATHS = (
    "form.silhouette", "form.dominant_geometry", "form.layering", "form.scale",
    "motif.primary", "motif.cultural_register", "motif.abstraction_level",
    "typography.script", "typography.style",
    "material_finish.apparent_metal", "material_finish.finish", "material_finish.stone_presence",
    "construction.apparent_technique", "construction.closure",
    "commercial.occasion", "commercial.gifting_signal", "commercial.perceived_tier",
    "commercial.target_segment",
)


def _get_path(attributes: dict, path: str) -> str:
    section, key = path.split(".", 1)
    value = (attributes.get(section) or {}).get(key, "")
    return str(value).strip().lower() if value else ""


@registry.register("corpus.add", required_grant="corpus.add", tags=(), side_effects="db",
                   description="Add an abstracted reference (attribute JSON + source ids) to the corpus.")
def corpus_add(ctx: ToolContext, source_id: str, source_handle: str,
               attributes: dict, url: str = "", segment: str = "") -> dict[str, Any]:
    existing = ctx.db.exec(select(CorpusRef).where(CorpusRef.source_id == source_id)).first()
    if existing:
        return {"corpus_ref_id": existing.id, "status": "already_present"}
    ref = CorpusRef(source_id=source_id, source_handle=source_handle,
                    attributes=attributes, url=url, segment=segment)
    ctx.db.add(ref)
    ctx.db.flush()
    return {"corpus_ref_id": ref.id, "status": "added"}


@registry.register("corpus.health", required_grant="corpus.health", tags=(),
                   description="Corpus size and source diversity vs the P4 floor.")
def corpus_health(ctx: ToolContext) -> dict[str, Any]:
    refs = ctx.db.exec(select(CorpusRef)).all()
    sources = {r.source_handle for r in refs}
    thresholds = ctx.kernel.policy_engine.thresholds
    min_refs = int(thresholds["corpus_min_references"])
    min_sources = int(thresholds["corpus_min_sources"])
    return {
        "references": len(refs), "required_references": min_refs,
        "sources": len(sources), "required_sources": min_sources,
        "floor_met": len(refs) >= min_refs and len(sources) >= min_sources,
        "shortfall": {
            "references": max(0, min_refs - len(refs)),
            "sources": max(0, min_sources - len(sources)),
        },
        "by_source": dict(Counter(r.source_handle for r in refs)),
    }


@registry.register("corpus.frequency_rank", required_grant="corpus.frequency_rank",
                   tags=("synthesis",),
                   description="Rank attribute values by corpus frequency.")
def frequency_rank(ctx: ToolContext, top_n: int = 15) -> dict[str, Any]:
    refs = ctx.db.exec(select(CorpusRef)).all()
    ranking: dict[str, list] = {}
    for path in TREND_PATHS:
        counts = Counter(v for r in refs if (v := _get_path(r.attributes, path)))
        ranking[path] = counts.most_common(top_n)
    return {"total_references": len(refs), "ranking": ranking}


@registry.register("corpus.cooccurrence", required_grant="corpus.cooccurrence",
                   tags=("synthesis",),
                   description="Co-occurrence matrix across attribute values.")
def cooccurrence_matrix(ctx: ToolContext, min_count: int = 2) -> dict[str, Any]:
    refs = ctx.db.exec(select(CorpusRef)).all()
    pair_counts: Counter = Counter()
    for r in refs:
        values = sorted({
            f"{path}={v}" for path in TREND_PATHS if (v := _get_path(r.attributes, path))
        })
        pair_counts.update(itertools.combinations(values, 2))
    pairs = [
        {"a": a, "b": b, "count": c}
        for (a, b), c in pair_counts.most_common()
        if c >= min_count
    ]
    return {"pairs": pairs, "total_references": len(refs)}


@registry.register("corpus.whitespace", required_grant="corpus.whitespace",
                   tags=("synthesis",),
                   description="Rare-but-plausible attribute combinations: the whitespace report.")
def whitespace_report(ctx: ToolContext, max_combo_count: int = 2,
                      min_component_count: int = 4, top_n: int = 20) -> dict[str, Any]:
    """Whitespace = pairs whose components are individually established but
    which rarely co-occur. A combination appearing 40 times is a saturated
    market, not an instruction to copy it."""
    refs = ctx.db.exec(select(CorpusRef)).all()
    value_counts: Counter = Counter()
    pair_counts: Counter = Counter()
    value_sources: dict[str, set] = defaultdict(set)
    for r in refs:
        values = sorted({
            f"{path}={v}" for path in TREND_PATHS if (v := _get_path(r.attributes, path))
        })
        value_counts.update(values)
        for val in values:
            value_sources[val].add(r.source_handle)
        pair_counts.update(itertools.combinations(values, 2))

    candidates = []
    established = [v for v, c in value_counts.items() if c >= min_component_count]
    for a, b in itertools.combinations(sorted(established), 2):
        if a.split("=")[0] == b.split("=")[0]:
            continue  # same attribute axis cannot combine
        combo = pair_counts.get((a, b), 0)
        if combo <= max_combo_count:
            candidates.append({
                "a": a, "b": b, "combo_count": combo,
                "a_count": value_counts[a], "b_count": value_counts[b],
                "a_sources": sorted(value_sources[a]), "b_sources": sorted(value_sources[b]),
                "opportunity_score": round(
                    (value_counts[a] * value_counts[b]) / (1 + combo), 2),
            })
    candidates.sort(key=lambda c: c["opportunity_score"], reverse=True)
    return {"whitespace": candidates[:top_n], "total_references": len(refs)}


@registry.register("corpus.segment_map", required_grant="corpus.segment_map",
                   tags=("synthesis",),
                   description="Distribution of references across commercial segments.")
def segment_map(ctx: ToolContext) -> dict[str, Any]:
    refs = ctx.db.exec(select(CorpusRef)).all()
    segments: dict[str, Counter] = defaultdict(Counter)
    for r in refs:
        seg = _get_path(r.attributes, "commercial.target_segment") or "unspecified"
        tier = _get_path(r.attributes, "commercial.perceived_tier") or "unspecified"
        occasion = _get_path(r.attributes, "commercial.occasion") or "unspecified"
        segments[seg]["total"] += 1
        segments[seg][f"tier:{tier}"] += 1
        segments[seg][f"occasion:{occasion}"] += 1
    return {"segments": {k: dict(v) for k, v in segments.items()}}


@registry.register("vector.search", required_grant="vector.search", tags=(),
                   description="Semantic search over corpus embeddings by reference key.")
def vector_search(ctx: ToolContext, key: str, top_k: int = 5) -> dict[str, Any]:
    store = ctx.adapters.require("vector_store")
    query = store.get(key)
    if query is None:
        raise ValueError(f"no embedding stored under '{key}'")
    return {"matches": [
        {"key": k, "similarity": round(s, 4)} for k, s in store.search(query, top_k=top_k)
    ]}


@registry.register("memory.domain.read", required_grant="memory.domain.read", tags=(),
                   description="Read-only domain queries for the Analyst.")
def memory_domain_read(ctx: ToolContext, table: str, limit: int = 100) -> dict[str, Any]:
    from bsos.memory import domain as dm

    models = {"corpusref": dm.CorpusRef, "brief": dm.Brief, "licence": dm.Licence}
    model = models.get(table.lower())
    if model is None:
        raise ValueError(f"table '{table}' is not readable through this skill")
    rows = ctx.db.exec(select(model).limit(limit)).all()
    return {"rows": [r.model_dump() for r in rows], "count": len(rows)}
