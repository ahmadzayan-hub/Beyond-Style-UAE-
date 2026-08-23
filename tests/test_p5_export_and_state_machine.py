"""P5 (no AI publication) and the workshop state machine's photograph gate."""

from __future__ import annotations

import csv

import pytest

from bsos.kernel.contracts import PolicyDenied
from bsos.memory.domain import Asset
from bsos.orchestrator.state_machine import STATES, StateMachine, TransitionError

from conftest import ingest_asset, make_licence


def _add_ai_asset(kernel) -> str:
    from conftest import make_pattern_image

    path = kernel.paths.exports_internal / "CONCEPT_ONLY_render.png"
    make_pattern_image(path, 77)
    with kernel.db_factory() as db:
        asset = Asset(id="ai_render_00000001", filename=path.name, path=str(path),
                      sha256="f" * 64, origin="ai_generated")
        db.add(asset)
        db.commit()
    return "ai_render_00000001"


def test_ai_render_blocked_from_catalogue_export(kernel):
    ai_id = _add_ai_asset(kernel)
    with pytest.raises(PolicyDenied) as excinfo:
        kernel.invoke("publisher", "export.flat", {"asset_ids": [ai_id]})
    d = next(d for d in excinfo.value.decisions if d.policy_id == "P5")
    assert d.detail["offenders"][0]["origin"] == "ai_generated"
    assert not any(kernel.paths.exports_catalogue.iterdir())


def test_workshop_photograph_exports_with_manifest(kernel):
    licence = make_licence(kernel)
    r1 = ingest_asset(kernel, 20, licence, origin="workshop_photograph", category="necklaces")
    r2 = ingest_asset(kernel, 21, licence, origin="workshop_photograph", category="rings")
    ids = [r1["asset_id"], r2["asset_id"]]

    flat = kernel.invoke("publisher", "export.flat", {"asset_ids": ids, "destination": "testrun"})
    assert flat["files"] == 2
    with open(flat["manifest"], newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 2
    assert {r["origin"] for r in rows} == {"workshop_photograph"}
    assert all(r["licence_id"] for r in rows)

    tree = kernel.invoke("publisher", "export.tree", {"asset_ids": ids, "destination": "testrun-tree"})
    assert tree["by_category"] == {"necklaces": 1, "rings": 1}

    products = kernel.invoke("publisher", "export.products_json",
                             {"asset_ids": ids, "destination": "testrun-products"})
    import json
    from pathlib import Path

    data = json.loads(Path(products["path"]).read_text(encoding="utf-8"))
    assert len(data) == 2
    expected_keys = {"product_code", "category", "image_file", "source_handle", "licence_id",
                     "caption_original", "name_en", "name_ar", "description_en",
                     "description_ar", "starting_price_aed"}
    assert set(data[0]) == expected_keys
    assert data[0]["name_en"] == "" and data[0]["name_ar"] == ""  # manual completion


def test_state_machine_never_skips(kernel):
    with kernel.db_factory() as db:
        sm = StateMachine(db)
        run = sm.create_run()
        with pytest.raises(TransitionError, match="illegal transition"):
            sm.advance(run.id, "generation")
        for state in STATES[1:4]:  # abstraction, synthesis, brief
            sm.advance(run.id, state)
        with pytest.raises(TransitionError, match="requires human approval"):
            sm.advance(run.id, "generation")
        sm.advance(run.id, "generation", approvals={"brief_approved": True})


def test_catalogue_ready_requires_workshop_photograph(kernel):
    licence = make_licence(kernel)
    with kernel.db_factory() as db:
        sm = StateMachine(db)
        run = sm.create_run()
        sm.advance(run.id, "abstraction")
        sm.advance(run.id, "synthesis")
        sm.advance(run.id, "brief")
        sm.advance(run.id, "generation", approvals={"brief_approved": True})
        sm.advance(run.id, "originality_gate")
        sm.advance(run.id, "workshop_spec")
        sm.advance(run.id, "prototype", approvals={"spec_approved": True})
        sm.advance(run.id, "photograph")

        with pytest.raises(TransitionError, match="requires human approval"):
            sm.advance(run.id, "catalogue_ready")
        with pytest.raises(TransitionError, match="photo_asset_id missing"):
            sm.advance(run.id, "catalogue_ready",
                       approvals={"photograph_confirmed": True})

    ai_id = _add_ai_asset(kernel)
    with kernel.db_factory() as db:
        sm = StateMachine(db)
        with pytest.raises(TransitionError, match="origin 'ai_generated'"):
            sm.advance(run.id, "catalogue_ready",
                       approvals={"photograph_confirmed": True},
                       payload={"photo_asset_id": ai_id})

    photo = ingest_asset(kernel, 30, licence, origin="workshop_photograph")
    with kernel.db_factory() as db:
        sm = StateMachine(db)
        final = sm.advance(run.id, "catalogue_ready",
                           approvals={"photograph_confirmed": True},
                           payload={"photo_asset_id": photo["asset_id"]})
        assert final.state == "catalogue_ready"


def test_gate_rejection_reroll_accounting(kernel):
    with kernel.db_factory() as db:
        sm = StateMachine(db)
        run = sm.create_run()
        sm.record_gate_rejection(run.id, {"max_similarity": 0.91, "nearest": []})
        sm.record_gate_rejection(run.id, {"max_similarity": 0.89, "nearest": []})
        assert sm.rerolls_used(run.id) == 2
