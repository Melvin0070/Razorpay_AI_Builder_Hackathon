"""Hash-chained, append-only audit log (D21). Lane E · Tier C · issue #8.

Governed by D21 and the D8 ordering rule (pack first, entry second). Owns
this package. Chain verification recomputes hashes, never compares bytes:
byte comparison against a golden log would fail on every rerun and break
D18's reproducibility guarantee (the same batch, run twice, produces entries
that agree on every *field* but differ in ``ts``).

Canonical JSON (the exact bytes that get hashed), so lane O and the metrics
harness can reproduce it independently rather than only through this module:

1. Take the entry, drop its own ``hash`` field.
2. Project every remaining field to a JSON-safe value (``_project`` below,
   owned by this module — NOT ``leakproof.serialize.to_jsonable``, whose
   docstring disclaims audit canonicalisation and whose derived-field table
   is keyed by dataclass class name, so a later change there must not be
   able to silently change a hash already committed to disk): enums by their
   ``.value`` string, ``datetime.date`` as ``.isoformat()``, everything else
   as-is.
3. ``json.dumps(obj, sort_keys=True, separators=(",", ":"),
   ensure_ascii=False)`` — sorted keys and no incidental whitespace so the
   same entry always serialises to the same bytes regardless of field
   insertion order.

Hash rule: ``sha256(canonical_json(entry - hash).encode("utf-8") +
prev_hash.encode("ascii")).hexdigest()``. Genesis ``prev_hash`` is 64 ``"0"``
characters. ``seq`` starts at 1 and increments by exactly one per entry.

Storage: one JSON object per physical line (JSONL) at ``AuditLog(path)``.
``append`` only ever opens the file in append mode, writes one line, flushes,
and fsyncs — it never reads the whole file back in to rewrite it, and never
truncates. Reopening an existing log (a fresh ``AuditLog`` instance pointing
at the same path) picks its next ``seq``/``prev_hash`` up from whatever is
on disk, so there is no in-memory state to lose between runs.

SECURITY.md is explicit that this makes the log tamper-*evident*, not
tamper-*proof*: anyone with write access to the file can rewrite an entry and
re-chain everything after it by hand. Verification catches an edit that was
NOT re-chained — the common case, and the one a hard gate can act on.

Malformed content (a truncated last line from an interrupted write, a garbage
line, a line missing a required key, a bad enum value) is a fact about the
file, not a bug in the caller: ``entries()``, ``head()`` and ``append()``
never let ``json.JSONDecodeError``/``KeyError``/``ValueError``/``TypeError``
escape from a bad line. They raise the single typed
:class:`AuditLogCorruptError` instead. ``verify_chain`` and
``audit_chain_gate`` in turn never raise on file content at all — a bad line
is reported as a normal, non-ok :class:`ChainVerification`/``GateResult``
naming the physical line and why, so a corrupt log fails the gate rather than
crashing ``make verify``.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Final

from leakproof.contract import AuditAction, Paise, State
from leakproof.gates import GateResult
from leakproof.types import AuditEntry

#: Genesis previous-hash: 64 zero characters, one per sha256 hex digit.
GENESIS_PREV_HASH: Final[str] = "0" * 64

#: Exceptions a malformed on-disk line can raise while being parsed back
#: into an AuditEntry: bad JSON, a missing field, a value of the wrong
#: shape for its field, or an enum string that names no member.
_PARSE_ERRORS: Final[tuple[type[Exception], ...]] = (
    json.JSONDecodeError,
    KeyError,
    ValueError,
    TypeError,
)


class AuditLogCorruptError(ValueError):
    """Raised by :meth:`AuditLog.entries`, :meth:`AuditLog.head` and
    :meth:`AuditLog.append` when a physical line in the on-disk log cannot be
    parsed back into an ``AuditEntry`` — bad JSON, a missing key, a value the
    wrong shape, or an enum string that names no member.

    The log is append-only and cannot be repaired in place: there is no
    "rewrite just this line" operation, because doing so without also
    re-chaining every entry after it is exactly the tampering the hash chain
    exists to catch. A corrupt line must be investigated (and, if it truly
    needs fixing, fixed by a human who understands the chain implications)
    before appending is safe to resume — ``append`` refuses to append past a
    line it cannot read, since it cannot otherwise determine the correct
    ``seq``/``prev_hash`` to continue from.
    """

    def __init__(self, line_no: int, reason: str) -> None:
        self.line_no = line_no
        self.reason = reason
        super().__init__(
            f"audit log corrupt at line {line_no}: {reason}. The log is "
            "append-only and cannot be repaired in place — investigate "
            "before appending continues."
        )


def _describe_parse_error(exc: Exception) -> str:
    """Turn one of ``_PARSE_ERRORS`` into a human-readable reason. KeyError's
    default ``str()`` is just the missing key's repr (e.g. ``'seq'``), which
    reads as a typo without context; every other error's message already
    names what was wrong."""
    if isinstance(exc, KeyError):
        return f"missing key {exc}"
    return str(exc)


def _project(entry: AuditEntry) -> dict[str, Any]:
    """The twelve-field, JSON-safe projection of ``entry`` (``hash``
    included — callers that need it excluded, i.e. ``canonical_json``, pop it
    themselves). Owned entirely by this module rather than delegating to
    ``leakproof.serialize.to_jsonable``: that function's docstring says audit
    canonicalisation is not its job, and its ``_DERIVED`` table injects extra
    keys by dataclass class name — an unrelated future change there would
    silently change every hash already committed to disk, and the chain
    verifier would then accuse the operator of tampering. Enums by
    ``.value``, ``date`` by ``.isoformat()``, everything else as-is."""
    return {
        "seq": entry.seq,
        "prev_hash": entry.prev_hash,
        "hash": entry.hash,
        "ts": entry.ts,
        "as_of": entry.as_of.isoformat(),
        "actor": entry.actor,
        "action": entry.action.value,
        "exception_id": entry.exception_id,
        "state_before": entry.state_before.value if entry.state_before is not None else None,
        "state_after": entry.state_after.value if entry.state_after is not None else None,
        "amount_paise": entry.amount_paise,
        "artifact_path": entry.artifact_path,
    }


def canonical_json(entry: AuditEntry) -> str:
    """The exact string that gets hashed for ``entry``: every field except
    ``hash`` itself, projected to JSON-safe values (see ``_project``) and
    dumped with sorted keys and no incidental whitespace. See the module
    docstring for why this exact recipe, and reproduce it exactly rather than
    approximating it."""
    payload = _project(entry)
    payload.pop("hash", None)
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def compute_hash(entry: AuditEntry, prev_hash: str) -> str:
    """``sha256(canonical_json(entry) + prev_hash)`` hex digest.

    ``entry.hash`` itself is never read here — ``canonical_json`` strips it —
    so callers building a not-yet-hashed entry may pass any placeholder
    (empty string is conventional) in that field.
    """
    digest = hashlib.sha256()
    digest.update(canonical_json(entry).encode("utf-8"))
    digest.update(prev_hash.encode("ascii"))
    return digest.hexdigest()


def _entry_line(entry: AuditEntry) -> str:
    """The JSONL storage line for an already-hashed ``entry``: same
    JSON-safe projection as ``canonical_json``, but keeping ``hash`` (this is
    what actually lands on disk) and sorted/compact for a stable, diffable
    file — not part of the hash rule itself."""
    return json.dumps(_project(entry), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _entry_from_dict(d: dict[str, Any]) -> AuditEntry:
    return AuditEntry(
        seq=d["seq"],
        prev_hash=d["prev_hash"],
        hash=d["hash"],
        ts=d["ts"],
        as_of=date.fromisoformat(d["as_of"]),
        actor=d["actor"],
        action=AuditAction(d["action"]),
        exception_id=d["exception_id"],
        state_before=State(d["state_before"]) if d["state_before"] is not None else None,
        state_after=State(d["state_after"]) if d["state_after"] is not None else None,
        amount_paise=d["amount_paise"],
        artifact_path=d["artifact_path"],
    )


def _resolve_artifact(artifacts_root: Path, artifact_path: str) -> tuple[Path | None, str | None]:
    """Resolve ``artifact_path`` under ``artifacts_root``, confining it
    there. SECURITY.md says claim packs are written under a fixed output
    directory from ids validated against the report before any path is
    formed — that is the argument for REJECTING a path that tries to point
    anywhere else (absolute, or escaping via ``..``), not for accepting one
    wherever it happens to point.

    Returns ``(resolved, None)`` on a path that is safely confined to
    ``artifacts_root`` (whether or not a file actually exists there yet —
    callers check that separately), or ``(None, reason)`` naming why the
    path itself is rejected outright, distinct from the file simply being
    missing (an orphan pack).
    """
    raw = Path(artifact_path)
    if raw.is_absolute():
        return None, "artifact_path must be relative to artifacts_root, not absolute"
    root = artifacts_root.resolve()
    resolved = (artifacts_root / raw).resolve()
    if resolved != root and root not in resolved.parents:
        return None, "artifact_path escapes artifacts_root"
    return resolved, None


@dataclass(frozen=True, slots=True)
class ChainVerification:
    ok: bool
    entries: int
    first_bad_seq: int | None
    detail: str


class AuditLog:
    """Append-only JSONL log at ``path``. Every method re-reads ``path`` from
    disk rather than caching — the file is the only state, which is what
    makes reopening a log (a new ``AuditLog(path)`` instance) pick up exactly
    where the last process left off."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

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
        head = self.head()
        seq = head.seq + 1 if head is not None else 1
        prev_hash = head.hash if head is not None else GENESIS_PREV_HASH
        # hash="" placeholder: compute_hash strips the hash field regardless
        # of what is passed here, so this is never read for hashing purposes.
        draft = AuditEntry(
            seq=seq,
            prev_hash=prev_hash,
            hash="",
            ts=ts,
            as_of=as_of,
            actor=actor,
            action=action,
            exception_id=exception_id,
            state_before=state_before,
            state_after=state_after,
            amount_paise=amount_paise,
            artifact_path=artifact_path,
        )
        entry = dataclasses.replace(draft, hash=compute_hash(draft, prev_hash))

        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Append-only: open in "a" mode only, never "w". Flush + fsync so a
        # crash right after this call cannot silently lose the entry.
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(_entry_line(entry) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        return entry

    def entries(self) -> tuple[AuditEntry, ...]:
        """Every entry, in file order. Raises :class:`AuditLogCorruptError`
        naming the exact physical line the moment a line fails to parse,
        rather than returning a partial result — a caller that wants the
        good entries before the break point should catch the error and read
        ``exc.line_no`` (``verify_chain`` does exactly this)."""
        if not self.path.exists():
            return ()
        out: list[AuditEntry] = []
        with self.path.open("r", encoding="utf-8") as fh:
            for line_no, raw_line in enumerate(fh, start=1):
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    out.append(_entry_from_dict(json.loads(line)))
                except _PARSE_ERRORS as exc:
                    raise AuditLogCorruptError(line_no, _describe_parse_error(exc)) from exc
        return tuple(out)

    def head(self) -> AuditEntry | None:
        es = self.entries()
        return es[-1] if es else None


def verify_chain(path: Path, artifacts_root: Path | None = None) -> ChainVerification:
    """Recompute every hash in ``path`` and check ``prev_hash``/``seq``
    linkage; never compares bytes to a stored or golden chain (see module
    docstring). Reports the first ``seq`` at which something is wrong and
    why. A missing file is a trivially-ok, zero-entry chain — there is
    nothing to have gone wrong yet.

    When ``artifacts_root`` is given, every entry carrying an
    ``artifact_path`` must resolve to a file that exists under it, so an
    audit entry claiming a pack whose file was never written (or was later
    deleted) is caught here rather than only by a human reading the pack
    (D8 orphan-pack detection).
    """
    path = Path(path)
    if not path.exists():
        return ChainVerification(ok=True, entries=0, first_bad_seq=None, detail="no audit log yet")

    try:
        entries = AuditLog(path).entries()
    except AuditLogCorruptError as exc:
        # A line that cannot even be parsed is reported like any other
        # verification failure — never a raised exception (see module
        # docstring) — naming the physical line, which is also the seq that
        # line was expected to carry under normal one-entry-per-line usage.
        return ChainVerification(
            ok=False,
            entries=exc.line_no - 1,
            first_bad_seq=exc.line_no,
            detail=f"line {exc.line_no} unparseable: {exc.reason}",
        )

    prev_hash = GENESIS_PREV_HASH
    expected_seq = 1
    for entry in entries:
        if entry.seq != expected_seq:
            return ChainVerification(
                ok=False,
                entries=len(entries),
                first_bad_seq=entry.seq,
                detail=f"seq {entry.seq} out of order: expected seq {expected_seq} next",
            )
        if entry.prev_hash != prev_hash:
            return ChainVerification(
                ok=False,
                entries=len(entries),
                first_bad_seq=entry.seq,
                detail=(
                    f"seq {entry.seq}: prev_hash {entry.prev_hash!r} does not match "
                    f"the preceding entry's hash {prev_hash!r}"
                ),
            )
        recomputed = compute_hash(entry, entry.prev_hash)
        if recomputed != entry.hash:
            return ChainVerification(
                ok=False,
                entries=len(entries),
                first_bad_seq=entry.seq,
                detail=(
                    f"seq {entry.seq}: hash mismatch, stored {entry.hash!r} "
                    f"but recomputed {recomputed!r} — entry was edited without "
                    "being re-chained"
                ),
            )
        if artifacts_root is not None and entry.artifact_path is not None:
            resolved, error = _resolve_artifact(Path(artifacts_root), entry.artifact_path)
            if error is not None:
                return ChainVerification(
                    ok=False,
                    entries=len(entries),
                    first_bad_seq=entry.seq,
                    detail=f"seq {entry.seq}: {error} ({entry.artifact_path!r})",
                )
            assert resolved is not None  # error is None iff resolved is set
            if not resolved.is_file():
                return ChainVerification(
                    ok=False,
                    entries=len(entries),
                    first_bad_seq=entry.seq,
                    detail=(
                        f"seq {entry.seq}: artifact_path {entry.artifact_path!r} is "
                        f"not a file under {artifacts_root} (orphan pack)"
                    ),
                )
        prev_hash = entry.hash
        expected_seq += 1
    return ChainVerification(
        ok=True, entries=len(entries), first_bad_seq=None, detail="chain verified"
    )


def audit_chain_gate(path: Path, artifacts_root: Path | None = None) -> GateResult:
    """``GateResult`` wrapper around ``verify_chain`` for registration in
    ``gates.HARD_GATES`` (the integrator binds ``path``/``artifacts_root``
    at merge time, since ``Gate`` callables take no arguments). An absent
    log file passes: nothing has been audited yet, so there is nothing to
    fail on.
    """
    path = Path(path)
    if not path.exists():
        return GateResult(name="audit-chain", ok=True, detail="no audit log yet")
    result = verify_chain(path, artifacts_root)
    detail = result.detail if not result.ok else f"{result.entries} entries verified"
    return GateResult(name="audit-chain", ok=result.ok, detail=detail)
