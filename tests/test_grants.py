"""Grant scoping: the agent/capability table is enforced literally."""

from __future__ import annotations

import pytest

from bsos.kernel.contracts import GrantViolation

# (agent, tool) pairs that must be rejected per the grant matrix.
FORBIDDEN_CALLS = [
    ("custodian", "generate.image"),
    ("custodian", "export.flat"),
    ("analyst", "library.ingest"),
    ("analyst", "generate.image"),
    ("analyst", "export.flat"),
    ("designer", "vision.extract"),
    ("designer", "library.ingest"),
    ("designer", "graph.business_discovery"),
    ("designer", "export.flat"),
    ("producer", "generate.image"),
    ("producer", "export.flat"),
    ("producer", "library.ingest"),
    ("publisher", "generate.image"),
    ("publisher", "library.ingest"),
    ("publisher", "vision.extract"),
]


@pytest.mark.parametrize("agent,tool", FORBIDDEN_CALLS)
def test_grant_violation_rejected(kernel, agent, tool):
    with pytest.raises(GrantViolation):
        kernel.invoke(agent, tool, {})
    entry = kernel.ledger.tail(5, "grant_violation")[-1]
    assert entry["actor"] == agent and entry["data"]["tool"] == tool


ALLOWED_SPOT_CHECKS = [
    ("custodian", "library.inbox_watch", {}),
    ("analyst", "corpus.health", {}),
    ("publisher", "export.selection_resolve", {}),
]


@pytest.mark.parametrize("agent,tool,payload", ALLOWED_SPOT_CHECKS)
def test_granted_calls_pass(kernel, agent, tool, payload):
    kernel.invoke(agent, tool, payload)  # must not raise


def test_designer_has_no_image_carrying_grant(kernel):
    """The load-bearing denial: no tool in the Designer's effective grant set
    can return image bytes or read library binaries."""
    designer = kernel.grants.get("designer")
    for tool in ("vision.extract", "library.read_binary", "library.ingest",
                 "graph.business_discovery", "graph.own_media"):
        assert not designer.permits(tool), f"designer must not hold {tool}"
