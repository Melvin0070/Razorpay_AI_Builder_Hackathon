"""The settlement files are the layout ``docs/specs/amazon-settlement-v2.md``
gives: header, summary, 24 tab-separated columns per transaction row, raw
strings from the contract tables, spec date formats, two-decimal amounts with
no thousands separator."""

import re

import pytest

from leakproof.contract import (
    LINE_VOCABULARY,
    TRANSACTION_VOCABULARY,
    LineKind,
    TransactionType,
    classify_line,
    classify_transaction,
)
from leakproof.generator import v2
from leakproof.generator.batch import UNSEEN_CODES
from leakproof.scenarios import Scenario
from tests.generator.reading import COL, Batch, Row

DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DATE_TIME = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} UTC$")
AMOUNT = re.compile(r"^-?\d+\.\d{2}$")


def _cited_rows(batch: Batch, scenario: Scenario) -> set[str]:
    return {line_id for e in batch.seeded(scenario) for line_id in e.line_ids}


@pytest.mark.parametrize("batch_name", ["demo", "measure"])
def test_v2_layout(batch_name: str, request: pytest.FixtureRequest):
    batch: Batch = request.getfixturevalue(batch_name)
    undated_orders = {e.order_id for e in batch.seeded(Scenario.C5_WINDOW_DATE_MISSING)}
    unseen_rows = _cited_rows(batch, Scenario.C8_CODE_UNSEEN)
    for file_name in batch.settlement_file_names():
        text = batch.text(file_name)
        assert text.endswith("\n") and "\r" not in text
        settlement = batch.settlement(file_name)
        assert settlement.header == v2.COLUMNS
        summary = settlement.summary
        assert len(summary) == 24
        assert summary[COL["settlement-id"]].isdigit()
        for column in ("settlement-start-date", "settlement-end-date", "deposit-date"):
            assert DATE.match(summary[COL[column]]), column
        assert AMOUNT.match(summary[COL["total-amount"]])
        assert summary[COL["currency"]] == "INR"
        assert all(field == "" for field in summary[6:])
        assert file_name == f"settlement_{summary[COL['settlement-end-date']]}.txt"
        assert settlement.rows, "a settlement file carries transaction rows"
        for row in settlement.rows:
            _check_row(row, settlement.settlement_id, undated_orders, unseen_rows)


def _check_row(row: Row, settlement_id: str, undated_orders: set[str], unseen_rows: set[str]):
    assert len(row.fields) == 24, row.line_id
    assert row["settlement-id"] == settlement_id
    assert all(row[c] == "" for c in ("settlement-start-date", "settlement-end-date"))
    assert row["deposit-date"] == "" and row["total-amount"] == "" and row["currency"] == ""
    assert row["marketplace-name"] == "Amazon.in"
    assert AMOUNT.match(row["amount"]), row.line_id
    txn = row["transaction-type"]
    assert txn in TRANSACTION_VOCABULARY or txn == v2.OTHER_TRANSACTION, row.line_id
    kind = classify_line(row["amount-type"], row["amount-description"])
    if row.line_id in unseen_rows:
        assert kind is LineKind.UNCLASSIFIED and row["amount-description"] in UNSEEN_CODES
    else:
        assert kind is not LineKind.UNCLASSIFIED, row.line_id
    if row["order-id"]:
        assert row["fulfillment-id"] == v2.FULFILLMENT_ID
        assert row["sku"] and row["quantity-purchased"].isdigit()
        assert int(row["quantity-purchased"]) >= 1
        assert classify_transaction(txn) is not TransactionType.OTHER
    else:
        assert txn == v2.OTHER_TRANSACTION and kind is LineKind.RESERVE
        assert row["sku"] == "" and row["quantity-purchased"] == ""
    if row["order-id"] in undated_orders and txn == TransactionType.REFUND.value:
        assert row["posted-date"] == "" and row["posted-date-time"] == "", row.line_id
    else:
        assert DATE.match(row["posted-date"]), row.line_id
        assert DATE_TIME.match(row["posted-date-time"]), row.line_id
        assert row["posted-date-time"].startswith(row["posted-date"])


