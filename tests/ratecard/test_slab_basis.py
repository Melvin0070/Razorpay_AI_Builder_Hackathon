"""What a slab bound is read on, and what happens when it is read on the wrong
figure (D17, D3).

``types.RateRule`` says slabs bound "the order principal", and ``Order`` carries
``principal_paise`` as the row's total with ``quantity`` beside it. Amazon bands
neither fee on that number. Both worked examples below are cases where feeding
the row total to ``lookup`` picks a neighbouring band and produces a wrong fee
above the materiality floor, which would surface as a spurious class-1 or
class-2 finding on an order with nothing wrong with it.
"""

from datetime import date

from leakproof.contract import LineKind, apply_bp
from leakproof.ratecard.loader import SlabBasis
from leakproof.types import RateRule

INSIDE = date(2026, 8, 21)


def test_each_banded_kind_names_the_figure_its_bounds_are_read_on(card):
    assert card.band_basis(LineKind.COMMISSION) is SlabBasis.UNIT_ITEM_PRICE
    assert card.band_basis(LineKind.FIXED_CLOSING_FEE) is SlabBasis.BUYER_PAID_ITEM_PRICE


def test_an_unbanded_kind_has_no_basis_because_any_band_key_resolves(card):
    for kind in (LineKind.FEE_TAX, LineKind.TCS, LineKind.TDS):
        assert card.band_basis(kind) is None, kind


def test_every_banded_rule_carries_its_kind_s_basis_and_no_other_rule_does(card):
    for rule in card.rules:
        banded = rule.slab_min_paise is not None or rule.slab_max_paise is not None
        basis = card.slab_basis(rule.rule_id)
        assert (basis is not None) is banded, rule.rule_id
        if banded:
            assert basis is card.band_basis(rule.kind), rule.rule_id


def test_commission_bands_on_one_unit_not_on_a_multi_unit_row_total(card):
    """Three shirts at 400 rupees: the band key is 40000 paise, not 120000.

    Apparel prices 0% up to 1000 rupees and 21% above it, so banding the row
    total turns an order with no discrepancy into a 25200-paise class-1
    overcharge, far above the materiality floor.
    """
    unit_price, quantity = 40_000, 3
    row_principal = unit_price * quantity

    banded = card.lookup(LineKind.COMMISSION, "apparel", INSIDE, row_principal // quantity)
    assert isinstance(banded, RateRule)
    assert banded.percent_bp == 0
    assert apply_bp(unit_price, banded.percent_bp) * quantity == 0

    on_the_row_total = card.lookup(LineKind.COMMISSION, "apparel", INSIDE, row_principal)
    assert isinstance(on_the_row_total, RateRule)
    assert on_the_row_total.percent_bp == 2100
    assert apply_bp(row_principal, on_the_row_total.percent_bp) == 25_200


def test_the_closing_fee_bands_on_what_the_buyer_paid_including_seller_shipping(card):
    """An item at 960 rupees with 60 rupees of seller-charged shipping is a
    1020-rupee buyer-paid price and bands above 1000, not below it."""
    item, seller_shipping = 96_000, 6_000

    banded = card.lookup(LineKind.FIXED_CLOSING_FEE, "apparel", INSIDE, item + seller_shipping)
    assert isinstance(banded, RateRule)
    assert banded.slab_min_paise == 100_001

    on_the_item_alone = card.lookup(LineKind.FIXED_CLOSING_FEE, "apparel", INSIDE, item)
    assert isinstance(on_the_item_alone, RateRule)
    assert on_the_item_alone.slab_max_paise == 100_000
    assert banded.fixed_paise is not None and on_the_item_alone.fixed_paise is not None
    assert banded.fixed_paise - on_the_item_alone.fixed_paise == 2_500


def test_the_declared_bases_and_the_rules_are_the_same_statement(corpus_documents):
    declared = corpus_documents["coverage.json"]["slab_bases"]
    for name, doc in corpus_documents.items():
        for raw in doc.get("rules", ()):
            banded = raw.get("slab_min_paise") is not None or raw.get("slab_max_paise") is not None
            if not banded:
                assert "slab_basis" not in raw, f"{name}:{raw['rule_id']}"
                continue
            assert raw.get("slab_basis") == declared[raw["kind"]], f"{name}:{raw['rule_id']}"
