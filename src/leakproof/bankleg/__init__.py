"""Payout ↔ bank UTR reconciliation. Lane I · Tier C · issue #12.

Governed by D6. Owns this package. Reported separately; never in match rate.
"""

from __future__ import annotations

from leakproof.contract import paise_within
from leakproof.types import BankCredit, BankLegResult, SettlementHeader


def reconcile_payouts(
    headers: tuple[SettlementHeader, ...], credits: tuple[BankCredit, ...]
) -> BankLegResult:
    used: set[str] = set()
    matched = 0
    missing = []
    duplicates = {c.utr for c in credits if sum(x.utr == c.utr for x in credits) > 1}
    for header in sorted(headers, key=lambda h: (h.deposit_date, h.settlement_id)):
        candidates = sorted(
            (
                c
                for c in credits
                if c.line_id not in used
                and c.credit_date >= header.deposit_date
                and paise_within(c.amount_paise, header.total_amount_paise)
            ),
            key=lambda c: (c.credit_date, c.utr, c.line_id),
        )
        if candidates:
            used.add(candidates[0].line_id)
            matched += 1
        else:
            missing.append(header.settlement_id)
    return BankLegResult(len(headers), matched, tuple(missing), tuple(sorted(duplicates)))
