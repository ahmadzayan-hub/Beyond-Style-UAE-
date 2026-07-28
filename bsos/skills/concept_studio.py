"""Designer skills: brief composition, generation, originality gate.

The Designer never touches image bytes. Briefs are attribute JSON with
per-attribute source provenance; generation is a text prompt through the
typed imagegen adapter; the gate works on embeddings computed inside the
skill from the concept render on disk — the payload never carries an image,
and the Designer holds no grant that returns one.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlmodel import select

from bsos.kernel.contracts import ToolContext
from bsos.memory.domain import Asset, Brief, Concept, CorpusRef
from bsos.skills.registry import registry


@registry.register("concept.brief_compose", required_grant="concept.brief_compose",
                   tags=("synthesis",), side_effects="db",
                   description="Compose a draft brief from whitespace values with per-attribute provenance.")
def brief_compose(ctx: ToolContext, title: str, seed_values: list[str]) -> dict[str, Any]:
    """seed_values: entries like 'motif.primary=falcon' (whitespace picks)."""
    refs = ctx.db.exec(select(CorpusRef)).all()
    attributes: dict[str, dict] = {}
    for seed in seed_values:
        path, _, value = seed.partition("=")
        section, _, key = path.partition(".")
        supporting = sorted({
            r.source_id for r in refs
            if str((r.attributes.get(section) or {}).get(key, "")).strip().lower() == value.strip().lower()
        })
        attributes[path] = {"value": value, "source_ids": supporting}
    brief = Brief(title=title, attributes=attributes,
                  corpus_snapshot_id=f"corpus@{len(refs)}refs")
    ctx.db.add(brief)
    ctx.db.flush()
    return {"brief_id": brief.id, "attributes": attributes, "status": brief.status}


@registry.register("concept.brief_provenance_check", required_grant="concept.brief_provenance_check",
                   tags=(), description="Report per-attribute source counts against the P3 minimum.")
def brief_provenance_check(ctx: ToolContext, brief_id: int) -> dict[str, Any]:
    brief = ctx.db.get(Brief, brief_id)
    if brief is None:
        raise ValueError(f"brief '{brief_id}' not found")
    minimum = int(ctx.kernel.policy_engine.thresholds["provenance_min_sources"])
    report = {
        path: {"sources": len(set(meta.get("source_ids", []))), "required": minimum,
               "ok": len(set(meta.get("source_ids", []))) >= minimum}
        for path, meta in brief.attributes.items()
    }
    return {"brief_id": brief_id, "attributes": report,
            "promotable": all(v["ok"] for v in report.values())}


@registry.register("concept.brief_promote", required_grant="concept.brief_promote",
                   tags=("brief_promote",), side_effects="db",
                   description="Promote a brief to generation. P3/P4 evaluate in the guard.")
def brief_promote(ctx: ToolContext, brief_id: int, attributes: dict) -> dict[str, Any]:
    brief = ctx.db.get(Brief, brief_id)
    if brief is None:
        raise ValueError(f"brief '{brief_id}' not found")
    brief.status = "approved"
    ctx.db.add(brief)
    return {"brief_id": brief_id, "status": "approved"}


@registry.register("concept.brief_drop_insufficient", required_grant="concept.brief_drop_insufficient",
                   tags=(), side_effects="db",
                   description="Drop under-provenanced attributes after a P3 denial; return brief for review.")
def brief_drop_insufficient(ctx: ToolContext, brief_id: int, offending: dict) -> dict[str, Any]:
    brief = ctx.db.get(Brief, brief_id)
    if brief is None:
        raise ValueError(f"brief '{brief_id}' not found")
    kept = {k: v for k, v in brief.attributes.items() if k not in offending}
    dropped = {**brief.dropped_attributes,
               **{k: {"reason": "insufficient_provenance", "source_ids": offending[k]}
                  for k in offending if k in brief.attributes}}
    brief.attributes = kept
    brief.dropped_attributes = dropped
    brief.status = "review"
    ctx.db.add(brief)
    return {"brief_id": brief_id, "dropped": sorted(dropped), "status": "review"}


@registry.register("concept.prompt_assemble", required_grant="concept.prompt_assemble", tags=(),
                   description="Assemble the exact generation prompt from an approved brief.")
def prompt_assemble(ctx: ToolContext, brief_id: int, style_notes: str = "") -> dict[str, Any]:
    brief = ctx.db.get(Brief, brief_id)
    if brief is None:
        raise ValueError(f"brief '{brief_id}' not found")
    if brief.status != "approved":
        raise ValueError(f"brief '{brief_id}' is '{brief.status}', not approved")
    fragments = [
        "Original jewellery design concept for a Dubai personalised gifts atelier.",
        "Product photography style, single piece on neutral studio background.",
    ]
    for path, meta in sorted(brief.attributes.items()):
        fragments.append(f"{path.replace('_', ' ').replace('.', ': ')} — {meta['value']}.")
    if style_notes:
        fragments.append(style_notes)
    fragments.append("Design must be original: no existing brand's product, logo or hallmark.")
    return {"brief_id": brief_id, "prompt": " ".join(fragments)}


@registry.register("generate.image", required_grant="generate.image",
                   tags=("imagegen",), side_effects="fs+db",
                   description="Generate a concept render from text only. P1 guards the payload; "
                               "the adapter re-validates; output is CONCEPT_ONLY.")
def generate_image(ctx: ToolContext, prompt: str, model: str, brief_id: int) -> dict[str, Any]:
    provider = ctx.adapters.require("imagegen")
    result = provider.generate_image(prompt, model)

    concept = Concept(brief_id=brief_id, prompt=prompt, model_id=result.model_id,
                      origin="ai_generated", status="generated")
    ctx.db.add(concept)
    ctx.db.flush()

    # AI renders write only to exports/internal_concepts, CONCEPT_ONLY in name+metadata.
    import io

    from PIL import Image, PngImagePlugin

    out_dir = ctx.paths.exports_internal
    stamp = result.generated_at.replace(":", "").replace("-", "")[:16]
    path = out_dir / f"CONCEPT_ONLY_c{concept.id}_{stamp}.png"
    img = Image.open(io.BytesIO(result.image_bytes))
    meta = PngImagePlugin.PngInfo()
    meta.add_text("Comment", f"CONCEPT_ONLY | origin=ai_generated | model={result.model_id} "
                             f"({result.model_version}) | not for publication")
    img.save(path, "PNG", pnginfo=meta)
    concept.image_path = str(path)
    ctx.db.add(concept)

    brief = ctx.db.get(Brief, brief_id)
    prov = ctx.adapters.require("provenance")
    prov.append(concept.id, "generation", {
        "brief_id": brief_id,
        "corpus_snapshot_id": brief.corpus_snapshot_id if brief else "",
        "brief_attributes": brief.attributes if brief else {},
        "prompt": prompt,
        "model_id": result.model_id,
        "model_version": result.model_version,
        "image_file": path.name,
    })
    return {"concept_id": concept.id, "image_path": str(path),
            "model_id": result.model_id, "origin": "ai_generated"}


@registry.register("originality.gate", required_grant="originality.gate",
                   tags=(), side_effects="db",
                   description="Score a concept against every corpus reference; reject above threshold.")
def originality_gate(ctx: ToolContext, concept_id: int) -> dict[str, Any]:
    from bsos.skills.imaging import perceptual_hash, phash_distance

    concept = ctx.db.get(Concept, concept_id)
    if concept is None or not concept.image_path:
        raise ValueError(f"concept '{concept_id}' not found or has no render")

    thresholds = ctx.kernel.policy_engine.thresholds
    max_sim_threshold = float(thresholds["originality_max_similarity"])
    min_phash = int(thresholds["phash_min_distance"])

    embedder = ctx.adapters.require("embedder")
    store = ctx.adapters.require("vector_store")
    query = embedder.embed_image(Path(concept.image_path))
    if store.count("corpus") == 0:
        raise ValueError("no corpus embeddings present; gate cannot run")
    nearest = store.search(query, namespace="corpus", top_k=3)
    max_sim = nearest[0][1] if nearest else 0.0

    concept_phash = perceptual_hash(Path(concept.image_path))
    min_distance, nearest_phash_asset = None, None
    for asset in ctx.db.exec(select(Asset).where(Asset.phash != "")).all():
        d = int(phash_distance(concept_phash, asset.phash))
        if min_distance is None or d < min_distance:
            min_distance, nearest_phash_asset = d, asset.id

    similarity_fail = max_sim >= max_sim_threshold
    phash_fail = min_distance is not None and min_distance < min_phash
    passed = not (similarity_fail or phash_fail)

    result = {
        "concept_id": concept_id, "passed": passed,
        "max_similarity": round(max_sim, 4), "threshold": max_sim_threshold,
        "nearest": [{"key": k, "similarity": round(s, 4)} for k, s in nearest],
        "phash_min_distance": min_distance, "phash_threshold": min_phash,
        "nearest_phash_asset": nearest_phash_asset,
        "embedder": embedder.describe(),
        "reasons": [r for r, fail in
                    (("similarity_above_threshold", similarity_fail),
                     ("perceptual_hash_too_close", phash_fail)) if fail],
    }
    concept.gate_result = result
    concept.status = "gate_passed" if passed else "gate_rejected"
    ctx.db.add(concept)
    ctx.adapters.require("provenance").append(concept_id, "originality_gate", result)
    return result


@registry.register("concept.promote", required_grant="concept.promote",
                   tags=("concept_promote",), side_effects="db",
                   description="Approve a gate-passed concept for workshop spec. Margin cases escalate.")
def concept_promote(ctx: ToolContext, concept_id: int, approver: str,
                    max_similarity: float | None = None,
                    margin_reviewed: bool = False) -> dict[str, Any]:
    concept = ctx.db.get(Concept, concept_id)
    if concept is None:
        raise ValueError(f"concept '{concept_id}' not found")
    if concept.status != "gate_passed":
        raise ValueError(f"concept '{concept_id}' is '{concept.status}', not gate_passed")
    concept.status = "approved"
    ctx.db.add(concept)
    ctx.adapters.require("provenance").append(concept_id, "approval", {
        "approver": approver, "margin_reviewed": margin_reviewed,
        "gate_result": concept.gate_result,
    })
    return {"concept_id": concept_id, "status": "approved", "approver": approver}


@registry.register("concept.variation_batch", required_grant="concept.variation_batch",
                   tags=(), side_effects="fs+db",
                   description="Generate a batch of prompt variations through the kernel, one call each.")
def variation_batch(ctx: ToolContext, brief_id: int, base_prompt: str, model: str,
                    variations: list[str]) -> dict[str, Any]:
    max_rerolls = int(ctx.kernel.policy_engine.thresholds["max_originality_rerolls"])
    if len(variations) > max_rerolls + 1:
        raise ValueError(f"at most {max_rerolls + 1} variations per batch "
                         f"(max_originality_rerolls={max_rerolls})")
    results = []
    for suffix in variations:
        # Each variation is a full kernel invocation: grants and P1 re-apply.
        results.append(ctx.kernel.invoke(ctx.agent, "generate.image", {
            "prompt": f"{base_prompt} Variation: {suffix}",
            "model": model, "brief_id": brief_id,
        }))
    return {"generated": results, "count": len(results)}
