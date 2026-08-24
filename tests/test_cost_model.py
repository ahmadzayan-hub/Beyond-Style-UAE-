"""Tests for the workshop cost model.

The module was ported from beyond-style-uae-v6's lib/pricing-engine.ts, which
shipped with no tests at all. These are new. Expected values are computed by
hand from the formulas rather than captured from a run, so they would catch a
port that is self-consistently wrong.
"""

import pytest

from bsos.design_studio.cost_model import (
    SAFE_FLOOR_MARGIN,
    CostInput,
    calculate,
    clamp,
    floor_for_quote,
    money,
    troy_ounce_to_gram,
)
from bsos.design_studio.pricing import PRICING_RULES


def test_money_rounds_half_up_not_bankers():
    # Python's bare round() is banker's: round(2.675, 2) == 2.67 and
    # round(0.125, 2) == 0.12. The money boundary must not do that.
    assert money(2.675) == 2.68
    assert money(0.125) == 0.13
    assert money(1.005) == 1.01


def test_money_leaves_exact_values_alone():
    assert money(10.0) == 10.0
    assert money(0.0) == 0.0
    assert money(265.25) == 265.25


def test_clamp_bounds():
    assert clamp(-5, 0, 100) == 0
    assert clamp(150, 0, 100) == 100
    assert clamp(42, 0, 100) == 42


def test_troy_ounce_conversion():
    # 1 troy oz = 31.1034768 g. USD 2400/oz at 3.6725 AED/USD.
    assert troy_ounce_to_gram(2400, 3.6725) == money(2400 * 3.6725 / 31.1034768)
    assert troy_ounce_to_gram(2400, 3.6725) == pytest.approx(283.39, abs=0.01)


def _silver_pendant() -> CostInput:
    """A 925 silver pendant: 10g issued, 5% wastage, no scrap returned."""
    return CostInput(
        metal_rate=3.0, issued_weight=10.0, purity=92.5,
        wastage_percent=5.0, workshop_cost=60.0, materials_cost=10.0,
        target_margin=40.0, vat_percent=5.0,
    )


def test_metal_cost_follows_purity_and_wastage():
    r = calculate(_silver_pendant())
    assert r.consumed_weight == 10.0          # nothing recovered
    assert r.fine_metal_weight == 9.25        # 10g x 92.5%
    assert r.metal_cost == money(9.25 * 3.0 * 1.05)   # 29.14


def test_recovered_scrap_reduces_both_consumption_and_cost():
    base = calculate(_silver_pendant())
    with_scrap = calculate(CostInput(**{**_silver_pendant().__dict__,
                                       "recovery_percent": 20.0}))
    assert with_scrap.consumed_weight == 8.0
    assert with_scrap.recovery_value == money(10.0 * 0.20 * 3.0)
    assert with_scrap.total_cost < base.total_cost


def test_total_cost_is_never_negative():
    # Recovery larger than everything else must floor at zero, not go negative.
    r = calculate(CostInput(metal_rate=100.0, issued_weight=10.0,
                            recovery_percent=100.0))
    assert r.total_cost == 0.0


def test_target_price_hits_the_requested_margin():
    r = calculate(_silver_pendant())
    # margin is of SELLING price, not of cost
    assert r.target_price == money(r.total_cost / 0.60)
    assert r.gross_margin == pytest.approx(40.0, abs=0.1)


def test_safe_floor_is_capped_at_the_floor_margin():
    """A 60% target still floors at 25%; a 10% target floors at 10%.

    Compared to within a cent, not for exact equality: the engine divides the
    UNROUNDED cost and rounds once at the end, so re-deriving the floor from
    the already-rounded total_cost can land a cent away. That is the intended
    order — rounding early would compound through every downstream figure —
    so the test compares the value, not the rounding path.
    """
    high = calculate(CostInput(**{**_silver_pendant().__dict__,
                                  "target_margin": 60.0}))
    assert high.safe_floor == pytest.approx(
        high.total_cost / (1 - SAFE_FLOOR_MARGIN / 100), abs=0.01)
    assert high.safe_floor < high.target_price

    low = calculate(CostInput(**{**_silver_pendant().__dict__,
                                 "target_margin": 10.0}))
    assert low.safe_floor == pytest.approx(low.total_cost / 0.90, abs=0.01)
    # Below the cap the floor and the target are the same calculation.
    assert low.safe_floor == low.target_price


def test_discount_cannot_push_price_below_the_safe_floor():
    r = calculate(CostInput(**{**_silver_pendant().__dict__,
                               "target_margin": 40.0, "discount_percent": 90.0}))
    assert r.recommended_price == r.safe_floor
    assert r.recommended_price > r.total_cost


def test_vat_is_charged_on_the_recommended_price_only():
    r = calculate(_silver_pendant())
    assert r.vat == money(r.recommended_price * 0.05)
    assert r.customer_total == money(r.recommended_price + r.vat)


def test_break_even_equals_total_cost():
    r = calculate(_silver_pendant())
    assert r.break_even == r.total_cost


def test_percent_inputs_are_clamped_not_trusted():
    r = calculate(CostInput(metal_rate=3.0, issued_weight=10.0, purity=999.0,
                            wastage_percent=-50.0, recovery_percent=500.0))
    assert r.consumed_weight == 0.0      # recovery clamped to 100%
    assert r.fine_metal_weight == 0.0    # purity clamp cannot produce metal


def test_warnings_flag_unusable_input():
    r = calculate(CostInput(metal_rate=0.0, issued_weight=0.0, target_margin=5.0))
    assert "Metal rate is missing or invalid." in r.warnings
    assert "Issued metal weight is required." in r.warnings
    assert "Target margin is below the suggested floor." in r.warnings
    assert "No recoverable scrap has been entered." in r.warnings


def test_healthy_input_produces_no_warnings():
    r = calculate(CostInput(metal_rate=3.0, issued_weight=10.0,
                            recovery_percent=15.0, target_margin=40.0))
    assert r.warnings == []


# ---------------------------------------------------------------- integration

def test_flat_floor_stands_when_no_physical_inputs_are_known():
    flat = PRICING_RULES["price_floor_aed"]
    assert floor_for_quote(flat, None) == flat


def test_computed_floor_overrides_the_flat_floor_for_an_expensive_piece():
    """The reason this module exists.

    pricing.py floors every quote at a flat AED 265. A gold piece can cost
    more than that in metal alone, so the flat floor would sell it at a loss.
    """
    flat = PRICING_RULES["price_floor_aed"]
    gold = calculate(CostInput(metal_rate=283.39, issued_weight=8.0,
                               purity=75.0, workshop_cost=150.0,
                               target_margin=40.0))
    assert gold.total_cost > flat
    assert floor_for_quote(flat, gold) == gold.safe_floor
    assert floor_for_quote(flat, gold) > flat


def test_flat_floor_wins_for_a_cheap_piece():
    flat = PRICING_RULES["price_floor_aed"]
    trinket = calculate(CostInput(metal_rate=3.0, issued_weight=2.0,
                                  workshop_cost=20.0, target_margin=40.0))
    assert trinket.safe_floor < flat
    assert floor_for_quote(flat, trinket) == flat
