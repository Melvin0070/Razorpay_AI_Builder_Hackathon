"""Dedup, overlap matrix, precedence ladder, rupee partition, report. Lane L · Tier A · issue #15.

Governed by D19, D10, D3, D4, the seven-step state derivation and the rupee
partition. Owns this package. Hard gates (both additivity identities,
exactly-one-state, per-order sum invariant) register in gates.HARD_GATES.
"""

from __future__ import annotations

from dataclasses import replace

from leakproof.bankleg import reconcile_payouts
from leakproof.contract import (
    BlockerKind,
    EvidenceSource,
    EvidenceStatus,
    Mechanism,
    NotClaimableReason,
    RupeeLine,
    State,
    UnexplainedBasis,
    is_material,
)
from leakproof.detect import run_detectors
from leakproof.evidence import assess
from leakproof.ledger import fold_batch, match
from leakproof.types import (
    Assessment,
    BatchInputs,
    BatchReport,
    DetectorContext,
    DispositionCounts,
    Finding,
    RateCard,
    RupeeLines,
    StateResult,
    TriagedFinding,
)


def dedup(findings: list[Finding]) -> tuple[Finding, ...]:
    return tuple(
        {
            x.finding_id: x for x in sorted(findings, key=lambda x: (x.finding_id, -x.amount_paise))
        }.values()
    )


def derive_state(finding: Finding, assessment: Assessment) -> StateResult:
    if finding.mechanism is Mechanism.NONE:
        return StateResult(
            finding.finding_id,
            State.UNEXPLAINED,
            0,
            (finding.unexplained_basis or UnexplainedBasis.CODE_UNSEEN).value,
            RupeeLine.UNEXPLAINED,
        )
    if finding.mechanism is Mechanism.CA_REVIEW:
        return StateResult(
            finding.finding_id,
            State.BLOCKED,
            0,
            "CA review",
            RupeeLine.TAX_REVIEW,
            BlockerKind.PROFESSIONAL_REVIEW,
        )
    failed = next((x for x in assessment.eligibility if not x.passed), None)
    if failed:
        return StateResult(
            finding.finding_id,
            State.NOT_CLAIMABLE,
            1,
            failed.description,
            RupeeLine.NOT_CLAIMABLE,
            not_claimable_reason=NotClaimableReason.RULE,
        )
    if assessment.deadline.status.value == "expired":
        return StateResult(
            finding.finding_id,
            State.NOT_CLAIMABLE,
            2,
            "filing window expired",
            RupeeLine.NOT_CLAIMABLE,
            not_claimable_reason=NotClaimableReason.WINDOW_EXPIRED,
        )
    if assessment.deadline.status.value == "start-date-missing":
        return StateResult(
            finding.finding_id,
            State.BLOCKED,
            3,
            "window start date missing",
            RupeeLine.BLOCKED,
            BlockerKind.TIMING,
        )
    item = next((x for x in assessment.evidence if x.source is EvidenceSource.UNOBTAINABLE), None)
    if item:
        return StateResult(
            finding.finding_id,
            State.NOT_CLAIMABLE,
            4,
            item.requirement,
            RupeeLine.NOT_CLAIMABLE,
            not_claimable_reason=NotClaimableReason.EVIDENCE_UNOBTAINABLE,
        )
    item = next(
        (
            x
            for x in assessment.evidence
            if x.status in (EvidenceStatus.MISSING, EvidenceStatus.PENDING)
        ),
        None,
    )
    if item:
        return StateResult(
            finding.finding_id,
            State.BLOCKED,
            5,
            item.requirement,
            RupeeLine.BLOCKED,
            BlockerKind.TIMING
            if item.status is EvidenceStatus.PENDING
            else BlockerKind.SELLER_ACTION,
        )
    return StateResult(
        finding.finding_id,
        State.CLAIM_READY,
        6,
        "all eligibility and evidence requirements satisfied",
        RupeeLine.CLAIM_READY,
    )


