"""Every preset generates by name; the shapes D9 and D13 ask for; the
malformed file is single-column; the clean batch carries no discrepancy a
correct detector could find."""

from collections import Counter, defaultdict
from pathlib import Path

import pytest

from leakproof.contract import ErrorClass, LineKind, TransactionType, classify_line
from leakproof.generator import fees, v2
from leakproof.generator.presets import PRESETS, generate_preset, preset_dir
from leakproof.scenarios import Scenario
from tests.generator.reading import Batch, Row


def test_presets(tmp_path: Path):
    assert set(PRESETS) == {"demo", "measure", "throughput", "malformed", "uncovered", "clean"}
    for name, preset in PRESETS.items():
        manifests = generate_preset(name, tmp_path)
        assert len(manifests) == len(preset.seeds)
        for manifest in manifests:
            directory = preset_dir(tmp_path, name, manifest.seed)
            assert (directory / v2.MANIFEST_FILE).exists(), name
            assert manifest.seed in preset.seeds
    with pytest.raises(KeyError):
        generate_preset("nope", tmp_path)


def test_demo_shape(demo: Batch):
    assert demo.manifest.order_count == 150
    assert len(demo.settlement_file_names()) == 4
    assert sum(1 for e in demo.manifest.seeded if e.expected_class is not None) == 20


def test_measure_shape(measure_batches: list[Batch]):
    assert [b.manifest.seed for b in measure_batches] == [1, 2, 3, 4, 5]
    for batch in measure_batches:
        assert batch.manifest.order_count == 500
        assert batch.manifest.batch_id == f"measure-{batch.manifest.seed}"
        assert len(batch.settlement_file_names()) == 8
        assert sum(1 for e in batch.manifest.seeded if e.expected_class is not None) == 120


def test_throughput_shape(throughput: Batch):
    assert throughput.manifest.order_count == 10_000 == len(throughput.orders())
    per_class = Counter(e.expected_class for e in throughput.manifest.seeded if e.expected_class)
    assert per_class == {cls: 400 for cls in ErrorClass}, "the measure ratio, 24% of orders"


def test_malformed_preset_saves_the_last_settlement_as_csv(malformed: Batch):
    files = malformed.settlement_file_names()
    last = malformed.text(files[-1])
    assert "\t" not in last, "saved as CSV: the parser sees a single tab-column per row"
    assert all(len(line.split(",")) == 24 for line in last.split("\n") if line)
    for name in files[:-1]:
        assert "\t" in malformed.text(name)
    (entry,) = malformed.seeded(Scenario.QUARANTINE_MALFORMED)
    assert entry.line_ids == (f"{files[-1]}:1", f"{files[-1]}:2")
    assert entry.order_id == malformed.settlement(files[-1]).settlement_id


def test_uncovered_preset_puts_every_order_outside_coverage(uncovered: Batch):
    categories = {o["category_id"] for o in uncovered.orders()}
    assert categories and not categories & set(fees.COVERED_CATEGORIES)
    assert categories <= set(fees.UNCOVERED_CATEGORIES)
    entries = uncovered.manifest.seeded
    assert len(entries) == uncovered.manifest.order_count == 150
    assert all(
        e.scenario is Scenario.UNCOVERED_CATEGORY and e.expected_class is None for e in entries
    )
    assert set(uncovered.manifest.categories) == categories


def _sale_blocks(batch: Batch) -> dict[str, list[Row]]:
    blocks: dict[str, list[Row]] = defaultdict(list)
    for row in batch.all_rows():
        if row["order-id"] and row["transaction-type"] == TransactionType.ORDER.value:
            blocks[row["order-id"]].append(row)
    return blocks


def _amount(rows: list[Row], kind: LineKind) -> int:
    return sum(
        r.amount for r in rows if classify_line(r["amount-type"], r["amount-description"]) is kind
    )


def test_clean_preset_has_no_material_discrepancy(clean: Batch):
    """Recompute every audited fee from the order export and the sale rows
    the way a detector would; every charge must equal the schedule."""
    assert not clean.manifest.seeded
    orders = {o["order_id"]: o for o in clean.orders()}
    sales = _sale_blocks(clean)
    assert set(sales) == set(orders), "every order is settled; nothing is unpaid"
    for order_id, rows in sales.items():
        order = orders[order_id]
        quantity = int(order["quantity"])
        principal = _amount(rows, LineKind.PRINCIPAL)
        assert principal == int(order["principal_paise"])
        unit_price = principal // quantity
        posted = rows[0].posted
        assert posted is not None
        positive_gift_wrap = sum(r.amount for r in rows if r["amount-description"] == "GiftWrap")
        key = fees.closing_key(
            principal, _amount(rows, LineKind.SHIPPING_CHARGE), positive_gift_wrap, quantity
        )
        category = order["category_id"]
        assert -_amount(rows, LineKind.COMMISSION) == fees.commission_paise(
            category, unit_price, quantity, posted
        )
        assert -_amount(rows, LineKind.FIXED_CLOSING_FEE) == fees.closing_fee_paise(
            category, key, quantity, posted
        )
        legs = {
            r["amount-description"]: -r.amount
            for r in rows
            if r["amount-type"] == "ItemWithheldTax"
        }
        tds = legs.pop("TDS (Section 194-O)")
        assert tds == fees.tds_paise(principal, posted)
        intra = "TCS-CGST" in legs
        assert legs == dict(fees.tcs_legs(principal, intra_state=intra, on=posted))
        kinds = {classify_line(r["amount-type"], r["amount-description"]) for r in rows}
        assert LineKind.UNCLASSIFIED not in kinds and LineKind.TECHNOLOGY_FEE not in kinds
    refunds: dict[str, list[Row]] = defaultdict(list)
    for row in clean.all_rows():
        if row["order-id"] and row["transaction-type"] != TransactionType.ORDER.value:
            refunds[row["order-id"]].append(row)
    assert refunds, "the clean batch still carries ordinary refunds"
    for order_id, rows in refunds.items():
        assert _amount(rows, LineKind.PRINCIPAL) == -_amount(sales[order_id], LineKind.PRINCIPAL)
        assert _amount(rows, LineKind.COMMISSION) == -_amount(sales[order_id], LineKind.COMMISSION)
        assert all(r.posted is not None for r in rows)
    assert len(clean.bank()) == len(clean.settlements())
