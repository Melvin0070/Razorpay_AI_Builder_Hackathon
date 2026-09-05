"""Stable, exact quarantine-reason strings shared by every ingest parser.

They are displayed on screen verbatim (D7, wireframe frame 4), so wording
changes here are interface changes even though nothing imports this module
outside ``ingest/``. The settlement-file reasons named in the lane brief are
marked *(brief)*; everything else is this lane's own addition, same style,
inventoried in ``leakproof.ingest``'s module docstring.
"""

from __future__ import annotations


def column_count(expected: int, found: int, sep_word: str) -> str:
    """*(brief, for sep_word="tab")* Reused verbatim for the comma-separated
    companion formats with the appropriate expected count."""
    return f"expected {expected} {sep_word}-separated columns, found {found}"


def amount_not_numeric(raw: str) -> str:
    """*(brief)*"""
    return f"amount not numeric: '{raw}'"


def bad_date(column: str, raw: str) -> str:
    """*(brief)*"""
    return f"bad date in {column}: '{raw}'"


def missing_order_id_on_order_row() -> str:
    """*(brief)*"""
    return "missing order-id on Order row"


def unknown_header_layout() -> str:
    """*(brief)*"""
    return "unknown header layout"


#: *(brief)* Exact string named in the brief; no interpolation.
DELIVERY_BEFORE_ORDER = "delivery_date before order_date"


def quantity_not_numeric(raw: str) -> str:
    return f"quantity not numeric: '{raw}'"


def missing_field(field: str) -> str:
    return f"missing {field}"


def unknown_refund_initiated_by(raw: str) -> str:
    return f"unknown refund_initiated_by: '{raw}'"


#: S1: a row that could not be decoded as UTF-8 (one or more undecodable
#: bytes, surfaced via ``errors="surrogateescape"``). The rest of the file
#: still parses -- only this row is quarantined.
NOT_VALID_UTF8 = "not valid UTF-8"

#: S2: the header row failed exact-name/column-count validation, so nothing
#: in the rest of the file is parsed by guessed column position -- every
#: later row gets this same stable reason rather than a fabricated value.
NOT_PARSED_BAD_HEADER = "not parsed: unknown header layout"


def quantity_not_positive(raw: str) -> str:
    """S12."""
    return f"quantity not positive: '{raw}'"


def principal_negative(raw: str) -> str:
    """S12."""
    return f"principal negative: '{raw}'"


def tax_negative(raw: str) -> str:
    """S12."""
    return f"tax negative: '{raw}'"
