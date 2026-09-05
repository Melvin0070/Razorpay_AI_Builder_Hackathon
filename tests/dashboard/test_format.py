"""Pure formatting helpers: rupee grouping, percentages, dates, labels, and
the "File by" precedence (brief, deliverable 3 / 9)."""

from datetime import date

import pytest

from leakproof.contract import (
    BlockerKind,
    ErrorClass,
    Mechanism,
    NotClaimableReason,
    RupeeLine,
    State,
    WindowStatus,
)
from leakproof.dashboard.format import (
    class_column,
    class_label,
    file_by,
    format_date_short,
    format_pct,
    format_rupees,
    format_rupees_bare,
    format_rupees_paise,
    named_blocker,
    override_consequence_lead,
    override_label,
    oxford_join,
)
from leakproof.types import Citation, Deadline, StateResult


def test_rupee_formatter_examples_from_brief():
    assert format_rupees(124_000) == "₹1,240"
    assert format_rupees(12_345_678_900) == "₹12,34,56,789"


def test_rupee_formatter_small_and_zero():
    assert format_rupees(0) == "₹0"
    assert format_rupees(999) == "₹10"  # 9.99 rounds to 10
    assert format_rupees(950) == "₹10"  # 9.50 rounds half away from zero
    assert format_rupees(949) == "₹9"


def test_rupee_formatter_bare_has_no_symbol():
    assert format_rupees_bare(124_000) == "1,240"


def test_rupee_paise_formatter_keeps_paise():
    assert format_rupees_paise(48_750) == "₹487.50"
    assert format_rupees_paise(-48_750) == "-₹487.50"
    assert format_rupees_paise(0) == "₹0.00"


def test_format_pct_matches_fixture_figures():
    assert format_pct(0.94) == "94.0%"
    assert format_pct(141 / 144) == "97.9%"


def test_format_date_short():
    assert format_date_short(date(2026, 9, 2)) == "02 Sep"
    assert format_date_short(date(2026, 12, 1)) == "01 Dec"


def test_class_labels_and_column():
    assert class_label(ErrorClass.COMMISSION_OVERCHARGE) == "Commission overcharge"
    assert class_column(ErrorClass.TAX_MISMATCH) == "7 · TCS/TDS mismatch"


#: The six fixed labels, a total function over (state, blocker kind or
#: not-claimable reason) -- ADR-0007 (finding 5). Every row of the table.
OVERRIDE_TABLE_ROWS = [
    (State.BLOCKED, BlockerKind.SELLER_ACTION, None, "DRAFT WITHOUT EVIDENCE"),
    (State.BLOCKED, BlockerKind.TIMING, None, "DRAFT BEFORE WINDOW RESOLVES"),
    (State.BLOCKED, BlockerKind.PROFESSIONAL_REVIEW, None, "DRAFT WITHOUT CA REVIEW"),
    (
        State.NOT_CLAIMABLE,
        None,
        NotClaimableReason.EVIDENCE_UNOBTAINABLE,
        "DRAFT WITHOUT EVIDENCE THAT CANNOT EXIST",
    ),
    (State.NOT_CLAIMABLE, None, NotClaimableReason.RULE, "DRAFT DESPITE EXCLUSION"),
    (
        State.NOT_CLAIMABLE,
        None,
        NotClaimableReason.WINDOW_EXPIRED,
        "DRAFT AFTER WINDOW CLOSED",
    ),
]


@pytest.mark.parametrize("state,blocker,nc_reason,label", OVERRIDE_TABLE_ROWS)
def test_override_label_covers_every_row_of_the_table(state, blocker, nc_reason, label):
    assert override_label(state, blocker, nc_reason) == label


def test_override_label_is_total_and_raises_on_unlisted_combinations():
    """Nothing falls back to a nearest fit: a combination the ladder cannot
    produce (BLOCKED with no blocker_kind, NOT-CLAIMABLE with no reason, a
    blocker_kind attached to NOT-CLAIMABLE, or CLAIM-READY/UNEXPLAINED --
    which never reach the override gate at all) raises loudly instead."""
    with pytest.raises(ValueError, match="no override label"):
        override_label(State.BLOCKED, None, None)
    with pytest.raises(ValueError, match="no override label"):
        override_label(State.NOT_CLAIMABLE, None, None)
    with pytest.raises(ValueError, match="no override label"):
        override_label(State.NOT_CLAIMABLE, BlockerKind.TIMING, None)
    with pytest.raises(ValueError, match="no override label"):
        override_label(State.CLAIM_READY, None, None)
    with pytest.raises(ValueError, match="no override label"):
        override_label(State.UNEXPLAINED, None, None)


