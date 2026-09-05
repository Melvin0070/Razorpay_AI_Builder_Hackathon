"""The manifest is the ground truth every published number is measured
against (D9, D10): its amounts clear the floor, its citations resolve to the
rows a person would open, and it reads back exactly as written."""

from pathlib import Path

import pytest

from leakproof.contract import MATERIALITY_FLOOR_PAISE, TOLERANCE_PAISE, parse_line_id
from leakproof.generator import load_manifest, v2, write_manifest
from leakproof.generator.batch import generate
from leakproof.generator.presets import DEMO_SEED, PRESETS
from leakproof.scenarios import SCENARIOS, Scenario, ScenarioKind
from tests.generator.reading import Batch


def test_manifest_round_trips_through_its_file(tmp_path: Path):
    manifest = generate(PRESETS["demo"].spec(DEMO_SEED), tmp_path)
    loaded = load_manifest(tmp_path / v2.MANIFEST_FILE)
    assert loaded == manifest
    write_manifest(loaded, tmp_path / "again.json")
    assert (tmp_path / "again.json").read_bytes() == (tmp_path / v2.MANIFEST_FILE).read_bytes()


@pytest.mark.parametrize("batch_name", ["demo", "measure"])
def test_seeded_amounts_are_material(batch_name: str, request: pytest.FixtureRequest):
    batch: Batch = request.getfixturevalue(batch_name)
    assert batch.manifest.materiality_floor_paise == MATERIALITY_FLOOR_PAISE
    for entry in batch.manifest.seeded:
        meta = SCENARIOS[entry.scenario]
        assert entry.expected_class == meta.expected_class, entry
        if meta.kind is ScenarioKind.SEEDED_ERROR:
            assert entry.expected_amount_paise is not None, entry
            assert entry.expected_amount_paise >= 2 * MATERIALITY_FLOOR_PAISE, entry
        elif entry.scenario is Scenario.BELOW_MATERIALITY:
            assert entry.expected_amount_paise is not None
            assert TOLERANCE_PAISE < entry.expected_amount_paise < MATERIALITY_FLOOR_PAISE, entry
        else:
            assert entry.expected_amount_paise is None, entry


@pytest.mark.parametrize("batch_name", ["demo", "measure", "malformed"])
def test_every_citation_resolves_to_a_physical_row_naming_the_order(
    batch_name: str, request: pytest.FixtureRequest
):
    batch: Batch = request.getfixturevalue(batch_name)
    for entry in batch.manifest.seeded:
        assert entry.line_ids, f"{entry.scenario} cites nothing"
        for line_id in entry.line_ids:
            file_name, number = parse_line_id(line_id)
            assert file_name in batch.manifest.files.values(), line_id
            row = batch.row(line_id)
            if entry.scenario is Scenario.QUARANTINE_MALFORMED:
                assert number in (1, 2), "the malformed file is cited by its header rows"
            elif file_name == v2.ORDERS_FILE:
                assert row[0] == entry.order_id, line_id
            elif file_name == v2.BANK_FILE:
                assert entry.scenario is Scenario.DUPLICATE_UTR
                assert row[3].endswith(entry.order_id), "bank rows are keyed by settlement id"
            else:
                assert row[7] == entry.order_id, line_id
                assert row[0] == batch.settlement(file_name).settlement_id


def test_seeded_orders_exist_in_the_order_export(demo: Batch, measure: Batch):
    for batch in (demo, measure):
        order_ids = {o["order_id"] for o in batch.orders()}
        settlement_ids = {s.settlement_id for s in batch.settlements()}
        for entry in batch.manifest.seeded:
            if entry.scenario is Scenario.DUPLICATE_UTR:
                assert entry.order_id in settlement_ids
            else:
                assert entry.order_id in order_ids, entry


def test_manifest_records_the_batch_and_the_encoding_basis(demo: Batch):
    m = demo.manifest
    assert m.batch_id == "demo" and m.seed == DEMO_SEED
    assert m.order_count == len(demo.orders()) == 150
    assert set(m.categories) == {o["category_id"] for o in demo.orders()}
    assert {"apparel", "electronics-accessories", "home-kitchen"} <= set(m.categories)
    assert {"orders", "bank", "seller_profile", "evidence"} <= set(m.files)
    on_disk = {p.name for p in demo.dir.iterdir()} - {v2.MANIFEST_FILE}
    assert set(m.files.values()) == on_disk
    assert "Fulfilment Centre" in m.generator_version
    assert "unit item price" in m.generator_version
    assert "shipping + gift wrap" in m.generator_version
    assert "2026-03-16" in m.generator_version and "2026-09-06" in m.generator_version


def test_notes_explain_every_seeded_entry(demo: Batch):
    for entry in demo.manifest.seeded:
        assert len(entry.note) > 20, entry
