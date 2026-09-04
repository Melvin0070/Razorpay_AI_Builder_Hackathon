"""Rate-card corpus with declared coverage. Lane C · Tier B · issue #6.

Governed by D17, D14, D3. Owns this package. Must not read generator/.
Implements the ``types.RateCard`` protocol; CONFIG_ERROR inside declared
coverage is a hard gate registered in gates.HARD_GATES at merge.
"""

from __future__ import annotations

from pathlib import Path

from leakproof.types import RateCard


def load_rate_card(path: Path | None = None) -> RateCard:
    raise NotImplementedError("lane C, issue #6")
