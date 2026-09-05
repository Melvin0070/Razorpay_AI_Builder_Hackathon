"""D18 and D20: ``as_of`` is the batch's maximum settlement posted-date, the
manifest declares the coverage window, and every cycle-sensitive case is
placed relative to ``as_of`` and ``cycle_days`` so the rules have something
to bite on."""

import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from leakproof.contract import DEFAULT_CYCLE_DAYS, TransactionType, parse_line_id
from leakproof.generator import generate_batch, v2
from leakproof.generator.batch import GST_CAPABILITY, SAFE_T_CAPABILITY
from leakproof.generator.money import parse_paise
from leakproof.scenarios import Scenario
from leakproof.types import CapabilityFact, SellerProfile
from tests.generator.reading import Batch, Row


def _profile(batch: Batch) -> SellerProfile:
    data = json.loads(batch.text(v2.PROFILE_FILE))
    facts = tuple(
        CapabilityFact(
            f["name"],
            f["holds"],
            date.fromisoformat(f["valid_from"]) if f["valid_from"] else None,
            date.fromisoformat(f["valid_to"]) if f["valid_to"] else None,
        )
        for f in data["capabilities"]
    )
    return SellerProfile(data["seller_id"], data["display_name"], facts)


def _order(batch: Batch, order_id: str) -> dict[str, str]:
    return next(o for o in batch.orders() if o["order_id"] == order_id)


def _rows(batch: Batch, order_id: str) -> list[Row]:
    return [r for r in batch.all_rows() if r["order-id"] == order_id]


def _refund_posted(batch: Batch, entry) -> date:
    """The posted-date of the refund principal row the entry cites."""
    for line_id in entry.line_ids:
        file_name, _ = parse_line_id(line_id)
        row = next(r for r in batch.settlement(file_name).rows if r.line_id == line_id)
        if row["transaction-type"] != TransactionType.ORDER.value:
            assert row.posted is not None
            return row.posted
    raise AssertionError(f"{entry.scenario} cites no refund row")


@pytest.mark.parametrize("batch_name", ["demo", "measure"])
def test_as_of_defaults_to_the_max_settlement_posted_date(
    batch_name: str, request: pytest.FixtureRequest
):
    batch: Batch = request.getfixturevalue(batch_name)
    m = batch.manifest
    posted = [r.posted for r in batch.all_rows() if r.posted is not None]
    assert m.as_of == max(posted)
    settlements = batch.settlements()
    assert m.as_of == settlements[-1].end
    assert m.cycle_days == DEFAULT_CYCLE_DAYS
    assert m.coverage.end == m.as_of
    starts = [date.fromisoformat(s.summary[1]) for s in settlements]
    assert m.coverage.start < min(starts)
    for s in settlements:
        assert m.coverage.contains(date.fromisoformat(s.summary[1])) and m.coverage.contains(s.end)
    assert all(m.coverage.contains(p) for p in posted)


def test_an_explicit_as_of_cuts_the_batch_on_that_date(tmp_path: Path):
    manifest = generate_batch(
        batch_id="cut",
        seed=11,
        order_count=40,
        errors_per_class=1,
        out_dir=tmp_path,
        as_of=date(2026, 7, 31),
    )
    batch = Batch(tmp_path, manifest)
    assert manifest.as_of == date(2026, 7, 31) == manifest.coverage.end
    assert batch.settlement_file_names()[-1] == "settlement_2026-07-31.txt"
    assert max(r.posted for r in batch.all_rows() if r.posted) == date(2026, 7, 31)


def test_a_batch_before_the_encoded_schedule_is_refused(tmp_path: Path):
    with pytest.raises(ValueError, match="before the encoded fee schedule"):
        generate_batch(
            batch_id="early",
            seed=1,
            order_count=40,
            errors_per_class=1,
            out_dir=tmp_path,
            as_of=date(2026, 4, 1),
        )


@pytest.mark.parametrize("batch_name", ["demo", "measure"])
def test_as_of_and_coverage(batch_name: str, request: pytest.FixtureRequest):
    batch: Batch = request.getfixturevalue(batch_name)
    m = batch.manifest
    cd = m.cycle_days
    out_of_window = {e.order_id for e in batch.seeded(Scenario.C6_OUT_OF_WINDOW)}
    assert out_of_window
    settled = {r["order-id"] for r in batch.all_rows()}
    for order in batch.orders():
        if not order["delivery_date"]:
            continue
        delivered = date.fromisoformat(order["delivery_date"])
        if order["order_id"] in out_of_window:
            assert delivered < m.coverage.start, order
            assert order["order_id"] not in settled
        else:
            assert m.coverage.contains(delivered), order
    for entry in batch.seeded(Scenario.C6_PLAIN):
        order = _order(batch, entry.order_id)
        delivered = date.fromisoformat(order["delivery_date"])
        assert entry.order_id not in settled, "class 6 is absence"
        assert (m.as_of - delivered).days > 2 * cd
        assert entry.expected_amount_paise == int(order["principal_paise"]) + int(
            order["tax_paise"]
        )
    for entry in batch.seeded(Scenario.C6_PAID_LATER_CYCLE):
        order = _order(batch, entry.order_id)
        delivered = date.fromisoformat(order["delivery_date"])
        rows = _rows(batch, entry.order_id)
        assert rows and all(r["transaction-type"] == TransactionType.ORDER.value for r in rows)
        file_names = {parse_line_id(r.line_id)[0] for r in rows}
        assert file_names <= set(batch.settlement_file_names()[1:]), "paid in a later cycle"
        assert (rows[0].posted - delivered).days > 2 * cd, "old enough to look unpaid"


