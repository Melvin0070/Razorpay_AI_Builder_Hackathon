"""Corpus loader and the ``types.RateCard`` implementation (D17, D14, D3).

The corpus is data, under ``corpus/``, one JSON file per source document, so a
rate can be re-read against its own page without touching Python. This module
turns that data into ``RateRule`` records and answers the two seam questions:
what does the corpus cover, and what does it say about one (kind, category,
as_of, principal).

Two dispositions, never one (D17). Outside the declared coverage a miss is
``UNCOVERED``, a documented limitation. Inside it a miss is ``CONFIG_ERROR``,
which ``gate.config_error_gate`` turns into a build failure naming category,
kind, slab and ``as_of``, so a corpus typo can never masquerade as the
three-category cap working as designed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from leakproof.contract import Disposition, LineKind, Paise
from leakproof.types import Citation, CoverageDeclaration, LookupMiss, RateLookup, RateRule

#: Files under ``corpus/`` are rule documents, except this one.
COVERAGE_FILE = "coverage.json"

_MONEY_FIELDS = ("percent_bp", "fixed_paise", "slab_min_paise", "slab_max_paise")


class CorpusError(ValueError):
    """The corpus on disk is not loadable. Distinct from CONFIG_ERROR, which is
    a well-formed corpus that cannot answer a question inside its coverage."""


def _parse_date(value: str, *, where: str) -> date:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise CorpusError(f"{where}: bad ISO date {value!r}") from exc


def _parse_int(value: Any, *, where: str) -> int | None:
    """Money and basis points are ``int`` or absent. A float in the corpus is a
    corpus bug, not a value to coerce (D3)."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise CorpusError(f"{where}: expected an integer or null, got {value!r}")
    return value


def _parse_citation(raw: dict[str, Any], *, where: str) -> Citation:
    for field in ("label", "url", "as_of", "verified"):
        if field not in raw:
            raise CorpusError(f"{where}: citation is missing {field!r}")
    if not isinstance(raw["verified"], bool):
        raise CorpusError(f"{where}: citation.verified must be a boolean")
    if not str(raw["url"]).startswith(("http://", "https://")):
        raise CorpusError(f"{where}: citation.url must be a URL, got {raw['url']!r}")
    return Citation(
        label=str(raw["label"]),
        url=str(raw["url"]),
        as_of=_parse_date(raw["as_of"], where=f"{where}.citation"),
        verified=raw["verified"],
    )


def _parse_kind(value: str, *, where: str) -> LineKind:
    try:
        return LineKind(value)
    except ValueError as exc:
        raise CorpusError(f"{where}: {value!r} is not a LineKind") from exc


def _parse_rule(raw: dict[str, Any], *, source: Citation, where: str) -> RateRule:
    rule_id = raw.get("rule_id")
    if not rule_id:
        raise CorpusError(f"{where}: rule_id is required")
    at = f"{where}[{rule_id}]"
    for field in ("kind", "category_id", "valid_from"):
        if field not in raw:
            raise CorpusError(f"{at}: {field!r} is required (write null for an absent value)")
    citation = _parse_citation(raw["citation"], where=at) if "citation" in raw else source
    values = {f: _parse_int(raw.get(f), where=f"{at}.{f}") for f in _MONEY_FIELDS}
    valid_to = raw.get("valid_to")
    rule = RateRule(
        rule_id=str(rule_id),
        kind=_parse_kind(raw["kind"], where=at),
        category_id=raw["category_id"] if raw.get("category_id") is not None else None,
        percent_bp=values["percent_bp"],
        fixed_paise=values["fixed_paise"],
        slab_min_paise=values["slab_min_paise"],
        slab_max_paise=values["slab_max_paise"],
        valid_from=_parse_date(raw["valid_from"], where=at),
        valid_to=_parse_date(valid_to, where=at) if valid_to is not None else None,
        citation=citation,
        audited=bool(raw.get("audited", True)),
    )
    if rule.valid_to is not None and rule.valid_to < rule.valid_from:
        raise CorpusError(f"{at}: valid_to {rule.valid_to} precedes valid_from {rule.valid_from}")
    if (
        rule.slab_min_paise is not None
        and rule.slab_max_paise is not None
        and rule.slab_max_paise < rule.slab_min_paise
    ):
        raise CorpusError(f"{at}: slab_max {rule.slab_max_paise} precedes slab_min")
    if rule.audited and rule.percent_bp is None and rule.fixed_paise is None:
        raise CorpusError(f"{at}: an audited rule must carry percent_bp or fixed_paise")
    if not rule.audited and (rule.percent_bp is not None or rule.fixed_paise is not None):
        raise CorpusError(f"{at}: an acknowledged rule must carry no rate (ADR-0005)")
    return rule


