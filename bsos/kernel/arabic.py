"""Deterministic text checks ported from the Agentic OS Arabic validator.

Joining resets at word boundaries; hamza alone joins neither neighbour.
This describes logical text, not an optical proof of an arbitrary image.
HarfBuzz and the studio's glyph checks remain responsible for vector shaping.
"""

import re
import unicodedata

ARABIC = re.compile(r"[\u0600-\u06ff\u0750-\u077f\u08a0-\u08ff\ufb50-\ufdff\ufe70-\ufeff]")
DIACRITICS = re.compile(r"[\u064b-\u065f\u0670]")
HAMZA = set("ءأؤإئآ")
DOTTED = set("بتثجخذزشضظغفقنةيئؤ")
RIGHT_ONLY = set("اأإآدذرزوؤةى")
# Directional overrides/isolates and invisible joining controls cannot be
# silently removed from approved Arabic.
CONTROLS = set("\u200b\u200c\u200d\u200e\u200f\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069\ufeff")


def contains_arabic(text: str) -> bool:
    return bool(ARABIC.search(text))


def strip_diacritics(text: str) -> str:
    return DIACRITICS.sub("", text)


def _letter(ch: str) -> bool:
    return contains_arabic(ch) and unicodedata.category(ch).startswith("L")


def compute_connectivity(text: str) -> list[dict]:
    result = []
    # Marks are transparent; punctuation/spaces terminate joining runs.
    runs = re.findall(r"[^\W\d_]+", strip_diacritics(text), re.UNICODE)
    for run in runs:
        letters = list(run)
        for i, ch in enumerate(letters):
            if not _letter(ch):
                continue
            prev = letters[i - 1] if i else ""
            nxt = letters[i + 1] if i + 1 < len(letters) else ""
            result.append({
                "char": ch,
                "joins_previous": bool(_letter(prev) and prev not in RIGHT_ONLY | {"ء"} and ch != "ء"),
                "joins_next": bool(_letter(nxt) and ch not in RIGHT_ONLY | {"ء"} and nxt != "ء"),
            })
    return result


def validate_arabic_text(text: str) -> dict:
    text = text.strip()
    issues = []
    if not text:
        issues.append("empty input")
    letters = [ch for ch in text if _letter(ch)]
    if not letters:
        issues.append("no Arabic letters present")
    if re.search(r"[A-Za-z]", text):
        issues.append("mixed Latin characters inside Arabic text")
    if any(ch in CONTROLS for ch in text):
        issues.append("direction/joining control present")
    return {
        "input": text, "valid": not issues, "is_rtl": bool(letters) and not re.search(r"[A-Za-z]", text),
        "letter_count": len(letters), "dot_bearing_letters": sum(ch in DOTTED for ch in letters),
        "has_diacritics": bool(DIACRITICS.search(text)), "has_hamza": any(ch in HAMZA for ch in text),
        "words": text.split(), "connectivity": compute_connectivity(text), "issues": issues,
    }


def compare_exact_text(approved: str, derived: str) -> list[str]:
    # NFC-equivalent Unicode spellings have the same letters/marks. No
    # compatibility folding, hamza substitution, or harakat stripping here.
    a, d = (unicodedata.normalize("NFC", t.strip()) for t in (approved, derived))
    if a == d:
        return []
    issues = []
    if strip_diacritics(a) != strip_diacritics(d):
        issues.append("letter sequence altered")
    if DIACRITICS.search(a) and a != d:
        issues.append("diacritics altered or dropped")
    if [c for c in a if c in HAMZA] != [c for c in d if c in HAMZA]:
        issues.append("hamza altered")
    if sum(c in DOTTED for c in a) != sum(c in DOTTED for c in d):
        issues.append("dot-bearing letters changed")
    if a.split() != d.split():
        issues.append("word order/spelling changed")
    return issues or ["text differs from approved spelling"]
