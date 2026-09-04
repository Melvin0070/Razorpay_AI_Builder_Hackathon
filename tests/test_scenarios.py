from leakproof.contract import ErrorClass
from leakproof.scenarios import (
    SCENARIOS,
    SEEDED_ERROR_SCENARIOS,
    Scenario,
    ScenarioKind,
    scenarios_for_class,
)


def test_every_scenario_has_metadata_and_a_description():
    assert set(SCENARIOS) == set(Scenario)
    assert all(m.description.strip() for m in SCENARIOS.values())


def test_seeded_errors_carry_a_class_and_nothing_else_does():
    for s, m in SCENARIOS.items():
        if m.kind is ScenarioKind.SEEDED_ERROR:
            assert m.expected_class is not None, s
        else:
            assert m.expected_class is None, s


def test_every_class_has_at_least_one_seeded_scenario():
    for cls in ErrorClass:
        assert scenarios_for_class(cls), cls
    assert Scenario.C1_PLAIN in scenarios_for_class(ErrorClass.COMMISSION_OVERCHARGE)
    assert Scenario.C5_REVERSED_LATER_CYCLE not in SEEDED_ERROR_SCENARIOS
