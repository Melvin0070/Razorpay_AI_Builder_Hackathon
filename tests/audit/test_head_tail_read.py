"""F5: head() reads only the tail of the file instead of parsing every
line, so a batch of N appends costs O(N) rather than O(N^2). Unit-tests the
backward chunked reader directly, then checks append stays roughly linear
over a few thousand entries."""

from __future__ import annotations

from pathlib import Path

from leakproof.audit import _DEFAULT_TAIL_CHUNK_SIZE, AuditLog, _read_tail_line_fast
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


class _CountingFile:
    """Wraps a binary file object opened for reading and accumulates every
    byte handed back by ``.read()``/iteration into ``counter["bytes"]`` —
    used below to measure exactly how much I/O ``head()``'s fast-tail path
    performs per ``append()`` call, independent of wall-clock noise (C3).

    Also iterable (delegating to the wrapped file's own line iteration,
    counting each line's bytes): if a full-scan regression ever made
    ``head()`` fall back to ``entries()`` (which iterates the file rather
    than calling ``.read()``), this wrapper still counts those bytes instead
    of raising ``TypeError: not iterable`` and masking the real signal this
    test exists to give — a bound violation, not a crash."""

    def __init__(self, fh: object, counter: dict[str, int]) -> None:
        self._fh = fh
        self._counter = counter

    def read(self, *args: object, **kwargs: object) -> bytes:
        data = self._fh.read(*args, **kwargs)  # type: ignore[attr-defined]
        self._counter["bytes"] += len(data)
        return data

    def __iter__(self) -> _CountingFile:
        return self

    def __next__(self) -> bytes:
        line = next(self._fh)  # type: ignore[call-overload]
        self._counter["bytes"] += len(line)
        return line

    def __getattr__(self, name: str) -> object:
        return getattr(self._fh, name)

    def __enter__(self) -> _CountingFile:
        return self

    def __exit__(self, *exc: object) -> object:
        return self._fh.__exit__(*exc)  # type: ignore[attr-defined]


def test_append_reads_bounded_bytes_per_call_independent_of_log_size(tmp_path, monkeypatch):
    """C3: this test used to assert a wall-clock bound
    (``second_half < first_half * 3 + 0.5``) over 1200 real appends and
    fsyncs. That carries no information when it passes -- wall-clock timing
    can look linear for reasons that have nothing to do with whether
    ``head()`` actually reads a bounded number of bytes -- and can flake on
    a loaded CI runner. Replaced with a deterministic bound on the thing
    that actually matters: bytes read from disk per ``append()`` call via
    ``head()``'s fast-tail path (``_read_tail_line_fast``, opened in "rb"),
    measured through a counting wrapper around ``Path.open``. This is the
    guard that actually catches the O(n^2) full-scan regression the
    original test meant to detect: if ``head()`` ever fell back to parsing
    the whole (growing) file, bytes-per-append would grow with ``n`` and
    blow straight through the bound below, at any n, deterministically."""
    path = tmp_path / "audit.jsonl"
    log = AuditLog(path)

    counter = {"bytes": 0}
    real_open = Path.open

    def counting_open(self: Path, mode: str = "r", *args: object, **kwargs: object) -> object:
        fh = real_open(self, mode, *args, **kwargs)
        if self == path and mode == "rb":
            return _CountingFile(fh, counter)
        return fh

    monkeypatch.setattr(Path, "open", counting_open)

    def bytes_per_append(count: int) -> float:
        counter["bytes"] = 0
        for i in range(count):
            append_sample(log, f"2026-08-21T00:00:00.{i:06d}Z")
        return counter["bytes"] / count

    # The reviewer measured 34880/50208/57873 bytes/append at n=200/400/800
    # against the old fixed-64KiB-window implementation, converging upward
    # on the chunk-size ceiling as more appends land once the file exceeds
    # it -- exactly the shape a bound independent of n needs to catch.
    n = 200
    per_n = bytes_per_append(n)  # log grows from 0 to n entries
    per_4n = bytes_per_append(3 * n)  # log grows from n to 4n entries

    # A generous over-estimate of one JSONL line in this fixture (actual
    # lines are on the order of 150-200 bytes); the bound only needs to
    # reject "read a chunk_size window regardless of line size" or worse
    # ("read the whole file"), not pin the exact byte count.
    max_line_len = 512
    bound = _DEFAULT_TAIL_CHUNK_SIZE + max_line_len
    assert per_n <= bound, f"bytes/append at n={n} exceeded bound: {per_n} > {bound}"
    assert per_4n <= bound, f"bytes/append at n={4 * n} exceeded bound: {per_4n} > {bound}"
