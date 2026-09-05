"""Each file's summary total is the sum of its rows, each bank credit is one
settlement's total, and the duplicate-UTR case is the only exception and is
listed in the manifest (D6). The hypothesis test asserts the same invariants
over specs the presets never use."""

import tempfile
from collections import defaultdict
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from leakproof.contract import MATERIALITY_FLOOR_PAISE
from leakproof.generator import generate_batch, load_manifest, v2
from leakproof.generator.money import format_paise
from leakproof.scenarios import SCENARIOS, Scenario, ScenarioKind
from tests.generator.reading import Batch


def _check_totals(batch: Batch) -> None:
    for settlement in batch.settlements():
        assert sum(row.amount for row in settlement.rows) == settlement.total, settlement.file_name
        assert settlement.total > 0


def _check_bank(batch: Batch) -> None:
    settlements = batch.settlements()
    credits: dict[str, list[dict[str, str]]] = defaultdict(list)
    for credit in batch.bank():
        credits[credit["narration"].rsplit("-", 1)[1]].append(credit)
    duplicates = batch.seeded(Scenario.DUPLICATE_UTR)
    assert len(duplicates) <= 1
    duplicated = duplicates[0].order_id if duplicates else None
    assert set(credits) == {s.settlement_id for s in settlements}
    for settlement in settlements:
        rows = credits[settlement.settlement_id]
        expected = 2 if settlement.settlement_id == duplicated else 1
        assert len(rows) == expected, settlement.settlement_id
        for row in rows:
            assert row["amount"] == format_paise(settlement.total)
            assert row["date"] == settlement.deposit.isoformat()
        if expected == 2:
            assert rows[0] == rows[1], "the duplicate is the same credit twice, same UTR"
            first, second = (batch.row(line_id) for line_id in duplicates[0].line_ids)
            assert first == second == list(rows[0].values())
    utrs = [c["utr"] for c in batch.bank()]
    assert len(set(utrs)) == len(settlements)


@pytest.mark.parametrize("batch_name", ["demo", "measure", "clean", "uncovered"])
def test_totals_reconcile(batch_name: str, request: pytest.FixtureRequest):
    batch: Batch = request.getfixturevalue(batch_name)
    _check_totals(batch)
    _check_bank(batch)


def test_reserve_rows_close_every_cycle(demo: Batch):
    settlements = demo.settlements()
    previous = 0
    for index, settlement in enumerate(settlements):
        reserve = [r for r in settlement.rows if r["order-id"] == ""]
        current = [r for r in reserve if r["amount-description"] == "Current Reserve Amount"]
        released = [
            r for r in reserve if r["amount-description"] == "Previous Reserve Amount Balance"
        ]
        assert len(current) == 1 and current[0].amount < 0
        assert current[0].posted == settlement.end
        if index == 0:
            assert not released
        else:
            assert len(released) == 1 and released[0].amount == -previous
        previous = current[0].amount


@settings(max_examples=20, deadline=None)
@given(
    seed=st.integers(min_value=0, max_value=10**6),
    order_count=st.integers(min_value=30, max_value=90),
    errors_per_class=st.integers(min_value=0, max_value=3),
)
def test_batch_invariants_hold_for_arbitrary_specs(
    seed: int, order_count: int, errors_per_class: int
):
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        manifest = generate_batch(
            batch_id="prop",
            seed=seed,
            order_count=order_count,
            errors_per_class=errors_per_class,
            out_dir=out,
        )
        assert load_manifest(out / v2.MANIFEST_FILE) == manifest
        batch = Batch(out, manifest)
        _check_totals(batch)
        _check_bank(batch)
        posted = [r.posted for r in batch.all_rows() if r.posted is not None]
        assert manifest.as_of == max(posted) == manifest.coverage.end
        assert manifest.order_count == order_count == len(batch.orders())
        seeded = [
            e for e in manifest.seeded if SCENARIOS[e.scenario].kind is ScenarioKind.SEEDED_ERROR
        ]
        assert len(seeded) == 6 * errors_per_class
        for entry in seeded:
            assert entry.expected_amount_paise >= 2 * MATERIALITY_FLOOR_PAISE
        for entry in manifest.seeded:
            for line_id in entry.line_ids:
                assert batch.row(line_id)
