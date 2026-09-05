"""Lookup semantics: two honest miss dispositions, never one (D17)."""

from datetime import date, timedelta

import pytest

from leakproof.contract import Disposition, LineKind
from leakproof.ratecard import RateCardCorpus
from leakproof.types import CoverageDeclaration, LookupMiss, RateRule

APPAREL = "apparel"
INSIDE = date(2026, 8, 21)


def test_unknown_category_is_uncovered(card):
    result = card.lookup(LineKind.COMMISSION, "garden-furniture", INSIDE, 150_000)
    assert isinstance(result, LookupMiss)
    assert result.disposition is Disposition.UNCOVERED
    assert "garden-furniture" in result.detail


def test_as_of_before_the_declared_window_is_uncovered(card):
    before = card.coverage().valid_from - timedelta(days=1)
    result = card.lookup(LineKind.COMMISSION, APPAREL, before, 150_000)
    assert isinstance(result, LookupMiss)
    assert result.disposition is Disposition.UNCOVERED
    assert before.isoformat() in result.detail


def test_as_of_after_the_declared_window_is_uncovered(card):
    """The packaged declaration is open-ended, so close it to exercise the arm."""
    declared = card.coverage()
    closed = RateCardCorpus(
        rules=card.rules,
        declaration=CoverageDeclaration(
            categories=declared.categories,
            valid_from=declared.valid_from,
            valid_to=date(2026, 6, 30),
            audited_kinds=declared.audited_kinds,
            acknowledged_kinds=declared.acknowledged_kinds,
        ),
        source_path=card.source_path,
    )
    result = closed.lookup(LineKind.COMMISSION, APPAREL, date(2026, 7, 1), 150_000)
    assert isinstance(result, LookupMiss)
    assert result.disposition is Disposition.UNCOVERED


def test_a_superseded_window_is_uncovered_not_returned(card):
    """The 2025 referral bands are encoded as history; they sit below the floor."""
    superseded = [r for r in card.rules if r.valid_to == date(2026, 3, 15)]
    assert superseded, "the superseded referral window is missing from the corpus"
    result = card.lookup(LineKind.COMMISSION, APPAREL, date(2026, 1, 15), 150_000)
    assert isinstance(result, LookupMiss)
    assert result.disposition is Disposition.UNCOVERED


def test_commission_resolves_to_one_dated_cited_rule(card):
    rule = card.lookup(LineKind.COMMISSION, APPAREL, INSIDE, 150_000)
    assert isinstance(rule, RateRule)
    assert rule.kind is LineKind.COMMISSION
    assert rule.category_id == APPAREL
    assert rule.audited is True
    assert rule.percent_bp is not None
    assert rule.valid_from <= INSIDE


def test_a_slab_boundary_resolves_on_both_sides(card):
    """C2_SLAB_BOUNDARY: the bound itself belongs to the lower band."""
    lower = card.lookup(LineKind.FIXED_CLOSING_FEE, APPAREL, INSIDE, 30_000)
    upper = card.lookup(LineKind.FIXED_CLOSING_FEE, APPAREL, INSIDE, 30_001)
    assert isinstance(lower, RateRule)
    assert isinstance(upper, RateRule)
    assert lower.slab_max_paise == 30_000
    assert upper.slab_min_paise == 30_001
    assert lower.rule_id != upper.rule_id


def test_the_september_2026_closing_fee_change_switches_on_its_own_edge(card):
    before = card.lookup(LineKind.FIXED_CLOSING_FEE, APPAREL, date(2026, 9, 6), 20_000)
    after = card.lookup(LineKind.FIXED_CLOSING_FEE, APPAREL, date(2026, 9, 7), 20_000)
    assert isinstance(before, RateRule)
    assert isinstance(after, RateRule)
    assert before.rule_id != after.rule_id
    assert before.fixed_paise != after.fixed_paise


@pytest.mark.parametrize("kind", [LineKind.FEE_TAX, LineKind.TCS, LineKind.TDS])
def test_marketplace_wide_rules_resolve_for_every_declared_category(card, kind):
    for category_id in card.coverage().categories:
        rule = card.lookup(kind, category_id, INSIDE)
        assert isinstance(rule, RateRule), (kind, category_id)
        assert rule.category_id is None
        assert rule.audited is True


