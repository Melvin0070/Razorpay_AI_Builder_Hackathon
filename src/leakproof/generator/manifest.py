"""Manifest file round trip. ``write_manifest`` is ``serialize.dumps``;
``load_manifest`` is its exact inverse for the fields ``types.Manifest`` carries."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from leakproof.contract import ErrorClass
from leakproof.scenarios import Scenario
from leakproof.serialize import dumps
from leakproof.types import CoverageWindow, Manifest, SeededError


def write_manifest(manifest: Manifest, path: Path) -> None:
    path.write_text(dumps(manifest), encoding="utf-8")


def load_manifest(path: Path) -> Manifest:
    data = json.loads(path.read_text(encoding="utf-8"))
    seeded = tuple(
        SeededError(
            scenario=Scenario(entry["scenario"]),
            order_id=entry["order_id"],
            expected_class=(
                None if entry["expected_class"] is None else ErrorClass(entry["expected_class"])
            ),
            expected_amount_paise=entry["expected_amount_paise"],
            line_ids=tuple(entry["line_ids"]),
            note=entry["note"],
        )
        for entry in data["seeded"]
    )
    return Manifest(
        batch_id=data["batch_id"],
        seed=data["seed"],
        as_of=date.fromisoformat(data["as_of"]),
        cycle_days=data["cycle_days"],
        coverage=CoverageWindow(
            date.fromisoformat(data["coverage"]["start"]),
            date.fromisoformat(data["coverage"]["end"]),
        ),
        order_count=data["order_count"],
        categories=tuple(data["categories"]),
        seeded=seeded,
        files=dict(data["files"]),
        materiality_floor_paise=data["materiality_floor_paise"],
        generator_version=data["generator_version"],
    )
