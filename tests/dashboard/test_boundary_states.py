"""Frame 4: the three empty/boundary narratives, each from a hand-built
``BatchReport`` (brief, deliverable 6 / Tests required)."""

from datetime import date

from leakproof.dashboard import render
from leakproof.types import (
    BatchReport,
    CoverageDeclaration,
    CoverageWindow,
    DispositionCounts,
    MatchRates,
    QuarantinedRow,
    RupeeLines,
)

AS_OF = date(2026, 8, 28)
COVERAGE = CoverageWindow(date(2026, 7, 1), date(2026, 8, 21))
DECLARED = CoverageDeclaration(
    categories=("electronics-accessories", "home-kitchen", "apparel"),
    valid_from=date(2026, 3, 1),
    valid_to=None,
    audited_kinds=(),
    acknowledged_kinds=(),
)


def _report(**overrides) -> BatchReport:
    base = dict(
        batch_id="B-test",
        marketplace="amazon-in",
        as_of=AS_OF,
        cycle_days=7,
        coverage=COVERAGE,
        settlement_ids=("S-1",),
        order_count=150,
        rupee_lines=RupeeLines(
            claim_ready=0,
            blocked=0,
            not_claimable=0,
            tax_review=0,
            unexplained=0,
            below_materiality=21_200,
            below_materiality_rows=18,
        ),
        match_rates=MatchRates(total_orders=150, matched=150, class6_flagged=0, quarantined_rows=0),
        dispositions=DispositionCounts(quarantine=0, uncovered=0, out_of_window=0, config_error=0),
        rate_card_coverage=DECLARED,
        queue=(),
        generated_by="test",
        mode="static",
    )
    base.update(overrides)
    return BatchReport(**base)


def test_zero_exceptions_strip_still_renders_and_names_what_was_checked():
    report = _report()
    html = render(report, mode="static")
    assert "₹0" in html  # tier 1 identified
    assert "150 orders reconciled. No discrepancies above ₹10." in html
    assert "₹212" in html  # below-materiality amount
    for label in ("Commission overcharge", "Closing fee error", "Unclassified deduction"):
        assert label.lower() in html.lower()
    assert "<table>" not in html  # no queue table when the queue is empty
    assert "<button" not in html


def test_every_row_uncovered_names_declared_categories():
    report = _report(
        dispositions=DispositionCounts(0, 150, 0, 0), match_rates=MatchRates(150, 0, 0, 0)
    )
    html = render(report, mode="static")
    assert "No orders in a covered category." in html
    for cat in DECLARED.categories:
        assert cat in html
    assert "150 of 150 orders fall outside declared coverage" in html


def test_nothing_parsed_shows_reasons_and_hint():
    reasons = tuple(
        QuarantinedRow(
            f"settlement_2026-08-14.txt:{i}", "expected 24 tab-separated columns, found 1"
        )
        for i in range(1, 151)
    )
    report = _report(
        dispositions=DispositionCounts(
            quarantine=150,
            uncovered=0,
            out_of_window=0,
            config_error=0,
            quarantine_reasons=reasons,
            hint="the file was saved as CSV. Amazon Settlement Flat File V2 is tab-separated.",
        ),
        match_rates=MatchRates(150, 0, 0, 150),
    )
    html = render(report, mode="static")
    assert "The settlement file did not parse." in html
    assert "0.0%</b> strict" in html  # tier-4 match rate
    assert "rate reads 0.0% rather than being hidden" in html
    assert html.count('class="cite"') == 3  # first two rows + the "…N more" line
    assert "…148 more, same reason" in html
    assert "Likely cause:" in html
    assert "saved as CSV" in html


def test_boundary_reports_render_identically_in_both_modes_above_the_gate():
    """No queue rows means no gate region to differ at all -- the whole page
    should be byte-identical between static and served for a boundary state."""
    report = _report()
    assert render(report, mode="static") == render(report, mode="served")