@pytest.mark.parametrize("batch_name", ["demo", "measure"])
def test_class_5_cases_sit_where_the_cycle_rule_bites(
    batch_name: str, request: pytest.FixtureRequest
):
    batch: Batch = request.getfixturevalue(batch_name)
    m = batch.manifest
    cd = m.cycle_days
    files = batch.settlement_file_names()
    for entry in batch.seeded(Scenario.C5_AWAITING_CYCLE):
        assert (m.as_of - _refund_posted(batch, entry)).days < cd, entry.note
    for scenario in (
        Scenario.C5_PLAIN,
        Scenario.C5_SELLER_ISSUED,
        Scenario.C5_ATOZ,
        Scenario.C5_GST_UNREGISTERED,
        Scenario.C5_INVOICE_PENDING,
    ):
        for entry in batch.seeded(scenario):
            days = (m.as_of - _refund_posted(batch, entry)).days
            assert cd < days < 2 * cd, (scenario, days)
    for entry in batch.seeded(Scenario.C5_WINDOW_EXPIRED):
        refund_file = parse_line_id(entry.line_ids[0])[0]
        assert refund_file == files[0], "expired: the refund is in the first cycle"
        assert (m.as_of - _refund_posted(batch, entry)).days >= 3 * cd
    for entry in batch.seeded(Scenario.C5_REVERSED_LATER_CYCLE):
        refund_file, _ = parse_line_id(entry.line_ids[0])
        reversal_file, _ = parse_line_id(entry.line_ids[-1])
        assert files.index(reversal_file) > files.index(refund_file)
        reversal = batch.row(entry.line_ids[-1])
        assert reversal[6] == TransactionType.REFUND.value and reversal[13] == "Commission"
        assert parse_paise(reversal[14]) > 0
    for scenario in (Scenario.C5_SELLER_ISSUED, Scenario.C5_ATOZ):
        for entry in batch.seeded(scenario):
            order = _order(batch, entry.order_id)
            refund_row = batch.row(entry.line_ids[0])
            if scenario is Scenario.C5_SELLER_ISSUED:
                assert order["refund_initiated_by"] == "seller"
            else:
                assert refund_row[6] == TransactionType.ATOZ_REFUND.value


@pytest.mark.parametrize("batch_name", ["demo", "measure"])
def test_gst_registration_window_separates_the_unregistered_case(
    batch_name: str, request: pytest.FixtureRequest
):
    batch: Batch = request.getfixturevalue(batch_name)
    profile = _profile(batch)
    assert profile.capability(SAFE_T_CAPABILITY, batch.manifest.as_of) is True
    unregistered = batch.seeded(Scenario.C5_GST_UNREGISTERED)
    assert unregistered
    must_read_registered = (
        Scenario.C5_PLAIN,
        Scenario.C5_AWAITING_CYCLE,
        Scenario.C5_SELLER_ISSUED,
        Scenario.C5_ATOZ,
        Scenario.C5_WINDOW_DATE_MISSING,
        Scenario.C5_INVOICE_PENDING,
    )

    def dates_of(order_id: str) -> list[date]:
        order = _order(batch, order_id)
        own = [date.fromisoformat(order["order_date"]), date.fromisoformat(order["delivery_date"])]
        return own + [r.posted for r in _rows(batch, order_id) if r.posted is not None]

    for entry in unregistered:
        for on in dates_of(entry.order_id):
            assert profile.capability(GST_CAPABILITY, on) is False, (on, entry.note)
    for scenario in must_read_registered:
        for entry in batch.seeded(scenario):
            for on in dates_of(entry.order_id):
                assert profile.capability(GST_CAPABILITY, on) is True, (scenario, on)


def test_evidence_file_marks_the_invoice_cases(demo: Batch):
    evidence = demo.evidence()
    assert list(evidence[0]) == list(v2.EVIDENCE_COLUMNS)
    by_order = {row["order_id"]: row for row in evidence}
    for entry in demo.seeded(Scenario.C5_INVOICE_PENDING):
        assert by_order[entry.order_id]["status"] == "pending"
        assert by_order[entry.order_id]["supplied_on"] == ""
    for entry in demo.seeded(Scenario.C5_PLAIN):
        row = by_order[entry.order_id]
        assert row["status"] == "satisfied"
        assert date.fromisoformat(row["supplied_on"]) <= demo.manifest.as_of
    for entry in demo.seeded(Scenario.C5_GST_UNREGISTERED):
        assert entry.order_id not in by_order, "an unregistered seller cannot supply the invoice"
    assert {row["requirement"] for row in evidence} == {"gst_tax_invoice"}


def test_clean_batch_profile_is_registered_throughout(clean: Batch):
    profile = _profile(clean)
    for delta in range(0, 60):
        assert profile.capability(GST_CAPABILITY, clean.manifest.as_of - timedelta(days=delta))
