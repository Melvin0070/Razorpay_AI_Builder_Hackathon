"""Dedup, overlap matrix, precedence ladder, rupee partition, report. Lane L · Tier A · issue #15.

Governed by D19, D10, D3, D4, the seven-step state derivation and the rupee
partition. Owns this package. Hard gates (both additivity identities,
exactly-one-state, per-order sum invariant) register in gates.HARD_GATES.
"""

from __future__ import annotations

from leakproof.types import (
    Assessment,
    BatchInputs,
    BatchReport,
    Finding,
    RateCard,
    RupeeLines,
    StateResult,
    TriagedFinding,
)


def dedup(findings: list[Finding]) -> tuple[Finding, ...]:
    raise NotImplementedError("lane L, issue #15")


def derive_state(finding: Finding, assessment: Assessment) -> StateResult:
    raise NotImplementedError("lane L, issue #15")


def partition(
    queue: tuple[TriagedFinding, ...], below_materiality: tuple[Finding, ...]
) -> RupeeLines:
    raise NotImplementedError("lane L, issue #15")


def run_batch(inputs: BatchInputs, rate_card: RateCard) -> BatchReport:
    raise NotImplementedError("lane L, issue #15")
