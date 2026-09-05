"""Named batches the CLI can generate by name (D9, D13)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from leakproof.generator import fees
from leakproof.generator.batch import BatchSpec, default_scenario_counts, generate
from leakproof.scenarios import Scenario
from leakproof.types import Manifest

DEMO_SEED: Final[int] = 2026
MEASURE_SEEDS: Final[tuple[int, ...]] = (1, 2, 3, 4, 5)
THROUGHPUT_SEED: Final[int] = 7

#: The demo mix follows the wireframe's queue: claim-ready claims to drill (the
#: class-5 one per ADR-0006), a blocked GST-invoice claim to decline, one of
#: each blocker and exclusion, and the dispositions. Twenty seeded errors.
#: ``C5_WINDOW_DATE_MISSING`` is left to the measure batch: its undated rows
#: are quarantined, and the malformed preset is the demo's quarantine story.
DEMO_COUNTS: Final[dict[Scenario, int]] = {
    Scenario.C1_PLAIN: 2,
    Scenario.C2_PLAIN: 1,
    Scenario.C2_SLAB_BOUNDARY: 1,
    Scenario.C5_PLAIN: 2,
    Scenario.C5_AWAITING_CYCLE: 2,
    Scenario.C5_SELLER_ISSUED: 1,
    Scenario.C5_ATOZ: 1,
    Scenario.C5_WINDOW_EXPIRED: 1,
    Scenario.C5_GST_UNREGISTERED: 1,
    Scenario.C5_INVOICE_PENDING: 1,
    Scenario.C6_PLAIN: 3,
    Scenario.C7_TCS_MISMATCH: 1,
    Scenario.C7_TDS_MISMATCH: 1,
    Scenario.C8_CODE_UNSEEN: 1,
    Scenario.C8_CODE_KNOWN_NO_RULE: 1,
    Scenario.C5_REVERSED_LATER_CYCLE: 1,
    Scenario.C6_PAID_LATER_CYCLE: 1,
    Scenario.C6_OUT_OF_WINDOW: 2,
    Scenario.BELOW_MATERIALITY: 3,
    Scenario.UNCOVERED_CATEGORY: 4,
    Scenario.DUPLICATE_UTR: 1,
}


@dataclass(frozen=True, slots=True)
class Preset:
    name: str
    description: str
    seeds: tuple[int, ...]
    spec: Callable[[int], BatchSpec]


def _demo(seed: int) -> BatchSpec:
    return BatchSpec("demo", seed, 150, DEMO_COUNTS)


def _measure(seed: int) -> BatchSpec:
    return BatchSpec(f"measure-{seed}", seed, 500, default_scenario_counts(20), cycle_count=8)


def _throughput(seed: int) -> BatchSpec:
    return BatchSpec("throughput", seed, 10_000, default_scenario_counts(400), cycle_count=8)


def _malformed(seed: int) -> BatchSpec:
    return BatchSpec("malformed", seed, 150, DEMO_COUNTS, malformed_last_settlement=True)


def _uncovered(seed: int) -> BatchSpec:
    return BatchSpec("uncovered", seed, 150, {}, categories=fees.UNCOVERED_CATEGORIES)


def _clean(seed: int) -> BatchSpec:
    return BatchSpec("clean", seed, 150, {})


PRESETS: Final[dict[str, Preset]] = {
    "demo": Preset("demo", "150 orders, 20 seeded errors, 4 cycles", (DEMO_SEED,), _demo),
    "measure": Preset(
        "measure",
        "500 orders, 20 errors per class x 6, seeds 1-5, 8 cycles",
        MEASURE_SEEDS,
        _measure,
    ),
    "throughput": Preset(
        "throughput",
        "10,000 orders seeded at the measure ratio",
        (THROUGHPUT_SEED,),
        _throughput,
    ),
    "malformed": Preset(
        "malformed",
        "the demo batch with its last settlement file saved as CSV",
        (DEMO_SEED,),
        _malformed,
    ),
    "uncovered": Preset(
        "uncovered",
        "every order in a category outside the declared three",
        (DEMO_SEED,),
        _uncovered,
    ),
    "clean": Preset("clean", "no seeded errors, no material discrepancy", (DEMO_SEED,), _clean),
}


def preset_dir(out_root: Path, name: str, seed: int) -> Path:
    """Single-seed presets write to ``<root>/<name>``; multi-seed ones to
    ``<root>/<name>/seed-<k>``."""
    preset = PRESETS[name]
    return out_root / name if len(preset.seeds) == 1 else out_root / name / f"seed-{seed}"


def generate_preset(name: str, out_root: Path) -> tuple[Manifest, ...]:
    if name not in PRESETS:
        raise KeyError(f"unknown preset {name!r}; known: {', '.join(PRESETS)}")
    preset = PRESETS[name]
    return tuple(
        generate(preset.spec(seed), preset_dir(out_root, name, seed)) for seed in preset.seeds
    )
