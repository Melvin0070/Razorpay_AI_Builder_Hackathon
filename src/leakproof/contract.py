"""Shared contract boundary (design doc D22).

Imported by BOTH the generator side and the detector side. Holds only what the
two must agree on and that is not itself under test: enums, the paise type and
its arithmetic, the materiality floor, the line_id format, ``as_of`` semantics,
the class table, the raw settlement-line vocabulary, and the frozen-labels
checksum.

Deliberately absent, and why:

* fee rates and slabs -- ``ratecard/`` (lane C) and ``generator/`` (lane B) are
  two independent encodings of the same public sources. Sharing them here would
  make the detector agree with the generator by construction and kill D12.
* eligibility rules -- ``evidence/`` (lane K), for the same reason against
  ``labels/`` (lane F).
* claimability labels -- ``labels/`` (lane F). Frozen; only their checksum
  lives here.
* the precedence ladder, dedup, and the partition sums -- ``triage/`` (lane L).
  Those are hard gates under test, so they are not contract.

This file is integrator-owned and frozen for the duration of a wave. Lanes that
need a change file an interface change request in their report.
"""

from __future__ import annotations

from enum import IntEnum, StrEnum
from typing import Final

# --------------------------------------------------------------------------- #
# Money (D3)
# --------------------------------------------------------------------------- #

#: Signed integer paise. Amounts are carried exactly as the settlement file
#: writes them: sales positive, fees and refunds negative. There is no float
#: anywhere on the money path.
Paise = int

#: Discrepancies below this are aggregated into "below materiality", counted and
#: reported, never queued, never in "identified" (D3). Ten rupees.
MATERIALITY_FLOOR_PAISE: Final[Paise] = 1_000

#: Per-rule comparison tolerance (D3). One rupee.
TOLERANCE_PAISE: Final[Paise] = 100

#: Basis points in a whole. 12% commission is 1_200 bp.
BP_PER_UNIT: Final[int] = 10_000


def apply_bp(paise: Paise, bp: int) -> Paise:
    """``paise × bp / 10_000`` rounded half away from zero.

    The one rounding rule both encodings (generator fee logic, detector
    recomputation) must share, otherwise ₹-agreement fails on rounding rather
    than on substance. Integer arithmetic only.
    """
    sign = -1 if (paise < 0) != (bp < 0) else 1
    q, r = divmod(abs(paise) * abs(bp), BP_PER_UNIT)
    if r * 2 >= BP_PER_UNIT:
        q += 1
    return sign * q


def paise_delta(a: Paise, b: Paise) -> Paise:
    """``a − b``. Exists so call sites read as money, not as arithmetic."""
    return a - b


def paise_within(a: Paise, b: Paise, tolerance: Paise = TOLERANCE_PAISE) -> bool:
    """True when ``a`` and ``b`` agree within ``tolerance`` (inclusive)."""
    return abs(a - b) <= tolerance


def compare_paise(a: Paise, b: Paise, tolerance: Paise = TOLERANCE_PAISE) -> int:
    """Three-way comparison with tolerance: -1 if ``a < b``, 0 if within
    tolerance, +1 if ``a > b``."""
    if paise_within(a, b, tolerance):
        return 0
    return -1 if a < b else 1


def is_material(paise: Paise) -> bool:
    """A discrepancy is material at or above the floor (D3)."""
    return abs(paise) >= MATERIALITY_FLOOR_PAISE


# --------------------------------------------------------------------------- #
# Line identity and clocks
# --------------------------------------------------------------------------- #

#: line_id is ``<source file basename>:<row>``, where row is the 1-based
#: physical line number in that file, header included, so a citation matches
#: what a person sees in a text editor. ``settlement_2026-08-21.txt:1204``.
LINE_ID_SEPARATOR: Final[str] = ":"


def make_line_id(source_file: str, row: int) -> str:
    if row < 1:
        raise ValueError(f"row must be 1-based, got {row}")
    if LINE_ID_SEPARATOR in source_file:
        raise ValueError(f"source file name may not contain {LINE_ID_SEPARATOR!r}: {source_file}")
    return f"{source_file}{LINE_ID_SEPARATOR}{row}"


def parse_line_id(line_id: str) -> tuple[str, int]:
    source_file, _, row = line_id.rpartition(LINE_ID_SEPARATOR)
    if not source_file or not row.isdigit() or int(row) < 1:
        raise ValueError(f"malformed line_id: {line_id!r}")
    return source_file, int(row)


