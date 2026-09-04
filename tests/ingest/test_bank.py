"""Bank CSV parser tests (companion format). Lane D · issue #7."""

from __future__ import annotations

from pathlib import Path

from leakproof.contract import make_line_id
from leakproof.ingest.bank import BANK_COLUMNS, parse_bank
from leakproof.ingest.reasons import amount_not_numeric, bad_date, column_count, missing_field
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
