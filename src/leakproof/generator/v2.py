"""Writers for the input files, in the layouts ``docs/specs/amazon-settlement-v2.md``
gives. The raw settlement vocabulary is written by inverting the contract
tables, so lane D's parser and this writer agree by construction.

Row numbering is physical and 1-based with the header as row 1 (contract
``make_line_id``), so every citation the manifest carries matches what a
person sees in a text editor.
"""

from __future__ import annotations

import csv
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Final

from leakproof.contract import (
    AMOUNT_TYPE_VOCABULARY,
    LINE_VOCABULARY,
    LineKind,
    Paise,
    TransactionType,
    make_line_id,
)
from leakproof.generator.money import format_paise

COLUMNS: Final[tuple[str, ...]] = (
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

MARKETPLACE_NAME: Final[str] = "Amazon.in"
CURRENCY: Final[str] = "INR"
#: Amazon-fulfilled network: the closing-fee schedule encoded in ``fees.py`` is
#: the Fulfilment Centre one, so the rows say so. No seam type reads this column.
FULFILLMENT_ID: Final[str] = "AFN"
#: Reserve rows carry this literal in both transaction-type and amount-type
#: (RS1 §2). It is outside ``contract.TransactionType``, so the parser keeps the
#: raw string and classifies the row as OTHER; the kind (RESERVE) is what matters.
OTHER_TRANSACTION: Final[str] = "other-transaction"

ORDERS_COLUMNS: Final[tuple[str, ...]] = (
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
BANK_COLUMNS: Final[tuple[str, ...]] = ("date", "utr", "amount", "narration")
#: Proposed companion input, not yet in the spec (see the lane report): one row
#: per seller-suppliable evidence item, ``status`` a ``contract.EvidenceStatus``
#: value, ``supplied_on`` an ISO date or empty.
EVIDENCE_COLUMNS: Final[tuple[str, ...]] = ("order_id", "requirement", "status", "supplied_on")

ORDERS_FILE: Final[str] = "orders.csv"
BANK_FILE: Final[str] = "bank.csv"
PROFILE_FILE: Final[str] = "seller_profile.json"
EVIDENCE_FILE: Final[str] = "evidence.csv"
MANIFEST_FILE: Final[str] = "manifest.json"

#: Row order inside a file for blocks sharing a posted date: the event order a
#: reader expects, with reserve rows closing the cycle.
BLOCK_ORDER: Final[dict[str, int]] = {
    "sale": 0,
    "refund": 1,
    "reversal": 2,
    "adjustment": 3,
    "reserve": 9,
}


def settlement_file_name(end: date) -> str:
    return f"settlement_{end.isoformat()}.txt"


def raw_pair(kind: LineKind, *, description: str | None = None) -> tuple[str, str]:
    """The (amount-type, amount-description) the contract table lists for a kind.
    Kinds with several spellings take ``description`` to pick one; ``PROMOTION``
    is an amount-type wildcard and takes the description verbatim."""
    if kind is LineKind.PROMOTION:
        (amount_type,) = [t for t, k in AMOUNT_TYPE_VOCABULARY.items() if k is kind]
        return amount_type, description or "Principal"
    candidates = [pair for pair, k in LINE_VOCABULARY.items() if k is kind]
    if description is not None:
        candidates = [pair for pair in candidates if pair[1] == description]
    if len(candidates) != 1:
        raise ValueError(f"{kind} needs a description to pick one of {candidates}")
    return candidates[0]


def raw_transaction(txn: TransactionType) -> str:
    if txn is TransactionType.OTHER:
        raise ValueError("OTHER has no canonical spelling; pass the raw string")
    return txn.value


@dataclass(frozen=True, slots=True)
class Line:
    """One transaction row minus what its block supplies."""

    amount_type: str
    description: str
    amount: Paise
    tag: str  # generator-internal handle the manifest resolves to a line_id
    promotion_id: str = ""


@dataclass(frozen=True, slots=True)
class Block:
    """A contiguous group of rows for one event on one order (or none, for a
    reserve row): same transaction-type, order-id and posted date.

    ``undated`` writes empty posted-date columns while keeping ``posted`` for
    ordering and the cycle: the C5_WINDOW_DATE_MISSING shape, where the event
    exists but no line carries a readable date."""

    txn_type: str  # raw transaction-type text
    order_id: str | None
    sku: str | None
    quantity: int | None
    posted: date
    posted_time: str  # HH:MM:SS
    cycle_index: int
    tag: str  # sale | refund | reversal | adjustment | reserve
    lines: tuple[Line, ...]
    shipment_id: str = ""
    order_item_code: str = ""
    adjustment_id: str = ""
    undated: bool = False


@dataclass(frozen=True, slots=True)
class RenderedSettlement:
    file_name: str
    rows: tuple[tuple[str, ...], ...]  # header, summary, then one row per line
    total: Paise
    #: (order_id, block tag, line tag) -> line_id; reserve rows are not indexed
    line_ids: dict[tuple[str, str, str], str]


def render_settlement(
    *,
    settlement_id: str,
    start: date,
    end: date,
    deposit: date,
    blocks: Iterable[Block],
    file_name: str,
) -> RenderedSettlement:
    ordered = sorted(
        blocks,
        key=lambda b: (
            b.posted,
            b.order_id is None,
            b.order_id or "",
            BLOCK_ORDER[b.tag],
            b.posted_time,
        ),
    )
    body: list[tuple[str, ...]] = []
    line_ids: dict[tuple[str, str, str], str] = {}
    total = 0
    for block in ordered:
        posted_date = "" if block.undated else block.posted.isoformat()
        posted_date_time = (
            "" if block.undated else f"{block.posted.isoformat()} {block.posted_time} UTC"
        )
        for line in block.lines:
            row = 3 + len(body)
            if block.order_id is not None:
                key = (block.order_id, block.tag, line.tag)
                if key in line_ids:
                    raise AssertionError(f"duplicate line tag {key}")
                line_ids[key] = make_line_id(file_name, row)
            total += line.amount
            body.append(
                (
                    settlement_id,
                    "",
                    "",
                    "",
                    "",
                    "",
                    block.txn_type,
                    block.order_id or "",
                    "",
                    block.adjustment_id,
                    block.shipment_id,
                    MARKETPLACE_NAME,
                    line.amount_type,
                    line.description,
                    format_paise(line.amount),
                    FULFILLMENT_ID if block.order_id is not None else "",
                    posted_date,
                    posted_date_time,
                    block.order_item_code,
                    "",
                    "",
                    block.sku or "",
                    str(block.quantity) if block.quantity is not None else "",
                    line.promotion_id,
                )
            )
    summary = (
        settlement_id,
        start.isoformat(),
        end.isoformat(),
        deposit.isoformat(),
        format_paise(total),
        CURRENCY,
        *([""] * 18),
    )
    return RenderedSettlement(file_name, (COLUMNS, summary, *body), total, line_ids)


def write_settlement(path: Path, rendered: RenderedSettlement, *, delimiter: str = "\t") -> None:
    """``delimiter=","`` writes the malformed-preset variant: the same rows
    saved as CSV, which the parser must quarantine with the saved-as-CSV hint."""
    for row in rendered.rows:
        if len(row) != len(COLUMNS):
            raise AssertionError(f"row has {len(row)} fields, expected {len(COLUMNS)}")
        if any(delimiter in field or "\n" in field for field in row):
            raise AssertionError(f"field contains the delimiter or a newline: {row}")
    text = "\n".join(delimiter.join(row) for row in rendered.rows) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")


def write_csv(path: Path, header: tuple[str, ...], rows: Iterable[tuple[str, ...]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(header)
        for row in rows:
            if len(row) != len(header):
                raise AssertionError(f"row has {len(row)} fields, expected {len(header)}")
            writer.writerow(row)
