"""P9: sibling SafetyAgent cases through the real kernel guard."""

import pytest

from bsos.kernel.child_safety import CHILD_AUTO_REJECT
from bsos.kernel.contracts import EscalationPending, PolicyDenied
from bsos.kernel.policy import PolicyConfigError, PolicyEngine
from bsos.memory.domain import Brief, Concept, Spec


def _spec(kernel, construction="solid plaque", **extra):
    with kernel.db_factory() as db:
        brief = Brief(title="child keepsake", attributes={"isChildProduct": True, **extra})
        db.add(brief)
        db.flush()
        concept = Concept(brief_id=brief.id, status="approved")
        db.add(concept)
        db.flush()
        spec = Spec(concept_id=concept.id, components=[{"construction": construction}])
        db.add(spec)
        db.commit()
        db.refresh(spec)
        return spec.id


def test_safe_nonwearable_keepsake_passes(kernel):
    sid = _spec(kernel)
    assert kernel.invoke("producer", "spec.component_breakdown", {"spec_id": sid})["count"] == 1


@pytest.mark.parametrize("hazard", [*CHILD_AUTO_REJECT, "silver slider bead", "charm", "magnetic mount"])
def test_child_hazards_cannot_be_overridden(kernel, hazard):
    sid = _spec(kernel, hazard)
    for override in ({}, {"safety_approved": True, "override": True, "human_approved": True}):
        with pytest.raises(PolicyDenied) as error:
            kernel.invoke("producer", "spec.component_breakdown", {"spec_id": sid, **override})
        decision = next(d for d in error.value.decisions if d.policy_id == "P9")
        assert decision.action == "deny" and decision.detail["hazards"]


def test_restricted_material_rejected(kernel):
    sid = _spec(kernel, safetyRestrictions=["not for babies-children"])
    with pytest.raises(PolicyDenied):
        kernel.invoke("producer", "spec.component_breakdown", {"spec_id": sid})


def test_snake_case_wrapped_brief_facts(kernel):
    sid = _spec(kernel, "toxic material", isChildProduct=False,
                **{"safety.is_child_product": {"value": True, "source_ids": []}})
    with pytest.raises(PolicyDenied):
        kernel.invoke("producer", "spec.component_breakdown", {"spec_id": sid})


def test_adult_minor_magnet_does_not_trigger_child_failure(kernel):
    sid = _spec(kernel, "magnet mount", isChildProduct=False)
    assert kernel.invoke("producer", "spec.component_breakdown", {"spec_id": sid})["count"] == 1


def test_wearable_requires_dedicated_review(kernel):
    sid = _spec(kernel, isWearableChildProduct=True)
    with pytest.raises(EscalationPending):
        kernel.invoke("producer", "spec.component_breakdown", {"spec_id": sid})


def test_new_components_checked_against_stored_child_brief(kernel):
    sid = _spec(kernel)
    with kernel.db_factory() as db:
        concept_id = db.get(Spec, sid).concept_id
    with pytest.raises(PolicyDenied):
        kernel.invoke("producer", "spec.compose", {
            "concept_id": concept_id, "components": [{"construction": "small charm"}],
        })


def test_general_structural_weakness_fails(kernel):
    with pytest.raises(PolicyDenied):
        kernel.invoke("analyst", "corpus.health", {
            "dimensions": {"thicknessMm": 0.5}, "minimumThicknessMm": 1,
        })


@pytest.mark.parametrize("pid", ["P9", "P10"])
def test_new_core_gates_cannot_be_disabled(tmp_path, pid):
    config = tmp_path / "policies.yaml"
    config.write_text(f"policies:\n  {pid}:\n    enabled: false\n")
    with pytest.raises(PolicyConfigError, match="cannot be disabled"):
        PolicyEngine(config)