#: ``as_of`` semantics (D18): every batch carries an evaluation date. Default is
#: the batch's maximum settlement posted-date; the manifest may override it.
#: All window arithmetic and the detector-6 cycle threshold evaluate against
#: ``as_of``, never the system clock. Deadline arithmetic is in calendar days.
AS_OF_DEFAULT_RULE: Final[str] = "max settlement posted-date in the batch"

#: Settlement cycle length the generator writes and the fold reads (D20).
DEFAULT_CYCLE_DAYS: Final[int] = 7


# --------------------------------------------------------------------------- #
# Vocabulary shared by every lane
# --------------------------------------------------------------------------- #


class ErrorClass(IntEnum):
    """Detected error classes. Numbering preserved from the design history;
    3 and 4 are cut, and their numbers are never reused."""

    COMMISSION_OVERCHARGE = 1
    FIXED_FEE_ERROR = 2
    REFUND_NO_FEE_REVERSAL = 5
    UNPAID_PAST_CYCLE = 6
    TAX_MISMATCH = 7
    UNEXPLAINED_DEDUCTION = 8


class Mechanism(StrEnum):
    SAFE_T = "SAFE-T"
    SUPPORT_TICKET = "support-ticket"
    CA_REVIEW = "CA-review"
    NONE = "none"


class State(StrEnum):
    CLAIM_READY = "CLAIM-READY"
    BLOCKED = "BLOCKED"
    UNEXPLAINED = "UNEXPLAINED"
    NOT_CLAIMABLE = "NOT-CLAIMABLE"


#: Queue group order (design doc, "Queue sort"): four groups matching four states.
STATE_ORDER: Final[tuple[State, ...]] = (
    State.CLAIM_READY,
    State.BLOCKED,
    State.UNEXPLAINED,
    State.NOT_CLAIMABLE,
)


class BlockerKind(StrEnum):
    SELLER_ACTION = "seller-action"
    TIMING = "timing"
    PROFESSIONAL_REVIEW = "professional-review"


class NotClaimableReason(StrEnum):
    """Why a finding is NOT-CLAIMABLE; one per emitting precedence step."""

    RULE = "rule"  # step 1
    WINDOW_EXPIRED = "window-expired"  # step 2
    EVIDENCE_UNOBTAINABLE = "evidence-unobtainable"  # step 4


class UnexplainedBasis(StrEnum):
    CODE_UNSEEN = "code-unseen"
    CODE_KNOWN_NO_RULE = "code-known-no-rule"


class Disposition(StrEnum):
    """Outcomes that sit outside every rupee line, each displayed as its own
    count beside the match rate (design doc, "Rupee partition")."""

    QUARANTINE = "quarantine"
    UNCOVERED = "uncovered"
    OUT_OF_WINDOW = "out-of-window"
    CONFIG_ERROR = "config-error"


class EvidenceSource(StrEnum):
    REPORT_DERIVABLE = "report-derivable"
    SELLER_SUPPLIABLE = "seller-suppliable"
    UNOBTAINABLE = "unobtainable"


class EvidenceStatus(StrEnum):
    SATISFIED = "satisfied"
    MISSING = "missing"
    PENDING = "pending"


class WindowStatus(StrEnum):
    """Filing-window arithmetic outcome (precedence steps 2 and 3)."""

    OPEN = "open"
    EXPIRED = "expired"
    START_DATE_MISSING = "start-date-missing"
    NOT_APPLICABLE = "not-applicable"


class AuditAction(StrEnum):
    """D21 actions plus ``flag`` (ADR-0004): the UNEXPLAINED gate writes one
    audit entry carrying the basis and no claim pack."""

    INGEST = "ingest"
    DETECT = "detect"
    CLASSIFY = "classify"
    DRAFT = "draft"
    APPROVE = "approve"
    APPROVE_OVERRIDE = "approve_override"
    REJECT = "reject"
    EXPORT = "export"
    FLAG = "flag"


class RefundInitiator(StrEnum):
    """Who initiated a refund, from the seller's own order export. SAFE-T
    excludes seller-issued refunds (premise P3)."""

    NONE = "none"
    SELLER = "seller"
    AMAZON = "amazon"


# --------------------------------------------------------------------------- #
# Class table (executable, D23) and the rupee partition function
# --------------------------------------------------------------------------- #

