"""Seller orders CSV parser (companion format, docs/specs/amazon-settlement-v2.md
"Companion inputs"). Same quarantine discipline as the settlement parser.

``principal_paise`` / ``tax_paise`` are already integer paise (the column
names say so), not rupee-decimal strings like the settlement file's
``amount`` -- so they parse as plain integers, never through the
decimal-separator path.

The header row is validated by exact name match, not just column count (S2):
on any mismatch nothing downstream is parsed by guessed position -- row 1 is
quarantined ``unknown header layout`` (or a column-count reason, mirroring
``settlement.py``'s own row-1 check) and every later row is quarantined
``not parsed: unknown header layout`` rather than silently mis-assigning a
swapped or shifted column.

Physical line numbers are tracked via ``csv.reader.line_num`` rather than a
plain ``enumerate`` counter (S9): a quoted field with an embedded newline
consumes more than one physical line for one logical CSV row, and
``line_num`` (read *before* each row is consumed) is what stays anchored to
what a text editor shows.
"""

from __future__ import annotations

import csv
import io
from pathlib import Path

from leakproof.contract import RefundInitiator, make_line_id
from leakproof.ingest.parsing import parse_flexible_date, parse_plain_int
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


def _header_missing_hint() -> str:
    return f"no valid header row found; the orders CSV begins with '{ORDERS_COLUMNS[0]}'"


def _has_undecodable_bytes(fields: list[str]) -> bool:
    """S1: true when any field of this row carries a lone surrogate left by
    ``errors="surrogateescape"`` -- i.e. this physical line was not valid
    UTF-8."""
    return any(0xDC80 <= ord(ch) <= 0xDCFF for field in fields for ch in field)


def _is_blank_row(row: list[str]) -> bool:
    """S6: a physical line empty after stripping whitespace. ``csv.reader``
    turns a genuinely blank line into ``[]``; a whitespace-only line into a
    single empty-after-strip field. A comma-separated row of empty fields
    (e.g. ``,,,``) is a malformed data row, not a blank line, and is left to
    the ordinary per-field checks below."""
    return not row or (len(row) == 1 and row[0].strip() == "")


def _read_physical_rows(text: str) -> list[tuple[int, list[str]]]:
    """``(physical_start_line, fields)`` per CSV row -- see module docstring, S9."""
    reader = csv.reader(io.StringIO(text))
    rows: list[tuple[int, list[str]]] = []
    while True:
        start = reader.line_num + 1
        try:
            row = next(reader)
        except StopIteration:
            break
        rows.append((start, row))
    return rows


def parse_orders(path: Path) -> OrdersParse:
    source_file = path.name
    text = path.read_bytes().decode("utf-8", errors="surrogateescape")
    text = text.removeprefix("﻿")  # S4: strip a leading BOM
    physical_rows = _read_physical_rows(text)

    quarantined: list[QuarantinedRow] = []
    orders: list[Order] = []

    if not physical_rows:
        return OrdersParse(source_file=source_file, orders=(), quarantined=(), hint=None)

    header_line, header_fields = physical_rows[0]
    header_row_ok = tuple(header_fields) == ORDERS_COLUMNS
    if len(header_fields) != len(ORDERS_COLUMNS):
        quarantined.append(
            QuarantinedRow(
                line_id=make_line_id(source_file, header_line),
                reason=column_count(len(ORDERS_COLUMNS), len(header_fields), "comma"),
            )
        )
    elif not header_row_ok:
        quarantined.append(
            QuarantinedRow(
                line_id=make_line_id(source_file, header_line), reason=unknown_header_layout()
            )
        )

    if not header_row_ok:
        # S2: nothing is parsed by guessed position once the header itself
        # cannot be trusted -- every later row is quarantined uniformly.
        for physical_row, row in physical_rows[1:]:
            if _is_blank_row(row):
                continue
            quarantined.append(
                QuarantinedRow(
                    line_id=make_line_id(source_file, physical_row), reason=NOT_PARSED_BAD_HEADER
                )
            )
        return OrdersParse(
            source_file=source_file,
            orders=(),
            quarantined=tuple(quarantined),
            hint=_header_missing_hint(),
        )

    for physical_row, row in physical_rows[1:]:
        if _is_blank_row(row):
            continue  # S6

        line_id = make_line_id(source_file, physical_row)

        if _has_undecodable_bytes(row):
            quarantined.append(QuarantinedRow(line_id=line_id, reason=NOT_VALID_UTF8))
            continue

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
        if quantity <= 0:
            quarantined.append(
                QuarantinedRow(line_id=line_id, reason=quantity_not_positive(quantity_raw))
            )
            continue

        principal_raw = row[4].strip()
        principal_paise = parse_plain_int(principal_raw)
        if principal_paise is None:
            quarantined.append(
                QuarantinedRow(line_id=line_id, reason=amount_not_numeric(principal_raw))
            )
            continue
        if principal_paise < 0:
            quarantined.append(
                QuarantinedRow(line_id=line_id, reason=principal_negative(principal_raw))
            )
            continue

        tax_raw = row[5].strip()
        tax_paise = parse_plain_int(tax_raw)
        if tax_paise is None:
            quarantined.append(QuarantinedRow(line_id=line_id, reason=amount_not_numeric(tax_raw)))
            continue
        if tax_paise < 0:
            quarantined.append(QuarantinedRow(line_id=line_id, reason=tax_negative(tax_raw)))
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
