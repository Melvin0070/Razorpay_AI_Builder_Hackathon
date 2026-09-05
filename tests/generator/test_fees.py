"""Properties of the generator's fee encoding: every percentage goes through
``contract.apply_bp``, fees are charged per unit at the band the unit key
selects, bands are contiguous and inclusive at the top, and the validity
windows select the schedule in force on the date asked for."""

from datetime import date, timedelta
from itertools import pairwise

import pytest
from hypothesis import given
from hypothesis import strategies as st

from leakproof.contract import CATEGORY_NODES, apply_bp
from leakproof.generator import fees

AUG_2026 = date(2026, 8, 21)
prices = st.integers(min_value=0, max_value=5_000_000)
quantities = st.integers(min_value=1, max_value=12)
dates = st.dates(min_value=date(2026, 3, 16), max_value=date(2027, 12, 31))
covered = st.sampled_from(fees.COVERED_CATEGORIES)


def test_every_pinned_category_has_tiers_and_a_closing_group():
    assert set(fees.REFERRAL_TIERS) == set(CATEGORY_NODES)
    assert set(fees.LEGACY_REFERRAL_TIERS) == set(CATEGORY_NODES)
    assert set(fees.CLOSING_GROUP) == set(CATEGORY_NODES)
    for tiers in (*fees.REFERRAL_TIERS.values(), *fees.LEGACY_REFERRAL_TIERS.values()):
        uppers = [u for u, _ in tiers[:-1]]
        assert tiers[-1][0] is None, "last band must be open"
        assert uppers == sorted(uppers) and len(set(uppers)) == len(uppers)


@given(covered, prices, quantities, dates)
def test_commission_is_quantity_times_apply_bp_of_the_unit_tier(category, unit_price, qty, on):
    bp = fees.referral_bp(category, unit_price, on)
    assert 0 <= bp <= 10_000
    assert fees.commission_paise(category, unit_price, qty, on) == qty * apply_bp(unit_price, bp)


@given(covered, prices, dates)
def test_the_band_is_keyed_on_the_unit_price_not_the_order_principal(category, unit_price, on):
    # 3 x ₹400 apparel must sit in the 0% band, never in the 21% tier a ₹1,200
    # principal would pick (the integrator's item-price decision): the fee for
    # three units is three times the one-unit fee, whatever band the total hits.
    assert fees.commission_paise(category, unit_price, 3, on) == 3 * fees.commission_paise(
        category, unit_price, 1, on
    )


def test_three_by_four_hundred_apparel_carries_no_commission():
    assert fees.commission_paise("apparel", 40_000, 3, AUG_2026) == 0
    assert fees.referral_bp("apparel", 120_000, AUG_2026) == 2_100


def test_referral_tiers_are_inclusive_at_the_upper_bound():
    assert fees.referral_bp("apparel", 100_000, AUG_2026) == 0
    assert fees.referral_bp("apparel", 100_001, AUG_2026) == 2_100
    assert fees.referral_bp("electronics-accessories", 30_000, AUG_2026) == 0
    assert fees.referral_bp("electronics-accessories", 30_001, AUG_2026) == 500
    assert fees.referral_bp("electronics-accessories", 100_000, AUG_2026) == 500
    assert fees.referral_bp("electronics-accessories", 100_001, AUG_2026) == 1_700
    assert fees.referral_bp("home-kitchen", 100_000, AUG_2026) == 0
    assert fees.referral_bp("home-kitchen", 100_001, AUG_2026) == 1_250


def test_legacy_tiers_are_the_pre_march_column():
    assert fees.legacy_referral_bp("apparel", 30_000) == 0
    assert fees.legacy_referral_bp("apparel", 40_000) == 450
    assert fees.legacy_referral_bp("apparel", 80_000) == 1_200
    assert fees.legacy_referral_bp("apparel", 200_000) == 2_100
    assert fees.legacy_referral_bp("electronics-accessories", 40_000) == 1_700
    assert fees.legacy_referral_bp("electronics-accessories", 80_000) == 1_550
    assert fees.legacy_referral_bp("home-kitchen", 40_000) == 500
    assert fees.legacy_referral_bp("home-kitchen", 80_000) == 900


def test_no_schedule_before_the_march_change():
    with pytest.raises(ValueError):
        fees.referral_bp("apparel", 50_000, date(2026, 3, 15))
    with pytest.raises(ValueError):
        fees.closing_fee_paise("apparel", 50_000, 1, date(2026, 3, 15))


def test_unknown_categories_are_rejected_and_uncovered_ones_are_flat():
    with pytest.raises(ValueError):
        fees.referral_bp("furniture", 50_000, AUG_2026)
    with pytest.raises(ValueError):
        fees.closing_group("furniture")
    assert fees.referral_bp("books", 50_000, AUG_2026) == fees.UNCOVERED_REFERRAL_BP
    assert fees.closing_group("books") == fees.STANDARD_GROUP
    assert fees.is_known_category("books") and not fees.is_known_category("furniture")


