"""FastAPI shell for BSOS.

Every mutating route acts through an agent, which acts through the kernel
guard. Policy outcomes map to HTTP: deny → 403 with the decisions, escalate
→ 409 with the decision card id, grant violation → 403.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlmodel import select
from sse_starlette.sse import EventSourceResponse

from bsos.agents import ANALYST, CUSTODIAN, DESIGNER, PRODUCER, PUBLISHER
from bsos.api.bootstrap import build_kernel
from bsos.kernel.contracts import EscalationPending, GrantViolation, PolicyDenied
from bsos.memory.domain import (
    Asset, Brief, Concept, Escalation, Licence, Run, Spec, utcnow,
)
from bsos.orchestrator.state_machine import StateMachine, TransitionError

kernel = build_kernel()
app = FastAPI(title="BSOS", version="0.1.0")
app.add_middleware(
    CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"], allow_headers=["*"],
)


def _act(agent, tool: str, payload: dict[str, Any] | None = None) -> Any:
    try:
        return agent.act(kernel, tool, payload or {})
    except PolicyDenied as exc:
        raise HTTPException(status_code=403, detail={
            "kind": "policy_denied",
            "decisions": [d.__dict__ for d in exc.decisions if d.action == "deny"],
        }) from exc
    except EscalationPending as exc:
        raise HTTPException(status_code=409, detail={
            "kind": "escalation", "escalation_id": exc.escalation_id,
            "decisions": [d.__dict__ for d in exc.decisions if d.action == "escalate"],
        }) from exc
    except GrantViolation as exc:
        raise HTTPException(status_code=403, detail={
            "kind": "grant_violation", "message": str(exc),
        }) from exc
    except (ValueError, FileNotFoundError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


# ---------------------------------------------------------------- system ----

@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "agents": [a for a in kernel.grants.all()],
            "skills": len(kernel.registry.all())}


@app.get("/api/policies")
def policies() -> dict:
    return {
        "thresholds": kernel.policy_engine.thresholds,
        "policies": [{"id": p.id, "name": p.name, "tags": p.tags, "description": p.description}
                     for p in kernel.policy_engine.policies],
        "grants": {name: {"allow": g.allow, "deny": g.deny}
                   for name, g in kernel.grants.all().items()},
    }


class ThresholdChange(BaseModel):
    key: str
    value: float
    reason: str
    actor: str = "owner"


@app.post("/api/policies/threshold")
def set_threshold(change: ThresholdChange) -> dict:
    try:
        kernel.policy_engine.set_threshold(change.key, change.value, change.actor, change.reason)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"thresholds": kernel.policy_engine.thresholds}


@app.get("/api/ledger")
def ledger_tail(limit: int = 100, event_type: str | None = None) -> dict:
    return {"entries": kernel.ledger.tail(limit, event_type), "verified": kernel.ledger.verify()}


@app.get("/api/feed")
async def feed() -> EventSourceResponse:
    queue = kernel.bus.attach_queue()

    async def stream():
        try:
            while True:
                event = await queue.get()
                yield {"event": event.get("topic", "event"), "data": json.dumps(event, default=str)}
        finally:
            kernel.bus.detach_queue(queue)

    return EventSourceResponse(stream())


@app.get("/api/escalations")
def escalations(status: str = "open") -> dict:
    with kernel.db_factory() as db:
        rows = db.exec(select(Escalation).where(Escalation.status == status)
                       .order_by(Escalation.created_at.desc())).all()
        return {"escalations": [r.model_dump() for r in rows]}


class EscalationResolution(BaseModel):
    decision: str  # approved | rejected
    note: str = ""


@app.post("/api/escalations/{escalation_id}/resolve")
def resolve_escalation(escalation_id: int, res: EscalationResolution) -> dict:
    with kernel.db_factory() as db:
        esc = db.get(Escalation, escalation_id)
        if esc is None:
            raise HTTPException(404, "escalation not found")
        esc.status = res.decision
        esc.resolution_note = res.note
        esc.resolved_at = utcnow()
        db.add(esc)
        db.commit()
    kernel.ledger.append("escalation_resolved", actor="owner", outcome=res.decision,
                         data={"escalation_id": escalation_id, "note": res.note})
    return {"escalation_id": escalation_id, "status": res.decision}


# --------------------------------------------------------------- custody ----

@app.get("/api/licences")
def list_licences() -> dict:
    with kernel.db_factory() as db:
        rows = db.exec(select(Licence)).all()
        out = []
        for r in rows:
            days = (r.valid_to - utcnow()).days
            out.append({**r.model_dump(), "days_left": days,
                        "expiring_soon": 0 <= days <= 30, "expired": days < 0})
        return {"licences": out}


class LicenceCreate(BaseModel):
    licence_id: str
    licensor: str
    scope: str = "ingest,derive"
    signed_doc_path: str
    valid_from: str
    valid_to: str
    licensor_handle: str = ""
    notes: str = ""


@app.post("/api/licences")
def create_licence(body: LicenceCreate) -> dict:
    return _act(CUSTODIAN, "licence.create", body.model_dump())


@app.get("/api/assets")
def list_assets(review_state: str | None = None, origin: str | None = None) -> dict:
    with kernel.db_factory() as db:
        q = select(Asset).order_by(Asset.created_at.desc())
        if review_state:
            q = q.where(Asset.review_state == review_state)
        if origin:
            q = q.where(Asset.origin == origin)
        return {"assets": [a.model_dump() for a in db.exec(q).all()]}


@app.get("/api/assets/{asset_id}/file")
def asset_file(asset_id: str):
    with kernel.db_factory() as db:
        asset = db.get(Asset, asset_id)
    if asset is None or not Path(asset.path).exists():
        raise HTTPException(404, "asset not found")
    return FileResponse(asset.path)


@app.get("/api/inbox")
def inbox() -> dict:
    return _act(CUSTODIAN, "library.inbox_watch")


class InboxIngest(BaseModel):
    licence_id: str
    origin: str = "manual_inbox"
    source_handle: str = ""
    category: str = ""
    acknowledge_expiry: bool = False


@app.post("/api/ingest/inbox")
def ingest_inbox(body: InboxIngest) -> dict:
    pending = _act(CUSTODIAN, "library.inbox_watch")["pending"]
    results = []
    for name in pending:
        try:
            results.append(_act(CUSTODIAN, "library.ingest", {
                "file_path": name, "licence_id": body.licence_id,
                "origin": body.origin, "source_handle": body.source_handle,
                "category": body.category, "acknowledge_expiry": body.acknowledge_expiry,
            }))
        except HTTPException as exc:
            results.append({"file": name, "error": exc.detail})
    return {"ingested": results, "count": len(results)}


@app.post("/api/assets/{asset_id}/extract")
def extract_asset(asset_id: str) -> dict:
    extraction = _act(CUSTODIAN, "vision.extract", {"asset_id": asset_id})
    with kernel.db_factory() as db:
        asset = db.get(Asset, asset_id)
    return _act(ANALYST, "corpus.add", {
        "source_id": asset_id,
        "source_handle": asset.source_handle or "library",
        "attributes": extraction["attributes"],
        "url": extraction["source_url"],
    }) | {"attributes": extraction["attributes"]}


class PhotographUpload(BaseModel):
    licence_note: str = ""


@app.post("/api/photographs")
async def upload_photograph(file: UploadFile = File(...), category: str = Form("")) -> dict:
    dest = kernel.paths.library_inbox / file.filename
    dest.write_bytes(await file.read())
    # Workshop photographs are own assets: the OWN licence row covers them.
    _ensure_own_licence()
    return _act(CUSTODIAN, "library.ingest", {
        "file_path": file.filename, "licence_id": "OWN",
        "origin": "workshop_photograph", "source_handle": "beyond_style_workshop",
        "category": category,
    })


def _ensure_own_licence() -> None:
    with kernel.db_factory() as db:
        if db.get(Licence, "OWN") is None:
            doc = kernel.paths.var / "own-works-declaration.txt"
            doc.write_text("Beyond Style UAE own-works declaration: assets produced in-house.\n")
            from datetime import datetime

            db.add(Licence(id="OWN", licensor="Beyond Style UAE", scope="ingest,derive,export",
                           signed_doc_path=str(doc), valid_from=datetime(2020, 1, 1),
                           valid_to=datetime(2099, 1, 1), notes="in-house works"))
            db.commit()


# ---------------------------------------------------------------- corpus ----

@app.get("/api/corpus/health")
def corpus_health() -> dict:
    return _act(ANALYST, "corpus.health")


@app.get("/api/corpus/refs")
def corpus_refs(limit: int = 200) -> dict:
    return _act(ANALYST, "memory.domain.read", {"table": "corpusref", "limit": limit})


# ---------------------------------------------------------------- trends ----

@app.get("/api/trends/frequency")
def trends_frequency() -> dict:
    return _act(ANALYST, "corpus.frequency_rank")


@app.get("/api/trends/cooccurrence")
def trends_cooccurrence() -> dict:
    return _act(ANALYST, "corpus.cooccurrence")


@app.get("/api/trends/whitespace")
def trends_whitespace() -> dict:
    return _act(ANALYST, "corpus.whitespace")


@app.get("/api/trends/segments")
def trends_segments() -> dict:
    return _act(ANALYST, "corpus.segment_map")


# ---------------------------------------------------------------- studio ----

class BriefCreate(BaseModel):
    title: str
    seed_values: list[str]


@app.get("/api/briefs")
def list_briefs() -> dict:
    with kernel.db_factory() as db:
        return {"briefs": [b.model_dump() for b in db.exec(
            select(Brief).order_by(Brief.created_at.desc())).all()]}


@app.post("/api/briefs")
def create_brief(body: BriefCreate) -> dict:
    return _act(DESIGNER, "concept.brief_compose", body.model_dump())


@app.get("/api/briefs/{brief_id}/provenance")
def brief_provenance(brief_id: int) -> dict:
    return _act(DESIGNER, "concept.brief_provenance_check", {"brief_id": brief_id})


@app.post("/api/briefs/{brief_id}/promote")
def promote_brief(brief_id: int) -> dict:
    with kernel.db_factory() as db:
        brief = db.get(Brief, brief_id)
        if brief is None:
            raise HTTPException(404, "brief not found")
        attributes = brief.attributes
    try:
        return DESIGNER.act(kernel, "concept.brief_promote",
                            {"brief_id": brief_id, "attributes": attributes})
    except PolicyDenied as exc:
        p3 = next((d for d in exc.decisions
                   if d.policy_id == "P3" and d.action == "deny"), None)
        if p3 is None:
            raise HTTPException(403, detail={
                "kind": "policy_denied",
                "decisions": [d.__dict__ for d in exc.decisions if d.action == "deny"],
            }) from exc
        # P3 contract: drop the offending attributes and return the brief for review.
        dropped = _act(DESIGNER, "concept.brief_drop_insufficient", {
            "brief_id": brief_id, "offending": p3.detail["insufficient_provenance"],
        })
        return {"promoted": False, "p3": p3.__dict__, **dropped}
    except (EscalationPending, GrantViolation) as exc:
        raise HTTPException(409 if isinstance(exc, EscalationPending) else 403,
                            detail=str(exc)) from exc


class GenerateRequest(BaseModel):
    brief_id: int
    model: str = "local-dev"
    style_notes: str = ""


@app.post("/api/concepts/generate")
def generate_concept(body: GenerateRequest) -> dict:
    prompt = _act(DESIGNER, "concept.prompt_assemble",
                  {"brief_id": body.brief_id, "style_notes": body.style_notes})["prompt"]
    result = _act(DESIGNER, "generate.image",
                  {"prompt": prompt, "model": body.model, "brief_id": body.brief_id})
    gate = _act(DESIGNER, "originality.gate", {"concept_id": result["concept_id"]})
    return {**result, "gate": gate}


@app.get("/api/concepts")
def list_concepts() -> dict:
    with kernel.db_factory() as db:
        return {"concepts": [c.model_dump() for c in db.exec(
            select(Concept).order_by(Concept.created_at.desc())).all()]}


@app.get("/api/concepts/{concept_id}/image")
def concept_image(concept_id: int):
    with kernel.db_factory() as db:
        concept = db.get(Concept, concept_id)
    if concept is None or not concept.image_path or not Path(concept.image_path).exists():
        raise HTTPException(404, "concept render not found")
    return FileResponse(concept.image_path)


class ConceptPromote(BaseModel):
    approver: str = "owner"
    margin_reviewed: bool = False


@app.post("/api/concepts/{concept_id}/promote")
def promote_concept(concept_id: int, body: ConceptPromote) -> dict:
    with kernel.db_factory() as db:
        concept = db.get(Concept, concept_id)
        if concept is None:
            raise HTTPException(404, "concept not found")
        max_sim = (concept.gate_result or {}).get("max_similarity")
    return _act(DESIGNER, "concept.promote", {
        "concept_id": concept_id, "approver": body.approver,
        "max_similarity": max_sim, "margin_reviewed": body.margin_reviewed,
    })


# -------------------------------------------------------------- workshop ----

class SpecCreate(BaseModel):
    concept_id: int
    components: list[dict]
    personalisation_zones: list[dict] = []


@app.get("/api/specs")
def list_specs() -> dict:
    with kernel.db_factory() as db:
        return {"specs": [s.model_dump() for s in db.exec(
            select(Spec).order_by(Spec.created_at.desc())).all()]}


@app.post("/api/specs")
def create_spec(body: SpecCreate) -> dict:
    return _act(PRODUCER, "spec.compose", body.model_dump())


class BandSet(BaseModel):
    band: str


@app.post("/api/specs/{spec_id}/band")
def set_band(spec_id: int, body: BandSet) -> dict:
    result = _act(PRODUCER, "spec.complexity_band", {"spec_id": spec_id, "band": body.band})
    price = _act(PRODUCER, "pricing.price_band_map", {"spec_id": spec_id})
    return {**result, **price}


class QuestionsSet(BaseModel):
    questions: list[str]


@app.post("/api/specs/{spec_id}/questions")
def set_questions(spec_id: int, body: QuestionsSet) -> dict:
    return _act(PRODUCER, "spec.open_questions", {"spec_id": spec_id, "questions": body.questions})


class MaterialsSet(BaseModel):
    fields: dict
    verified_source: str = ""


@app.post("/api/specs/{spec_id}/materials")
def set_materials(spec_id: int, body: MaterialsSet) -> dict:
    try:
        return PRODUCER.act(kernel, "spec.material_set", {
            "spec_id": spec_id, "fields": body.fields,
            "verified_source": body.verified_source,
        })
    except PolicyDenied as exc:
        p6 = next((d for d in exc.decisions if d.policy_id == "P6" and d.action == "deny"), None)
        if p6 is None:
            raise HTTPException(403, detail=str(exc)) from exc
        pending = _act(PRODUCER, "spec.material_pending",
                       {"spec_id": spec_id, "fields": p6.detail["unverified_fields"]})
        return {"applied": False, "p6": p6.__dict__, **pending}


# ------------------------------------------------------------------ runs ----

@app.post("/api/runs")
def create_run() -> dict:
    with kernel.db_factory() as db:
        run = StateMachine(db).create_run()
        return run.model_dump()


class RunAdvance(BaseModel):
    to_state: str
    approvals: dict = {}
    payload: dict = {}


@app.post("/api/runs/{run_id}/advance")
def advance_run(run_id: int, body: RunAdvance) -> dict:
    with kernel.db_factory() as db:
        try:
            run = StateMachine(db).advance(run_id, body.to_state, body.approvals, body.payload)
        except TransitionError as exc:
            raise HTTPException(409, str(exc)) from exc
        kernel.ledger.append("run_transition", actor="orchestrator", outcome=body.to_state,
                             data={"run_id": run_id})
        return run.model_dump()


@app.get("/api/runs")
def list_runs() -> dict:
    with kernel.db_factory() as db:
        return {"runs": [r.model_dump() for r in db.exec(
            select(Run).order_by(Run.updated_at.desc())).all()]}


# --------------------------------------------------------------- exports ----

class ExportRequest(BaseModel):
    category: str = ""
    targets: list[str] = ["flat"]  # flat | tree | products_json


@app.post("/api/exports")
def run_export(body: ExportRequest) -> dict:
    selection = _act(PUBLISHER, "export.selection_resolve", {"category": body.category})
    if not selection["asset_ids"]:
        return {"exported": False, "reason": "selection resolved to zero assets", **selection}
    from datetime import datetime, timezone

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    results: dict[str, Any] = {}
    tools = {"flat": "export.flat", "tree": "export.tree", "products_json": "export.products_json"}
    for target in body.targets:
        tool = tools.get(target)
        if tool is None:
            raise HTTPException(422, f"unknown export target '{target}'")
        results[target] = _act(PUBLISHER, tool, {
            "asset_ids": selection["asset_ids"], "destination": stamp,
        })
    return {"exported": True, "destination": stamp, **results}


@app.get("/api/audit/concept/{concept_id}")
def audit_concept(concept_id: int) -> dict:
    prov = kernel.adapters.provenance
    return {"concept_id": concept_id, "chain": prov.chain(concept_id)}


@app.post("/api/audit/concept/{concept_id}/pdf")
def audit_concept_pdf(concept_id: int) -> dict:
    return _act(PUBLISHER, "export.provenance_pdf", {"concept_id": concept_id})
