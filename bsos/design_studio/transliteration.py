"""Latin → Arabic name suggestions for the Design Studio intake.

Customers frequently type names in Latin letters ("Zahran", "Shaghaf").
This module proposes Arabic spellings the same way everything else in the
studio works — deterministically:

1. Curated dictionary of common Arab/Gulf names (with Latin variants) →
   high-confidence suggestions.
2. Rule-based letter mapping as a fallback → explicitly low-confidence,
   `requires_confirmation`.

A suggestion is only ever a SUGGESTION. The customer confirms the Arabic
text, and the confirmed text still goes through the structural typography
verification before anything is composed. No image model is involved.
"""

from __future__ import annotations

import re
from typing import Any

# Latin variants (lowercase) → Arabic spellings, most common first.
NAME_DICT: dict[str, list[str]] = {
    "zahran": ["زهران"],
    "mohammed": ["محمد"], "muhammad": ["محمد"], "mohamed": ["محمد"], "mohammad": ["محمد"],
    "ahmed": ["أحمد"], "ahmad": ["أحمد"],
    "ali": ["علي"],
    "omar": ["عمر"], "umar": ["عمر"],
    "khalid": ["خالد"], "khaled": ["خالد"],
    "hamdan": ["حمدان"],
    "rashid": ["راشد"], "rashed": ["راشد"],
    "zayed": ["زايد"], "zaid": ["زايد", "زيد"],
    "salem": ["سالم"], "salim": ["سالم", "سليم"],
    "saif": ["سيف"], "seif": ["سيف"],
    "sultan": ["سلطان"],
    "majid": ["ماجد"], "majed": ["ماجد"],
    "nasser": ["ناصر"], "naser": ["ناصر"],
    "khalifa": ["خليفة"],
    "hassan": ["حسن"],
    "hussein": ["حسين"], "hussain": ["حسين"],
    "ibrahim": ["إبراهيم"],
    "yousef": ["يوسف"], "yusuf": ["يوسف"], "youssef": ["يوسف"],
    "abdullah": ["عبدالله"], "abdulla": ["عبدالله"],
    "saeed": ["سعيد"], "said": ["سعيد"],
    "tariq": ["طارق"], "tarek": ["طارق"],
    "adel": ["عادل"],
    "karim": ["كريم"], "kareem": ["كريم"],
    "marwan": ["مروان"],
    "jassim": ["جاسم"], "jasem": ["جاسم"],
    "obaid": ["عبيد"],
    "faisal": ["فيصل"], "faysal": ["فيصل"],
    "mansour": ["منصور"],
    "fatima": ["فاطمة"], "fatma": ["فاطمة"],
    "maryam": ["مريم"], "mariam": ["مريم"],
    "aisha": ["عائشة"], "ayesha": ["عائشة"],
    "sara": ["سارة", "سارا"], "sarah": ["سارة"],
    "noura": ["نورة"], "nora": ["نورة", "نورا"], "noor": ["نور"], "nour": ["نور"],
    "layla": ["ليلى"], "laila": ["ليلى"], "leila": ["ليلى"],
    "salma": ["سلمى"],
    "reem": ["ريم"],
    "dana": ["دانة", "دانا"],
    "hind": ["هند"],
    "latifa": ["لطيفة"],
    "shamsa": ["شمسة"],
    "moza": ["موزة"], "mouza": ["موزة"],
    "zainab": ["زينب"], "zaynab": ["زينب"],
    "huda": ["هدى"],
    "amna": ["آمنة"],
    "meera": ["ميرا"], "mira": ["ميرا"],
    "alia": ["عالية", "علياء"], "alya": ["علياء", "عالية"],
    "shaghaf": ["شغف"],
    "farah": ["فرح"],
    "rose": ["روز"], "roz": ["روز"],
    "hessa": ["حصة"], "hassa": ["حصة"],
    "shaikha": ["شيخة"], "sheikha": ["شيخة"],
    "maha": ["مها"],
    "abeer": ["عبير"],
    "rania": ["رانيا"],
    "lina": ["لينا"],
    "hana": ["هناء", "هنا"],
    "jana": ["جنى"],
    "ghala": ["غلا"],
    "wadima": ["وديمة"],
}

# Rule-based fallback: digraphs first, then single letters. This is an
# approximation and is always flagged for confirmation.
_DIGRAPHS = [
    ("kh", "خ"), ("gh", "غ"), ("sh", "ش"), ("th", "ث"), ("dh", "ذ"),
    ("aa", "ا"), ("ee", "ي"), ("oo", "و"), ("ou", "و"), ("ai", "اي"), ("ay", "اي"),
]
_SINGLES = {
    "a": "ا", "b": "ب", "c": "ك", "d": "د", "e": "ي", "f": "ف", "g": "ج",
    "h": "ه", "i": "ي", "j": "ج", "k": "ك", "l": "ل", "m": "م", "n": "ن",
    "o": "و", "p": "ب", "q": "ق", "r": "ر", "s": "س", "t": "ت", "u": "و",
    "v": "ف", "w": "و", "x": "كس", "y": "ي", "z": "ز",
}


def _rule_based(word: str) -> str:
    w = word.lower()
    out: list[str] = []
    i = 0
    while i < len(w):
        for lat, ar in _DIGRAPHS:
            if w.startswith(lat, i):
                out.append(ar)
                i += len(lat)
                break
        else:
            out.append(_SINGLES.get(w[i], ""))
            i += 1
    # leading short vowel usually keeps its alef; drop other mapped
    # double-alefs the naive pass can produce
    return re.sub("ا+", "ا", "".join(out))


def has_latin(text: str) -> bool:
    return bool(re.search(r"[A-Za-z]", text))


def suggest(text: str, limit_per_word: int = 3) -> dict[str, Any]:
    """Suggestions for a Latin-typed inscription, word by word.

    Multi-word input (e.g. a three-name necklace "Shaghaf Farah Rose")
    returns per-word suggestions plus combined full-phrase options.
    """
    words = [w for w in re.split(r"[\s,،]+", text.strip()) if w]
    per_word: list[dict[str, Any]] = []
    for word in words:
        clean = re.sub(r"[^A-Za-z]", "", word).lower()
        if not clean:
            per_word.append({"latin": word, "suggestions": []})
            continue
        options: list[dict[str, Any]] = []
        for arabic in NAME_DICT.get(clean, [])[:limit_per_word]:
            options.append({"arabic": arabic, "source": "dictionary",
                            "confidence": "high", "requires_confirmation": False})
        if not options:
            options.append({"arabic": _rule_based(clean), "source": "rules",
                            "confidence": "low", "requires_confirmation": True})
        per_word.append({"latin": word, "suggestions": options})

    combined: list[dict[str, Any]] = []
    if words and all(w["suggestions"] for w in per_word):
        firsts = [w["suggestions"][0] for w in per_word]
        combined.append({
            "arabic": " ".join(s["arabic"] for s in firsts),
            "source": "dictionary" if all(s["source"] == "dictionary" for s in firsts) else "mixed",
            "requires_confirmation": any(s["requires_confirmation"] for s in firsts),
        })

    return {
        "input": text,
        "words": per_word,
        "combined": combined,
        "note": "Suggestions only — the customer confirms the Arabic spelling, "
                "and the confirmed text is then verified structurally by the "
                "typography engine.",
    }
