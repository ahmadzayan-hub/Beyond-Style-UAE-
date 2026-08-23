"""P4 (corpus floor) and P3 (three-source provenance) enforcement."""

from __future__ import annotations

import pytest

from bsos.kernel.contracts import PolicyDenied

from conftest import build_corpus, make_licence


def test_corpus_floor_blocks_synthesis_and_reports_counts(kernel):
    with pytest.raises(PolicyDenied) as excinfo:
        kernel.invoke("analyst", "corpus.whitespace", {})
    d = next(d for d in excinfo.value.decisions if d.policy_id == "P4")
    assert "0/40 references" in d.message and "0/12" in d.message
    assert d.detail["required_references"] == 40
    assert d.detail["required_sources"] == 12


def test_corpus_floor_met_allows_synthesis(kernel):
    licence = make_licence(kernel)
    build_corpus(kernel, licence, count=42)  # 42 refs across 14 sources
    health = kernel.invoke("analyst", "corpus.health", {})
    assert health["floor_met"], health
    report = kernel.invoke("analyst", "corpus.whitespace", {})
    assert report["total_references"] == 42
    freq = kernel.invoke("analyst", "corpus.frequency_rank", {})
    assert freq["total_references"] == 42


def test_p3_drops_single_source_attribute_and_returns_brief_for_review(kernel):
    licence = make_licence(kernel)
    build_corpus(kernel, licence, count=42)

    # Compose a brief whose second attribute is supported by nothing in corpus.
    composed = kernel.invoke("designer", "concept.brief_compose", {
        "title": "test brief",
        "seed_values": ["motif.primary=falcon", "form.silhouette=nonexistent value"],
    })
    brief_id = composed["brief_id"]
    weak = composed["attributes"]["form.silhouette"]
    assert len(weak["source_ids"]) < 3

    with pytest.raises(PolicyDenied) as excinfo:
        kernel.invoke("designer", "concept.brief_promote", {
            "brief_id": brief_id, "attributes": composed["attributes"],
        })
    p3 = next(d for d in excinfo.value.decisions if d.policy_id == "P3")
    assert "form.silhouette" in p3.detail["insufficient_provenance"]

    # The P3 contract: offending attributes dropped, brief returned for review.
    dropped = kernel.invoke("designer", "concept.brief_drop_insufficient", {
        "brief_id": brief_id, "offending": p3.detail["insufficient_provenance"],
    })
    assert dropped["status"] == "review"
    assert "form.silhouette" in dropped["dropped"]

    from bsos.memory.domain import Brief

    with kernel.db_factory() as db:
        brief = db.get(Brief, brief_id)
        assert "form.silhouette" not in brief.attributes
        assert brief.dropped_attributes["form.silhouette"]["reason"] == "insufficient_provenance"

    # With only well-supported attributes left, promotion succeeds.
    result = kernel.invoke("designer", "concept.brief_promote", {
        "brief_id": brief_id, "attributes": brief.attributes,
    })
    assert result["status"] == "approved"
