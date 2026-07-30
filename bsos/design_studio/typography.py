"""Deterministic Arabic/Latin typography engine.

Pipeline: Unicode NFC normalization → HarfBuzz shaping with the actual font
(OpenType GSUB/GPOS, contextual forms, RTL) → per-glyph vector outlines via
fontTools → composed SVG path with correct advances.

Verification is structural, not visual-guess: every input codepoint's
cluster must be covered, and every rendered glyph's name must map back to
the expected base letter (e.g. cluster for ز must yield a `zain-ar*` glyph,
never a substitute). If any check fails, the result is flagged
`human_review` — it can never silently pass.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import uharfbuzz as hb
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

FONTS_DIR = Path(__file__).parent / "fonts"

# Arabic letter → the glyph-name stems a faithful font may use for it.
# (Amiri and Noto follow AGL-style `<letter>-ar` naming; `uniXXXX` accepted.)
ARABIC_LETTER_GLYPH_STEMS: dict[str, tuple[str, ...]] = {
    "ا": ("alef-ar", "uni0627"),
    "ب": ("beh-ar", "uni0628"),
    "ت": ("teh-ar", "uni062A"),
    "ث": ("theh-ar", "uni062B"),
    "ج": ("jeem-ar", "uni062C"),
    "ح": ("hah-ar", "uni062D"),
    "خ": ("khah-ar", "uni062E"),
    "د": ("dal-ar", "uni062F"),
    "ذ": ("thal-ar", "uni0630"),
    "ر": ("reh-ar", "uni0631"),
    "ز": ("zain-ar", "uni0632"),
    "س": ("seen-ar", "uni0633"),
    "ش": ("sheen-ar", "uni0634"),
    "ص": ("sad-ar", "uni0635"),
    "ض": ("dad-ar", "uni0636"),
    "ط": ("tah-ar", "uni0637"),
    "ظ": ("zah-ar", "uni0638"),
    "ع": ("ain-ar", "uni0639"),
    "غ": ("ghain-ar", "uni063A"),
    "ف": ("feh-ar", "uni0641"),
    "ق": ("qaf-ar", "uni0642"),
    "ك": ("kaf-ar", "uni0643"),
    "ل": ("lam-ar", "uni0644"),
    "م": ("meem-ar", "uni0645"),
    "ن": ("noon-ar", "uni0646"),
    "ه": ("heh-ar", "uni0647"),
    "و": ("waw-ar", "uni0648"),
    "ي": ("yeh-ar", "uni064A"),
    "ة": ("tehmarbuta-ar", "uni0629"),
    "ء": ("hamza-ar", "uni0621"),
    "آ": ("alefmadda-ar", "uni0622"),
    "أ": ("alefhamzaabove-ar", "uni0623"),
    "إ": ("alefhamzabelow-ar", "uni0625"),
    "ؤ": ("wawhamzaabove-ar", "uni0624"),
    "ئ": ("yehhamzaabove-ar", "uni0626"),
    "ى": ("alefmaksura-ar", "uni0649"),
    "ـ": ("tatweel-ar", "kashida-ar", "uni0640"),
    " ": ("space",),
}

ARABIC_RANGE = set(range(0x0600, 0x0700)) | set(range(0x0750, 0x0780))


def letter_name(ch: str) -> str:
    try:
        return unicodedata.name(ch)
    except ValueError:
        return f"U+{ord(ch):04X}"


@dataclass
class ShapedGlyph:
    glyph_name: str
    cluster: int
    x_advance: float
    x_offset: float
    y_offset: float
    path_d: str  # outline in font units, y-up, positioned at pen origin


@dataclass
class ShapingResult:
    text: str
    normalized_text: str
    direction: str
    font_id: str
    upem: int
    glyphs: list[ShapedGlyph]
    total_advance: float
    verification: dict[str, Any] = field(default_factory=dict)

    @property
    def verified(self) -> bool:
        return bool(self.verification.get("passed"))


class TypographyEngine:
    def __init__(self, font_path: Path, font_id: str = ""):
        self.font_path = Path(font_path)
        self.font_id = font_id or self.font_path.stem
        blob = hb.Blob.from_file_path(str(self.font_path))
        self._face = hb.Face(blob)
        self._hbfont = hb.Font(self._face)
        self._tt = TTFont(str(self.font_path))
        self._glyph_order = self._tt.getGlyphOrder()
        self._glyph_set = self._tt.getGlyphSet()
        self.upem = self._face.upem

    # ------------------------------------------------------------------
    def normalize(self, text: str) -> str:
        # NFC canonical composition; strip zero-width controls that could
        # smuggle a different rendering than the audited sequence.
        cleaned = "".join(
            ch for ch in unicodedata.normalize("NFC", text)
            if ch not in ("​", "‎", "‏", "﻿")
        )
        return cleaned.strip()

    def letter_sequence(self, text: str) -> list[dict[str, str]]:
        return [{"char": ch, "codepoint": f"U+{ord(ch):04X}", "name": letter_name(ch)}
                for ch in text]

    # ------------------------------------------------------------------
    def shape(self, text: str) -> ShapingResult:
        normalized = self.normalize(text)
        buf = hb.Buffer()
        buf.add_str(normalized)
        buf.guess_segment_properties()
        direction = str(buf.direction)
        hb.shape(self._hbfont, buf)

        glyphs: list[ShapedGlyph] = []
        total = 0.0
        for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
            gname = self._glyph_order[info.codepoint]
            pen = SVGPathPen(self._glyph_set)
            self._glyph_set[gname].draw(pen)
            glyphs.append(ShapedGlyph(
                glyph_name=gname, cluster=info.cluster,
                x_advance=pos.x_advance, x_offset=pos.x_offset,
                y_offset=pos.y_offset, path_d=pen.getCommands(),
            ))
            total += pos.x_advance

        result = ShapingResult(
            text=text, normalized_text=normalized, direction=direction,
            font_id=self.font_id, upem=self.upem, glyphs=glyphs,
            total_advance=total,
        )
        result.verification = self._verify(result)
        return result

    # ------------------------------------------------------------------
    def _verify(self, result: ShapingResult) -> dict[str, Any]:
        """Structural spelling verification. Fail-closed."""
        text = result.normalized_text
        issues: list[str] = []
        checks: list[dict[str, Any]] = []

        is_arabic = any(ord(c) in ARABIC_RANGE for c in text)
        if is_arabic and result.direction not in ("rtl", "DirectionRTL", "4"):
            issues.append(f"expected RTL direction for Arabic text, got {result.direction}")

        # .notdef anywhere = missing glyph coverage.
        for g in result.glyphs:
            if g.glyph_name in (".notdef", "notdef"):
                issues.append(f"font lacks a glyph for cluster {g.cluster}")

        clusters_covered = {g.cluster for g in result.glyphs}
        by_cluster: dict[int, list[str]] = {}
        for g in result.glyphs:
            by_cluster.setdefault(g.cluster, []).append(g.glyph_name)

        for idx, ch in enumerate(text):
            entry: dict[str, Any] = {
                "index": idx, "char": ch, "codepoint": f"U+{ord(ch):04X}",
                "unicode_name": letter_name(ch),
            }
            if idx not in clusters_covered:
                # A cluster may merge into the previous one via a required
                # ligature (e.g. lam-alef). Accept only known ligature merges.
                prev = by_cluster.get(idx - 1, [])
                merged_lig = any("lamalef" in n.replace("_", "").lower()
                                 or "lam-alef" in n.lower() for n in prev)
                if merged_lig and ch in ("ا", "آ", "أ", "إ"):
                    entry["resolved_by"] = f"ligature {prev}"
                    entry["ok"] = True
                else:
                    entry["ok"] = False
                    issues.append(
                        f"character {idx} ({letter_name(ch)}) produced no glyph"
                    )
                checks.append(entry)
                continue

            glyph_names = by_cluster[idx]
            entry["glyphs"] = glyph_names
            stems = ARABIC_LETTER_GLYPH_STEMS.get(ch)
            if stems is None:
                # Latin/other: accept any non-notdef glyph for the cluster.
                entry["ok"] = all(n not in (".notdef",) for n in glyph_names)
            else:
                entry["ok"] = any(
                    any(n == stem or n.startswith(stem + ".") or n.startswith(stem)
                        for stem in stems)
                    for n in glyph_names
                )
                if not entry["ok"]:
                    issues.append(
                        f"character {idx} ({letter_name(ch)}) rendered as "
                        f"{glyph_names}, which does not match the expected letter"
                    )
            checks.append(entry)

        return {
            "passed": not issues,
            "status": "typography_verified" if not issues else "human_review",
            "direction_ok": not any("RTL" in i for i in issues),
            "letter_checks": checks,
            "issues": issues,
            "engine": "harfbuzz+fonttools (deterministic)",
            "font": self.font_id,
        }

    # ------------------------------------------------------------------
    def to_svg_path(self, result: ShapingResult, flip_y: bool = True) -> tuple[str, float, float]:
        """Compose positioned glyph outlines into one SVG path string.

        Returns (path_d, width, height) in font units, y-down when flip_y.
        HarfBuzz already emitted glyphs in visual order, so we place them
        left-to-right by accumulated advance — the RTL ordering is preserved
        structurally, not re-guessed.
        """
        from fontTools.misc.transform import Transform
        from fontTools.pens.recordingPen import RecordingPen

        x_cursor = 0.0
        parts: list[str] = []
        for g in result.glyphs:
            transform = Transform(1, 0, 0, -1 if flip_y else 1,
                                  x_cursor + g.x_offset,
                                  (result.upem * 0.78) - g.y_offset if flip_y else g.y_offset)
            rec = RecordingPen()
            tpen = TransformPen(rec, transform)
            self._glyph_set[g.glyph_name].draw(tpen)
            spen = SVGPathPen(self._glyph_set)
            rec.replay(spen)
            d = spen.getCommands()
            if d:
                parts.append(d)
            x_cursor += g.x_advance
        return " ".join(parts), x_cursor, result.upem


def available_fonts() -> dict[str, Path]:
    return {p.stem: p for p in sorted(FONTS_DIR.glob("*.ttf"))}


def engine_for(font_id: str) -> TypographyEngine:
    fonts = available_fonts()
    if font_id not in fonts:
        raise ValueError(f"font '{font_id}' is not in the approved local set {sorted(fonts)}")
    return TypographyEngine(fonts[font_id], font_id)
