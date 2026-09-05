"""The CONFIG_ERROR hard gate, both ways (D17, D10).

The packaged corpus must sweep clean; the hand-authored broken corpus must fail
the sweep and say where. Without the second half the gate is untested and a
corpus typo would still land as a quietly lower recall number.
"""

from datetime import date

import pytest

from leakproof.contract import Disposition, LineKind
from leakproof.ratecard import config_error_gate, load_rate_card, sweep
from leakproof.ratecard.gate import GATE_NAME
from leakproof.scenarios import SCENARIOS, Scenario, ScenarioKind
from leakproof.types import LookupMiss
from tests.ratecard.conftest import SLAB_GAP_CORPUS

GAP_PRINCIPAL = 40_000
INSIDE = date(2026, 8, 21)


def test_the_packaged_corpus_sweeps_clean():
    result = config_error_gate()
    assert result.ok, result.detail
    assert result.name == GATE_NAME


def test_the_gate_result_names_the_declared_coverage():
    result = config_error_gate()
    for category_id in load_rate_card().coverage().categories:
        assert category_id in result.detail


def test_the_sweep_probes_both_sides_of_every_slab_bound(card):
    """A regression guard on the sweep itself: shrinking it must fail here."""
    from leakproof.ratecard.gate import _probe_band_keys

    probes = _probe_band_keys(card, LineKind.FIXED_CLOSING_FEE, "apparel", INSIDE)
    for bound in (30_000, 50_000, 100_000):
        assert {bound - 1, bound, bound + 1} <= set(probes), bound


def test_the_sweep_probes_both_sides_of_every_validity_edge(card):
    from leakproof.ratecard.gate import _probe_dates

    probes = set(_probe_dates(card))
    for edge in (date(2026, 9, 6), date(2026, 9, 7)):
        assert {edge, edge + date.resolution} <= probes, edge


def test_a_deliberate_slab_gap_is_a_config_error_from_lookup(broken_card):
    result = broken_card.lookup(LineKind.COMMISSION, "apparel", INSIDE, GAP_PRINCIPAL)
    assert isinstance(result, LookupMiss)
    assert result.disposition is Disposition.CONFIG_ERROR
    assert "apparel" in result.detail
    assert "commission" in result.detail
    assert str(GAP_PRINCIPAL) in result.detail
    assert INSIDE.isoformat() in result.detail


def test_a_deliberate_slab_gap_fails_the_gate(broken_card):
    misses = sweep(broken_card)
    assert misses
    result = config_error_gate(SLAB_GAP_CORPUS)
    assert not result.ok
    assert "apparel" in result.detail
    assert "commission" in result.detail
    assert "slab gap" in result.detail


def test_the_gap_is_the_only_failure_in_the_fixture(broken_card):
    """So the fixture tests the gate, not a corpus that is broken everywhere."""
    misses = sweep(broken_card)
    assert {m.kind for m in misses} == {LineKind.COMMISSION}


@pytest.mark.parametrize("scenario", [Scenario.CONFIG_ERROR])
def test_the_config_error_scenario_is_a_fixture_that_must_fail_verify(scenario):
    assert SCENARIOS[scenario].kind is ScenarioKind.CONFIG_FIXTURE
    assert not config_error_gate(SLAB_GAP_CORPUS).ok
