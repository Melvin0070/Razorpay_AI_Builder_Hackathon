"""Bank CSV parser (companion format, docs/specs/amazon-settlement-v2.md
"Companion inputs"): ``date, utr, amount, narration``. Same quarantine
discipline. Unlike the settlement file, the amount's decimal separator is
not a per-file trap here (project convention, not an Amazon export), so it
is always parsed with ``.``.

The header row is validated by exact name match, not just column count (S2);
see ``orders.py`` for the shared rationale and S9's physical-line tracking
(a narration field can embed a newline when quoted).
"""

from __future__ import annotations

import csv
import io
from pathlib import Path

from leakproof.contract import make_line_id
from leakproof.ingest.parsing import parse_decimal_amount, parse_flexible_date
from leakproof.ingest.reasons import (
    NOT_PARSED_BAD_HEADER,
    NOT_VALID_UTF8,
    amount_not_numeric,
    bad_date,
    column_count,
    missing_field,
    unknown_header_layout,
)
from leakproof.types import BankCredit, BankParse, QuarantinedRow

BANK_COLUMNS: tuple[str, ...] = ("date", "utr", "amount", "narration")


def _header_missing_hint() -> str:
    return f"no valid header row found; the bank CSV begins with '{BANK_COLUMNS[0]}'"


def _has_undecodable_bytes(fields: list[str]) -> bool:
    """S1: see ``orders.py``."""
    return any(0xDC80 <= ord(ch) <= 0xDCFF for field in fields for ch in field)


def _is_blank_row(row: list[str]) -> bool:
    """S6: see ``orders.py``."""
    return not row or (len(row) == 1 and row[0].strip() == "")


def _read_physical_rows(text: str) -> list[tuple[int, list[str]]]:
    """``(physical_start_line, fields)`` per CSV row -- see ``orders.py``, S9
    and G1 for why ``newline=""`` on the ``StringIO`` is load-bearing."""
    reader = csv.reader(io.StringIO(text, newline=""))
    rows: list[tuple[int, list[str]]] = []
    while True:
        start = reader.line_num + 1
        try:
            row = next(reader)
        except StopIteration:
            break
        rows.append((start, row))
    return rows


def parse_bank(path: Path) -> BankParse:
    source_file = path.name
    text = path.read_bytes().decode("utf-8", errors="surrogateescape")
    text = text.removeprefix("﻿")  # S4: strip a leading BOM
    physical_rows = _read_physical_rows(text)

    quarantined: list[QuarantinedRow] = []
    credits: list[BankCredit] = []

    if not physical_rows:
        return BankParse(source_file=source_file, credits=(), quarantined=(), hint=None)

    header_line, header_fields = physical_rows[0]
    header_row_ok = tuple(header_fields) == BANK_COLUMNS
    if len(header_fields) != len(BANK_COLUMNS):
        quarantined.append(
            QuarantinedRow(
                line_id=make_line_id(source_file, header_line),
                reason=column_count(len(BANK_COLUMNS), len(header_fields), "comma"),
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
        return BankParse(
            source_file=source_file,
            credits=(),
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

        if len(row) != len(BANK_COLUMNS):
            quarantined.append(
                QuarantinedRow(
                    line_id=line_id, reason=column_count(len(BANK_COLUMNS), len(row), "comma")
                )
            )
            continue

        date_raw = row[0].strip()
        credit_date = parse_flexible_date(date_raw)
        if credit_date is None:
            quarantined.append(QuarantinedRow(line_id=line_id, reason=bad_date("date", date_raw)))
            continue

        utr = row[1].strip()
        if not utr:
            quarantined.append(QuarantinedRow(line_id=line_id, reason=missing_field("utr")))
            continue

        amount_raw = row[2].strip()
        amount_paise = parse_decimal_amount(amount_raw, ".")
        if amount_paise is None:
            quarantined.append(
                QuarantinedRow(line_id=line_id, reason=amount_not_numeric(amount_raw))
            )
            continue

        credits.append(
            BankCredit(
                line_id=line_id,
                credit_date=credit_date,
                utr=utr,
                amount_paise=amount_paise,
                narration=row[3],
            )
        )

    return BankParse(
        source_file=source_file, credits=tuple(credits), quarantined=tuple(quarantined), hint=None
    )
