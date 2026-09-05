"""F1: malformed content must fail the gate, never raise past it -- and
must make append() refuse to continue past it (append can only ever see
corruption in the tail line it reads to find the current head/seq, so all
four scenarios corrupt the LAST line of an otherwise-healthy log; see the
module docstring's single-writer/head-is-the-last-line note)."""

from __future__ import annotations

import json
from datetime import date

import pytest

from leakproof.audit import AuditLog, AuditLogCorruptError, audit_chain_gate, verify_chain
from leakproof.contract import AuditAction
from tests.audit.conftest import append_sample

_APPEND_KWARGS = dict(
    ts="2026-08-21T10:00:03Z",
    as_of=date(2026, 8, 21),
    actor="system",
    action=AuditAction.INGEST,
    exception_id=None,
    state_before=None,
    state_after=None,
    amount_paise=None,
    artifact_path=None,
)


def _build_three_entry_log(tmp_path):
    path = tmp_path / "audit.jsonl"
    log = AuditLog(path)
    append_sample(log, "2026-08-21T10:00:00Z")
    append_sample(log, "2026-08-21T10:00:01Z")
    append_sample(log, "2026-08-21T10:00:02Z")
    return path


def _assert_fails_gate_and_append_at_line_3(path, tmp_path, *, reason_substring):
    result = verify_chain(path)
    assert not result.ok
    assert result.first_bad_seq == 3
    assert result.entries == 2
    assert result.detail.startswith("line 3 unparseable:")
    assert reason_substring in result.detail

    gate_result = audit_chain_gate(path, tmp_path / "artifacts")
    assert not gate_result.ok
    assert gate_result.detail == result.detail

    with pytest.raises(AuditLogCorruptError) as excinfo:
        AuditLog(path).append(**_APPEND_KWARGS)
    assert excinfo.value.line_no == 3


def test_truncated_tail_fails_gate_and_append(tmp_path):
    path = _build_three_entry_log(tmp_path)
    lines = path.read_text(encoding="utf-8").splitlines()
    truncated = lines[-1][: len(lines[-1]) // 2]
    # No trailing newline either: a truncated write is exactly what leaves
    # the file in this state (the writer was cut off mid-line).
    path.write_text("\n".join([*lines[:-1], truncated]), encoding="utf-8")

    _assert_fails_gate_and_append_at_line_3(path, tmp_path, reason_substring="Unterminated")


def test_garbage_line_fails_gate_and_append(tmp_path):
    path = _build_three_entry_log(tmp_path)
    lines = path.read_text(encoding="utf-8").splitlines()
    lines[-1] = "not json at all {{{"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    _assert_fails_gate_and_append_at_line_3(path, tmp_path, reason_substring="Expecting")


def test_deleted_key_fails_gate_and_append(tmp_path):
    path = _build_three_entry_log(tmp_path)
    lines = path.read_text(encoding="utf-8").splitlines()
    obj = json.loads(lines[-1])
    del obj["actor"]
    lines[-1] = json.dumps(obj, sort_keys=True, separators=(",", ":"))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    _assert_fails_gate_and_append_at_line_3(path, tmp_path, reason_substring="actor")


def test_wrong_enum_value_fails_gate_and_append(tmp_path):
    path = _build_three_entry_log(tmp_path)
    lines = path.read_text(encoding="utf-8").splitlines()
    obj = json.loads(lines[-1])
    obj["action"] = "not_a_real_action"
    lines[-1] = json.dumps(obj, sort_keys=True, separators=(",", ":"))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    _assert_fails_gate_and_append_at_line_3(path, tmp_path, reason_substring="not_a_real_action")


def test_truncated_mid_multibyte_char_fails_gate_and_append_without_raising(tmp_path):
    """C1: entries() used to open with encoding="utf-8" and decode inside
    the `for line in fh` iteration itself -- OUTSIDE the try/except that
    catches every other parse failure -- and _read_tail_line_fast's
    .decode("utf-8") was similarly unguarded. A write cut off mid-UTF-8
    character (the canonical shape of an interrupted write on a non-ASCII
    field, e.g. an actor name) used to raise a bare UnicodeDecodeError past
    verify_chain/audit_chain_gate/append instead of being reported as
    ordinary corruption -- exactly the failure mode F1 existed to remove.
    Uses a non-ASCII actor (conftest's default actor is pure ASCII, which is
    why the original F1 corruption tests never exercised this path)."""
    path = tmp_path / "audit.jsonl"
    log = AuditLog(path)
    append_sample(log, "2026-08-21T10:00:00Z")
    append_sample(log, "2026-08-21T10:00:01Z")
    append_sample(log, "2026-08-21T10:00:02Z", actor="détectrice")

    raw = path.read_bytes()
    body, trailing_newline, after = raw.rpartition(b"\n")
    assert trailing_newline == b"\n" and after == b"", "fixture assumption: file ends in \\n"
    lines = body.split(b"\n")
    last_line = lines[-1]
    # "é" is a 2-byte UTF-8 sequence (0xc3 0xa9); cut right after the first
    # byte so the line ends mid-character, with no trailing newline either
    # -- a truncated write is exactly what leaves the file in this state.
    cut_at = last_line.index("é".encode()) + 1
    lines[-1] = last_line[:cut_at]
    path.write_bytes(b"\n".join(lines))

    result = verify_chain(path)
    assert not result.ok
    assert result.first_bad_seq == 3
    assert result.entries == 2
    assert result.detail.startswith("line 3 unparseable:")
    assert "codec can't decode" in result.detail

    gate_result = audit_chain_gate(path, tmp_path / "artifacts")
    assert not gate_result.ok
    assert gate_result.detail == result.detail

    with pytest.raises(AuditLogCorruptError) as excinfo:
        AuditLog(path).append(**_APPEND_KWARGS)
    assert excinfo.value.line_no == 3


def test_corrupt_with_blank_lines_reports_seq_not_physical_line(tmp_path):
    """C2: entries/first_bad_seq must report the count of parsed entries
    and the seq that would have come next, never the physical line number --
    a blank line before the break (silently skipped by entries()) must not
    inflate either. Two real entries, two blank physical lines, then garbage
    at physical line 5: before the fix this reported entries=4,
    first_bad_seq=5 (both derived from line_no), naming a seq that would
    actually have been 3."""
    path = tmp_path / "audit.jsonl"
    log = AuditLog(path)
    append_sample(log, "2026-08-21T10:00:00Z")
    append_sample(log, "2026-08-21T10:00:01Z")
    with path.open("a", encoding="utf-8") as fh:
        fh.write("\n\n")  # blank physical lines 3 and 4, silently skipped
        fh.write("not json at all {{{\n")  # physical line 5

    result = verify_chain(path)
    assert not result.ok
    assert result.entries == 2, "two real entries parsed before the break"
    assert result.first_bad_seq == 3, "the seq that would have been assigned next"
    assert result.detail.startswith("line 5 unparseable:"), "physical line stays in detail"


def test_log_path_is_a_directory_fails_gate_without_raising(tmp_path):
    """C1: the log path itself being a directory used to raise a bare
    IsADirectoryError out of _read_tail_line_fast (opening it "rb") and out
    of entries() (opening it "r"), past every guard."""
    path = tmp_path / "audit.jsonl"
    path.mkdir()

    result = verify_chain(path)
    assert not result.ok
    assert "directory" in result.detail

    gate_result = audit_chain_gate(path, tmp_path / "artifacts")
    assert not gate_result.ok
    assert gate_result.detail == result.detail

    with pytest.raises(AuditLogCorruptError):
        AuditLog(path).append(**_APPEND_KWARGS)
