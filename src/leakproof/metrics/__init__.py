"""Accuracy harness, both match rates, holdout line, throughput. Lane N · Tier A · issue #17.

Governed by D10, D12 (holdout line), D13, D9. Owns this package. Everything
here is published, never gated, except the throughput threshold (D13).
"""

from __future__ import annotations

from leakproof.scenarios import Scenario
from leakproof.types import BatchReport, ClaimabilityLabel, HoldoutCase, Manifest


def score(
    report: BatchReport, manifest: Manifest, labels: dict[Scenario, ClaimabilityLabel]
) -> dict[str, object]:
    raise NotImplementedError("lane N, issue #17")


def score_holdout(cases: tuple[HoldoutCase, ...]) -> dict[str, object]:
    raise NotImplementedError("lane N, issue #17")
