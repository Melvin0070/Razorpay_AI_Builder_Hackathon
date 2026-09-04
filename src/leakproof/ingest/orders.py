"""Seller orders CSV parser (companion format, docs/specs/amazon-settlement-v2.md
"Companion inputs"). Same quarantine discipline as the settlement parser.

``principal_paise`` / ``tax_paise`` are already integer paise (the column
names say so), not rupee-decimal strings like the settlement file's
``amount`` -- so they parse as plain integers, never through the
decimal-separator path.
"""

from __future__ import annotations

import csv
import io
from pathlib import Path

from leakproof.contract import RefundInitiator, make_line_id
from leakproof.ingest.parsing import parse_flexible_date, parse_plain_int
from leakproof.ingest.reasons import (
    DELIVERY_BEFORE_ORDER,
    amount_not_numeric,
    bad_date,
    column_count,
    missing_field,
    quantity_not_numeric,
    unknown_refund_initiated_by,
)
from leakproof.types import Order, OrdersParse, QuarantinedRow

ORDERS_COLUMNS: tuple[str, ...] = (
    "order_id",
    "sku",
    "category_id",
    "quantity",
    "principal_paise",
    "tax_paise",
    "order_date",
    "delivery_date",
    "refund_initiated_by",
)

_REFUND_INITIATORS: dict[str, RefundInitiator] = {r.value: r for r in RefundInitiator}


def parse_orders(path: Path) -> OrdersParse:
    source_file = path.name
    rows = list(csv.reader(io.StringIO(path.read_text(encoding="utf-8"))))
    quarantined: list[QuarantinedRow] = []
    orders: list[Order] = []

    if not rows:
        return OrdersParse(source_file=source_file, orders=(), quarantined=(), hint=None)

    if len(rows[0]) != len(ORDERS_COLUMNS):
        quarantined.append(
            QuarantinedRow(
                line_id=make_line_id(source_file, 1),
                reason=column_count(len(ORDERS_COLUMNS), len(rows[0]), "comma"),
            )
        )

    for physical_row, row in enumerate(rows[1:], start=2):
        line_id = make_line_id(source_file, physical_row)

        if len(row) != len(ORDERS_COLUMNS):
            quarantined.append(
                QuarantinedRow(
                    line_id=line_id, reason=column_count(len(ORDERS_COLUMNS), len(row), "comma")
                )
            )
            continue

        order_id = row[0].strip()
        if not order_id:
            quarantined.append(QuarantinedRow(line_id=line_id, reason=missing_field("order_id")))
            continue

        quantity_raw = row[3].strip()
        quantity = parse_plain_int(quantity_raw)
        if quantity is None:
            quarantined.append(
                QuarantinedRow(line_id=line_id, reason=quantity_not_numeric(quantity_raw))
            )
            continue

        principal_raw = row[4].strip()
        principal_paise = parse_plain_int(principal_raw)
        if principal_paise is None:
            quarantined.append(
                QuarantinedRow(line_id=line_id, reason=amount_not_numeric(principal_raw))
            )
            continue

        tax_raw = row[5].strip()
        tax_paise = parse_plain_int(tax_raw)
        if tax_paise is None:
            quarantined.append(QuarantinedRow(line_id=line_id, reason=amount_not_numeric(tax_raw)))
            continue

        order_date_raw = row[6].strip()
        order_date = parse_flexible_date(order_date_raw)
        if order_date is None:
            quarantined.append(
                QuarantinedRow(line_id=line_id, reason=bad_date("order_date", order_date_raw))
            )
            continue

        # Empty delivery_date is not an error -- it means "not yet delivered".
        delivery_date_raw = row[7].strip()
        delivery_date = None
        if delivery_date_raw:
            delivery_date = parse_flexible_date(delivery_date_raw)
            if delivery_date is None:
                quarantined.append(
                    QuarantinedRow(
                        line_id=line_id, reason=bad_date("delivery_date", delivery_date_raw)
                    )
                )
                continue
            if delivery_date < order_date:
                quarantined.append(QuarantinedRow(line_id=line_id, reason=DELIVERY_BEFORE_ORDER))
                continue

        refund_raw = row[8].strip()
        refund_initiated_by = _REFUND_INITIATORS.get(refund_raw.lower())
        if refund_initiated_by is None:
            quarantined.append(
                QuarantinedRow(line_id=line_id, reason=unknown_refund_initiated_by(refund_raw))
            )
            continue

        orders.append(
            Order(
                order_id=order_id,
                sku=row[1].strip(),
                category_id=row[2].strip(),
                quantity=quantity,
                principal_paise=principal_paise,
                tax_paise=tax_paise,
                order_date=order_date,
                delivery_date=delivery_date,
                refund_initiated_by=refund_initiated_by,
                source_line_id=line_id,
            )
        )

    return OrdersParse(
        source_file=source_file, orders=tuple(orders), quarantined=tuple(quarantined), hint=None
    )
