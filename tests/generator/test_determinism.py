"""Same seed, same bytes (D11): the manifest is only ground truth if the files
it describes can be regenerated exactly."""

from datetime import date
from pathlib import Path

from leakproof.generator import generate_batch, v2
from leakproof.generator.batch import generate
from leakproof.generator.presets import DEMO_SEED, PRESETS


def _files(directory: Path) -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in sorted(directory.iterdir())}


def test_determinism(tmp_path: Path):
    spec = PRESETS["demo"].spec(DEMO_SEED)
    first = generate(spec, tmp_path / "a")
    second = generate(spec, tmp_path / "b")
    assert first == second
    a, b = _files(tmp_path / "a"), _files(tmp_path / "b")
    assert a.keys() == b.keys()
    for name in a:
        assert a[name] == b[name], f"{name} differs between two runs of the same seed"


def test_a_different_seed_changes_the_data_but_not_the_shape(tmp_path: Path):
    first = generate(PRESETS["demo"].spec(DEMO_SEED), tmp_path / "a")
    second = generate(PRESETS["demo"].spec(DEMO_SEED + 1), tmp_path / "b")
    assert first != second
    assert first.order_count == second.order_count
    assert [e.scenario for e in first.seeded] == [e.scenario for e in second.seeded]
    assert (tmp_path / "a" / v2.ORDERS_FILE).read_bytes() != (
        tmp_path / "b" / v2.ORDERS_FILE
    ).read_bytes()


def test_generate_batch_writes_every_input_file(tmp_path: Path):
    manifest = generate_batch(
        batch_id="unit", seed=3, order_count=60, errors_per_class=2, out_dir=tmp_path
    )
    names = {p.name for p in tmp_path.iterdir()}
    settlement_files = {v for k, v in manifest.files.items() if k.startswith("settlement:")}
    assert len(settlement_files) == 4, "the default batch has four weekly cycles"
    assert names == {
        v2.ORDERS_FILE,
        v2.BANK_FILE,
        v2.PROFILE_FILE,
        v2.EVIDENCE_FILE,
        v2.MANIFEST_FILE,
        *settlement_files,
    }
    assert manifest.batch_id == "unit" and manifest.seed == 3 and manifest.order_count == 60
    assert all(name == f"settlement_{name[11:21]}.txt" for name in settlement_files)
    assert all(date.fromisoformat(name[11:21]) for name in settlement_files)
