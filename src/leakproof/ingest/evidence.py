"""Parser for the seller-authored evidence companion CSV."""

from __future__ import annotations

import csv
import io
from pathlib import Path

from leakproof.contract import EvidenceStatus, make_line_id
from leakproof.ingest.parsing import parse_flexible_date
from leakproof.types import EvidenceParse, EvidenceSupply, QuarantinedRow

_COLUMNS = ("order_id", "requirement", "status", "supplied_on")


def parse_evidence(path_or_text: Path | str, source_file: str | None = None) -> EvidenceParse:
    if isinstance(path_or_text, Path):
        source_file = source_file or path_or_text.name
        text = path_or_text.read_bytes().decode("utf-8", errors="surrogateescape")
    else:
        text = path_or_text
        source_file = source_file or "evidence.csv"
    rows = list(csv.reader(io.StringIO(text, newline="")))
    if not rows:
        return EvidenceParse(source_file, ())
    bad: list[QuarantinedRow] = []
    good: list[EvidenceSupply] = []
    if tuple(rows[0]) != _COLUMNS:
        bad.append(QuarantinedRow(make_line_id(source_file, 1), "unknown header layout"))
        bad.extend(
            QuarantinedRow(make_line_id(source_file, i), "not parsed: unknown header layout")
            for i, row in enumerate(rows[1:], 2)
            if row
        )
        return EvidenceParse(
            source_file,
            (),
            tuple(bad),
            "no valid header row found; the evidence CSV begins with 'order_id'",
        )
    for i, row in enumerate(rows[1:], 2):
        if not row or (len(row) == 1 and not row[0].strip()):
            continue
        line_id = make_line_id(source_file, i)
        if len(row) != 4:
            bad.append(
                QuarantinedRow(line_id, f"expected 4 comma-separated columns, found {len(row)}")
            )
            continue
        order_id, requirement, raw_status, raw_date = (
            row[0].strip(),
            row[1].strip(),
            row[2].strip(),
            row[3].strip(),
        )
        if not order_id:
            bad.append(QuarantinedRow(line_id, "missing order_id"))
            continue
        if not requirement:
            bad.append(QuarantinedRow(line_id, "missing requirement"))
            continue
        try:
            status = EvidenceStatus(raw_status)
        except ValueError:
            bad.append(QuarantinedRow(line_id, f"unknown status: {raw_status!r}"))
            continue
        supplied_on = parse_flexible_date(raw_date) if raw_date else None
        if raw_date and supplied_on is None:
            bad.append(QuarantinedRow(line_id, f"bad date in supplied_on: {raw_date!r}"))
            continue
        if status is EvidenceStatus.SATISFIED and supplied_on is None:
            bad.append(QuarantinedRow(line_id, "supplied_on required for status 'satisfied'"))
            continue
        if status is not EvidenceStatus.SATISFIED and raw_date:
            bad.append(QuarantinedRow(line_id, f"supplied_on forbidden for status {raw_status!r}"))
            continue
        good.append(EvidenceSupply(order_id, requirement, status, supplied_on, line_id))
    dupes = {
        (x.order_id, x.requirement)
        for x in good
        if sum((y.order_id, y.requirement) == (x.order_id, x.requirement) for y in good) > 1
    }
    if dupes:
        kept = []
        for item in good:
            if (item.order_id, item.requirement) in dupes:
                bad.append(
                    QuarantinedRow(
                        item.source_line_id,
                        f"duplicate evidence pair: {(item.order_id, item.requirement)!r}",
                    )
                )
            else:
                kept.append(item)
        good = kept
    return EvidenceParse(source_file, tuple(good), tuple(bad))
