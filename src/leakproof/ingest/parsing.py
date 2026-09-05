"""Shared value parsers: dates (three accepted forms) and amounts (decimal-
separator aware, D4/D7 traps 1 and 3). Pure functions that return ``None`` on
any failure; every caller decides the exact quarantine reason and line_id, so
these never raise and never guess.

Offset-aware timestamps (the ISO-8601-with-offset form) are converted to UTC
*before* the date is taken, so ``2026-08-16T02:00:00+05:30`` and
``2026-08-15 20:30:00 UTC`` -- the same instant, spelled two accepted ways --
agree on the date (S8). Naive dates (``YYYY-MM-DD``) and the ``... UTC`` form
are taken exactly as written: they carry no offset to convert. This matters
because ``posted_date`` feeds D20 cycle folding and the ``as_of`` default; a
date that depends on which spelling the file happened to use would make
window arithmetic non-deterministic across otherwise-identical settlements.
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime

from leakproof.contract import Paise

# docs/specs/amazon-settlement-v2.md, "Dates" row: exactly these three forms.
_RE_DATE_ONLY = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_RE_DATE_TIME_UTC = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} UTC$")
_RE_ISO_OFFSET = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$")

_RE_PLAIN_INT = re.compile(r"^-?\d+$")


def parse_flexible_date(raw: str) -> date | None:
    """Accepts ``YYYY-MM-DD``, ``YYYY-MM-DD HH:MM:SS UTC``, and ISO-8601 with
    a numeric offset. Anything else (including empty) is ``None`` so the
    caller can quarantine with the literal string -- the date/timestamp
    format is unconfirmed for the flat file (spec trap 3).

    The ISO-offset form is converted to UTC before its date is taken (S8);
    the other two forms carry no offset and are taken as written.
    """
    s = raw.strip()
    if not s:
        return None
    if _RE_DATE_ONLY.fullmatch(s):
        try:
            return date.fromisoformat(s)
        except ValueError:
            return None
    if _RE_DATE_TIME_UTC.fullmatch(s):
        try:
            return datetime.strptime(s, "%Y-%m-%d %H:%M:%S UTC").date()
        except ValueError:
            return None
    if _RE_ISO_OFFSET.fullmatch(s):
        try:
            dt = datetime.fromisoformat(s)
        except ValueError:
            return None
        return dt.astimezone(UTC).date()
    return None


def parse_decimal_amount(raw: str, separator: str) -> Paise | None:
    """Rupee-decimal string -> signed integer paise under the given decimal
    ``separator`` (``.`` or ``,``). ``None`` on anything else: the *other*
    character appearing anywhere (thousands grouping, spec trap 1), a
    fractional part that is not exactly two digits, or no fractional part at
    all -- the spec requires two decimal places, always.
    """
    s = raw.strip()
    if not s:
        return None
    other = "," if separator == "." else "."
    if other in s:
        return None
    sign = 1
    if s.startswith("-"):
        sign = -1
        s = s[1:]
    elif s.startswith("+"):
        s = s[1:]
    if separator not in s:
        return None
    whole, _, frac = s.partition(separator)
    if not whole or not whole.isdigit() or not frac.isdigit() or len(frac) != 2:
        return None
    return sign * (int(whole) * 100 + int(frac))


def detect_separator(raw: str) -> str | None:
    """Per-file decimal-separator detection from the summary row's
    ``total-amount`` (spec trap 1): try ``.`` then ``,``; ``None`` if neither
    parses, so the caller can fall back to a default and quarantine the
    header row on its own terms."""
    if parse_decimal_amount(raw, ".") is not None:
        return "."
    if parse_decimal_amount(raw, ",") is not None:
        return ","
    return None


def parse_plain_int(raw: str) -> int | None:
    """A whole-number field already in its final unit (paise, a quantity):
    no decimal point, no separator, optional leading ``-``."""
    s = raw.strip()
    if not _RE_PLAIN_INT.fullmatch(s):
        return None
    return int(s)
