"""The amount text the generator writes is exact in both directions (D3)."""

import re

import pytest
from hypothesis import given
from hypothesis import strategies as st

from leakproof.generator.money import format_paise, parse_paise

TWO_DECIMALS = re.compile(r"^-?\d+\.\d{2}$")


@given(st.integers(min_value=-(10**13), max_value=10**13))
def test_format_parse_round_trip(paise):
    text = format_paise(paise)
    assert TWO_DECIMALS.match(text), text
    assert "," not in text
    assert parse_paise(text) == paise


@pytest.mark.parametrize(
    ("paise", "text"),
    [(0, "0.00"), (5, "0.05"), (-5, "-0.05"), (-48_750, "-487.50"), (124_000_00, "124000.00")],
)
def test_known_values(paise, text):
    assert format_paise(paise) == text
    assert parse_paise(text) == paise


@pytest.mark.parametrize("bad", ["1,240.00", "12.345", "12", "12.", ".50", "abc", "1.2"])
def test_parse_rejects_other_shapes(bad):
    with pytest.raises(ValueError):
        parse_paise(bad)
