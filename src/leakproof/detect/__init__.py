"""Detectors 1, 2, 5, 6, 7, 8. Lane J · Tier A · issue #13.

Governed by D23, D1, D3, D19 (claimed line), D20 (cycle rules for 5 and 6),
and the class table in contract. Owns this package. Must not read generator/
or labels/. Every detector emits through make_finding(), which raises on an
empty source set, a claimed line outside it, or a class/mechanism pair the
class table forbids.
"""

from __future__ import annotations

from typing import Protocol

from leakproof.types import DetectorContext, Finding, FoldedOrder


class Detector(Protocol):
    def __call__(self, folded: FoldedOrder, ctx: DetectorContext) -> list[Finding]: ...


def make_finding(**fields: object) -> Finding:
    raise NotImplementedError("lane J, issue #13")


DETECTORS: tuple[Detector, ...] = ()


def run_detectors(folded: tuple[FoldedOrder, ...], ctx: DetectorContext) -> list[Finding]:
    raise NotImplementedError("lane J, issue #13")
