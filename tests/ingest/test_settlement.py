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
    NOT_PARSED_BAD_HEADER,
    NOT_VALID_UTF8,
    amount_not_numeric,
    bad_date,
    column_count,
    missing_order_id_on_order_row,
    quantity_not_numeric,
    quantity_not_positive,
    unknown_header_layout,
)
from leakproof.ingest.settlement import (
    CSV_HINT,
    SETTLEMENT_COLUMNS,
    SUMMARY_ROW_MISSING_HINT,
    TRAILING_TAB_HINT,
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
    """G2: 24 fields, all present, but not the canonical names in the
    canonical order -- row 1's fault cascades to every other row instead of
    letting rows 2+ parse by trusted fixed offsets."""
    shuffled = "\t".join(reversed(SETTLEMENT_COLUMNS))
    path = _write(tmp_path, "shuffled.txt", [shuffled, _summary_row(), _order_row()])
    result = parse_settlement_file(path)

    assert result.header is None
    assert result.lines == ()
    assert result.hint == (
        "no valid header row found; Amazon Settlement Flat File V2 begins with 'settlement-id'"
    )
    assert result.quarantined == (
        _q(path.name, 1, unknown_header_layout()),
        _q(path.name, 2, NOT_PARSED_BAD_HEADER),
        _q(path.name, 3, NOT_PARSED_BAD_HEADER),
    )


def test_transposed_amount_columns_in_header_cascades_no_line_emitted(tmp_path):
    """G2: the reviewer's exact probe -- ``total-amount`` and ``amount``
    swapped in the header, all 24 names still present. Trusting fixed
    offsets here would silently emit +Rs 1,25,000 principal instead of
    -Rs 487.50; the cascade must mean no SettlementLine is emitted at all."""
    columns = list(SETTLEMENT_COLUMNS)
    i, j = columns.index("total-amount"), columns.index("amount")
    columns[i], columns[j] = columns[j], columns[i]
    transposed_header = "\t".join(columns)
    path = _write(
        tmp_path,
        "transposed.txt",
        [transposed_header, _summary_row(), _order_row(amount="-487.50")],
    )
    result = parse_settlement_file(path)

    assert result.header is None
    assert result.lines == ()
    assert result.quarantined == (
        _q(path.name, 1, unknown_header_layout()),
        _q(path.name, 2, NOT_PARSED_BAD_HEADER),
        _q(path.name, 3, NOT_PARSED_BAD_HEADER),
    )


def test_saved_as_csv_reason_unchanged_by_the_header_cascade():
    """G2: the cascade is gated on column count == 24, so the saved-as-CSV
    file (column count 1) must still get its own column-count reason, not
    the not-parsed-bad-header cascade reason."""
    result = parse_settlement_file(FIXTURES / "settlement_saved_as_csv.txt")

    assert result.quarantined[0].reason == column_count(24, 1, "tab")
    assert all(q.reason != NOT_PARSED_BAD_HEADER for q in result.quarantined)


def test_trailing_tab_reason_unchanged_by_the_header_cascade(tmp_path):
    """G2: the cascade is gated on column count == 24, so the trailing-tab
    file (column count 25) must still quarantine every row on the ordinary
    column-count reason, not the not-parsed-bad-header cascade reason."""
    rows = [HEADER_ROW + "\t", _summary_row() + "\t", _order_row() + "\t"]
    path = _write(tmp_path, "trailingtab2.txt", rows)
    result = parse_settlement_file(path)

    assert all(q.reason == column_count(24, 25, "tab") for q in result.quarantined)


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
# G9: quantity-purchased must reject 0 and negative values, matching the
# orders CSV's own rule (S12) for the same concept.
# --------------------------------------------------------------------------- #


def test_quantity_zero_is_not_positive(tmp_path):
    path = _write(
        tmp_path,
        "qty0.txt",
        [HEADER_ROW, _summary_row(), _order_row(**{"quantity-purchased": "0"})],
    )
    result = parse_settlement_file(path)

    assert result.lines == ()
    assert result.quarantined == (_q(path.name, 3, quantity_not_positive("0")),)


def test_quantity_negative_is_not_positive(tmp_path):
    path = _write(
        tmp_path,
        "qtyneg.txt",
        [HEADER_ROW, _summary_row(), _order_row(**{"quantity-purchased": "-5"})],
    )
    result = parse_settlement_file(path)

    assert result.lines == ()
    assert result.quarantined == (_q(path.name, 3, quantity_not_positive("-5")),)


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


# --------------------------------------------------------------------------- #
# S1: undecodable bytes quarantine only their own row; physical splitting
# survives control characters str.splitlines() would treat as line breaks.
# --------------------------------------------------------------------------- #


def test_undecodable_byte_quarantines_only_that_row(tmp_path):
    """An Excel re-save as Windows-1252 (``Caf\\xe9``) is not valid UTF-8."""
    bad_row = (
        _order_row(**{"order-id": "ORD-BAD", "marketplace-name": "PLACEHOLDER"})
        .encode("utf-8")
        .replace(b"PLACEHOLDER", b"Caf\xe9")
    )
    good_row = _order_row(**{"order-id": "ORD-2", "posted-date": "2026-08-17"}).encode("utf-8")
    path = tmp_path / "badutf8.txt"
    path.write_bytes(
        b"\n".join([HEADER_ROW.encode(), _summary_row().encode(), bad_row, good_row]) + b"\n"
    )

    result = parse_settlement_file(path)

    assert result.quarantined == (_q(path.name, 3, NOT_VALID_UTF8),)
    assert len(result.lines) == 1
    assert result.lines[0].line_id == f"{path.name}:4"
    assert result.header is not None


def test_vertical_tab_inside_a_field_keeps_physical_numbering(tmp_path):
    """``bytes.splitlines()`` breaks only on \\n, \\r, \\r\\n -- a stray
    \\x0b inside a field must not be treated as a line break the way
    ``str.splitlines()`` would."""
    path = _write(
        tmp_path,
        "vtab.txt",
        [
            HEADER_ROW,
            _summary_row(),
            _order_row(**{"order-id": "ORD-1", "marketplace-name": "Amazon.in\x0bExtra"}),
            _order_row(**{"order-id": "ORD-2", "posted-date": "2026-08-17"}),
        ],
    )
    result = parse_settlement_file(path)

    assert result.quarantined == ()
    assert len(result.lines) == 2
    assert result.lines[0].line_id == f"{path.name}:3"
    assert result.lines[1].line_id == f"{path.name}:4"


# --------------------------------------------------------------------------- #
# S3: per-file separator detection falls back to a transaction row, not
# straight to '.', when the summary row's total-amount is unreadable.
# --------------------------------------------------------------------------- #


def test_separator_detected_from_transaction_row_when_summary_amount_unreadable(tmp_path):
    """The reviewer's exact probe: summary total-amount is unreadable, the
    transaction row is comma-decimal. Only row 2 quarantines; the transaction
    row parses under the separator detected from itself, not '.'."""
    path = _write(
        tmp_path,
        "sep.txt",
        [HEADER_ROW, _summary_row(**{"total-amount": "oops"}), _order_row(amount="100,00")],
    )
    result = parse_settlement_file(path)

    assert result.header is None
    assert result.quarantined == (_q(path.name, 2, amount_not_numeric("oops")),)
    assert len(result.lines) == 1
    assert result.lines[0].line_id == f"{path.name}:3"
    assert result.lines[0].amount_paise == 10000


# --------------------------------------------------------------------------- #
# S4: a leading UTF-8 BOM does not turn a valid file into "unknown header
# layout".
# --------------------------------------------------------------------------- #


def test_bom_valid_settlement_file_parses_with_no_quarantine(tmp_path):
    content = ("﻿" + HEADER_ROW + "\n" + _summary_row() + "\n" + _order_row() + "\n").encode("utf-8")
    path = tmp_path / "bom.txt"
    path.write_bytes(content)

    result = parse_settlement_file(path)

    assert result.quarantined == ()
    assert result.hint is None
    assert result.header is not None
    assert len(result.lines) == 1


# --------------------------------------------------------------------------- #
# S5: a trailing tab on every row still quarantines on column count, but the
# hint names the actual cause.
# --------------------------------------------------------------------------- #


def test_trailing_tab_on_every_row_names_the_cause_in_the_hint(tmp_path):
    rows = [HEADER_ROW + "\t", _summary_row() + "\t", _order_row() + "\t"]
    path = _write(tmp_path, "trailingtab.txt", rows)

    result = parse_settlement_file(path)

    assert result.hint == TRAILING_TAB_HINT
    assert result.header is None
    assert result.lines == ()
    assert len(result.quarantined) == 3
    for q in result.quarantined:
        assert q.reason == column_count(24, 25, "tab")


# --------------------------------------------------------------------------- #
# S6: blank lines are skipped, never quarantined, and physical numbering
# survives them.
# --------------------------------------------------------------------------- #


def test_blank_lines_are_skipped_and_physical_numbering_is_preserved(tmp_path):
    rows = [
        HEADER_ROW,
        _summary_row(),
        _order_row(**{"order-id": "ORD-1"}),
        "",  # interior blank line
        _order_row(**{"order-id": "ORD-2", "posted-date": "2026-08-17"}),
        "",  # trailing blank line
    ]
    path = _write(tmp_path, "blank.txt", rows)

    result = parse_settlement_file(path)

    assert result.quarantined == ()
    assert len(result.lines) == 2
    assert result.lines[0].line_id == f"{path.name}:3"
    assert result.lines[1].line_id == f"{path.name}:5"


# --------------------------------------------------------------------------- #
# G5: a data row of 24 empty tab-separated fields is malformed, not blank --
# matching orders.py's documented rule for its own comma-separated case
# instead of vanishing from the D7 denominator.
# --------------------------------------------------------------------------- #


def test_all_empty_data_row_is_malformed_not_blank(tmp_path):
    all_empty_row = "\t".join("" for _ in SETTLEMENT_COLUMNS)
    path = _write(
        tmp_path,
        "allempty.txt",
        [HEADER_ROW, _summary_row(), all_empty_row, _order_row(**{"order-id": "ORD-2"})],
    )

    result = parse_settlement_file(path)

    assert result.quarantined == (_q(path.name, 3, amount_not_numeric("")),)
    assert len(result.lines) == 1
    assert result.lines[0].line_id == f"{path.name}:4"


# --------------------------------------------------------------------------- #
# S7: a missing summary row must not eat the first real transaction row.
# --------------------------------------------------------------------------- #


def test_missing_summary_row_parses_every_row_from_two_onward_as_a_transaction(tmp_path):
    rows = [
        HEADER_ROW,
        _order_row(**{"order-id": "ORD-1"}),
        _order_row(**{"order-id": "ORD-2", "posted-date": "2026-08-17"}),
    ]
    path = _write(tmp_path, "nosummary.txt", rows)

    result = parse_settlement_file(path)

    assert result.header is None
    assert result.quarantined == ()
    assert result.hint == SUMMARY_ROW_MISSING_HINT
    assert len(result.lines) == 2
    assert result.lines[0].line_id == f"{path.name}:2"
    assert result.lines[1].line_id == f"{path.name}:3"


# --------------------------------------------------------------------------- #
# S10(a): line_id stays physical after a quarantined middle row.
# --------------------------------------------------------------------------- #


def test_line_id_stays_physical_after_a_quarantined_middle_row(tmp_path):
    rows = [
        HEADER_ROW,
        _summary_row(),
        _order_row(**{"order-id": "ORD-1"}),
        _order_row(**{"amount": "not-a-number", "order-id": "ORD-BAD"}),
        _order_row(**{"order-id": "ORD-2", "posted-date": "2026-08-17"}),
    ]
    path = _write(tmp_path, "midbad.txt", rows)

    result = parse_settlement_file(path)

    assert result.quarantined == (_q(path.name, 4, amount_not_numeric("not-a-number")),)
    assert len(result.lines) == 2
    assert result.lines[0].line_id == f"{path.name}:3"
    assert result.lines[1].line_id == f"{path.name}:5"


# --------------------------------------------------------------------------- #
# S10(b): end-to-end comma-decimal file through parse_settlement_file, not
# just the parsing-helper unit tests.
# --------------------------------------------------------------------------- #


def test_comma_decimal_file_parses_end_to_end(tmp_path):
    rows = [
        HEADER_ROW,
        _summary_row(**{"total-amount": "1234,50"}),
        _order_row(amount="500,00"),
    ]
    path = _write(tmp_path, "comma.txt", rows)

    result = parse_settlement_file(path)

    assert result.quarantined == ()
    assert result.header is not None
    assert result.header.total_amount_paise == 123450
    assert len(result.lines) == 1
    assert result.lines[0].amount_paise == 50000


def _q(source_file: str, row: int, reason: str) -> QuarantinedRow:
    return QuarantinedRow(line_id=make_line_id(source_file, row), reason=reason)
