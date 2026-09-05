"""Claimability labels and the adversarial holdout. Lane F · Tier B · issue #9.

Governed by D12, P2, P3. Owns this package. Must not read evidence/,
ratecard/, generator/. ``claimability.json`` is frozen at the Wave 1 close;
its SHA-256 is recorded in contract.FROZEN_LABELS_SHA256 (ADR-0003).
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Final

from leakproof.contract import (
    MECHANISMS_WITH_WINDOW,
    PRIMARY_MECHANISM,
    BlockerKind,
    ErrorClass,
    Mechanism,
    NotClaimableReason,
    State,
    rupee_line_for,
)
from leakproof.labels.ladder import STEP_TO_INT, LadderError, check_combination
from leakproof.scenarios import SCENARIOS, SEEDED_ERROR_SCENARIOS, Scenario
from leakproof.types import Citation, ClaimabilityLabel, HoldoutCase

LABELS_PATH = Path(__file__).with_name("claimability.json")

__all__ = ["LABELS_PATH", "LabelsError", "LadderError", "load_holdout", "load_labels"]

#: Mechanisms the design terminates at a fixed step before any eligibility,
#: window or evidence question is asked. A class whose primary mechanism is one
#: of these may only be labelled at that step, and no other class may use it.
TERMINAL_STEP_FOR_MECHANISM: Final[dict[Mechanism, str]] = {
    Mechanism.NONE: "0",
    Mechanism.CA_REVIEW: "0b",
}

#: The two steps that read a filing window.
WINDOW_STEPS: Final[frozenset[str]] = frozenset({"2", "3"})


class LabelsError(ValueError):
    """The labels file is not a valid set of claimability labels."""


def _enum(cls, raw: object, field: str, where: str):
    if raw is None:
        return None
    try:
        return cls(raw)
    except ValueError as exc:
        raise LabelsError(f"{where}: {field} {raw!r} is not a {cls.__name__}") from exc


def _citation(raw: object, where: str) -> Citation:
    if not isinstance(raw, dict):
        raise LabelsError(f"{where}: citation must be an object")
    missing = {"label", "url", "as_of", "verified"} - set(raw)
    if missing:
        raise LabelsError(f"{where}: citation missing {sorted(missing)}")
    if not isinstance(raw["verified"], bool):
        raise LabelsError(f"{where}: citation.verified must be a boolean")
    if not str(raw["url"]).startswith(("http://", "https://")):
        raise LabelsError(f"{where}: citation.url must be an absolute URL, got {raw['url']!r}")
    try:
        as_of = date.fromisoformat(str(raw["as_of"]))
    except ValueError as exc:
        raise LabelsError(f"{where}: citation.as_of {raw['as_of']!r} is not an ISO date") from exc
    return Citation(
        label=str(raw["label"]), url=str(raw["url"]), as_of=as_of, verified=raw["verified"]
    )


def _check_class_table(scenario: Scenario, step: str, state: State, where: str) -> None:
    """Raise ``LabelsError`` unless the label agrees with the contract's class
    table (D23), not merely with the ladder's shape.

    The ladder alone would accept a class-7 label at step 6 or a class-8 label
    at step 5: both are combinations the ladder emits, for a class that can
    never reach them. Since these labels are frozen ground truth, the check has
    to live where the file is read, not only in a test that a post-freeze
    ADR-0003 amendment could be applied without running.
    """
    error_class: ErrorClass | None = SCENARIOS[scenario].expected_class
    if error_class is None:
        raise LabelsError(f"{where}: scenario declares no expected class, so it cannot be labelled")

    mechanism = PRIMARY_MECHANISM[error_class]
    terminal = TERMINAL_STEP_FOR_MECHANISM.get(mechanism)
    if terminal is not None and step != terminal:
        raise LabelsError(
            f"{where}: class {int(error_class)} files through {mechanism}, "
            f"which terminates at step {terminal}, label says step {step}"
        )
    if terminal is None and step in set(TERMINAL_STEP_FOR_MECHANISM.values()):
        raise LabelsError(
            f"{where}: step {step} belongs to "
            f"{sorted(m.value for m in TERMINAL_STEP_FOR_MECHANISM)}, "
            f"but class {int(error_class)} files through {mechanism}"
        )
    if step in WINDOW_STEPS and mechanism not in MECHANISMS_WITH_WINDOW:
        raise LabelsError(f"{where}: step {step} reads a filing window, and {mechanism} has none")

    try:
        rupee_line_for(error_class, state)
    except ValueError as exc:
        raise LabelsError(f"{where}: {exc}") from exc


def load_labels(path: Path | None = None) -> dict[Scenario, ClaimabilityLabel]:
    """Read and validate the frozen claimability labels (D12).

    Validation is the point: the file is ground truth that no test can derive,
    so the only defence against a typo in it is a loader that refuses a label
    the ladder cannot produce. Raises ``LabelsError`` on a missing, extra or
    malformed label, or one the contract's class table forbids for its class,
    and ``LadderError`` on a step/state/reason combination the design's
    precedence ladder never emits.
    """
    source = LABELS_PATH if path is None else path
    try:
        raw = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise LabelsError(f"{source}: not valid JSON: {exc}") from exc
    if not isinstance(raw, dict):
        raise LabelsError(f"{source}: top level must be an object")
    entries = raw.get("labels")
    if not isinstance(entries, list):
        raise LabelsError(f"{source}: 'labels' must be a list")

    labels: dict[Scenario, ClaimabilityLabel] = {}
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise LabelsError(f"{source.name}[{index}]: a label must be an object")
        name = entry.get("scenario")
        where = f"{source.name}[{name}]"
        try:
            scenario = Scenario(name)
        except ValueError as exc:
            raise LabelsError(f"{where}: not a known scenario") from exc
        if scenario in labels:
            raise LabelsError(f"{where}: duplicate label")
        if scenario not in SEEDED_ERROR_SCENARIOS:
            raise LabelsError(f"{where}: not a seeded-error scenario")

        try:
            step = str(entry["expected_precedence_step"])
            raw_state = entry["expected_state"]
        except KeyError as exc:
            raise LabelsError(f"{where}: missing field {exc.args[0]!r}") from exc
        state = _enum(State, raw_state, "expected_state", where)
        if state is None:
            raise LabelsError(f"{where}: expected_state may not be null")
        blocker = _enum(
            BlockerKind, entry.get("expected_blocker_kind"), "expected_blocker_kind", where
        )
        reason = _enum(
            NotClaimableReason,
            entry.get("expected_not_claimable_reason"),
            "expected_not_claimable_reason",
            where,
        )
        check_combination(
            step=step,
            state=state,
            blocker_kind=blocker,
            not_claimable_reason=reason,
            where=where,
        )
        _check_class_table(scenario, step, state, where)
        rationale = str(entry.get("rationale", "")).strip()
        if not rationale:
            raise LabelsError(f"{where}: rationale is empty")

        labels[scenario] = ClaimabilityLabel(
            scenario=scenario,
            expected_state=state,
            expected_precedence_step=STEP_TO_INT[step],
            rationale=rationale,
            citation=_citation(entry.get("citation"), where),
            expected_blocker_kind=blocker,
            expected_not_claimable_reason=reason,
        )

    absent = [s.value for s in SEEDED_ERROR_SCENARIOS if s not in labels]
    if absent:
        raise LabelsError(f"{source}: seeded-error scenarios with no label: {absent}")
    return labels


def load_holdout() -> tuple[HoldoutCase, ...]:
    """The 25-case adversarial holdout (D12). Imported lazily so that reading a
    label never pays for building the fixtures."""
    from leakproof.labels.holdout.cases import load_holdout as _load

    return _load()
