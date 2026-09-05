"""D12: the 26-case adversarial holdout. These tests check the fixtures are
well-formed and self-consistent; the pipeline is scored against them by lane N,
as its own published line."""

from __future__ import annotations

import pytest

from leakproof import contract as c
from leakproof.labels import load_holdout
from leakproof.labels.holdout.cases import (
    ASSUMED_COMMISSION_BP,
    SETTLEMENT_CYCLE_END,
    cycle_bounds,
)

CASES = load_holdout()


def test_exactly_twenty_six_cases():
    assert len(CASES) == 26


def test_case_ids_are_unique_and_stable():
    ids = [case.case_id for case in CASES]
    assert len(set(ids)) == len(ids)
    assert ids == sorted(ids), "case ids are numbered, so their order is their identity"


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.case_id)
def test_every_fold_carries_an_as_of(case):
    assert case.folded.as_of is not None


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.case_id)
def test_every_line_id_parses(case):
    for line in case.folded.lines:
        source_file, row = c.parse_line_id(line.line_id)
        assert source_file and row >= 1


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.case_id)
def test_line_ids_are_unique_within_a_fold(case):
    ids = [line.line_id for line in case.folded.lines]
    assert len(set(ids)) == len(ids)


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.case_id)
def test_lines_belong_to_the_folded_order_and_a_declared_settlement(case):
    for line in case.folded.lines:
        assert line.order_id == case.folded.order_id
        assert line.settlement_id in case.folded.settlement_ids


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.case_id)
def test_settlement_ids_are_cycle_ordered_oldest_first(case):
    # FoldedOrder documents settlement_ids as cycle order, oldest first (D20).
    ends = [SETTLEMENT_CYCLE_END[sid] for sid in case.folded.settlement_ids]
    assert ends == sorted(ends)
    assert len(set(case.folded.settlement_ids)) == len(case.folded.settlement_ids)


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.case_id)
def test_every_line_is_posted_inside_the_cycle_it_claims(case):
    for line in case.folded.lines:
        start, end = cycle_bounds(line.settlement_id)
        assert start <= line.posted_date <= end, line.line_id


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.case_id)
def test_commission_is_the_assumed_rate_unless_class_1_is_declared(case):
    # Gap 4: the 13%/19% split is a rate-card assumption expressed in
    # arithmetic. What the holdout may assert is the relation, and only against
    # its own single named constant, never against lane C's corpus (D12).
    order = case.folded.order
    charged = -sum(
        ln.amount_paise
        for ln in case.folded.lines
        if ln.kind is c.LineKind.COMMISSION
        and ln.txn_type is c.TransactionType.ORDER
        and ln.amount_paise < 0
    )
    if order is None or charged == 0:
        return
    assumed = c.apply_bp(order.principal_paise, ASSUMED_COMMISSION_BP)
    declares_class_1 = case.expected_class is c.ErrorClass.COMMISSION_OVERCHARGE or (
        "detector 1" in case.expected_reason.lower()
    )
    if declares_class_1:
        assert charged > assumed, case.case_id
    else:
        assert charged == assumed, case.case_id


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.case_id)
def test_class_and_state_are_declared_together(case):
    assert (case.expected_class is None) == (case.expected_state is None)


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.case_id)
def test_expected_class_and_state_land_in_a_real_rupee_line(case):
    if case.expected_class is None:
        return
    c.rupee_line_for(case.expected_class, case.expected_state)


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.case_id)
def test_every_case_states_its_reason(case):
    assert len(case.expected_reason.split()) >= 15
    assert case.description.strip()


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.case_id)
def test_amounts_are_integer_paise(case):
    if case.expected_amount_paise is None:
        return
    assert isinstance(case.expected_amount_paise, int)
    assert not isinstance(case.expected_amount_paise, bool)
    assert case.expected_amount_paise > 0, "a discrepancy is carried positive"


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.case_id)
def test_a_queued_amount_is_material_and_an_unqueued_one_is_not(case):
    if case.expected_amount_paise is None:
        return
    if case.expected_class is None:
        assert not c.is_material(case.expected_amount_paise)
    else:
        assert c.is_material(case.expected_amount_paise)


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.case_id)
def test_finding_amount_never_exceeds_the_orders_deductions(case):
    # The D19 per-order sum invariant, per bucket (ADR-0005.5). Class 6 has no
    # lines to bound it, so it is bounded by the order's own value instead.
    if case.expected_amount_paise is None or case.expected_class is None:
        return
    if case.expected_class is c.ErrorClass.UNPAID_PAST_CYCLE:
        order = case.folded.order
        assert order is not None
        bound = order.principal_paise + order.tax_paise
    else:
        bound = case.folded.deductions_paise
    assert case.expected_amount_paise <= bound


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.case_id)
def test_line_kinds_agree_with_the_shared_vocabulary(case):
    for line in case.folded.lines:
        assert c.classify_line(line.amount_type, line.amount_description) is line.kind
        assert c.classify_transaction(line.transaction_type_raw) is line.txn_type


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.case_id)
def test_an_order_row_matches_the_fold_it_belongs_to(case):
    order = case.folded.order
    if order is None:
        return
    assert order.order_id == case.folded.order_id
    assert order.category_id in c.CATEGORY_NODES
    c.parse_line_id(order.source_line_id)


