"""The contract is shared vocabulary; these tests pin its arithmetic and its tables."""

import pytest

from leakproof import contract as c


@pytest.mark.parametrize(
    ("paise", "bp", "expected"),
    [
        (100_000, 1_200, 12_000),  # 12% of ₹1,000
        (33_333, 1_200, 4_000),  # 3999.96 rounds up
        (33_329, 1_200, 3_999),  # 3999.48 rounds down
        (1, 5_000, 1),  # exactly half rounds away from zero
        (-1, 5_000, -1),
        (-33_333, 1_200, -4_000),  # symmetric for negatives
        (0, 1_200, 0),
        (12_500, 0, 0),
    ],
)
def test_apply_bp_rounds_half_away_from_zero(paise, bp, expected):
    assert c.apply_bp(paise, bp) == expected


def test_compare_paise_tolerance_is_inclusive():
    assert c.compare_paise(1_000, 1_100) == 0
    assert c.compare_paise(1_000, 1_101) == -1
    assert c.compare_paise(1_101, 1_000) == 1
    assert c.paise_within(5, -95)
    assert not c.paise_within(5, -96)


def test_materiality_floor_is_ten_rupees_inclusive():
    assert not c.is_material(999)
    assert c.is_material(1_000)
    assert c.is_material(-1_000)


def test_line_id_round_trip_and_validation():
    lid = c.make_line_id("settlement_2026-08-21.txt", 1204)
    assert lid == "settlement_2026-08-21.txt:1204"
    assert c.parse_line_id(lid) == ("settlement_2026-08-21.txt", 1204)
    with pytest.raises(ValueError):
        c.make_line_id("a.txt", 0)
    with pytest.raises(ValueError):
        c.make_line_id("a:b.txt", 1)
    for bad in ("a.txt", "a.txt:", ":3", "a.txt:x", "a.txt:0"):
        with pytest.raises(ValueError):
            c.parse_line_id(bad)


def test_class_table_is_complete_and_consistent():
    assert set(c.ALLOWED_MECHANISMS) == set(c.ErrorClass)
    assert set(c.PRIMARY_MECHANISM) == set(c.ErrorClass)
    assert set(c.CLASS_BUCKET) == set(c.ErrorClass)
    for cls in c.ErrorClass:
        assert c.PRIMARY_MECHANISM[cls] in c.ALLOWED_MECHANISMS[cls]
    assert c.ALLOWED_MECHANISMS[c.ErrorClass.UNEXPLAINED_DEDUCTION] == {c.Mechanism.NONE}
    assert c.ALLOWED_MECHANISMS[c.ErrorClass.TAX_MISMATCH] == {c.Mechanism.CA_REVIEW}
    assert {c.Mechanism.SAFE_T} == c.MECHANISMS_WITH_WINDOW


def test_state_order_lists_each_state_once():
    assert sorted(c.STATE_ORDER, key=str) == sorted(c.State, key=str)
    assert len(c.STATE_ORDER) == len(set(c.STATE_ORDER))


@pytest.mark.parametrize(
    ("cls", "state", "line"),
    [
        (c.ErrorClass.COMMISSION_OVERCHARGE, c.State.CLAIM_READY, c.RupeeLine.CLAIM_READY),
        (c.ErrorClass.FIXED_FEE_ERROR, c.State.BLOCKED, c.RupeeLine.BLOCKED),
        (c.ErrorClass.REFUND_NO_FEE_REVERSAL, c.State.NOT_CLAIMABLE, c.RupeeLine.NOT_CLAIMABLE),
        (c.ErrorClass.UNPAID_PAST_CYCLE, c.State.CLAIM_READY, c.RupeeLine.CLAIM_READY),
        (c.ErrorClass.TAX_MISMATCH, c.State.BLOCKED, c.RupeeLine.TAX_REVIEW),
        (c.ErrorClass.TAX_MISMATCH, c.State.NOT_CLAIMABLE, c.RupeeLine.TAX_REVIEW),
        (c.ErrorClass.UNEXPLAINED_DEDUCTION, c.State.UNEXPLAINED, c.RupeeLine.UNEXPLAINED),
    ],
)
def test_rupee_line_is_a_function_of_bucket_and_state(cls, state, line):
    assert c.rupee_line_for(cls, state) is line


def test_rupee_line_rejects_combinations_the_ladder_cannot_produce():
    with pytest.raises(ValueError):
        c.rupee_line_for(c.ErrorClass.UNEXPLAINED_DEDUCTION, c.State.CLAIM_READY)
    with pytest.raises(ValueError):
        c.rupee_line_for(c.ErrorClass.COMMISSION_OVERCHARGE, c.State.UNEXPLAINED)


def test_line_vocabulary_maps_known_codes_and_never_drops_unknown_ones():
    assert c.classify_line("ItemFees", "Commission") is c.LineKind.COMMISSION
    assert c.classify_line("ItemWithheldTax", "TCS-IGST") is c.LineKind.TCS
    assert c.classify_line("Promotion", "Shipping") is c.LineKind.PROMOTION
    assert c.classify_line("other-transaction", "MISC-ADJ-7") is c.LineKind.UNCLASSIFIED
    assert c.classify_transaction("A-to-z Guarantee Refund") is c.TransactionType.ATOZ_REFUND
    assert c.classify_transaction("Something New") is c.TransactionType.OTHER
