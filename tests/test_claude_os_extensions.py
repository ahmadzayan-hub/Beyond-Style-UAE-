"""Claude-OS components: progress memory, sessions log, Second Brain,
local LLM provider, video recognition path, engineering expert review."""

from __future__ import annotations

import json

import httpx
import pytest

from bsos.kernel.contracts import GrantViolation
from bsos.memory.brain import SecondBrain
from bsos.memory.domain import Brief, Concept, Milestone, SessionLogEntry, Spec


# ---------------------------------------------------------------- memory ----

def test_progress_and_sessions_log_persist(kernel):
    with kernel.db_factory() as db:
        db.add(Milestone(title="Corpus to 40 refs", status="in_progress",
                         notes="12 suppliers signed"))
        db.add(SessionLogEntry(session_id="s-001",
                               summary="Ingested first supplier batch",
                               data={"assets": 20}))
        db.commit()
    with kernel.db_factory() as db:
        from sqlmodel import select

        milestone = db.exec(select(Milestone)).one()
        session = db.exec(select(SessionLogEntry)).one()
        assert milestone.status == "in_progress"
        assert session.data == {"assets": 20}


# ----------------------------------------------------------------- brain ----

def test_second_brain_fts_search(tmp_path):
    brain = SecondBrain(tmp_path / "brain.db")
    brain.add("Clasp decision", "Lobster clasps for daily wear; toggle only above 4mm chains.",
              ["workshop", "clasps"])
    brain.add("Eid window", "Gift sets outsell single pieces during Eid.", ["market"])
    hits = brain.search("clasp")
    assert len(hits) == 1 and hits[0]["title"] == "Clasp decision"
    assert "Lobster" in hits[0]["snippet"] or "clasp" in hits[0]["snippet"].lower()
    assert len(brain.all()) == 2


def test_brain_search_skill_is_granted_read_only(kernel):
    kernel.adapters.brain.add("Pricing floor", "Starting prices never below AED 265.", ["policy"])
    for agent in ("analyst", "designer", "producer"):
        result = kernel.invoke(agent, "brain.search", {"query": "pricing"})
        assert result["results"], agent
    with pytest.raises(GrantViolation):
        kernel.invoke("publisher", "brain.search", {"query": "pricing"})


# ------------------------------------------------------------- local LLM ----

def test_ollama_provider_chat_roundtrip():
    from bsos.adapters.llm import OllamaLLM

    def transport(url, payload):
        assert url.endswith("/api/chat") and payload["stream"] is False
        return httpx.Response(200, json={"message": {"role": "assistant",
                                                     "content": f"echo:{payload['messages'][0]['content']}"}})

    llm = OllamaLLM(model="llama3.2", transport=transport)
    assert llm.complete("hi") == "echo:hi"


def test_ollama_provider_clear_error_when_down():
    from bsos.adapters.llm import LLMError, OllamaLLM

    llm = OllamaLLM(transport=lambda url, payload: httpx.Response(500, text="boom"))
    with pytest.raises(LLMError, match="ollama serve"):
        llm.complete("hi")


# ----------------------------------------------------------------- video ----

def test_video_extraction_fails_loudly_without_video_extra(kernel):
    """Without bsos[video], the skill reports exactly what to install."""
    pytest.importorskip_reason = None
    try:
        import imageio.v3  # noqa: F401

        pytest.skip("video extra installed; loud-failure path not applicable")
    except ImportError:
        pass
    (kernel.paths.library_inbox / "clip.mp4").write_bytes(b"\x00\x00\x00 ftypisom")
    from conftest import make_licence

    licence = make_licence(kernel)
    with pytest.raises(Exception, match="bsos\\[video\\]"):
        kernel.invoke("custodian", "vision.extract_video",
                      {"file_path": "clip.mp4", "licence_id": licence})


def test_video_extraction_requires_licence(kernel):
    from bsos.kernel.contracts import PolicyDenied

    (kernel.paths.library_inbox / "clip.mp4").write_bytes(b"\x00")
    with pytest.raises(PolicyDenied):
        kernel.invoke("custodian", "vision.extract_video",
                      {"file_path": "clip.mp4", "licence_id": ""})


def test_designer_cannot_touch_video(kernel):
    with pytest.raises(GrantViolation):
        kernel.invoke("designer", "vision.extract_video",
                      {"file_path": "clip.mp4", "licence_id": "LIC-X"})


# ---------------------------------------------------- engineering expert ----

class FakeEngineerLLM:
    def complete(self, prompt: str, max_tokens: int = 2048) -> str:
        assert "jewellery design engineer" in prompt
        assert "Workshop spec to review" in prompt
        return json.dumps({
            "manufacturability_risks": ["enclosed Arabic counters will drop out of laser cut"],
            "setting_and_stone_notes": [],
            "wearability_notes": ["pendant over 6g needs >=1.2mm chain"],
            "personalisation_notes": [],
            "open_questions_for_workshop": ["confirm chain gauge for 8g pendant"],
            "overall": "buildable with two changes",
        })


def test_engineering_review_appends_open_questions(kernel):
    kernel.adapters.llm = FakeEngineerLLM()
    with kernel.db_factory() as db:
        brief = Brief(title="b", attributes={}, status="approved")
        db.add(brief)
        db.commit()
        db.refresh(brief)
        concept = Concept(brief_id=brief.id, status="approved")
        db.add(concept)
        db.commit()
        db.refresh(concept)
        spec = Spec(concept_id=concept.id, components=[{"part": "pendant"}],
                    open_questions=["clasp type?"])
        db.add(spec)
        db.commit()
        db.refresh(spec)
        spec_id = spec.id

    result = kernel.invoke("producer", "spec.engineering_review", {"spec_id": spec_id})
    assert result["review"]["overall"] == "buildable with two changes"
    assert result["questions_added"] == ["confirm chain gauge for 8g pendant"]
    with kernel.db_factory() as db:
        spec = db.get(Spec, spec_id)
        assert spec.open_questions == ["clasp type?", "confirm chain gauge for 8g pendant"]

    with pytest.raises(GrantViolation):
        kernel.invoke("designer", "spec.engineering_review", {"spec_id": spec_id})
