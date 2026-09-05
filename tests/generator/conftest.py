"""Batches generated once per session; every test reads them from disk."""

from pathlib import Path

import pytest

from leakproof.generator.presets import PRESETS, generate_preset, preset_dir
from tests.generator.reading import Batch


def _preset(tmp_path_factory: pytest.TempPathFactory, name: str, seed: int | None = None) -> Batch:
    root = tmp_path_factory.mktemp(f"preset-{name}")
    generate_preset(name, root)
    return Batch.load(preset_dir(root, name, seed if seed is not None else PRESETS[name].seeds[0]))


@pytest.fixture(scope="session")
def demo(tmp_path_factory: pytest.TempPathFactory) -> Batch:
    return _preset(tmp_path_factory, "demo")


@pytest.fixture(scope="session")
def measure_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("preset-measure")
    generate_preset("measure", root)
    return root


@pytest.fixture(scope="session")
def measure(measure_root: Path) -> Batch:
    return Batch.load(preset_dir(measure_root, "measure", PRESETS["measure"].seeds[0]))


@pytest.fixture(scope="session")
def measure_batches(measure_root: Path) -> list[Batch]:
    return [
        Batch.load(preset_dir(measure_root, "measure", seed)) for seed in PRESETS["measure"].seeds
    ]


@pytest.fixture(scope="session")
def malformed(tmp_path_factory: pytest.TempPathFactory) -> Batch:
    return _preset(tmp_path_factory, "malformed")


@pytest.fixture(scope="session")
def clean(tmp_path_factory: pytest.TempPathFactory) -> Batch:
    return _preset(tmp_path_factory, "clean")


@pytest.fixture(scope="session")
def uncovered(tmp_path_factory: pytest.TempPathFactory) -> Batch:
    return _preset(tmp_path_factory, "uncovered")


@pytest.fixture(scope="session")
def throughput(tmp_path_factory: pytest.TempPathFactory) -> Batch:
    return _preset(tmp_path_factory, "throughput")
