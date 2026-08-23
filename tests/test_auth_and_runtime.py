"""API token auth, the agent reasoning runtime, pipeline orchestration, backup."""

from __future__ import annotations

import json

import pytest

from bsos.kernel.contracts import GrantViolation  # noqa: F401 (documented behaviour)


# ------------------------------------------------------------------ auth ----

@pytest.fixture(scope="module")
def client(tmp_path_factory):
    import os

    root = tmp_path_factory.mktemp("approot")
    os.environ["BSOS_ROOT"] = str(root)
    os.environ["BSOS_API_TOKEN"] = "test-token-123"
    from fastapi.testclient import TestClient

    from bsos.api.app import app

    return TestClient(app)


def test_api_requires_token(client):
    assert client.get("/api/assets").status_code == 401
    assert client.get("/api/ledger").status_code == 401
    assert client.post("/api/exports", json={}).status_code == 401


def test_health_is_open_and_token_grants_access(client):
    assert client.get("/api/health").status_code == 200
    ok = client.get("/api/assets", headers={"Authorization": "Bearer test-token-123"})
    assert ok.status_code == 200
    # query-param form for <img>/EventSource contexts
    assert client.get("/api/assets?token=test-token-123").status_code == 200
    bad = client.get("/api/assets", headers={"Authorization": "Bearer wrong"})
    assert bad.status_code == 401


def test_metrics_behind_auth(client):
    assert client.get("/api/metrics").status_code == 401
    resp = client.get("/api/metrics?token=test-token-123")
    assert resp.status_code == 200
    assert b"bsos_http_requests_total" in resp.content


def test_agent_profiles_and_avatar_roundtrip(client):
    headers = {"Authorization": "Bearer test-token-123"}
    agents = client.get("/api/agents/profiles", headers=headers).json()["agents"]
    assert {a["name"] for a in agents} == {"custodian", "analyst", "designer", "producer", "publisher", "calligrapher"}

    client.post("/api/agents/analyst/profile", headers=headers,
                json={"display_name": "Layla", "tagline": "trend synthesis"})
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (64, 64), (80, 90, 100)).save(buf, format="PNG")
    up = client.post("/api/agents/analyst/avatar", headers=headers,
                     files={"file": ("layla.png", buf.getvalue(), "image/png")})
    assert up.status_code == 200
    assert client.get("/api/agents/analyst/avatar?token=test-token-123").status_code == 200
    agents = client.get("/api/agents/profiles", headers=headers).json()["agents"]
    layla = next(a for a in agents if a["name"] == "analyst")
    assert layla["display_name"] == "Layla"


# --------------------------------------------------------- agent runtime ----

class ScriptedLLM:
    """Emits a fixed sequence of protocol actions."""

    def __init__(self, actions):
        self.actions = list(actions)

    def complete(self, prompt: str, max_tokens: int = 2048) -> str:
        return json.dumps(self.actions.pop(0))


def test_agent_runtime_reasons_through_the_guard(kernel):
    from bsos.agents import ANALYST
    from bsos.agents.runtime import AgentRuntime

    llm = ScriptedLLM([
        # step 1: tries a tool outside its grant — must be denied, not executed
        {"action": "tool", "tool": "library.ingest",
         "payload": {"file_path": "x.png", "licence_id": "L"}, "why": "overreach"},
        # step 2: adapts, uses a granted tool
        {"action": "tool", "tool": "corpus.health", "payload": {}, "why": "check floor"},
        {"action": "final", "answer": "corpus below floor", "data": {}},
    ])
    result = AgentRuntime(kernel, ANALYST, llm).run("assess corpus readiness")
    assert result["answer"] == "corpus below floor"
    assert "denied" in result["transcript"][0]
    assert "grant violation" in result["transcript"][0]["denied"]
    assert result["transcript"][1]["result"]["floor_met"] is False
    # the violation is ledgered like any other
    assert any(e["event_type"] == "grant_violation" for e in kernel.ledger.entries())


def test_agent_runtime_tool_list_respects_grants(kernel):
    from bsos.agents import DESIGNER
    from bsos.agents.runtime import AgentRuntime

    runtime = AgentRuntime(kernel, DESIGNER, ScriptedLLM([]))
    tools = {t["tool"] for t in runtime._granted_tools()}
    assert "generate.image" in tools and "originality.gate" in tools
    assert "vision.extract" not in tools and "library.ingest" not in tools


# ------------------------------------------------------ pipeline planner ----

def test_pipeline_next_actions_follows_the_plan(kernel):
    from bsos.orchestrator.pipeline import PipelineOrchestrator
    from bsos.orchestrator.state_machine import StateMachine

    with kernel.db_factory() as db:
        run = StateMachine(db).create_run()
        run_id = run.id
    pipe = PipelineOrchestrator(kernel)
    first = pipe.next_actions(run_id)
    assert first["state"] == "intake" and first["next_actions"] == []
    with kernel.db_factory() as db:
        sm = StateMachine(db)
        sm.advance(run_id, "abstraction")
        sm.advance(run_id, "synthesis")
    synth = pipe.next_actions(run_id)
    assert [s["tool"] for s in synth["next_actions"]] == ["corpus.whitespace"]
    with kernel.db_factory() as db:
        StateMachine(db).advance(run_id, "brief")
    brief = pipe.next_actions(run_id)
    assert brief["human_gate"] == "brief_approved"
    assert "concept.brief_promote" in [s["tool"] for s in brief["next_actions"]]


def test_gate_advisory_flag_on_dev_embedder(kernel):
    from conftest import build_corpus, make_licence
    from bsos.memory.domain import Brief

    licence = make_licence(kernel)
    build_corpus(kernel, licence, count=42)
    with kernel.db_factory() as db:
        b = Brief(title="t", attributes={}, status="approved")
        db.add(b)
        db.commit()
        db.refresh(b)
        brief_id = b.id
    generated = kernel.invoke("designer", "generate.image", {
        "prompt": "original cuff, brushed finish", "model": "local-dev", "brief_id": brief_id,
    })
    gate = kernel.invoke("designer", "originality.gate", {"concept_id": generated["concept_id"]})
    assert gate["advisory"] is True
    assert "dev" in gate["embedder"]


# ---------------------------------------------------------------- backup ----

def test_backup_archives_var_and_externalizes_head(tmp_path, kernel):
    import zipfile

    from bsos.cli import main

    kernel.ledger.append("marker", actor="t", data={})
    dest = tmp_path / "backups"
    code = main(["--root", str(kernel.paths.root), "backup", "--dest", str(dest)])
    assert code == 0
    archives = list(dest.glob("bsos-var-*.zip"))
    heads = list(dest.glob("ledger-head-*.txt"))
    assert len(archives) == 1 and len(heads) == 1
    names = zipfile.ZipFile(archives[0]).namelist()
    assert any(n.endswith("ledger.jsonl") for n in names)
    assert not any(n.endswith("api-token.txt") for n in names)  # token never leaves the box
    head = heads[0].read_text()
    assert kernel.ledger._prev_hash.split()[0] in head  # noqa: SLF001