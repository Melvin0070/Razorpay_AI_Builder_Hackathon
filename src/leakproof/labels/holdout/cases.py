"""The 26-case adversarial holdout (D12). Lane F, hand-authored, frozen with
the labels.

Cases the generator never produces. Each one is a canonical ``FoldedOrder``
plus the ``SellerProfile`` in force, and each names the outcome the pipeline
must reach. Scored and published as its own line, never merged into headline
recall or precision.

Reading the expectations:

* ``expected_class`` is ``None`` when no single class is the answer. That
  covers three shapes: nothing should fire at all (a true negative), the case
  is a disposition rather than a finding, and two classes must co-fire. Which
  one it is, is in ``expected_reason``.
* ``expected_state`` is ``None`` whenever ``expected_class`` is, since a state
  belongs to a finding.
* ``expected_amount_paise`` is ``None`` when the amount is a rate-card
  recomputation. This package must never encode a fee rate (D12), so those
  cases score class, state and reason, and the ₹-agreement metric takes its
  evidence from the seeded batches instead.

Dates are explicit and every ``as_of`` is set on the fold, because half of
these cases exist to catch off-by-one deadline arithmetic (D18).
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Final

from leakproof.contract import (
    DEFAULT_CYCLE_DAYS,
    MATERIALITY_FLOOR_PAISE,
    TOLERANCE_PAISE,
    ErrorClass,
    LineKind,
    Paise,
    RefundInitiator,
    State,
    TransactionType,
    apply_bp,
    make_line_id,
)
from leakproof.types import (
    CapabilityFact,
    FoldedOrder,
    HoldoutCase,
    Order,
    SellerProfile,
    SettlementLine,
)

# --------------------------------------------------------------------------- #
# Fixture vocabulary
# --------------------------------------------------------------------------- #

ORDERS_FILE: Final[str] = "orders_2026-q3.csv"
C1_FILE: Final[str] = "settlement_2026-07-07.txt"
C2_FILE: Final[str] = "settlement_2026-07-14.txt"
C3_FILE: Final[str] = "settlement_2026-07-21.txt"

C1_ID: Final[str] = "IN-SET-C1"
C2_ID: Final[str] = "IN-SET-C2"
C3_ID: Final[str] = "IN-SET-C3"

C1_DATE: Final[date] = date(2026, 7, 7)
C2_DATE: Final[date] = date(2026, 7, 14)
C3_DATE: Final[date] = date(2026, 7, 21)

#: A date inside cycle 2 but off its last day. H03 and H25 used to post their
#: refunds on C2_DATE, exactly ``DEFAULT_CYCLE_DAYS`` before the batch's max
#: settlement date; that is the D20 one-cycle boundary, which H26 exists to
#: pin. A case that pins the materiality floor or chargeback eligibility must
#: not sit on it too, or an off-by-one in the fold reads as a broken floor.
C2_MID_DATE: Final[date] = date(2026, 7, 10)

#: Last day of each settlement cycle in this module. A cycle is
#: ``contract.DEFAULT_CYCLE_DAYS`` long and ends on the settlement's own date,
#: so a line's posted date has to fall inside the cycle whose id it carries.
SETTLEMENT_CYCLE_END: Final[dict[str, date]] = {
    C1_ID: C1_DATE,
    C2_ID: C2_DATE,
    C3_ID: C3_DATE,
    "IN-SET-2028-02-16": date(2028, 2, 16),
    "IN-SET-2026-02-03": date(2026, 2, 3),
}

#: The commission rate every fee line in this module is computed from.
#:
#: It is an **assumption about lane C's corpus, not a figure read from it**:
#: this package must never encode a rate card (D12), and it never opens
#: ``ratecard/`` or ``generator/``. What the holdout actually asserts is a
#: relation — a case that declares no class-1 finding is charged exactly this
#: rate, and a case that declares one is charged strictly above it. Naming the
#: assumption once means the whole module moves together if lane C's audited
#: rate for the pinned category turns out to differ, instead of nine cases
#: silently disagreeing with each other. It is applied regardless of the
#: order's category on purpose, so that no category-level rate structure is
#: encoded here either.
ASSUMED_COMMISSION_BP: Final[int] = 1_300

#: How far above the assumed rate an over-charged case is charged. Only the
#: sign is load-bearing: these cases exist to test that "above" is noticed, not
#: that any particular wrong rate is.
OVERCHARGE_MARGIN_BP: Final[int] = 600

OVERCHARGED_COMMISSION_BP: Final[int] = ASSUMED_COMMISSION_BP + OVERCHARGE_MARGIN_BP


def cycle_bounds(settlement_id: str) -> tuple[date, date]:
    """First and last day, both inclusive, of the cycle ``settlement_id`` covers."""
    end = SETTLEMENT_CYCLE_END[settlement_id]
    return end - timedelta(days=DEFAULT_CYCLE_DAYS - 1), end


def _commission(principal_paise: Paise, *, bp: int = ASSUMED_COMMISSION_BP) -> Paise:
    """The signed amount of a commission line: negative, because it is a fee."""
    return -apply_bp(principal_paise, bp)


def _rupees(paise: Paise) -> str:
    """A ₹ figure for prose, formatted from the same integer the case carries.

    The reason strings used to state their rupee figures as literals, so the
    rate unification left H04 claiming a ₹200 shortfall the case no longer
    contained and every test stayed green. Deriving the words from the paise
    means a move in ``ASSUMED_COMMISSION_BP`` or in the materiality floor
    rewrites the prose along with the numbers instead of leaving it behind.
    """
    whole, part = divmod(abs(paise), 100)
    return f"₹{whole}" if part == 0 else f"₹{whole}.{part:02d}"


#: H04's commission reversal, split unevenly across two lines in one cycle. The
#: split is derived from the charge rather than pinned in paise so that both
#: halves stay positive under any rate, and so that the shortfall a one-to-one
#: matcher wrongly sees against either line is exactly the other line's amount.
H04_CHARGE_PAISE: Final[Paise] = -_commission(400_000)
H04_REVERSAL_A_PAISE: Final[Paise] = H04_CHARGE_PAISE * 3 // 5
H04_REVERSAL_B_PAISE: Final[Paise] = H04_CHARGE_PAISE - H04_REVERSAL_A_PAISE

#: H21's principal, picked so that the commission on it lands exactly one paisa
#: under the materiality floor.
#:
#: H21 is the one case in this module that cannot survive a move in
#: ``ASSUMED_COMMISSION_BP``: at 1_400 bp the same principal yields ₹10.76,
#: which is material, and the case turns from a below-materiality true negative
#: into a live class-5 finding while still declaring ``expected_class=None``.
#: The expectation is therefore derived from the same arithmetic the settlement
#: line carries rather than pinned at the floor, so a rate move fails the
#: holdout's own materiality tests loudly instead of passing green.
H21_PRINCIPAL_PAISE: Final[Paise] = 7_685
H21_UNREVERSED_PAISE: Final[Paise] = -_commission(H21_PRINCIPAL_PAISE)


#: The seller in force for most cases: GST-registered without end date.
REGISTERED: Final[SellerProfile] = SellerProfile(
    seller_id="A1SELLERIN0001",
    display_name="Holdout Traders",
    capabilities=(CapabilityFact("gst_registration", True, valid_from=date(2024, 4, 1)),),
)

#: Never declared a capability at all. Lane K must read this as "permanence
#: unknown" and degrade to step 5, never as False (design doc, step 4).
UNDECLARED: Final[SellerProfile] = SellerProfile(
    seller_id="A1SELLERIN0002",
    display_name="Holdout Traders (no profile facts)",
)

#: Registration that lapsed on 2026-06-30 and is declared absent from 2026-07-01.
#: The Amazon-native shape of premise P2's Flipkart SPF/VMS case.
LAPSED_GST: Final[SellerProfile] = SellerProfile(
    seller_id="A1SELLERIN0003",
    display_name="Holdout Traders (registration surrendered)",
    capabilities=(
        CapabilityFact(
            "gst_registration", True, valid_from=date(2024, 4, 1), valid_to=date(2026, 6, 30)
        ),
        CapabilityFact("gst_registration", False, valid_from=date(2026, 7, 1)),
    ),
)


def _order(
    order_id: str,
    row: int,
    *,
    principal_paise: Paise,
    tax_paise: Paise,
    category_id: str = "electronics-accessories",
    sku: str = "SKU-HOLDOUT",
    quantity: int = 1,
    order_date: date = date(2026, 6, 28),
    delivery_date: date | None = date(2026, 7, 2),
    refund_initiated_by: RefundInitiator = RefundInitiator.NONE,
) -> Order:
    return Order(
        order_id=order_id,
        sku=sku,
        category_id=category_id,
        quantity=quantity,
        principal_paise=principal_paise,
        tax_paise=tax_paise,
        order_date=order_date,
        delivery_date=delivery_date,
        refund_initiated_by=refund_initiated_by,
        source_line_id=make_line_id(ORDERS_FILE, row),
    )


def _line(
    source_file: str,
    row: int,
    settlement_id: str,
    txn: TransactionType,
    kind: LineKind,
    amount_type: str,
    amount_description: str,
    amount_paise: Paise,
    posted: date,
    order_id: str,
    *,
    sku: str | None = "SKU-HOLDOUT",
    quantity: int | None = 1,
    adjustment_id: str | None = None,
) -> SettlementLine:
    return SettlementLine(
        line_id=make_line_id(source_file, row),
        settlement_id=settlement_id,
        txn_type=txn,
        kind=kind,
        amount_type=amount_type,
        amount_description=amount_description,
        amount_paise=amount_paise,
        posted_date=posted,
        order_id=order_id,
        sku=sku,
        quantity=quantity,
        adjustment_id=adjustment_id,
        transaction_type_raw=txn.value,
    )


def _fold(
    order_id: str,
    order: Order | None,
    lines: tuple[SettlementLine, ...],
    settlement_ids: tuple[str, ...],
    as_of: date,
    *,
    in_coverage: bool = True,
) -> FoldedOrder:
    return FoldedOrder(
        order_id=order_id,
        order=order,
        lines=lines,
        settlement_ids=settlement_ids,
        in_coverage=in_coverage,
        as_of=as_of,
    )


# --------------------------------------------------------------------------- #
# 01-02 — the ±₹1 comparison tolerance, both sides (D3)
# --------------------------------------------------------------------------- #

H01 = HoldoutCase(
    case_id="H01-tolerance-under-by-one-rupee",
    description=(
        f"Refund whose commission reversal is exactly {_rupees(TOLERANCE_PAISE)} smaller "
        "than the commission originally charged."
    ),
    folded=_fold(
        "403-1000001-0000001",
        _order("403-1000001-0000001", 2, principal_paise=250_000, tax_paise=45_000),
        (
            _line(
                C1_FILE,
                11,
                C1_ID,
                TransactionType.ORDER,
                LineKind.PRINCIPAL,
                "ItemPrice",
                "Principal",
                250_000,
                C1_DATE,
                "403-1000001-0000001",
            ),
            _line(
                C1_FILE,
                12,
                C1_ID,
                TransactionType.ORDER,
                LineKind.COMMISSION,
                "ItemFees",
                "Commission",
                _commission(250_000),
                C1_DATE,
                "403-1000001-0000001",
            ),
            _line(
                C2_FILE,
                21,
                C2_ID,
                TransactionType.REFUND,
                LineKind.PRINCIPAL,
                "ItemPrice",
                "Principal",
                -250_000,
                C2_MID_DATE,
                "403-1000001-0000001",
            ),
            _line(
                C2_FILE,
                22,
                C2_ID,
                TransactionType.REFUND,
                LineKind.COMMISSION,
                "ItemFees",
                "Commission",
                -_commission(250_000) - TOLERANCE_PAISE,
                C2_MID_DATE,
                "403-1000001-0000001",
            ),
        ),
        (C1_ID, C2_ID),
        C3_DATE,
    ),
    profile=REGISTERED,
    expected_class=None,
    expected_state=None,
    expected_reason=(
        f"The reversal is short by exactly {TOLERANCE_PAISE} paise, which compare_paise "
        f"reports as equal at the ±{_rupees(TOLERANCE_PAISE)} tolerance. Nothing fires; the shortfall is not even below-materiality, "
        "because no discrepancy was found."
    ),
    expected_amount_paise=None,
)

H02 = HoldoutCase(
    case_id="H02-tolerance-over-by-one-rupee",
    description=(
        f"The mirror of H01: the commission reversal is exactly {_rupees(TOLERANCE_PAISE)} "
        "larger than the commission charged, so the tolerance is exercised on the other "
        "side of zero."
    ),
    folded=_fold(
        "403-1000002-0000002",
        _order("403-1000002-0000002", 3, principal_paise=250_000, tax_paise=45_000),
        (
            _line(
                C1_FILE,
                31,
                C1_ID,
                TransactionType.ORDER,
                LineKind.PRINCIPAL,
                "ItemPrice",
                "Principal",
                250_000,
                C1_DATE,
                "403-1000002-0000002",
            ),
            _line(
                C1_FILE,
                32,
                C1_ID,
                TransactionType.ORDER,
                LineKind.COMMISSION,
                "ItemFees",
                "Commission",
                _commission(250_000),
                C1_DATE,
                "403-1000002-0000002",
            ),
            _line(
                C2_FILE,
                41,
                C2_ID,
                TransactionType.REFUND,
                LineKind.PRINCIPAL,
                "ItemPrice",
                "Principal",
                -250_000,
                C2_MID_DATE,
                "403-1000002-0000002",
            ),
            _line(
                C2_FILE,
                42,
                C2_ID,
                TransactionType.REFUND,
                LineKind.COMMISSION,
                "ItemFees",
                "Commission",
                -_commission(250_000) + TOLERANCE_PAISE,
                C2_MID_DATE,
                "403-1000002-0000002",
            ),
        ),
        (C1_ID, C2_ID),
        C3_DATE,
    ),
    profile=REGISTERED,
    expected_class=None,
    expected_state=None,
    expected_reason=(
        "An over-reversal of exactly 100 paise is inside the same tolerance. A detector "
        "that only guards the under side fires here and must not."
    ),
    expected_amount_paise=None,
)

# --------------------------------------------------------------------------- #
# 03 — the materiality floor, exactly on it (D3)
# --------------------------------------------------------------------------- #

H03 = HoldoutCase(
    case_id="H03-discrepancy-exactly-at-the-floor",
    description=(
        f"Partially reversed commission leaving a shortfall of exactly "
        f"{_rupees(MATERIALITY_FLOOR_PAISE)}, the materiality floor."
    ),
    folded=_fold(
        "403-1000003-0000003",
        _order("403-1000003-0000003", 4, principal_paise=200_000, tax_paise=36_000),
        (
            _line(
                C1_FILE,
                51,
                C1_ID,
                TransactionType.ORDER,
                LineKind.PRINCIPAL,
                "ItemPrice",
                "Principal",
                200_000,
                C1_DATE,
                "403-1000003-0000003",
            ),
            _line(
                C1_FILE,
                52,
                C1_ID,
                TransactionType.ORDER,
                LineKind.COMMISSION,
                "ItemFees",
                "Commission",
                _commission(200_000),
                C1_DATE,
                "403-1000003-0000003",
            ),
            _line(
                C2_FILE,
                61,
                C2_ID,
                TransactionType.REFUND,
                LineKind.PRINCIPAL,
                "ItemPrice",
                "Principal",
                -200_000,
                C2_MID_DATE,
                "403-1000003-0000003",
            ),
            _line(
                C2_FILE,
                62,
                C2_ID,
                TransactionType.REFUND,
                LineKind.COMMISSION,
                "ItemFees",
                "Commission",
                -_commission(200_000) - MATERIALITY_FLOOR_PAISE,
                C2_MID_DATE,
                "403-1000003-0000003",
            ),
        ),
        (C1_ID, C2_ID),
        C3_DATE,
    ),
    profile=REGISTERED,
    expected_class=ErrorClass.REFUND_NO_FEE_REVERSAL,
    expected_state=State.CLAIM_READY,
    expected_reason=(
        f"is_material is at-or-above the floor, so {_rupees(MATERIALITY_FLOOR_PAISE)} "
        "exactly is queued and lands in ₹ identified. An implementation using a strict greater-than pushes it into "
        "below-materiality and quietly shrinks the headline number. The refund is posted "
        "on 2026-07-10, eleven days before the batch's max settlement date, so this case "
        "sits well clear of the D20 one-cycle boundary that H26 owns: an off-by-one in "
        "the fold must not be able to surface here as a broken materiality floor."
    ),
    expected_amount_paise=MATERIALITY_FLOOR_PAISE,
)

# --------------------------------------------------------------------------- #
# 04-05 — cross-cycle composition (D20)
# --------------------------------------------------------------------------- #

H04 = HoldoutCase(
    case_id="H04-reversal-split-across-two-lines",
    description=(
        "The commission reversal arrives as two lines in the same cycle that together "
        "equal the charge."
    ),
    folded=_fold(
        "403-1000004-0000004",
        _order("403-1000004-0000004", 5, principal_paise=400_000, tax_paise=72_000),
        (
            _line(
                C1_FILE,
                71,
                C1_ID,
                TransactionType.ORDER,
                LineKind.PRINCIPAL,
                "ItemPrice",
                "Principal",
                400_000,
                C1_DATE,
                "403-1000004-0000004",
            ),
            _line(
                C1_FILE,
                72,
                C1_ID,
                TransactionType.ORDER,
                LineKind.COMMISSION,
                "ItemFees",
                "Commission",
                _commission(400_000),
                C1_DATE,
                "403-1000004-0000004",
            ),
            _line(
                C2_FILE,
                81,
                C2_ID,
                TransactionType.REFUND,
                LineKind.PRINCIPAL,
                "ItemPrice",
                "Principal",
                -400_000,
                C2_MID_DATE,
                "403-1000004-0000004",
            ),
            _line(
                C2_FILE,
                82,
                C2_ID,
                TransactionType.REFUND,
                LineKind.COMMISSION,
                "ItemFees",
                "Commission",
                H04_REVERSAL_A_PAISE,
                C2_MID_DATE,
                "403-1000004-0000004",
            ),
            _line(
                C2_FILE,
                83,
                C2_ID,
                TransactionType.REFUND,
                LineKind.COMMISSION,
                "ItemFees",
                "Commission",
                H04_REVERSAL_B_PAISE,
                C2_MID_DATE,
                "403-1000004-0000004",
            ),
        ),
        (C1_ID, C2_ID),
        C3_DATE,
    ),
    profile=REGISTERED,
    expected_class=None,
    expected_state=None,
    expected_reason=(
        "Reversal completeness is a sum over every reversal line on the order, not a "
        "one-to-one line match. The two lines together equal the "
        f"{_rupees(H04_CHARGE_PAISE)} charged, but matching the charge against either "
        f"alone sees a shortfall that does not exist: {_rupees(H04_REVERSAL_B_PAISE)} "
        f"against the larger line, {_rupees(H04_REVERSAL_A_PAISE)} against the smaller. "
        "The two reversal lines also share a settlement id and a posted date, so the "
        "fold's deterministic tiebreak orders them and must not change the outcome."
    ),
    expected_amount_paise=None,
)

H05 = HoldoutCase(
    case_id="H05-cycle-3-reversal-cancels-cycle-1-finding",
    description=(
        "Refund in cycle 1, commission reversal in cycle 3, both inside the batch: the "
        "false positive D20 was written for."
    ),
    folded=_fold(
        "403-1000005-0000005",
        _order("403-1000005-0000005", 6, principal_paise=320_000, tax_paise=57_600),
        (
            _line(
                C1_FILE,
                91,
                C1_ID,
                TransactionType.ORDER,
                LineKind.PRINCIPAL,
                "ItemPrice",
                "Principal",
                320_000,
                C1_DATE,
                "403-1000005-0000005",
            ),
            _line(
                C1_FILE,
                92,
                C1_ID,
                TransactionType.ORDER,
                LineKind.COMMISSION,
                "ItemFees",
                "Commission",
                _commission(320_000),
                C1_DATE,
                "403-1000005-0000005",
            ),
            _line(
                C1_FILE,
                93,
                C1_ID,
                TransactionType.REFUND,
                LineKind.PRINCIPAL,
                "ItemPrice",
                "Principal",
                -320_000,
                C1_DATE,
                "403-1000005-0000005",
            ),
            _line(
                C3_FILE,
                101,
                C3_ID,
                TransactionType.REFUND,
                LineKind.COMMISSION,
                "ItemFees",
                "Commission",
                -_commission(320_000),
                C3_DATE,
                "403-1000005-0000005",
            ),
        ),
        (C1_ID, C3_ID),
        C3_DATE,
    ),
    profile=REGISTERED,
    expected_class=None,
    expected_state=None,
    expected_reason=(
        "Detectors consume the fold across every cycle in the batch, so the cycle-3 "
        "reversal cancels the cycle-1 finding. A per-cycle detector reports a "
        f"{_rupees(_commission(320_000))} loss that was repaid two cycles later."
    ),
    expected_amount_paise=None,
)

# --------------------------------------------------------------------------- #
# 06 — two classes on one order, additive (D19)
# --------------------------------------------------------------------------- #

H06 = HoldoutCase(
    case_id="H06-class-1-and-class-5-co-fire",
    description=(
        "One order carrying both a commission charged above the rate card and a refund "
        "whose commission was never reversed."
    ),
    folded=_fold(
        "403-1000006-0000006",
        _order("403-1000006-0000006", 7, principal_paise=500_000, tax_paise=90_000),
        (
            _line(
                C1_FILE,
                111,
                C1_ID,
                TransactionType.ORDER,
                LineKind.PRINCIPAL,
                "ItemPrice",
                "Principal",
                500_000,
                C1_DATE,
                "403-1000006-0000006",
            ),
            _line(
                C1_FILE,
                112,
                C1_ID,
                TransactionType.ORDER,
                LineKind.COMMISSION,
                "ItemFees",
                "Commission",
                _commission(500_000, bp=OVERCHARGED_COMMISSION_BP),
                C1_DATE,
                "403-1000006-0000006",
            ),
            _line(
                C2_FILE,
                121,
                C2_ID,
                TransactionType.REFUND,
                LineKind.PRINCIPAL,
                "ItemPrice",
                "Principal",
                -500_000,
                C2_MID_DATE,
                "403-1000006-0000006",
            ),
        ),
        (C1_ID, C2_ID),
        C3_DATE,
    ),
    profile=REGISTERED,
    expected_class=None,
    expected_state=None,
    expected_reason=(
        "Both classes must fire and their amounts add. Detector 1 references the "
        "commission line to recompute the percentage; detector 5 claims the same line for "
        "the absent reversal. The D19 key is (order, class, claimed line), so referencing "
        "is free and only claiming is exclusive. The two amounts together must still not "
        "exceed the order's total deductions."
    ),
    expected_amount_paise=None,
)

# --------------------------------------------------------------------------- #
# 07 — settlement lines for an order the seller never exported
# --------------------------------------------------------------------------- #

H07 = HoldoutCase(
    case_id="H07-order-absent-from-the-seller-export",
    description="Settlement lines reference an order id that appears in no row of the order export.",
    folded=_fold(
        "403-1000007-0000007",
        None,
        (
            _line(
                C1_FILE,
                131,
                C1_ID,
                TransactionType.ORDER,
                LineKind.PRINCIPAL,
                "ItemPrice",
                "Principal",
                210_000,
                C1_DATE,
                "403-1000007-0000007",
            ),
            _line(
                C1_FILE,
                132,
                C1_ID,
                TransactionType.ORDER,
                LineKind.COMMISSION,
                "ItemFees",
                "Commission",
                _commission(210_000),
                C1_DATE,
                "403-1000007-0000007",
            ),
        ),
        (C1_ID,),
        C3_DATE,
    ),
    profile=REGISTERED,
    expected_class=None,
    expected_state=None,
    expected_reason=(
        "An orphan is the mirror of class 6, not an instance of it: class 6 is an order in "
        "the export that no settlement pays, and this is a settlement with no export row. "
        "It is counted in orphan_order_ids and produces no finding. Without the order the "
        "category is unknown, so no rate-card recomputation may be attempted on it either. "
        "in_coverage is True and carries no meaning for this case: coverage is decided "
        "from the order's delivery date, and there is no order row to read one from, so "
        "the disposition that applies to this fold is orphan, never out-of-window."
    ),
    expected_amount_paise=None,
)

# --------------------------------------------------------------------------- #
# 08-09 — capability facts and evidence permanence (steps 4 and 5, premise P2)
# --------------------------------------------------------------------------- #

H08 = HoldoutCase(
    case_id="H08-capability-lapsed-before-the-event",
    description=(
        "GST registration held until 2026-06-30 and declared absent from 2026-07-01. Every "
        "date this order carries — ordered 2026-07-03, delivered 2026-07-05, settled "
        "2026-07-07 — falls after the lapse, so no reading of 'the event date' finds the "
        "seller registered. The Amazon-native form of the SPF/VMS case in premise P2. A "
        "plain over-charged sale with no refund, so only class 1 can fire."
    ),
    folded=_fold(
        "403-1000008-0000008",
        _order(
            "403-1000008-0000008",
            8,
            principal_paise=260_000,
            # Unregistered at the date of supply, so the order carries no GST.
            tax_paise=0,
            order_date=date(2026, 7, 3),
            delivery_date=date(2026, 7, 5),
        ),
        (
            _line(
                C1_FILE,
                141,
                C1_ID,
                TransactionType.ORDER,
                LineKind.PRINCIPAL,
                "ItemPrice",
                "Principal",
                260_000,
                C1_DATE,
                "403-1000008-0000008",
            ),
            _line(
                C1_FILE,
                142,
                C1_ID,
                TransactionType.ORDER,
                LineKind.COMMISSION,
                "ItemFees",
                "Commission",
                _commission(260_000, bp=OVERCHARGED_COMMISSION_BP),
                C1_DATE,
                "403-1000008-0000008",
            ),
        ),
        (C1_ID,),
        C2_DATE,
    ),
    profile=LAPSED_GST,
    expected_class=ErrorClass.COMMISSION_OVERCHARGE,
    expected_state=State.NOT_CLAIMABLE,
    expected_reason=(
        "evidence-unobtainable at step 4. The capability must be read at the event date, "
        "not at whichever fact appears first: reading the lapsed fact's holds=True passes "
        "a seller who can no longer issue a GST tax invoice. A GST tax invoice is dated "
        "to the supply and Order.order_date is the only invoice-shaped date the pipeline "
        "carries, so this case puts the order date, the delivery date and the settlement "
        "posting all after the lapse; whichever a reasonable implementation picks, the "
        "answer is the same and the case cannot be passed by choosing the convenient "
        "date. Class 1 files through a support ticket and has no filing window "
        "(ADR-0006), so steps 2 and 3 cannot pre-empt step 4 at all. The order carries no "
        "refund line, so detector 5 has nothing to fire on and the case isolates the "
        "capability question."
    ),
    expected_amount_paise=None,
)

H09 = HoldoutCase(
    case_id="H09-registered-but-invoice-not-yet-supplied",
    description=(
        "Same fee shape as H08 on a seller whose registration covers the event date, with "
        "the tax invoice not yet attached. No refund, so class 5 cannot co-fire."
    ),
    folded=_fold(
        "403-1000009-0000009",
        _order("403-1000009-0000009", 9, principal_paise=260_000, tax_paise=46_800),
        (
            _line(
                C2_FILE,
                151,
                C2_ID,
                TransactionType.ORDER,
                LineKind.PRINCIPAL,
                "ItemPrice",
                "Principal",
                260_000,
                C2_DATE,
                "403-1000009-0000009",
            ),
            _line(
                C2_FILE,
                152,
                C2_ID,
                TransactionType.ORDER,
                LineKind.COMMISSION,
                "ItemFees",
                "Commission",
                _commission(260_000, bp=OVERCHARGED_COMMISSION_BP),
                C2_DATE,
                "403-1000009-0000009",
            ),
        ),
        (C2_ID,),
        C3_DATE,
    ),
    profile=REGISTERED,
    expected_class=ErrorClass.COMMISSION_OVERCHARGE,
    expected_state=State.BLOCKED,
    expected_reason=(
        "seller-action at step 5, naming the tax invoice. The document exists and can be "
        "produced, so it is missing rather than unobtainable; collapsing steps 4 and 5 "
        "turns a to-do into a verdict. Class 1 has no filing window, so nothing above "
        "step 4 can decide this, and with no refund line only detector 1 fires: the case "
        "isolates the invoice question and scores exactly one class."
    ),
    expected_amount_paise=None,
)

# --------------------------------------------------------------------------- #
# 10-12 — calendar-day deadline arithmetic (D18)
# --------------------------------------------------------------------------- #

H10 = HoldoutCase(
    case_id="H10-window-expires-on-as-of-itself",
    description=(
        "Refund on 2026-07-06 and a 15-calendar-day window, evaluated with as_of on the "
        "expiry date itself."
    ),
    folded=_fold(
        "403-1000010-0000010",
        _order("403-1000010-0000010", 10, principal_paise=150_000, tax_paise=27_000),
        (
            _line(
                C1_FILE,
                161,
                C1_ID,
                TransactionType.ORDER,
                LineKind.PRINCIPAL,
                "ItemPrice",
                "Principal",
                150_000,
                C1_DATE,
                "403-1000010-0000010",
            ),
            _line(
                C1_FILE,
                162,
                C1_ID,
                TransactionType.ORDER,
                LineKind.COMMISSION,
                "ItemFees",
                "Commission",
                _commission(150_000),
                C1_DATE,
                "403-1000010-0000010",
            ),
            _line(
                C1_FILE,
                163,
                C1_ID,
                TransactionType.REFUND,
                LineKind.PRINCIPAL,
                "ItemPrice",
                "Principal",
                -150_000,
                date(2026, 7, 6),
                "403-1000010-0000010",
            ),
        ),
        (C1_ID,),
        date(2026, 7, 21),
    ),
    profile=REGISTERED,
    expected_class=ErrorClass.REFUND_NO_FEE_REVERSAL,
    expected_state=State.CLAIM_READY,
    expected_reason=(
        "2026-07-06 plus 15 calendar days is 2026-07-21, which is as_of. The window is "
        "open through its last day, days_left is 0, and the exception is claim-ready and "
        "sorts to the top of the queue. Treating expiry day as expired loses the claim on "
        "the one day it matters most."
    ),
    expected_amount_paise=-_commission(150_000),
)

H11 = HoldoutCase(
    case_id="H11-window-lands-on-a-leap-day",
    description="Refund on 2028-02-14 with a 15-day window landing on 2028-02-29.",
    folded=_fold(
        "403-1000011-0000011",
        _order(
            "403-1000011-0000011",
            11,
            principal_paise=220_000,
            tax_paise=39_600,
            order_date=date(2028, 2, 1),
            delivery_date=date(2028, 2, 5),
        ),
        (
            _line(
                "settlement_2028-02-16.txt",
                21,
                "IN-SET-2028-02-16",
                TransactionType.ORDER,
                LineKind.PRINCIPAL,
                "ItemPrice",
                "Principal",
                220_000,
                date(2028, 2, 16),
                "403-1000011-0000011",
            ),
            _line(
                "settlement_2028-02-16.txt",
                22,
                "IN-SET-2028-02-16",
                TransactionType.ORDER,
                LineKind.COMMISSION,
                "ItemFees",
                "Commission",
                _commission(220_000),
                date(2028, 2, 16),
                "403-1000011-0000011",
            ),
            _line(
                "settlement_2028-02-16.txt",
                23,
                "IN-SET-2028-02-16",
                TransactionType.REFUND,
                LineKind.PRINCIPAL,
                "ItemPrice",
                "Principal",
                -220_000,
                date(2028, 2, 14),
                "403-1000011-0000011",
            ),
        ),
        ("IN-SET-2028-02-16",),
        date(2028, 2, 29),
    ),
    profile=REGISTERED,
    expected_class=ErrorClass.REFUND_NO_FEE_REVERSAL,
    expected_state=State.CLAIM_READY,
    expected_reason=(
        "2028 is a leap year, so 2028-02-14 plus 15 calendar days is 2028-02-29 and the "
        "window is open on as_of with days_left 0. Arithmetic that skips 29 February "
        "expires this claim a day early."
    ),
    expected_amount_paise=-_commission(220_000),
)

H12 = HoldoutCase(
    case_id="H12-window-from-a-month-end-refund",
    description=(
        "Refund on 2026-01-31 with a 15-day window expiring 2026-02-15, evaluated one day later."
    ),
    folded=_fold(
        "403-1000012-0000012",
        _order(
            "403-1000012-0000012",
            12,
            principal_paise=95_000,
            tax_paise=17_100,
            order_date=date(2026, 1, 12),
            delivery_date=date(2026, 1, 18),
        ),
        (
            _line(
                "settlement_2026-02-03.txt",
                31,
                "IN-SET-2026-02-03",
                TransactionType.ORDER,
                LineKind.PRINCIPAL,
                "ItemPrice",
                "Principal",
                95_000,
                date(2026, 2, 3),
                "403-1000012-0000012",
            ),
            _line(
                "settlement_2026-02-03.txt",
                32,
                "IN-SET-2026-02-03",
                TransactionType.ORDER,
                LineKind.COMMISSION,
                "ItemFees",
                "Commission",
                _commission(95_000),
                date(2026, 2, 3),
                "403-1000012-0000012",
            ),
            _line(
                "settlement_2026-02-03.txt",
                33,
                "IN-SET-2026-02-03",
                TransactionType.REFUND,
                LineKind.PRINCIPAL,
                "ItemPrice",
                "Principal",
                -95_000,
                date(2026, 1, 31),
                "403-1000012-0000012",
            ),
        ),
        ("IN-SET-2026-02-03",),
        date(2026, 2, 16),
    ),
    profile=REGISTERED,
    expected_class=ErrorClass.REFUND_NO_FEE_REVERSAL,
    expected_state=State.NOT_CLAIMABLE,
    expected_reason=(
        "window-expired at step 2, by one day. Calendar-day arithmetic gives 2026-02-15; "
        "month-based arithmetic from a 31st gives 2026-02-28 and keeps a dead claim in "
        "₹ claim-ready, which is the worst direction for this error to run."
    ),
    expected_amount_paise=-_commission(95_000),
)

# --------------------------------------------------------------------------- #
# 13-14 — tax and reimbursement true negatives
# --------------------------------------------------------------------------- #

H13 = HoldoutCase(
    case_id="H13-tcs-reversed-on-a-refund",
    description=(
        "A refunded order carrying the matching positive TCS lines that give the collected "
        "tax back."
    ),
    folded=_fold(
        "403-1000013-0000013",
        _order("403-1000013-0000013", 13, principal_paise=300_000, tax_paise=54_000),
        (
            _line(
                C1_FILE,
                171,
                C1_ID,
                TransactionType.ORDER,
                LineKind.PRINCIPAL,
                "ItemPrice",
                "Principal",
                300_000,
                C1_DATE,
                "403-1000013-0000013",
            ),
            _line(
                C1_FILE,
                172,
                C1_ID,
                TransactionType.ORDER,
                LineKind.TCS,
                "ItemWithheldTax",
                "TCS-CGST",
                -1_500,
                C1_DATE,
                "403-1000013-0000013",
            ),
            _line(
                C1_FILE,
                173,
                C1_ID,
                TransactionType.ORDER,
                LineKind.TCS,
                "ItemWithheldTax",
                "TCS-SGST",
                -1_500,
                C1_DATE,
                "403-1000013-0000013",
            ),
            _line(
                C2_FILE,
                181,
                C2_ID,
                TransactionType.REFUND,
                LineKind.PRINCIPAL,
                "ItemPrice",
                "Principal",
                -300_000,
                C2_MID_DATE,
                "403-1000013-0000013",
            ),
            _line(
                C2_FILE,
                182,
                C2_ID,
                TransactionType.REFUND,
                LineKind.TCS,
                "ItemWithheldTax",
                "TCS-CGST",
                1_500,
                C2_MID_DATE,
                "403-1000013-0000013",
            ),
            _line(
                C2_FILE,
                183,
                C2_ID,
                TransactionType.REFUND,
                LineKind.TCS,
                "ItemWithheldTax",
                "TCS-SGST",
                1_500,
                C2_MID_DATE,
                "403-1000013-0000013",
            ),
        ),
        (C1_ID, C2_ID),
        C3_DATE,
    ),
    profile=REGISTERED,
    expected_class=None,
    expected_state=None,
    expected_reason=(
        "Section 52's own definition of net value of taxable supplies subtracts supplies "
        "returned during the month, so a refunded order nets to nil TCS and nothing "
        "fires. Recomputing against gross principal without netting the return invents a "
        "class-7 mismatch, and class 7 is the one bucket a false positive cannot be "
        "argued away in, because it goes to a tax professional."
    ),
    expected_amount_paise=None,
)

H14 = HoldoutCase(
    case_id="H14-safe-t-reimbursement-already-received",
    description=(
        "Unreversed commission on a refund, followed by a SAFE-T reimbursement line in a "
        "later cycle that already made the seller whole."
    ),
    folded=_fold(
        "403-1000014-0000014",
        _order("403-1000014-0000014", 14, principal_paise=280_000, tax_paise=50_400),
        (
            _line(
                C1_FILE,
                191,
                C1_ID,
                TransactionType.ORDER,
                LineKind.PRINCIPAL,
                "ItemPrice",
                "Principal",
                280_000,
                C1_DATE,
                "403-1000014-0000014",
            ),
            _line(
                C1_FILE,
                192,
                C1_ID,
                TransactionType.ORDER,
                LineKind.COMMISSION,
                "ItemFees",
                "Commission",
                _commission(280_000),
                C1_DATE,
                "403-1000014-0000014",
            ),
            _line(
                C1_FILE,
                193,
                C1_ID,
                TransactionType.REFUND,
                LineKind.PRINCIPAL,
                "ItemPrice",
                "Principal",
                -280_000,
                C1_DATE,
                "403-1000014-0000014",
            ),
            _line(
                C3_FILE,
                201,
                C3_ID,
                TransactionType.SAFET_REIMBURSEMENT,
                LineKind.SAFET_REIMBURSEMENT,
                "other-transaction",
                "SAFE-T Reimbursement",
                -_commission(280_000),
                C3_DATE,
                "403-1000014-0000014",
                sku=None,
                quantity=None,
                adjustment_id="27732-20132-7929303",
            ),
        ),
        (C1_ID, C3_ID),
        C3_DATE,
    ),
    profile=REGISTERED,
    expected_class=None,
    expected_state=None,
    expected_reason=(
        "A reimbursement already received is money back, so the loss is closed even though "
        "no commission-reversal line exists. Missing it produces a claim the seller has "
        "already won, which is the single most embarrassing false positive this product "
        "can emit, and Amazon.in allows only one SAFE-T claim per order id."
    ),
    expected_amount_paise=None,
)

# --------------------------------------------------------------------------- #
# 15-16 — line-level pathology
# --------------------------------------------------------------------------- #

H15 = HoldoutCase(
    case_id="H15-two-identical-commission-lines",
    description=(
        "The same commission charged twice on one order: two lines identical in every "
        "field but their row number."
    ),
    folded=_fold(
        "403-1000015-0000015",
        _order("403-1000015-0000015", 15, principal_paise=160_000, tax_paise=28_800),
        (
            _line(
                C1_FILE,
                211,
                C1_ID,
                TransactionType.ORDER,
                LineKind.PRINCIPAL,
                "ItemPrice",
                "Principal",
                160_000,
                C1_DATE,
                "403-1000015-0000015",
            ),
            _line(
                C1_FILE,
                212,
                C1_ID,
                TransactionType.ORDER,
                LineKind.COMMISSION,
                "ItemFees",
                "Commission",
                _commission(160_000),
                C1_DATE,
                "403-1000015-0000015",
            ),
            _line(
                C1_FILE,
                213,
                C1_ID,
                TransactionType.ORDER,
                LineKind.COMMISSION,
                "ItemFees",
                "Commission",
                _commission(160_000),
                C1_DATE,
                "403-1000015-0000015",
            ),
        ),
        (C1_ID,),
        C3_DATE,
    ),
    profile=REGISTERED,
    expected_class=ErrorClass.COMMISSION_OVERCHARGE,
    expected_state=State.CLAIM_READY,
    expected_reason=(
        "Exactly one finding, for the duplicate charge, claimed on the second line's own "
        "line_id: the rows are distinct deductions and de-duplicating them at parse time "
        f"would erase a real {_rupees(_commission(160_000))} loss. CLAIM-READY at step 6, and this case is why "
        "ADR-0006 was taken: while class 1 filed through SAFE-T it expected "
        "BLOCKED(timing) at step 3 forever, because a plain un-refunded sale has no "
        "refund or return-scan date to start a window from. Class 1 now files through a "
        "support ticket with no window, so steps 2 and 3 cannot fire, both commission "
        "lines and the principal row are report-derivable, this seller holds the GST "
        "registration the tax invoice needs, and the ladder falls through."
    ),
    expected_amount_paise=-_commission(160_000),
)

H16 = HoldoutCase(
    case_id="H16-zero-amount-line",
    description="A well-formed settlement line whose amount is exactly zero.",
    folded=_fold(
        "403-1000016-0000016",
        _order("403-1000016-0000016", 16, principal_paise=140_000, tax_paise=25_200),
        (
            _line(
                C1_FILE,
                221,
                C1_ID,
                TransactionType.ORDER,
                LineKind.PRINCIPAL,
                "ItemPrice",
                "Principal",
                140_000,
                C1_DATE,
                "403-1000016-0000016",
            ),
            _line(
                C1_FILE,
                222,
                C1_ID,
                TransactionType.ORDER,
                LineKind.PROMOTION,
                "Promotion",
                "Principal",
                0,
                C1_DATE,
                "403-1000016-0000016",
            ),
            _line(
                C1_FILE,
                223,
                C1_ID,
                TransactionType.ORDER,
                LineKind.COMMISSION,
                "ItemFees",
                "Commission",
                _commission(140_000),
                C1_DATE,
                "403-1000016-0000016",
            ),
        ),
        (C1_ID,),
        C3_DATE,
    ),
    profile=REGISTERED,
    expected_class=None,
    expected_state=None,
    expected_reason=(
        "Zero is a value, not a defect. The line is neither quarantined nor treated as a "
        "discrepancy; it stays in the match-rate denominator and contributes nothing to "
        "any rupee line. A truthiness check on the amount drops it and moves the match "
        "rate for a row that parsed perfectly."
    ),
    expected_amount_paise=None,
)

# --------------------------------------------------------------------------- #
# 17-18 — class 8, the two bases (ADR-0005)
# --------------------------------------------------------------------------- #

H17 = HoldoutCase(
    case_id="H17-known-code-with-no-rule",
    description=(
        "A deduction under a vocabulary pair the parser recognises, for a kind the rate "
        "card neither audits nor acknowledges. The case assumes lane C's corpus declares "
        "neither a rule nor an acknowledgement for LineKind.TECHNOLOGY_FEE; this package "
        "never reads that corpus (D12), so the assumption is stated rather than checked, "
        "and if lane C acknowledges the kind this case has to move to another one."
    ),
    folded=_fold(
        "403-1000017-0000017",
        _order("403-1000017-0000017", 17, principal_paise=190_000, tax_paise=34_200),
        (
            _line(
                C1_FILE,
                231,
                C1_ID,
                TransactionType.ORDER,
                LineKind.PRINCIPAL,
                "ItemPrice",
                "Principal",
                190_000,
                C1_DATE,
                "403-1000017-0000017",
            ),
            _line(
                C1_FILE,
                232,
                C1_ID,
                TransactionType.ORDER,
                LineKind.TECHNOLOGY_FEE,
                "ItemFees",
                "TechnologyFee",
                -25_000,
                C1_DATE,
                "403-1000017-0000017",
            ),
        ),
        (C1_ID,),
        C3_DATE,
    ),
    profile=REGISTERED,
    expected_class=ErrorClass.UNEXPLAINED_DEDUCTION,
    expected_state=State.UNEXPLAINED,
    expected_reason=(
        "Basis code-known-no-rule. Recognising the pair is not the same as being able to "
        "say the charge was wrong, so the mechanism is none and the ladder stops at step "
        "0. Reporting it as claim-ready because the code parsed would put a number nobody "
        "can defend in front of a seller."
    ),
    expected_amount_paise=25_000,
)

H18 = HoldoutCase(
    case_id="H18-unseen-code",
    description="A deduction under an amount-description that is not in the vocabulary at all.",
    folded=_fold(
        "403-1000018-0000018",
        _order("403-1000018-0000018", 18, principal_paise=210_000, tax_paise=37_800),
        (
            _line(
                C1_FILE,
                241,
                C1_ID,
                TransactionType.ORDER,
                LineKind.PRINCIPAL,
                "ItemPrice",
                "Principal",
                210_000,
                C1_DATE,
                "403-1000018-0000018",
            ),
            _line(
                C1_FILE,
                242,
                C1_ID,
                TransactionType.ORDER,
                LineKind.UNCLASSIFIED,
                "ItemFees",
                "SellerRewardsAdjustment",
                -34_000,
                C1_DATE,
                "403-1000018-0000018",
            ),
        ),
        (C1_ID,),
        C3_DATE,
    ),
    profile=REGISTERED,
    expected_class=ErrorClass.UNEXPLAINED_DEDUCTION,
    expected_state=State.UNEXPLAINED,
    expected_reason=(
        "Basis code-unseen. The pair maps to UNCLASSIFIED and the raw strings stay on the "
        "line so the report can name what it could not read. Above the floor it is class "
        "8 and reported under ₹ unexplained; it is never dropped and never inside "
        "₹ identified."
    ),
    expected_amount_paise=34_000,
)

# --------------------------------------------------------------------------- #
# 19-20 — the two SAFE-T exclusions (premise P3)
# --------------------------------------------------------------------------- #

H19 = HoldoutCase(
    case_id="H19-a-to-z-refund-without-fee-reversal",
    description="Commission never reversed on an order refunded under the A-to-z Guarantee.",
    folded=_fold(
        "403-1000019-0000019",
        _order(
            "403-1000019-0000019",
            19,
            principal_paise=340_000,
            tax_paise=61_200,
            refund_initiated_by=RefundInitiator.AMAZON,
        ),
        (
            _line(
                C1_FILE,
                251,
                C1_ID,
                TransactionType.ORDER,
                LineKind.PRINCIPAL,
                "ItemPrice",
                "Principal",
                340_000,
                C1_DATE,
                "403-1000019-0000019",
            ),
            _line(
                C1_FILE,
                252,
                C1_ID,
                TransactionType.ORDER,
                LineKind.COMMISSION,
                "ItemFees",
                "Commission",
                _commission(340_000),
                C1_DATE,
                "403-1000019-0000019",
            ),
            _line(
                C2_FILE,
                261,
                C2_ID,
                TransactionType.ATOZ_REFUND,
                LineKind.PRINCIPAL,
                "ItemPrice",
                "Principal",
                -340_000,
                C2_MID_DATE,
                "403-1000019-0000019",
            ),
        ),
        (C1_ID, C2_ID),
        C3_DATE,
    ),
    profile=REGISTERED,
    expected_class=ErrorClass.REFUND_NO_FEE_REVERSAL,
    expected_state=State.NOT_CLAIMABLE,
    expected_reason=(
        "rule at step 1. A granted A-to-z claim is an adjudication Amazon already made on "
        "the order, and the only eligible/ineligible list found names it as an exclusion. "
        "The window is still open, which is the trap: a ladder that checks the window "
        "before the rules reports this as claim-ready."
    ),
    expected_amount_paise=-_commission(340_000),
)

H20 = HoldoutCase(
    case_id="H20-seller-issued-refund-without-fee-reversal",
    description="The same shape as H19 on a refund the seller issued themselves.",
    folded=_fold(
        "403-1000020-0000020",
        _order(
            "403-1000020-0000020",
            20,
            principal_paise=340_000,
            tax_paise=61_200,
            refund_initiated_by=RefundInitiator.SELLER,
        ),
        (
            _line(
                C1_FILE,
                271,
                C1_ID,
                TransactionType.ORDER,
                LineKind.PRINCIPAL,
                "ItemPrice",
                "Principal",
                340_000,
                C1_DATE,
                "403-1000020-0000020",
            ),
            _line(
                C1_FILE,
                272,
                C1_ID,
                TransactionType.ORDER,
                LineKind.COMMISSION,
                "ItemFees",
                "Commission",
                _commission(340_000),
                C1_DATE,
                "403-1000020-0000020",
            ),
            _line(
                C2_FILE,
                281,
                C2_ID,
                TransactionType.REFUND,
                LineKind.PRINCIPAL,
                "ItemPrice",
                "Principal",
                -340_000,
                C2_MID_DATE,
                "403-1000020-0000020",
            ),
        ),
        (C1_ID, C2_ID),
        C3_DATE,
    ),
    profile=REGISTERED,
    expected_class=ErrorClass.REFUND_NO_FEE_REVERSAL,
    expected_state=State.NOT_CLAIMABLE,
    expected_reason=(
        "rule at step 1, on refund_initiated_by from the seller's own export. The "
        "settlement lines are identical to a claimable case, so the exclusion can only be "
        "read from the order export; a detector that works from settlement rows alone "
        "cannot tell H20 from a genuine claim."
    ),
    expected_amount_paise=-_commission(340_000),
)

# --------------------------------------------------------------------------- #
# 21-25 — dispositions, cycles, and the boundary of what the sources cover
# --------------------------------------------------------------------------- #

H21 = HoldoutCase(
    case_id="H21-one-paisa-below-the-floor",
    description=(
        f"Unreversed commission of {_rupees(H21_UNREVERSED_PAISE)}, a single paisa under "
        "the materiality floor."
    ),
    folded=_fold(
        "403-1000021-0000021",
        _order(
            "403-1000021-0000021",
            21,
            principal_paise=H21_PRINCIPAL_PAISE,
            tax_paise=1_383,
        ),
        (
            _line(
                C1_FILE,
                291,
                C1_ID,
                TransactionType.ORDER,
                LineKind.PRINCIPAL,
                "ItemPrice",
                "Principal",
                H21_PRINCIPAL_PAISE,
                C1_DATE,
                "403-1000021-0000021",
            ),
            _line(
                C1_FILE,
                292,
                C1_ID,
                TransactionType.ORDER,
                LineKind.COMMISSION,
                "ItemFees",
                "Commission",
                _commission(H21_PRINCIPAL_PAISE),
                C1_DATE,
                "403-1000021-0000021",
            ),
            _line(
                C2_FILE,
                301,
                C2_ID,
                TransactionType.REFUND,
                LineKind.PRINCIPAL,
                "ItemPrice",
                "Principal",
                -H21_PRINCIPAL_PAISE,
                C2_MID_DATE,
                "403-1000021-0000021",
            ),
        ),
        (C1_ID, C2_ID),
        C3_DATE,
    ),
    profile=REGISTERED,
    expected_class=None,
    expected_state=None,
    expected_reason=(
        "Aggregated into ₹ below-materiality, counted in the row count beside it, never "
        "queued and never inside ₹ identified. Paired with H03 it pins both sides of the "
        "floor to the paisa."
    ),
    expected_amount_paise=H21_UNREVERSED_PAISE,
)

H22 = HoldoutCase(
    case_id="H22-delivery-outside-the-declared-coverage",
    description=(
        "A delivered order whose delivery date falls outside the batch's declared cycle "
        "coverage window."
    ),
    folded=_fold(
        "403-1000022-0000022",
        _order(
            "403-1000022-0000022",
            22,
            principal_paise=175_000,
            tax_paise=31_500,
            order_date=date(2026, 4, 2),
            delivery_date=date(2026, 4, 9),
        ),
        (),
        (),
        C3_DATE,
        in_coverage=False,
    ),
    profile=REGISTERED,
    expected_class=None,
    expected_state=None,
    expected_reason=(
        "OUT-OF-WINDOW disposition, displayed with its own count beside the match rate and "
        "outside every rupee line. Class 6 must not fire: the order is unpaid inside this "
        "batch only because the seller uploaded a partial history, which is one of the "
        "three false positives D20 exists to stop."
    ),
    expected_amount_paise=None,
)

H23 = HoldoutCase(
    case_id="H23-capability-never-declared",
    description=(
        "The same fee shape as H08 and H09, charged at the same rate above the assumed "
        "one, on a seller profile that declares no capability facts at all."
    ),
    folded=_fold(
        "403-1000023-0000023",
        _order("403-1000023-0000023", 23, principal_paise=260_000, tax_paise=46_800),
        (
            _line(
                C2_FILE,
                311,
                C2_ID,
                TransactionType.ORDER,
                LineKind.PRINCIPAL,
                "ItemPrice",
                "Principal",
                260_000,
                C2_DATE,
                "403-1000023-0000023",
            ),
            _line(
                C2_FILE,
                312,
                C2_ID,
                TransactionType.ORDER,
                LineKind.COMMISSION,
                "ItemFees",
                "Commission",
                _commission(260_000, bp=OVERCHARGED_COMMISSION_BP),
                C2_DATE,
                "403-1000023-0000023",
            ),
        ),
        (C2_ID,),
        C3_DATE,
    ),
    profile=UNDECLARED,
    expected_class=ErrorClass.COMMISSION_OVERCHARGE,
    expected_state=State.BLOCKED,
    expected_reason=(
        "seller-action at step 5, naming the tax invoice and noting permanence unknown. "
        "capability() returns None here, and None is not False: without the profile "
        "config step 4 is unreachable and the case must degrade to step 5 honestly rather "
        "than be declared unobtainable. Reading None as False sends H23 to the same "
        "not-claimable line as H08 on no evidence at all. The commission here is charged "
        "above the assumed rate, exactly as in H08 and H09; at the assumed rate no class-1 "
        "finding could exist and the case would be unsatisfiable. There is no refund line, "
        "so class 5 cannot co-fire and the permanence question is the only one being asked."
    ),
    expected_amount_paise=None,
)

H24 = HoldoutCase(
    case_id="H24-unpaid-in-cycle-1-paid-in-cycle-3",
    description=(
        "A delivered order absent from the first two settlements and settled in the third, "
        "inside the batch."
    ),
    folded=_fold(
        "403-1000024-0000024",
        _order("403-1000024-0000024", 24, principal_paise=230_000, tax_paise=41_400),
        (
            _line(
                C3_FILE,
                321,
                C3_ID,
                TransactionType.ORDER,
                LineKind.PRINCIPAL,
                "ItemPrice",
                "Principal",
                230_000,
                C3_DATE,
                "403-1000024-0000024",
            ),
            _line(
                C3_FILE,
                322,
                C3_ID,
                TransactionType.ORDER,
                LineKind.COMMISSION,
                "ItemFees",
                "Commission",
                _commission(230_000),
                C3_DATE,
                "403-1000024-0000024",
            ),
        ),
        (C3_ID,),
        C3_DATE,
    ),
    profile=REGISTERED,
    expected_class=None,
    expected_state=None,
    expected_reason=(
        "Delivery on 2026-07-02 is more than two cycles before as_of, so a detector "
        "looking only at the cycles it expected payment in fires. The fold carries the "
        "cycle-3 payment, so class 6 must not fire, and the order counts as matched in "
        "both match rates."
    ),
    expected_amount_paise=None,
)

H25 = HoldoutCase(
    case_id="H25-chargeback-refund-no-source-covers",
    description=(
        "Commission never reversed on a chargeback refund: neither seller-issued nor a "
        "granted A-to-z claim, and no source read this session says whether it is eligible."
    ),
    folded=_fold(
        "403-1000025-0000025",
        _order(
            "403-1000025-0000025",
            25,
            principal_paise=410_000,
            tax_paise=73_800,
            category_id="apparel",
            refund_initiated_by=RefundInitiator.NONE,
        ),
        (
            _line(
                C1_FILE,
                331,
                C1_ID,
                TransactionType.ORDER,
                LineKind.PRINCIPAL,
                "ItemPrice",
                "Principal",
                410_000,
                C1_DATE,
                "403-1000025-0000025",
            ),
            _line(
                C1_FILE,
                332,
                C1_ID,
                TransactionType.ORDER,
                LineKind.COMMISSION,
                "ItemFees",
                "Commission",
                _commission(410_000),
                C1_DATE,
                "403-1000025-0000025",
            ),
            _line(
                C2_FILE,
                341,
                C2_ID,
                TransactionType.CHARGEBACK_REFUND,
                LineKind.PRINCIPAL,
                "ItemPrice",
                "Principal",
                -410_000,
                C2_MID_DATE,
                "403-1000025-0000025",
            ),
        ),
        (C1_ID, C2_ID),
        C3_DATE,
    ),
    profile=REGISTERED,
    expected_class=ErrorClass.REFUND_NO_FEE_REVERSAL,
    expected_state=State.CLAIM_READY,
    expected_reason=(
        "Neither encoded exclusion fires and the window is open, so the ladder falls "
        "through to step 6. This is the case most likely to be wrong: Amazon.in's A-to-z "
        "page lists bank-initiated chargebacks as outside that guarantee, and the SAFE-T "
        "terms that would say whether a chargeback refund is claimable are behind the "
        "Seller Central sign-in. Recorded deliberately so that reaching the primary page "
        "later changes a published holdout line rather than a silent assumption. The "
        "refund is posted on 2026-07-10 rather than on the cycle-2 boundary, so an "
        "off-by-one in the D20 fold cannot surface here as a chargeback-eligibility "
        "answer; H26 owns that boundary."
    ),
    expected_amount_paise=-_commission(410_000),
)


# --------------------------------------------------------------------------- #
# 26 — the D20 one-cycle boundary, on it deliberately
# --------------------------------------------------------------------------- #

H26 = HoldoutCase(
    case_id="H26-refund-exactly-one-cycle-before-the-batch-max",
    description=(
        "Unreversed commission on a refund posted exactly DEFAULT_CYCLE_DAYS before the "
        "batch's max settlement date: the boundary between C5_PLAIN and C5_AWAITING_CYCLE."
    ),
    folded=_fold(
        "403-1000026-0000026",
        _order("403-1000026-0000026", 26, principal_paise=300_000, tax_paise=54_000),
        (
            _line(
                C1_FILE,
                351,
                C1_ID,
                TransactionType.ORDER,
                LineKind.PRINCIPAL,
                "ItemPrice",
                "Principal",
                300_000,
                C1_DATE,
                "403-1000026-0000026",
            ),
            _line(
                C1_FILE,
                352,
                C1_ID,
                TransactionType.ORDER,
                LineKind.COMMISSION,
                "ItemFees",
                "Commission",
                _commission(300_000),
                C1_DATE,
                "403-1000026-0000026",
            ),
            _line(
                C2_FILE,
                361,
                C2_ID,
                TransactionType.REFUND,
                LineKind.PRINCIPAL,
                "ItemPrice",
                "Principal",
                -300_000,
                C2_DATE,
                "403-1000026-0000026",
            ),
        ),
        (C1_ID, C2_ID),
        C3_DATE,
    ),
    profile=REGISTERED,
    expected_class=ErrorClass.REFUND_NO_FEE_REVERSAL,
    expected_state=State.CLAIM_READY,
    expected_reason=(
        "The refund is posted on 2026-07-14 and the batch's max settlement date is "
        "2026-07-21, exactly DEFAULT_CYCLE_DAYS apart. C5_PLAIN is a refund settled at "
        "least one full cycle ago and C5_AWAITING_CYCLE is one settled less than a full "
        "cycle ago, so at-or-above is the rule and this case is C5_PLAIN, not "
        "C5_AWAITING_CYCLE: strict greater-than parks a real claim in BLOCKED(timing) "
        "for a week. It exists so that an off-by-one in the fold shows up here, on the "
        "boundary it names, rather than in H03 or H25, which pin the materiality floor "
        "and chargeback eligibility and used to sit on this boundary by accident. The "
        "refund date is on the line and 2026-07-14 plus the encoded 15-day filing window "
        "is 2026-07-29, so the window is open and the ladder falls through to step 6."
    ),
    expected_amount_paise=-_commission(300_000),
)


HOLDOUT_CASES: Final[tuple[HoldoutCase, ...]] = (
    H01,
    H02,
    H03,
    H04,
    H05,
    H06,
    H07,
    H08,
    H09,
    H10,
    H11,
    H12,
    H13,
    H14,
    H15,
    H16,
    H17,
    H18,
    H19,
    H20,
    H21,
    H22,
    H23,
    H24,
    H25,
    H26,
)


def load_holdout() -> tuple[HoldoutCase, ...]:
    """The hand-authored adversarial cases, in stable order (D12)."""
    return HOLDOUT_CASES
