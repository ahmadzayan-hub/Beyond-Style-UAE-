"""Publisher skills: selection, catalogue export, manifest, provenance PDF.

Everything customer-facing is tagged `catalogue_export`, so P5 evaluates in
the guard: only origin=workshop_photograph assets pass; AI renders never
reach these tools' outputs. Every export writes MANIFEST.csv — non-negotiable.
"""

from __future__ import annotations

import csv
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlmodel import select

from bsos.kernel.contracts import ToolContext
from bsos.memory.domain import Asset, Licence, Product
from bsos.skills.registry import registry

CATEGORIES = (
    "necklaces", "bracelets", "anklets", "rings", "earrings",
    "gift_sets", "kids", "brooches", "mens_chains", "car_hangers_keychains",
)


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _write_manifest(ctx: ToolContext, out_dir: Path, assets: list[Asset]) -> Path:
    manifest = out_dir / "MANIFEST.csv"
    stamp = datetime.now(timezone.utc).isoformat()
    with manifest.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["filename", "origin", "source", "licence_id",
                         "licence_scope", "permalink", "export_timestamp"])
        for asset in assets:
            licence = ctx.db.get(Licence, asset.licence_id) if asset.licence_id else None
            writer.writerow([
                asset.filename, asset.origin, asset.source_handle,
                asset.licence_id or "own_asset",
                licence.scope if licence else "n/a",
                asset.permalink, stamp,
            ])
    return manifest


@registry.register("export.selection_resolve", required_grant="export.selection_resolve", tags=(),
                   description="Resolve a selection (category/review state) to exportable asset ids.")
def selection_resolve(ctx: ToolContext, category: str = "", origin: str = "workshop_photograph",
                      include_flagged: bool = False) -> dict[str, Any]:
    query = select(Asset).where(Asset.origin == origin)
    if category:
        query = query.where(Asset.category == category)
    assets = ctx.db.exec(query).all()
    if not include_flagged:
        assets = [a for a in assets if a.review_state == "clear"]
    return {"asset_ids": [a.id for a in assets], "count": len(assets)}


@registry.register("export.flat", required_grant="export.flat",
                   tags=("catalogue_export",), side_effects="fs",
                   description="Flat-folder export of selected assets with MANIFEST.csv (primary target).")
def flat_export(ctx: ToolContext, asset_ids: list[str],
                destination: str = "") -> dict[str, Any]:
    out_dir = ctx.paths.exports_catalogue / (destination or _timestamp())
    out_dir.mkdir(parents=True, exist_ok=True)
    assets = [ctx.db.get(Asset, aid) for aid in asset_ids]
    missing = [aid for aid, a in zip(asset_ids, assets) if a is None]
    if missing:
        raise ValueError(f"unknown asset ids: {missing}")
    for asset in assets:
        shutil.copy2(asset.path, out_dir / asset.filename)
    manifest = _write_manifest(ctx, out_dir, assets)
    return {"destination": str(out_dir), "files": len(assets), "manifest": str(manifest)}


@registry.register("export.tree", required_grant="export.tree",
                   tags=("catalogue_export",), side_effects="fs",
                   description="Category-tree export with MANIFEST.csv at the root.")
def tree_export(ctx: ToolContext, asset_ids: list[str],
                destination: str = "") -> dict[str, Any]:
    out_dir = ctx.paths.exports_catalogue / (destination or _timestamp())
    out_dir.mkdir(parents=True, exist_ok=True)
    assets = [ctx.db.get(Asset, aid) for aid in asset_ids]
    if any(a is None for a in assets):
        raise ValueError("unknown asset id in selection")
    by_category: dict[str, int] = {}
    for asset in assets:
        category = asset.category if asset.category in CATEGORIES else "gift_sets"
        cat_dir = out_dir / category
        cat_dir.mkdir(exist_ok=True)
        shutil.copy2(asset.path, cat_dir / asset.filename)
        by_category[category] = by_category.get(category, 0) + 1
    manifest = _write_manifest(ctx, out_dir, assets)
    return {"destination": str(out_dir), "by_category": by_category, "manifest": str(manifest)}


@registry.register("export.products_json", required_grant="export.products_json",
                   tags=("catalogue_export",), side_effects="fs",
                   description="products.json matching the existing Beyond Style catalogue schema; "
                               "text fields left empty for manual completion.")
def products_json_export(ctx: ToolContext, asset_ids: list[str],
                         destination: str = "") -> dict[str, Any]:
    import json

    out_dir = ctx.paths.exports_catalogue / (destination or _timestamp())
    out_dir.mkdir(parents=True, exist_ok=True)
    assets = [ctx.db.get(Asset, aid) for aid in asset_ids]
    if any(a is None for a in assets):
        raise ValueError("unknown asset id in selection")
    products = []
    for i, asset in enumerate(assets, 1):
        product_row = ctx.db.exec(
            select(Product).where(Product.image_asset_id == asset.id)
        ).first()
        products.append({
            "product_code": product_row.product_code if product_row else f"BS-{_timestamp()[:8]}-{i:03d}",
            "category": asset.category if asset.category in CATEGORIES else "",
            "image_file": asset.filename,
            "source_handle": asset.source_handle,
            "licence_id": asset.licence_id or "own_asset",
            "caption_original": asset.caption,
            "name_en": "", "name_ar": "",
            "description_en": "", "description_ar": "",
            "starting_price_aed": product_row.starting_price_aed if product_row else None,
        })
    path = out_dir / "products.json"
    path.write_text(json.dumps(products, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest = _write_manifest(ctx, out_dir, assets)
    return {"destination": str(out_dir), "products": len(products),
            "path": str(path), "manifest": str(manifest)}


@registry.register("manifest.write", required_grant="manifest.write",
                   tags=("catalogue_export",), side_effects="fs",
                   description="Standalone manifest write for an existing export directory.")
def manifest_write(ctx: ToolContext, asset_ids: list[str], destination: str) -> dict[str, Any]:
    out_dir = ctx.paths.exports_catalogue / destination
    if not out_dir.exists():
        raise FileNotFoundError(f"export directory missing: {out_dir}")
    assets = [ctx.db.get(Asset, aid) for aid in asset_ids]
    manifest = _write_manifest(ctx, out_dir, [a for a in assets if a])
    return {"manifest": str(manifest)}


@registry.register("export.provenance_pdf", required_grant="export.provenance_pdf",
                   tags=(), side_effects="fs",
                   description="Export a concept's full provenance chain as a signed PDF.")
def provenance_pdf(ctx: ToolContext, concept_id: int, destination: str = "") -> dict[str, Any]:
    prov = ctx.adapters.require("provenance")
    out = ctx.paths.exports / (destination or f"provenance-concept-{concept_id}.pdf")
    path = prov.export_pdf(concept_id, out)
    return {"concept_id": concept_id, "pdf": str(path),
            "chain_length": len(prov.chain(concept_id))}


@registry.register("ledger.append", required_grant="ledger.append",
                   tags=(), description="Publisher note into the audit ledger.")
def ledger_append(ctx: ToolContext, note: str, data: dict | None = None) -> dict[str, Any]:
    entry = ctx.kernel.ledger.append("publisher_note", actor=ctx.agent,
                                     data={"note": note, **(data or {})}, outcome="ok")
    return {"seq": entry["seq"]}
