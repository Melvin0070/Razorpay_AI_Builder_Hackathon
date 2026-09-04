"""Amount-string parsing (D4/D7 trap 1): decimal-separator detection, thousands
separators, and fractional-digit strictness. Dedicated unit tests on the pure
helper so the four cases in the lane brief are pinned independently of any
particular row context."""

import pytest

from leakproof.ingest.parsing import detect_separator, parse_decimal_amount, parse_plain_int


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("-487.50", -48750),
        ("0.00", 0),
    ],
)
def test_dot_separator_amounts_parse(raw, expected):
    assert parse_decimal_amount(raw, ".") == expected


@pytest.mark.parametrize("raw", ["1,240.00", "12.345"])
def test_malformed_dot_amounts_are_quarantined(raw):
    assert parse_decimal_amount(raw, ".") is None


def test_comma_separator_amounts_parse():
    assert parse_decimal_amount("-487,50", ",") == -48750
    assert parse_decimal_amount("0,00", ",") == 0


def test_comma_amount_rejects_dot_as_thousands_separator():
    assert parse_decimal_amount("1.240,00", ",") is None


def test_empty_and_missing_fractional_digits_are_rejected():
    assert parse_decimal_amount("", ".") is None
    assert parse_decimal_amount("487", ".") is None  # no fractional part at all
    assert parse_decimal_amount("487.5", ".") is None  # one digit, not two


def test_detect_separator_prefers_dot_then_comma_then_none():
    assert detect_separator("1234.50") == "."
    assert detect_separator("1234,50") == ","
    assert detect_separator("garbage") is None
    assert detect_separator("1,240.00") is None  # neither separator parses cleanly


def test_parse_plain_int_rejects_decimals_and_separators():
    assert parse_plain_int("48750") == 48750
    assert parse_plain_int("-48750") == -48750
    assert parse_plain_int("487.50") is None
    assert parse_plain_int("1,240") is None
    assert parse_plain_int("") is None