def test_undated_rows_exist_only_for_the_date_missing_case(measure: Batch):
    entries = measure.seeded(Scenario.C5_WINDOW_DATE_MISSING)
    assert entries, "the measure batch seeds the date-missing case"
    undated = [r for r in measure.all_rows() if r["posted-date"] == ""]
    assert undated
    assert {r["order-id"] for r in undated} == {e.order_id for e in entries}
    assert all(r["transaction-type"] == TransactionType.REFUND.value for r in undated)
    for entry in entries:
        assert any(line_id in {r.line_id for r in undated} for line_id in entry.line_ids)


def test_demo_has_no_undated_rows(demo: Batch):
    assert not demo.seeded(Scenario.C5_WINDOW_DATE_MISSING)
    assert all(r["posted-date"] for r in demo.all_rows())


def test_raw_strings_are_the_contract_spellings(demo: Batch, measure: Batch):
    pairs = {
        (r["amount-type"], r["amount-description"]) for b in (demo, measure) for r in b.all_rows()
    }
    known = set(LINE_VOCABULARY)
    promotions = {p for p in pairs if p[0] == "Promotion"}
    unseen = {p for p in pairs if p[1] in UNSEEN_CODES}
    assert pairs - promotions - unseen <= known, pairs - promotions - unseen - known
    assert unseen and all(p[0] == v2.OTHER_TRANSACTION for p in unseen)
    txns = {r["transaction-type"] for b in (demo, measure) for r in b.all_rows()}
    assert {
        TransactionType.ORDER.value,
        TransactionType.REFUND.value,
        TransactionType.ATOZ_REFUND.value,
        TransactionType.ADJUSTMENT.value,
        v2.OTHER_TRANSACTION,
    } <= txns
    kinds = {classify_line(*p) for p in pairs}
    for kind in (
        LineKind.PRINCIPAL,
        LineKind.ITEM_TAX,
        LineKind.SHIPPING_CHARGE,
        LineKind.GIFT_WRAP,
        LineKind.COMMISSION,
        LineKind.FIXED_CLOSING_FEE,
        LineKind.SHIPPING_FEE,
        LineKind.REFUND_ADMIN_FEE,
        LineKind.FEE_TAX,
        LineKind.PROMOTION,
        LineKind.TCS,
        LineKind.TDS,
        LineKind.RESERVE,
        LineKind.TECHNOLOGY_FEE,
    ):
        assert kind in kinds, kind


def test_line_ids_are_one_based_physical_rows(demo: Batch):
    for file_name in demo.settlement_file_names():
        lines = demo.lines(file_name)
        for row in demo.settlement(file_name).rows:
            assert lines[row.number - 1].split("\t") == list(row.fields)
        assert lines[0].split("\t") == list(v2.COLUMNS)


def test_orders_and_bank_layouts(demo: Batch):
    orders = demo.orders()
    assert list(orders[0]) == list(v2.ORDERS_COLUMNS)
    assert len(orders) == demo.manifest.order_count
    for o in orders:
        assert o["quantity"].isdigit() and int(o["quantity"]) >= 1
        assert o["principal_paise"].isdigit() and o["tax_paise"].isdigit()
        assert int(o["principal_paise"]) % int(o["quantity"]) == 0, "principal is quantity x unit"
        assert DATE.match(o["order_date"])
        assert o["delivery_date"] == "" or DATE.match(o["delivery_date"])
        assert o["refund_initiated_by"] in {"none", "seller", "amazon"}
    dates = [o["order_date"] for o in orders]
    assert dates == sorted(dates), "the export is in order-date order"
    bank = demo.bank()
    assert list(bank[0]) == list(v2.BANK_COLUMNS)
    for credit in bank:
        assert DATE.match(credit["date"]) and AMOUNT.match(credit["amount"])
        assert credit["utr"] and credit["narration"]