@given(
    prices, st.integers(min_value=0, max_value=20_000), st.integers(min_value=0, max_value=6_000)
)
def test_closing_key_is_the_per_unit_item_price_including_shipping_and_gift_wrap(
    unit_price, shipping_per_unit, wrap_per_unit
):
    for qty in (1, 2, 3):
        key = fees.closing_key(unit_price * qty, shipping_per_unit * qty, wrap_per_unit * qty, qty)
        assert key == unit_price + shipping_per_unit + wrap_per_unit


def test_closing_key_refuses_a_total_that_is_not_whole_per_unit():
    with pytest.raises(ValueError):
        fees.per_unit(100_001, 2)
    with pytest.raises(ValueError):
        fees.per_unit(100, 0)


@given(covered, prices, quantities)
def test_closing_fee_is_quantity_times_the_band_fee_and_september_adds_the_stated_rupees(
    category, key, qty
):
    before = fees.closing_fee_paise(category, key, qty, date(2026, 9, 6))
    after = fees.closing_fee_paise(category, key, qty, date(2026, 9, 7))
    unit_before = fees.closing_fee_per_unit(category, key, date(2026, 9, 6))
    assert before == qty * unit_before
    assert after - before == qty * (100 if key <= 50_000 else 300)
    group = fees.closing_group(category)
    expected = {
        fees.STANDARD_GROUP: {2_600, 2_200, 2_700, 5_200},
        fees.SELECT_GROUP: {2_000, 1_800, 2_700, 5_200},
    }[group]
    assert unit_before in expected


def test_closing_bands_inclusive_at_boundaries_for_both_groups():
    std, sel = "apparel", "electronics-accessories"
    assert fees.closing_group(std) == fees.STANDARD_GROUP
    assert fees.closing_group("home-kitchen") == fees.STANDARD_GROUP
    assert fees.closing_group(sel) == fees.SELECT_GROUP
    assert fees.closing_fee_per_unit(std, 30_000, AUG_2026) == 2_600
    assert fees.closing_fee_per_unit(std, 30_001, AUG_2026) == 2_200
    assert fees.closing_fee_per_unit(std, 50_000, AUG_2026) == 2_200
    assert fees.closing_fee_per_unit(std, 50_001, AUG_2026) == 2_700
    assert fees.closing_fee_per_unit(std, 100_000, AUG_2026) == 2_700
    assert fees.closing_fee_per_unit(std, 100_001, AUG_2026) == 5_200
    assert fees.closing_fee_per_unit(sel, 30_000, AUG_2026) == 2_000
    assert fees.closing_fee_per_unit(sel, 30_001, AUG_2026) == 1_800
    assert fees.closing_fee_per_unit(sel, 50_000, AUG_2026) == 1_800
    assert fees.closing_fee_per_unit(sel, 50_001, AUG_2026) == 2_700
    assert fees.closing_fee_per_unit(sel, 100_001, AUG_2026) == 5_200
    assert fees.closing_band(0) == 0 and fees.closing_band(100_001) == 3


def test_closing_schedules_are_contiguous_and_the_last_is_open():
    schedules = fees.CLOSING_SCHEDULES
    for earlier, later in pairwise(schedules):
        assert earlier.valid_to is not None
        assert later.valid_from == earlier.valid_to + timedelta(days=1)
    assert schedules[-1].valid_to is None


@given(prices)
def test_tcs_legs_sum_to_half_a_percent_within_a_paise(principal):
    intra = sum(v for _, v in fees.tcs_legs(principal, intra_state=True, on=AUG_2026))
    inter = sum(v for _, v in fees.tcs_legs(principal, intra_state=False, on=AUG_2026))
    assert inter == apply_bp(principal, 50)
    assert abs(intra - inter) <= 1
    assert fees.tds_paise(principal, AUG_2026) == apply_bp(principal, 10)
    assert fees.fee_gst_paise(principal) == apply_bp(principal, 1_800)


def test_statutory_windows():
    day_before = fees.TCS_VALID_FROM - timedelta(days=1)
    assert fees.tcs_legs(100_000, intra_state=False, on=day_before) == (("TCS-IGST", 1_000),)
    assert fees.tcs_legs(100_000, intra_state=False, on=fees.TCS_VALID_FROM) == (("TCS-IGST", 500),)
    assert fees.tcs_legs(100_000, intra_state=True, on=fees.TCS_VALID_FROM) == (
        ("TCS-CGST", 250),
        ("TCS-SGST", 250),
    )
    assert fees.legacy_tcs_legs(100_000, intra_state=False) == (("TCS-IGST", 1_000),)
    assert fees.tds_paise(100_000, fees.TDS_VALID_FROM - timedelta(days=1)) == 1_000
    assert fees.tds_paise(100_000, fees.TDS_VALID_FROM) == 100
    assert fees.legacy_tds_paise(100_000) == 1_000


def test_schedule_label_names_the_window_and_the_basis():
    label = fees.schedule_label(AUG_2026)
    assert "2026-03-16..2026-09-06" in label
    assert "Fulfilment Centre" in label
    assert "unit item price" in label and "shipping + gift wrap" in label
    assert "2026-09-07..open" in fees.schedule_label(date(2026, 9, 7))
