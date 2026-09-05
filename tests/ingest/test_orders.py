"""Seller orders CSV parser tests (companion format). Lane D · issue #7."""

from __future__ import annotations

from pathlib import Path

from leakproof.contract import RefundInitiator, make_line_id
from leakproof.ingest.orders import ORDERS_COLUMNS, parse_orders
from leakproof.ingest.reasons import (
    DELIVERY_BEFORE_ORDER,
    NOT_PARSED_BAD_HEADER,
    NOT_VALID_UTF8,
    amount_not_numeric,
    bad_date,
    column_count,
    missing_field,
    principal_negative,
    quantity_not_numeric,
    quantity_not_positive,
    tax_negative,
    unknown_header_layout,
    unknown_refund_initiated_by,
)
from leakproof.types import QuarantinedRow

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "ingest"

HEADER_ROW = ",".join(ORDERS_COLUMNS)


def _row(**overrides: str) -> str:
    base = {
        "order_id": "ORD-1",
        "sku": "SKU-1",
        "category_id": "electronics-accessories",
        "quantity": "1",
        "principal_paise": "50000",
        "tax_paise": "2500",
        "order_date": "2026-08-10",
        "delivery_date": "2026-08-15",
        "refund_initiated_by": "none",
    }
    base.update(overrides)
    return ",".join(base[c] for c in ORDERS_COLUMNS)


def _write(tmp_path: Path, name: str, rows: list[str]) -> Path:
    path = tmp_path / name
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return path


def _q(source_file: str, row: int, reason: str) -> QuarantinedRow:
    return QuarantinedRow(line_id=make_line_id(source_file, row), reason=reason)


def test_golden_parse():
    result = parse_orders(FIXTURES / "orders_golden.csv")

    assert result.source_file == "orders_golden.csv"
    assert result.quarantined == ()
    assert result.hint is None
    assert len(result.orders) == 3

    first, second, third = result.orders
    assert first.order_id == "ORD-1"
    assert first.sku == "SKU-1"
    assert first.category_id == "electronics-accessories"
    assert first.quantity == 1
    assert first.principal_paise == 50000
    assert first.tax_paise == 2500
    assert first.order_date.isoformat() == "2026-08-10"
    assert first.delivery_date.isoformat() == "2026-08-15"
    assert first.refund_initiated_by is RefundInitiator.NONE
    assert first.source_line_id == "orders_golden.csv:2"

    # Empty delivery_date is not an error -- it means "not yet delivered".
    assert second.delivery_date is None
    assert second.source_line_id == "orders_golden.csv:3"

    assert third.refund_initiated_by is RefundInitiator.SELLER
    assert third.source_line_id == "orders_golden.csv:4"


def test_delivery_before_order_is_quarantined():
    result = parse_orders(FIXTURES / "orders_quarantine_delivery_before_order.csv")

    assert result.orders == ()
    assert result.quarantined == (
        _q("orders_quarantine_delivery_before_order.csv", 2, DELIVERY_BEFORE_ORDER),
    )


def test_column_count_mismatch(tmp_path):
    path = _write(tmp_path, "cc.csv", [HEADER_ROW, "ORD-1,SKU-1,electronics-accessories"])
    result = parse_orders(path)

    assert result.orders == ()
    assert result.quarantined == (_q(path.name, 2, column_count(9, 3, "comma")),)


def test_missing_order_id(tmp_path):
    path = _write(tmp_path, "noid.csv", [HEADER_ROW, _row(order_id="")])
    result = parse_orders(path)

    assert result.orders == ()
    assert result.quarantined == (_q(path.name, 2, missing_field("order_id")),)


def test_quantity_not_numeric(tmp_path):
    path = _write(tmp_path, "qty.csv", [HEADER_ROW, _row(quantity="one")])
    result = parse_orders(path)

    assert result.orders == ()
    assert result.quarantined == (_q(path.name, 2, quantity_not_numeric("one")),)


def test_principal_not_numeric(tmp_path):
    path = _write(tmp_path, "principal.csv", [HEADER_ROW, _row(principal_paise="500.00")])
    result = parse_orders(path)

    assert result.orders == ()
    assert result.quarantined == (_q(path.name, 2, amount_not_numeric("500.00")),)


