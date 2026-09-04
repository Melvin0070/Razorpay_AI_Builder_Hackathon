"""Vocabulary behaviour the research lanes asked for (RS1, RS3)."""

from datetime import date

from leakproof import contract as c
from leakproof.types import SettlementLine


def test_lookups_case_fold_and_strip():
    assert c.classify_line("itemfees", "COMMISSION") is c.LineKind.COMMISSION
    assert c.classify_line(" Other-Transaction ", "current reserve amount") is c.LineKind.RESERVE
    assert c.classify_line("PROMOTION", "anything") is c.LineKind.PROMOTION
    assert c.classify_transaction("order") is c.TransactionType.ORDER
    assert c.classify_transaction("A-TO-Z GUARANTEE REFUND") is c.TransactionType.ATOZ_REFUND


def test_transaction_type_is_open_and_keeps_the_raw_string():
    assert c.classify_transaction("Order_Retrocharge") is c.TransactionType.ORDER_RETROCHARGE
    assert c.classify_transaction("Liquidations") is c.TransactionType.OTHER
    line = SettlementLine(
        line_id="settlement_2026-08-21.txt:3",
        settlement_id="S-1",
        txn_type=c.classify_transaction("Liquidations"),
        kind=c.LineKind.UNCLASSIFIED,
        amount_type="other-transaction",
        amount_description="Liquidation Proceeds",
        amount_paise=12_345,
        posted_date=date(2026, 8, 20),
        order_id=None,
        transaction_type_raw="Liquidations",
    )
    assert line.txn_type is c.TransactionType.OTHER
    assert line.transaction_type_raw == "Liquidations"


def test_verified_vocabulary_from_research_is_mapped_not_unclassified():
    for amount_type, desc, kind in [
        ("ItemFees", "FBAPerUnitFulfillmentFee", c.LineKind.FULFILMENT_FEE),
        ("ItemFees", "FBAWeightBasedFee", c.LineKind.FULFILMENT_FEE),
        ("ItemFees", "GiftwrapChargeback", c.LineKind.GIFT_WRAP),
        ("ItemPrice", "Goodwill", c.LineKind.GOODWILL),
        ("ItemPrice", "RestockingFee", c.LineKind.RESTOCKING_FEE),
        ("ItemFees", "LongTermStorageFee", c.LineKind.STORAGE_FEE),
        (
            "ItemWithheldTax",
            "MarketplaceFacilitatorTax-Principal",
            c.LineKind.MARKETPLACE_FACILITATOR_TAX,
        ),
    ]:
        assert c.classify_line(amount_type, desc) is kind, (amount_type, desc)


def test_every_line_kind_except_unclassified_is_reachable_from_the_tables():
    reachable = set(c.LINE_VOCABULARY.values()) | set(c.AMOUNT_TYPE_VOCABULARY.values())
    missing = set(c.LineKind) - reachable - {c.LineKind.UNCLASSIFIED}
    assert not missing, missing


def test_category_identifiers_are_pinned_to_one_node_each():
    assert set(c.CATEGORY_NODES) == {"electronics-accessories", "home-kitchen", "apparel"}
    assert len(set(c.CATEGORY_NODES.values())) == 3
    assert all(
        " - " in node or node == "Electronics Accessories" for node in c.CATEGORY_NODES.values()
    )
