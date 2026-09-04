"""Seller profile JSON loader (companion format, docs/specs/amazon-settlement-v2.md
"Companion inputs"). Config, not user-uploaded data: malformed profile JSON is
a build-time error, not a quarantine case, so this raises rather than
degrading -- there is no per-row citation to attach the fault to.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from leakproof.types import CapabilityFact, SellerProfile


def _parse_date(raw: str | None) -> date | None:
    return date.fromisoformat(raw) if raw else None


def load_profile(path: Path) -> SellerProfile:
    data = json.loads(path.read_text(encoding="utf-8"))
    capabilities = tuple(
        CapabilityFact(
            name=c["name"],
            holds=bool(c["holds"]),
            valid_from=_parse_date(c.get("valid_from")),
            valid_to=_parse_date(c.get("valid_to")),
        )
        for c in data.get("capabilities", [])
    )
    return SellerProfile(
        seller_id=data["seller_id"],
        display_name=data["display_name"],
        capabilities=capabilities,
    )
