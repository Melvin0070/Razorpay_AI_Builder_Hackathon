"""The ``gen`` handler the integrator wires into cli.py."""

import argparse
from pathlib import Path

import pytest

from leakproof.generator import v2
from leakproof.generator.command import add_arguments, main, run
from leakproof.generator.presets import PRESETS


def test_gen_writes_the_named_preset(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    assert main(["--preset", "demo", "--out", str(tmp_path)]) == 0
    assert (tmp_path / "demo" / v2.MANIFEST_FILE).exists()
    out = capsys.readouterr().out
    assert (
        "demo:" in out and "orders=150" in out and "seeded_errors=20" in out and "cycles=4" in out
    )


def test_gen_all_writes_every_preset(tmp_path: Path):
    assert main(["--all", "--out", str(tmp_path)]) == 0
    assert {p.name for p in tmp_path.iterdir()} == set(PRESETS)
    assert sorted(p.name for p in (tmp_path / "measure").iterdir()) == [
        f"seed-{k}" for k in PRESETS["measure"].seeds
    ]


def test_gen_rejects_an_unknown_preset():
    with pytest.raises(SystemExit):
        main(["--preset", "nope"])


def test_arguments_attach_to_an_integrator_subparser(tmp_path: Path):
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd")
    add_arguments(sub.add_parser("gen"))
    args = parser.parse_args(["gen", "--preset", "clean", "--out", str(tmp_path)])
    assert run(args) == 0
    assert (tmp_path / "clean" / v2.MANIFEST_FILE).exists()
