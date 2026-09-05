"""Synthetic batches and manifest. Lane B · Tier A · issue #5.

Governed by D9, D12, D18, D20, D3. Owns this package. Must not read
ratecard/, labels/, evidence/ or detect/; the D12 import test fails the build
if this package's module graph reaches any of them.

``fees.py`` is this side's encoding of the public rate card, with every
number's source, as-of date and basis in its docstring; ``batch.py`` builds
one batch from a ``BatchSpec``; ``presets.py`` names the batches the CLI
generates; ``manifest.py`` reads the manifest back; ``v2.py`` writes the
files; ``money.py`` formats paise; ``command.py`` is the ``leakproof gen``
handler the integrator wires into ``cli.py``.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from leakproof.generator.batch import BatchSpec, default_scenario_counts, generate
from leakproof.generator.manifest import load_manifest, write_manifest
from leakproof.generator.presets import PRESETS, Preset, generate_preset, preset_dir
from leakproof.types import Manifest

__all__ = [
    "PRESETS",
    "BatchSpec",
    "Preset",
    "default_scenario_counts",
    "generate",
    "generate_batch",
    "generate_preset",
    "load_manifest",
    "preset_dir",
    "write_manifest",
]


def generate_batch(
    *,
    batch_id: str,
    seed: int,
    order_count: int,
    errors_per_class: int,
    out_dir: Path,
    as_of: date | None = None,
) -> Manifest:
    """Write ``orders.csv``, one ``settlement_<end-date>.txt`` per cycle,
    ``bank.csv``, ``seller_profile.json``, ``evidence.csv`` and
    ``manifest.json`` into ``out_dir`` and return the manifest (D9).

    ``errors_per_class`` seeded errors per class, dealt over the class's
    scenarios; true negatives, dispositions and the duplicate credit come
    with them (``default_scenario_counts``). ``as_of`` is the date the batch
    is cut: the last cycle ends on it, so it is also the batch's maximum
    settlement posted-date, the D18 default."""
    spec = BatchSpec(
        batch_id=batch_id,
        seed=seed,
        order_count=order_count,
        scenario_counts=default_scenario_counts(errors_per_class),
        as_of=as_of,
    )
    return generate(spec, out_dir)
