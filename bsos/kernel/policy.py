"""Policy engine.

Eight non-negotiable rules (P1–P8) plus escalation policies. Each policy is a
``Policy`` object with an id, an applicability filter over the tool call
context (via skill tags), and a check that yields a ``Decision``. The guard
evaluates every applicable policy on every tool call and logs each evaluation
— including passes — to the ledger.

Thresholds load from ``kernel/policies.yaml`` and are tunable (changes are
ledgered). Rule *enablement* is not configurable: any attempt to disable
P1–P8 through configuration fails the load.
"""

from __future__ import annotations

import base64
import binascii
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

import yaml

from bsos.kernel.contracts import Decision, ToolContext

CORE_POLICY_IDS = ("P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8")

# Context tags that must never share a record, path, or export bundle (P8).
COMMERCIAL_CONTEXTS = {"beyond_style", "bcgt"}
PUBLIC_SECTOR_CONTEXTS = {"rta", "public_sector"}

IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tiff", ".heic", ".avif")
_B64_IMAGE_SIGNATURES = ("iVBOR", "/9j/", "R0lGOD", "UklGR", "Qk0")  # png jpeg gif webp bmp
_URL_RE = re.compile(r"https?://", re.IGNORECASE)
_DATA_URI_RE = re.compile(r"data:\s*image/", re.IGNORECASE)


def _looks_like_base64_blob(s: str) -> bool:
    if len(s) < 256:
        return False
    candidate = s.strip().replace("\n", "")
    if any(candidate.startswith(sig) for sig in _B64_IMAGE_SIGNATURES):
        return True
    if len(candidate) >= 4096 and re.fullmatch(r"[A-Za-z0-9+/=\s]+", candidate):
        try:
            base64.b64decode(candidate[:4096], validate=True)
            return True
        except (binascii.Error, ValueError):
            return False
    return False


def contains_image_bearing_value(value: Any, _depth: int = 0) -> str | None:
    """Return a human-readable reason if `value` carries or references image data."""
    if _depth > 8:
        return None
    if isinstance(value, (bytes, bytearray, memoryview)):
        return "binary payload"
    if isinstance(value, Path):
        return f"file path: {value}"
    if isinstance(value, str):
        if _DATA_URI_RE.search(value):
            return "data URI"
        if _URL_RE.search(value):
            return "URL in payload"
        lowered = value.lower().strip()
        if lowered.endswith(IMAGE_EXTENSIONS) and ("/" in value or "\\" in value or Path(value).exists()):
            return f"image file path: {value}"
        if _looks_like_base64_blob(value):
            return "base64 image blob"
        return None
    if isinstance(value, dict):
        for k, v in value.items():
            reason = contains_image_bearing_value(v, _depth + 1)
            if reason:
                return f"{k}: {reason}"
        return None
    if isinstance(value, (list, tuple, set)):
        for v in value:
            reason = contains_image_bearing_value(v, _depth + 1)
            if reason:
                return reason
    return None


@dataclass
class Policy:
    id: str
    name: str
    tags: tuple[str, ...]  # skill tags this policy applies to; ("*",) = every call
    check: Callable[["PolicyEngine", ToolContext], Decision | None]
    description: str = ""

    def applies_to(self, skill_tags: set[str]) -> bool:
        return "*" in self.tags or bool(skill_tags.intersection(self.tags))


class PolicyConfigError(Exception):
    pass


DEFAULT_THRESHOLDS: dict[str, float | int] = {
    "originality_max_similarity": 0.86,
    "originality_escalation_margin": 0.03,
    "phash_min_distance": 8,
    "corpus_min_references": 40,
    "corpus_min_sources": 12,
    "provenance_min_sources": 3,
    "licence_expiry_warning_days": 30,
    "price_floor_aed": 265,
    "graph_rate_limit_per_hour": 150,
    "asset_min_resolution": 512,
    "max_originality_rerolls": 2,
}


