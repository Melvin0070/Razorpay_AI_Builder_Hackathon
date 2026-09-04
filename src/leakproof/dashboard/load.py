"""JSON -> ``BatchReport``. The mirror image of ``leakproof.serialize.to_jsonable``,
which is forward-only (dataclass -> JSON) by design, so this loader lives here
rather than in the frozen ``serialize.py``.

Needed only by ``serve.py``: ``create_app(report_path)`` reads a report off
disk (the committed demo fixture until the pipeline exists, or a future
``make triage`` artifact) and needs a real ``BatchReport`` to hand to
``render(..., mode="served")``.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from leakproof.contract import (
    AuditAction,
    BlockerKind,
    ErrorClass,
    EvidenceSource,
    EvidenceStatus,
    LineKind,
    Mechanism,
    NotClaimableReason,
    RupeeLine,
    State,
    UnexplainedBasis,
    WindowStatus,
)
from leakproof.types import (
    Assessment,
    BankLegResult,
    BatchReport,
    Citation,
    CoverageDeclaration,
    CoverageWindow,
    Deadline,
    DispositionCounts,
    Draft,
    EligibilityCheck,
    EvidenceItem,
    Finding,
    GateRecord,
    MatchRates,
    QuarantinedRow,
    RecomputationRow,
    RupeeLines,
    StateResult,
    TriagedFinding,
)


def _d(value: str | None) -> date | None:
    return date.fromisoformat(value) if value is not None else None


def _citation(d: dict[str, Any] | None) -> Citation | None:
    if d is None:
        return None
    return Citation(label=d["label"], url=d["url"], as_of=_d(d["as_of"]), verified=d["verified"])


def _quarantined_row(d: dict[str, Any]) -> QuarantinedRow:
    return QuarantinedRow(line_id=d["line_id"], reason=d["reason"])


def _recomputation_row(d: dict[str, Any]) -> RecomputationRow:
    return RecomputationRow(label=d["label"], amount_paise=d["amount_paise"], note=d["note"])


def _finding(d: dict[str, Any]) -> Finding:
    return Finding(
        error_class=ErrorClass(d["error_class"]),
        order_id=d["order_id"],
        source_line_ids=tuple(d["source_line_ids"]),
        claimed_line_id=d["claimed_line_id"],
        amount_paise=d["amount_paise"],
        mechanism=Mechanism(d["mechanism"]),
        basis=d["basis"],
        recomputation=tuple(_recomputation_row(r) for r in d["recomputation"]),
        unexplained_basis=(
            UnexplainedBasis(d["unexplained_basis"]) if d["unexplained_basis"] is not None else None
        ),
        event_date=_d(d["event_date"]),
        category_id=d["category_id"],
        sku=d["sku"],
    )


def _eligibility_check(d: dict[str, Any]) -> EligibilityCheck:
    return EligibilityCheck(
        rule_id=d["rule_id"],
        description=d["description"],
        passed=d["passed"],
        citation=_citation(d["citation"]),
    )


def _evidence_item(d: dict[str, Any]) -> EvidenceItem:
    return EvidenceItem(
        requirement=d["requirement"],
        source=EvidenceSource(d["source"]),
        status=EvidenceStatus(d["status"]),
        source_line_ids=tuple(d["source_line_ids"]),
        note=d["note"],
    )


def _deadline(d: dict[str, Any]) -> Deadline:
    return Deadline(
        mechanism=Mechanism(d["mechanism"]),
        status=WindowStatus(d["status"]),
        window_days=d["window_days"],
        starts_on=_d(d["starts_on"]),
        expires_on=_d(d["expires_on"]),
        days_left=d["days_left"],
        citation=_citation(d["citation"]),
    )


def _assessment(d: dict[str, Any]) -> Assessment:
    return Assessment(
        finding_id=d["finding_id"],
        eligibility=tuple(_eligibility_check(e) for e in d["eligibility"]),
        evidence=tuple(_evidence_item(e) for e in d["evidence"]),
        deadline=_deadline(d["deadline"]),
    )


def _state_result(d: dict[str, Any]) -> StateResult:
    return StateResult(
        finding_id=d["finding_id"],
        state=State(d["state"]),
        precedence_step=d["precedence_step"],
        reason=d["reason"],
        rupee_line=RupeeLine(d["rupee_line"]),
        blocker_kind=BlockerKind(d["blocker_kind"]) if d["blocker_kind"] is not None else None,
        not_claimable_reason=(
            NotClaimableReason(d["not_claimable_reason"])
            if d["not_claimable_reason"] is not None
            else None
        ),
    )


def _draft(d: dict[str, Any] | None) -> Draft | None:
    if d is None:
        return None
    return Draft(
        finding_id=d["finding_id"],
        template_text=d["template_text"],
        rendered_text=d["rendered_text"],
        magnitude=d["magnitude"],
        model=d["model"],
        model_version=d["model_version"],
        placeholders=tuple(d["placeholders"]),
    )


def _gate_record(d: dict[str, Any] | None) -> GateRecord | None:
    if d is None:
        return None
    return GateRecord(
        action=AuditAction(d["action"]),
        audit_seq=d["audit_seq"],
        state_before=State(d["state_before"]),
        artifact_path=d["artifact_path"],
        overridden=d["overridden"],
    )


def _triaged_finding(d: dict[str, Any]) -> TriagedFinding:
    return TriagedFinding(
        finding=_finding(d["finding"]),
        assessment=_assessment(d["assessment"]),
        state=_state_result(d["state"]),
        draft=_draft(d["draft"]),
        gate=_gate_record(d["gate"]),
    )


def _rupee_lines(d: dict[str, Any]) -> RupeeLines:
    return RupeeLines(
        claim_ready=d["claim_ready"],
        blocked=d["blocked"],
        not_claimable=d["not_claimable"],
        tax_review=d["tax_review"],
        unexplained=d["unexplained"],
        below_materiality=d["below_materiality"],
        not_claimable_rule=d["not_claimable_rule"],
        not_claimable_window_expired=d["not_claimable_window_expired"],
        not_claimable_evidence_unobtainable=d["not_claimable_evidence_unobtainable"],
        claim_ready_count=d["claim_ready_count"],
        blocked_count=d["blocked_count"],
        not_claimable_count=d["not_claimable_count"],
        tax_review_count=d["tax_review_count"],
        unexplained_count=d["unexplained_count"],
        below_materiality_rows=d["below_materiality_rows"],
    )


def _match_rates(d: dict[str, Any]) -> MatchRates:
    return MatchRates(
        total_orders=d["total_orders"],
        matched=d["matched"],
        class6_flagged=d["class6_flagged"],
        quarantined_rows=d["quarantined_rows"],
    )


def _disposition_counts(d: dict[str, Any]) -> DispositionCounts:
    return DispositionCounts(
        quarantine=d["quarantine"],
        uncovered=d["uncovered"],
        out_of_window=d["out_of_window"],
        config_error=d["config_error"],
        quarantine_reasons=tuple(_quarantined_row(q) for q in d["quarantine_reasons"]),
        hint=d["hint"],
    )


def _coverage_declaration(d: dict[str, Any]) -> CoverageDeclaration:
    return CoverageDeclaration(
        categories=tuple(d["categories"]),
        valid_from=_d(d["valid_from"]),
        valid_to=_d(d["valid_to"]),
        audited_kinds=tuple(LineKind(k) for k in d["audited_kinds"]),
        acknowledged_kinds=tuple(LineKind(k) for k in d["acknowledged_kinds"]),
    )


def _coverage_window(d: dict[str, Any]) -> CoverageWindow:
    return CoverageWindow(start=_d(d["start"]), end=_d(d["end"]))


def _bank_leg(d: dict[str, Any] | None) -> BankLegResult | None:
    if d is None:
        return None
    return BankLegResult(
        payouts=d["payouts"],
        matched=d["matched"],
        unmatched_settlement_ids=tuple(d["unmatched_settlement_ids"]),
        duplicate_credit_utrs=tuple(d["duplicate_credit_utrs"]),
    )


def report_from_jsonable(d: dict[str, Any]) -> BatchReport:
    """Reconstruct a ``BatchReport`` from ``leakproof.serialize.to_jsonable``
    output (derived fields such as ``rupee_lines.identified`` are recomputed
    by the dataclass properties, not read back)."""
    return BatchReport(
        batch_id=d["batch_id"],
        marketplace=d["marketplace"],
        as_of=_d(d["as_of"]),
        cycle_days=d["cycle_days"],
        coverage=_coverage_window(d["coverage"]),
        settlement_ids=tuple(d["settlement_ids"]),
        order_count=d["order_count"],
        rupee_lines=_rupee_lines(d["rupee_lines"]),
        match_rates=_match_rates(d["match_rates"]),
        dispositions=_disposition_counts(d["dispositions"]),
        rate_card_coverage=_coverage_declaration(d["rate_card_coverage"]),
        queue=tuple(_triaged_finding(q) for q in d["queue"]),
        generated_by=d["generated_by"],
        mode=d["mode"],
        schema_version=d["schema_version"],
        bank_leg=_bank_leg(d["bank_leg"]),
        audit_head_seq=d["audit_head_seq"],
        audit_head_hash=d["audit_head_hash"],
    )


def load_report(path: Path) -> BatchReport:
    return report_from_jsonable(json.loads(path.read_text(encoding="utf-8")))