def test_tax_not_numeric(tmp_path):
    path = _write(tmp_path, "tax.csv", [HEADER_ROW, _row(tax_paise="abc")])
    result = parse_orders(path)

    assert result.orders == ()
    assert result.quarantined == (_q(path.name, 2, amount_not_numeric("abc")),)


def test_bad_order_date(tmp_path):
    path = _write(tmp_path, "od.csv", [HEADER_ROW, _row(order_date="10-08-2026")])
    result = parse_orders(path)

    assert result.orders == ()
    assert result.quarantined == (_q(path.name, 2, bad_date("order_date", "10-08-2026")),)


def test_bad_delivery_date(tmp_path):
    path = _write(tmp_path, "dd.csv", [HEADER_ROW, _row(delivery_date="not-a-date")])
    result = parse_orders(path)

    assert result.orders == ()
    assert result.quarantined == (_q(path.name, 2, bad_date("delivery_date", "not-a-date")),)


def test_unknown_refund_initiated_by(tmp_path):
    path = _write(tmp_path, "refund.csv", [HEADER_ROW, _row(refund_initiated_by="courier")])
    result = parse_orders(path)

    assert result.orders == ()
    assert result.quarantined == (_q(path.name, 2, unknown_refund_initiated_by("courier")),)


# --------------------------------------------------------------------------- #
# S12: non-positive quantity, negative principal/tax.
# --------------------------------------------------------------------------- #


def test_quantity_not_positive(tmp_path):
    path = _write(tmp_path, "qty0.csv", [HEADER_ROW, _row(quantity="0")])
    result = parse_orders(path)

    assert result.orders == ()
    assert result.quarantined == (_q(path.name, 2, quantity_not_positive("0")),)


def test_quantity_negative_is_not_positive(tmp_path):
    path = _write(tmp_path, "qtyneg.csv", [HEADER_ROW, _row(quantity="-1")])
    result = parse_orders(path)

    assert result.orders == ()
    assert result.quarantined == (_q(path.name, 2, quantity_not_positive("-1")),)


def test_principal_negative(tmp_path):
    path = _write(tmp_path, "principalneg.csv", [HEADER_ROW, _row(principal_paise="-50000")])
    result = parse_orders(path)

    assert result.orders == ()
    assert result.quarantined == (_q(path.name, 2, principal_negative("-50000")),)


def test_tax_negative(tmp_path):
    path = _write(tmp_path, "taxneg.csv", [HEADER_ROW, _row(tax_paise="-2500")])
    result = parse_orders(path)

    assert result.orders == ()
    assert result.quarantined == (_q(path.name, 2, tax_negative("-2500")),)


# --------------------------------------------------------------------------- #
# S2: exact header-name match, not just column count. On mismatch nothing is
# parsed by guessed position.
# --------------------------------------------------------------------------- #


def test_swapped_header_columns_quarantines_header_and_every_data_row(tmp_path):
    """principal_paise and tax_paise swapped in the header: same column
    count, wrong names -- must not silently mis-assign money."""
    swapped = (
        "order_id,sku,category_id,quantity,tax_paise,principal_paise,"
        "order_date,delivery_date,refund_initiated_by"
    )
    path = _write(tmp_path, "swapped.csv", [swapped, _row(), _row(order_id="ORD-2")])

    result = parse_orders(path)

    assert result.orders == ()
    assert result.hint == "no valid header row found; the orders CSV begins with 'order_id'"
    assert result.quarantined[0] == _q(path.name, 1, unknown_header_layout())
    assert result.quarantined[1] == _q(path.name, 2, NOT_PARSED_BAD_HEADER)
    assert result.quarantined[2] == _q(path.name, 3, NOT_PARSED_BAD_HEADER)
    assert len(result.quarantined) == 3


def test_headerless_file_drops_no_row_from_the_denominator(tmp_path):
    """No header row at all: row 1 is real data, but it does not match the
    canonical column names, so it is quarantined like every other row --
    never silently treated as the header and dropped."""
    path = _write(tmp_path, "headerless.csv", [_row(order_id="ORD-1"), _row(order_id="ORD-2")])

    result = parse_orders(path)

    assert result.orders == ()
    assert result.hint == "no valid header row found; the orders CSV begins with 'order_id'"
    assert result.quarantined[0] == _q(path.name, 1, unknown_header_layout())
    assert result.quarantined[1] == _q(path.name, 2, NOT_PARSED_BAD_HEADER)
    assert len(result.quarantined) == 2


