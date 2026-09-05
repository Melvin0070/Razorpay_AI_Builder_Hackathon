"""Every seeded-error scenario appears in the measurement batch at the D9
ratio, and the true negatives, dispositions and the duplicate credit ride
along with ``expected_class = None``."""

from collections import Counter

import pytest

from leakproof.contract import ErrorClass
from leakproof.generator.batch import BatchSpec, default_scenario_counts, validate_spec
from leakproof.scenarios import SCENARIOS, SEEDED_ERROR_SCENARIOS, Scenario, ScenarioKind
from tests.generator.reading import Batch

RIDE_ALONG = (
    Scenario.C5_REVERSED_LATER_CYCLE,
    Scenario.C6_PAID_LATER_CYCLE,
    Scenario.C6_OUT_OF_WINDOW,
    Scenario.BELOW_MATERIALITY,
    Scenario.UNCOVERED_CATEGORY,
    Scenario.DUPLICATE_UTR,
)


def test_scenario_coverage(measure_batches: list[Batch]):
    assert len(measure_batches) == 5
    for batch in measure_batches:
        seeded = [
            e
            for e in batch.manifest.seeded
            if SCENARIOS[e.scenario].kind is ScenarioKind.SEEDED_ERROR
        ]
        assert {e.scenario for e in seeded} == set(SEEDED_ERROR_SCENARIOS)
        per_class = Counter(e.expected_class for e in seeded)
        assert per_class == {cls: 20 for cls in ErrorClass}, per_class
        assert len(seeded) == 120
        for scenario in RIDE_ALONG:
            entries = batch.seeded(scenario)
            assert entries, f"{scenario} missing from {batch.manifest.batch_id}"
            assert all(e.expected_class is None for e in entries)
        assert len(batch.seeded(Scenario.DUPLICATE_UTR)) == 1
        assert not batch.seeded(Scenario.QUARANTINE_MALFORMED, Scenario.CONFIG_ERROR)


def test_default_counts_deal_each_class_round_robin():
    counts = default_scenario_counts(20)
    for cls in ErrorClass:
        members = [s for s in SEEDED_ERROR_SCENARIOS if SCENARIOS[s].expected_class is cls]
        assert sum(counts[s] for s in members) == 20
        assert all(counts[s] >= 1 for s in members)
    assert counts[Scenario.DUPLICATE_UTR] == 1
    assert all(counts[s] == 10 for s in RIDE_ALONG if s is not Scenario.DUPLICATE_UTR)
    assert default_scenario_counts(0) == {}


def test_demo_carries_twenty_seeded_errors_and_the_ride_alongs(demo: Batch):
    seeded = [e for e in demo.manifest.seeded if e.expected_class is not None]
    assert len(seeded) == 20
    assert {e.expected_class for e in seeded} == set(ErrorClass)
    for scenario in RIDE_ALONG:
        assert demo.seeded(scenario), scenario


def test_malformed_preset_lists_its_quarantine(malformed: Batch):
    entries = malformed.seeded(Scenario.QUARANTINE_MALFORMED)
    assert len(entries) == 1
    assert entries[0].expected_class is None and entries[0].expected_amount_paise is None
    seeded = [e for e in malformed.manifest.seeded if e.expected_class is not None]
    assert len(seeded) == 20, "the malformed batch is the demo batch"


def test_fixture_only_and_writer_seeded_scenarios_cannot_be_counted():
    with pytest.raises(ValueError, match="CONFIG_ERROR"):
        validate_spec(BatchSpec("x", 1, 50, {Scenario.CONFIG_ERROR: 1}))
    with pytest.raises(ValueError, match="QUARANTINE_MALFORMED"):
        validate_spec(BatchSpec("x", 1, 50, {Scenario.QUARANTINE_MALFORMED: 1}))
    with pytest.raises(ValueError, match="DUPLICATE_UTR"):
        validate_spec(BatchSpec("x", 1, 50, {Scenario.DUPLICATE_UTR: 2}))
    with pytest.raises(ValueError, match="exceed"):
        validate_spec(BatchSpec("x", 1, 5, {Scenario.C1_PLAIN: 6}))
    with pytest.raises(ValueError, match="cycles"):
        validate_spec(BatchSpec("x", 1, 50, {Scenario.C1_PLAIN: 1}, cycle_count=2))
