"""Claimability labels and the adversarial holdout. Lane F · Tier B · issue #9.

Governed by D12, P2, P3. Owns this package. Must not read evidence/,
ratecard/, generator/. ``claimability.json`` is frozen at the Wave 1 close;
its SHA-256 is recorded in contract.FROZEN_LABELS_SHA256 (ADR-0003).
"""

from __future__ import annotations

from pathlib import Path

from leakproof.scenarios import Scenario
from leakproof.types import ClaimabilityLabel, HoldoutCase


def load_labels(path: Path | None = None) -> dict[Scenario, ClaimabilityLabel]:
    raise NotImplementedError("lane F, issue #9")


def load_holdout() -> tuple[HoldoutCase, ...]:
    raise NotImplementedError("lane F, issue #9")
