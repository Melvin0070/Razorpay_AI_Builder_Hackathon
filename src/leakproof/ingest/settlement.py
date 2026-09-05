"""Amazon Settlement Flat File V2 parser (D4, D7; docs/specs/amazon-settlement-v2.md).

Quarantine, never raise: every malformed row is kept with a stable, exact
reason string and a line_id citing its physical row (header is row 1, per
``contract.make_line_id``). Unknown ``amount-description`` /
``transaction-type`` values are NOT quarantined -- they classify to
``LineKind.UNCLASSIFIED`` / ``TransactionType.OTHER`` with the raw string
kept on the line (D4); only structurally malformed rows are quarantined.

Physical lines are read as bytes and split with ``bytes.splitlines()``, not
``str.splitlines()`` -- the latter also breaks on ``\\v``, ``\\f``, U+001C-U+001E
and U+0085, which would shift every later line_id off what a text editor
shows (S9's sibling trap for this file). Each physical line is then decoded on
its own with ``errors="surrogateescape"``: an undecodable byte becomes a lone
surrogate (U+DC80-U+DCFF) rather than raising, so one bad row (S1, e.g. an
Excel re-save as Windows-1252) quarantines only that row -- the rest of the
file still parses.
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

#: S5: every row has exactly one extra, empty, trailing tab-separated field --
#: the file was re-saved with a stray trailing tab on every line, not
#: genuinely malformed.
TRAILING_TAB_HINT = (
    "every row has one extra empty column: a trailing tab; "
    "Amazon Settlement Flat File V2 has 24 tab-separated columns"
)

#: S7: row 2 carries a non-empty ``transaction-type``, so it is a transaction
#: row, not the summary -- the summary row itself is missing from the file.
SUMMARY_ROW_MISSING_HINT = "summary row missing: row 2 is a transaction row"


def _header_missing_hint() -> str:
    return (
        "no valid header row found; Amazon Settlement Flat File V2 begins "
        f"with '{SETTLEMENT_COLUMNS[0]}'"
    )


def _has_undecodable_bytes(s: str) -> bool:
    """True when ``s`` contains a lone surrogate left by
    ``errors="surrogateescape"`` -- i.e. this physical line was not valid
    UTF-8 (S1)."""
    return any(0xDC80 <= ord(ch) <= 0xDCFF for ch in s)


def _is_blank(raw: str) -> bool:
    """S6: a physical line with no tab-separated content at all -- the raw
    string is empty once whitespace is stripped. A row of 24 *empty*
    tab-separated fields is a different thing (G5): it tab-splits to more
    than one field, so it is malformed data (every per-field check below
    will quarantine it, typically on the empty ``amount``), matching
    ``orders.py``'s documented rule for its own comma-separated case rather
    than silently vanishing from the D7 denominator."""
    fields = raw.split("\t")
    return len(fields) == 1 and fields[0].strip() == ""


def _all_rows_have_trailing_tab(non_blank_rows: list[str]) -> bool:
    if not non_blank_rows:
        return False
    return all(len(r.split("\t")) == 25 and r.split("\t")[-1] == "" for r in non_blank_rows)


def _detect_file_separator(summary_amount_raw: str | None, transaction_rows: list[str]) -> str:
    """S3: detect from the summary row's ``total-amount`` first; if that
    yields nothing (missing, unreadable, or the summary row itself is
    missing/malformed), from the first transaction row whose ``amount``
    contains ``.`` or ``,``; only then default to ``.``."""
    if summary_amount_raw is not None:
        separator = detect_separator(summary_amount_raw)
        if separator is not None:
            return separator
    for raw in transaction_rows:
        if _is_blank(raw) or _has_undecodable_bytes(raw):
            continue
        fields = raw.split("\t")
        if len(fields) < 15:
            continue
        candidate = fields[14]
        if "." in candidate or "," in candidate:
            separator = detect_separator(candidate)
            if separator is not None:
                return separator
    return "."


def parse_settlement_file(path: Path) -> SettlementFileParse:
    source_file = path.name
    byte_lines = path.read_bytes().splitlines()
    rows = [bl.decode("utf-8", errors="surrogateescape") for bl in byte_lines]
    if rows:
        rows[0] = rows[0].lstrip("﻿")  # S4: strip a leading BOM on row 1 only

    if not rows:
        return SettlementFileParse(
            source_file=source_file,
            header=None,
            lines=(),
            quarantined=(),
            hint=_header_missing_hint(),
        )

    non_blank_rows = [r for r in rows if not _is_blank(r)]
    all_single_column = bool(non_blank_rows) and all(
        len(r.split("\t")) == 1 for r in non_blank_rows
    )
    trailing_tab = _all_rows_have_trailing_tab(non_blank_rows)

    quarantined: list[QuarantinedRow] = []

    # Row 1: header layout, validated against the 24 column names. Tracked
    # separately from the parsed summary row below -- "header" in the brief's
    # hint rule ("missing or unknown") means *this* row, not SettlementHeader.
    row1 = rows[0]
    header_row_ok = False
    header_cascade = False
    if _has_undecodable_bytes(row1):
        quarantined.append(
            QuarantinedRow(line_id=make_line_id(source_file, 1), reason=NOT_VALID_UTF8)
        )
    else:
        header_fields = row1.split("\t")
        header_row_ok = tuple(header_fields) == SETTLEMENT_COLUMNS
        if len(header_fields) != 24:
            quarantined.append(
                QuarantinedRow(
                    line_id=make_line_id(source_file, 1),
                    reason=column_count(24, len(header_fields), "tab"),
                )
            )
        elif not header_row_ok:
            # G2: 24 fields, all present, but not the canonical names in the
            # canonical order (e.g. total-amount/amount transposed) -- row 1
            # alone cannot say *which* columns moved where, so trusting the
            # fixed offsets below would silently emit a wrong amount or the
            # wrong date under a still-plausible-looking parse. Cascade
            # exactly like orders.py/bank.py do for their own bad header,
            # gated on the count being right so this never fires for the
            # saved-as-CSV or trailing-tab files, whose column-count reason
            # is the real cause (S5) and must stay the hint (wireframe
            # frame 4 renders it verbatim).
            header_cascade = True
            quarantined.append(
                QuarantinedRow(line_id=make_line_id(source_file, 1), reason=unknown_header_layout())
            )

    if header_cascade:
        for physical_row, raw in enumerate(rows[1:], start=2):
            if _is_blank(raw):
                continue
            quarantined.append(
                QuarantinedRow(
                    line_id=make_line_id(source_file, physical_row), reason=NOT_PARSED_BAD_HEADER
                )
            )
        return SettlementFileParse(
            source_file=source_file,
            header=None,
            lines=(),
            quarantined=tuple(quarantined),
            hint=_header_missing_hint(),
        )

    # Row 2: is it really the summary row, or (S7) a transaction row because
    # the summary is missing from the file? A non-empty transaction-type in
    # what should be an all-blank-but-for-five-fields summary row is the tell.
    row2_raw = rows[1] if len(rows) >= 2 else None
    row2_blank = row2_raw is not None and _is_blank(row2_raw)
    row2_bad_utf8 = row2_raw is not None and not row2_blank and _has_undecodable_bytes(row2_raw)
    row2_is_transaction = False
    if row2_raw is not None and not row2_blank and not row2_bad_utf8:
        row2_fields = row2_raw.split("\t")
        if len(row2_fields) >= 7 and row2_fields[6].strip() != "":
            row2_is_transaction = True

    summary_missing_hint: str | None = None
    summary_amount_raw: str | None = None
    if row2_is_transaction:
        summary_missing_hint = SUMMARY_ROW_MISSING_HINT
        transaction_slice = list(enumerate(rows[1:], start=2))
    elif row2_raw is not None and not row2_blank and not row2_bad_utf8:
        summary_fields = row2_raw.split("\t")
        summary_amount_raw = summary_fields[4] if len(summary_fields) >= 5 else None
        transaction_slice = list(enumerate(rows[2:], start=3))
    else:
        transaction_slice = list(enumerate(rows[2:], start=3))

    separator = _detect_file_separator(
        summary_amount_raw,
        [raw for _, raw in transaction_slice] if row2_is_transaction else rows[2:],
    )

    header: SettlementHeader | None = None
    if not row2_is_transaction and row2_raw is not None and not row2_blank:
        if row2_bad_utf8:
            quarantined.append(
                QuarantinedRow(line_id=make_line_id(source_file, 2), reason=NOT_VALID_UTF8)
            )
        else:
            summary_fields = row2_raw.split("\t")
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

    # Transaction lines: rows 3+ normally, or rows 2+ under S7.
    lines: list[SettlementLine] = []
    for physical_row, raw in transaction_slice:
        if _is_blank(raw):
            continue  # S6: blank line, never quarantined; physical numbering unaffected

        line_id = make_line_id(source_file, physical_row)

        if _has_undecodable_bytes(raw):
            quarantined.append(QuarantinedRow(line_id=line_id, reason=NOT_VALID_UTF8))
            continue

        fields = raw.split("\t")
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
            if quantity <= 0:
                # G9: match orders.py -- a quantity that parses but is <= 0
                # is still not a real quantity.
                quarantined.append(
                    QuarantinedRow(line_id=line_id, reason=quantity_not_positive(quantity_raw))
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
    elif trailing_tab:
        hint = TRAILING_TAB_HINT
    elif summary_missing_hint is not None:
        hint = summary_missing_hint
    elif not header_row_ok:
        hint = _header_missing_hint()

    return SettlementFileParse(
        source_file=source_file,
        header=header,
        lines=tuple(lines),
        quarantined=tuple(quarantined),
        hint=hint,
    )
