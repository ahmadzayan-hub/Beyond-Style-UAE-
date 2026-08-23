"""Design Studio skills: verified inscription → variants → validation → files.

The status ladder is enforced here, fail-closed, not in the UI:
draft → typography_verified → variants_composed → manufacturing_checked
→ workshop_approved. Spelling verification is deterministic (HarfBuzz
shaping + glyph-name checks in bsos.design_studio.typography); geometry
validation is real shapely erosion/dilation testing. An export package can
only be produced for a variant that passed validation AND carries a human
workshop approval.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlmodel import select

from bsos.kernel.contracts import ToolContext
from bsos.memory.domain import DesignProject, utcnow
from bsos.skills.registry import registry

REGISTRY_JSON = Path(__file__).parent.parent / "design_studio" / "registry.json"


def _prov_key(project_id: int) -> str:
    return f"design-{project_id}"


def _compose(project: DesignProject):
    """Recompute the deterministic compositions for a project."""
    from bsos.design_studio.composition import compose_all

    return compose_all(project.normalized_inscription or project.inscription,
                       project.frame or None)


def _variant(project: DesignProject, variant_id: str):
    comps = {c.variant_id: c for c in _compose(project)}
    if variant_id not in comps:
        raise ValueError(f"unknown variant '{variant_id}'")
    return comps[variant_id]


@registry.register("design.fonts", required_grant="design.fonts", tags=(),
                   description="Approved-font registry with licensing metadata; nothing is fetched at runtime.")
def design_fonts(ctx: ToolContext) -> dict[str, Any]:
    from bsos.design_studio.typography import available_fonts

    reg = json.loads(REGISTRY_JSON.read_text(encoding="utf-8"))
    on_disk = set(available_fonts())
    for f in reg["fonts"]:
        f["binary_present"] = f["id"] in on_disk
        f["usable"] = f["binary_present"] and f.get("status") == "approved"
    return reg


@registry.register("design.project_create", required_grant="design.project_create",
                   tags=(), side_effects="db",
                   description="Create a design project; shape and verify the inscription deterministically.")
def project_create(ctx: ToolContext, inscription: str, item_type: str = "cufflink",
                   frame: dict | None = None, font_id: str = "Amiri-Regular") -> dict[str, Any]:
    from bsos.design_studio.composition import DEFAULT_FRAME
    from bsos.design_studio.typography import engine_for

    engine = engine_for(font_id)
    shaped = engine.shape(inscription)
    verified = shaped.verified

    project = DesignProject(
        inscription=inscription,
        normalized_inscription=shaped.normalized_text,
        item_type=item_type,
        frame={**DEFAULT_FRAME, **(frame or {})},
        letter_sequence=engine.letter_sequence(shaped.normalized_text),
        verification=shaped.verification,
        status="typography_verified" if verified else "human_review",
    )
    ctx.db.add(project)
    ctx.db.flush()

    ctx.adapters.require("provenance").append(_prov_key(project.id), "typography_verification", {
        "inscription": inscription,
        "normalized": shaped.normalized_text,
        "font": font_id,
        "engine": shaped.verification.get("engine"),
        "passed": verified,
        "issues": shaped.verification.get("issues", []),
    })
    return {"project_id": project.id, "status": project.status,
            "letter_sequence": project.letter_sequence,
            "verification": project.verification}


@registry.register("design.compose", required_grant="design.compose",
                   tags=(), side_effects="fs+db",
                   description="Compose the three Diwani-inspired variants for a verified project.")
def compose(ctx: ToolContext, project_id: int) -> dict[str, Any]:
    from bsos.design_studio.validation import validate_composition

    project = ctx.db.get(DesignProject, project_id)
    if project is None:
        raise ValueError(f"design project '{project_id}' not found")
    if project.status not in ("typography_verified", "variants_composed",
                              "manufacturing_checked"):
        raise ValueError(
            f"project '{project_id}' is '{project.status}'; variants require a "
            "typography-verified inscription (fail-closed)")

    out_dir = ctx.paths.exports / "design_studio" / f"project-{project_id}"
    out_dir.mkdir(parents=True, exist_ok=True)

    variants: list[dict[str, Any]] = []
    validations: dict[str, Any] = {}
    for comp in _compose(project):
        report = validate_composition(comp)
        (out_dir / f"{comp.variant_id}.svg").write_text(comp.svg, encoding="utf-8")
        variants.append({
            "variant_id": comp.variant_id,
            "svg": comp.svg,
            "font": comp.font_id,
            "spelling_verified": bool(comp.verification.get("passed")),
            "legibility": comp.legibility,
            "feasibility_hint": comp.feasibility_hint,
            "text_mm": [round(comp.text_width_mm, 2), round(comp.text_height_mm, 2)],
            "meta": comp.meta,
            "validation_passed": report.passed,
        })
        validations[comp.variant_id] = report.to_dict()

    project.variants = variants
    project.validations = validations
    if project.status == "typography_verified":
        project.status = "variants_composed"
    project.updated_at = utcnow()
    ctx.db.add(project)

    ctx.adapters.require("provenance").append(_prov_key(project_id), "variants_composed", {
        "variants": [{k: v for k, v in item.items() if k != "svg"} for item in variants],
    })
    return {"project_id": project_id, "status": project.status,
            "variants": variants, "validations": validations}


@registry.register("design.validate", required_grant="design.validate",
                   tags=(), side_effects="db",
                   description="Run manufacturing geometry validation for one variant; fail-closed status move.")
def validate(ctx: ToolContext, project_id: int, variant_id: str) -> dict[str, Any]:
    from bsos.design_studio.validation import validate_composition

    project = ctx.db.get(DesignProject, project_id)
    if project is None:
        raise ValueError(f"design project '{project_id}' not found")
    if not project.variants:
        raise ValueError(f"project '{project_id}' has no composed variants yet")

    comp = _variant(project, variant_id)
    report = validate_composition(comp)
    project.validations = {**project.validations, variant_id: report.to_dict()}
    if report.passed:
        project.selected_variant = variant_id
        project.status = "manufacturing_checked"
    project.updated_at = utcnow()
    ctx.db.add(project)

    ctx.adapters.require("provenance").append(_prov_key(project_id), "manufacturing_validation", {
        "variant": variant_id, "passed": report.passed, "checks": report.checks,
    })
    return {"project_id": project_id, "variant": variant_id,
            "passed": report.passed, "status": project.status,
            "report": report.to_dict()}


@registry.register("design.approve", required_grant="design.approve",
                   tags=(), side_effects="db",
                   description="Record human workshop approval for a manufacturing-checked variant.")
def approve(ctx: ToolContext, project_id: int, variant_id: str,
            approver: str, note: str = "") -> dict[str, Any]:
    project = ctx.db.get(DesignProject, project_id)
    if project is None:
        raise ValueError(f"design project '{project_id}' not found")
    if project.status != "manufacturing_checked" or project.selected_variant != variant_id:
        raise ValueError(
            f"variant '{variant_id}' of project '{project_id}' is not "
            "manufacturing_checked; approval is only possible after validation passes")
    project.status = "workshop_approved"
    project.approver = approver
    project.approval_note = note
    project.updated_at = utcnow()
    ctx.db.add(project)

    ctx.adapters.require("provenance").append(_prov_key(project_id), "workshop_approval", {
        "variant": variant_id, "approver": approver, "note": note,
    })
    return {"project_id": project_id, "variant": variant_id,
            "status": "workshop_approved", "approver": approver}


@registry.register("design.export_package", required_grant="design.export_package",
                   tags=(), side_effects="fs+db",
                   description="Produce the workshop file package (SVG/DXF/PDF/PNG, mm) for an approved variant.")
def export_package(ctx: ToolContext, project_id: int, brief: dict | None = None) -> dict[str, Any]:
    from bsos.design_studio.exports import export_package as _export
    from bsos.design_studio.validation import validate_composition

    project = ctx.db.get(DesignProject, project_id)
    if project is None:
        raise ValueError(f"design project '{project_id}' not found")
    if project.status != "workshop_approved":
        raise ValueError(
            f"project '{project_id}' is '{project.status}'; workshop files are "
            "only produced after human approval (fail-closed)")

    comp = _variant(project, project.selected_variant)
    report = validate_composition(comp)
    if not report.passed:
        raise ValueError("validation no longer passes for the approved variant; re-validate")

    out_dir = ctx.paths.exports / "design_studio" / f"project-{project_id}" / "package"
    approval_id = f"BS-DS-{project_id}-{project.selected_variant[:4].upper()}"
    files = _export(comp, report.to_dict(), brief or {}, out_dir, approval_id)

    project.export_manifest = {"approval_id": approval_id, "files": files}
    project.updated_at = utcnow()
    ctx.db.add(project)

    ctx.adapters.require("provenance").append(_prov_key(project_id), "export_package", {
        "approval_id": approval_id, "files": sorted(files),
    })
    return {"project_id": project_id, "approval_id": approval_id, "files": files}


@registry.register("design.transliterate", required_grant="design.transliterate", tags=(),
                   description="Deterministic Latin→Arabic name suggestions; each checked against the typography engine.")
def transliterate(ctx: ToolContext, text: str, font_id: str = "Amiri-Regular") -> dict[str, Any]:
    from bsos.design_studio.transliteration import suggest
    from bsos.design_studio.typography import engine_for

    result = suggest(text)
    engine = engine_for(font_id)
    # Every suggestion is pre-checked by the deterministic engine so the UI
    # can show upfront whether the spelling would verify.
    for word in result["words"]:
        for s in word["suggestions"]:
            s["typography_verifiable"] = bool(engine.shape(s["arabic"]).verified)
    for c in result["combined"]:
        c["typography_verifiable"] = bool(engine.shape(c["arabic"]).verified)
    return result


@registry.register("design.pricing_rules", required_grant="design.pricing_rules", tags=(),
                   description="The configurable pricing rules (AED starting prices) served to the showroom UI.")
def pricing_rules(ctx: ToolContext) -> dict[str, Any]:
    from bsos.design_studio.pricing import PRICING_RULES

    return {"rules": PRICING_RULES}


@registry.register("design.quote", required_grant="design.quote",
                   tags=(), side_effects="db",
                   description="Authoritative starting-price quote for a variant; recorded in provenance.")
def quote(ctx: ToolContext, project_id: int, variant_id: str,
          material: str = "silver_925", finish: str = "mirror_polish",
          quantity: int = 1) -> dict[str, Any]:
    from bsos.design_studio.pricing import estimate

    project = ctx.db.get(DesignProject, project_id)
    if project is None:
        raise ValueError(f"design project '{project_id}' not found")
    if not project.variants:
        raise ValueError(f"project '{project_id}' has no composed variants to price")
    if variant_id not in {v.get("variant_id") for v in project.variants}:
        raise ValueError(f"unknown variant '{variant_id}'")

    letters = len([c for c in project.letter_sequence if c.get("char", "").strip()])
    result = estimate(project.item_type, variant_id, letters,
                      material=material, finish=finish, quantity=quantity)
    # A quote never implies production readiness — the trust ladder is separate.
    result["project_status"] = project.status

    ctx.adapters.require("provenance").append(_prov_key(project_id), "price_quote", {
        "variant": variant_id, "material": material, "finish": finish,
        "quantity": quantity, "result": result,
    })
    return {"project_id": project_id, "variant": variant_id, **result}


@registry.register("design.project_list", required_grant="design.project_list", tags=(),
                   description="List design projects newest-first (SVG bodies omitted).")
def project_list(ctx: ToolContext, limit: int = 50) -> dict[str, Any]:
    rows = ctx.db.exec(select(DesignProject)
                       .order_by(DesignProject.created_at.desc()).limit(limit)).all()
    out = []
    for p in rows:
        d = p.model_dump()
        d["variants"] = [{k: v for k, v in item.items() if k != "svg"}
                         for item in (p.variants or [])]
        out.append(d)
    return {"projects": out}
