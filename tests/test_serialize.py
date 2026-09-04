from datetime import date

import pytest

from leakproof.contract import State
from leakproof.serialize import dumps, to_jsonable
from leakproof.types import MatchRates, RupeeLines


def test_derived_sums_are_written_out():
    lines = RupeeLines(
        claim_ready=1, blocked=2, not_claimable=3, tax_review=4, unexplained=5, below_materiality=6
    )
    j = to_jsonable(lines)
    assert j["identified"] == 6
    assert j["total"] == 21
    rates = to_jsonable(
        MatchRates(total_orders=150, matched=141, class6_flagged=6, quarantined_rows=3)
    )
    assert rates["strict"] == pytest.approx(0.94)
    assert rates["adjusted"] == pytest.approx(141 / 144)


def test_enums_dates_and_tuples():
    assert to_jsonable({"s": State.BLOCKED, "d": date(2026, 8, 28), "t": (1, 2)}) == {
        "s": "BLOCKED",
        "d": "2026-08-28",
        "t": [1, 2],
    }
    assert dumps({"a": 1}, indent=None) == '{"a": 1}\n'
    with pytest.raises(TypeError):
        to_jsonable(object())
