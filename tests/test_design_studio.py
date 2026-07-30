"""Design Studio: the زهران reference test and the fail-closed ladder.

Phase-16 requirement: the deterministic text/vector layer — not a visual
impression — must confirm the artwork genuinely represents زهران, and the
export package must contain SVG, DXF, vector PDF, technical PDF and PNG.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from bsos.kernel.contracts import GrantViolation

ZAHRAN = "زهران"
EXPECTED_SEQUENCE = ["ز", "ه", "ر", "ا", "ن"]


# ------------------------------------------------------------- typography ----

def test_zahran_letter_sequence_and_structural_verification():
    from bsos.design_studio.typography import engine_for

    engine = engine_for("Amiri-Regular")
    shaped = engine.shape(ZAHRAN)
    assert [c["char"] for c in engine.letter_sequence(shaped.normalized_text)] == EXPECTED_SEQUENCE
    assert shaped.verified, shaped.verification["issues"]
    assert shaped.direction in ("rtl", "DirectionRTL", "4")
    names = " ".join(g.glyph_name for g in shaped.glyphs)
    for stem in ("zain", "heh", "reh", "alef", "noon"):
        assert stem in names, f"expected a {stem} glyph in: {names}"


def test_verification_fails_closed_on_missing_glyph():
    from bsos.design_studio.typography import engine_for

    engine = engine_for("Amiri-Regular")
    # A codepoint the font does not cover must land in human_review,
    # never silently pass.
    shaped = engine.shape("زهر一")
    assert not shaped.verified
    assert shaped.verification["status"] == "human_review"


def test_zero_width_characters_are_stripped():
    from bsos.design_studio.typography import engine_for

    engine = engine_for("Amiri-Regular")
    assert engine.normalize("زهر​ان") == ZAHRAN


# ------------------------------------------------- composition/validation ----

def test_three_variants_all_spelling_verified_and_mfg_variant_passes():
    from bsos.design_studio.composition import VARIANT_SPECS, compose_all
    from bsos.design_studio.validation import validate_composition

    comps = compose_all(ZAHRAN)
    assert [c.variant_id for c in comps] == list(VARIANT_SPECS)
    for comp in comps:
        assert comp.verification["passed"], comp.variant_id
        assert "Diwani-INSPIRED" in comp.meta["authenticity"]
    luxury = comps[0]
    assert luxury.meta["expert_review_recommended"] is True

    mfg = next(c for c in comps if c.variant_id == "manufacturing_optimized")
    report = validate_composition(mfg)
    assert report.passed, [c for c in report.checks if not c["ok"]]


def test_validation_is_real_geometry_not_labels():
    """Shrinking the workshop rules must actually change the verdict."""
    from bsos.design_studio.composition import compose_variant
    from bsos.design_studio.validation import validate_composition

    strict = compose_variant("manufacturing_optimized", ZAHRAN,
                             frame={"min_stroke_mm": 3.0})
    assert not validate_composition(strict).passed


# ------------------------------------------------------------ skill ladder ----

@pytest.fixture
def project(kernel):
    result = kernel.invoke("calligrapher", "design.project_create",
                           {"inscription": ZAHRAN})
    assert result["status"] == "typography_verified"
    return result["project_id"]


def test_ladder_and_export_package(kernel, project):
    composed = kernel.invoke("calligrapher", "design.compose", {"project_id": project})
    assert composed["status"] == "variants_composed"
    assert len(composed["variants"]) == 3

    # Export before approval is fail-closed.
    with pytest.raises(ValueError, match="workshop files"):
        kernel.invoke("calligrapher", "design.export_package", {"project_id": project})

    validated = kernel.invoke("calligrapher", "design.validate", {
        "project_id": project, "variant_id": "manufacturing_optimized"})
    assert validated["passed"] and validated["status"] == "manufacturing_checked"

    # Approving a variant that did not pass validation is impossible.
    with pytest.raises(ValueError, match="manufacturing_checked"):
        kernel.invoke("calligrapher", "design.approve", {
            "project_id": project, "variant_id": "luxury_diwani_jali",
            "approver": "owner"})

    kernel.invoke("calligrapher", "design.approve", {
        "project_id": project, "variant_id": "manufacturing_optimized",
        "approver": "owner"})
    package = kernel.invoke("calligrapher", "design.export_package", {
        "project_id": project, "brief": {"material": "stainless steel"}})

    files = package["files"]
    for key in ("svg", "svg_mirrored", "dxf", "vector_pdf", "technical_pdf",
                "png_flat", "png_enamel_macro", "png_pair"):
        assert key in files and Path(files[key]).stat().st_size > 0, key

    # Provenance chain records every rung.
    chain = kernel.adapters.provenance.chain(f"design-{project}")
    assert [e["event"] for e in chain] == [
        "typography_verification", "variants_composed",
        "manufacturing_validation", "workshop_approval", "export_package",
    ]


def test_design_grants_are_calligrapher_only(kernel, project):
    for agent in ("designer", "publisher", "custodian"):
        with pytest.raises(GrantViolation):
            kernel.invoke(agent, "design.approve", {
                "project_id": project, "variant_id": "manufacturing_optimized",
                "approver": agent})


def test_unverified_inscription_cannot_compose(kernel):
    result = kernel.invoke("calligrapher", "design.project_create",
                           {"inscription": "زهر一"})
    assert result["status"] == "human_review"
    with pytest.raises(ValueError, match="fail-closed"):
        kernel.invoke("calligrapher", "design.compose",
                      {"project_id": result["project_id"]})


def test_font_registry_never_downloads(kernel):
    fonts = kernel.invoke("calligrapher", "design.fonts", {})
    assert "no runtime font downloads" in fonts["policy"]
    usable = {f["id"] for f in fonts["fonts"] if f["usable"]}
    assert {"Amiri-Regular", "Amiri-Bold"} <= usable
    # review-required entries without a vendored binary are not usable
    assert all(f["binary_present"] for f in fonts["fonts"] if f["usable"])
