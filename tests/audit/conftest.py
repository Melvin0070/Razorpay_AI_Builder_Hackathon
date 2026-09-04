"""Shared helper for tests/audit/: build an AuditEntry with sane defaults so
each test only spells out the fields it cares about."""

from __future__ import annotations

from datetime import date

from leakproof.audit import AuditLog
from leakproof.contract import AuditAction
from leakproof.types import AuditEntry

DEFAULT_AS_OF = date(2026, 8, 21)


def append_sample(log: AuditLog, ts: str, **overrides: object) -> AuditEntry:
    kwargs: dict[str, object] = dict(
        ts=ts,
        as_of=DEFAULT_AS_OF,
        actor="system",
        action=AuditAction.INGEST,
        exception_id=None,
        state_before=None,
        state_after=None,
        amount_paise=None,
        artifact_path=None,
    )
    kwargs.update(overrides)
    return log.append(**kwargs)  # type: ignore[arg-type]
