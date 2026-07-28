"""End-to-end: ingest → abstraction → synthesis → brief → generation → gate
→ spec → photograph → export, with the provenance chain intact."""

from __future__ import annotations

import json

from bsos.memory.domain import Asset, Concept

from conftest import build_corpus, ingest_asset, make_licence


def test_signal_to_catalogue(kernel):
    licence = make_licence(kernel)

    # 1-2. Ingest and abstract a corpus (checkpoint 2/3): sidecars on disk,
    # dedupe active, zero images reachable from the generation path.
    asset_ids = build_corpus(kernel, licence, count=42)
    assert len(list(kernel.paths.library_meta.glob("*.json"))) >= 42

    # Dedupe: re-dropping the same file is caught.
    from conftest import make_pattern_image

    make_pattern_image(kernel.paths.library_inbox / "dup.png", 0)
    dup = kernel.invoke("custodian", "library.ingest",
                        {"file_path": "dup.png", "licence_id": licence})
    assert dup["status"] == "duplicate_exact"

    # 4. Synthesis (checkpoint 4): a readable whitespace report.
    ws = kernel.invoke("analyst", "corpus.whitespace", {})
    assert ws["whitespace"], "expected at least one whitespace candidate"
    pick = ws["whitespace"][0]

    # 5. Brief with P3 enforcement (checkpoint 5).
    composed = kernel.invoke("designer", "concept.brief_compose", {
        "title": "whitespace concept", "seed_values": [pick["a"], pick["b"]],
    })
    brief_id = composed["brief_id"]
    check = kernel.invoke("designer", "concept.brief_provenance_check", {"brief_id": brief_id})
    if not check["promotable"]:
        # drop weak attributes exactly as the P3 contract requires
        weak = {p: m for p, m in composed["attributes"].items() if len(m["source_ids"]) < 3}
        kernel.invoke("designer", "concept.brief_drop_insufficient",
                      {"brief_id": brief_id, "offending": {k: v["source_ids"] for k, v in weak.items()}})
    from bsos.memory.domain import Brief

    with kernel.db_factory() as db:
        attributes = db.get(Brief, brief_id).attributes
    kernel.invoke("designer", "concept.brief_promote",
                  {"brief_id": brief_id, "attributes": attributes})

    # 6. Generation through the typed text-only path (checkpoint 6).
    prompt = kernel.invoke("designer", "concept.prompt_assemble", {"brief_id": brief_id})["prompt"]
    generated = kernel.invoke("designer", "generate.image",
                              {"prompt": prompt, "model": "local-dev", "brief_id": brief_id})
    concept_id = generated["concept_id"]

    # 7. Originality gate (checkpoint 7).
    gate = kernel.invoke("designer", "originality.gate", {"concept_id": concept_id})
    assert gate["passed"], gate
    kernel.invoke("designer", "concept.promote", {
        "concept_id": concept_id, "approver": "owner",
        "max_similarity": gate["max_similarity"],
    })

    # 8. Workshop spec, pricing floor, photograph, export (checkpoint 8).
    spec = kernel.invoke("producer", "spec.compose", {
        "concept_id": concept_id,
        "components": [{"part": "pendant body"}, {"part": "chain"}],
    })
    spec_id = spec["spec_id"]
    kernel.invoke("producer", "spec.complexity_band", {"spec_id": spec_id, "band": "A"})
    price = kernel.invoke("producer", "pricing.price_band_map", {"spec_id": spec_id})
    assert price["starting_price_aed"] >= 265
    kernel.invoke("producer", "spec.open_questions",
                  {"spec_id": spec_id, "questions": ["clasp type?", "chain length options?"]})

    photo = ingest_asset(kernel, 90, licence, origin="workshop_photograph",
                         category="necklaces")
    export = kernel.invoke("publisher", "export.flat",
                           {"asset_ids": [photo["asset_id"]], "destination": "e2e"})
    assert export["files"] == 1

    # AI render still cannot leak into the same export path.
    with kernel.db_factory() as db:
        concept = db.get(Concept, concept_id)
        ai_asset = Asset(id="leaktest00000001", filename="x.png", path=concept.image_path,
                         sha256="e" * 64, origin="ai_generated")
        db.add(ai_asset)
        db.commit()
    import pytest

    from bsos.kernel.contracts import PolicyDenied

    with pytest.raises(PolicyDenied):
        kernel.invoke("publisher", "export.flat",
                      {"asset_ids": [photo["asset_id"], "leaktest00000001"]})

    # Provenance chain: generation → gate → approval, exportable as PDF.
    chain = kernel.adapters.provenance.chain(concept_id)
    assert [c["event"] for c in chain] == ["generation", "originality_gate", "approval"]
    assert chain[0]["data"]["prompt"] == prompt
    pdf = kernel.invoke("publisher", "export.provenance_pdf", {"concept_id": concept_id})
    assert json.loads(json.dumps(pdf))["chain_length"] == 3
