"""Append/verify basics, tamper detection, reorder detection, idempotent
reopen, and the recompute-not-compare property (D21)."""

from __future__ import annotations

import pytest

from leakproof.audit import AuditLog, audit_chain_gate, verify_chain
from leakproof.contract import AuditAction
from tests.audit.conftest import append_sample


def test_append_three_hashes_differ_and_prev_hash_links(tmp_path):
    path = tmp_path / "audit.jsonl"
    log = AuditLog(path)
    e1 = append_sample(log, "2026-08-21T10:00:00Z")
    e2 = append_sample(log, "2026-08-21T10:00:01Z", action=AuditAction.DETECT)
    e3 = append_sample(log, "2026-08-21T10:00:02Z", action=AuditAction.CLASSIFY)

    assert [e.seq for e in (e1, e2, e3)] == [1, 2, 3]
    assert e1.prev_hash == "0" * 64
    assert e2.prev_hash == e1.hash
    assert e3.prev_hash == e2.hash
    assert len({e1.hash, e2.hash, e3.hash}) == 3, "each entry's hash must differ"

    result = verify_chain(path)
    assert result.ok
    assert result.entries == 3
    assert result.first_bad_seq is None

    # entries()/head() round-trip what was appended
    assert log.entries() == (e1, e2, e3)
    assert log.head() == e3


def test_verify_ok_detail_says_artifact_paths_not_checked_without_root(tmp_path):
    """F2: a passing result must never claim a check it did not run."""
    path = tmp_path / "audit.jsonl"
    log = AuditLog(path)
    append_sample(log, "2026-08-21T10:00:00Z")

    without_root = verify_chain(path)
    assert without_root.ok
    assert without_root.detail == "1 entries verified; artifact paths not checked"

    with_root = verify_chain(path, artifacts_root=tmp_path / "artifacts")
    assert with_root.ok
    assert with_root.detail == "1 entries verified"


def test_verify_missing_file_is_ok_empty_chain(tmp_path):
    result = verify_chain(tmp_path / "does-not-exist.jsonl")
    assert result.ok
    assert result.entries == 0
    assert result.first_bad_seq is None
    assert result.detail == "no audit log yet"


def test_tamper_detected_at_exact_seq_naming_hash_mismatch(tmp_path):
    path = tmp_path / "audit.jsonl"
    log = AuditLog(path)
    append_sample(log, "2026-08-21T10:00:00Z")
    append_sample(log, "2026-08-21T10:00:01Z", actor="reviewer")
    append_sample(log, "2026-08-21T10:00:02Z")

    lines = path.read_text(encoding="utf-8").splitlines()
    tampered = lines[1].replace('"reviewer"', '"reviewerx"')
    assert tampered != lines[1], "fixture assumption: actor string is present verbatim"
    lines[1] = tampered
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    result = verify_chain(path)
    assert not result.ok
    assert result.entries == 3
    assert result.first_bad_seq == 2
    assert "hash mismatch" in result.detail


def test_reorder_fails_at_first_out_of_order_seq(tmp_path):
    path = tmp_path / "audit.jsonl"
    log = AuditLog(path)
    append_sample(log, "2026-08-21T10:00:00Z")
    append_sample(log, "2026-08-21T10:00:01Z")
    append_sample(log, "2026-08-21T10:00:02Z")

    lines = path.read_text(encoding="utf-8").splitlines()
    lines[1], lines[2] = lines[2], lines[1]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    result = verify_chain(path)
    assert not result.ok
    assert result.first_bad_seq == 3, "seq 3 now appears before seq 2 was consumed"
    assert "out of order" in result.detail


def test_recompute_not_byte_compare_across_reruns(tmp_path):
    """Two logs whose entries differ only in ts (as a rerun on a later day
    would) are NOT byte-identical, yet both independently verify — proving
    verify_chain recomputes rather than comparing against a golden file."""
    path_a = tmp_path / "a.jsonl"
    path_b = tmp_path / "b.jsonl"
    log_a = AuditLog(path_a)
    log_b = AuditLog(path_b)

    for i in range(3):
        append_sample(log_a, f"2026-08-21T10:00:0{i}Z", action=AuditAction.DETECT)
        append_sample(log_b, f"2026-08-22T11:30:1{i}Z", action=AuditAction.DETECT)

    assert path_a.read_bytes() != path_b.read_bytes()
    result_a = verify_chain(path_a)
    result_b = verify_chain(path_b)
    assert result_a.ok
    assert result_b.ok
    # the two chains carry different hashes at every seq (ts feeds the hash)
    assert log_a.entries()[0].hash != log_b.entries()[0].hash


def test_idempotent_open_continues_seq_and_prev_hash(tmp_path):
    path = tmp_path / "audit.jsonl"
    e1 = append_sample(AuditLog(path), "2026-08-21T10:00:00Z")

    # a fresh AuditLog instance over the same path simulates a new process
    # reopening the log; it must not restart seq or forget the head hash.
    reopened = AuditLog(path)
    e2 = append_sample(reopened, "2026-08-21T10:00:01Z")

    assert e2.seq == 2
    assert e2.prev_hash == e1.hash
    result = verify_chain(path)
    assert result.ok
    assert result.entries == 2


def test_next_seq_on_empty_log_is_one_and_matches_append(tmp_path):
    path = tmp_path / "audit.jsonl"
    log = AuditLog(path)
    assert log.next_seq() == 1

    e1 = append_sample(log, "2026-08-21T10:00:00Z")
    assert e1.seq == 1
    assert log.next_seq() == 2

    e2 = append_sample(log, "2026-08-21T10:00:01Z")
    assert e2.seq == 2
    assert log.next_seq() == 3


def test_lone_surrogate_actor_raises_value_error_not_unicode_error(tmp_path):
    """F10: append(actor="\\ud800") used to crash with a bare
    UnicodeEncodeError from deep inside .encode("utf-8"); it must now raise
    a clear ValueError instead."""
    path = tmp_path / "audit.jsonl"
    log = AuditLog(path)
    with pytest.raises(ValueError, match="not valid UTF-8"):
        append_sample(log, "2026-08-21T10:00:00Z", actor="\ud800")
    # nothing was written: the failure happens before the file is touched
    assert not path.exists()


def test_gate_passes_with_no_log_file(tmp_path):
    result = audit_chain_gate(tmp_path / "nope.jsonl", tmp_path / "artifacts")
    assert result.ok
    assert result.detail == "no audit log yet"
    assert result.name == "audit-chain"


def test_gate_fails_when_chain_is_broken(tmp_path):
    path = tmp_path / "audit.jsonl"
    log = AuditLog(path)
    append_sample(log, "2026-08-21T10:00:00Z")
    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text(lines[0].replace('"system"', '"tampered"') + "\n", encoding="utf-8")

    result = audit_chain_gate(path, tmp_path / "artifacts")
    assert not result.ok
    assert "hash mismatch" in result.detail


def test_gate_passes_on_a_clean_chain(tmp_path):
    path = tmp_path / "audit.jsonl"
    log = AuditLog(path)
    append_sample(log, "2026-08-21T10:00:00Z")
    append_sample(log, "2026-08-21T10:00:01Z")

    result = audit_chain_gate(path, tmp_path / "artifacts")
    assert result.ok
    assert result.detail == "2 entries verified"
