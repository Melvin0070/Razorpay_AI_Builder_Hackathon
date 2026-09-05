"""Read a generated batch back the way a person or lane D's parser would: by
physical row, splitting on the delimiter, with no help from the generator's
own in-memory structures. Every check in this package goes through here so
that what is asserted is what is on disk."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from leakproof.contract import parse_line_id
from leakproof.generator import v2
from leakproof.generator.manifest import load_manifest
from leakproof.generator.money import parse_paise
from leakproof.types import Manifest

COL = {name: i for i, name in enumerate(v2.COLUMNS)}


def _delimiter(line: str) -> str:
    """Tab for a well-formed V2 row; comma for the malformed preset's saved-as-CSV file."""
    return "\t" if "\t" in line else ","


@dataclass(frozen=True)
class Row:
    """One transaction row of a settlement file (rows 3+), by column name."""

    file_name: str
    number: int  # physical 1-based row, header included
    fields: tuple[str, ...]

    def __getitem__(self, column: str) -> str:
        return self.fields[COL[column]]

    @property
    def line_id(self) -> str:
        return f"{self.file_name}:{self.number}"

    @property
    def amount(self) -> int:
        return parse_paise(self["amount"])

    @property
    def posted(self) -> date | None:
        return date.fromisoformat(self["posted-date"]) if self["posted-date"] else None


@dataclass(frozen=True)
class Settlement:
    file_name: str
    header: tuple[str, ...]
    summary: tuple[str, ...]
    rows: tuple[Row, ...]

    @property
    def settlement_id(self) -> str:
        return self.summary[COL["settlement-id"]]

    @property
    def end(self) -> date:
        return date.fromisoformat(self.summary[COL["settlement-end-date"]])

    @property
    def deposit(self) -> date:
        return date.fromisoformat(self.summary[COL["deposit-date"]])

    @property
    def total(self) -> int:
        return parse_paise(self.summary[COL["total-amount"]])

    def for_order(self, order_id: str) -> tuple[Row, ...]:
        return tuple(r for r in self.rows if r["order-id"] == order_id)


@dataclass(frozen=True)
class Batch:
    dir: Path
    manifest: Manifest

    @classmethod
    def load(cls, dir: Path) -> Batch:
        return cls(dir, load_manifest(dir / v2.MANIFEST_FILE))

    def text(self, file_name: str) -> str:
        return (self.dir / file_name).read_text(encoding="utf-8")

    def lines(self, file_name: str) -> list[str]:
        return self.text(file_name).split("\n")[:-1]

    def row(self, line_id: str) -> list[str]:
        """The physical row a line_id names, split on the file's delimiter."""
        file_name, number = parse_line_id(line_id)
        line = self.lines(file_name)[number - 1]
        return next(csv.reader([line], delimiter=_delimiter(line)))

    def settlement_file_names(self) -> list[str]:
        return sorted(v for k, v in self.manifest.files.items() if k.startswith("settlement:"))

    def settlement(self, file_name: str) -> Settlement:
        lines = self.lines(file_name)
        delimiter = _delimiter(lines[0])
        split = [tuple(line.split(delimiter)) for line in lines]
        rows = tuple(Row(file_name, i + 3, f) for i, f in enumerate(split[2:]))
        return Settlement(file_name, split[0], split[1], rows)

    def settlements(self) -> list[Settlement]:
        return [self.settlement(name) for name in self.settlement_file_names()]

    def all_rows(self) -> list[Row]:
        return [row for s in self.settlements() for row in s.rows]

    def orders(self) -> list[dict[str, str]]:
        with (self.dir / v2.ORDERS_FILE).open(encoding="utf-8", newline="") as fh:
            return list(csv.DictReader(fh))

    def bank(self) -> list[dict[str, str]]:
        with (self.dir / v2.BANK_FILE).open(encoding="utf-8", newline="") as fh:
            return list(csv.DictReader(fh))

    def evidence(self) -> list[dict[str, str]]:
        with (self.dir / v2.EVIDENCE_FILE).open(encoding="utf-8", newline="") as fh:
            return list(csv.DictReader(fh))

    def seeded(self, *scenarios) -> list:
        return [e for e in self.manifest.seeded if e.scenario in scenarios]
