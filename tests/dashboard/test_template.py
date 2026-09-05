"""Unit-level template tests against hand-built rows (rather than the full
demo fixture): HTML/JS attribute injection, the eligibility checklist, the
legend's pinned bold, PENDING vs MISSING evidence, and the finding subline
(brief fix round, findings 1 / 3 / 7 / 12)."""

from __future__ import annotations

import re
from datetime import date

from leakproof.contract import (
    ErrorClass,
    EvidenceSource,
    EvidenceStatus,
    Mechanism,
    RupeeLine,
    State,
    WindowStatus,
)
from leakproof.dashboard import render
from leakproof.dashboard.html_utils import esc, js_str
from leakproof.types import (
    Assessment,
    BatchReport,
    Citation,
    CoverageDeclaration,
    CoverageWindow,
    Deadline,
    DispositionCounts,
    EligibilityCheck,
    EvidenceItem,
    Finding,
    MatchRates,
    RupeeLines,
    StateResult,
    TriagedFinding,
)

AS_OF = date(2026, 8, 28)
COVERAGE = CoverageWindow(date(2026, 7, 1), date(2026, 8, 21))
DECLARED = CoverageDeclaration(
    categories=("home-kitchen",),
    valid_from=date(2026, 3, 1),
    valid_to=None,
    audited_kinds=(),
    acknowledged_kinds=(),
)


def _finding(**overrides) -> Finding:
    base = dict(
        error_class=ErrorClass.COMMISSION_OVERCHARGE,
        order_id="O-1",
        source_line_ids=("line-1",),
        claimed_line_id="line-1",
        amount_paise=124_000,
        mechanism=Mechanism.SAFE_T,
        basis="basis text",
    )
    base.update(overrides)
    return Finding(**base)


def _report(queue: tuple[TriagedFinding, ...], **overrides) -> BatchReport:
    base = dict(
        batch_id="B-test",
        marketplace="amazon-in",
        as_of=AS_OF,
        cycle_days=7,
        coverage=COVERAGE,
        settlement_ids=("S-1",),
        order_count=len(queue) or 1,
        rupee_lines=RupeeLines(
            claim_ready=sum(i.finding.amount_paise for i in queue),
            blocked=0,
            not_claimable=0,
            tax_review=0,
            unexplained=0,
            below_materiality=0,
        ),
        match_rates=MatchRates(
            total_orders=len(queue) or 1,
            matched=len(queue) or 1,
            class6_flagged=0,
            quarantined_rows=0,
        ),
        dispositions=DispositionCounts(quarantine=0, uncovered=0, out_of_window=0, config_error=0),
        rate_card_coverage=DECLARED,
        queue=queue,
        generated_by="test",
        mode="static",
    )
    base.update(overrides)
    return BatchReport(**base)


def _triaged(finding: Finding, *, eligibility=(), evidence=(), gate=None) -> TriagedFinding:
    assessment = Assessment(
        finding_id=finding.finding_id,
        eligibility=eligibility,
        evidence=evidence,
        deadline=Deadline(mechanism=finding.mechanism, status=WindowStatus.NOT_APPLICABLE),
    )
    state = StateResult(
        finding_id=finding.finding_id,
        state=State.CLAIM_READY,
        precedence_step=6,
        reason="evidence complete",
        rupee_line=RupeeLine.CLAIM_READY,
    )
    return TriagedFinding(finding=finding, assessment=assessment, state=state, gate=gate)


# --------------------------------------------------------------------------- #
# Finding 1: attribute injection via a hostile finding_id.
# --------------------------------------------------------------------------- #


def test_special_characters_in_finding_id_cannot_break_html_attributes():
    """A settlement line id -- and therefore the finding_id built from it --
    can carry any byte a real file's basename can. ``esc(js_str(...))`` at
    every onclick site (row selection, approve/reject) must keep a literal
    ``"``, ``'``, ``<`` or ``&`` from ever appearing unescaped inside an
    attribute value."""
    hostile_line = "set\"o=1' x&<>.txt:1"
    finding = _finding(
        order_id="O\"1'<&", claimed_line_id=hostile_line, source_line_ids=(hostile_line,)
    )
    row = _triaged(finding)
    report = _report((row,))

    for html in (render(report, mode="static"), render(report, mode="served")):
        assert "onmouseover" not in html
        assert "<script>alert" not in html
        # The row's onclick attribute, taken literally from the source text,
        # must contain no bare '"' -- if it did, this regex (which stops at
        # the first '"') would capture a truncated, wrong value instead of
        # the full escaped finding_id.
        m = re.search(r'onclick="lpSelect\(\'([^"]*)\'\)"', html)
        assert m is not None
        assert m.group(1) == esc(js_str(finding.finding_id))