class PolicyEngine:
    def __init__(self, config_path: Path | None = None, ledger=None):
        self.ledger = ledger
        self.thresholds = dict(DEFAULT_THRESHOLDS)
        if config_path and Path(config_path).exists():
            self._load_config(Path(config_path))
        self.policies: list[Policy] = _build_policies()

    def _load_config(self, path: Path) -> None:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        policies_cfg = raw.get("policies", {}) or {}
        for pid, cfg in policies_cfg.items():
            if pid in CORE_POLICY_IDS and isinstance(cfg, dict) and cfg.get("enabled") is False:
                raise PolicyConfigError(
                    f"{pid} cannot be disabled: core policies P1-P8 are not configurable off"
                )
        for key, value in (raw.get("thresholds", {}) or {}).items():
            if key not in DEFAULT_THRESHOLDS:
                raise PolicyConfigError(f"unknown threshold '{key}'")
            self.thresholds[key] = value

    def set_threshold(self, key: str, value: float | int, actor: str, reason: str) -> None:
        if key not in self.thresholds:
            raise PolicyConfigError(f"unknown threshold '{key}'")
        old = self.thresholds[key]
        self.thresholds[key] = value
        if self.ledger:
            self.ledger.append(
                "threshold_change",
                actor=actor,
                data={"key": key, "old": old, "new": value, "reason": reason},
                outcome="applied",
            )

    def evaluate(self, ctx: ToolContext, skill_tags: set[str]) -> list[Decision]:
        decisions: list[Decision] = []
        for policy in self.policies:
            if not policy.applies_to(skill_tags):
                continue
            decision = policy.check(self, ctx)
            if decision is None:
                decision = Decision(policy_id=policy.id, action="allow", message="pass")
            decisions.append(decision)
        return decisions


# --------------------------------------------------------------------------
# Policy checks. Each returns None (pass) or a Decision (deny/escalate).
# --------------------------------------------------------------------------


def _p1_no_image_to_generator(engine: PolicyEngine, ctx: ToolContext) -> Decision | None:
    reason = contains_image_bearing_value(ctx.payload)
    if reason:
        return Decision(
            policy_id="P1",
            action="deny",
            message=f"image-bearing input to generator rejected ({reason}); "
            "the generation path accepts text prompts only",
            detail={"reason": reason},
        )
    return None


def _p2_licence_required(engine: PolicyEngine, ctx: ToolContext) -> Decision | None:
    from bsos.memory.domain import Licence  # local import: kernel may run without DB

    licence_id = ctx.payload.get("licence_id")
    use = ctx.payload.get("use", "ingest")
    if not licence_id:
        return Decision(
            policy_id="P2",
            action="deny",
            message="no licence supplied for third-party asset operation",
            detail={"use": use},
        )
    licence = ctx.db.get(Licence, licence_id) if ctx.db else None
    if licence is None:
        return Decision(
            policy_id="P2", action="deny",
            message=f"licence '{licence_id}' not found", detail={"licence_id": licence_id},
        )
    problems = []
    doc = Path(licence.signed_doc_path) if licence.signed_doc_path else None
    if not doc or not doc.exists():
        problems.append("signed document missing on disk")
    if licence.valid_to <= datetime.now(timezone.utc).replace(tzinfo=None):
        problems.append(f"expired {licence.valid_to.date()}")
    scopes = {s.strip() for s in (licence.scope or "").split(",") if s.strip()}
    if use not in scopes:
        problems.append(f"scope {sorted(scopes)} does not cover '{use}'")
    if problems:
        return Decision(
            policy_id="P2", action="deny",
            message=f"licence '{licence_id}' invalid: " + "; ".join(problems),
            detail={"licence_id": licence_id, "problems": problems},
        )
    return None


def _p3_provenance_minimum(engine: PolicyEngine, ctx: ToolContext) -> Decision | None:
    attributes: dict = ctx.payload.get("attributes", {})
    minimum = int(engine.thresholds["provenance_min_sources"])
    offending = {
        attr: sorted(set(meta.get("source_ids", [])))
        for attr, meta in attributes.items()
        if len(set(meta.get("source_ids", []))) < minimum
    }
    if offending:
        return Decision(
            policy_id="P3",
            action="deny",
            message=f"{len(offending)} attribute(s) below the {minimum}-source provenance minimum: "
            + ", ".join(sorted(offending)),
            detail={"insufficient_provenance": offending, "minimum": minimum},
        )
    return None


def _p4_corpus_floor(engine: PolicyEngine, ctx: ToolContext) -> Decision | None:
    from sqlmodel import func, select

    from bsos.memory.domain import CorpusRef

    if ctx.db is None:
        return Decision(policy_id="P4", action="deny", message="no corpus available (no database)")
    ref_count = ctx.db.exec(select(func.count()).select_from(CorpusRef)).one()
    source_count = ctx.db.exec(select(func.count(func.distinct(CorpusRef.source_handle)))).one()
    min_refs = int(engine.thresholds["corpus_min_references"])
    min_sources = int(engine.thresholds["corpus_min_sources"])
    if ref_count < min_refs or source_count < min_sources:
        return Decision(
            policy_id="P4",
            action="deny",
            message=(
                f"corpus floor not met: {ref_count}/{min_refs} references, "
                f"{source_count}/{min_sources} distinct sources "
                f"(short {max(0, min_refs - ref_count)} references, "
                f"{max(0, min_sources - source_count)} sources)"
            ),
            detail={
                "references": ref_count, "required_references": min_refs,
                "sources": source_count, "required_sources": min_sources,
            },
        )
    return None


