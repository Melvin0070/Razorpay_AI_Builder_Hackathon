"""F4: a committed golden log pins the exact hashed bytes, independent of
this module's own implementation drifting. tests/fixtures/audit/golden.jsonl
was produced by AuditLog.append() itself (three entries: ingest, detect with
a non-ASCII actor, approve with a relative artifact_path) with a matching
pack file committed at tests/fixtures/audit/packs/e-100.json.

Also carries the "recompute, not compare" claim (reviewer F9): a log built
from the same three entries but with different ts values verifies even
though none of its hashes equal the golden file's."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path

from leakproof.audit import GENESIS_PREV_HASH, AuditLog, canonical_json, verify_chain
from leakproof.contract import AuditAction, State
from leakproof.types import AuditEntry, ClaimPack

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "audit"
GOLDEN_PATH = FIXTURES_DIR / "golden.jsonl"
# The committed pack lives at FIXTURES_DIR/packs/e-100.json, matching the
# golden log's relative artifact_path "packs/e-100.json".
ARTIFACTS_ROOT = FIXTURES_DIR


def _independent_recipe_hash(entry: AuditEntry, prev_hash: str) -> str:
    """Reimplements the documented hash recipe from scratch -- its own
    json.dumps call over a hand-built dict, deliberately NOT calling
    leakproof.audit.canonical_json or _project -- so this test would catch a
    change to the module's implementation that silently drifted from what
    the module docstring promises lane O and the metrics harness they can
    reproduce independently."""
    payload = {
        "seq": entry.seq,
        "prev_hash": entry.prev_hash,
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
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256()
    digest.update(canonical.encode("utf-8"))
    digest.update(prev_hash.encode("ascii"))
    return digest.hexdigest()


def test_golden_log_verifies_with_committed_packs_dir():
    result = verify_chain(GOLDEN_PATH, artifacts_root=ARTIFACTS_ROOT)
    assert result.ok, result.detail
    assert result.entries == 3


def test_committed_pack_parses_as_a_real_claim_pack():
    """C5: verify_chain's orphan-pack check only calls Path.is_file() on
    artifact_path -- it has never actually parsed the committed pack as a
    types.ClaimPack, so a placeholder JSON file missing required fields
    (cited_rows_csv, recomputation_csv, state_before, audit_seq -- the shape
    this fixture originally had) was inert today but would silently start
    failing the day another lane asserts every committed pack parses. This
    test is that assertion, run now rather than left for that day."""
    raw = json.loads((FIXTURES_DIR / "packs" / "e-100.json").read_text(encoding="utf-8"))
    pack = ClaimPack(
        exception_id=raw["exception_id"],
        path=raw["path"],
        claim_text=raw["claim_text"],
        cited_rows_csv=raw["cited_rows_csv"],
        recomputation_csv=raw["recomputation_csv"],
        state_before=State(raw["state_before"]),
        audit_seq=raw["audit_seq"],
        overridden=raw["overridden"],
    )
    # audit_seq/path/exception_id line up with the golden log's own seq-3
    # approve entry, which names this exact artifact_path.
    assert pack.audit_seq == 3
    assert pack.path == "packs/e-100.json"
    assert pack.exception_id == "e-100"
    assert pack.state_before == State.CLAIM_READY


def test_golden_hashes_match_independently_reimplemented_recipe():
    entries = AuditLog(GOLDEN_PATH).entries()
    assert len(entries) == 3
    prev_hash = GENESIS_PREV_HASH
    for entry in entries:
        assert entry.hash == _independent_recipe_hash(entry, prev_hash)
        prev_hash = entry.hash


def test_golden_entry_1_canonical_string_is_pinned():
    entry1 = AuditLog(GOLDEN_PATH).entries()[0]
    assert canonical_json(entry1) == (
        '{"action":"ingest","actor":"ops","amount_paise":null,"artifact_path":null,'
        '"as_of":"2026-08-21","exception_id":null,'
        '"prev_hash":"0000000000000000000000000000000000000000000000000000000000000000",'
        '"seq":1,"state_after":null,"state_before":null,"ts":"2026-08-21T09:00:00Z"}'
    )


def test_regenerated_batch_with_different_ts_verifies_but_hashes_differ_from_golden(tmp_path):
    """F9: proves verify_chain recomputes rather than comparing bytes to
    this (or any) golden log -- the same three entries, re-run on a later
    day so only ts changes, still verify even though every hash differs."""
    path = tmp_path / "regenerated.jsonl"
    log = AuditLog(path)
    as_of = date(2026, 8, 21)
    e1 = log.append(
        ts="2026-09-01T09:00:00Z",
        as_of=as_of,
        actor="ops",
        action=AuditAction.INGEST,
        exception_id=None,
        state_before=None,
        state_after=None,
        amount_paise=None,
        artifact_path=None,
    )
    e2 = log.append(
        ts="2026-09-01T09:05:00Z",
        as_of=as_of,
        actor="détectrice",
        action=AuditAction.DETECT,
        exception_id="e-100",
        state_before=None,
        state_after=State.BLOCKED,
        amount_paise=150000,
        artifact_path=None,
    )
    e3 = log.append(
        ts="2026-09-01T10:00:00Z",
        as_of=as_of,
        actor="ops",
        action=AuditAction.APPROVE,
        exception_id="e-100",
        state_before=State.CLAIM_READY,
        state_after=State.CLAIM_READY,
        amount_paise=150000,
        artifact_path="packs/e-100.json",
    )

    result = verify_chain(path, artifacts_root=ARTIFACTS_ROOT)
    assert result.ok, result.detail

    golden_entries = AuditLog(GOLDEN_PATH).entries()
    assert e1.hash != golden_entries[0].hash
    assert e2.hash != golden_entries[1].hash
    assert e3.hash != golden_entries[2].hash
