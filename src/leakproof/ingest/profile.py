"""Seller profile JSON loader (companion format, docs/specs/amazon-settlement-v2.md
"Companion inputs"). Config, not user-uploaded data: malformed profile JSON is
a build-time error, not a quarantine case, so this raises rather than
degrading -- there is no per-row citation to attach the fault to.

Every content-level fault (bad encoding, invalid JSON, a missing required
key, an unparsable capability date) raises the single ``ProfileError``,
naming the file and the cause (S13), instead of three unrelated exception
types (``UnicodeDecodeError``, ``json.JSONDecodeError``, ``KeyError``) with
no path attached. A missing file still raises ``FileNotFoundError`` --
that is the integrator's job, per every other parser in this package.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from leakproof.types import CapabilityFact, SellerProfile


class ProfileError(ValueError):
    """Malformed seller-profile content. The message names the file and the
    underlying cause."""


def _parse_date(path: Path, raw: str | None) -> date | None:
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise ProfileError(f"{path}: bad capability date {raw!r}: {exc}") from exc


def load_profile(path: Path) -> SellerProfile:
    raw_bytes = path.read_bytes()
    try:
        text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ProfileError(f"{path}: not valid UTF-8: {exc}") from exc

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ProfileError(f"{path}: invalid JSON: {exc}") from exc

    try:
        capabilities = tuple(
            CapabilityFact(
                name=c["name"],
                holds=bool(c["holds"]),
                valid_from=_parse_date(path, c.get("valid_from")),
                valid_to=_parse_date(path, c.get("valid_to")),
            )
            for c in data.get("capabilities", [])
        )
        return SellerProfile(
            seller_id=data["seller_id"],
            display_name=data["display_name"],
            capabilities=capabilities,
        )
    except KeyError as exc:
        raise ProfileError(f"{path}: missing required key {exc}") from exc
