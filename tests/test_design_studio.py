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


def test_common_names_battery_verifies():
    """Regression: Amiri's camelCase glyph names (tehMarbuta-ar, alefMaksura-ar)
    must match the stem table — common names may never bounce to human review
    for a case mismatch."""
    from bsos.design_studio.typography import engine_for

    engine = engine_for("Amiri-Regular")
    names = ["نورة", "ليلى", "عائشة", "أحمد", "إبراهيم", "فاطمة", "عبدالله",
             "سلمى", "هدى", "آمنة", "شيخة", "موزة", "جنى", "محمد", "خالد",
             "حمدان", "زايد", "مريم", "شغف", "فرح", "روز", "حصة", "يوسف",
             "طارق", "سارة", "علياء", "خليفة", "حسين", "وديمة"]
    failed = [n for n in names if not engine.shape(n).verified]
    assert not failed, f"names bounced to human_review: {failed}"


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


# ---------------------------------------------------------------- pricing ----

def test_pricing_is_deterministic_with_floor_and_tiers():
    from bsos.design_studio.pricing import PRICING_RULES, estimate

    single = estimate("cufflink", "manufacturing_optimized", 5)
    assert single["is_starting_price"] and single["currency"] == "AED"
    assert single["unit_price_aed"] >= PRICING_RULES["price_floor_aed"]
    assert single == estimate("cufflink", "manufacturing_optimized", 5)

    bulk = estimate("cufflink", "manufacturing_optimized", 5, quantity=10)
    assert bulk["unit_price_aed"] < single["unit_price_aed"]
    assert bulk["total_aed"] == bulk["unit_price_aed"] * 10

    gold = estimate("cufflink", "luxury_diwani_jali", 5, material="gold_plated",
                    finish="black_enamel")
    assert gold["unit_price_aed"] > single["unit_price_aed"]

    solid = estimate("pendant", "balanced_diwani", 3, material="solid_gold_18k")
    assert solid["quote_on_request"] is True


def test_quote_skill_records_provenance_without_touching_ladder(kernel, project):
    kernel.invoke("calligrapher", "design.compose", {"project_id": project})
    q = kernel.invoke("calligrapher", "design.quote", {
        "project_id": project, "variant_id": "luxury_diwani_jali",
        "material": "gold_plated", "finish": "black_enamel", "quantity": 2})
    assert q["is_starting_price"] and q["unit_price_aed"] > 0
    # quoting never advances production status
    assert q["project_status"] == "variants_composed"
    events = [e["event"] for e in kernel.adapters.provenance.chain(f"design-{project}")]
    assert events[-1] == "price_quote"

    with pytest.raises(ValueError, match="unknown variant"):
        kernel.invoke("calligrapher", "design.quote", {
            "project_id": project, "variant_id": "nope"})


# --------------------------------------------------------- transliteration ----

def test_transliteration_dictionary_and_flagged_fallback(kernel):
    r = kernel.invoke("calligrapher", "design.transliterate", {"text": "Zahran"})
    top = r["words"][0]["suggestions"][0]
    assert top["arabic"] == ZAHRAN
    assert top["source"] == "dictionary" and not top["requires_confirmation"]
    assert top["typography_verifiable"] is True

    # the three-name necklace example from the spec
    r = kernel.invoke("calligrapher", "design.transliterate", {"text": "Shaghaf Farah Rose"})
    assert r["combined"][0]["arabic"] == "شغف فرح روز"
    assert r["combined"][0]["typography_verifiable"] is True

    # unknown words fall back to a rule-based guess that MUST be flagged
    r = kernel.invoke("calligrapher", "design.transliterate", {"text": "Qwertyname"})
    fallback = r["words"][0]["suggestions"][0]
    assert fallback["source"] == "rules" and fallback["requires_confirmation"] is True


def test_font_registry_never_downloads(kernel):
    fonts = kernel.invoke("calligrapher", "design.fonts", {})
    assert "no runtime font downloads" in fonts["policy"]
    usable = {f["id"] for f in fonts["fonts"] if f["usable"]}
    assert {"Amiri-Regular", "Amiri-Bold"} <= usable
    # review-required entries without a vendored binary are not usable
    assert all(f["binary_present"] for f in fonts["fonts"] if f["usable"])
