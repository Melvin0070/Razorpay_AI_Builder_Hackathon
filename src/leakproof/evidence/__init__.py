"""Eligibility rules, evidence requirements, deadline arithmetic. Lane K · Tier A · issue #14.

Governed by D14, D18 and the inputs of precedence steps 1–5. Owns this
package. Must not read labels/ (D12 wall; a different agent from lane F).
"""

from __future__ import annotations

from datetime import date

from leakproof.contract import (
    EvidenceSource,
    EvidenceStatus,
    Mechanism,
    RefundInitiator,
    WindowStatus,
)
from leakproof.types import (
    Assessment,
    Citation,
    Deadline,
    EligibilityCheck,
    EvidenceItem,
    EvidenceParse,
    Finding,
    FoldedOrder,
    SellerProfile,
)

_CITATION = Citation(
    "SAFE-T policy research",
    "https://sellercentral.amazon.in/help/hub/reference/G202031970",
    date(2026, 9, 5),
    False,
)


def assess(
    finding: Finding,
    folded: FoldedOrder,
    profile: SellerProfile,
    as_of: date,
    *,
    evidence_supply: EvidenceParse | None = None,
    cycle_days: int = 7,
) -> Assessment:
    eligibility = []
    evidence = []
    if finding.mechanism is Mechanism.SAFE_T:
        order = folded.order
        atoz = any(x.txn_type.value == "A-to-z Guarantee Refund" for x in folded.lines)
        seller = bool(order and order.refund_initiated_by is RefundInitiator.SELLER)
        eligibility.extend(
            (
                EligibilityCheck(
                    "safe-t-a-to-z", "A-to-Z refunds are excluded from SAFE-T", not atoz, _CITATION
                ),
                EligibilityCheck(
                    "safe-t-seller-refund",
                    "seller-issued refunds are excluded from SAFE-T",
                    not seller,
                    _CITATION,
                ),
            )
        )
        status = (
            EvidenceStatus.PENDING
            if finding.event_date and (as_of - finding.event_date).days < cycle_days
            else EvidenceStatus.MISSING
        )
        requirement = "Tax invoice for the returned item"
        invoice_status = EvidenceStatus.MISSING
        invoice_note = "seller assertion not supplied"
        if evidence_supply is not None:
            supplied = next(
                (
                    x
                    for x in evidence_supply.supplies
                    if x.order_id == finding.order_id and x.requirement == requirement
                ),
                None,
            )
            if supplied is not None:
                invoice_status = supplied.status
                invoice_note = f"seller assertion from {supplied.source_line_id}"
        evidence.extend(
            (
                EvidenceItem(
                    requirement,
                    EvidenceSource.SELLER_SUPPLIABLE,
                    invoice_status,
                    note=invoice_note,
                ),
                EvidenceItem(
                    "Settlement refund row",
                    EvidenceSource.REPORT_DERIVABLE,
                    EvidenceStatus.SATISFIED,
                    finding.source_line_ids,
                ),
            )
        )
        evidence.append(
            EvidenceItem("Commission reversal for refund", EvidenceSource.REPORT_DERIVABLE, status)
        )
    return Assessment(
        finding.finding_id,
        tuple(eligibility),
        tuple(evidence),
        deadline_for(finding.mechanism, finding.event_date, as_of),
    )


def deadline_for(mechanism: Mechanism, event_date: date | None, as_of: date) -> Deadline:
    if mechanism is not Mechanism.SAFE_T:
        return Deadline(mechanism, WindowStatus.NOT_APPLICABLE)
    if event_date is None:
        return Deadline(mechanism, WindowStatus.START_DATE_MISSING, 15, citation=_CITATION)
    expires = event_date.fromordinal(event_date.toordinal() + 15)
    left = (expires - as_of).days
    return Deadline(
        mechanism,
        WindowStatus.OPEN if left >= 0 else WindowStatus.EXPIRED,
        15,
        event_date,
        expires,
        left,
        _CITATION,
    )
