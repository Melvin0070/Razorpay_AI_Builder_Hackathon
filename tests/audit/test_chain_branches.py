"""F7: verify_chain branches not otherwise reached by the tamper/reorder
tests in test_chain.py -- each fabricated entry below is internally
self-consistent (its own hash correctly matches a recomputation given its
own stored prev_hash) so only the ONE targeted check fails, isolating:

  (a) prev_hash linkage, independent of the hash-mismatch check
  (b) a seq gap, with fully valid hashes/linkage
  (c) a duplicate seq, with fully valid hashes/linkage
"""

from __future__ import annotations

import dataclasses

from leakproof.audit import AuditLog, _entry_line, compute_hash, verify_chain
from leakproof.contract import AuditAction
from leakproof.types import AuditEntry
from tests.audit.conftest import DEFAULT_AS_OF, append_sample


def _fabricate(*, seq: int, prev_hash: str, ts: str) -> AuditEntry:
    """A fully self-consistent AuditEntry: its hash is computed from
    exactly the seq/prev_hash/ts given, the same way append() builds one --
    so verify_chain's hash-recompute check always passes for it, leaving
    only whatever's anomalous about seq/prev_hash to fail a different check.
    """
    draft = AuditEntry(
        seq=seq,
        prev_hash=prev_hash,
        hash="",
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
    return dataclasses.replace(draft, hash=compute_hash(draft, prev_hash))


def test_wrong_prev_hash_with_valid_self_hash_fails_at_linkage_check(tmp_path):
    path = tmp_path / "audit.jsonl"
    log = AuditLog(path)
    e1 = append_sample(log, "2026-08-21T10:00:00Z")
    append_sample(log, "2026-08-21T10:00:01Z")  # entry 2 placeholder, overwritten below
    append_sample(log, "2026-08-21T10:00:02Z")  # entry 3, untouched

    bogus_prev_hash = "1" * 64
    assert bogus_prev_hash != e1.hash, "fixture assumption: the bogus value must actually differ"
    fabricated_e2 = _fabricate(seq=2, prev_hash=bogus_prev_hash, ts="2026-08-21T10:00:01Z")

    lines = path.read_text(encoding="utf-8").splitlines()
    lines[1] = _entry_line(fabricated_e2)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    result = verify_chain(path)
    assert not result.ok
    assert result.first_bad_seq == 2
    assert "prev_hash" in result.detail
    assert bogus_prev_hash in result.detail
    assert "hash mismatch" not in result.detail, "must fail linkage, not the self-hash check"


def test_seq_gap_with_valid_hash_and_linkage_fails_out_of_order(tmp_path):
    path = tmp_path / "audit.jsonl"
    log = AuditLog(path)
    e1 = append_sample(log, "2026-08-21T10:00:00Z")

    # Correct linkage to e1 and a correct self-hash; only the seq jumps.
    fabricated = _fabricate(seq=5, prev_hash=e1.hash, ts="2026-08-21T10:00:01Z")
    with path.open("a", encoding="utf-8") as fh:
        fh.write(_entry_line(fabricated) + "\n")

    result = verify_chain(path)
    assert not result.ok
    assert result.first_bad_seq == 5
    assert "out of order" in result.detail
    assert "expected seq 2" in result.detail


def test_duplicate_seq_with_valid_hash_and_linkage_fails_out_of_order(tmp_path):
    path = tmp_path / "audit.jsonl"
    log = AuditLog(path)
    e1 = append_sample(log, "2026-08-21T10:00:00Z")

    # Correct linkage to e1 and a correct self-hash; only the seq repeats.
    fabricated = _fabricate(seq=1, prev_hash=e1.hash, ts="2026-08-21T10:00:01Z")
    with path.open("a", encoding="utf-8") as fh:
        fh.write(_entry_line(fabricated) + "\n")

    result = verify_chain(path)
    assert not result.ok
    assert result.first_bad_seq == 1
    assert "out of order" in result.detail
    assert "expected seq 2" in result.detail
