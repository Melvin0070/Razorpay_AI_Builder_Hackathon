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
