"""P2: no licence, no ingest — refusal paths and the expiry escalation."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from bsos.kernel.contracts import EscalationPending, PolicyDenied

from conftest import ingest_asset, make_licence, make_pattern_image


def _expect_p2(excinfo, fragment: str):
    d = next(d for d in excinfo.value.decisions if d.policy_id == "P2" and d.action == "deny")
    assert fragment in d.message


def test_missing_licence_denied(kernel):
    make_pattern_image(kernel.paths.library_inbox / "x.png", 1)
    with pytest.raises(PolicyDenied) as excinfo:
        kernel.invoke("custodian", "library.ingest",
                      {"file_path": "x.png", "licence_id": ""})
    _expect_p2(excinfo, "no licence supplied")


def test_unknown_licence_denied_names_the_licence(kernel):
    make_pattern_image(kernel.paths.library_inbox / "x.png", 2)
    with pytest.raises(PolicyDenied) as excinfo:
        kernel.invoke("custodian", "library.ingest",
                      {"file_path": "x.png", "licence_id": "LIC-GHOST-9"})
    _expect_p2(excinfo, "LIC-GHOST-9")


def test_expired_licence_denied(kernel):
    doc = kernel.paths.var / "expired.pdf"
    doc.write_bytes(b"%PDF expired")
    kernel.invoke("custodian", "licence.create", {
        "licence_id": "LIC-EXPIRED", "licensor": "Old Supplier", "scope": "ingest",
        "signed_doc_path": str(doc),
        "valid_from": (datetime.utcnow() - timedelta(days=400)).isoformat(),
        "valid_to": (datetime.utcnow() - timedelta(days=30)).isoformat(),
    })
    make_pattern_image(kernel.paths.library_inbox / "x.png", 3)
    with pytest.raises(PolicyDenied) as excinfo:
        kernel.invoke("custodian", "library.ingest",
                      {"file_path": "x.png", "licence_id": "LIC-EXPIRED"})
    _expect_p2(excinfo, "expired")


def test_missing_signed_document_denied(kernel):
    licence = make_licence(kernel, "LIC-NODOC")
    (kernel.paths.var / "LIC-NODOC.pdf").unlink()
    make_pattern_image(kernel.paths.library_inbox / "x.png", 4)
    with pytest.raises(PolicyDenied) as excinfo:
        kernel.invoke("custodian", "library.ingest",
                      {"file_path": "x.png", "licence_id": licence})
    _expect_p2(excinfo, "signed document missing")


def test_out_of_scope_use_denied(kernel):
    licence = make_licence(kernel, "LIC-NARROW", scope="derive")
    make_pattern_image(kernel.paths.library_inbox / "x.png", 5)
    with pytest.raises(PolicyDenied) as excinfo:
        kernel.invoke("custodian", "library.ingest",
                      {"file_path": "x.png", "licence_id": licence})
    _expect_p2(excinfo, "does not cover 'ingest'")


def test_valid_licence_ingests(kernel):
    licence = make_licence(kernel)
    result = ingest_asset(kernel, 10, licence)
    assert result["status"] == "ingested"
    sidecar = kernel.paths.library_meta / f"{result['asset_id']}.json"
    assert sidecar.exists()


def test_licence_expiring_within_30_days_escalates(kernel):
    licence = make_licence(kernel, "LIC-SOON", days_valid=10)
    make_pattern_image(kernel.paths.library_inbox / "soon.png", 6)
    with pytest.raises(EscalationPending) as excinfo:
        kernel.invoke("custodian", "library.ingest",
                      {"file_path": "soon.png", "licence_id": licence})
    d = next(d for d in excinfo.value.decisions if d.action == "escalate")
    assert d.policy_id == "E_LICENCE_EXPIRING" and "LIC-SOON" in d.message
    # Acknowledged, the same ingest proceeds.
    result = kernel.invoke("custodian", "library.ingest", {
        "file_path": "soon.png", "licence_id": licence, "acknowledge_expiry": True,
    })
    assert result["status"] == "ingested"
