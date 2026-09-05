"""Pure formatting helpers for the dashboard. No HTML, no I/O, no clock (D18).

Kept separate from ``template.py`` so the money and date formatting can be
tested without rendering a page.
"""

from __future__ import annotations

from datetime import date

from leakproof.contract import BlockerKind, ErrorClass, NotClaimableReason, State, WindowStatus
from leakproof.types import Deadline, StateResult


def _indian_group(n: int) -> str:
    """Digit grouping: last 3 digits, then groups of 2 to the left.
    ``n`` must be non-negative."""
    s = str(n)
    if len(s) <= 3:
        return s
    last3 = s[-3:]
    rest = s[:-3]
    parts: list[str] = []
    while len(rest) > 2:
        parts.insert(0, rest[-2:])
        rest = rest[:-2]
    if rest:
        parts.insert(0, rest)
    return ",".join(parts) + "," + last3


def format_rupees(paise: int) -> str:
    """Whole rupees, paise dropped (rounded half away from zero), Indian
    digit grouping. Used in the queue and the metrics strip."""
    sign = "-" if paise < 0 else ""
    q, r = divmod(abs(paise), 100)
    if r * 2 >= 100:
        q += 1
    return f"{sign}₹{_indian_group(q)}"


def format_rupees_bare(paise: int) -> str:
    """Whole rupees, paise dropped, no ``₹`` sign. Used in the queue's ₹
    column, which already carries the symbol in its header."""
    sign = "-" if paise < 0 else ""
    q, r = divmod(abs(paise), 100)
    if r * 2 >= 100:
        q += 1
    return f"{sign}{_indian_group(q)}"


def format_rupees_paise(paise: int) -> str:
    """Rupees and paise, Indian digit grouping on the rupee part. Used in
    recomputation rows, where the exact figure matters."""
    sign = "-" if paise < 0 else ""
    p = abs(paise)
    rupees, cents = divmod(p, 100)
    return f"{sign}₹{_indian_group(rupees)}.{cents:02d}"


def format_pct(fraction: float) -> str:
    return f"{fraction * 100:.1f}%"


def format_date_short(d: date) -> str:
    """``DD Mon``, e.g. ``02 Sep``."""
    return f"{d.day:02d} {d.strftime('%b')}"


#: Class label text. Fidelity note: 1, 5, 6 match the wireframe's own wording
#: verbatim; 2 shortens the design doc's "Fixed/closing fee error" the same
#: way the wireframe does ("Closing fee error"); 7 uses the design doc's
#: "TCS/TDS mismatch" rather than the wireframe's TCS-only example text,
#: because the fixture's one class-7 row happens to be a TCS case and a
#: TDS-mismatch finding rendered as "TCS mismatch" would be wrong (see report,
#: Open questions).
CLASS_LABELS: dict[ErrorClass, str] = {
    ErrorClass.COMMISSION_OVERCHARGE: "Commission overcharge",
    ErrorClass.FIXED_FEE_ERROR: "Closing fee error",
    ErrorClass.REFUND_NO_FEE_REVERSAL: "Refund, fee not reversed",
    ErrorClass.UNPAID_PAST_CYCLE: "Unpaid order past cycle",
    ErrorClass.TAX_MISMATCH: "TCS/TDS mismatch",
    ErrorClass.UNEXPLAINED_DEDUCTION: "Unclassified deduction",
}


def class_label(error_class: ErrorClass) -> str:
    return CLASS_LABELS.get(error_class, f"class {int(error_class)}")


def class_column(error_class: ErrorClass) -> str:
    return f"{int(error_class)} · {class_label(error_class)}"


#: State -> the wireframe's fill-pattern CSS suffix (design decision 3A).
_STATE_CSS = {
    State.CLAIM_READY: "ready",
    State.BLOCKED: "blocked",
    State.UNEXPLAINED: "unexp",
    State.NOT_CLAIMABLE: "noclaim",
}


def state_css(state: State) -> str:
    return _STATE_CSS[state]


