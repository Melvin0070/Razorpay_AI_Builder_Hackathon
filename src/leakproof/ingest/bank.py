"""Bank CSV parser (companion format, docs/specs/amazon-settlement-v2.md
"Companion inputs"): ``date, utr, amount, narration``. Same quarantine
discipline. Unlike the settlement file, the amount's decimal separator is
not a per-file trap here (project convention, not an Amazon export), so it
is always parsed with ``.``.
"""

from __future__ import annotations

import csv
import io
from pathlib import Path

from leakproof.contract import make_line_id
from leakproof.ingest.parsing import parse_decimal_amount, parse_flexible_date
from leakproof.ingest.reasons import amount_not_numeric, bad_date, column_count, missing_field
from leakproof.types import BankCredit, BankParse, QuarantinedRow

BANK_COLUMNS: tuple[str, ...] = ("date", "utr", "amount", "narration")


def parse_bank(path: Path) -> BankParse:
    source_file = path.name
    rows = list(csv.reader(io.StringIO(path.read_text(encoding="utf-8"))))
    quarantined: list[QuarantinedRow] = []
    credits: list[BankCredit] = []

    if not rows:
        return BankParse(source_file=source_file, credits=(), quarantined=(), hint=None)

    if len(rows[0]) != len(BANK_COLUMNS):
        quarantined.append(
            QuarantinedRow(
                line_id=make_line_id(source_file, 1),
                reason=column_count(len(BANK_COLUMNS), len(rows[0]), "comma"),
            )
        )

    for physical_row, row in enumerate(rows[1:], start=2):
        line_id = make_line_id(source_file, physical_row)

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