def _p5_no_ai_publication(engine: PolicyEngine, ctx: ToolContext) -> Decision | None:
    from bsos.memory.domain import Asset

    dest = str(ctx.payload.get("destination", ""))
    asset_ids = ctx.payload.get("asset_ids", [])
    offenders = []
    for aid in asset_ids:
        asset = ctx.db.get(Asset, aid) if ctx.db else None
        origin = asset.origin if asset else "unknown"
        if origin != "workshop_photograph":
            offenders.append({"asset_id": aid, "origin": origin})
    if offenders:
        return Decision(
            policy_id="P5",
            action="deny",
            message=f"{len(offenders)} asset(s) blocked from customer-facing export: "
            "only origin=workshop_photograph may publish; AI renders are CONCEPT_ONLY "
            "and write to exports/internal_concepts only",
            detail={"offenders": offenders, "destination": dest},
        )
    if "internal_concepts" in dest:
        return Decision(
            policy_id="P5", action="deny",
            message="customer-facing export tool may not write into exports/internal_concepts",
            detail={"destination": dest},
        )
    return None


def _p6_no_unverified_material_claims(engine: PolicyEngine, ctx: ToolContext) -> Decision | None:
    material_fields = ("metal", "purity", "plating_type", "plating_thickness", "stone", "carat", "weight")
    fields_payload: dict = ctx.payload.get("fields", {})
    claimed = [f for f in material_fields if fields_payload.get(f) not in (None, "", "pending_workshop_verification")]
    if claimed and not ctx.payload.get("verified_source"):
        return Decision(
            policy_id="P6",
            action="deny",
            message="material claims without verified_source: "
            + ", ".join(claimed)
            + " — fields will be set to pending_workshop_verification",
            detail={"unverified_fields": claimed},
        )
    return None


def _p7_no_scraping(engine: PolicyEngine, ctx: ToolContext) -> Decision | None:
    url = str(ctx.payload.get("url", ""))
    if not url:
        return None
    host = re.sub(r"^https?://", "", url.lower()).split("/")[0]
    meta_domains = ("instagram.com", "facebook.com", "meta.com", "cdninstagram.com", "fbcdn.net")
    is_meta = any(host == d or host.endswith("." + d) for d in meta_domains)
    if not is_meta:
        return None
    is_graph = host == "graph.facebook.com"
    has_token = bool(ctx.payload.get("access_token") or ctx.metadata.get("oauth_token"))
    if is_graph and has_token:
        return None
    return Decision(
        policy_id="P7",
        action="deny",
        message="outbound call to Meta/Instagram must target an official Graph API endpoint "
        "with a valid OAuth token; scraping paths are structurally closed",
        detail={"url": url, "graph_endpoint": is_graph, "token_present": has_token},
    )


def _p8_context_separation(engine: PolicyEngine, ctx: ToolContext) -> Decision | None:
    tags: set[str] = set()
    for key in ("context_tag", "context_tags"):
        v = ctx.payload.get(key)
        if isinstance(v, str):
            tags.add(v)
        elif isinstance(v, (list, tuple, set)):
            tags.update(v)
    haystack = " ".join(
        str(ctx.payload.get(k, "")) for k in ("destination", "path", "record")
    ).lower()
    for name in COMMERCIAL_CONTEXTS | PUBLIC_SECTOR_CONTEXTS:
        if name in haystack:
            tags.add(name)
    if tags & COMMERCIAL_CONTEXTS and tags & PUBLIC_SECTOR_CONTEXTS:
        return Decision(
            policy_id="P8",
            action="deny",
            message="operation mixes commercial (Beyond Style/BCGT) data with RTA/public-sector "
            "context in one record, path, or export bundle",
            detail={"context_tags": sorted(tags)},
        )
    return None


# ---- escalation policies -------------------------------------------------


def _e_licence_expiring(engine: PolicyEngine, ctx: ToolContext) -> Decision | None:
    from sqlmodel import select

    from bsos.memory.domain import Asset, Licence

    if ctx.db is None:
        return None
    licence_id = ctx.payload.get("licence_id")
    if not licence_id:
        return None
    licence = ctx.db.get(Licence, licence_id)
    if licence is None:
        return None
    days = int(engine.thresholds["licence_expiry_warning_days"])
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if now < licence.valid_to <= now + timedelta(days=days):
        affected = ctx.db.exec(select(Asset.id).where(Asset.licence_id == licence_id)).all()
        if ctx.payload.get("acknowledge_expiry"):
            return None
        return Decision(
            policy_id="E_LICENCE_EXPIRING",
            action="escalate",
            message=f"licence '{licence_id}' expires {licence.valid_to.date()} "
            f"(within {days} days); {len(affected)} asset(s) affected",
            detail={"licence_id": licence_id, "valid_to": str(licence.valid_to), "affected_assets": list(affected)},
        )
    return None


