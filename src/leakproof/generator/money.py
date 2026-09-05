"""Paise to and from the settlement file's amount text. Integer arithmetic only.

The V2 file writes ``-487.50``; the parser reads it back to ``-48750``. Both
directions are exact, so a float never touches an amount (D3).
"""

from __future__ import annotations

from leakproof.contract import Paise


def format_paise(paise: Paise) -> str:
    """``-48750`` → ``-487.50``. Two decimals, no thousands separator, ``.`` as
    the decimal separator (RS1 §4: the India file is written with ``.``)."""
    sign = "-" if paise < 0 else ""
    rupees, p = divmod(abs(paise), 100)
    return f"{sign}{rupees}.{p:02d}"


def parse_paise(text: str) -> Paise:
    """Inverse of :func:`format_paise`; rejects anything that is not exactly
    that shape, so a test reading a generated file cannot silently accept a
    thousands separator or a third decimal."""
    s = text.strip()
    negative = s.startswith("-")
    if negative:
        s = s[1:]
    whole, dot, frac = s.partition(".")
    if not whole.isdigit() or dot != "." or len(frac) != 2 or not frac.isdigit():
        raise ValueError(f"not a two-decimal amount: {text!r}")
    value = int(whole) * 100 + int(frac)
    return -value if negative else value