@pytest.mark.parametrize("state,blocker,nc_reason,_label", OVERRIDE_TABLE_ROWS)
def test_override_consequence_lead_never_calls_an_exclusion_missing(
    state, blocker, nc_reason, _label
):
    """rule and window-expired are exclusions, not missing documents -- their
    consequences text must not say "without" (finding 5)."""
    lead = override_consequence_lead(state, blocker, nc_reason)
    if nc_reason in (NotClaimableReason.RULE, NotClaimableReason.WINDOW_EXPIRED):
        assert "without" not in lead.lower()
    assert lead  # every row has a non-empty lead


def test_named_blocker_strips_kind_prefix():
    assert named_blocker("seller-action — GST tax invoice pending") == "GST tax invoice pending"
    assert named_blocker("no dash here") == "no dash here"


def test_oxford_join():
    assert oxford_join([]) == ""
    assert oxford_join(["a"]) == "a"
    assert oxford_join(["a", "b"]) == "a and b"
    assert oxford_join(["a", "b", "c"]) == "a, b, and c"


CITE_UNVERIFIED = Citation("SAFE-T policy", "https://example.com", date(2026, 8, 20), False)


def _state(state: State, *, blocker=None, nc_reason=None) -> StateResult:
    return StateResult(
        finding_id="x",
        state=state,
        precedence_step=0,
        reason="reason",
        rupee_line=RupeeLine.BLOCKED,  # not exercised by file_by
        blocker_kind=blocker,
        not_claimable_reason=nc_reason,
    )


def test_file_by_open_window():
    dl = Deadline(
        mechanism=Mechanism.SAFE_T,
        status=WindowStatus.OPEN,
        window_days=60,
        starts_on=date(2026, 7, 4),
        expires_on=date(2026, 9, 2),
        days_left=5,
        citation=CITE_UNVERIFIED,
    )
    assert file_by(dl, _state(State.CLAIM_READY)) == "5d · 02 Sep"


def test_file_by_expired():
    dl = Deadline(
        mechanism=Mechanism.SAFE_T, status=WindowStatus.EXPIRED, expires_on=date(2026, 8, 21)
    )
    assert file_by(
        dl, _state(State.NOT_CLAIMABLE, nc_reason=NotClaimableReason.WINDOW_EXPIRED)
    ) == ("expired")


def test_file_by_blocked_timing_wins_over_open_status():
    """A BLOCKED(timing) row reads "watch" even when its own window is open --
    the operative fact is "wait for the event", not the countdown (format.py,
    ``file_by`` docstring)."""
    dl = Deadline(
        mechanism=Mechanism.SAFE_T,
        status=WindowStatus.OPEN,
        expires_on=date(2026, 10, 23),
        days_left=56,
    )
    assert file_by(dl, _state(State.BLOCKED, blocker=BlockerKind.TIMING)) == "watch"


def test_file_by_not_claimable_permanent_block_hides_the_window():
    dl = Deadline(
        mechanism=Mechanism.SAFE_T, status=WindowStatus.OPEN, expires_on=date(2026, 10, 2)
    )
    assert file_by(dl, _state(State.NOT_CLAIMABLE, nc_reason=NotClaimableReason.RULE)) == "—"
    assert (
        file_by(dl, _state(State.NOT_CLAIMABLE, nc_reason=NotClaimableReason.EVIDENCE_UNOBTAINABLE))
        == "—"
    )


def test_file_by_not_applicable_and_start_date_missing():
    not_applicable = Deadline(
        mechanism=Mechanism.SUPPORT_TICKET, status=WindowStatus.NOT_APPLICABLE
    )
    assert file_by(not_applicable, _state(State.CLAIM_READY)) == "—"
    missing = Deadline(mechanism=Mechanism.SAFE_T, status=WindowStatus.START_DATE_MISSING)
    assert file_by(missing, _state(State.BLOCKED, blocker=BlockerKind.SELLER_ACTION)) == "—"
