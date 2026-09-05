"""Slab completeness per declared category (D17).

A gap or an overlap in a slab set is the exact defect the CONFIG_ERROR
disposition exists to surface, so it is asserted here directly on the corpus as
well as through the gate.
"""

from itertools import pairwise

import pytest

from leakproof.contract import LineKind

SLABBED_KINDS = (LineKind.COMMISSION, LineKind.FIXED_CLOSING_FEE)


def _windows(card, kind, category_id):
    """Every distinct validity window the corpus declares for one cell."""
    seen = {
        (r.valid_from, r.valid_to)
        for r in card.rules
        if r.kind is kind and r.category_id == category_id
    }
    return sorted(seen, key=lambda w: w[0])


def _bands(card, kind, category_id, window):
    return sorted(
        (
            r
            for r in card.rules
            if r.kind is kind
            and r.category_id == category_id
            and (r.valid_from, r.valid_to) == window
        ),
        key=lambda r: r.slab_min_paise if r.slab_min_paise is not None else -1,
    )


@pytest.mark.parametrize("kind", SLABBED_KINDS)
def test_every_declared_category_has_slabs_in_every_window(card, kind):
    for category_id in card.coverage().categories:
        windows = _windows(card, kind, category_id)
        assert windows, f"{category_id} has no {kind.value} rule at all"
        for window in windows:
            assert _bands(card, kind, category_id, window)


@pytest.mark.parametrize("kind", SLABBED_KINDS)
def test_slabs_have_no_gaps_and_no_overlaps_across_the_full_principal_range(card, kind):
    for category_id in card.coverage().categories:
        for window in _windows(card, kind, category_id):
            bands = _bands(card, kind, category_id, window)
            where = f"{category_id} {kind.value} {window[0]}..{window[1]}"
            assert bands[0].slab_min_paise is None, f"{where}: lowest band is not open below"
            assert bands[-1].slab_max_paise is None, f"{where}: highest band is not open above"
            for lower, upper in pairwise(bands):
                assert lower.slab_max_paise is not None, f"{where}: unbounded band in the middle"
                assert upper.slab_min_paise == lower.slab_max_paise + 1, (
                    f"{where}: {lower.rule_id} ends at {lower.slab_max_paise} and "
                    f"{upper.rule_id} starts at {upper.slab_min_paise}"
                )


def test_every_declared_category_has_a_commission_rule_in_force_at_the_coverage_floor(card):
    floor = card.coverage().valid_from
    for category_id in card.coverage().categories:
        in_force = card.rules_for(LineKind.COMMISSION, category_id, floor)
        assert in_force, category_id
        assert all(r.category_id == category_id for r in in_force)


def test_closing_fee_windows_meet_without_a_day_of_daylight(card):
    """The 7 September 2026 change is two windows, not an edit to one."""
    for category_id in card.coverage().categories:
        windows = _windows(card, LineKind.FIXED_CLOSING_FEE, category_id)
        assert len(windows) >= 2, category_id
        for (_, earlier_end), (later_start, _) in pairwise(windows):
            assert earlier_end is not None
            assert (later_start - earlier_end).days == 1, category_id