def test_correct_header_parses_normally(tmp_path):
    path = _write(tmp_path, "correct.csv", [HEADER_ROW, _row()])
    result = parse_orders(path)

    assert result.hint is None
    assert result.quarantined == ()
    assert len(result.orders) == 1


# --------------------------------------------------------------------------- #
# S1: undecodable bytes quarantine only their own row.
# --------------------------------------------------------------------------- #


def test_undecodable_byte_quarantines_only_that_row(tmp_path):
    bad_row = (
        _row(order_id="ORD-BAD", sku="PLACEHOLDER")
        .encode("utf-8")
        .replace(b"PLACEHOLDER", b"Caf\xe9")
    )
    good_row = _row(order_id="ORD-2").encode("utf-8")
    path = tmp_path / "badutf8.csv"
    path.write_bytes(b"\n".join([HEADER_ROW.encode(), bad_row, good_row]) + b"\n")

    result = parse_orders(path)

    assert result.quarantined == (_q(path.name, 2, NOT_VALID_UTF8),)
    assert len(result.orders) == 1
    assert result.orders[0].source_line_id == f"{path.name}:3"


# --------------------------------------------------------------------------- #
# S4: a leading UTF-8 BOM does not turn a valid file into "unknown header
# layout".
# --------------------------------------------------------------------------- #


def test_bom_valid_orders_file_parses_with_no_quarantine(tmp_path):
    content = ("﻿" + HEADER_ROW + "\n" + _row() + "\n").encode("utf-8")
    path = tmp_path / "bom.csv"
    path.write_bytes(content)

    result = parse_orders(path)

    assert result.quarantined == ()
    assert result.hint is None
    assert len(result.orders) == 1


# --------------------------------------------------------------------------- #
# S6: blank lines are skipped, never quarantined, and physical numbering
# survives them.
# --------------------------------------------------------------------------- #


def test_blank_lines_are_skipped_and_physical_numbering_is_preserved(tmp_path):
    rows = [
        HEADER_ROW,
        _row(order_id="ORD-1"),
        "",  # interior blank line
        _row(order_id="ORD-2"),
        "",  # trailing blank line
    ]
    path = _write(tmp_path, "blank.csv", rows)

    result = parse_orders(path)

    assert result.quarantined == ()
    assert len(result.orders) == 2
    assert result.orders[0].source_line_id == f"{path.name}:2"
    assert result.orders[1].source_line_id == f"{path.name}:4"


# --------------------------------------------------------------------------- #
# G1: a CR-only or CRLF file must parse like any other -- the salvage commit
# that swapped ``read_text`` for ``read_bytes().decode(...)`` dropped
# universal-newline translation, so a bare ``\r`` reached ``csv.reader``
# unrecognised as a line ending and the whole file raised ``_csv.Error``
# instead of quarantining a row.
# --------------------------------------------------------------------------- #


def test_cr_only_line_endings_parse_like_lf(tmp_path):
    content = (
        "\r".join([HEADER_ROW, _row(order_id="ORD-1"), _row(order_id="ORD-2")]) + "\r"
    ).encode("utf-8")
    path = tmp_path / "cr_only.csv"
    path.write_bytes(content)

    result = parse_orders(path)

    assert result.quarantined == ()
    assert len(result.orders) == 2
    assert result.orders[0].source_line_id == f"{path.name}:2"
    assert result.orders[1].source_line_id == f"{path.name}:3"


def test_crlf_line_endings_parse_like_lf(tmp_path):
    content = (
        "\r\n".join([HEADER_ROW, _row(order_id="ORD-1"), _row(order_id="ORD-2")]) + "\r\n"
    ).encode("utf-8")
    path = tmp_path / "crlf.csv"
    path.write_bytes(content)

    result = parse_orders(path)

    assert result.quarantined == ()
    assert len(result.orders) == 2
    assert result.orders[0].source_line_id == f"{path.name}:2"
    assert result.orders[1].source_line_id == f"{path.name}:3"
