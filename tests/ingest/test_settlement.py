"""Amazon Settlement Flat File V2 parser tests (D4, D7). Lane D · issue #7.

The golden fixture (``tests/fixtures/ingest/settlement_golden.txt``) is
hand-authored: header, summary, two transaction rows. Every other case here
builds a minimal in-memory file via ``_row``/``_summary_row`` so each
quarantine reason is pinned independently of the others.
"""

from __future__ import annotations

from pathlib import Path

from leakproof.contract import LineKind, TransactionType, make_line_id
from leakproof.ingest.reasons import (
    amount_not_numeric,
    bad_date,
    column_count,
    missing_order_id_on_order_row,
    quantity_not_numeric,
    unknown_header_layout,
)
from leakproof.ingest.settlement import (
    CSV_HINT,
    SETTLEMENT_COLUMNS,
    parse_settlement_file,
)
from leakproof.types import QuarantinedRow

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "ingest"

HEADER_ROW = "\t".join(SETTLEMENT_COLUMNS)


def _summary_row(**overrides: str) -> str:
    base = {c: "" for c in SETTLEMENT_COLUMNS}
    base.update(
        {
            "settlement-id": "S-1",
            "settlement-start-date": "2026-08-01",
            "settlement-end-date": "2026-08-07",
            "deposit-date": "2026-08-08",
            "total-amount": "100.00",
            "currency": "INR",
        }
    )
    base.update(overrides)
    return "\t".join(base[c] for c in SETTLEMENT_COLUMNS)


def _order_row(**overrides: str) -> str:
    base = {c: "" for c in SETTLEMENT_COLUMNS}
    base.update(
        {
            "settlement-id": "S-1",
            "transaction-type": "Order",
            "order-id": "ORD-1",
            "merchant-order-id": "MO-1",
            "marketplace-name": "Amazon.in",
            "amount-type": "ItemPrice",
            "amount-description": "Principal",
            "amount": "100.00",
            "posted-date": "2026-08-02",
            "sku": "SKU-1",
            "quantity-purchased": "1",
        }
    )
    base.update(overrides)
    return "\t".join(base[c] for c in SETTLEMENT_COLUMNS)


def _write(tmp_path: Path, name: str, rows: list[str]) -> Path:
    path = tmp_path / name
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return path


# --------------------------------------------------------------------------- #
# Golden parse
# --------------------------------------------------------------------------- #


def test_golden_parse():
    result = parse_settlement_file(FIXTURES / "settlement_golden.txt")

    assert result.source_file == "settlement_golden.txt"
    assert result.quarantined == ()
    assert result.hint is None

    header = result.header
    assert header is not None
    assert header.settlement_id == "S-1000"
    assert header.start_date.isoformat() == "2026-08-14"
    assert header.end_date.isoformat() == "2026-08-20"
    assert header.deposit_date.isoformat() == "2026-08-21"
    assert header.total_amount_paise == 123450
    assert header.currency == "INR"
    assert header.source_line_id == "settlement_golden.txt:2"

    assert len(result.lines) == 2
    order_line, refund_line = result.lines

    assert order_line.line_id == "settlement_golden.txt:3"
    assert order_line.settlement_id == "S-1000"
    assert order_line.txn_type is TransactionType.ORDER
    assert order_line.transaction_type_raw == "Order"
    assert order_line.kind is LineKind.PRINCIPAL
    assert order_line.amount_type == "ItemPrice"
    assert order_line.amount_description == "Principal"
    assert order_line.amount_paise == 50000
    assert order_line.posted_date.isoformat() == "2026-08-15"
    assert order_line.order_id == "ORD-1"
    assert order_line.sku == "SKU-1"
    assert order_line.quantity == 1
    assert order_line.adjustment_id is None

    assert refund_line.line_id == "settlement_golden.txt:4"
    assert refund_line.txn_type is TransactionType.REFUND
    assert refund_line.kind is LineKind.COMMISSION
    assert refund_line.amount_paise == -7500
    assert refund_line.posted_date.isoformat() == "2026-08-16"
    assert refund_line.order_id == "ORD-2"
    assert refund_line.sku == "SKU-2"
    assert refund_line.quantity is None


# --------------------------------------------------------------------------- #
# One test per quarantine reason (brief, deliverable 2)
# --------------------------------------------------------------------------- #


def test_column_count_mismatch_on_transaction_row(tmp_path):
    bad_row = "S-1\tOrder\tORD-1"  # 3 fields, not 24
    path = _write(tmp_path, "cc.txt", [HEADER_ROW, _summary_row(), bad_row])
    result = parse_settlement_file(path)

    assert result.lines == ()
    assert result.quarantined == (_q(path.name, 3, column_count(24, 3, "tab")),)


def test_amount_not_numeric_on_transaction_row(tmp_path):
    path = _write(
        tmp_path,
        "amt.txt",
        [HEADER_ROW, _summary_row(), _order_row(amount="not-a-number")],
    )
    result = parse_settlement_file(path)

    assert result.lines == ()
    assert result.quarantined == (_q(path.name, 3, amount_not_numeric("not-a-number")),)


