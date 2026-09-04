"""Hash-chained, append-only audit log. Lane E · Tier C · issue #8.

Governed by D21 and the D8 ordering rule (pack first, entry second). Owns
this package. Chain verification recomputes hashes, never compares bytes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from leakproof.contract import AuditAction, Paise, State
from leakproof.types import AuditEntry


@dataclass(frozen=True, slots=True)
class ChainVerification:
    ok: bool
    entries: int
    first_bad_seq: int | None
    detail: str


class AuditLog:
    def __init__(self, path: Path) -> None:
        self.path = path

    def append(
        self,
        *,
        ts: str,
        as_of: date,
        actor: str,
        action: AuditAction,
        exception_id: str | None,
        state_before: State | None,
        state_after: State | None,
        amount_paise: Paise | None,
        artifact_path: str | None,
    ) -> AuditEntry:
        raise NotImplementedError("lane E, issue #8")

    def entries(self) -> tuple[AuditEntry, ...]:
        raise NotImplementedError("lane E, issue #8")

    def head(self) -> AuditEntry | None:
        raise NotImplementedError("lane E, issue #8")


def verify_chain(path: Path) -> ChainVerification:
    raise NotImplementedError("lane E, issue #8")
