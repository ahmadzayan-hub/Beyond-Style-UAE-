"""Diwani-inspired composition for jewellery frames.

A digital font alone is not authentic Diwani Jali; this module is honest
about that. It produces three *Diwani-inspired* compositions from verified
shaped text, applying controlled geometric treatment (arc baselines,
overlap, weight) on top of a licensed base font, and records per-variant
legibility/feasibility indicators. The `luxury` variant is additionally
flagged `expert_review_recommended` — a calligrapher review state, exactly
as the workflow requires.

All geometry is emitted in millimetres inside a configurable circular frame
(cufflink default: 20 mm face, 17 mm safe diameter).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from bsos.design_studio.typography import ShapingResult, TypographyEngine

# Configurable workshop rules, not universal assumptions.
DEFAULT_FRAME = {
    "face_diameter_mm": 20.0,
    "safe_diameter_mm": 17.0,
    "edge_clearance_mm": 1.5,
    "min_stroke_mm": 0.70,   # positive feature
    "min_gap_mm": 0.45,      # negative feature
}

# Circular face presets per item type (stroke/gap rules stay the workshop
# defaults). Bracelet is modelled as a round charm plate for now.
FRAME_PRESETS: dict[str, dict[str, float]] = {
    "cufflink": {"face_diameter_mm": 20.0, "safe_diameter_mm": 17.0},
    "pendant": {"face_diameter_mm": 24.0, "safe_diameter_mm": 20.5},
    "ring": {"face_diameter_mm": 14.0, "safe_diameter_mm": 11.5},
    "brooch": {"face_diameter_mm": 30.0, "safe_diameter_mm": 26.0},
    "coin": {"face_diameter_mm": 32.0, "safe_diameter_mm": 28.0},
    "bracelet": {"face_diameter_mm": 22.0, "safe_diameter_mm": 19.0},
    "corporate_gift": {"face_diameter_mm": 40.0, "safe_diameter_mm": 35.0},
}


def frame_for(item_type: str) -> dict[str, float]:
    return {**DEFAULT_FRAME, **FRAME_PRESETS.get(item_type, {})}

VARIANT_SPECS = {
    "luxury_diwani_jali": {
        "label_en": "Luxury Diwani Jali (inspired)",
        "label_ar": "ديواني جلي فاخر (مستوحى)",
        "font": "Amiri-Regular",
        "tracking": -0.10,          # controlled overlap between letters
        "arc_degrees": 26,          # curved baseline
        "target_fill": 0.80,
        "expert_review_recommended": True,
        "notes": "rich overlap and curved baseline; a calligrapher should "
                 "review authenticity before customer presentation",
    },
    "balanced_diwani": {
        "label_en": "Balanced Diwani (inspired)",
        "label_ar": "ديواني متوازن (مستوحى)",
        "font": "Amiri-Regular",
        "tracking": 0.0,
        "arc_degrees": 12,
        "target_fill": 0.72,
        "expert_review_recommended": False,
        "notes": "elegant and easier to read",
    },
    "manufacturing_optimized": {
        "label_en": "Manufacturing-Optimized",
        "label_ar": "محسّن للتصنيع",
        "font": "Amiri-Bold",
        "tracking": 0.10,
        "arc_degrees": 0,
        "target_fill": 0.76,
        "reinforce_mm": 0.32,   # geometric stroke strengthening per side
        "expert_review_recommended": False,
        "notes": "bolder strokes, safer spacing, reduced fragile detail "
                 "for small jewellery",
    },
}


@dataclass
class Composition:
    variant_id: str
    inscription: str
    font_id: str
    frame: dict[str, float]
    svg: str                      # full SVG document, mm units
    path_d_mm: str                # inscription path in mm coordinates
    scale_mm_per_unit: float
    text_width_mm: float
    text_height_mm: float
    legibility: float             # 0..1 heuristic indicator
    feasibility_hint: float       # 0..1 pre-validation indicator
    verification: dict[str, Any]
    meta: dict[str, Any] = field(default_factory=dict)


def _arc_transformed_path(engine: TypographyEngine, shaped: ShapingResult,
                          tracking: float, arc_degrees: float) -> tuple[str, float, float]:
    """Position glyphs along a shallow arc with optional tracking overlap.

    Returns path in font units (y-down) plus width/height.
    """
    import math

    from fontTools.misc.transform import Transform
    from fontTools.pens.recordingPen import RecordingPen
    from fontTools.pens.svgPathPen import SVGPathPen
    from fontTools.pens.transformPen import TransformPen

    upem = shaped.upem
    advances = [g.x_advance * (1 + tracking) for g in shaped.glyphs]
    total = sum(advances)
    parts: list[str] = []
    x_cursor = 0.0
    baseline_y = upem * 0.78

    for g, adv in zip(shaped.glyphs, advances):
        center = (x_cursor + adv / 2) / max(total, 1)
        if arc_degrees:
            # shallow arch: middle raised, ends lowered; slight glyph rotation
            theta = math.radians(arc_degrees) * (center - 0.5)
            dy = -math.cos(theta * 2) if False else -(arc_degrees / 90) * upem * 0.22 * (
                1 - (2 * center - 1) ** 2
            )
            rot = -theta * 0.9
        else:
            dy, rot = 0.0, 0.0
        transform = (
            Transform(1, 0, 0, -1, x_cursor + g.x_offset, baseline_y + dy - g.y_offset)
            .rotate(rot)
        )
        rec = RecordingPen()
        engine._glyph_set[g.glyph_name].draw(TransformPen(rec, transform))
        spen = SVGPathPen(engine._glyph_set)
        rec.replay(spen)
        if spen.getCommands():
            parts.append(spen.getCommands())
        x_cursor += adv
    return " ".join(parts), x_cursor, upem


def compose_variant(variant_id: str, inscription: str,
                    frame: dict[str, float] | None = None,
                    engines: dict[str, TypographyEngine] | None = None) -> Composition:
    from bsos.design_studio.typography import engine_for

    spec = VARIANT_SPECS[variant_id]
    frame = {**DEFAULT_FRAME, **(frame or {})}
    engine = (engines or {}).get(spec["font"]) or engine_for(spec["font"])

    shaped = engine.shape(inscription)
    path_units, width_u, height_u = _arc_transformed_path(
        engine, shaped, spec["tracking"], spec["arc_degrees"]
    )

    # Fit and centre on the ACTUAL ink bounds — advance width and upem
    # fractions misplace words with deep descenders (e.g. نور).
    import math

    from bsos.design_studio.validation import _flatten_path

    rings_u = [r for r in _flatten_path(path_units, curve_steps=4) if len(r) >= 3]
    xs = [x for ring in rings_u for x, _ in ring]
    ys = [y for ring in rings_u for _, y in ring]
    minx_u, maxx_u = (min(xs), max(xs)) if xs else (0.0, max(width_u, 1))
    miny_u, maxy_u = (min(ys), max(ys)) if ys else (0.0, max(height_u, 1))
    real_w_u = max(maxx_u - minx_u, 1)
    real_h_u = max(maxy_u - miny_u, 1)

    usable = frame["safe_diameter_mm"]
    scale = (usable * spec["target_fill"]) / real_w_u
    scale = min(scale, (usable * 0.62) / real_h_u)
    # circle-fit cap: the ink bounding-box corner must stay inside the safe
    # circle; the margin absorbs stroke reinforcement growth.
    half_diag_u = math.hypot(real_w_u / 2, real_h_u / 2)
    scale = min(scale, (usable / 2 - 0.5) / half_diag_u)
    text_w = real_w_u * scale
    text_h = real_h_u * scale

    face = frame["face_diameter_mm"]
    cx = cy = face / 2
    tx = cx - (minx_u * scale) - text_w / 2
    ty = cy - (miny_u * scale) - text_h / 2

    path_mm = (
        f'<g transform="translate({tx:.3f},{ty:.3f}) scale({scale:.6f})">'
        f'<path d="{path_units}" fill="#111111"/></g>'
    )
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{face}mm" height="{face}mm" '
        f'viewBox="0 0 {face} {face}">'
        f'<circle cx="{cx}" cy="{cy}" r="{face/2 - 0.1}" fill="none" '
        f'stroke="#888" stroke-width="0.2"/>'
        f'<circle cx="{cx}" cy="{cy}" r="{frame["safe_diameter_mm"]/2}" fill="none" '
        f'stroke="#bbb" stroke-width="0.1" stroke-dasharray="0.6,0.6"/>'
        f"{path_mm}</svg>"
    )

    # Heuristic indicators (validation.py performs the hard checks).
    est_stroke_mm = scale * shaped.upem * (0.085 if "Bold" in spec["font"] else 0.062)
    legibility = max(0.0, min(1.0, 1.2 - abs(spec["tracking"]) * 2 - spec["arc_degrees"] / 90))
    feasibility = max(0.0, min(1.0, est_stroke_mm / frame["min_stroke_mm"]))

    comp = Composition(
        variant_id=variant_id, inscription=shaped.normalized_text,
        font_id=spec["font"], frame=frame, svg=svg,
        path_d_mm=path_units, scale_mm_per_unit=scale,
        text_width_mm=text_w, text_height_mm=text_h,
        legibility=round(legibility, 2), feasibility_hint=round(feasibility, 2),
        verification=shaped.verification,
        meta={
            "placement": {"tx": round(tx, 4), "ty": round(ty, 4)},
            "label_en": spec["label_en"], "label_ar": spec["label_ar"],
            "expert_review_recommended": spec["expert_review_recommended"],
            "estimated_stroke_mm": round(est_stroke_mm, 3),
            "notes": spec["notes"],
            "authenticity": "Diwani-INSPIRED composition over a licensed base "
                            "font; not certified traditional Diwani Jali",
        },
    )
    if spec.get("reinforce_mm"):
        _reinforce_strokes(comp, spec["reinforce_mm"])
    return comp


def _reinforce_strokes(comp: Composition, grow_mm: float) -> None:
    """Real geometric stroke strengthening for small jewellery.

    Buffers the artwork outward so every stroke gains `grow_mm` per side,
    then re-emits the SVG from the reinforced polygons. This is what makes
    the manufacturing-optimized variant genuinely manufacturable at cufflink
    scale instead of merely being labelled so.
    """
    from bsos.design_studio.validation import geometry_from_rings, rings_mm

    geom = geometry_from_rings(rings_mm(comp)).buffer(grow_mm, join_style=1)
    geom = geom.simplify(0.02)
    rings: list[list[tuple[float, float]]] = []
    for poly in getattr(geom, "geoms", [geom]):
        rings.append([(round(x, 3), round(y, 3)) for x, y in poly.exterior.coords])
        for interior in poly.interiors:
            rings.append([(round(x, 3), round(y, 3)) for x, y in interior.coords])
    comp.meta["reinforced_rings_mm"] = rings
    comp.meta["reinforced_by_mm"] = grow_mm

    face = comp.frame["face_diameter_mm"]
    cx = cy = face / 2
    path = " ".join(
        "M " + " L ".join(f"{x:.3f} {y:.3f}" for x, y in ring) + " Z"
        for ring in rings
    )
    minx = min(x for r in rings for x, _ in r)
    maxx = max(x for r in rings for x, _ in r)
    miny = min(y for r in rings for _, y in r)
    maxy = max(y for r in rings for _, y in r)
    comp.text_width_mm = maxx - minx
    comp.text_height_mm = maxy - miny
    comp.svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{face}mm" height="{face}mm" '
        f'viewBox="0 0 {face} {face}">'
        f'<circle cx="{cx}" cy="{cy}" r="{face/2 - 0.1}" fill="none" '
        f'stroke="#888" stroke-width="0.2"/>'
        f'<circle cx="{cx}" cy="{cy}" r="{comp.frame["safe_diameter_mm"]/2}" fill="none" '
        f'stroke="#bbb" stroke-width="0.1" stroke-dasharray="0.6,0.6"/>'
        f'<path d="{path}" fill="#111111" fill-rule="evenodd"/></svg>'
    )


def compose_all(inscription: str, frame: dict[str, float] | None = None) -> list[Composition]:
    from bsos.design_studio.typography import engine_for

    engines = {
        "Amiri-Regular": engine_for("Amiri-Regular"),
        "Amiri-Bold": engine_for("Amiri-Bold"),
    }
    return [compose_variant(v, inscription, frame, engines) for v in VARIANT_SPECS]