def partition(
    queue: tuple[TriagedFinding, ...], below_materiality: tuple[Finding, ...]
) -> RupeeLines:
    vals = {
        x: 0
        for x in (
            "claim_ready",
            "blocked",
            "not_claimable",
            "tax_review",
            "unexplained",
            "below_materiality",
        )
    }
    counts = {
        x: 0
        for x in (
            "claim_ready",
            "blocked",
            "not_claimable",
            "tax_review",
            "unexplained",
            "below_materiality_rows",
        )
    }
    breakouts = {"rule": 0, "window": 0, "evidence": 0}
    for item in queue:
        key = item.state.rupee_line.value.replace("-", "_")
        vals[key] += item.finding.amount_paise
        counts[key if key != "below_materiality" else "below_materiality_rows"] += 1
        if item.state.not_claimable_reason is NotClaimableReason.RULE:
            breakouts["rule"] += item.finding.amount_paise
        elif item.state.not_claimable_reason is NotClaimableReason.WINDOW_EXPIRED:
            breakouts["window"] += item.finding.amount_paise
        elif item.state.not_claimable_reason is NotClaimableReason.EVIDENCE_UNOBTAINABLE:
            breakouts["evidence"] += item.finding.amount_paise
    vals["below_materiality"] = sum(x.amount_paise for x in below_materiality)
    counts["below_materiality_rows"] = len(below_materiality)
    return RupeeLines(
        claim_ready=vals["claim_ready"],
        blocked=vals["blocked"],
        not_claimable=vals["not_claimable"],
        tax_review=vals["tax_review"],
        unexplained=vals["unexplained"],
        below_materiality=vals["below_materiality"],
        not_claimable_rule=breakouts["rule"],
        not_claimable_window_expired=breakouts["window"],
        not_claimable_evidence_unobtainable=breakouts["evidence"],
        claim_ready_count=counts["claim_ready"],
        blocked_count=counts["blocked"],
        not_claimable_count=counts["not_claimable"],
        tax_review_count=counts["tax_review"],
        unexplained_count=counts["unexplained"],
        below_materiality_rows=counts["below_materiality_rows"],
    )


def run_batch(inputs: BatchInputs, rate_card: RateCard) -> BatchReport:
    folded = fold_batch(inputs)
    max_date = max(
        (x.posted_date for s in inputs.settlements for x in s.lines), default=inputs.as_of
    )
    findings = run_detectors(
        folded,
        DetectorContext(rate_card, inputs.profile, inputs.as_of, inputs.cycle_days, max_date),
    )
    by_id = {x.order_id: x for x in folded}
    material = [x for x in dedup(findings) if is_material(x.amount_paise)]
    below = tuple(x for x in findings if not is_material(x.amount_paise))
    queue = tuple(
        TriagedFinding(
            x,
            (
                a := assess(
                    x,
                    by_id[x.order_id],
                    inputs.profile,
                    inputs.as_of,
                    evidence_supply=inputs.evidence,
                    cycle_days=inputs.cycle_days,
                )
            ),
            derive_state(x, a),
        )
        for x in material
    )
    queue = tuple(
        sorted(
            queue,
            key=lambda x: (
                {
                    State.CLAIM_READY: 0,
                    State.BLOCKED: 1,
                    State.UNEXPLAINED: 2,
                    State.NOT_CLAIMABLE: 3,
                }[x.state.state],
                x.assessment.deadline.expires_on or inputs.as_of,
                -x.finding.amount_paise,
            ),
        )
    )
    m = match(inputs, folded, class6_flagged=sum(x.error_class.value == 6 for x in findings))
    qrows = inputs.orders.quarantined + tuple(y for s in inputs.settlements for y in s.quarantined)
    disp = DispositionCounts(len(qrows), 0, sum(not x.in_coverage for x in folded), 0, qrows)
    bank = (
        reconcile_payouts(
            tuple(s.header for s in inputs.settlements if s.header), inputs.bank.credits
        )
        if inputs.bank
        else None
    )
    return BatchReport(
        inputs.batch_id,
        inputs.marketplace,
        inputs.as_of,
        inputs.cycle_days,
        inputs.coverage,
        tuple(sorted({s.header.settlement_id for s in inputs.settlements if s.header})),
        len(inputs.orders.orders),
        partition(queue, below),
        m.rates,
        disp,
        rate_card.coverage(),
        queue,
        "leakproof",
        bank_leg=bank,
    )


def apply_drafts(report: BatchReport, drafts: dict[str, object]) -> BatchReport:
    """Return a second-pass report with persisted Draft values attached."""
    return replace(
        report,
        queue=tuple(
            replace(item, draft=drafts.get(item.finding.finding_id, item.draft))
            for item in report.queue
        ),
    )


def apply_gate(report: BatchReport, finding_id: str, gate_record: object) -> BatchReport:
    """Return a second-pass report with one human gate record attached."""
    found = False
    queue = []
    for item in report.queue:
        if item.finding.finding_id == finding_id:
            queue.append(replace(item, gate=gate_record))
            found = True
        else:
            queue.append(item)
    if not found:
        raise KeyError(f"unknown finding_id: {finding_id!r}")
    return replace(report, queue=tuple(queue))
