"""The design's precedence ladder, as a table the labels are validated against.

Lane F owns this because a claimability label is a claim about *which step*
decides a scenario, and a label that names a step whose state it does not carry
is a label nobody can score. The triage lane (L) implements the ladder; this is
the ladder's shape, not its implementation, and the two are checked against each
other by lane N rather than by import.

The design names eight steps and calls the second one ``0b``, which has no
integer, so the frozen labels file carries the step as the design's own string.
``StateResult.precedence_step`` is an ``int``, so ``0b`` maps onto 0: the pair
(0, BLOCKED/professional-review) is distinguishable from (0, UNEXPLAINED)
without a ninth integer, and every other step is its own digit.
"""

from __future__ import annotations

from typing import Final

from leakproof.contract import BlockerKind, NotClaimableReason, State

#: Ladder label -> the integer a ``StateResult`` carries (design doc,
#: "Evidence-state model"; types.StateResult.precedence_step).
STEP_TO_INT: Final[dict[str, int]] = {
    "0": 0,
    "0b": 0,
    "1": 1,
    "2": 2,
    "3": 3,
    "4": 4,
    "5": 5,
    "6": 6,
}

#: Ladder label -> the state that step emits.
STEP_STATE: Final[dict[str, State]] = {
    "0": State.UNEXPLAINED,
    "0b": State.BLOCKED,
    "1": State.NOT_CLAIMABLE,
    "2": State.NOT_CLAIMABLE,
    "3": State.BLOCKED,
    "4": State.NOT_CLAIMABLE,
    "5": State.BLOCKED,
    "6": State.CLAIM_READY,
}

#: Ladder label -> the blocker kind that step must carry, where the design fixes
#: one. Step 5 names whichever item is missing, so its kind is open.
STEP_BLOCKER_KIND: Final[dict[str, BlockerKind | None]] = {
    "0b": BlockerKind.PROFESSIONAL_REVIEW,
    "3": BlockerKind.TIMING,
}

#: Ladder label -> the not-claimable reason that step emits (contract.NotClaimableReason
#: carries the same step numbers in its comments).
STEP_NOT_CLAIMABLE_REASON: Final[dict[str, NotClaimableReason]] = {
    "1": NotClaimableReason.RULE,
    "2": NotClaimableReason.WINDOW_EXPIRED,
    "4": NotClaimableReason.EVIDENCE_UNOBTAINABLE,
}

STEPS: Final[tuple[str, ...]] = tuple(STEP_STATE)


class LadderError(ValueError):
    """A label names a (step, state, blocker, reason) combination the ladder
    cannot produce."""


def check_combination(
    *,
    step: str,
    state: State,
    blocker_kind: BlockerKind | None,
    not_claimable_reason: NotClaimableReason | None,
    where: str,
) -> None:
    """Raise ``LadderError`` unless the four fields agree with the ladder."""
    if step not in STEP_STATE:
        raise LadderError(f"{where}: unknown precedence step {step!r}; expected one of {STEPS}")
    expected_state = STEP_STATE[step]
    if state is not expected_state:
        raise LadderError(f"{where}: step {step} emits {expected_state}, label says {state}")

    if state is State.BLOCKED:
        if blocker_kind is None:
            raise LadderError(f"{where}: BLOCKED without a blocker kind")
        fixed = STEP_BLOCKER_KIND.get(step)
        if fixed is not None and blocker_kind is not fixed:
            raise LadderError(
                f"{where}: step {step} blocks with {fixed}, label says {blocker_kind}"
            )
    elif blocker_kind is not None:
        raise LadderError(f"{where}: {state} carries no blocker kind, label says {blocker_kind}")

    if state is State.NOT_CLAIMABLE:
        expected_reason = STEP_NOT_CLAIMABLE_REASON[step]
        if not_claimable_reason is not expected_reason:
            raise LadderError(
                f"{where}: step {step} is {expected_reason}, label says {not_claimable_reason}"
            )
    elif not_claimable_reason is not None:
        raise LadderError(
            f"{where}: {state} carries no not-claimable reason, label says {not_claimable_reason}"
        )
