"""Kernel fundamentals: guard, ledger, grants, policy config immutability."""

from __future__ import annotations

import pytest

from bsos.kernel.contracts import GrantViolation, PolicyDenied
from bsos.kernel.grants import GrantSet
from bsos.kernel.ledger import Ledger
from bsos.kernel.policy import PolicyConfigError, PolicyEngine

from conftest import make_licence


def test_policy_denial_writes_correct_ledger_entry(kernel):
    with pytest.raises(PolicyDenied) as excinfo:
        kernel.invoke("designer", "generate.image", {
            "prompt": "pendant referencing data:image/png;base64,iVBORw0KGgo",
            "model": "local-dev", "brief_id": 1,
        })
    assert any(d.policy_id == "P1" and d.action == "deny" for d in excinfo.value.decisions)

    evaluations = kernel.ledger.tail(50, "policy_evaluation")
    p1 = [e for e in evaluations if e["data"].get("policy_id") == "P1"]
    assert p1 and p1[-1]["outcome"] == "deny"
    denied_calls = kernel.ledger.tail(50, "tool_call")
    assert denied_calls[-1]["outcome"] == "denied"
    assert kernel.ledger.verify()


def test_policy_passes_are_also_ledgered(kernel):
    licence = make_licence(kernel)
    kernel.invoke("custodian", "licence.verify", {"licence_id": licence})
    # P8 applies to every call, so at least one allow evaluation must exist.
    evaluations = kernel.ledger.tail(100, "policy_evaluation")
    assert any(e["outcome"] == "allow" for e in evaluations)


def test_ledger_tamper_detection(tmp_path):
    ledger = Ledger(tmp_path / "ledger.jsonl")
    ledger.append("event_a", actor="t", data={"n": 1})
    ledger.append("event_b", actor="t", data={"n": 2})
    assert ledger.verify()
    lines = (tmp_path / "ledger.jsonl").read_text().splitlines()
    (tmp_path / "ledger.jsonl").write_text(lines[0].replace('"n":1', '"n":9') + "\n" + lines[1] + "\n")
    assert not Ledger(tmp_path / "ledger.jsonl").verify()


def test_unknown_tool_rejected(kernel):
    with pytest.raises(GrantViolation):
        kernel.invoke("custodian", "no.such.tool", {})


def test_grants_are_immutable_and_wildcard_free(kernel):
    with pytest.raises(ValueError):
        kernel.grants.register("custodian", GrantSet.of(["library.*"]))
    with pytest.raises(ValueError):
        GrantSet.of(["*"])


def test_core_policies_cannot_be_disabled(tmp_path):
    config = tmp_path / "policies.yaml"
    config.write_text("policies:\n  P5:\n    enabled: false\n")
    with pytest.raises(PolicyConfigError, match="P5 cannot be disabled"):
        PolicyEngine(config)


def test_threshold_change_is_ledgered(kernel):
    kernel.policy_engine.set_threshold("originality_max_similarity", 0.84,
                                       actor="owner", reason="tuning session 1")
    changes = kernel.ledger.tail(10, "threshold_change")
    assert changes[-1]["data"] == {
        "key": "originality_max_similarity", "old": 0.86, "new": 0.84,
        "reason": "tuning session 1",
    }