def test_marketplace_wide_rules_also_resolve_with_no_category(card):
    rule = card.lookup(LineKind.FEE_TAX, None, INSIDE)
    assert isinstance(rule, RateRule)


@pytest.mark.parametrize("kind", [LineKind.COMMISSION, LineKind.FIXED_CLOSING_FEE])
def test_a_category_scoped_kind_with_no_category_is_uncovered(card, kind):
    """None means "marketplace-wide" in the corpus and "I do not know the
    category" at the call site. A settlement line whose order is absent from
    the seller's export (D5, D7) has a commission deduction and no category, so
    a lane that passes None must get a limitation, not the disposition D17
    reserves for a corpus bug."""
    assert kind in card.category_scoped_kinds
    result = card.lookup(kind, None, INSIDE, 150_000)
    assert isinstance(result, LookupMiss)
    assert result.disposition is Disposition.UNCOVERED
    assert kind.value in result.detail


def test_no_declared_kind_is_a_config_error_with_no_category(card):
    """Otherwise DispositionCounts.config_error goes non-zero on a clean corpus
    while make verify stays green, which is the confusion D17 exists to end."""
    for kind in (*card.audited_kinds, *card.acknowledged_kinds):
        result = card.lookup(kind, None, INSIDE, 150_000)
        config_error = (
            isinstance(result, LookupMiss) and result.disposition is Disposition.CONFIG_ERROR
        )
        assert not config_error, kind


def test_an_acknowledged_kind_returns_a_rule_that_is_not_audited(card):
    for kind in card.coverage().acknowledged_kinds:
        rule = card.lookup(kind, APPAREL, INSIDE)
        assert isinstance(rule, RateRule), kind
        assert rule.audited is False, kind
        assert rule.percent_bp is None and rule.fixed_paise is None, kind


def test_a_known_kind_with_no_rule_is_a_config_error_not_a_silent_pass(card):
    """LineKind.TECHNOLOGY_FEE is deliberately absent (C8_CODE_KNOWN_NO_RULE).

    The detector reaches that scenario through the empty lookup, so the miss
    must be loud: inside declared coverage it is CONFIG_ERROR, and the gate
    does not sweep undeclared kinds, so nothing here fails the build.
    """
    result = card.lookup(LineKind.TECHNOLOGY_FEE, APPAREL, INSIDE, 150_000)
    assert isinstance(result, LookupMiss)
    assert result.disposition is Disposition.CONFIG_ERROR


def test_a_slabbed_kind_without_a_principal_raises_rather_than_guessing(card):
    with pytest.raises(ValueError, match="band_key_paise"):
        card.lookup(LineKind.COMMISSION, APPAREL, INSIDE)


def test_coverage_reports_exactly_the_declared_categories_and_kinds(card):
    coverage = card.coverage()
    assert coverage.categories == ("electronics-accessories", "home-kitchen", "apparel")
    assert set(coverage.audited_kinds) == {
        LineKind.COMMISSION,
        LineKind.FIXED_CLOSING_FEE,
        LineKind.FEE_TAX,
        LineKind.TCS,
        LineKind.TDS,
    }
    assert set(coverage.acknowledged_kinds) == {
        LineKind.PRINCIPAL,
        LineKind.ITEM_TAX,
        LineKind.SHIPPING_CHARGE,
        LineKind.SHIPPING_CHARGE_TAX,
        LineKind.SHIPPING_FEE,
        LineKind.FULFILMENT_FEE,
        LineKind.STORAGE_FEE,
        LineKind.GIFT_WRAP,
        LineKind.GOODWILL,
        LineKind.RESTOCKING_FEE,
        LineKind.MARKETPLACE_FACILITATOR_TAX,
        LineKind.REFUND_ADMIN_FEE,
        LineKind.PROMOTION,
        LineKind.RESERVE,
        LineKind.SAFET_REIMBURSEMENT,
    }
    assert not set(coverage.audited_kinds) & set(coverage.acknowledged_kinds)
    declared = set(coverage.audited_kinds) | set(coverage.acknowledged_kinds)
    assert declared == set(LineKind) - {LineKind.TECHNOLOGY_FEE, LineKind.UNCLASSIFIED}
