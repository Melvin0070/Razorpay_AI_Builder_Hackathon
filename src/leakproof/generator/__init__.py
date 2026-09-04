"""Synthetic batches and manifest. Lane B · Tier A · issue #5.

Governed by D9, D12, D18, D20, D3. Owns this package. Must not read
ratecard/ or labels/; the D12 import test fails the build if this package's
module graph reaches either.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from leakproof.types import Manifest


def generate_batch(
    *,
    batch_id: str,
    seed: int,
    order_count: int,
    errors_per_class: int,
    out_dir: Path,
    as_of: date | None = None,
) -> Manifest:
    raise NotImplementedError("lane B, issue #5")
