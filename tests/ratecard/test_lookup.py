"""Lookup semantics: two honest miss dispositions, never one (D17)."""

from dataclasses import replace
from datetime import date, timedelta

import pytest

from leakproof.contract import Disposition, LineKind
from leakproof.ratecard import CorpusError, RateCardCorpus, SlabBandRequiredError, sweep
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


def test_an_undeclared_kind_is_uncovered_because_the_hole_is_deliberate(card):
    """LineKind.TECHNOLOGY_FEE is deliberately absent (ADR-0005 decision 2,
    C8_CODE_KNOWN_NO_RULE), so the miss is a declared limitation and not a
    corpus bug: CONFIG_ERROR here would put a real count on the dashboard for
    a seeded error that must land as an ordinary class-8 finding, while
    make verify reported zero and the README said a config error fails the
    build."""
    result = card.lookup(LineKind.TECHNOLOGY_FEE, APPAREL, INSIDE, 150_000)
    assert isinstance(result, LookupMiss)
    assert result.disposition is Disposition.UNCOVERED


def test_the_class_8_hole_is_readable_off_the_seam_not_off_the_detail_prose(card):
    """What lane J tests to reach code-known-no-rule: the kind is absent from
    both declared lists. Nothing in this path parses a sentence."""
    coverage = card.coverage()
    declared = set(coverage.audited_kinds) | set(coverage.acknowledged_kinds)
    assert LineKind.TECHNOLOGY_FEE not in declared
    assert not card.declares(LineKind.TECHNOLOGY_FEE)
    assert card.declares(LineKind.COMMISSION)


def test_a_declared_kind_with_no_rule_in_force_is_still_a_config_error(card):
    """CONFIG_ERROR keeps its meaning: a hole INSIDE what the corpus claims.

    The apparel commission schedule with its 2026 window deleted is a corpus
    the gate must fail, and it is one edit away from the packaged one.
    """
    surviving = tuple(
        r
        for r in card.rules
        if not (r.kind is LineKind.COMMISSION and r.category_id == APPAREL and r.valid_to is None)
    )
    holed = RateCardCorpus(
        rules=surviving,
        declaration=card.declaration,
        source_path=card.source_path,
        slab_bases=card.slab_bases,
    )
    result = holed.lookup(LineKind.COMMISSION, APPAREL, INSIDE, 150_000)
    assert isinstance(result, LookupMiss)
    assert result.disposition is Disposition.CONFIG_ERROR
    assert APPAREL in result.detail


def _with(card, rules):
    return RateCardCorpus(
        rules=rules,
        declaration=card.declaration,
        source_path=card.source_path,
        slab_bases=card.slab_bases,
    )


def test_overlapping_slabs_are_a_config_error_naming_both_bands(card):
    """The other half of a broken slab set, and the half no fixture carries.

    A gap answers nothing; an overlap answers twice, and picking either match
    would be a coin flip between two rupee amounts. Both are holes inside
    declared coverage, so both are CONFIG_ERROR and both name their rules.
    """
    bands = card.rules_for(LineKind.COMMISSION, APPAREL, INSIDE)
    upper = max(bands, key=lambda r: r.slab_min_paise or 0)
    lower = min(bands, key=lambda r: r.slab_min_paise or 0)
    widened = replace(upper, slab_min_paise=0)
    overlapping = _with(card, tuple(widened if r is upper else r for r in card.rules))

    result = overlapping.lookup(LineKind.COMMISSION, APPAREL, INSIDE, 40_000)
    assert isinstance(result, LookupMiss)
    assert result.disposition is Disposition.CONFIG_ERROR
    assert "overlapping slabs" in result.detail
    assert lower.rule_id in result.detail
    assert widened.rule_id in result.detail


def test_an_overlap_fails_the_gate_too(card):
    """Otherwise the branch is reachable only from a hand-written lookup."""
    bands = card.rules_for(LineKind.COMMISSION, APPAREL, INSIDE)
    upper = max(bands, key=lambda r: r.slab_min_paise or 0)
    overlapping = _with(
        card, tuple(replace(r, slab_min_paise=0) if r is upper else r for r in card.rules)
    )
    misses = sweep(overlapping)
    assert misses
    assert all("overlapping slabs" in m.detail for m in misses)


def test_a_kind_with_a_marketplace_wide_rule_is_never_category_scoped(card):
    """The subtraction in ``category_scoped_kinds``: a kind the corpus also
    prices marketplace-wide answers a lookup with no category from the
    fallback, so it must not be reported as needing one. Nothing in the
    packaged corpus prices a kind both ways, so the branch is built here."""
    wide = card.lookup(LineKind.FEE_TAX, None, INSIDE)
    assert isinstance(wide, RateRule) and wide.category_id is None
    both_ways = _with(card, (*card.rules, replace(wide, rule_id="x-fee-gst", category_id=APPAREL)))

    assert LineKind.FEE_TAX not in both_ways.category_scoped_kinds
    assert LineKind.COMMISSION in both_ways.category_scoped_kinds
    assert both_ways.lookup(LineKind.FEE_TAX, None, INSIDE) is wide


def test_a_slabbed_kind_without_a_band_key_raises_rather_than_guessing(card):
    with pytest.raises(SlabBandRequiredError, match="band_key_paise"):
        card.lookup(LineKind.COMMISSION, APPAREL, INSIDE)


def test_every_slabbed_kind_is_named_on_the_corpus_and_raises_without_a_key(card):
    """ "Always pass a band key for these kinds" is a list, not a docstring."""
    assert set(card.slabbed_kinds) == {LineKind.COMMISSION, LineKind.FIXED_CLOSING_FEE}
    for kind in card.slabbed_kinds:
        with pytest.raises(SlabBandRequiredError):
            card.lookup(kind, APPAREL, INSIDE)


def test_the_band_required_error_is_catchable_apart_from_a_corpus_error(card):
    """CorpusError and LineKind(value) are both ValueError; this is a caller
    mistake with a fix of its own, so it must not be caught by the same except."""
    assert not issubclass(SlabBandRequiredError, ValueError)
    assert not issubclass(SlabBandRequiredError, CorpusError)
    try:
        card.lookup(LineKind.COMMISSION, APPAREL, INSIDE)
    except SlabBandRequiredError as exc:
        assert exc.kind is LineKind.COMMISSION
        assert exc.category_id == APPAREL
        assert exc.as_of == INSIDE


def test_a_lone_half_open_band_resolves_without_a_band_key(card):
    """One band in force is no choice to make. Requiring both ends open raised
    on a corpus that was unambiguous, which sent a caller looking for a band
    key it had no way to compute."""
    lone = tuple(
        r
        for r in card.rules
        if r.kind is LineKind.COMMISSION
        and r.category_id == APPAREL
        and r.slab_min_paise == 100_001
        and r.valid_to is None
    )
    assert len(lone) == 1 and lone[0].slab_max_paise is None
    card_with_one_band = RateCardCorpus(
        rules=lone,
        declaration=card.declaration,
        source_path=card.source_path,
        slab_bases=card.slab_bases,
    )
    assert card_with_one_band.lookup(LineKind.COMMISSION, APPAREL, INSIDE) is lone[0]


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