#: Six fixed override labels, a total function over (state, blocker kind or
#: not-claimable reason) -- ADR-0007. The set grew from four: the original
#: four collapsed BLOCKED(timing) with NOT-CLAIMABLE(window-expired), and
#: NOT-CLAIMABLE(rule) with BLOCKED(seller-action), which put "DRAFT WITHOUT
#: EVIDENCE" -- a missing-document reading -- on a policy exclusion, and put
#: "the window resolves" on a window that had already closed for good. Each
#: state now only ever looks at its own axis (BLOCKED reads blocker_kind,
#: NOT-CLAIMABLE reads not_claimable_reason), so a combination the ladder
#: cannot produce (e.g. BLOCKED with no blocker_kind) raises rather than
#: silently falling back to a nearest fit.
_OVERRIDE_TABLE: dict[tuple[State, BlockerKind | NotClaimableReason], tuple[str, str]] = {
    (State.BLOCKED, BlockerKind.SELLER_ACTION): ("DRAFT WITHOUT EVIDENCE", "Drafts without"),
    (State.BLOCKED, BlockerKind.TIMING): (
        "DRAFT BEFORE WINDOW RESOLVES",
        "Drafts before the window resolves",
    ),
    (State.BLOCKED, BlockerKind.PROFESSIONAL_REVIEW): (
        "DRAFT WITHOUT CA REVIEW",
        "Drafts without",
    ),
    (State.NOT_CLAIMABLE, NotClaimableReason.EVIDENCE_UNOBTAINABLE): (
        "DRAFT WITHOUT EVIDENCE THAT CANNOT EXIST",
        "Drafts without",
    ),
    (State.NOT_CLAIMABLE, NotClaimableReason.RULE): (
        "DRAFT DESPITE EXCLUSION",
        "Drafts despite the exclusion",
    ),
    (State.NOT_CLAIMABLE, NotClaimableReason.WINDOW_EXPIRED): (
        "DRAFT AFTER WINDOW CLOSED",
        "Drafts after the window closed",
    ),
}


def _override_key(
    state: State, blocker_kind: BlockerKind | None, not_claimable_reason: NotClaimableReason | None
) -> tuple[State, BlockerKind | NotClaimableReason | None]:
    if state is State.BLOCKED:
        return (state, blocker_kind)
    if state is State.NOT_CLAIMABLE:
        return (state, not_claimable_reason)
    return (state, None)


def _override_entry(
    state: State, blocker_kind: BlockerKind | None, not_claimable_reason: NotClaimableReason | None
) -> tuple[str, str]:
    entry = _OVERRIDE_TABLE.get(_override_key(state, blocker_kind, not_claimable_reason))
    if entry is None:
        raise ValueError(
            f"no override label for state={state!r} blocker_kind={blocker_kind!r} "
            f"not_claimable_reason={not_claimable_reason!r}"
        )
    return entry


def override_label(
    state: State, blocker_kind: BlockerKind | None, not_claimable_reason: NotClaimableReason | None
) -> str:
    return _override_entry(state, blocker_kind, not_claimable_reason)[0]


def override_consequence_lead(
    state: State, blocker_kind: BlockerKind | None, not_claimable_reason: NotClaimableReason | None
) -> str:
    """The consequences text's opening phrase, chosen to match the label's
    tense (ADR-0007): an exclusion is never phrased as something missing."""
    return _override_entry(state, blocker_kind, not_claimable_reason)[1]


#: Filter-chip / group-header text. Deliberately distinct from the State enum
#: values (which are the all-caps CLAIM-READY/etc. shown on the state chips).
FILTER_LABELS: dict[State, str] = {
    State.CLAIM_READY: "Claim-ready",
    State.BLOCKED: "Blocked",
    State.UNEXPLAINED: "Unexplained",
    State.NOT_CLAIMABLE: "Not claimable",
}


def oxford_join(items: list[str]) -> str:
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + f", and {items[-1]}"


def named_blocker(reason: str) -> str:
    """The part of a state reason after the kind prefix, e.g. "seller-action
    — GST tax invoice pending" -> "GST tax invoice pending". Falls back to the
    whole reason when there is no em-dash separator."""
    _, sep, rest = reason.partition("—")
    return rest.strip() if sep else reason.strip()


def file_by(deadline: Deadline, state: StateResult) -> str:
    """The queue's "File by" column (brief, deliverable 3):
    ``Nd · DD Mon`` when open, ``expired`` when expired, ``watch`` when
    BLOCKED on timing, ``—`` when not applicable or start date missing.

    Two refinements beyond that literal, state-blind mapping, both forced by
    the fixture (see report, Open questions): a BLOCKED row on a timing
    blocker reads "watch" even when its own window happens to be open or its
    start date is missing -- the row's operative fact is "wait for the next
    event", not the raw window status, so the blocker-kind check runs before
    the status check. And a NOT-CLAIMABLE row whose reason is a permanent
    block (rule exclusion, evidence that can never exist) reads "—" even when
    its underlying window is technically still open, because the window is
    moot once the claim is permanently blocked; only NOT-CLAIMABLE(window
    expired) is itself about the window, so it alone shows the countdown-like
    "expired" outcome.
    """
    if state.state is State.BLOCKED and state.blocker_kind is BlockerKind.TIMING:
        return "watch"
    if deadline.status is WindowStatus.EXPIRED:
        return "expired"
    if state.state is State.NOT_CLAIMABLE and state.not_claimable_reason in (
        NotClaimableReason.RULE,
        NotClaimableReason.EVIDENCE_UNOBTAINABLE,
    ):
        return "—"
    if deadline.status is WindowStatus.OPEN and deadline.expires_on is not None:
        return f"{deadline.days_left}d · {format_date_short(deadline.expires_on)}"
    return "—"
