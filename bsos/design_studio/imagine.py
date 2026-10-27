"""Imagine engine: turn a free-text wish into a concrete design brief.

A customer describes what they imagine — in Arabic, English, or both:

    "خاتم ذهب وردي باسم نورة"
    "a minimal silver pendant with the name Zahran for my father"

This module extracts a deterministic design brief from that sentence:
item type, material, finish, style leaning, and the inscription to
engrave. The inscription then flows through the SAME fail-closed
typography pipeline as a directly-typed name — imagination widens the
input, it never bypasses verification.

It also builds an English photo prompt for an OPEN-SOURCE image model
(FLUX family / Qwen-Image class). Image models cannot spell Arabic, so
the prompt explicitly forbids any text on the piece: the model paints
the jewel, the deterministic engine supplies the Arabic. The generated
photo is CONCEPT imagery only and is labelled as such wherever shown.
"""

from __future__ import annotations

import re
import unicodedata

_ARABIC_RE = re.compile(r"[؀-ۿ]")
_LATIN_RE = re.compile(r"[A-Za-z]")

# ---------------------------------------------------------------- keywords
# Keyword → canonical value. Arabic entries are matched on the tashkeel-
# stripped, alef/teh-normalized skeleton so ة/ه and أ/إ/ا variants all hit.

ITEM_WORDS = {
    # rings
    "ring": "ring", "rings": "ring", "خاتم": "ring", "محبس": "ring",
    # pendants / necklaces
    "pendant": "pendant", "necklace": "pendant", "chain": "pendant",
    "قلاده": "pendant", "سلسله": "pendant", "سلسال": "pendant",
    "تعليقه": "pendant", "عقد": "pendant",
    # cufflinks
    "cufflink": "cufflink", "cufflinks": "cufflink", "كبك": "cufflink",
    "ازرار": "cufflink",
    # bracelets
    "bracelet": "bracelet", "bangle": "bracelet",
    "سوار": "bracelet", "اسواره": "bracelet", "غويشه": "bracelet",
    # brooches
    "brooch": "brooch", "pin": "brooch", "بروش": "brooch", "دبوس": "brooch",
    # coins / medallions
    "coin": "coin", "medallion": "coin", "medal": "coin",
    "عمله": "coin", "ميداليه": "coin", "درهم": "coin",
    # corporate gifts
    "gift": "corporate_gift", "trophy": "corporate_gift", "award": "corporate_gift",
    "هديه": "corporate_gift", "درع": "corporate_gift", "تذكار": "corporate_gift",
}

MATERIAL_WORDS = {
    "silver": "silver_925", "فضه": "silver_925", "فضي": "silver_925",
    "gold": "gold_plated", "golden": "gold_plated",
    "ذهب": "gold_plated", "ذهبي": "gold_plated",
    "oxidized": "oxidized_silver", "black": "oxidized_silver",
    "اسود": "oxidized_silver", "مؤكسد": "oxidized_silver",
}
# Two-word senses checked before single words (rose gold, 18k gold).
MATERIAL_PHRASES = [
    (re.compile(r"rose\s*gold|وردي"), "rose_gold_plated"),
    (re.compile(r"18\s*k|18\s*قيراط|عيار\s*18|solid\s+gold|ذهب\s+خالص"),
     "solid_gold_18k"),
]

FINISH_WORDS = {
    "enamel": "black_enamel", "مينا": "black_enamel",
    "matte": "brushed", "brushed": "brushed", "مطفي": "brushed",
    "polished": "mirror_polish", "mirror": "mirror_polish",
    "shiny": "mirror_polish", "لامع": "mirror_polish", "مصقول": "mirror_polish",
    "white": "white_enamel", "ابيض": "white_enamel",
}

STYLE_WORDS = {
    "luxury": "luxury_diwani_jali", "ornate": "luxury_diwani_jali",
    "rich": "luxury_diwani_jali", "فخم": "luxury_diwani_jali",
    "فاخر": "luxury_diwani_jali", "ملكي": "luxury_diwani_jali",
    "minimal": "manufacturing_optimized", "simple": "manufacturing_optimized",
    "modern": "manufacturing_optimized", "بسيط": "manufacturing_optimized",
    "عصري": "manufacturing_optimized", "ناعم": "manufacturing_optimized",
    "classic": "balanced_diwani", "elegant": "balanced_diwani",
    "كلاسيكي": "balanced_diwani", "انيق": "balanced_diwani",
}

# Words that describe the wish rather than name anyone. Kept small and
# conservative: anything not recognized stays in the inscription so we
# never silently drop part of a name.
_STOPWORDS = {
    # English
    "a", "an", "the", "i", "want", "would", "like", "love", "need", "please",
    "make", "design", "create", "me", "my", "for", "with", "of", "in", "on",
    "and", "to", "that", "this", "engraved", "engraving", "name", "named",
    "word", "words", "says", "saying", "written", "text", "style", "look",
    "father", "mother", "husband", "wife", "son", "daughter", "friend",
    "him", "her", "them", "gift", "plated",
    # Arabic
    "اريد", "ابي", "ابغى", "عايز", "عاوز", "اطلب", "ممكن", "لو", "سمحت",
    "صمم", "اصنع", "سوي", "اعمل", "لي", "له", "لها", "لهم", "من", "في",
    "على", "مع", "و", "او", "هذا", "هذه", "ان", "يكون", "تكون", "شكل",
    "نقش", "منقوش", "مكتوب", "عليه", "عليها", "كلمه", "حرف",
    "اسم", "باسم", "بسم", "لابي", "لامي", "لزوجي", "لزوجتي", "لابني",
    "لبنتي", "لصديقي", "هديه", "مطلي", "عيار", "قيراط", "لون",
}

