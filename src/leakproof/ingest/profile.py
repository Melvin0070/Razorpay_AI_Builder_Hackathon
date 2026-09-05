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

    # S13/G3: valid JSON is not necessarily a JSON *object* -- a file wrapped
    # in an array, or reduced to a bare string or null, is the commonest
    # hand-edit mistake and must not surface as a bare AttributeError with no
    # file name attached.
    if not isinstance(data, dict):
        raise ProfileError(
            f"{path}: expected a JSON object at the top level, got {type(data).__name__}"
        )

    raw_capabilities = data.get("capabilities", [])
    if not isinstance(raw_capabilities, list):
        raise ProfileError(
            f"{path}: 'capabilities' must be a JSON array, got {type(raw_capabilities).__name__}"
        )

    try:
        capabilities = []
        for c in raw_capabilities:
            if not isinstance(c, dict):
                raise ProfileError(
                    f"{path}: capability entry must be a JSON object, got {type(c).__name__}"
                )
            capabilities.append(
                CapabilityFact(
                    name=c["name"],
                    holds=bool(c["holds"]),
                    valid_from=_parse_date(path, c.get("valid_from")),
                    valid_to=_parse_date(path, c.get("valid_to")),
                )
            )
        seller_id = data["seller_id"]
        display_name = data["display_name"]
    except KeyError as exc:
        raise ProfileError(f"{path}: missing required key {exc}") from exc

    if not isinstance(seller_id, str):
        raise ProfileError(f"{path}: seller_id must be a string, got {type(seller_id).__name__}")
    if not isinstance(display_name, str):
        raise ProfileError(
            f"{path}: display_name must be a string, got {type(display_name).__name__}"
        )

    return SellerProfile(
        seller_id=seller_id,
        display_name=display_name,
        capabilities=tuple(capabilities),
    )
