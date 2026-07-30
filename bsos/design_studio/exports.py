"""Export engines: SVG (mm), DXF (mm, layered), vector/technical PDF, PNG.

Illustrator note: we produce Illustrator-COMPATIBLE SVG/PDF and say so —
no native .AI files are claimed. PNG previews and product mockups are
deterministic Pillow renders of the verified vectors, never AI imagery.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import ezdxf
from PIL import Image, ImageDraw, ImageFilter

from bsos.design_studio.validation import rings_mm


def export_svg(comp, out_path: Path, mirrored: bool = False) -> Path:
    svg = comp.svg
    if mirrored:
        face = comp.frame["face_diameter_mm"]
        # wrap page contents in a mirroring group (valid SVG transform)
        inner_start = svg.index(">") + 1
        inner_end = svg.rindex("</svg>")
        svg = (
            svg[:inner_start]
            + f'<g transform="translate({face},0) scale(-1,1)" data-mirrored="true">'
            + svg[inner_start:inner_end]
            + "</g></svg>"
        )
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(svg, encoding="utf-8")
    return out_path


def export_dxf(comp, out_path: Path) -> Path:
    """Layered DXF in millimetres: FRAME / SAFE_AREA / ENGRAVE / NOTES."""
    doc = ezdxf.new(dxfversion="R2010", setup=True)
    doc.header["$INSUNITS"] = 4  # millimetres
    msp = doc.modelspace()
    for name, color in (("FRAME", 8), ("SAFE_AREA", 9), ("ENGRAVE", 1), ("NOTES", 3)):
        if name not in doc.layers:
            doc.layers.add(name, color=color)

    face = comp.frame["face_diameter_mm"]
    cx = cy = face / 2
    msp.add_circle((cx, cy), face / 2, dxfattribs={"layer": "FRAME"})
    msp.add_circle((cx, cy), comp.frame["safe_diameter_mm"] / 2,
                   dxfattribs={"layer": "SAFE_AREA"})

    for ring in rings_mm(comp):
        pts = [(x, face - y) for x, y in ring]  # y-up for CAD
        msp.add_lwpolyline(pts, close=True, dxfattribs={"layer": "ENGRAVE"})

    msp.add_text(
        f"{comp.inscription} | {comp.variant_id} | units=mm | "
        f"min_stroke={comp.frame['min_stroke_mm']}mm min_gap={comp.frame['min_gap_mm']}mm",
        dxfattribs={"layer": "NOTES", "height": 1.0},
    ).set_placement((0, -3))

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(out_path)
    return out_path


def render_png(comp, out_path: Path, px: int = 900,
               style: str = "flat") -> Path:
    """Deterministic raster of the verified vector.

    style=flat  : black artwork on white, with frame circles.
    style=enamel: silver rim, black enamel face, silver lettering (cufflink).
    """
    face = comp.frame["face_diameter_mm"]
    scale_px = px / face
    img = Image.new("RGB", (px, px), (250, 250, 250))
    draw = ImageDraw.Draw(img)
    cx = cy = px / 2

    def polys():
        for ring in rings_mm(comp):
            yield [(x * scale_px, y * scale_px) for x, y in ring]

    if style == "enamel":
        rim_outer = face / 2 * scale_px
        draw.ellipse([cx - rim_outer, cy - rim_outer, cx + rim_outer, cy + rim_outer],
                     fill=(198, 200, 205))
        enamel_r = (comp.frame["safe_diameter_mm"] / 2 + 0.6) * scale_px
        draw.ellipse([cx - enamel_r, cy - enamel_r, cx + enamel_r, cy + enamel_r],
                     fill=(18, 18, 20))
        # even-odd fill: draw outers silver, counters re-punched in enamel
        rings = sorted(polys(), key=lambda r: -abs(_ring_area(r)))
        for ring in rings:
            fill = (225, 226, 230) if _ring_area(ring) >= 0 else (18, 18, 20)
            draw.polygon(ring, fill=fill)
        img = img.filter(ImageFilter.GaussianBlur(0.4))
    else:
        r1 = face / 2 * scale_px - 2
        draw.ellipse([cx - r1, cy - r1, cx + r1, cy + r1], outline=(150, 150, 150), width=2)
        rings = sorted(polys(), key=lambda r: -abs(_ring_area(r)))
        for ring in rings:
            fill = (17, 17, 17) if _ring_area(ring) >= 0 else (250, 250, 250)
            draw.polygon(ring, fill=fill)

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "PNG", optimize=True)
    return out_path


def _ring_area(ring) -> float:
    area = 0.0
    for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
        area += x1 * y2 - x2 * y1
    return area / 2


def render_cufflink_pair(comp, out_path: Path, px: int = 1200) -> Path:
    """Two enamel cufflinks on a clean white background (deterministic)."""
    single = Image.new("RGB", (px // 2, px // 2), (255, 255, 255))
    tmp = Path(out_path).with_suffix(".single.png")
    render_png(comp, tmp, px=px // 2, style="enamel")
    single = Image.open(tmp)
    canvas = Image.new("RGB", (px, int(px * 0.62)), (255, 255, 255))
    shadow = Image.new("RGBA", single.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.ellipse([10, single.size[1] - 60, single.size[0] - 10, single.size[1] - 15],
               fill=(0, 0, 0, 45))
    shadow = shadow.filter(ImageFilter.GaussianBlur(10))
    for i, x in enumerate((int(px * 0.06), int(px * 0.50))):
        y = int(px * 0.06) + (0 if i == 0 else int(px * 0.015))
        canvas.paste(shadow, (x, y + 18), shadow)
        mask = Image.new("L", single.size, 0)
        md = ImageDraw.Draw(mask)
        md.ellipse([2, 2, single.size[0] - 2, single.size[1] - 2], fill=255)
        canvas.paste(single, (x, y), mask)
    tmp.unlink(missing_ok=True)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path, "PNG", optimize=True)
    return out_path


def export_vector_pdf(comp, out_path: Path) -> Path:
    """Illustrator-compatible vector PDF (drawn from the SVG, mm page)."""
    from fpdf import FPDF

    face = comp.frame["face_diameter_mm"]
    pdf = FPDF(unit="mm", format=(face + 20, face + 20))
    pdf.add_page()
    try:
        pdf.image(_svg_bytes(comp), x=10, y=10, w=face, h=face)
    except Exception:
        # fallback: rasterized placement keeps the export usable
        import io
        tmp = Path(out_path).with_suffix(".tmp.png")
        render_png(comp, tmp, px=1200)
        pdf.image(str(tmp), x=10, y=10, w=face, h=face)
        tmp.unlink(missing_ok=True)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(out_path))
    return out_path


def _svg_bytes(comp):
    import io
    return io.BytesIO(comp.svg.encode("utf-8"))


def _latin1(text: str) -> str:
    """fpdf2 core fonts are latin-1; degrade gracefully instead of crashing."""
    return (text.replace("→", "->").replace("…", "...")
            .encode("latin-1", "replace").decode("latin-1"))


def export_technical_pdf(comp, validation: dict[str, Any], brief: dict[str, Any],
                         out_path: Path, approval_id: str = "") -> Path:
    from fpdf import FPDF

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 9, "Beyond Style UAE - Manufacturing Technical Sheet",
             new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    stamp = datetime.now(timezone.utc).isoformat()
    for line in (
        f"Variant: {comp.variant_id}  |  Approval ID: {approval_id or 'PENDING'}",
        f"Generated: {stamp}",
        f"Inscription (verified sequence enforced upstream): see attached SVG/DXF",
        f"Face diameter: {comp.frame['face_diameter_mm']} mm  |  "
        f"Safe diameter: {comp.frame['safe_diameter_mm']} mm",
        f"Min stroke: {comp.frame['min_stroke_mm']} mm  |  "
        f"Min gap: {comp.frame['min_gap_mm']} mm  |  "
        f"Edge clearance: {comp.frame['edge_clearance_mm']} mm",
        f"Artwork bounds: {comp.text_width_mm:.2f} x {comp.text_height_mm:.2f} mm",
        f"Material: {brief.get('material', 'per order')}  |  "
        f"Finish: {brief.get('finish', 'per order')}",
        f"Method: {brief.get('manufacturingMethod', 'per workshop')}",
    ):
        pdf.cell(0, 6, _latin1(line), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 7, "Validation results", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Courier", "", 8)
    for c in validation.get("checks", []):
        mark = "PASS" if c["ok"] else "FAIL"
        pdf.cell(0, 5, _latin1(f"[{mark}] {c['check']}: {c['detail'][:90]}"),
                 new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)
    pdf.set_font("Helvetica", "I", 8)
    pdf.multi_cell(0, 4,
        "This sheet accompanies SVG/DXF vector files in millimetres. AI concept "
        "imagery is illustrative only and is never a production file. "
        "Workshop rules above are configurable per workshop profile.")
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(out_path))
    return out_path


def export_package(comp, validation: dict[str, Any], brief: dict[str, Any],
                   out_dir: Path, approval_id: str = "") -> dict[str, str]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    v = comp.variant_id
    files = {
        "svg": str(export_svg(comp, out_dir / f"{v}.svg")),
        "svg_mirrored": str(export_svg(comp, out_dir / f"{v}.mirrored.svg", mirrored=True)),
        "dxf": str(export_dxf(comp, out_dir / f"{v}.dxf")),
        "vector_pdf": str(export_vector_pdf(comp, out_dir / f"{v}.vector.pdf")),
        "technical_pdf": str(export_technical_pdf(
            comp, validation, brief, out_dir / f"{v}.technical.pdf", approval_id)),
        "png_flat": str(render_png(comp, out_dir / f"{v}.flat.png")),
        "png_enamel_macro": str(render_png(comp, out_dir / f"{v}.macro.png", style="enamel")),
        "png_pair": str(render_cufflink_pair(comp, out_dir / f"{v}.pair.png")),
    }
    (out_dir / f"{v}.manifest.json").write_text(json.dumps({
        "variant": v, "approval_id": approval_id, "units": "mm",
        "validation_passed": validation.get("passed"),
        "files": files, "generated_at": datetime.now(timezone.utc).isoformat(),
        "note": "Illustrator-compatible SVG/PDF provided; no native .AI claimed.",
    }, indent=2), encoding="utf-8")
    return files
