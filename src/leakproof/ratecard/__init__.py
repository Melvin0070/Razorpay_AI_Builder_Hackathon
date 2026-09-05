"""Rate-card corpus with declared coverage. Lane C · Tier B · issue #6.

Governed by D17, D14, D3. Owns this package. Must not read generator/.
Implements the ``types.RateCard`` protocol; CONFIG_ERROR inside declared
coverage is a hard gate; cli.py appends it to gates.HARD_GATES at merge.
"""

from __future__ import annotations

from leakproof.ratecard.gate import GATE_NAME, config_error_gate, sweep
from leakproof.ratecard.loader import (
    CorpusError,
    RateCardCorpus,
    SlabBandRequiredError,
    SlabBasis,
    load_corpus,
    load_rate_card,
)

__all__ = [
    "GATE_NAME",
    "CorpusError",
    "RateCardCorpus",
    "SlabBandRequiredError",
    "SlabBasis",
    "config_error_gate",
    "load_corpus",
    "load_rate_card",
    "sweep",
]