def _slab_contains(rule: RateRule, principal_paise: Paise) -> bool:
    """Slab bounds are inclusive on both ends; ``None`` is an open end."""
    if rule.slab_min_paise is not None and principal_paise < rule.slab_min_paise:
        return False
    return not (rule.slab_max_paise is not None and principal_paise > rule.slab_max_paise)


def _slab_text(rule: RateRule) -> str:
    low = "open" if rule.slab_min_paise is None else str(rule.slab_min_paise)
    high = "open" if rule.slab_max_paise is None else str(rule.slab_max_paise)
    return f"[{low}, {high}] paise"


@dataclass(frozen=True, slots=True)
class RateCardCorpus:
    """A loaded corpus. Implements ``types.RateCard``.

    ``lookup`` takes one argument the frozen Protocol does not name,
    ``principal_paise``, because a fee slab is a function of the order
    principal and the seam has no other way to select a band. It is optional so
    the three-argument Protocol call still type-checks and still works for
    every kind whose rule spans the whole principal range (fee GST, TCS, TDS,
    every acknowledgement). Asking for a slabbed kind without a principal is a
    caller bug and raises, rather than silently returning the lowest band: a
    wrong band is a wrong rupee amount, and deterministic money does not guess.
    An interface change request for the seam is in the lane report.
    """

    rules: tuple[RateRule, ...]
    declaration: CoverageDeclaration
    source_path: Path

    # ---------------------------------------------------------------- seam --

    def coverage(self) -> CoverageDeclaration:
        return self.declaration

    def lookup(
        self,
        kind: LineKind,
        category_id: str | None,
        as_of: date,
        principal_paise: Paise | None = None,
    ) -> RateLookup:
        uncovered = self._coverage_miss(kind, category_id, as_of)
        if uncovered is not None:
            return uncovered

        candidates = self.rules_for(kind, category_id, as_of)
        if not candidates:
            return self._config_error(
                kind,
                category_id,
                as_of,
                principal_paise,
                "no rule and no acknowledgement in the corpus",
            )

        if principal_paise is None:
            if len(candidates) == 1 and _is_open_slab(candidates[0]):
                return candidates[0]
            raise ValueError(
                f"{kind} for category {category_id!r} at {as_of.isoformat()} is priced in "
                f"{len(candidates)} slabs; lookup needs principal_paise to choose one"
            )

        matches = [r for r in candidates if _slab_contains(r, principal_paise)]
        if len(matches) == 1:
            return matches[0]
        if not matches:
            return self._config_error(
                kind,
                category_id,
                as_of,
                principal_paise,
                "slab gap: "
                + ", ".join(f"{r.rule_id} {_slab_text(r)}" for r in candidates)
                + " cover neither side of it",
            )
        return self._config_error(
            kind,
            category_id,
            as_of,
            principal_paise,
            "overlapping slabs: " + ", ".join(f"{r.rule_id} {_slab_text(r)}" for r in matches),
        )

    # ------------------------------------------------------------- helpers --

    def rules_for(
        self, kind: LineKind, category_id: str | None, as_of: date
    ) -> tuple[RateRule, ...]:
        """Rules in force at ``as_of`` for this kind, category-specific first
        and marketplace-wide (``category_id`` None) as the fallback, never both:
        a category rule always wins over the marketplace-wide one."""
        in_force = [r for r in self.rules if r.kind is kind and _applies_on(r, as_of)]
        specific = tuple(r for r in in_force if r.category_id == category_id)
        if specific:
            return specific
        return tuple(r for r in in_force if r.category_id is None)

    @property
    def audited_kinds(self) -> tuple[LineKind, ...]:
        return self.declaration.audited_kinds

    @property
    def acknowledged_kinds(self) -> tuple[LineKind, ...]:
        return self.declaration.acknowledged_kinds

    def covers(self, category_id: str | None, as_of: date) -> bool:
        return self._coverage_miss(LineKind.UNCLASSIFIED, category_id, as_of) is None

    def _coverage_miss(
        self, kind: LineKind, category_id: str | None, as_of: date
    ) -> LookupMiss | None:
        d = self.declaration
        if category_id is not None and category_id not in d.categories:
            return LookupMiss(
                disposition=Disposition.UNCOVERED,
                kind=kind,
                category_id=category_id,
                as_of=as_of,
                detail=(
                    f"category {category_id!r} is outside the declared coverage "
                    f"({', '.join(d.categories)})"
                ),
            )
        if as_of < d.valid_from or (d.valid_to is not None and as_of > d.valid_to):
            end = d.valid_to.isoformat() if d.valid_to else "open"
            return LookupMiss(
                disposition=Disposition.UNCOVERED,
                kind=kind,
                category_id=category_id,
                as_of=as_of,
                detail=(
                    f"as_of {as_of.isoformat()} is outside the declared coverage window "
                    f"[{d.valid_from.isoformat()}, {end}]"
                ),
            )
        return None

    def _config_error(
        self,
        kind: LineKind,
        category_id: str | None,
        as_of: date,
        principal_paise: Paise | None,
        why: str,
    ) -> LookupMiss:
        principal = "unspecified" if principal_paise is None else f"{principal_paise} paise"
        return LookupMiss(
            disposition=Disposition.CONFIG_ERROR,
            kind=kind,
            category_id=category_id,
            as_of=as_of,
            detail=(
                f"category={category_id or 'marketplace-wide'} kind={kind.value} "
                f"principal={principal} as_of={as_of.isoformat()}: {why}"
            ),
        )