#: Mechanisms a class may carry. ``make_finding`` (lane J) raises on disagreement.
ALLOWED_MECHANISMS: Final[dict[ErrorClass, frozenset[Mechanism]]] = {
    ErrorClass.COMMISSION_OVERCHARGE: frozenset({Mechanism.SUPPORT_TICKET}),
    ErrorClass.FIXED_FEE_ERROR: frozenset({Mechanism.SUPPORT_TICKET}),
    ErrorClass.REFUND_NO_FEE_REVERSAL: frozenset({Mechanism.SAFE_T, Mechanism.SUPPORT_TICKET}),
    ErrorClass.UNPAID_PAST_CYCLE: frozenset({Mechanism.SUPPORT_TICKET}),
    ErrorClass.TAX_MISMATCH: frozenset({Mechanism.CA_REVIEW}),
    ErrorClass.UNEXPLAINED_DEDUCTION: frozenset({Mechanism.NONE}),
}

#: The mechanism a detector assigns. The design's precedence ladder has no
#: "try the next mechanism" step, so a class with two allowed mechanisms still
#: files under its primary one; the alternative is documentation (ADR-0005).
PRIMARY_MECHANISM: Final[dict[ErrorClass, Mechanism]] = {
    ErrorClass.COMMISSION_OVERCHARGE: Mechanism.SUPPORT_TICKET,
    ErrorClass.FIXED_FEE_ERROR: Mechanism.SUPPORT_TICKET,
    ErrorClass.REFUND_NO_FEE_REVERSAL: Mechanism.SAFE_T,
    ErrorClass.UNPAID_PAST_CYCLE: Mechanism.SUPPORT_TICKET,
    ErrorClass.TAX_MISMATCH: Mechanism.CA_REVIEW,
    ErrorClass.UNEXPLAINED_DEDUCTION: Mechanism.NONE,
}

#: Only SAFE-T carries a real filing window (design doc, approach B′ costs).
#: SAFE-T is scoped to refund- and return-shaped loss, so only class 5 files
#: through it; a fee-arithmetic dispute has no return event to start a window
#: from and goes by support ticket (ADR-0006).
MECHANISMS_WITH_WINDOW: Final[frozenset[Mechanism]] = frozenset({Mechanism.SAFE_T})


class ClassBucket(StrEnum):
    IDENTIFIED = "identified"  # classes 1, 2, 5, 6
    TAX_REVIEW = "tax-review"  # class 7
    UNEXPLAINED = "unexplained"  # class 8


CLASS_BUCKET: Final[dict[ErrorClass, ClassBucket]] = {
    ErrorClass.COMMISSION_OVERCHARGE: ClassBucket.IDENTIFIED,
    ErrorClass.FIXED_FEE_ERROR: ClassBucket.IDENTIFIED,
    ErrorClass.REFUND_NO_FEE_REVERSAL: ClassBucket.IDENTIFIED,
    ErrorClass.UNPAID_PAST_CYCLE: ClassBucket.IDENTIFIED,
    ErrorClass.TAX_MISMATCH: ClassBucket.TAX_REVIEW,
    ErrorClass.UNEXPLAINED_DEDUCTION: ClassBucket.UNEXPLAINED,
}


class RupeeLine(StrEnum):
    """The seven-line partition minus the two sums (identified, total), which
    are derived, and plus below-materiality, which never carries a state."""

    CLAIM_READY = "claim-ready"
    BLOCKED = "blocked"
    NOT_CLAIMABLE = "not-claimable"
    TAX_REVIEW = "tax-review"
    UNEXPLAINED = "unexplained"
    BELOW_MATERIALITY = "below-materiality"


def rupee_line_for(error_class: ErrorClass, state: State) -> RupeeLine:
    """The rupee line is a pure function of (class-bucket, state), never a
    hand-maintained parallel taxonomy (design doc, "Rupee partition").

    Below-materiality is decided before a finding is queued (``is_material``)
    and therefore never reaches this function. Combinations the ladder cannot
    produce raise, so a bug upstream fails loudly instead of landing in the
    wrong line.
    """
    bucket = CLASS_BUCKET[error_class]
    if bucket is ClassBucket.TAX_REVIEW:
        return RupeeLine.TAX_REVIEW
    if bucket is ClassBucket.UNEXPLAINED:
        if state is not State.UNEXPLAINED:
            raise ValueError(f"class 8 can only be UNEXPLAINED, got {state}")
        return RupeeLine.UNEXPLAINED
    match state:
        case State.CLAIM_READY:
            return RupeeLine.CLAIM_READY
        case State.BLOCKED:
            return RupeeLine.BLOCKED
        case State.NOT_CLAIMABLE:
            return RupeeLine.NOT_CLAIMABLE
        case _:
            raise ValueError(f"class {int(error_class)} cannot be {state}")


