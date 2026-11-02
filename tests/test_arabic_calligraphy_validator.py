"""P10: deterministic Arabic logic and the real calligrapher tool path."""

import unicodedata

import pytest

from bsos.kernel.arabic import compare_exact_text, compute_connectivity, validate_arabic_text
from bsos.kernel.contracts import PolicyDenied
from bsos.memory.domain import DesignProject


def test_arabic_report():
    report = validate_arabic_text("خالد")
    assert report["valid"] and report["is_rtl"]
    assert report["dot_bearing_letters"] == 1
    assert validate_arabic_text("نور")["dot_bearing_letters"] == 1
    assert validate_arabic_text("يثب")["dot_bearing_letters"] == 3
    assert validate_arabic_text("أمل")["has_hamza"]
    assert validate_arabic_text("مُحَمَّد")["has_diacritics"]


@pytest.mark.parametrize("text", ["", "Khalid", "خالد Khalid", "خالد\u200e", "خالد\u202e", "١٢٣", "خ\u200cالد"])
def test_invalid_arabic_rejected(text):
    assert not validate_arabic_text(text)["valid"]


def test_connectivity_resets_at_boundaries_and_hamza():
    joins = compute_connectivity("خالد")
    assert [j["joins_next"] for j in joins] == [True, False, True, False]
    assert not joins[0]["joins_previous"] and joins[3]["joins_previous"]
    joins = compute_connectivity("بِ ب،بءب")
    assert all(not j["joins_previous"] and not j["joins_next"] for j in joins)


@pytest.mark.parametrize("approved,derived", [
    ("خالد", "حالد"), ("نور الهدى", "الهدى نور"), ("أمل", "امل"),
    ("أمل", "إمل"), ("مُحَمَّد", "محمد"), ("مُحَمَّد", "مَحَمَّد"),
])
def test_exact_preservation(approved, derived):
    assert compare_exact_text(approved, derived)
    assert not compare_exact_text(approved, approved)


def test_canonical_unicode_is_equivalent():
    assert not compare_exact_text("أمل", unicodedata.normalize("NFD", "أمل"))


def test_calligrapher_rejects_invalid_before_db_write(kernel):
    with pytest.raises(PolicyDenied) as error:
        kernel.invoke("calligrapher", "design.project_create", {"inscription": "خالد Khalid"})
    assert any(d.policy_id == "P10" and d.action == "deny" for d in error.value.decisions)


def test_calligrapher_preserves_diacritics(kernel):
    text = "مُحَمَّد"
    result = kernel.invoke("calligrapher", "design.project_create", {"inscription": text})
    assert result["status"] == "typography_verified", result["verification"]
    with kernel.db_factory() as db:
        assert db.get(DesignProject, result["project_id"]).normalized_inscription == unicodedata.normalize("NFC", text)


@pytest.mark.parametrize("tool", ["design.compose", "design.validate", "design.approve", "design.export_package"])
def test_stored_spelling_checked_on_every_output_path(kernel, tool):
    with kernel.db_factory() as db:
        project = DesignProject(inscription="أمل", normalized_inscription="امل", status="workshop_approved")
        db.add(project)
        db.commit()
        db.refresh(project)
        project_id = project.id
    with pytest.raises(PolicyDenied) as error:
        kernel.invoke("calligrapher", tool, {"project_id": project_id})
    assert any(d.policy_id == "P10" and d.action == "deny" for d in error.value.decisions)
