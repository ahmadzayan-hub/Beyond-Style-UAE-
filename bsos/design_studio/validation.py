"""Manufacturing geometry validation.

Polygonizes the composed glyph outlines (quadratic curves flattened) and
runs real checks with shapely: closure, self-intersection, minimum positive
stroke (erosion test), minimum negative gap (dilation collision), edge
clearance, tiny islands, and scale sanity. The report is fail-closed: a
variant can only reach `manufacturing_checked` when `passed` is true.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from shapely.geometry import MultiPolygon, Polygon
from shapely.ops import unary_union
from shapely.validation import explain_validity

_TOKEN = re.compile(r"([MLQCTHVZmlqcthvz])|(-?\d*\.?\d+(?:e-?\d+)?)")


def _flatten_path(d: str, curve_steps: int = 8) -> list[list[tuple[float, float]]]:
    """Flatten an SVG path (M/L/Q/T/C/Z as emitted by SVGPathPen) into rings."""
    tokens = _TOKEN.findall(d)
    seq: list = [t[0] if t[0] else float(t[1]) for t in tokens]
    rings: list[list[tuple[float, float]]] = []
    ring: list[tuple[float, float]] = []
    i, cur = 0, (0.0, 0.0)
    cmd = ""
    prev_ctrl: tuple[float, float] | None = None

    def quad(x0, y0, cx_, cy_, x, y):
        for s in range(1, curve_steps + 1):
            t = s / curve_steps
            ring.append((
                (1 - t) ** 2 * x0 + 2 * (1 - t) * t * cx_ + t * t * x,
                (1 - t) ** 2 * y0 + 2 * (1 - t) * t * cy_ + t * t * y,
            ))

    while i < len(seq):
        if isinstance(seq[i], str):
            cmd = seq[i]
            i += 1
            if cmd in ("Z", "z"):
                if ring:
                    rings.append(ring)
                    ring = []
                prev_ctrl = None
                continue
        if cmd in ("M", "L"):
            cur = (seq[i], seq[i + 1])
            i += 2
            if cmd == "M" and ring:
                rings.append(ring)
                ring = []
            ring.append(cur)
            prev_ctrl = None
            if cmd == "M":
                cmd = "L"
        elif cmd == "H":
            cur = (seq[i], cur[1])
            i += 1
            ring.append(cur)
            prev_ctrl = None
        elif cmd == "V":
            cur = (cur[0], seq[i])
            i += 1
            ring.append(cur)
            prev_ctrl = None
        elif cmd == "Q":
            cx_, cy_, x, y = seq[i], seq[i + 1], seq[i + 2], seq[i + 3]
            i += 4
            quad(cur[0], cur[1], cx_, cy_, x, y)
            prev_ctrl = (cx_, cy_)
            cur = (x, y)
        elif cmd == "T":
            x, y = seq[i], seq[i + 1]
            i += 2
            if prev_ctrl is None:
                cx_, cy_ = cur
            else:
                cx_, cy_ = 2 * cur[0] - prev_ctrl[0], 2 * cur[1] - prev_ctrl[1]
            quad(cur[0], cur[1], cx_, cy_, x, y)
            prev_ctrl = (cx_, cy_)
            cur = (x, y)
        elif cmd == "C":
            c1x, c1y, c2x, c2y, x, y = (seq[i], seq[i + 1], seq[i + 2],
                                        seq[i + 3], seq[i + 4], seq[i + 5])
            i += 6
            x0, y0 = cur
            for s in range(1, curve_steps + 1):
                t = s / curve_steps
                mt = 1 - t
                ring.append((
                    mt**3 * x0 + 3 * mt**2 * t * c1x + 3 * mt * t**2 * c2x + t**3 * x,
                    mt**3 * y0 + 3 * mt**2 * t * c1y + 3 * mt * t**2 * c2y + t**3 * y,
                ))
            prev_ctrl = None
            cur = (x, y)
        else:
            i += 1
    if ring:
        rings.append(ring)
    return rings


def rings_mm(comp) -> list[list[tuple[float, float]]]:
    """The composition's rings in millimetre space (single source of truth).

    Reinforced geometry (manufacturing variants) takes precedence over the
    raw font outlines.
    """
    reinforced = comp.meta.get("reinforced_rings_mm")
    if reinforced:
        return [[(x, y) for x, y in ring] for ring in reinforced]
    face = comp.frame["face_diameter_mm"]
    placement = comp.meta.get("placement")
    if placement:
        tx, ty = placement["tx"], placement["ty"]
    else:
        tx = face / 2 - comp.text_width_mm / 2
        ty = face / 2 - comp.text_height_mm / 2
    s = comp.scale_mm_per_unit
    return [
        [(x * s + tx, y * s + ty) for x, y in ring]
        for ring in _flatten_path(comp.path_d_mm, curve_steps=10)
        if len(ring) >= 3
    ]


def geometry_from_rings(rings: list[list[tuple[float, float]]]):
    polys = []
    for ring in rings:
        poly = Polygon(ring)
        if not poly.is_valid:
            poly = poly.buffer(0)
        if not poly.is_empty:
            polys.append(poly)
    if not polys:
        return MultiPolygon([])
    polys.sort(key=lambda p: p.area, reverse=True)
    result = polys[0]
    for p in polys[1:]:
        if result.contains(p.representative_point()):
            result = result.difference(p)
        else:
            result = result.union(p)
    return result


def geometry_from_path(d: str, scale: float, translate: tuple[float, float] = (0, 0)):
    """Build a shapely geometry (mm) from a font-unit path."""
    rings = _flatten_path(d)
    polys = []
    for ring in rings:
        if len(ring) < 3:
            continue
        pts = [(x * scale + translate[0], y * scale + translate[1]) for x, y in ring]
        poly = Polygon(pts)
        if not poly.is_valid:
            poly = poly.buffer(0)
        if not poly.is_empty:
            polys.append(poly)
    if not polys:
        return MultiPolygon([])
    # even-odd composition: outer contours minus counters (holes)
    polys.sort(key=lambda p: p.area, reverse=True)
    result = polys[0]
    for p in polys[1:]:
        if result.contains(p.representative_point()):
            result = result.difference(p)
        else:
            result = result.union(p)
    return result


@dataclass
class ValidationReport:
    passed: bool
    checks: list[dict[str, Any]]
    frame: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        return {"passed": self.passed, "checks": self.checks, "frame": self.frame}


def validate_composition(comp) -> ValidationReport:
    """`comp` is a composition.Composition."""
    frame = comp.frame
    face = frame["face_diameter_mm"]
    cx = cy = face / 2

    # Recreate the mm-space geometry exactly as placed in the SVG.
    geom = geometry_from_rings(rings_mm(comp))

    checks: list[dict[str, Any]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"check": name, "ok": bool(ok), "detail": detail})

    check("geometry_present", not geom.is_empty,
          f"area {getattr(geom, 'area', 0):.2f} mm²")
    check("paths_closed_and_valid", geom.is_valid,
          explain_validity(geom) if not geom.is_valid else "all rings valid")

    # Minimum positive stroke: erosion by half min-stroke must not erase
    # a disproportionate share of the artwork.
    min_stroke = frame["min_stroke_mm"]
    eroded = geom.buffer(-min_stroke / 2)
    survival = (eroded.area / geom.area) if geom.area else 0
    check("min_stroke", survival > 0.35,
          f"erosion by {min_stroke/2:.2f} mm keeps {survival:.0%} of area "
          f"(threshold 35%)")

    # Minimum negative gap: dilate by half min-gap; count merged components.
    parts_before = len(getattr(geom, "geoms", [geom]))
    dilated = geom.buffer(frame["min_gap_mm"] / 2)
    parts_after = len(getattr(dilated, "geoms", [dilated]))
    merge_ratio = parts_after / max(parts_before, 1)
    check("min_gap", merge_ratio >= 0.5,
          f"{parts_before} components -> {parts_after} after {frame['min_gap_mm']/2:.2f} mm "
          "dilation (heavy merging indicates sub-minimum gaps)")

    # Edge clearance: artwork must stay inside safe circle minus clearance.
    from shapely.geometry import Point

    safe = Point(cx, cy).buffer(frame["safe_diameter_mm"] / 2)
    outside = geom.difference(safe)
    check("edge_clearance", outside.area < 0.01,
          f"{outside.area:.3f} mm² outside the safe diameter")

    # Tiny islands: components smaller than a manufacturable dot.
    min_island = (frame["min_stroke_mm"] ** 2) * 0.6
    islands = [g for g in getattr(geom, "geoms", [geom]) if g.area < min_island]
    check("tiny_islands", len(islands) == 0,
          f"{len(islands)} island(s) below {min_island:.2f} mm²")

    # Scale sanity.
    minx, miny, maxx, maxy = geom.bounds if not geom.is_empty else (0, 0, 0, 0)
    check("scale_and_units", 1.0 < (maxx - minx) <= face and 0.5 < (maxy - miny) <= face,
          f"artwork {maxx-minx:.1f} × {maxy-miny:.1f} mm inside {face} mm face")

    passed = all(c["ok"] for c in checks)
    return ValidationReport(passed=passed, checks=checks, frame=frame)
