"""Eligibility rules, evidence requirements, deadline arithmetic. Lane K · Tier A · issue #14.

Governed by D14, D18 and the inputs of precedence steps 1–5. Owns this
package. Must not read labels/ (D12 wall; a different agent from lane F).
"""

from __future__ import annotations

from datetime import date

from leakproof.contract import Mechanism
from leakproof.types import Assessment, Deadline, Finding, FoldedOrder, SellerProfile


def assess(
    finding: Finding, folded: FoldedOrder, profile: SellerProfile, as_of: date
) -> Assessment:
    raise NotImplementedError("lane K, issue #14")


def deadline_for(mechanism: Mechanism, event_date: date | None, as_of: date) -> Deadline:
    raise NotImplementedError("lane K, issue #14")