def test_the_holdout_covers_the_shapes_the_brief_names():
    by_id = {case.case_id: case for case in CASES}

    tolerances = [
        by_id["H01-tolerance-under-by-one-rupee"],
        by_id["H02-tolerance-over-by-one-rupee"],
    ]
    assert all(case.expected_class is None for case in tolerances)

    floor = by_id["H03-discrepancy-exactly-at-the-floor"]
    assert floor.expected_amount_paise == c.MATERIALITY_FLOOR_PAISE

    below = by_id["H21-one-paisa-below-the-floor"]
    assert below.expected_amount_paise == c.MATERIALITY_FLOOR_PAISE - 1

    split = by_id["H04-reversal-split-across-two-lines"]
    reversals = [
        ln for ln in split.folded.lines if ln.kind is c.LineKind.COMMISSION and ln.amount_paise > 0
    ]
    assert len(reversals) == 2

    late = by_id["H05-cycle-3-reversal-cancels-cycle-1-finding"]
    assert late.folded.settlement_ids[0] != late.folded.settlement_ids[-1]

    orphan = by_id["H07-order-absent-from-the-seller-export"]
    assert orphan.folded.order is None

    lapsed = by_id["H08-capability-lapsed-before-the-event"]
    event = min(ln.posted_date for ln in lapsed.folded.lines)
    assert lapsed.profile.capability("gst_registration", on=event) is False
    assert (
        lapsed.profile.capability("gst_registration", on=lapsed.folded.as_of.replace(year=2025))
        is True
    )

    pending = by_id["H09-registered-but-invoice-not-yet-supplied"]
    assert pending.expected_state is c.State.BLOCKED

    on_as_of = by_id["H10-window-expires-on-as-of-itself"]
    refund = min(
        ln.posted_date for ln in on_as_of.folded.lines if ln.txn_type is c.TransactionType.REFUND
    )
    assert (on_as_of.folded.as_of - refund).days == 15

    leap = by_id["H11-window-lands-on-a-leap-day"]
    assert (leap.folded.as_of.month, leap.folded.as_of.day) == (2, 29)

    month_end = by_id["H12-window-from-a-month-end-refund"]
    month_end_refund = min(
        ln.posted_date for ln in month_end.folded.lines if ln.txn_type is c.TransactionType.REFUND
    )
    assert month_end_refund.day == 31
    assert (month_end.folded.as_of - month_end_refund).days == 16

    tcs = by_id["H13-tcs-reversed-on-a-refund"]
    assert sum(ln.amount_paise for ln in tcs.folded.lines if ln.kind is c.LineKind.TCS) == 0

    reimbursed = by_id["H14-safe-t-reimbursement-already-received"]
    assert any(ln.kind is c.LineKind.SAFET_REIMBURSEMENT for ln in reimbursed.folded.lines)

    duplicate = by_id["H15-two-identical-commission-lines"]
    commissions = [ln for ln in duplicate.folded.lines if ln.kind is c.LineKind.COMMISSION]
    assert len(commissions) == 2
    assert commissions[0].amount_paise == commissions[1].amount_paise
    assert commissions[0].line_id != commissions[1].line_id

    zero = by_id["H16-zero-amount-line"]
    assert any(ln.amount_paise == 0 for ln in zero.folded.lines)

    known = by_id["H17-known-code-with-no-rule"]
    assert known.expected_class is c.ErrorClass.UNEXPLAINED_DEDUCTION
    unseen = by_id["H18-unseen-code"]
    assert c.classify_line("ItemFees", "SellerRewardsAdjustment") is c.LineKind.UNCLASSIFIED
    assert unseen.expected_class is c.ErrorClass.UNEXPLAINED_DEDUCTION

    atoz = by_id["H19-a-to-z-refund-without-fee-reversal"]
    assert any(ln.txn_type is c.TransactionType.ATOZ_REFUND for ln in atoz.folded.lines)
    assert atoz.expected_state is c.State.NOT_CLAIMABLE

    seller = by_id["H20-seller-issued-refund-without-fee-reversal"]
    assert seller.folded.order.refund_initiated_by is c.RefundInitiator.SELLER
    assert seller.expected_state is c.State.NOT_CLAIMABLE

    out_of_window = by_id["H22-delivery-outside-the-declared-coverage"]
    assert out_of_window.folded.in_coverage is False


REFUND_TXNS = (
    c.TransactionType.REFUND,
    c.TransactionType.CHARGEBACK_REFUND,
    c.TransactionType.ATOZ_REFUND,
)


def _cycles_from_as_of(case) -> set[int]:
    """Days between each refund-side line and the batch's as_of, in days."""
    return {
        (case.folded.as_of - ln.posted_date).days
        for ln in case.folded.lines
        if ln.txn_type in REFUND_TXNS
    }


def test_exactly_one_case_sits_on_the_one_cycle_boundary():
    # Gap 9: H03 and H25 used to sit exactly DEFAULT_CYCLE_DAYS before as_of
    # while existing to pin the materiality floor and chargeback eligibility,
    # so an off-by-one in the fold would have surfaced as a broken floor. The
    # boundary now belongs to one case that says so.
    on_boundary = [
        case.case_id for case in CASES if c.DEFAULT_CYCLE_DAYS in _cycles_from_as_of(case)
    ]
    assert on_boundary == ["H26-refund-exactly-one-cycle-before-the-batch-max"]

    boundary = next(case for case in CASES if case.case_id.startswith("H26"))
    assert "boundary" in boundary.description.lower()
    assert boundary.expected_class is c.ErrorClass.REFUND_NO_FEE_REVERSAL
    assert boundary.expected_state is c.State.CLAIM_READY


def test_co_firing_case_declares_no_single_class():
    co_fire = next(case for case in CASES if case.case_id.startswith("H06"))
    assert co_fire.expected_class is None
    reason = co_fire.expected_reason.lower()
    assert "detector 1" in reason and "detector 5" in reason