def _e_gate_margin(engine: PolicyEngine, ctx: ToolContext) -> Decision | None:
    score = ctx.payload.get("max_similarity")
    if score is None:
        return None
    threshold = float(engine.thresholds["originality_max_similarity"])
    margin = float(engine.thresholds["originality_escalation_margin"])
    if threshold - margin <= float(score) < threshold and not ctx.payload.get("margin_reviewed"):
        return Decision(
            policy_id="E_GATE_MARGIN",
            action="escalate",
            message=f"concept passed the originality gate but max similarity {score:.3f} is within "
            f"{margin:.2f} of the {threshold:.2f} threshold — human review required",
            detail={"max_similarity": score, "threshold": threshold, "margin": margin},
        )
    return None


def _e_price_floor_contradiction(engine: PolicyEngine, ctx: ToolContext) -> Decision | None:
    source_price = ctx.payload.get("source_price_aed")
    if source_price is None:
        return None
    floor = float(engine.thresholds["price_floor_aed"])
    if float(source_price) < floor and not ctx.payload.get("contradiction_reviewed"):
        return Decision(
            policy_id="E_SOURCE_CONTRADICTION",
            action="escalate",
            message=f"source database price AED {source_price} contradicts the Beyond Style "
            f"starting-price floor AED {floor:.0f} — flagged, not silently resolved",
            detail={"source_price_aed": source_price, "floor_aed": floor},
        )
    return None


def _e_supplier_mark(engine: PolicyEngine, ctx: ToolContext) -> Decision | None:
    flags = ctx.payload.get("flags", []) or []
    concerning = [f for f in flags if f in ("brand_mark_detected", "unverified_material_claim")]
    if concerning and not ctx.payload.get("mark_reviewed"):
        return Decision(
            policy_id="E_SUPPLIER_MARK",
            action="escalate",
            message="supplier asset carries " + " and ".join(concerning).replace("_", " ")
            + " — excluded pending human review (a prior supplier asset carried another "
            "goldsmith's mark alongside an unverified purity claim)",
            detail={"flags": concerning},
        )
    return None


def _build_policies() -> list[Policy]:
    return [
        Policy("P1", "NO_IMAGE_TO_GENERATOR", ("imagegen",), _p1_no_image_to_generator,
               "Generation adapters accept text prompts only; any image-carrying payload is rejected."),
        Policy("P2", "LICENCE_REQUIRED", ("licence_required",), _p2_licence_required,
               "Ingest/copy/export of third-party assets requires an active, in-scope, signed licence."),
        Policy("P3", "PROVENANCE_MINIMUM", ("brief_promote",), _p3_provenance_minimum,
               "Every brief attribute must be supported by >= 3 independent source records."),
        Policy("P4", "CORPUS_FLOOR", ("synthesis", "brief_promote"), _p4_corpus_floor,
               "Synthesis and briefing are blocked below 40 references across 12 distinct sources."),
        Policy("P5", "NO_AI_PUBLICATION", ("catalogue_export",), _p5_no_ai_publication,
               "Only workshop photographs reach customer-facing exports; AI renders stay CONCEPT_ONLY."),
        Policy("P6", "NO_UNVERIFIED_MATERIAL_CLAIMS", ("material_write",), _p6_no_unverified_material_claims,
               "Material fields require a verified source; otherwise pending_workshop_verification."),
        Policy("P7", "NO_SCRAPING", ("outbound_http",), _p7_no_scraping,
               "Meta/Instagram traffic must be official Graph API with OAuth; scraping is closed."),
        Policy("P8", "CONTEXT_SEPARATION", ("*",), _p8_context_separation,
               "Beyond Style/BCGT commercial data never mixes with RTA or public-sector context."),
        Policy("E_LICENCE_EXPIRING", "LICENCE_EXPIRY_WARNING", ("licence_required",), _e_licence_expiring),
        Policy("E_GATE_MARGIN", "ORIGINALITY_MARGIN_REVIEW", ("concept_promote",), _e_gate_margin),
        Policy("E_SOURCE_CONTRADICTION", "PRICE_FLOOR_CONTRADICTION", ("pricing",), _e_price_floor_contradiction),
        Policy("E_SUPPLIER_MARK", "SUPPLIER_MARK_REVIEW", ("ingest_finalize",), _e_supplier_mark),
    ]