# --------------------------------------------------------------------------- #
# Settlement-line vocabulary (Amazon Settlement Flat File V2; D4)
# --------------------------------------------------------------------------- #


class TransactionType(StrEnum):
    """An open vocabulary (RS1 saw ``Order_Retrocharge`` in a real file), so
    ``OTHER`` is a real outcome and the raw string is kept on the line."""

    ORDER = "Order"
    REFUND = "Refund"
    CHARGEBACK_REFUND = "Chargeback Refund"
    ATOZ_REFUND = "A-to-z Guarantee Refund"
    ADJUSTMENT = "Adjustment"
    SERVICE_FEE = "ServiceFee"
    ORDER_RETROCHARGE = "Order_Retrocharge"
    TRANSFER = "Transfer"
    SAFET_REIMBURSEMENT = "SAFE-T Reimbursement"
    OTHER = "other"


class LineKind(StrEnum):
    """Canonical meaning of a (amount-type, amount-description) pair. The kind
    says what a line is; the transaction type says under which event it was
    posted, so a refund's commission reversal is (REFUND, COMMISSION, positive).
    """

    PRINCIPAL = "principal"
    ITEM_TAX = "item-tax"
    SHIPPING_CHARGE = "shipping-charge"
    SHIPPING_CHARGE_TAX = "shipping-charge-tax"
    COMMISSION = "commission"
    FIXED_CLOSING_FEE = "fixed-closing-fee"
    SHIPPING_FEE = "shipping-fee"
    FULFILMENT_FEE = "fulfilment-fee"
    STORAGE_FEE = "storage-fee"
    GIFT_WRAP = "gift-wrap"
    GOODWILL = "goodwill"
    RESTOCKING_FEE = "restocking-fee"
    MARKETPLACE_FACILITATOR_TAX = "marketplace-facilitator-tax"
    REFUND_ADMIN_FEE = "refund-admin-fee"
    TECHNOLOGY_FEE = "technology-fee"
    FEE_TAX = "fee-tax"
    PROMOTION = "promotion"
    TCS = "tcs"
    TDS = "tds"
    RESERVE = "reserve"
    SAFET_REIMBURSEMENT = "safe-t-reimbursement"
    UNCLASSIFIED = "unclassified"


#: Raw vocabulary the generator writes and the parser reads. The human-readable
#: table with per-row verification status is docs/specs/amazon-settlement-v2.md.
#: Rows marked there as ``verified: false`` may be corrected by the integrator
#: between waves; the LineKind enum is the stable seam.
LINE_VOCABULARY: Final[dict[tuple[str, str], LineKind]] = {
    ("ItemPrice", "Principal"): LineKind.PRINCIPAL,
    ("ItemPrice", "Tax"): LineKind.ITEM_TAX,
    ("ItemPrice", "Shipping"): LineKind.SHIPPING_CHARGE,
    ("ItemPrice", "ShippingTax"): LineKind.SHIPPING_CHARGE_TAX,
    ("ItemPrice", "GiftWrap"): LineKind.GIFT_WRAP,
    ("ItemPrice", "Goodwill"): LineKind.GOODWILL,
    ("ItemPrice", "RestockingFee"): LineKind.RESTOCKING_FEE,
    ("ItemFees", "Commission"): LineKind.COMMISSION,
    ("ItemFees", "FixedClosingFee"): LineKind.FIXED_CLOSING_FEE,
    ("ItemFees", "ShippingChargeback"): LineKind.SHIPPING_FEE,
    ("ItemFees", "RefundCommission"): LineKind.REFUND_ADMIN_FEE,
    ("ItemFees", "FBAPerUnitFulfillmentFee"): LineKind.FULFILMENT_FEE,
    ("ItemFees", "FBAWeightBasedFee"): LineKind.FULFILMENT_FEE,
    ("ItemFees", "FBAPerOrderFulfillmentFee"): LineKind.FULFILMENT_FEE,
    ("ItemFees", "GiftwrapChargeback"): LineKind.GIFT_WRAP,
    ("ItemFees", "StorageFee"): LineKind.STORAGE_FEE,
    ("ItemFees", "LongTermStorageFee"): LineKind.STORAGE_FEE,
    ("ItemFees", "TechnologyFee"): LineKind.TECHNOLOGY_FEE,
    ("ItemFees", "TaxOnFees"): LineKind.FEE_TAX,
    ("ItemWithheldTax", "TCS-CGST"): LineKind.TCS,
    ("ItemWithheldTax", "TCS-SGST"): LineKind.TCS,
    ("ItemWithheldTax", "TCS-IGST"): LineKind.TCS,
    ("ItemWithheldTax", "TDS (Section 194-O)"): LineKind.TDS,
    (
        "ItemWithheldTax",
        "MarketplaceFacilitatorTax-Principal",
    ): LineKind.MARKETPLACE_FACILITATOR_TAX,
    ("ItemWithheldTax", "MarketplaceFacilitatorTax-Shipping"): LineKind.MARKETPLACE_FACILITATOR_TAX,
    ("other-transaction", "Current Reserve Amount"): LineKind.RESERVE,
    ("other-transaction", "Previous Reserve Amount Balance"): LineKind.RESERVE,
    ("other-transaction", "SAFE-T Reimbursement"): LineKind.SAFET_REIMBURSEMENT,
}

