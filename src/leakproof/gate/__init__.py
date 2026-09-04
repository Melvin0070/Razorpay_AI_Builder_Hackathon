"""Human gate: approve, override, reject, flag → claim pack. Lane O · Tier B · issue #18.

Governed by D8, D21, D16. Owns this package and, from Wave 4, dashboard/serve.py.
Pack is written first, audit entry second. Approve is idempotent.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from leakproof.audit import AuditLog
from leakproof.types import BatchReport, ClaimPack


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
    raise NotImplementedError("lane O, issue #18")


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
    raise NotImplementedError("lane O, issue #18")


def reject(
    exception_id: str, report: BatchReport, log: AuditLog, *, actor: str, ts: str, as_of: date
) -> None:
    raise NotImplementedError("lane O, issue #18")


def flag(
    exception_id: str, report: BatchReport, log: AuditLog, *, actor: str, ts: str, as_of: date
) -> None:
    raise NotImplementedError("lane O, issue #18")
