"""Producer skills: workshop specification and pricing.

Material fields are written only through `spec.material_set`, which is
tagged `material_write` so P6 evaluates in the guard: no verified source, no
claim — the field becomes pending_workshop_verification. Pricing is tagged
`pricing` so a source database contradicting the AED 265 floor escalates
instead of resolving silently.
"""

from __future__ import annotations

from typing import Any

from bsos.kernel.contracts import ToolContext
from bsos.memory.domain import Concept, Spec
from bsos.skills.registry import registry

COMPLEXITY_BANDS = {
    "A": {"label": "simple single-element", "starting_price_aed": 265},
    "B": {"label": "multi-element or layered", "starting_price_aed": 345},
    "C": {"label": "articulated / stone-set", "starting_price_aed": 495},
    "D": {"label": "complex custom build", "starting_price_aed": 695},
}

MATERIAL_FIELDS = ("metal", "purity", "plating_type", "plating_thickness", "stone", "carat", "weight")


@registry.register("spec.compose", required_grant="spec.compose", tags=(), side_effects="db",
                   description="Create a workshop spec from an approved concept.")
def spec_compose(ctx: ToolContext, concept_id: int, components: list[dict],
                 personalisation_zones: list[dict] | None = None) -> dict[str, Any]:
    concept = ctx.db.get(Concept, concept_id)
    if concept is None:
        raise ValueError(f"concept '{concept_id}' not found")
    if concept.status != "approved":
        raise ValueError(f"concept '{concept_id}' is '{concept.status}', not approved")
    spec = Spec(concept_id=concept_id, components=components,
                personalisation_zones=personalisation_zones or [],
                materials={f: "pending_workshop_verification" for f in MATERIAL_FIELDS})
    ctx.db.add(spec)
    ctx.db.flush()
    concept.status = "specced"
    ctx.db.add(concept)
    return {"spec_id": spec.id, "concept_id": concept_id,
            "components": len(components)}


@registry.register("spec.component_breakdown", required_grant="spec.component_breakdown", tags=(),
                   description="Derive a component checklist from brief attributes.")
def component_breakdown(ctx: ToolContext, spec_id: int) -> dict[str, Any]:
    spec = ctx.db.get(Spec, spec_id)
    if spec is None:
        raise ValueError(f"spec '{spec_id}' not found")
    return {"spec_id": spec_id, "components": spec.components,
            "count": len(spec.components)}


@registry.register("spec.personalisation_zone", required_grant="spec.personalisation_zone",
                   tags=(), side_effects="db",
                   description="Declare engraving/personalisation zones on the spec.")
def personalisation_zone(ctx: ToolContext, spec_id: int, zones: list[dict]) -> dict[str, Any]:
    spec = ctx.db.get(Spec, spec_id)
    if spec is None:
        raise ValueError(f"spec '{spec_id}' not found")
    spec.personalisation_zones = zones
    ctx.db.add(spec)
    return {"spec_id": spec_id, "zones": zones}


@registry.register("spec.complexity_band", required_grant="spec.complexity_band",
                   tags=(), side_effects="db",
                   description="Assign a complexity band (A-D) driving the starting-price band.")
def complexity_band(ctx: ToolContext, spec_id: int, band: str) -> dict[str, Any]:
    if band not in COMPLEXITY_BANDS:
        raise ValueError(f"band must be one of {sorted(COMPLEXITY_BANDS)}")
    spec = ctx.db.get(Spec, spec_id)
    if spec is None:
        raise ValueError(f"spec '{spec_id}' not found")
    spec.complexity_band = band
    ctx.db.add(spec)
    return {"spec_id": spec_id, "band": band, **COMPLEXITY_BANDS[band]}


@registry.register("pricing.price_band_map", required_grant="pricing.price_band_map",
                   tags=("pricing",), side_effects="db",
                   description="Map complexity band to starting price. Floor AED 265; all prices "
                               "are starting prices confirmed on WhatsApp.")
def price_band_map(ctx: ToolContext, spec_id: int,
                   source_price_aed: float | None = None,
                   contradiction_reviewed: bool = False) -> dict[str, Any]:
    spec = ctx.db.get(Spec, spec_id)
    if spec is None:
        raise ValueError(f"spec '{spec_id}' not found")
    if not spec.complexity_band:
        raise ValueError(f"spec '{spec_id}' has no complexity band yet")
    floor = float(ctx.kernel.policy_engine.thresholds["price_floor_aed"])
    price = max(floor, COMPLEXITY_BANDS[spec.complexity_band]["starting_price_aed"])
    spec.starting_price_aed = price
    ctx.db.add(spec)
    return {"spec_id": spec_id, "starting_price_aed": price,
            "band": spec.complexity_band, "floor_aed": floor,
            "note": "starting price; final confirmed with customer on WhatsApp"}


@registry.register("spec.material_set", required_grant="spec.material_set",
                   tags=("material_write",), side_effects="db",
                   description="Write material fields. P6: verified_source required, else pending.")
def material_set(ctx: ToolContext, spec_id: int, fields: dict,
                 verified_source: str = "") -> dict[str, Any]:
    spec = ctx.db.get(Spec, spec_id)
    if spec is None:
        raise ValueError(f"spec '{spec_id}' not found")
    materials = dict(spec.materials)
    applied = {}
    for key, value in fields.items():
        if key not in MATERIAL_FIELDS:
            raise ValueError(f"'{key}' is not a material field")
        materials[key] = value
        applied[key] = value
    if verified_source:
        materials["verified_source"] = verified_source
    spec.materials = materials
    ctx.db.add(spec)
    return {"spec_id": spec_id, "applied": applied, "verified_source": verified_source}


@registry.register("spec.material_pending", required_grant="spec.material_pending",
                   tags=(), side_effects="db",
                   description="Mark material fields pending_workshop_verification after a P6 denial.")
def material_pending(ctx: ToolContext, spec_id: int, fields: list[str]) -> dict[str, Any]:
    spec = ctx.db.get(Spec, spec_id)
    if spec is None:
        raise ValueError(f"spec '{spec_id}' not found")
    materials = dict(spec.materials)
    for key in fields:
        if key in MATERIAL_FIELDS:
            materials[key] = "pending_workshop_verification"
    spec.materials = materials
    ctx.db.add(spec)
    return {"spec_id": spec_id, "pending": fields}


@registry.register("spec.open_questions", required_grant="spec.open_questions",
                   tags=(), side_effects="db",
                   description="Record the open questions the workshop must answer before prototyping.")
def open_questions(ctx: ToolContext, spec_id: int, questions: list[str]) -> dict[str, Any]:
    spec = ctx.db.get(Spec, spec_id)
    if spec is None:
        raise ValueError(f"spec '{spec_id}' not found")
    spec.open_questions = questions
    ctx.db.add(spec)
    return {"spec_id": spec_id, "open_questions": questions}


@registry.register("memory.domain.write", required_grant="memory.domain.write",
                   tags=(), side_effects="db",
                   description="Producer-scope domain writes (spec state notes).")
def memory_domain_write(ctx: ToolContext, spec_id: int, state: str) -> dict[str, Any]:
    spec = ctx.db.get(Spec, spec_id)
    if spec is None:
        raise ValueError(f"spec '{spec_id}' not found")
    spec.state = state
    ctx.db.add(spec)
    return {"spec_id": spec_id, "state": state}
