"""P6 (material claims), P7 (no scraping), P8 (context separation)."""

from __future__ import annotations

import pytest

from bsos.kernel.contracts import PolicyDenied
from bsos.memory.domain import Brief, Concept, Spec


def _spec_id(kernel) -> int:
    with kernel.db_factory() as db:
        brief = Brief(title="b", attributes={}, status="approved")
        db.add(brief)
        db.commit()
        db.refresh(brief)
        concept = Concept(brief_id=brief.id, status="approved")
        db.add(concept)
        db.commit()
        db.refresh(concept)
        spec = Spec(concept_id=concept.id)
        db.add(spec)
        db.commit()
        db.refresh(spec)
        return spec.id


def test_p6_material_claims_require_verified_source(kernel):
    spec_id = _spec_id(kernel)
    with pytest.raises(PolicyDenied) as excinfo:
        kernel.invoke("producer", "spec.material_set", {
            "spec_id": spec_id, "fields": {"metal": "silver", "purity": "925"},
        })
    d = next(d for d in excinfo.value.decisions if d.policy_id == "P6")
    assert set(d.detail["unverified_fields"]) == {"metal", "purity"}

    # The P6 contract: fields become pending_workshop_verification.
    pending = kernel.invoke("producer", "spec.material_pending",
                            {"spec_id": spec_id, "fields": d.detail["unverified_fields"]})
    assert pending["pending"] == ["metal", "purity"]

    result = kernel.invoke("producer", "spec.material_set", {
        "spec_id": spec_id, "fields": {"metal": "silver", "purity": "925"},
        "verified_source": "workshop assay note 2026-07-14",
    })
    assert result["applied"]["purity"] == "925"


def test_p7_scraping_paths_denied(kernel):
    for url in ("https://www.instagram.com/harf__tellyourstory/",
                "https://instagram.com/p/xyz/media",
                "https://scontent.cdninstagram.com/v/t51/img.jpg"):
        with pytest.raises(PolicyDenied) as excinfo:
            kernel.invoke("custodian", "graph.own_media", {"url": url})
        assert any(d.policy_id == "P7" for d in excinfo.value.decisions)


def test_p7_graph_endpoint_without_token_denied(kernel):
    with pytest.raises(PolicyDenied) as excinfo:
        kernel.invoke("custodian", "graph.own_media",
                      {"url": "https://graph.facebook.com/v25.0/me/media"})
    d = next(d for d in excinfo.value.decisions if d.policy_id == "P7")
    assert d.detail["graph_endpoint"] is True and d.detail["token_present"] is False


def test_p8_context_mixing_denied_everywhere(kernel):
    # P8 applies to every tool call, whatever the agent or skill.
    with pytest.raises(PolicyDenied) as excinfo:
        kernel.invoke("publisher", "export.selection_resolve", {
            "context_tags": ["beyond_style", "rta"],
        })
    assert any(d.policy_id == "P8" for d in excinfo.value.decisions)

    with pytest.raises(PolicyDenied) as excinfo:
        kernel.invoke("analyst", "corpus.health", {
            "context_tags": ["bcgt"], "record": "rta maintenance report Q3",
        })
    assert any(d.policy_id == "P8" for d in excinfo.value.decisions)
