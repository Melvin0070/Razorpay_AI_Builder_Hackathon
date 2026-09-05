"""The CONFIG_ERROR hard gate, both ways (D17, D10).

The packaged corpus must sweep clean; the hand-authored broken corpus must fail
the sweep and say where. Without the second half the gate is untested and a
corpus typo would still land as a quietly lower recall number.
"""

import shutil
from datetime import date

import pytest

from leakproof.contract import Disposition, LineKind
from leakproof.ratecard import RateCardCorpus, config_error_gate, load_rate_card, sweep
from leakproof.ratecard.gate import GATE_NAME
from leakproof.scenarios import SCENARIOS, Scenario, ScenarioKind
from leakproof.types import LookupMiss
from tests.ratecard.conftest import CORPUS, SLAB_GAP_CORPUS

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


def test_the_sweep_probes_the_no_category_call_site(card):
    """The orphan line (D5, D7) has a kind and no category, and the sweep is
    the only place that says so before lane J finds out at runtime."""
    seen: list[str | None] = []

    class Recording(RateCardCorpus):
        def lookup(self, kind, category_id, as_of, band_key_paise=None):
            seen.append(category_id)
            return super().lookup(kind, category_id, as_of, band_key_paise)

    sweep(
        Recording(
            rules=card.rules,
            declaration=card.declaration,
            source_path=card.source_path,
            slab_bases=card.slab_bases,
        )
    )
    assert None in seen
    assert set(card.coverage().categories) <= set(seen)


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


@pytest.mark.parametrize(
    ("document", "kind"),
    [("amazon-in-fee-gst.json", "fee-tax"), ("cgst-section-52-tcs.json", "tcs")],
)
def test_deleting_a_whole_rule_document_fails_the_gate(tmp_path, document, kind):
    """The regression the declared kinds exist for.

    With the kind lists derived from the loaded rules, deleting a document
    deleted the claim with it: the sweep iterated the surviving kinds, the gate
    stayed green, and every lookup of the deleted kind missed at runtime.
    """
    root = tmp_path / "corpus"
    shutil.copytree(CORPUS, root)
    (root / document).unlink()

    result = config_error_gate(root)
    assert not result.ok
    assert kind in result.detail
    assert document not in result.detail  # the claim is named, not the file


def test_the_packaged_corpus_still_sweeps_clean_when_copied(tmp_path):
    """So the deletion above is what fails, not the copy."""
    root = tmp_path / "corpus"
    shutil.copytree(CORPUS, root)
    assert config_error_gate(root).ok


@pytest.mark.parametrize("scenario", [Scenario.CONFIG_ERROR])
def test_the_config_error_scenario_is_a_fixture_that_must_fail_verify(scenario):
    assert SCENARIOS[scenario].kind is ScenarioKind.CONFIG_FIXTURE
    assert not config_error_gate(SLAB_GAP_CORPUS).ok