def _applies_on(rule: RateRule, on: date) -> bool:
    if on < rule.valid_from:
        return False
    return not (rule.valid_to is not None and on > rule.valid_to)


def _is_open_slab(rule: RateRule) -> bool:
    return rule.slab_min_paise is None and rule.slab_max_paise is None


def _default_corpus_path() -> Path:
    return Path(__file__).resolve().parent / "corpus"


def load_rate_card(path: Path | None = None) -> RateCardCorpus:
    """Read the corpus at ``path`` (default: the packaged one) into a RateCard.

    Every rule file is ``{source: <citation>, rules: [...]}``; a rule may carry
    its own ``citation`` when its provenance differs from the file's, which is
    how a rate read off a primary page keeps a ``verified: false`` flag when
    only its validity window came from a secondary one (D14).
    """
    root = Path(path) if path is not None else _default_corpus_path()
    if not root.is_dir():
        raise CorpusError(f"corpus directory not found: {root}")

    coverage_raw = _read_json(root / COVERAGE_FILE)
    for field in ("categories", "valid_from"):
        if field not in coverage_raw:
            raise CorpusError(f"{COVERAGE_FILE}: {field!r} is required")
    rules: list[RateRule] = []
    seen: dict[str, str] = {}
    for file in sorted(root.glob("*.json")):
        if file.name == COVERAGE_FILE:
            continue
        doc = _read_json(file)
        if "source" not in doc:
            raise CorpusError(f"{file.name}: every rule document needs a 'source' citation (D14)")
        source = _parse_citation(doc["source"], where=file.name)
        for raw in doc.get("rules", ()):
            rule = _parse_rule(raw, source=source, where=file.name)
            if rule.rule_id in seen:
                raise CorpusError(
                    f"duplicate rule_id {rule.rule_id!r} in {file.name} and {seen[rule.rule_id]}"
                )
            seen[rule.rule_id] = file.name
            rules.append(rule)

    if not rules:
        raise CorpusError(f"corpus at {root} declares no rules")

    ordered = tuple(rules)
    declaration = CoverageDeclaration(
        categories=tuple(coverage_raw["categories"]),
        valid_from=_parse_date(coverage_raw["valid_from"], where=COVERAGE_FILE),
        valid_to=(
            _parse_date(coverage_raw["valid_to"], where=COVERAGE_FILE)
            if coverage_raw.get("valid_to") is not None
            else None
        ),
        # Derived, never a second hand-maintained list: a kind is audited when
        # the corpus prices it and acknowledged when the corpus only knows it.
        audited_kinds=_kinds(ordered, audited=True),
        acknowledged_kinds=_kinds(ordered, audited=False),
    )
    overlap = set(declaration.audited_kinds) & set(declaration.acknowledged_kinds)
    if overlap:
        raise CorpusError(
            "a kind is either audited or acknowledged, never both: "
            + ", ".join(sorted(k.value for k in overlap))
        )
    return RateCardCorpus(rules=ordered, declaration=declaration, source_path=root)


def _kinds(rules: tuple[RateRule, ...], *, audited: bool) -> tuple[LineKind, ...]:
    found = {r.kind for r in rules if r.audited is audited}
    return tuple(k for k in LineKind if k in found)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise CorpusError(f"corpus file not found: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CorpusError(f"{path.name}: {exc}") from exc