def test_gate_button_onclick_escapes_hostile_finding_id():
    hostile_line = 'x".txt:1'
    finding = _finding(
        order_id='O"2', claimed_line_id=hostile_line, source_line_ids=(hostile_line,)
    )
    row = _triaged(finding)  # CLAIM_READY, no gate -> approve/reject buttons render
    report = _report((row,))
    served = render(report, mode="served")

    m = re.search(r"onclick=\"lpGate\('approve','([^\"]*)',this\)\"", served)
    assert m is not None
    assert m.group(1) == esc(js_str(finding.finding_id))


# --------------------------------------------------------------------------- #
# Finding 3: eligibility checks in the evidence checklist.
# --------------------------------------------------------------------------- #

VERIFIED_CITE = Citation("ratecard v1", "https://example.com/rc", date(2026, 1, 1), True)
UNVERIFIED_CITE = Citation("policy (secondary)", "https://example.com/pol", date(2026, 1, 1), False)


def test_eligibility_checks_render_with_checkbox_and_unverified_tag():
    finding = _finding()
    row = _triaged(
        finding,
        eligibility=(
            EligibilityCheck("R-01", "Not an A-to-z Guarantee refund", False, UNVERIFIED_CITE),
            EligibilityCheck("R-02", "Not a seller-issued refund", True, VERIFIED_CITE),
        ),
    )
    html = render(_report((row,)), mode="static")

    assert '<span class="miss">Not an A-to-z Guarantee refund</span>' in html
    assert '<span class="ok">Not a seller-issued refund</span>' in html
    # The failed rule (unverified citation) is tagged; the passed one (a
    # verified citation) is not.
    failed_idx = html.index("Not an A-to-z Guarantee refund")
    passed_idx = html.index("Not a seller-issued refund")
    assert "rule unverified" in html[failed_idx : failed_idx + 200]
    assert "rule unverified" not in html[passed_idx : passed_idx + 100]


# --------------------------------------------------------------------------- #
# Finding 7: legend bolds "window expired", not the largest reason.
# --------------------------------------------------------------------------- #


def test_legend_bolds_window_expired_even_when_another_reason_is_largest():
    finding = _finding()
    row = _triaged(finding)
    report = _report(
        (row,),
        rupee_lines=RupeeLines(
            claim_ready=finding.amount_paise,
            blocked=0,
            not_claimable=900_000,
            tax_review=0,
            unexplained=0,
            below_materiality=0,
            not_claimable_rule=800_000,  # the largest reason
            not_claimable_window_expired=50_000,  # smallest, but always bolded
            not_claimable_evidence_unobtainable=50_000,
        ),
    )
    html = render(report, mode="static")
    assert "<b>₹500 window expired</b>" in html
    assert "<b>₹8,000 excluded by rule</b>" not in html


# --------------------------------------------------------------------------- #
# Finding 12: PENDING vs MISSING, and the finding subline.
# --------------------------------------------------------------------------- #


def test_pending_evidence_is_tagged_distinctly_from_missing():
    finding = _finding()
    row = _triaged(
        finding,
        evidence=(
            EvidenceItem(
                "GST tax invoice",
                EvidenceSource.SELLER_SUPPLIABLE,
                EvidenceStatus.PENDING,
                note="requested from seller",
            ),
            EvidenceItem(
                "GST tax invoice",
                EvidenceSource.UNOBTAINABLE,
                EvidenceStatus.MISSING,
                note="seller not GST-registered",
            ),
        ),
    )
    html = render(_report((row,)), mode="static")
    assert html.count('<span class="pend">pending</span>') == 1
    pending_idx = html.index("requested from seller")
    missing_idx = html.index("seller not GST-registered")
    assert '<span class="pend">pending</span>' in html[pending_idx - 10 : pending_idx + 200]
    assert '<span class="pend">pending</span>' not in html[missing_idx - 10 : missing_idx + 200]


def test_finding_subline_omits_missing_sku_and_category():
    with_both = _triaged(_finding(sku="SKU-1", category_id="home-kitchen"))
    no_sku = _triaged(_finding(order_id="O-2", sku=None, category_id="home-kitchen"))
    no_category = _triaged(_finding(order_id="O-3", sku="SKU-1", category_id=None))
    html = render(_report((with_both, no_sku, no_category)), mode="static")

    assert "Order O-1 · SKU SKU-1 · home-kitchen" in html
    assert "Order O-2 · home-kitchen" in html
    assert "SKU  ·" not in html
    assert "Order O-3 · SKU SKU-1</div>" in html
    assert "SKU-1 · </div>" not in html
