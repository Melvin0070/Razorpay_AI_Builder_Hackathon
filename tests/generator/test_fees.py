"""Properties of the generator's fee encoding: every percentage goes through
``contract.apply_bp``, bands are contiguous and inclusive at the top, and the
validity windows select the schedule in force on the date asked for."""

from datetime import date, timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st

from leakproof.contract import CATEGORY_NODES, apply_bp
from leakproof.generator import fees

AUG_2026 = date(2026, 8, 21)
principals = st.integers(min_value=0, max_value=5_000_000)
dates = st.dates(min_value=date(2026, 3, 16), max_value=date(2027, 12, 31))


def test_every_pinned_category_has_tiers():
    assert set(fees.REFERRAL_TIERS) == set(CATEGORY_NODES)
    assert set(fees.LEGACY_REFERRAL_TIERS) == set(CATEGORY_NODES)
    for tiers in (*fees.REFERRAL_TIERS.values(), *fees.LEGACY_REFERRAL_TIERS.values()):
        uppers = [u for u, _ in tiers[:-1]]
        assert tiers[-1][0] is None, "last band must be open"
        assert uppers == sorted(uppers) and len(set(uppers)) == len(uppers)


@given(st.sampled_from(fees.COVERED_CATEGORIES), principals, dates)
def test_commission_is_apply_bp_of_the_tier(category, principal, on):
    bp = fees.referral_bp(category, principal, on)
    assert fees.commission_paise(category, principal, on) == apply_bp(principal, bp)
    assert 0 <= bp <= 10_000


def test_tiers_are_inclusive_at_the_upper_bound():
    assert fees.referral_bp("apparel", 100_000, AUG_2026) == 0
    assert fees.referral_bp("apparel", 100_001, AUG_2026) == 2_100
    assert fees.referral_bp("electronics-accessories", 30_000, AUG_2026) == 0
    assert fees.referral_bp("electronics-accessories", 30_001, AUG_2026) == 500
    assert fees.referral_bp("electronics-accessories", 100_001, AUG_2026) == 1_700
    assert fees.referral_bp("home-kitchen", 100_000, AUG_2026) == 0
    assert fees.referral_bp("home-kitchen", 100_001, AUG_2026) == 1_250


def test_no_schedule_before_the_march_change():
    with pytest.raises(ValueError):
        fees.referral_bp("apparel", 50_000, date(2026, 3, 15))
    with pytest.raises(ValueError):
        fees.closing_fee_paise(50_000, date(2026, 3, 15))


@given(principals)
def test_closing_bands_are_contiguous_and_the_september_change_adds_the_stated_rupees(principal):
    before = fees.closing_fee_paise(principal, date(2026, 9, 6))
    after = fees.closing_fee_paise(principal, date(2026, 9, 7))
    assert after - before == (100 if principal <= 50_000 else 300)
    assert before in {100, 2_200, 4_500, 7_600}


def test_closing_bands_inclusive_at_boundaries():
    assert fees.closing_fee_paise(30_000, AUG_2026) == 100
    assert fees.closing_fee_paise(30_001, AUG_2026) == 2_200
    assert fees.closing_fee_paise(50_000, AUG_2026) == 2_200
    assert fees.closing_fee_paise(100_000, AUG_2026) == 4_500
    assert fees.closing_fee_paise(100_001, AUG_2026) == 7_600


@given(principals)
def test_tcs_legs_sum_to_half_a_percent_within_a_paise(principal):
    intra = sum(v for _, v in fees.tcs_legs(principal, intra_state=True, on=AUG_2026))
    inter = sum(v for _, v in fees.tcs_legs(principal, intra_state=False, on=AUG_2026))
    assert inter == apply_bp(principal, 50)
    assert abs(intra - inter) <= 1
    assert fees.tds_paise(principal, AUG_2026) == apply_bp(principal, 10)


def test_statutory_windows():
    day_before = fees.TCS_VALID_FROM - timedelta(days=1)
    assert fees.tcs_legs(100_000, intra_state=False, on=day_before) == (("TCS-IGST", 1_000),)
    assert fees.tcs_legs(100_000, intra_state=False, on=fees.TCS_VALID_FROM) == (("TCS-IGST", 500),)
    assert fees.tds_paise(100_000, fees.TDS_VALID_FROM - timedelta(days=1)) == 1_000
    assert fees.tds_paise(100_000, fees.TDS_VALID_FROM) == 100
    assert fees.legacy_tds_paise(100_000) == 1_000


def test_schedule_label_names_the_window_in_force():
    assert "2026-03-16..2026-09-06" in fees.schedule_label(AUG_2026)
    assert "2026-09-07..open" in fees.schedule_label(date(2026, 9, 7))
