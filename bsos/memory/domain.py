"""Domain memory: SQLite via SQLModel.

This database is an *index over the folders*, never the source of truth —
``library_reconcile`` rebuilds it from sidecar files on disk. Provenance is a
separate append-only store (see provenance.py).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlmodel import JSON, Column, Field, Session, SQLModel, create_engine


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Licence(SQLModel, table=True):
    id: str = Field(primary_key=True)  # e.g. LIC-2026-001
    licensor: str
    licensor_handle: str = ""
    scope: str = ""  # comma-separated uses: ingest,derive,export
    signed_doc_path: str = ""
    valid_from: datetime
    valid_to: datetime
    notes: str = ""
    created_at: datetime = Field(default_factory=utcnow)


class Asset(SQLModel, table=True):
    id: str = Field(primary_key=True)  # sha256[:16]
    filename: str
    path: str
    sha256: str = Field(index=True)
    phash: str = ""
    origin: str = Field(index=True)  # supplier_authorised|business_discovery|manual_inbox|ai_generated|workshop_photograph
    source_handle: str = ""
    permalink: str = ""
    licence_id: Optional[str] = Field(default=None, foreign_key="licence.id")
    width: int = 0
    height: int = 0
    context_tag: str = "beyond_style"
    flags: list = Field(default_factory=list, sa_column=Column(JSON))
    review_state: str = "clear"  # clear|mark_review|duplicate_review|resolution_review|excluded
    caption: str = ""
    category: str = ""
    created_at: datetime = Field(default_factory=utcnow)


class CorpusRef(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    source_id: str = Field(index=True)  # stable id of the market record (media id / asset id)
    source_handle: str = Field(index=True)  # account or supplier the record came from
    url: str = ""
    attributes: dict = Field(default_factory=dict, sa_column=Column(JSON))
    segment: str = ""
    added_at: datetime = Field(default_factory=utcnow)


class Brief(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    # attributes: {attr_path: {"value": str, "source_ids": [str, ...]}}
    attributes: dict = Field(default_factory=dict, sa_column=Column(JSON))
    dropped_attributes: dict = Field(default_factory=dict, sa_column=Column(JSON))
    corpus_snapshot_id: str = ""
    status: str = "draft"  # draft|review|approved|generating|done
    created_at: datetime = Field(default_factory=utcnow)


class Concept(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    brief_id: int = Field(foreign_key="brief.id")
    prompt: str = ""
    model_id: str = ""
    image_path: str = ""
    origin: str = "ai_generated"  # structurally immutable: no skill exposes a setter
    gate_result: dict = Field(default_factory=dict, sa_column=Column(JSON))
    reroll_count: int = 0
    status: str = "generated"  # generated|gate_passed|gate_rejected|approved|specced
    created_at: datetime = Field(default_factory=utcnow)


class Spec(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    concept_id: int = Field(foreign_key="concept.id")
    components: list = Field(default_factory=list, sa_column=Column(JSON))
    personalisation_zones: list = Field(default_factory=list, sa_column=Column(JSON))
    materials: dict = Field(default_factory=dict, sa_column=Column(JSON))
    complexity_band: str = ""  # A|B|C|D
    starting_price_aed: float = 0
    open_questions: list = Field(default_factory=list, sa_column=Column(JSON))
    state: str = "workshop_spec"
    photo_asset_id: Optional[str] = Field(default=None, foreign_key="asset.id")
    created_at: datetime = Field(default_factory=utcnow)


class Product(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    spec_id: Optional[int] = Field(default=None, foreign_key="spec.id")
    product_code: str = Field(index=True)
    category: str = ""
    image_asset_id: Optional[str] = Field(default=None, foreign_key="asset.id")
    name_en: str = ""
    name_ar: str = ""
    description_en: str = ""
    description_ar: str = ""
    starting_price_aed: float = 0
    created_at: datetime = Field(default_factory=utcnow)


class Escalation(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    policy_id: str
    message: str
    detail: dict = Field(default_factory=dict, sa_column=Column(JSON))
    status: str = "open"  # open|approved|rejected
    resolution_note: str = ""
    created_at: datetime = Field(default_factory=utcnow)
    resolved_at: Optional[datetime] = None


class Milestone(SQLModel, table=True):
    """Project progress memory: what BSOS is being used to achieve, and where it stands."""

    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    status: str = "planned"  # planned|in_progress|done|dropped
    notes: str = ""
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class SessionLogEntry(SQLModel, table=True):
    """Sessions log: one row per working session, human-readable summary plus data."""

    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: str = Field(index=True)
    summary: str
    data: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow)


class Run(SQLModel, table=True):
    """One pass of the orchestrator state machine for a concept-to-product flow."""

    id: Optional[int] = Field(default=None, primary_key=True)
    state: str = "intake"
    brief_id: Optional[int] = Field(default=None, foreign_key="brief.id")
    concept_id: Optional[int] = Field(default=None, foreign_key="concept.id")
    spec_id: Optional[int] = Field(default=None, foreign_key="spec.id")
    history: list = Field(default_factory=list, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


def make_engine(db_path: str = "var/bsos.db"):
    engine = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False}
    )
    SQLModel.metadata.create_all(engine)
    return engine


def session_factory(engine):
    def factory() -> Session:
        return Session(engine)

    return factory
