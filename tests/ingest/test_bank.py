"""Bank CSV parser tests (companion format). Lane D · issue #7."""

from __future__ import annotations

from pathlib import Path

from leakproof.contract import make_line_id
from leakproof.ingest.bank import BANK_COLUMNS, _header_missing_hint, parse_bank
from leakproof.ingest.reasons import (
    NOT_PARSED_BAD_HEADER,
    NOT_VALID_UTF8,
    amount_not_numeric,
    bad_date,
    column_count,
    missing_field,
    unknown_header_layout,
)
from leakproof.types import QuarantinedRow

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "ingest"

HEADER_ROW = ",".join(BANK_COLUMNS)


def _row(**overrides: str) -> str:
    base = {
        "date": "2026-08-21",
        "utr": "UTR1000001",
        "amount": "1234.50",
        "narration": "Settlement payout S-1000",
    }
    base.update(overrides)
    return ",".join(base[c] for c in BANK_COLUMNS)


def _write(tmp_path: Path, name: str, rows: list[str]) -> Path:
    path = tmp_path / name
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return path


def _q(source_file: str, row: int, reason: str) -> QuarantinedRow:
    return QuarantinedRow(line_id=make_line_id(source_file, row), reason=reason)


def test_golden_parse():
    result = parse_bank(FIXTURES / "bank_golden.csv")

    assert result.source_file == "bank_golden.csv"
    assert result.quarantined == ()
    assert result.hint is None
    assert len(result.credits) == 2

    first, second = result.credits
    assert first.line_id == "bank_golden.csv:2"
    assert first.credit_date.isoformat() == "2026-08-21"
    assert first.utr == "UTR1000001"
    assert first.amount_paise == 123450
    assert first.narration == "Settlement payout S-1000"

    assert second.line_id == "bank_golden.csv:3"
    assert second.utr == "UTR1000002"
    assert second.amount_paise == 98765


def test_bad_amount_is_quarantined():
    result = parse_bank(FIXTURES / "bank_quarantine_bad_amount.csv")

    assert result.credits == ()
    assert result.quarantined == (
        _q("bank_quarantine_bad_amount.csv", 2, amount_not_numeric("not-a-number")),
    )


def test_column_count_mismatch(tmp_path):
    path = _write(tmp_path, "cc.csv", [HEADER_ROW, "2026-08-21,UTR1"])
    result = parse_bank(path)

    assert result.credits == ()
    assert result.quarantined == (_q(path.name, 2, column_count(4, 2, "comma")),)


def test_bad_date(tmp_path):
    path = _write(tmp_path, "date.csv", [HEADER_ROW, _row(date="21/08/2026")])
    result = parse_bank(path)

    assert result.credits == ()
    assert result.quarantined == (_q(path.name, 2, bad_date("date", "21/08/2026")),)


def test_missing_utr(tmp_path):
    path = _write(tmp_path, "utr.csv", [HEADER_ROW, _row(utr="")])
    result = parse_bank(path)

    assert result.credits == ()
    assert result.quarantined == (_q(path.name, 2, missing_field("utr")),)


# --------------------------------------------------------------------------- #
# S2: exact header-name match, not just column count. On mismatch nothing is
# parsed by guessed position.
# --------------------------------------------------------------------------- #


def test_swapped_header_columns_quarantines_header_and_every_data_row(tmp_path):
    swapped = "utr,date,amount,narration"
    path = _write(tmp_path, "swapped.csv", [swapped, _row(), _row(utr="UTR1000002")])

    result = parse_bank(path)

    assert result.credits == ()
    assert result.hint == _header_missing_hint()
    assert result.quarantined[0] == _q(path.name, 1, unknown_header_layout())
    assert result.quarantined[1] == _q(path.name, 2, NOT_PARSED_BAD_HEADER)
    assert result.quarantined[2] == _q(path.name, 3, NOT_PARSED_BAD_HEADER)
    assert len(result.quarantined) == 3


