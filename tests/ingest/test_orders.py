"""Seller orders CSV parser tests (companion format). Lane D · issue #7."""

from __future__ import annotations

from pathlib import Path

from leakproof.contract import RefundInitiator, make_line_id
from leakproof.ingest.orders import ORDERS_COLUMNS, parse_orders
from leakproof.ingest.reasons import (
    DELIVERY_BEFORE_ORDER,
    amount_not_numeric,
    bad_date,
    column_count,
    missing_field,
    quantity_not_numeric,
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