_TASHKEEL = set(range(0x064B, 0x0653)) | {0x0670}


def _skeleton(word: str) -> str:
    """Lowercased, tashkeel-stripped, alef/teh-marbuta-normalized key."""
    w = unicodedata.normalize("NFC", word.lower())
    w = "".join(c for c in w if ord(c) not in _TASHKEEL)
    return (w.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
             .replace("ة", "ه").replace("ى", "ي"))


_QUOTED = re.compile(r"[\"“”«]([^\"“”«»]+)[\"“”»]|'([^']+)'")
_NAME_MARKERS = re.compile(
    r"(?:باسم|بسم|اسم|named?|name of|called|says?|saying|reads?)\s+", re.IGNORECASE)


def parse_intent(text: str) -> dict:
    """Extract a design brief from a free-text wish. Deterministic."""
    raw = unicodedata.normalize("NFC", text or "").strip()
    lowered = raw.lower()

    material = None
    for pattern, mat in MATERIAL_PHRASES:
        if pattern.search(lowered):
            material = mat
            break

    item = None
    finish = None
    style = None
    inscription_words: list[str] = []

    # An explicitly quoted phrase, or the words after a name marker,
    # win the inscription outright.
    explicit = None
    m = _QUOTED.search(raw)
    if m:
        explicit = (m.group(1) or m.group(2)).strip()
    else:
        m = _NAME_MARKERS.search(raw)
        if m:
            tail = raw[m.end():].strip()
            # keep up to three words of the same script from the tail
            tw = tail.split()
            if tw:
                arabic_tail = _ARABIC_RE.search(tw[0]) is not None
                kept = []
                for w in tw[:3]:
                    if (_ARABIC_RE.search(w) is not None) != arabic_tail:
                        break
                    if _skeleton(re.sub(r"[^\w؀-ۿ]", "", w)) in _STOPWORDS:
                        break
                    kept.append(w)
                if kept:
                    explicit = " ".join(kept)

    for word in raw.split():
        clean = re.sub(r"[^\w؀-ۿ]", "", word)
        if not clean:
            continue
        key = _skeleton(clean)
        if key in ITEM_WORDS and item is None:
            item = ITEM_WORDS[key]
            continue
        if key in MATERIAL_WORDS and material is None:
            material = MATERIAL_WORDS[key]
            continue
        if key in FINISH_WORDS and finish is None:
            finish = FINISH_WORDS[key]
            continue
        if key in STYLE_WORDS and style is None:
            style = STYLE_WORDS[key]
            continue
        if key in _STOPWORDS or key.isdigit():
            continue
        inscription_words.append(clean)

    inscription = explicit if explicit else " ".join(inscription_words[:3])
    inscription = inscription.strip()

    has_ar = bool(_ARABIC_RE.search(raw))
    has_la = bool(_LATIN_RE.search(raw))
    return {
        "input": raw,
        "inscription": inscription,
        "item": item or "pendant",
        "item_detected": item is not None,
        "material": material or "silver_925",
        "material_detected": material is not None,
        "finish": finish or "black_enamel",
        "style_variant": style or "balanced_diwani",
        "language": "mixed" if has_ar and has_la else ("ar" if has_ar else "en"),
        "needs_inscription": not inscription,
    }


# ---------------------------------------------------------- photo prompt

_ITEM_SCENE = {
    "ring": "a heavy signet ring with a round engraved face",
    "pendant": "a round pendant medallion on a fine chain",
    "cufflink": "a pair of round cufflinks",
    "bracelet": "a bracelet with a round engraved medallion charm",
    "brooch": "a round brooch",
    "coin": "a commemorative coin medallion",
    "corporate_gift": "a desk medallion in a presentation box",
}

_MATERIAL_SCENE = {
    "silver_925": "polished sterling silver",
    "gold_plated": "polished yellow gold",
    "rose_gold_plated": "polished rose gold",
    "oxidized_silver": "dark oxidized silver",
    "solid_gold_18k": "solid 18k yellow gold",
}

_STYLE_SCENE = {
    "luxury_diwani_jali": "ornate, regal, richly detailed",
    "balanced_diwani": "elegant, refined, timeless",
    "manufacturing_optimized": "minimal, modern, clean-lined",
}


def build_photo_prompt(intent: dict) -> str:
    """English prompt for an open-source image model (FLUX / Qwen-Image
    class). The engraved face is REQUIRED to be blank: image models
    corrupt Arabic letterforms, so the verified inscription is overlaid
    from the deterministic engine, never painted by the model."""
    return (
        "Ultra-realistic professional studio photograph, luxury Emirati "
        f"jewellery: {_ITEM_SCENE.get(intent['item'], _ITEM_SCENE['pendant'])} "
        f"in {_MATERIAL_SCENE.get(intent['material'], 'polished sterling silver')}, "
        f"{_STYLE_SCENE.get(intent['style_variant'], 'elegant, refined')} design, "
        "perfectly smooth blank engraved face with no text, no letters, no "
        "script, no calligraphy, no symbols of any kind, "
        "black velvet display stand, soft warm key light, subtle gold rim "
        "light, macro lens, shallow depth of field, 8k product photography"
    )
