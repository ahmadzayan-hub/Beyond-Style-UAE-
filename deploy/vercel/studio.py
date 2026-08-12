"""Live Design Studio API for the hosted preview (Vercel serverless).

This is the REAL deterministic pipeline — the same HarfBuzz shaping,
structural spelling verification, shapely geometry validation and pricing
engine that run in the full local system — exposed statelessly so the
hosted site delivers genuine outputs for any name a customer types.

Because the pipeline is deterministic, no database is needed: every
response is recomputed from the inscription itself.

Honesty rules preserved on the public host: spelling verification is
structural (failures return human_review), and every file is extractable —
vector/technical files are marked PREVIEW until the workshop-approval
workflow signs them off in the full system.
"""

from __future__ import annotations

import re
import tempfile
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import Response

app = FastAPI(title="Beyond Style — Live Design Studio")

MAX_LEN = 40
VARIANTS = ("luxury_diwani_jali", "balanced_diwani", "manufacturing_optimized")


_ARABIC_RE = re.compile(r"[؀-ۿ]")
_LATIN_RE = re.compile(r"[A-Za-z]")


def _mixed_parts(text: str) -> tuple[str, str] | None:
    """If the inscription mixes Arabic and Latin, return the two parts."""
    if _ARABIC_RE.search(text) and _LATIN_RE.search(text):
        arabic = " ".join(w for w in text.split() if _ARABIC_RE.search(w))
        latin = " ".join(w for w in text.split() if _LATIN_RE.search(w)
                         and not _ARABIC_RE.search(w))
        return arabic, latin
    return None


def _pipeline(text: str, item: str = "cufflink"):
    from bsos.design_studio.composition import compose_all, frame_for
    from bsos.design_studio.pricing import PRICING_RULES, estimate
    from bsos.design_studio.typography import engine_for
    from bsos.design_studio.validation import validate_composition

    if item not in PRICING_RULES["base_by_item"]:
        item = "cufflink"
    engine = engine_for("Amiri-Regular")
    shaped = engine.shape(text)
    letters = engine.letter_sequence(shaped.normalized_text)
    result = {
        "input": text,
        "normalized": shaped.normalized_text,
        "item": item,
        "frame": frame_for(item),
        "letter_sequence": letters,
        "verification": shaped.verification,
        "variants": [],
    }
    if not shaped.verified:
        return result, None

    comps = compose_all(shaped.normalized_text, frame_for(item))
    letter_count = len([c for c in letters if c["char"].strip()])
    for comp in comps:
        report = validate_composition(comp)
        price = estimate(item, comp.variant_id, letter_count)
        result["variants"].append({
            "variant_id": comp.variant_id,
            "svg": comp.svg,
            "spelling_verified": bool(comp.verification.get("passed")),
            "validation_passed": report.passed,
            "failed_checks": [c["check"] for c in report.checks if not c["ok"]],
            "meta": comp.meta,
            "text_mm": [round(comp.text_width_mm, 2), round(comp.text_height_mm, 2)],
            "price_from_aed": price.get("unit_price_aed"),
        })
    return result, comps


@app.get("/api/studio/preview")
def preview(text: str = Query(..., min_length=1, max_length=MAX_LEN),
            item: str = Query("cufflink")):
    if not text.strip():
        raise HTTPException(422, "inscription is empty")
    mixed = _mixed_parts(text)
    if mixed:
        return {
            "input": text, "status": "mixed_script",
            "arabic_part": mixed[0], "latin_part": mixed[1],
            "verification": {"passed": False, "issues": [
                "inscription mixes Arabic and Latin — engrave one script per side, "
                "or pick one below"],
                "issues_ar": ["النقش يخلط العربية واللاتينية — يُنقش كل نص على وجه، "
                              "أو اختر أحدهما"]},
            "letter_sequence": [], "variants": [],
        }
    result, _ = _pipeline(text, item)
    result["status"] = (
        "human_review" if not result["verification"].get("passed")
        else "manufacturing_checked"
        if any(v["validation_passed"] for v in result["variants"])
        else "variants_composed"
    )
    result["note"] = (
        "Live deterministic pipeline. All files are extractable; vector and "
        "technical files are marked PREVIEW until workshop approval in the "
        "full system."
    )
    return result


@app.get("/api/studio/transliterate")
def transliterate(text: str = Query(..., min_length=1, max_length=MAX_LEN)):
    from bsos.design_studio.transliteration import suggest
    from bsos.design_studio.typography import engine_for

    result = suggest(text)
    engine = engine_for("Amiri-Regular")
    for word in result["words"]:
        for s in word["suggestions"]:
            s["typography_verifiable"] = bool(engine.shape(s["arabic"]).verified)
    for c in result["combined"]:
        c["typography_verifiable"] = bool(engine.shape(c["arabic"]).verified)
    return result