#: amount-types whose every description maps to one kind.
AMOUNT_TYPE_VOCABULARY: Final[dict[str, LineKind]] = {
    "Promotion": LineKind.PROMOTION,
}

TRANSACTION_VOCABULARY: Final[dict[str, TransactionType]] = {
    t.value: t for t in TransactionType if t is not TransactionType.OTHER
}

# Sources disagree on casing (`Other-Transaction` vs `other-transaction`, RS1),
# so every lookup case-folds. The tables above keep the canonical spelling the
# generator writes.
_LINE_LOOKUP: Final[dict[tuple[str, str], LineKind]] = {
    (t.casefold(), d.casefold()): k for (t, d), k in LINE_VOCABULARY.items()
}
_AMOUNT_TYPE_LOOKUP: Final[dict[str, LineKind]] = {
    t.casefold(): k for t, k in AMOUNT_TYPE_VOCABULARY.items()
}
_TRANSACTION_LOOKUP: Final[dict[str, TransactionType]] = {
    s.casefold(): t for s, t in TRANSACTION_VOCABULARY.items()
}


def classify_line(amount_type: str, amount_description: str) -> LineKind:
    """Exact pair first, then amount-type wildcard, else UNCLASSIFIED (D4).
    Unknown codes are never dropped; above the floor they become class 8."""
    kind = _LINE_LOOKUP.get((amount_type.strip().casefold(), amount_description.strip().casefold()))
    if kind is not None:
        return kind
    return _AMOUNT_TYPE_LOOKUP.get(amount_type.strip().casefold(), LineKind.UNCLASSIFIED)


def classify_transaction(transaction_type: str) -> TransactionType:
    """Open vocabulary: unknown values are OTHER, and the caller keeps the raw
    string on the line (``types.SettlementLine.transaction_type_raw``)."""
    return _TRANSACTION_LOOKUP.get(transaction_type.strip().casefold(), TransactionType.OTHER)


# --------------------------------------------------------------------------- #
# Category identifiers (D17 coverage) pinned to one Amazon.in fee-category node
# --------------------------------------------------------------------------- #

#: The three identifiers the generator tags orders with and the rate card
#: declares coverage for, each pinned to exactly one Amazon.in fee-category
#: node (RS3 §1: "home-kitchen" and "apparel" are umbrellas of a dozen nodes
#: each, so an unpinned identifier would make the coverage declaration false).
#: Node names only; every rate lives in ratecard/ and generator/ separately.
CATEGORY_NODES: Final[dict[str, str]] = {
    "electronics-accessories": "Accessories - Electronics, PC and Wireless",
    "home-kitchen": "Kitchen - Cookware, Tableware & Dinnerware",
    "apparel": "Apparel - Shirts",
}


# --------------------------------------------------------------------------- #
# Ground-truth freeze (D12)
# --------------------------------------------------------------------------- #

#: Path of the claimability labels file, relative to the repository root.
LABELS_FILE: Final[str] = "src/leakproof/labels/claimability.json"

#: SHA-256 of ``LABELS_FILE`` at the freeze. ``None`` until lane F merges and the
#: integrator freezes the labels at the Wave 1 close. Once set, a test fails if
#: the file changes without the ADR-0003 amendment procedure.
FROZEN_LABELS_SHA256: Final[str | None] = None
