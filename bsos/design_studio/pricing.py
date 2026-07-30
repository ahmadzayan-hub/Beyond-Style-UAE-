"""Design Studio pricing engine.

Configurable rules → deterministic AED estimate with a full breakdown.
Every price is a STARTING price, confirmed with the customer on WhatsApp —
the same commercial policy as the rest of BSOS. Rules are data, not code,
so the workshop can retune them without redeploying; the same rules JSON is
served to the UI so the showroom screen can show live prices instantly and
the server can still record the authoritative quote.
"""

from __future__ import annotations

from typing import Any

# All AED. Starting prices only.
PRICING_RULES: dict[str, Any] = {
    "currency": "AED",
    "price_floor_aed": 265,
    "policy_note_en": "Starting price. Final price is confirmed with the customer on WhatsApp.",
    "policy_note_ar": "سعر ابتدائي. يُؤكد السعر النهائي مع العميل عبر واتساب.",
    "base_by_item": {
        "cufflink": 295,        # pair
        "pendant": 265,
        "bracelet": 285,
        "ring": 275,
        "brooch": 295,
        "coin": 320,
        "corporate_gift": 350,
    },
    "material_multiplier": {
        "silver_925": {"label_en": "925 Silver", "label_ar": "فضة ٩٢٥", "factor": 1.0},
        "gold_plated": {"label_en": "Gold plated", "label_ar": "مطلي ذهب", "factor": 1.18},
        "rose_gold_plated": {"label_en": "Rose gold plated", "label_ar": "مطلي ذهب وردي", "factor": 1.18},
        "oxidized_silver": {"label_en": "Oxidized silver", "label_ar": "فضة مؤكسدة", "factor": 1.08},
        "solid_gold_18k": {"label_en": "18k Gold", "label_ar": "ذهب ١٨ قيراط", "factor": None,
                           "quote_on_request": True},
    },
    "finish_adder": {
        "mirror_polish": {"label_en": "Mirror polish", "label_ar": "تلميع مرآة", "aed": 0},
        "brushed": {"label_en": "Brushed", "label_ar": "مصقول ناعم", "aed": 15},
        "black_enamel": {"label_en": "Black enamel", "label_ar": "مينا سوداء", "aed": 45},
        "white_enamel": {"label_en": "White enamel", "label_ar": "مينا بيضاء", "aed": 45},
    },
    # Calligraphic complexity by variant: richer composition = more finishing work.
    "variant_factor": {
        "luxury_diwani_jali": 1.25,
        "balanced_diwani": 1.10,
        "manufacturing_optimized": 1.0,
    },
    "per_letter_after": {"letters_included": 4, "aed_per_letter": 12},
    "quantity_tiers": [
        {"min_qty": 10, "factor": 0.85},
        {"min_qty": 5, "factor": 0.90},
        {"min_qty": 2, "factor": 0.95},
        {"min_qty": 1, "factor": 1.0},
    ],
}


def estimate(item_type: str, variant_id: str, letter_count: int,
             material: str = "silver_925", finish: str = "mirror_polish",
             quantity: int = 1, rules: dict[str, Any] | None = None) -> dict[str, Any]:
    """Deterministic starting-price estimate with an itemised breakdown."""
    r = rules or PRICING_RULES
    breakdown: list[dict[str, Any]] = []

    base = r["base_by_item"].get(item_type)
    if base is None:
        raise ValueError(f"no base price configured for item '{item_type}'")
    breakdown.append({"label": f"base:{item_type}", "aed": base})

    mat = r["material_multiplier"].get(material)
    if mat is None:
        raise ValueError(f"unknown material '{material}'")
    if mat.get("quote_on_request") or mat["factor"] is None:
        return {
            "currency": r["currency"], "quote_on_request": True,
            "material": material,
            "note": "Solid precious metal is priced per current market rates on WhatsApp.",
        }

    fin = r["finish_adder"].get(finish)
    if fin is None:
        raise ValueError(f"unknown finish '{finish}'")

    vfac = r["variant_factor"].get(variant_id, 1.0)
    extra_letters = max(0, letter_count - r["per_letter_after"]["letters_included"])
    letters_aed = extra_letters * r["per_letter_after"]["aed_per_letter"]

    unit = base * mat["factor"] * vfac + fin["aed"] + letters_aed
    breakdown.append({"label": f"material:{material}", "factor": mat["factor"]})
    breakdown.append({"label": f"variant:{variant_id}", "factor": vfac})
    breakdown.append({"label": f"finish:{finish}", "aed": fin["aed"]})
    if letters_aed:
        breakdown.append({"label": f"extra_letters:{extra_letters}", "aed": letters_aed})

    qty = max(1, int(quantity))
    qfac = next(t["factor"] for t in sorted(r["quantity_tiers"],
                                            key=lambda t: -t["min_qty"])
                if qty >= t["min_qty"])
    if qfac != 1.0:
        breakdown.append({"label": f"quantity:{qty}", "factor": qfac})

    unit = max(unit * qfac, r["price_floor_aed"])
    unit = round(unit / 5) * 5  # clean showroom numbers

    return {
        "currency": r["currency"],
        "quote_on_request": False,
        "unit_price_aed": unit,
        "quantity": qty,
        "total_aed": unit * qty,
        "is_starting_price": True,
        "note_en": r["policy_note_en"],
        "note_ar": r["policy_note_ar"],
        "breakdown": breakdown,
    }