def test_headerless_file_drops_no_row_from_the_denominator(tmp_path):
    path = _write(tmp_path, "headerless.csv", [_row(), _row(utr="UTR1000002")])

    result = parse_bank(path)

    assert result.credits == ()
    assert result.hint == _header_missing_hint()
    assert result.quarantined[0] == _q(path.name, 1, unknown_header_layout())
    assert result.quarantined[1] == _q(path.name, 2, NOT_PARSED_BAD_HEADER)
    assert len(result.quarantined) == 2


def test_correct_header_parses_normally(tmp_path):
    path = _write(tmp_path, "correct.csv", [HEADER_ROW, _row()])
    result = parse_bank(path)

    assert result.hint is None
    assert result.quarantined == ()
    assert len(result.credits) == 1


# --------------------------------------------------------------------------- #
# S1: undecodable bytes quarantine only their own row.
# --------------------------------------------------------------------------- #


def test_undecodable_byte_quarantines_only_that_row(tmp_path):
    bad_row = (
        _row(utr="UTR-BAD", narration="PLACEHOLDER")
        .encode("utf-8")
        .replace(b"PLACEHOLDER", b"Caf\xe9")
    )
    good_row = _row(utr="UTR1000002").encode("utf-8")
    path = tmp_path / "badutf8.csv"
    path.write_bytes(b"\n".join([HEADER_ROW.encode(), bad_row, good_row]) + b"\n")

    result = parse_bank(path)

    assert result.quarantined == (_q(path.name, 2, NOT_VALID_UTF8),)
    assert len(result.credits) == 1
    assert result.credits[0].line_id == f"{path.name}:3"


# --------------------------------------------------------------------------- #
# S4: a leading UTF-8 BOM does not turn a valid file into "unknown header
# layout".
# --------------------------------------------------------------------------- #


def test_bom_valid_bank_file_parses_with_no_quarantine(tmp_path):
    content = ("﻿" + HEADER_ROW + "\n" + _row() + "\n").encode("utf-8")
    path = tmp_path / "bom.csv"
    path.write_bytes(content)

    result = parse_bank(path)

    assert result.quarantined == ()
    assert result.hint is None
    assert len(result.credits) == 1


# --------------------------------------------------------------------------- #
# S6: blank lines are skipped, never quarantined, and physical numbering
# survives them.
# --------------------------------------------------------------------------- #


def test_blank_lines_are_skipped_and_physical_numbering_is_preserved(tmp_path):
    rows = [
        HEADER_ROW,
        _row(utr="UTR1000001"),
        "",  # interior blank line
        _row(utr="UTR1000002"),
        "",  # trailing blank line
    ]
    path = _write(tmp_path, "blank.csv", rows)

    result = parse_bank(path)

    assert result.quarantined == ()
    assert len(result.credits) == 2
    assert result.credits[0].line_id == f"{path.name}:2"
    assert result.credits[1].line_id == f"{path.name}:4"


# --------------------------------------------------------------------------- #
# S9: a quoted field with an embedded newline must not shift a later row's
# physical line_id.
# --------------------------------------------------------------------------- #


def test_embedded_newline_in_quoted_narration_keeps_next_row_at_its_physical_line(tmp_path):
    content = (
        HEADER_ROW + "\n"
        '2026-08-21,UTR1000001,1234.50,"Payout\nS-1000"\n'
        "2026-08-22,UTR1000002,555.00,Second credit\n"
    )
    path = tmp_path / "embedded_newline.csv"
    path.write_text(content, encoding="utf-8")

    result = parse_bank(path)

    assert result.quarantined == ()
    assert len(result.credits) == 2
    first, second = result.credits
    assert first.narration == "Payout\nS-1000"
    assert first.line_id == f"{path.name}:2"
    # The quoted field spans physical lines 2-3, so the second credit is on line 4.
    assert second.line_id == f"{path.name}:4"
