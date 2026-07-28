"""Originality gate: derivative concepts rejected, margin cases escalate."""

from __future__ import annotations

import shutil

import pytest

from bsos.kernel.contracts import EscalationPending
from bsos.memory.domain import Brief, Concept

from conftest import build_corpus, make_licence


def _make_concept(kernel, image_path: str) -> int:
    with kernel.db_factory() as db:
        brief = Brief(title="gate test", attributes={}, status="approved")
        db.add(brief)
        db.commit()
        db.refresh(brief)
        concept = Concept(brief_id=brief.id, prompt="p", model_id="local-dev",
                          image_path=image_path, origin="ai_generated")
        db.add(concept)
        db.commit()
        db.refresh(concept)
        return concept.id


def test_derivative_concept_is_rejected_with_nearest_three(kernel):
    licence = make_licence(kernel)
    asset_ids = build_corpus(kernel, licence, count=42)

    # Deliberately derivative: the "concept" is a byte-for-byte corpus image.
    from sqlmodel import select

    from bsos.memory.domain import Asset

    with kernel.db_factory() as db:
        source = db.exec(select(Asset).where(Asset.id == asset_ids[0])).one()
    copy_path = kernel.paths.exports_internal / "CONCEPT_ONLY_derivative.png"
    shutil.copy2(source.path, copy_path)
    concept_id = _make_concept(kernel, str(copy_path))

    result = kernel.invoke("designer", "originality.gate", {"concept_id": concept_id})
    assert result["passed"] is False
    assert result["max_similarity"] >= result["threshold"]
    assert len(result["nearest"]) == 3
    assert "similarity_above_threshold" in result["reasons"]
    assert "perceptual_hash_too_close" in result["reasons"]

    with kernel.db_factory() as db:
        assert db.get(Concept, concept_id).status == "gate_rejected"

    # Rejection is recorded in provenance, automatically.
    chain = kernel.adapters.provenance.chain(concept_id)
    assert chain[-1]["event"] == "originality_gate"
    assert chain[-1]["data"]["passed"] is False


def test_distinct_concept_passes(kernel):
    licence = make_licence(kernel)
    build_corpus(kernel, licence, count=42)
    result = kernel.invoke("designer", "generate.image", {
        "prompt": "an original bar pendant with wave-line engraving, brushed rose tone",
        "model": "local-dev", "brief_id": _brief_id(kernel),
    })
    gate = kernel.invoke("designer", "originality.gate", {"concept_id": result["concept_id"]})
    assert gate["passed"] is True, gate


def _brief_id(kernel) -> int:
    with kernel.db_factory() as db:
        brief = Brief(title="ok", attributes={}, status="approved")
        db.add(brief)
        db.commit()
        db.refresh(brief)
        return brief.id


def test_margin_pass_escalates_on_promotion(kernel):
    licence = make_licence(kernel)
    build_corpus(kernel, licence, count=42)
    result = kernel.invoke("designer", "generate.image", {
        "prompt": "an original charm cluster, organic curve, matte finish",
        "model": "local-dev", "brief_id": _brief_id(kernel),
    })
    concept_id = result["concept_id"]
    kernel.invoke("designer", "originality.gate", {"concept_id": concept_id})

    # Force a within-margin score on the promotion payload: threshold 0.86,
    # margin 0.03 → 0.845 passes the gate but must escalate for human review.
    with pytest.raises(EscalationPending) as excinfo:
        kernel.invoke("designer", "concept.promote", {
            "concept_id": concept_id, "approver": "owner", "max_similarity": 0.845,
        })
    esc = next(d for d in excinfo.value.decisions if d.action == "escalate")
    assert esc.policy_id == "E_GATE_MARGIN"

    promoted = kernel.invoke("designer", "concept.promote", {
        "concept_id": concept_id, "approver": "owner",
        "max_similarity": 0.845, "margin_reviewed": True,
    })
    assert promoted["status"] == "approved"
