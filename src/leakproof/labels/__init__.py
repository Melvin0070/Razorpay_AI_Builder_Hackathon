"""Claimability labels and the adversarial holdout. Lane F · Tier B · issue #9.

Governed by D12, P2, P3. Owns this package. Must not read evidence/,
ratecard/, generator/. ``claimability.json`` is frozen at the Wave 1 close;
its SHA-256 is recorded in contract.FROZEN_LABELS_SHA256 (ADR-0003).
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from leakproof.contract import BlockerKind, NotClaimableReason, State
from leakproof.labels.ladder import STEP_TO_INT, LadderError, check_combination
from leakproof.scenarios import SEEDED_ERROR_SCENARIOS, Scenario
from leakproof.types import Citation, ClaimabilityLabel, HoldoutCase

LABELS_PATH = Path(__file__).with_name("claimability.json")

__all__ = ["LABELS_PATH", "LabelsError", "LadderError", "load_holdout", "load_labels"]


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


def load_labels(path: Path | None = None) -> dict[Scenario, ClaimabilityLabel]:
    """Read and validate the frozen claimability labels (D12).

    Validation is the point: the file is ground truth that no test can derive,
    so the only defence against a typo in it is a loader that refuses a label
    the ladder cannot produce. Raises ``LabelsError`` on a missing, extra or
    malformed label, and ``LadderError`` on a step/state/reason combination the
    design's precedence ladder never emits.
    """
    source = LABELS_PATH if path is None else path
    raw = json.loads(source.read_text(encoding="utf-8"))
    entries = raw.get("labels")
    if not isinstance(entries, list):
        raise LabelsError(f"{source}: 'labels' must be a list")

    labels: dict[Scenario, ClaimabilityLabel] = {}
    for entry in entries:
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

        step = str(entry["expected_precedence_step"])
        state = _enum(State, entry["expected_state"], "expected_state", where)
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
