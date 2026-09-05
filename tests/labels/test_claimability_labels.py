"""D12: the frozen claimability labels are ground truth, so the loader is the
only thing standing between a typo and a wrong published metric."""

from __future__ import annotations

import json

import pytest

from leakproof import contract as c
from leakproof.labels import LABELS_PATH, LabelsError, load_labels
from leakproof.labels.ladder import (
    PROFESSIONAL_REVIEW_STEP,
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


def test_a_windowed_label_may_not_claim_its_source_states_the_window(labels):
    # Gap 7: the ladder is first-match-wins, so any class-5 label decided at
    # step 2 or later turns on the SAFE-T window not having expired first, and
    # no page read states a day count. Such a label may not carry verified.
    for scenario, label in labels.items():
        error_class = SCENARIOS[scenario].expected_class
        if c.PRIMARY_MECHANISM[error_class] not in c.MECHANISMS_WITH_WINDOW:
            continue
        if label.expected_precedence_step >= 2:
            assert label.citation.verified is False, scenario


def _write(raw: dict, entries: list[dict], tmp_path) -> object:
    path = tmp_path / "claimability.json"
    path.write_text(json.dumps(dict(raw, labels=entries)), encoding="utf-8")
    return path


def _replace(raw: dict, scenario: Scenario, **fields) -> list[dict]:
    return [
        dict(entry, **fields) if entry["scenario"] == scenario.value else entry
        for entry in raw["labels"]
    ]


def test_load_labels_rejects_a_combination_the_ladder_cannot_emit(tmp_path, raw):
    # Gap 10: the assertion has to run through the loader, because the loader is
    # what a post-freeze ADR-0003 amendment would be read by.
    entries = _replace(raw, Scenario.C5_WINDOW_EXPIRED, expected_state="CLAIM-READY")
    with pytest.raises(LadderError, match="step 2 emits"):
        load_labels(_write(raw, entries, tmp_path))


def test_load_labels_rejects_a_class_7_label_off_step_0b(tmp_path, raw):
    entries = _replace(
        raw,
        Scenario.C7_TCS_MISMATCH,
        expected_precedence_step="6",
        expected_state="CLAIM-READY",
        expected_blocker_kind=None,
    )
    with pytest.raises(LabelsError, match="terminates at step 0b"):
        load_labels(_write(raw, entries, tmp_path))


def test_load_labels_rejects_a_class_8_label_off_step_0(tmp_path, raw):
    entries = _replace(
        raw,
        Scenario.C8_CODE_UNSEEN,
        expected_precedence_step="5",
        expected_state="BLOCKED",
        expected_blocker_kind="seller-action",
    )
    with pytest.raises(LabelsError, match="terminates at step 0"):
        load_labels(_write(raw, entries, tmp_path))


def test_load_labels_rejects_a_windowed_step_on_a_class_with_no_window(tmp_path, raw):
    # Class 1 files through a support ticket and has no window (ADR-0006).
    entries = _replace(
        raw,
        Scenario.C1_PLAIN,
        expected_precedence_step="2",
        expected_state="NOT-CLAIMABLE",
        expected_not_claimable_reason="window-expired",
    )
    with pytest.raises(LabelsError, match="reads a filing window"):
        load_labels(_write(raw, entries, tmp_path))


def test_load_labels_rejects_step_0_on_a_class_that_files_something(tmp_path, raw):
    entries = _replace(
        raw, Scenario.C6_PLAIN, expected_precedence_step="0", expected_state="UNEXPLAINED"
    )
    with pytest.raises(LabelsError, match="step 0 belongs to"):
        load_labels(_write(raw, entries, tmp_path))


def test_load_labels_rejects_professional_review_off_step_0b(tmp_path, raw):
    # Gap F6: STEP_BLOCKER_KIND fixes a kind for steps 0b and 3 only, so step 5
    # was free to claim a kind the design gives to step 0b alone, and
    # _check_class_table only forbade it by the mechanism route.
    entries = _replace(
        raw, Scenario.C5_INVOICE_PENDING, expected_blocker_kind="professional-review"
    )
    with pytest.raises(LadderError, match="belongs to step 0b alone"):
        load_labels(_write(raw, entries, tmp_path))


def test_professional_review_is_rejected_on_every_step_but_0b():
    blocking = [s for s in STEP_STATE if STEP_STATE[s] is c.State.BLOCKED]
    assert blocking == [PROFESSIONAL_REVIEW_STEP, "3", "5"]
    for step in blocking:
        if step == PROFESSIONAL_REVIEW_STEP:
            continue
        with pytest.raises(LadderError):
            check_combination(
                step=step,
                state=c.State.BLOCKED,
                blocker_kind=c.BlockerKind.PROFESSIONAL_REVIEW,
                not_claimable_reason=None,
                where="synthetic",
            )


def test_load_labels_names_the_entry_when_a_field_is_missing(tmp_path, raw):
    entries = [
        {k: v for k, v in entry.items() if k != "expected_precedence_step"}
        if entry["scenario"] == Scenario.C5_PLAIN.value
        else entry
        for entry in raw["labels"]
    ]
    # Gap 12: the docstring promises LabelsError, not a bare KeyError.
    with pytest.raises(LabelsError, match=r"C5_PLAIN\]: missing field"):
        load_labels(_write(raw, entries, tmp_path))


def test_load_labels_rejects_a_label_that_is_not_an_object(tmp_path, raw):
    with pytest.raises(LabelsError, match="must be an object"):
        load_labels(_write(raw, [*raw["labels"], "C5_PLAIN"], tmp_path))


def test_check_combination_rejects_what_the_ladder_cannot_emit():
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


def test_the_verified_flag_rule_is_recorded_in_the_file(raw):
    # Gap F8: every citation carries a verified flag and several are false on
    # purpose. The rule that decides which is which is the only thing that makes
    # a false flag readable as a judgement rather than an omission, so it has to
    # survive the freeze in the file, exactly as window_tie_break does.
    assert raw["verified_flag_rule"].strip()
