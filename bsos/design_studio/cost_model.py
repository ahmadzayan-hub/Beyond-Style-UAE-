"""Workshop cost model — what a piece costs to make, and the floor below which
selling it loses money.

This answers a different question from `pricing.py`, and the two are meant to
be used together:

    pricing.py   what do we QUOTE the customer for this design?
                 base by item x material x variant, + finish, + letters,
                 x quantity tier, floored at a flat AED 265.

    cost_model   what does this piece actually COST us, given the metal that
                 went into it? Issued weight, purity, wastage, scrap recovered,
                 workshop and materials, payment fees, overhead, risk — then
                 break-even, a per-piece safe floor, target price and VAT.

`pricing.py`'s floor is a single flat number. That cannot be right for a 925
silver pendant and an 18k gold coin at the same time: the flat floor is either
far above the silver piece's true cost or far below the gold one's. This module
computes the floor per piece from the metal actually consumed, so
`floor_for_quote()` can raise the flat floor when the physical inputs are known
and leave it alone when they are not.

Ported from the `beyond-style-uae-v6` prototype's `lib/pricing-engine.ts`,
which was the only place this calculation existed and had no tests. The
arithmetic is preserved exactly, including its rounding at money boundaries and
its clamping of percentage inputs; the tests here are new.
"""

from __future__ import annotations

from dataclasses import dataclass, field

TROY_OUNCE_GRAMS = 31.1034768


def money(n: float) -> float:
    """Round to 2dp at a money boundary, half-up on the positive side.

    Python's round() is banker's rounding, so round(2.675, 2) is 2.67. The
    epsilon nudge matches the TypeScript original and keeps 2.675 -> 2.68.
    """
    return round(n + 1e-9, 2)


def clamp(n: float, lo: float, hi: float) -> float:
    return min(hi, max(lo, n))


@dataclass(frozen=True)
class CostInput:
    metal_rate: float             # AED per gram of fine metal
    issued_weight: float          # grams handed to the workshop
    purity: float = 92.5          # percent fine
    wastage_percent: float = 0.0
    recovery_percent: float = 0.0  # percent of issued metal returned as scrap
    workshop_cost: float = 0.0
    materials_cost: float = 0.0
    packaging_cost: float = 0.0
    delivery_cost: float = 0.0
    payment_percent: float = 0.0   # card/gateway fee on direct cost
    overhead_cost: float = 0.0
    risk_percent: float = 0.0
    target_margin: float = 0.0     # percent of selling price
    discount_percent: float = 0.0
    vat_percent: float = 0.0


@dataclass(frozen=True)
class CostResult:
    fine_metal_weight: float
    consumed_weight: float
    metal_cost: float
    recovery_value: float
    manufacturing_cost: float
    variable_cost: float
    risk_allowance: float
    total_cost: float
    break_even: float
    safe_floor: float
    target_price: float
    recommended_price: float
    premium_price: float
    discount_value: float
    gross_profit: float
    gross_margin: float
    markup: float
    vat: float
    customer_total: float
    warnings: list[str] = field(default_factory=list)


#: Margin the safe floor is held at, whatever target margin is asked for.
SAFE_FLOOR_MARGIN = 25.0


def calculate(inp: CostInput) -> CostResult:
    issued = max(0.0, inp.issued_weight)
    recovery_pct = clamp(inp.recovery_percent, 0, 100)

    recovery_value = issued * recovery_pct / 100 * inp.metal_rate
    consumed_weight = max(0.0, issued - issued * recovery_pct / 100)
    fine_metal_weight = consumed_weight * clamp(inp.purity, 0, 100) / 100
    metal_cost = (fine_metal_weight * inp.metal_rate
                  * (1 + clamp(inp.wastage_percent, 0, 100) / 100))

    manufacturing_cost = max(0.0, inp.workshop_cost) + max(0.0, inp.materials_cost)
    variable_cost = (max(0.0, inp.packaging_cost) + max(0.0, inp.delivery_cost)
                     + (manufacturing_cost + metal_cost)
                     * max(0.0, inp.payment_percent) / 100)

    subtotal = metal_cost + manufacturing_cost + variable_cost + max(0.0, inp.overhead_cost)
    risk_allowance = subtotal * clamp(inp.risk_percent, 0, 100) / 100
    total_cost = max(0.0, subtotal + risk_allowance - recovery_value)

    target_margin = clamp(inp.target_margin, 0, 99)
    target_price = total_cost / max(0.01, 1 - target_margin / 100)
    # The floor never rides above the asked-for margin: a 10% target gives a
    # 10% floor, a 60% target still gives a 25% floor.
    safe_floor = total_cost / max(0.01, 1 - min(target_margin, SAFE_FLOOR_MARGIN) / 100)

    discount_value = target_price * clamp(inp.discount_percent, 0, 100) / 100
    recommended_price = max(safe_floor, target_price - discount_value)
    vat = recommended_price * max(0.0, inp.vat_percent) / 100
    gross_profit = recommended_price - total_cost

    warnings: list[str] = []
    if inp.metal_rate <= 0:
        warnings.append("Metal rate is missing or invalid.")
    if inp.issued_weight <= 0:
        warnings.append("Issued metal weight is required.")
    if inp.target_margin < SAFE_FLOOR_MARGIN:
        warnings.append("Target margin is below the suggested floor.")
    if inp.recovery_percent <= 0:
        warnings.append("No recoverable scrap has been entered.")

    return CostResult(
        fine_metal_weight=money(fine_metal_weight),
        consumed_weight=money(consumed_weight),
        metal_cost=money(metal_cost),
        recovery_value=money(recovery_value),
        manufacturing_cost=money(manufacturing_cost),
        variable_cost=money(variable_cost),
        risk_allowance=money(risk_allowance),
        total_cost=money(total_cost),
        break_even=money(total_cost),
        safe_floor=money(safe_floor),
        target_price=money(target_price),
        recommended_price=money(recommended_price),
        premium_price=money(target_price * 1.1),
        discount_value=money(discount_value),
        gross_profit=money(gross_profit),
        gross_margin=money(gross_profit / max(1.0, recommended_price) * 100),
        markup=money(gross_profit / max(1.0, total_cost) * 100),
        vat=money(vat),
        customer_total=money(recommended_price + vat),
        warnings=warnings,
    )


def troy_ounce_to_gram(usd_per_ounce: float, usd_to_aed: float) -> float:
    """Spot quote (USD/troy oz) to the AED-per-gram rate this module wants."""
    return money(usd_per_ounce * usd_to_aed / TROY_OUNCE_GRAMS)


def floor_for_quote(flat_floor_aed: float, cost: CostResult | None) -> float:
    """The floor a quote must respect.

    Without physical inputs there is nothing better than the configured flat
    floor. With them, the computed per-piece floor wins whenever it is higher —
    a quote must never fall below what the metal in the piece actually cost.
    """
    if cost is None:
        return flat_floor_aed
    return max(flat_floor_aed, cost.safe_floor)
