"""JSON projection of seam records. Integrator-owned.

Forward only: dataclass → plain JSON types. Enums by value, dates as ISO-8601,
tuples as lists. Derived sums (``RupeeLines.identified``, ``.total``,
``MatchRates.strict``, ``.adjusted``, ``Finding.finding_id``) are written out
explicitly so the JSON the dashboard reads carries the numbers it shows.
Audit-log canonicalisation is NOT this function; lane E owns that (D21).
"""

from __future__ import annotations

import dataclasses
import json
from datetime import date
from enum import Enum
from typing import Any

_DERIVED: dict[str, tuple[str, ...]] = {
    "RupeeLines": ("identified", "total"),
    "MatchRates": ("strict", "adjusted"),
    "Finding": ("finding_id",),
}


def to_jsonable(obj: Any) -> Any:
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        out = {f.name: to_jsonable(getattr(obj, f.name)) for f in dataclasses.fields(obj)}
        for name in _DERIVED.get(type(obj).__name__, ()):
            out[name] = to_jsonable(getattr(obj, name))
        return out
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, date):
        return obj.isoformat()
    if isinstance(obj, list | tuple):
        return [to_jsonable(x) for x in obj]
    if isinstance(obj, dict):
        return {str(k): to_jsonable(v) for k, v in obj.items()}
    if obj is None or isinstance(obj, str | int | float | bool):
        return obj
    raise TypeError(f"cannot serialise {type(obj).__name__}")


def dumps(obj: Any, *, indent: int | None = 2) -> str:
    return json.dumps(to_jsonable(obj), indent=indent, ensure_ascii=False) + "\n"
