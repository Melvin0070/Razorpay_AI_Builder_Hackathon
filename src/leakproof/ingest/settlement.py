"""Amazon Settlement Flat File V2 parser (D4, D7; docs/specs/amazon-settlement-v2.md).

Quarantine, never raise: every malformed row is kept with a stable, exact
reason string and a line_id citing its physical row (header is row 1, per
``contract.make_line_id``). Unknown ``amount-description`` /
``transaction-type`` values are NOT quarantined -- they classify to
``LineKind.UNCLASSIFIED`` / ``TransactionType.OTHER`` with the raw string
kept on the line (D4); only structurally malformed rows are quarantined.
"""

from __future__ import annotations

from pathlib import Path

from leakproof.contract import TransactionType, classify_line, classify_transaction, make_line_id
from leakproof.ingest.parsing import (
    detect_separator,
    parse_decimal_amount,
    parse_flexible_date,
    parse_plain_int,
)
from leakproof.ingest.reasons import (
    amount_not_numeric,
    bad_date,
    column_count,
    missing_order_id_on_order_row,
    quantity_not_numeric,
    unknown_header_layout,
)
from leakproof.types import QuarantinedRow, SettlementFileParse, SettlementHeader, SettlementLine

#: The 24 columns, in order (spec "Columns" section).
SETTLEMENT_COLUMNS: tuple[str, ...] = (
    "settlement-id",
    "settlement-start-date",
    "settlement-end-date",
    "deposit-date",
    "total-amount",
    "currency",
    "transaction-type",
    "order-id",
    "merchant-order-id",
    "adjustment-id",
    "shipment-id",
    "marketplace-name",
    "amount-type",
    "amount-description",
    "amount",
    "fulfillment-id",
    "posted-date",
    "posted-date-time",
    "order-item-code",
    "merchant-order-item-id",
    "merchant-adjustment-item-id",
    "sku",
    "quantity-purchased",
    "promotion-id",
)

#: Wireframe frame 4, "Nothing parsed": every row saved as CSV has one column.
CSV_HINT = "the file was saved as CSV; Amazon Settlement Flat File V2 is tab-separated"


def _header_missing_hint() -> str:
    return (
        "no valid header row found; Amazon Settlement Flat File V2 begins "
        f"with '{SETTLEMENT_COLUMNS[0]}'"
    )


def parse_settlement_file(path: Path) -> SettlementFileParse:
    source_file = path.name
    rows = path.read_text(encoding="utf-8").splitlines()

    if not rows:
        return SettlementFileParse(
            source_file=source_file,
            header=None,
            lines=(),
            quarantined=(),
            hint=_header_missing_hint(),
        )

    all_single_column = all(len(r.split("\t")) == 1 for r in rows)
    quarantined: list[QuarantinedRow] = []

    # Row 1: header layout, validated against the 24 column names. Tracked
    # separately from the parsed summary row below -- "header" in the brief's
    # hint rule ("missing or unknown") means *this* row, not SettlementHeader.
    header_fields = rows[0].split("\t")
    header_row_ok = tuple(header_fields) == SETTLEMENT_COLUMNS
    if len(header_fields) != 24:
        quarantined.append(
            QuarantinedRow(
                line_id=make_line_id(source_file, 1),
                reason=column_count(24, len(header_fields), "tab"),
            )
        )
    elif not header_row_ok:
        quarantined.append(
            QuarantinedRow(line_id=make_line_id(source_file, 1), reason=unknown_header_layout())
        )

    # Row 2: summary -> SettlementHeader, and the file's decimal separator
    # (detected from total-amount regardless of whether the rest of the row
    # is otherwise well-formed, so downstream lines still parse correctly).
    header: SettlementHeader | None = None
    separator = "."
    if len(rows) >= 2:
        summary_fields = rows[1].split("\t")
        total_amount_raw = summary_fields[4] if len(summary_fields) >= 5 else ""
        separator = detect_separator(total_amount_raw) or "."

        if len(summary_fields) != 24:
            quarantined.append(
                QuarantinedRow(
                    line_id=make_line_id(source_file, 2),
                    reason=column_count(24, len(summary_fields), "tab"),
                )
            )
        else:
            start_date = parse_flexible_date(summary_fields[1])
            end_date = parse_flexible_date(summary_fields[2])
            deposit_date = parse_flexible_date(summary_fields[3])
            total_amount_paise = parse_decimal_amount(summary_fields[4], separator)
            reason: str | None = None
            if start_date is None:
                reason = bad_date("settlement-start-date", summary_fields[1])
            elif end_date is None:
                reason = bad_date("settlement-end-date", summary_fields[2])
            elif deposit_date is None:
                reason = bad_date("deposit-date", summary_fields[3])
            elif total_amount_paise is None:
                reason = amount_not_numeric(summary_fields[4])
            if reason is not None:
                quarantined.append(
                    QuarantinedRow(line_id=make_line_id(source_file, 2), reason=reason)
                )
            else:
                assert start_date is not None
                assert end_date is not None
                assert deposit_date is not None
                assert total_amount_paise is not None
                header = SettlementHeader(
                    settlement_id=summary_fields[0].strip(),
                    start_date=start_date,
                    end_date=end_date,
                    deposit_date=deposit_date,
                    total_amount_paise=total_amount_paise,
                    currency=summary_fields[5].strip(),
                    source_line_id=make_line_id(source_file, 2),
                )

    # Rows 3+: transaction lines.
    lines: list[SettlementLine] = []
    for physical_row, raw in enumerate(rows[2:], start=3):
        fields = raw.split("\t")
        line_id = make_line_id(source_file, physical_row)

        if len(fields) != 24:
            quarantined.append(
                QuarantinedRow(line_id=line_id, reason=column_count(24, len(fields), "tab"))
            )
            continue

        amount_paise = parse_decimal_amount(fields[14], separator)
        if amount_paise is None:
            quarantined.append(
                QuarantinedRow(line_id=line_id, reason=amount_not_numeric(fields[14]))
            )
            continue

        posted_date = parse_flexible_date(fields[16])
        if posted_date is None:
            quarantined.append(
                QuarantinedRow(line_id=line_id, reason=bad_date("posted-date", fields[16]))
            )
            continue

        txn_type = classify_transaction(fields[6])
        order_id = fields[7].strip() or None
        if txn_type is TransactionType.ORDER and not order_id:
            quarantined.append(
                QuarantinedRow(line_id=line_id, reason=missing_order_id_on_order_row())
            )
            continue

        quantity_raw = fields[22].strip()
        quantity: int | None = None
        if quantity_raw:
            quantity = parse_plain_int(quantity_raw)
            if quantity is None:
                quarantined.append(
                    QuarantinedRow(line_id=line_id, reason=quantity_not_numeric(quantity_raw))
                )
                continue

        lines.append(
            SettlementLine(
                line_id=line_id,
                settlement_id=fields[0].strip(),
                txn_type=txn_type,
                kind=classify_line(fields[12], fields[13]),
                amount_type=fields[12],
                amount_description=fields[13],
                amount_paise=amount_paise,
                posted_date=posted_date,
                order_id=order_id,
                sku=fields[21].strip() or None,
                quantity=quantity,
                adjustment_id=fields[9].strip() or None,
                transaction_type_raw=fields[6],
            )
        )

    hint: str | None = None
    if all_single_column:
        hint = CSV_HINT
    elif not header_row_ok:
        hint = _header_missing_hint()

    return SettlementFileParse(
        source_file=source_file,
        header=header,
        lines=tuple(lines),
        quarantined=tuple(quarantined),
        hint=hint,
    )
