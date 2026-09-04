"""Seeded-error scenario vocabulary. Integrator-owned, frozen per wave.

IDs only. What a scenario *means* for claimability lives in ``labels/`` (lane
F, frozen); how it is *seeded* lives in ``generator/`` (lane B); which rule
*decides* it lives in ``evidence/`` (lane K); how it is *scored* lives in
``metrics/`` (lane N). Four lanes, one vocabulary, no shared numbers.

``expected_class`` is detection ground truth (which detector should fire), not
a claimability label. ``None`` means no detector should fire.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from leakproof.contract import ErrorClass


class ScenarioKind(StrEnum):
    SEEDED_ERROR = "seeded-error"  # a detector should fire; carries an expected amount
    TRUE_NEGATIVE = "true-negative"  # looks like an error, is not; nothing should fire
    DISPOSITION = "disposition"  # row lands outside every rupee line
    BANK = "bank"  # exercises the payout ↔ UTR leg only
    CONFIG_FIXTURE = "config-fixture"  # exists only in a test that must fail verify


class Scenario(StrEnum):
    # class 1 — commission overcharge
    C1_PLAIN = "C1_PLAIN"
    C1_WINDOW_EXPIRED = "C1_WINDOW_EXPIRED"
    C1_WINDOW_DATE_MISSING = "C1_WINDOW_DATE_MISSING"
    C1_GST_UNREGISTERED = "C1_GST_UNREGISTERED"
    C1_ATOZ_EXCLUDED = "C1_ATOZ_EXCLUDED"
    C1_SELLER_REFUND_EXCLUDED = "C1_SELLER_REFUND_EXCLUDED"
    C1_INVOICE_PENDING = "C1_INVOICE_PENDING"
    # class 2 — fixed / closing fee
    C2_PLAIN = "C2_PLAIN"
    C2_SLAB_BOUNDARY = "C2_SLAB_BOUNDARY"
    # class 5 — refund without fee reversal
    C5_PLAIN = "C5_PLAIN"
    C5_AWAITING_CYCLE = "C5_AWAITING_CYCLE"
    C5_SELLER_ISSUED = "C5_SELLER_ISSUED"
    C5_ATOZ = "C5_ATOZ"
    C5_REVERSED_LATER_CYCLE = "C5_REVERSED_LATER_CYCLE"
    # class 6 — unpaid order past cycle
    C6_PLAIN = "C6_PLAIN"
    C6_PAID_LATER_CYCLE = "C6_PAID_LATER_CYCLE"
    C6_OUT_OF_WINDOW = "C6_OUT_OF_WINDOW"
    # class 7 — tax
    C7_TCS_MISMATCH = "C7_TCS_MISMATCH"
    C7_TDS_MISMATCH = "C7_TDS_MISMATCH"
    # class 8 — unexplained
    C8_CODE_UNSEEN = "C8_CODE_UNSEEN"
    C8_CODE_KNOWN_NO_RULE = "C8_CODE_KNOWN_NO_RULE"
    # outside every class
    BELOW_MATERIALITY = "BELOW_MATERIALITY"
    QUARANTINE_MALFORMED = "QUARANTINE_MALFORMED"
    UNCOVERED_CATEGORY = "UNCOVERED_CATEGORY"
    DUPLICATE_UTR = "DUPLICATE_UTR"
    CONFIG_ERROR = "CONFIG_ERROR"


@dataclass(frozen=True, slots=True)
class ScenarioMeta:
    kind: ScenarioKind
    expected_class: ErrorClass | None
    description: str


_C = ErrorClass
_K = ScenarioKind

SCENARIOS: Final[dict[Scenario, ScenarioMeta]] = {
    Scenario.C1_PLAIN: ScenarioMeta(
        _K.SEEDED_ERROR,
        _C.COMMISSION_OVERCHARGE,
        "Commission charged above the rate-card percentage; every evidence item satisfiable.",
    ),
    Scenario.C1_WINDOW_EXPIRED: ScenarioMeta(
        _K.SEEDED_ERROR,
        _C.COMMISSION_OVERCHARGE,
        "Commission overcharge whose SAFE-T filing window has already closed at as_of.",
    ),
    Scenario.C1_WINDOW_DATE_MISSING: ScenarioMeta(
        _K.SEEDED_ERROR,
        _C.COMMISSION_OVERCHARGE,
        "Commission overcharge where the window's start date cannot be read from any line.",
    ),
    Scenario.C1_GST_UNREGISTERED: ScenarioMeta(
        _K.SEEDED_ERROR,
        _C.COMMISSION_OVERCHARGE,
        "Commission overcharge on a seller whose profile says not GST-registered; the tax invoice can never exist.",
    ),
    Scenario.C1_ATOZ_EXCLUDED: ScenarioMeta(
        _K.SEEDED_ERROR,
        _C.COMMISSION_OVERCHARGE,
        "Commission overcharge on an order that later carried an A-to-z Guarantee refund.",
    ),
    Scenario.C1_SELLER_REFUND_EXCLUDED: ScenarioMeta(
        _K.SEEDED_ERROR,
        _C.COMMISSION_OVERCHARGE,
        "Commission overcharge on an order the seller refunded themselves.",
    ),
    Scenario.C1_INVOICE_PENDING: ScenarioMeta(
        _K.SEEDED_ERROR,
        _C.COMMISSION_OVERCHARGE,
        "Commission overcharge on a GST-registered seller who has not yet supplied the tax invoice.",
    ),
    Scenario.C2_PLAIN: ScenarioMeta(
        _K.SEEDED_ERROR,
        _C.FIXED_FEE_ERROR,
        "Fixed closing fee charged from the wrong slab.",
    ),
    Scenario.C2_SLAB_BOUNDARY: ScenarioMeta(
        _K.SEEDED_ERROR,
        _C.FIXED_FEE_ERROR,
        "Closing fee error on an order priced exactly at a slab boundary.",
    ),
    Scenario.C5_PLAIN: ScenarioMeta(
        _K.SEEDED_ERROR,
        _C.REFUND_NO_FEE_REVERSAL,
        "Refund settled at least one full cycle ago with no commission reversal line since.",
    ),
    Scenario.C5_AWAITING_CYCLE: ScenarioMeta(
        _K.SEEDED_ERROR,
        _C.REFUND_NO_FEE_REVERSAL,
        "Refund settled less than one full cycle before the batch's max settlement date.",
    ),
    Scenario.C5_SELLER_ISSUED: ScenarioMeta(
        _K.SEEDED_ERROR,
        _C.REFUND_NO_FEE_REVERSAL,
        "Missing fee reversal on a refund the seller issued themselves.",
    ),
    Scenario.C5_ATOZ: ScenarioMeta(
        _K.SEEDED_ERROR,
        _C.REFUND_NO_FEE_REVERSAL,
        "Missing fee reversal on an A-to-z Guarantee refund.",
    ),
    Scenario.C5_REVERSED_LATER_CYCLE: ScenarioMeta(
        _K.TRUE_NEGATIVE,
        None,
        "Refund in one cycle, commission reversal in a later cycle inside the batch. Nothing should fire.",
    ),
    Scenario.C6_PLAIN: ScenarioMeta(
        _K.SEEDED_ERROR,
        _C.UNPAID_PAST_CYCLE,
        "Delivered order absent from every settlement more than two cycles after delivery.",
    ),
    Scenario.C6_PAID_LATER_CYCLE: ScenarioMeta(
        _K.TRUE_NEGATIVE,
        None,
        "Delivered order paid in a later cycle inside the batch. Nothing should fire.",
    ),
    Scenario.C6_OUT_OF_WINDOW: ScenarioMeta(
        _K.DISPOSITION,
        None,
        "Delivered order whose delivery date falls outside the batch's declared cycle coverage.",
    ),
    Scenario.C7_TCS_MISMATCH: ScenarioMeta(
        _K.SEEDED_ERROR,
        _C.TAX_MISMATCH,
        "TCS withheld differs from the simplified Section 52 recompute.",
    ),
    Scenario.C7_TDS_MISMATCH: ScenarioMeta(
        _K.SEEDED_ERROR,
        _C.TAX_MISMATCH,
        "TDS withheld differs from the simplified Section 194-O recompute.",
    ),
    Scenario.C8_CODE_UNSEEN: ScenarioMeta(
        _K.SEEDED_ERROR,
        _C.UNEXPLAINED_DEDUCTION,
        "Deduction under an amount-description not in the vocabulary.",
    ),
    Scenario.C8_CODE_KNOWN_NO_RULE: ScenarioMeta(
        _K.SEEDED_ERROR,
        _C.UNEXPLAINED_DEDUCTION,
        "Deduction under a known code for which the rate card declares neither a rule nor an acknowledgement.",
    ),
    Scenario.BELOW_MATERIALITY: ScenarioMeta(
        _K.DISPOSITION,
        None,
        "Discrepancy below the ten-rupee floor; aggregated, counted, never queued.",
    ),
    Scenario.QUARANTINE_MALFORMED: ScenarioMeta(
        _K.DISPOSITION,
        None,
        "Malformed row; quarantined with a reason and kept in the match-rate denominator.",
    ),
    Scenario.UNCOVERED_CATEGORY: ScenarioMeta(
        _K.DISPOSITION,
        None,
        "Order in a category outside the rate card's declared coverage.",
    ),
    Scenario.DUPLICATE_UTR: ScenarioMeta(
        _K.BANK,
        None,
        "Two bank credits of the same amount on the same day; only one may satisfy a payout.",
    ),
    Scenario.CONFIG_ERROR: ScenarioMeta(
        _K.CONFIG_FIXTURE,
        None,
        "Lookup miss inside declared coverage. Exists only in a test asserting that verify fails.",
    ),
}

SEEDED_ERROR_SCENARIOS: Final[tuple[Scenario, ...]] = tuple(
    s for s, m in SCENARIOS.items() if m.kind is ScenarioKind.SEEDED_ERROR
)


def scenarios_for_class(error_class: ErrorClass) -> tuple[Scenario, ...]:
    return tuple(s for s, m in SCENARIOS.items() if m.expected_class is error_class)
