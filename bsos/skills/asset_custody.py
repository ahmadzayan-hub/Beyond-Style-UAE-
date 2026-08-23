"""Custodian skills: licences, ingest pipeline, library reconciliation.

Ingest is a pipeline of small skills: download/copy → dedupe → resolution
gate → mark detect → sidecar write. Every third-party ingest carries a
licence_id and is policy-checked by P2 before any byte lands in the library.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlmodel import select

from bsos.kernel.contracts import ToolContext
from bsos.memory.domain import Asset, Licence, utcnow
from bsos.skills.registry import registry


@registry.register("licence.create", required_grant="licence.create", tags=(),
                   side_effects="db", description="Create a licence record for a signed permission document.")
def licence_create(ctx: ToolContext, licence_id: str, licensor: str, scope: str,
                   signed_doc_path: str, valid_from: str, valid_to: str,
                   licensor_handle: str = "", notes: str = "") -> dict[str, Any]:
    doc = Path(signed_doc_path)
    if not doc.exists():
        raise FileNotFoundError(f"signed document not found on disk: {signed_doc_path}")
    licence = Licence(
        id=licence_id, licensor=licensor, licensor_handle=licensor_handle,
        scope=scope, signed_doc_path=str(doc),
        valid_from=datetime.fromisoformat(valid_from),
        valid_to=datetime.fromisoformat(valid_to), notes=notes,
    )
    ctx.db.add(licence)
    return {"licence_id": licence_id, "scope": scope, "valid_to": valid_to}


@registry.register("licence.verify", required_grant="licence.verify", tags=(),
                   description="Report licence validity: document, dates, scope.")
def licence_verify(ctx: ToolContext, licence_id: str) -> dict[str, Any]:
    licence = ctx.db.get(Licence, licence_id)
    if licence is None:
        return {"licence_id": licence_id, "valid": False, "problems": ["not found"]}
    problems = []
    if not Path(licence.signed_doc_path).exists():
        problems.append("signed document missing")
    if licence.valid_to <= utcnow():
        problems.append(f"expired {licence.valid_to.date()}")
    days_left = (licence.valid_to - utcnow()).days
    return {
        "licence_id": licence_id, "valid": not problems, "problems": problems,
        "days_left": days_left, "scope": licence.scope, "licensor": licence.licensor,
    }


@registry.register("library.inbox_watch", required_grant="library.inbox_watch", tags=(),
                   side_effects="fs", description="List files waiting in library/inbox.")
def inbox_watch(ctx: ToolContext) -> dict[str, Any]:
    files = sorted(
        str(p.relative_to(ctx.paths.library_inbox))
        for p in ctx.paths.library_inbox.rglob("*")
        if p.is_file() and not p.name.startswith(".")
    )
    return {"pending": files, "count": len(files)}


@registry.register(
    "library.ingest", required_grant="library.ingest",
    tags=("licence_required", "ingest_finalize"), side_effects="fs+db",
    description="Ingest one file: copy to originals, dedupe, resolution gate, mark detect, sidecar.",
)
def library_ingest(ctx: ToolContext, file_path: str, licence_id: str,
                   origin: str = "manual_inbox", source_handle: str = "",
                   permalink: str = "", caption: str = "", category: str = "",
                   use: str = "ingest", flags: list | None = None,
                   acknowledge_expiry: bool = False, mark_reviewed: bool = False,
                   context_tag: str = "beyond_style") -> dict[str, Any]:
    # P2 (licence) and escalation policies have already passed in the guard.
    from bsos.skills.imaging import perceptual_hash, sha256_file

    src = Path(file_path)
    if not src.is_absolute():
        src = ctx.paths.library_inbox / file_path
    if not src.exists():
        raise FileNotFoundError(f"ingest source missing: {src}")

    sha = sha256_file(src)
    asset_id = sha[:16]

    # Dedupe on exact hash.
    existing = ctx.db.exec(select(Asset).where(Asset.sha256 == sha)).first()
    if existing:
        src.unlink(missing_ok=True)
        return {"asset_id": existing.id, "status": "duplicate_exact", "kept": existing.path}

    from PIL import Image

    with Image.open(src) as im:
        width, height = im.size
    phash = perceptual_hash(src)

    detected_flags = list(flags or [])
    review_state = "clear"

    # Near-duplicate check on perceptual hash.
    from bsos.skills.imaging import phash_distance

    for other in ctx.db.exec(select(Asset)).all():
        if other.phash and phash_distance(phash, other.phash) <= 6:
            detected_flags.append("near_duplicate")
            review_state = "duplicate_review"
            break

    # Resolution gate.
    min_res = int(ctx.kernel.policy_engine.thresholds["asset_min_resolution"])
    if min(width, height) < min_res:
        detected_flags.append("low_resolution")
        review_state = "resolution_review"

    # Mark detection (OCR of bottom strip + corners).
    mark = _detect_marks(src)
    if mark["flagged"]:
        detected_flags.append("brand_mark_detected")
        review_state = "mark_review"

    dest = ctx.paths.library_originals / f"{asset_id}{src.suffix.lower()}"
    shutil.copy2(src, dest)
    if ctx.paths.library_inbox in src.parents:
        src.unlink(missing_ok=True)

    asset = Asset(
        id=asset_id, filename=dest.name, path=str(dest), sha256=sha, phash=phash,
        origin=origin, source_handle=source_handle, permalink=permalink,
        licence_id=licence_id, width=width, height=height, flags=detected_flags,
        review_state=review_state, caption=caption, category=category,
        context_tag=context_tag,
    )
    ctx.db.add(asset)

    sidecar = _write_sidecar(ctx, asset, mark)
    return {
        "asset_id": asset_id, "status": "ingested", "review_state": review_state,
        "flags": detected_flags, "sidecar": str(sidecar),
        "detected_text": mark.get("text", ""),
    }


def _detect_marks(image_path: Path) -> dict[str, Any]:
    """OCR the bottom 15% and the four corners; flag any text. Never remove.

    Uses pytesseract when installed; otherwise falls back to a high-contrast
    text-likeness heuristic and reports which engine ran, so a reviewer knows
    the confidence level of a 'clear' verdict.
    """
    from PIL import Image

    with Image.open(image_path) as im:
        im = im.convert("L")
        w, h = im.size
        corner = max(64, min(w, h) // 5)
        regions = [
            im.crop((0, int(h * 0.85), w, h)),  # bottom 15%
            im.crop((0, 0, corner, corner)),
            im.crop((w - corner, 0, w, corner)),
            im.crop((0, h - corner, corner, h)),
            im.crop((w - corner, h - corner, w, h)),
        ]
        try:
            import pytesseract

            text = " ".join(pytesseract.image_to_string(r).strip() for r in regions).strip()
            return {"flagged": bool(text), "text": text, "engine": "tesseract"}
        except Exception:
            import numpy as np

            score = 0.0
            for r in regions:
                arr = np.asarray(r, dtype=np.float32)
                edges = np.abs(np.diff(arr, axis=1))
                score = max(score, float((edges > 60).mean()))
            return {"flagged": score > 0.06, "text": "", "engine": "heuristic",
                    "edge_density": round(score, 4)}


def _write_sidecar(ctx: ToolContext, asset: Asset, mark: dict[str, Any]) -> Path:
    sidecar = ctx.paths.library_meta / f"{asset.id}.json"
    sidecar.write_text(json.dumps({
        "asset_id": asset.id, "filename": asset.filename, "sha256": asset.sha256,
        "phash": asset.phash, "origin": asset.origin, "source_handle": asset.source_handle,
        "permalink": asset.permalink, "licence_id": asset.licence_id,
        "width": asset.width, "height": asset.height, "flags": asset.flags,
        "review_state": asset.review_state, "caption": asset.caption,
        "category": asset.category, "context_tag": asset.context_tag,
        "mark_detection": mark, "ingested_at": str(utcnow()),
    }, indent=2), encoding="utf-8")
    return sidecar


@registry.register("library.reconcile", required_grant="library.reconcile", tags=(),
                   side_effects="fs+db",
                   description="Rebuild the asset index from sidecars: disk is the source of truth.")
def library_reconcile(ctx: ToolContext) -> dict[str, Any]:
    seen, restored, orphaned = 0, 0, []
    for sidecar in sorted(ctx.paths.library_meta.glob("*.json")):
        data = json.loads(sidecar.read_text(encoding="utf-8"))
        seen += 1
        original = ctx.paths.library_originals / data["filename"]
        if not original.exists():
            orphaned.append(data["asset_id"])
            continue
        if ctx.db.get(Asset, data["asset_id"]) is None:
            ctx.db.add(Asset(
                id=data["asset_id"], filename=data["filename"], path=str(original),
                sha256=data["sha256"], phash=data.get("phash", ""), origin=data["origin"],
                source_handle=data.get("source_handle", ""), permalink=data.get("permalink", ""),
                licence_id=data.get("licence_id"), width=data.get("width", 0),
                height=data.get("height", 0), flags=data.get("flags", []),
                review_state=data.get("review_state", "clear"),
                caption=data.get("caption", ""), category=data.get("category", ""),
                context_tag=data.get("context_tag", "beyond_style"),
            ))
            restored += 1
    return {"sidecars": seen, "restored": restored, "orphaned_sidecars": orphaned}


@registry.register(
    "graph.business_discovery", required_grant="graph.business_discovery",
    tags=("outbound_http", "licence_required"), side_effects="network",
    description="Fetch a professional account's profile and media via Business Discovery.",
)
def graph_business_discovery(ctx: ToolContext, target_username: str, licence_id: str,
                             url: str = "https://graph.facebook.com/v25.0/",
                             access_token: str = "", use: str = "ingest",
                             max_items: int = 50,
                             acknowledge_expiry: bool = False) -> dict[str, Any]:
    graph = ctx.adapters.require("graph")
    items = list(graph.iter_media(target_username, max_items=max_items))
    from bsos.kernel.metrics import GRAPH_BUDGET

    GRAPH_BUDGET.set(graph.bucket.remaining)
    return {
        "target": target_username, "media_count": len(items), "media": items,
        "rate_budget_remaining": graph.bucket.remaining,
    }


@registry.register(
    "graph.own_media", required_grant="graph.own_media",
    tags=("outbound_http",), side_effects="network",
    description="Fetch the brand's own media (supplier-authorised OAuth mode).",
)
def graph_own_media(ctx: ToolContext, url: str = "https://graph.facebook.com/v25.0/",
                    access_token: str = "", limit: int = 50) -> dict[str, Any]:
    graph = ctx.adapters.require("graph")
    data = graph.own_media(limit=limit)
    return {"media": data.get("data", []), "rate_budget_remaining": graph.bucket.remaining}


@registry.register(
    "vision.extract_video", required_grant="vision.extract_video",
    tags=("licence_required",), side_effects="fs",
    description="Sample frames from a licensed video, abstract each into attribute JSON, "
                "and aggregate by majority. Frames and video go no further than this call.",
)
def vision_extract_video(ctx: ToolContext, file_path: str, licence_id: str,
                         max_frames: int = 6, use: str = "ingest",
                         acknowledge_expiry: bool = False) -> dict[str, Any]:
    src = Path(file_path)
    if not src.is_absolute():
        src = ctx.paths.library_inbox / file_path
    if not src.exists():
        raise FileNotFoundError(f"video not found: {src}")

    extractor = ctx.adapters.require("vision")
    frames_dir = ctx.paths.var / "video_frames" / src.stem
    # sample_video_frames lives behind the vision adapter boundary via ctx
    frames = ctx.adapters.require("video_sampler")(src, frames_dir, max_frames)

    from collections import Counter

    per_frame, marks = [], []
    for frame in frames:
        per_frame.append(extractor.extract_attributes(frame))
        mark = _detect_marks(frame)
        if mark["flagged"]:
            marks.append({"frame": frame.name, **mark})

    # Majority vote per attribute across frames.
    aggregated: dict[str, dict] = {}
    for section in per_frame[0]:
        aggregated[section] = {}
        for key in per_frame[0][section]:
            values = [f[section][key] for f in per_frame
                      if not isinstance(f[section][key], list)]
            if values:
                aggregated[section][key] = Counter(map(str, values)).most_common(1)[0][0]
            else:
                aggregated[section][key] = per_frame[0][section][key]

    return {
        "video": src.name, "frames_analysed": len(frames),
        "attributes": aggregated, "per_frame": per_frame,
        "marks": marks, "source_url": str(src),
    }


@registry.register(
    "brain.search", required_grant="brain.search", tags=(),
    description="Read-only search over the owner's Second Brain notes.",
)
def brain_search(ctx: ToolContext, query: str, limit: int = 10) -> dict[str, Any]:
    brain = ctx.adapters.require("brain")
    return {"query": query, "results": brain.search(query, limit)}


@registry.register(
    "vision.extract", required_grant="vision.extract", tags=(),
    side_effects="db",
    description="Abstract an asset into attribute JSON; embed and hash it for the gate. "
                "The image goes no further than this call.",
)
def vision_extract(ctx: ToolContext, asset_id: str) -> dict[str, Any]:
    asset = ctx.db.get(Asset, asset_id)
    if asset is None:
        raise ValueError(f"asset '{asset_id}' not found")
    if asset.review_state == "excluded":
        raise ValueError(f"asset '{asset_id}' is excluded from processing")
    extractor = ctx.adapters.require("vision")
    attributes = extractor.extract_attributes(Path(asset.path))

    embedder = ctx.adapters.require("embedder")
    vector_store = ctx.adapters.require("vector_store")
    vector_store.upsert(f"corpus:{asset_id}", embedder.embed_image(Path(asset.path)),
                        namespace="corpus")
    return {"asset_id": asset_id, "attributes": attributes,
            "source_url": asset.permalink or asset.path,
            "embedder": embedder.describe()}
