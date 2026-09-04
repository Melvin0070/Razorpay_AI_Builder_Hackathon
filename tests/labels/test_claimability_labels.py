"""D12: the frozen claimability labels are ground truth, so the loader is the
only thing standing between a typo and a wrong published metric."""

from __future__ import annotations

import json

import pytest

from leakproof import contract as c
from leakproof.labels import LABELS_PATH, LabelsError, load_labels
from leakproof.labels.ladder import (
    STEP_BLOCKER_KIND,
    STEP_NOT_CLAIMABLE_REASON,
    STEP_STATE,
    STEP_TO_INT,
    LadderError,
    check_combination,
)
from leakproof.scenarios import SCENARIOS, SEEDED_ERROR_SCENARIOS, Scenario


@pytest.fixture(scope="module")
def labels():
    return load_labels()


@pytest.fixture(scope="module")
def raw() -> dict:
    return json.loads(LABELS_PATH.read_text(encoding="utf-8"))


def test_every_seeded_scenario_has_exactly_one_label(labels, raw):
    assert set(labels) == set(SEEDED_ERROR_SCENARIOS)
    names = [entry["scenario"] for entry in raw["labels"]]
    assert len(names) == len(set(names)) == len(SEEDED_ERROR_SCENARIOS)


def test_no_label_for_a_scenario_that_is_not_a_seeded_error(labels):
    extras = {s for s in Scenario if s not in SEEDED_ERROR_SCENARIOS} & set(labels)
    assert not extras


def test_combinations_agree_with_the_ladder(raw):
    for entry in raw["labels"]:
        step = str(entry["expected_precedence_step"])
        assert step in STEP_STATE, entry["scenario"]
        assert entry["expected_state"] == STEP_STATE[step].value, entry["scenario"]
        fixed = STEP_BLOCKER_KIND.get(step)
        if fixed is not None:
            assert entry["expected_blocker_kind"] == fixed.value, entry["scenario"]
        reason = STEP_NOT_CLAIMABLE_REASON.get(step)
        expected_reason = reason.value if reason is not None else None
        assert entry["expected_not_claimable_reason"] == expected_reason, entry["scenario"]


def test_step_string_maps_onto_the_integer_a_state_result_carries(labels, raw):
    by_scenario = {entry["scenario"]: entry for entry in raw["labels"]}
    for scenario, label in labels.items():
        step = str(by_scenario[scenario.value]["expected_precedence_step"])
        assert label.expected_precedence_step == STEP_TO_INT[step]
        assert 0 <= label.expected_precedence_step <= 6


def test_step_0b_is_distinguishable_from_step_0(labels):
    zero = [x for x in labels.values() if x.expected_precedence_step == 0]
    assert zero, "no label sits on step 0 or 0b"
    for label in zero:
        if label.expected_state is c.State.BLOCKED:
            assert label.expected_blocker_kind is c.BlockerKind.PROFESSIONAL_REVIEW
        else:
            assert label.expected_state is c.State.UNEXPLAINED


def test_every_citation_carries_a_url_and_an_as_of(labels):
    for scenario, label in labels.items():
        assert label.citation.url.startswith("https://"), scenario
        assert label.citation.as_of.year >= 2024, scenario
        assert label.citation.label.strip(), scenario


def test_every_citation_declares_a_verified_flag(raw):
    # D14: unverified-but-labelled beats blocked, but the flag may never be absent.
    for entry in raw["labels"]:
        assert "verified" in entry["citation"], entry["scenario"]
        assert isinstance(entry["citation"]["verified"], bool), entry["scenario"]


def test_rationale_names_something(labels):
    for scenario, label in labels.items():
        assert len(label.rationale.split()) >= 25, scenario


def test_rupee_line_never_raises_for_a_labelled_combination(labels):
    for scenario, label in labels.items():
        error_class = SCENARIOS[scenario].expected_class
        assert error_class is not None, scenario
        c.rupee_line_for(error_class, label.expected_state)


def test_label_state_agrees_with_the_class_bucket(labels):
    for scenario, label in labels.items():
        error_class = SCENARIOS[scenario].expected_class
        bucket = c.CLASS_BUCKET[error_class]
        if bucket is c.ClassBucket.UNEXPLAINED:
            assert label.expected_state is c.State.UNEXPLAINED, scenario
        else:
            assert label.expected_state is not c.State.UNEXPLAINED, scenario


def test_a_window_step_is_only_used_where_the_mechanism_has_a_window(labels):
    windowed = {"2", "3"}
    for scenario, label in labels.items():
        error_class = SCENARIOS[scenario].expected_class
        mechanism = c.PRIMARY_MECHANISM[error_class]
        step = label.expected_precedence_step
        if str(step) in windowed:
            assert mechanism in c.MECHANISMS_WITH_WINDOW, scenario


def test_loader_rejects_a_combination_the_ladder_cannot_emit():
    with pytest.raises(LadderError):
        check_combination(
            step="2",
            state=c.State.CLAIM_READY,
            blocker_kind=None,
            not_claimable_reason=None,
            where="synthetic",
        )
    with pytest.raises(LadderError):
        check_combination(
            step="3",
            state=c.State.BLOCKED,
            blocker_kind=c.BlockerKind.SELLER_ACTION,
            not_claimable_reason=None,
            where="synthetic",
        )
    with pytest.raises(LadderError):
        check_combination(
            step="1",
            state=c.State.NOT_CLAIMABLE,
            blocker_kind=None,
            not_claimable_reason=c.NotClaimableReason.WINDOW_EXPIRED,
            where="synthetic",
        )


def test_loader_rejects_a_file_with_a_missing_label(tmp_path, raw):
    short = dict(raw, labels=raw["labels"][:-1])
    path = tmp_path / "claimability.json"
    path.write_text(json.dumps(short), encoding="utf-8")
    with pytest.raises(LabelsError, match="no label"):
        load_labels(path)


def test_loader_rejects_a_label_for_a_non_seeded_scenario(tmp_path, raw):
    extra = dict(raw["labels"][0], scenario=Scenario.C5_REVERSED_LATER_CYCLE.value)
    path = tmp_path / "claimability.json"
    path.write_text(json.dumps(dict(raw, labels=[*raw["labels"], extra])), encoding="utf-8")
    with pytest.raises(LabelsError, match="not a seeded-error scenario"):
        load_labels(path)


def test_loader_rejects_a_citation_with_no_as_of(tmp_path, raw):
    entries = [dict(e) for e in raw["labels"]]
    entries[0] = dict(
        entries[0], citation={k: v for k, v in entries[0]["citation"].items() if k != "as_of"}
    )
    path = tmp_path / "claimability.json"
    path.write_text(json.dumps(dict(raw, labels=entries)), encoding="utf-8")
    with pytest.raises(LabelsError, match="citation missing"):
        load_labels(path)


def test_the_window_tie_break_is_recorded_in_the_file(raw):
    # Sources disagree on the SAFE-T filing window; the alternatives have to
    # survive the freeze, not just the report that accompanied it.
    assert raw["window_tie_break"].strip()
