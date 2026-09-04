"""Order-keyed fold, coverage window, tiebreak, exact matcher. Lane H · Tier B · issue #11.

Governed by D20, D7, D10 (match-rate definitions). Owns this package.
"""

from __future__ import annotations

from leakproof.types import BatchInputs, FoldedOrder, MatchResult


def fold_batch(inputs: BatchInputs) -> tuple[FoldedOrder, ...]:
    raise NotImplementedError("lane H, issue #11")


def match(inputs: BatchInputs, folded: tuple[FoldedOrder, ...]) -> MatchResult:
    raise NotImplementedError("lane H, issue #11")
