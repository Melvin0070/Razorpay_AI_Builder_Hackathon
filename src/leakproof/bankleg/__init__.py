"""Payout ↔ bank UTR reconciliation. Lane I · Tier C · issue #12.

Governed by D6. Owns this package. Reported separately; never in match rate.
"""

from __future__ import annotations

from leakproof.types import BankCredit, BankLegResult, SettlementHeader


def reconcile_payouts(
    headers: tuple[SettlementHeader, ...], credits: tuple[BankCredit, ...]
) -> BankLegResult:
    raise NotImplementedError("lane I, issue #12")