PREVIEW_MARK = "PREVIEW - PENDING WORKSHOP APPROVAL"
FORMATS = ("png", "pair", "svg", "svg_mirrored", "pdf",
           "dxf", "vector_pdf", "technical_pdf", "zip")


@app.get("/api/studio/export")
def export(text: str = Query(..., min_length=1, max_length=MAX_LEN),
           variant: str = Query("manufacturing_optimized"),
           item: str = Query("cufflink"),
           fmt: str = Query("png", alias="format")):
    """Every output is extractable. Vector/technical files carry an explicit
    PREVIEW marking until the workshop-approval workflow signs them off -
    they are deterministic verified vectors, never AI imagery."""
    if variant not in VARIANTS:
        raise HTTPException(422, f"unknown variant '{variant}'")
    if fmt not in FORMATS:
        raise HTTPException(422, f"unsupported format '{fmt}' - use one of {FORMATS}")

    result, comps = _pipeline(text, item)
    if comps is None:
        raise HTTPException(409, {"reason": "spelling did not verify",
                                  "issues": result["verification"].get("issues", [])})
    comp = next(c for c in comps if c.variant_id == variant)

    from bsos.design_studio.exports import (
        export_dxf, export_package, export_svg, export_technical_pdf,
        export_vector_pdf, render_cufflink_pair, render_png,
    )
    from bsos.design_studio.validation import validate_composition

    def _resp(data: bytes, media: str, filename: str) -> Response:
        return Response(data, media_type=media, headers={
            "Content-Disposition": f'attachment; filename="{filename}"'})

    if fmt == "svg":
        face = comp.frame["face_diameter_mm"]
        svg = comp.svg.replace(
            "</svg>",
            f'<text x="{face/2}" y="{face - 0.6}" font-size="{face*0.04}" '
            f'text-anchor="middle" fill="#999">{PREVIEW_MARK}</text></svg>')
        return _resp(svg.encode(), "image/svg+xml", f"{variant}.preview.svg")

    with tempfile.TemporaryDirectory() as td_str:
        td = Path(td_str)
        if fmt == "zip":
            import io
            import zipfile

            report = validate_composition(comp)
            export_package(comp, report.to_dict(), {"item": item},
                           td, approval_id=PREVIEW_MARK)
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
                for f in sorted(td.iterdir()):
                    z.write(f, f.name)
            return _resp(buf.getvalue(), "application/zip",
                         f"beyond-style-{variant}-{item}.preview.zip")
        if fmt == "svg_mirrored":
            out = export_svg(comp, td / "m.svg", mirrored=True)
            return _resp(out.read_bytes(), "image/svg+xml",
                         f"{variant}.mirrored.preview.svg")
        if fmt == "dxf":
            out = export_dxf(comp, td / "a.dxf", note=PREVIEW_MARK)
            return _resp(out.read_bytes(), "application/dxf",
                         f"{variant}.preview.dxf")
        if fmt == "vector_pdf":
            out = export_vector_pdf(comp, td / "v.pdf")
            return _resp(out.read_bytes(), "application/pdf",
                         f"{variant}.vector.preview.pdf")
        if fmt == "technical_pdf":
            report = validate_composition(comp)
            out = export_technical_pdf(comp, report.to_dict(), {"item": item},
                                       td / "t.pdf", approval_id=PREVIEW_MARK)
            return _resp(out.read_bytes(), "application/pdf",
                         f"{variant}.technical.preview.pdf")
        if fmt == "pair":
            out = td / "pair.png"
            render_cufflink_pair(comp, out)
            return _resp(out.read_bytes(), "image/png", f"{variant}.pair.png")
        if fmt == "png":
            out = td / "macro.png"
            render_png(comp, out, style="enamel")
            return _resp(out.read_bytes(), "image/png", f"{variant}.macro.png")
        # pdf - customer approval sheet
        from fpdf import FPDF
        png = td / "art.png"
        render_cufflink_pair(comp, png)
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(0, 10, "Beyond Style UAE - Design Preview",
                 new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 6, f"Variant: {variant}  |  Item: {item}  |  Starting price from AED "
                       f"{next(v['price_from_aed'] for v in result['variants'] if v['variant_id'] == variant)}",
                 new_x="LMARGIN", new_y="NEXT")
        pdf.image(str(png), x=20, y=35, w=170)
        pdf.set_y(150)
        pdf.set_font("Helvetica", "I", 9)
        pdf.multi_cell(0, 5, "PREVIEW ONLY - pending workshop approval. Spelling "
                             "verified structurally by the deterministic "
                             "typography engine. Final price confirmed on "
                             "WhatsApp +971 55 561 5509.")
        return _resp(bytes(pdf.output()), "application/pdf", f"{variant}.sheet.pdf")


@app.get("/api/studio/health")
def health():
    from bsos.design_studio.typography import available_fonts
    return {"ok": True, "engine": "harfbuzz+fonttools (deterministic)",
            "fonts": sorted(available_fonts())}
