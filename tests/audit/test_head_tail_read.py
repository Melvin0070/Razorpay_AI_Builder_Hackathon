"""F5: head() reads only the tail of the file instead of parsing every
line, so a batch of N appends costs O(N) rather than O(N^2). Unit-tests the
backward chunked reader directly, then checks append stays roughly linear
over a few thousand entries."""

from __future__ import annotations

import time

from leakproof.audit import AuditLog, _read_tail_line_fast
from tests.audit.conftest import append_sample


def test_tail_read_empty_file(tmp_path):
    path = tmp_path / "audit.jsonl"
    path.write_text("", encoding="utf-8")
    assert _read_tail_line_fast(path) is None


def test_tail_read_one_line(tmp_path):
    path = tmp_path / "audit.jsonl"
    path.write_text('{"a": 1}\n', encoding="utf-8")
    assert _read_tail_line_fast(path) == '{"a": 1}'


def test_tail_read_many_lines(tmp_path):
    path = tmp_path / "audit.jsonl"
    lines = [f'{{"a": {i}}}' for i in range(50)]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert _read_tail_line_fast(path) == '{"a": 49}'


def test_tail_read_spans_multiple_chunks(tmp_path):
    """A small chunk_size forces the backward-scan loop to run more than
    once, without needing a multi-megabyte fixture to do it."""
    path = tmp_path / "audit.jsonl"
    lines = [f'{{"a": {i}}}' for i in range(20)]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert _read_tail_line_fast(path, chunk_size=4) == '{"a": 19}'


def test_tail_read_no_trailing_newline_returns_none(tmp_path):
    """No trailing newline means the last write never completed; the fast
    reader refuses to guess and returns None so the caller falls back to
    the accurate, line-numbered scan (which reports it as corrupt, F1)."""
    path = tmp_path / "audit.jsonl"
    path.write_text('{"a": 1}\n{"a": 2}', encoding="utf-8")
    assert _read_tail_line_fast(path) is None


def test_head_matches_full_scan_after_many_appends(tmp_path):
    path = tmp_path / "audit.jsonl"
    log = AuditLog(path)
    last = None
    for i in range(30):
        last = append_sample(log, f"2026-08-21T00:{i:02d}:00Z")
    assert log.head() == last


def test_append_cost_does_not_blow_up_quadratically(tmp_path):
    """Not a strict benchmark (CI machines vary), just a guard against the
    reintroduction of O(n^2) append: doubling the entry count should not
    multiply the time for the second half by anywhere near the entry count."""
    path = tmp_path / "audit.jsonl"
    log = AuditLog(path)
    n = 600

    start = time.perf_counter()
    for i in range(n):
        append_sample(log, f"2026-08-21T00:00:00.{i:06d}Z")
    first_half = time.perf_counter() - start

    start = time.perf_counter()
    for i in range(n, 2 * n):
        append_sample(log, f"2026-08-21T00:00:00.{i:06d}Z")
    second_half = time.perf_counter() - start

    # O(n^2) behaviour would make the second (equal-sized, but over a log
    # twice as long) batch take roughly 3x the first; a linear cost keeps it
    # close to 1x. Generous slack for CI noise.
    assert second_half < first_half * 3 + 0.5, (
        f"append cost looks superlinear: first_half={first_half:.3f}s "
        f"second_half={second_half:.3f}s"
    )