def test_amount_not_numeric_on_summary_row(tmp_path):
    path = _write(
        tmp_path,
        "amt2.txt",
        [HEADER_ROW, _summary_row(**{"total-amount": "oops"})],
    )
    result = parse_settlement_file(path)

    assert result.header is None
    assert result.quarantined == (_q(path.name, 2, amount_not_numeric("oops")),)


def test_bad_date_on_transaction_row(tmp_path):
    path = _write(
        tmp_path,
        "date.txt",
        [HEADER_ROW, _summary_row(), _order_row(**{"posted-date": "21/08/2026"})],
    )
    result = parse_settlement_file(path)

    assert result.lines == ()
    assert result.quarantined == (_q(path.name, 3, bad_date("posted-date", "21/08/2026")),)


def test_bad_date_on_summary_row(tmp_path):
    path = _write(
        tmp_path,
        "date2.txt",
        [HEADER_ROW, _summary_row(**{"settlement-start-date": "not-a-date"})],
    )
    result = parse_settlement_file(path)

    assert result.header is None
    assert result.quarantined == (
        _q(path.name, 2, bad_date("settlement-start-date", "not-a-date")),
    )


def test_missing_order_id_on_order_row(tmp_path):
    path = _write(
        tmp_path,
        "noorder.txt",
        [HEADER_ROW, _summary_row(), _order_row(**{"order-id": ""})],
    )
    result = parse_settlement_file(path)

    assert result.lines == ()
    assert result.quarantined == (_q(path.name, 3, missing_order_id_on_order_row()),)


def test_unknown_header_layout(tmp_path):
    shuffled = "\t".join(reversed(SETTLEMENT_COLUMNS))
    path = _write(tmp_path, "shuffled.txt", [shuffled, _summary_row(), _order_row()])
    result = parse_settlement_file(path)

    assert result.quarantined[0] == _q(path.name, 1, unknown_header_layout())
    assert result.hint == (
        "no valid header row found; Amazon Settlement Flat File V2 begins with 'settlement-id'"
    )


def test_quantity_not_numeric_on_transaction_row(tmp_path):
    path = _write(
        tmp_path,
        "qty.txt",
        [HEADER_ROW, _summary_row(), _order_row(**{"quantity-purchased": "one"})],
    )
    result = parse_settlement_file(path)

    assert result.lines == ()
    assert result.quarantined == (_q(path.name, 3, quantity_not_numeric("one")),)


# --------------------------------------------------------------------------- #
# hint (brief, deliverable 3)
# --------------------------------------------------------------------------- #


def test_saved_as_csv_quarantines_everything_and_sets_hint():
    result = parse_settlement_file(FIXTURES / "settlement_saved_as_csv.txt")

    assert result.header is None
    assert result.lines == ()
    assert result.hint == CSV_HINT
    # Header row (row 1) is quarantined and reported like every other row.
    assert result.quarantined[0].line_id == "settlement_saved_as_csv.txt:1"
    assert result.quarantined[0].reason == column_count(24, 1, "tab")
    assert len(result.quarantined) == 3  # header + summary + one transaction row


# --------------------------------------------------------------------------- #
# Open vocabulary (D4 / trap 2): unclassified kinds and OTHER txn types are
# data, never quarantine.
# --------------------------------------------------------------------------- #


def test_unknown_amount_description_is_unclassified_not_quarantined(tmp_path):
    path = _write(
        tmp_path,
        "unclassified.txt",
        [
            HEADER_ROW,
            _summary_row(),
            _order_row(**{"amount-type": "SomeNewType", "amount-description": "SomeNewCode"}),
        ],
    )
    result = parse_settlement_file(path)

    assert result.quarantined == ()
    assert len(result.lines) == 1
    line = result.lines[0]
    assert line.kind is LineKind.UNCLASSIFIED
    assert line.amount_type == "SomeNewType"
    assert line.amount_description == "SomeNewCode"


def test_open_vocabulary_transaction_type_recognized(tmp_path):
    """RS1 trap 3: ``Order_Retrocharge`` was seen first-hand and has its own
    enum member -- distinct from the "anything else" -> OTHER case below."""
    path = _write(
        tmp_path,
        "other_txn.txt",
        [
            HEADER_ROW,
            _summary_row(),
            _order_row(**{"transaction-type": "Order_Retrocharge"}),
        ],
    )
    result = parse_settlement_file(path)

    assert result.quarantined == ()
    assert len(result.lines) == 1
    line = result.lines[0]
    assert line.txn_type is TransactionType.ORDER_RETROCHARGE
    assert line.transaction_type_raw == "Order_Retrocharge"


def test_fully_unknown_transaction_type_maps_to_other(tmp_path):
    path = _write(
        tmp_path,
        "other_txn2.txt",
        [
            HEADER_ROW,
            _summary_row(),
            _order_row(**{"transaction-type": "TotallyNovelType", "order-id": "ORD-1"}),
        ],
    )
    result = parse_settlement_file(path)

    assert result.quarantined == ()
    line = result.lines[0]
    assert line.txn_type is TransactionType.OTHER
    assert line.transaction_type_raw == "TotallyNovelType"


def _q(source_file: str, row: int, reason: str) -> QuarantinedRow:
    return QuarantinedRow(line_id=make_line_id(source_file, row), reason=reason)
