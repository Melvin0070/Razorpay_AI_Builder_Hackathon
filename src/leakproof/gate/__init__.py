"""Human gate: approve, override, reject, flag → claim pack. Lane O · Tier B · issue #18.

Governed by D8, D21, D16. Owns this package and, from Wave 4, dashboard/serve.py.
Pack is written first, audit entry second. Approve is idempotent.
"""

from __future__ import annotations

import csv
import io
import json
from datetime import date
from pathlib import Path

from leakproof.audit import AuditLog
from leakproof.contract import AuditAction, BlockerKind, NotClaimableReason, State
from leakproof.types import BatchReport, ClaimPack, TriagedFinding


def _item(report: BatchReport, exception_id: str) -> TriagedFinding:
    for item in report.queue:
        if item.finding.finding_id == exception_id:
            return item
    raise KeyError(f"unknown finding_id: {exception_id!r}")


def _existing_pack(out_dir: Path, exception_id: str) -> ClaimPack | None:
    path = out_dir / f"{exception_id.replace('|', '__')}.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return ClaimPack(**data)


def _csv_rows(item: TriagedFinding) -> tuple[str, str]:
    cited = io.StringIO()
    recomputed = io.StringIO()
    cw = csv.writer(cited)
    rw = csv.writer(recomputed)
    cw.writerow(("line_id",))
    for line_id in item.finding.source_line_ids:
        cw.writerow((line_id,))
    rw.writerow(("label", "amount_paise", "note"))
    for row in item.finding.recomputation:
        rw.writerow((row.label, row.amount_paise, row.note))
    return cited.getvalue(), recomputed.getvalue()


def override_label(item: TriagedFinding) -> str:
    """The closed six-case operator vocabulary from ADR-0007."""
    key = (item.state.state, item.state.blocker_kind or item.state.not_claimable_reason)
    labels = {
        (State.BLOCKED, BlockerKind.SELLER_ACTION): "DRAFT WITHOUT EVIDENCE",
        (State.BLOCKED, BlockerKind.TIMING): "DRAFT BEFORE WINDOW RESOLVES",
        (State.BLOCKED, BlockerKind.PROFESSIONAL_REVIEW): "DRAFT WITHOUT CA REVIEW",
        (
            State.NOT_CLAIMABLE,
            NotClaimableReason.EVIDENCE_UNOBTAINABLE,
        ): "DRAFT WITHOUT EVIDENCE THAT CANNOT EXIST",
        (State.NOT_CLAIMABLE, NotClaimableReason.RULE): "DRAFT DESPITE EXCLUSION",
        (State.NOT_CLAIMABLE, NotClaimableReason.WINDOW_EXPIRED): "DRAFT AFTER WINDOW CLOSED",
    }
    try:
        return labels[key]
    except KeyError as exc:
        raise ValueError(f"no override label for {key!r}") from exc


def _write_pack(
    item: TriagedFinding, out_dir: Path, log: AuditLog, *, overridden: bool
) -> ClaimPack:
    out_dir.mkdir(parents=True, exist_ok=True)
    existing = _existing_pack(out_dir, item.finding.finding_id)
    if existing is not None:
        return existing
    cited, recomputation = _csv_rows(item)
    pack = ClaimPack(
        item.finding.finding_id,
        str(out_dir / f"{item.finding.finding_id.replace('|', '__')}.json"),
        item.draft.rendered_text if item.draft else item.finding.basis,
        cited,
        recomputation,
        item.state.state,
        log.next_seq(),
        overridden,
    )
    Path(pack.path).write_text(
        json.dumps(
            pack.__dict__
            if hasattr(pack, "__dict__")
            else {
                "exception_id": pack.exception_id,
                "path": pack.path,
                "claim_text": pack.claim_text,
                "cited_rows_csv": pack.cited_rows_csv,
                "recomputation_csv": pack.recomputation_csv,
                "state_before": pack.state_before.value,
                "audit_seq": pack.audit_seq,
                "overridden": pack.overridden,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return pack


def _append(
    item: TriagedFinding,
    log: AuditLog,
    *,
    action: AuditAction,
    actor: str,
    ts: str,
    as_of: date,
    artifact: str | None = None,
) -> None:
    log.append(
        ts=ts,
        as_of=as_of,
        actor=actor,
        action=action,
        exception_id=item.finding.finding_id,
        state_before=item.state.state,
        state_after=item.state.state,
        amount_paise=item.finding.amount_paise,
        artifact_path=artifact,
    )


def approve(
    exception_id: str,
    report: BatchReport,
    log: AuditLog,
    out_dir: Path,
    *,
    actor: str,
    ts: str,
    as_of: date,
) -> ClaimPack:
    item = _item(report, exception_id)
    if item.state.state is not State.CLAIM_READY:
        raise ValueError("non-claim-ready exceptions require override")
    pack = _write_pack(item, out_dir, log, overridden=False)
    # Existing artifact means a prior successful approval; never duplicate audit.
    if pack.audit_seq == log.next_seq():
        _append(
            item,
            log,
            action=AuditAction.APPROVE,
            actor=actor,
            ts=ts,
            as_of=as_of,
            artifact=Path(pack.path).name,
        )
    return pack


def override(
    exception_id: str,
    report: BatchReport,
    log: AuditLog,
    out_dir: Path,
    *,
    actor: str,
    ts: str,
    as_of: date,
) -> ClaimPack:
    item = _item(report, exception_id)
    if item.state.state is State.CLAIM_READY:
        raise ValueError("claim-ready exceptions must be approved, not overridden")
    override_label(item)
    pack = _write_pack(item, out_dir, log, overridden=True)
    if pack.audit_seq == log.next_seq():
        _append(
            item,
            log,
            action=AuditAction.APPROVE_OVERRIDE,
            actor=actor,
            ts=ts,
            as_of=as_of,
            artifact=Path(pack.path).name,
        )
    return pack


def reject(
    exception_id: str, report: BatchReport, log: AuditLog, *, actor: str, ts: str, as_of: date
) -> None:
    item = _item(report, exception_id)
    _append(item, log, action=AuditAction.REJECT, actor=actor, ts=ts, as_of=as_of)


def flag(
    exception_id: str, report: BatchReport, log: AuditLog, *, actor: str, ts: str, as_of: date
) -> None:
    item = _item(report, exception_id)
    if item.state.state is not State.UNEXPLAINED:
        raise ValueError("only unexplained deductions can be flagged")
    _append(item, log, action=AuditAction.FLAG, actor=actor, ts=ts, as_of=as_of)
