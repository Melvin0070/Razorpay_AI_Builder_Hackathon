"""Corpus loader and the ``types.RateCard`` implementation (D17, D14, D3).

The corpus is data, under ``corpus/``, one JSON file per source document, so a
rate can be re-read against its own page without touching Python. This module
turns that data into ``RateRule`` records and answers the two seam questions:
what does the corpus cover, and what does it say about one (kind, category,
as_of, band key).

Two dispositions, never one (D17). Outside the declared coverage a miss is
``UNCOVERED``, a documented limitation. Inside it a miss is ``CONFIG_ERROR``,
which ``gate.config_error_gate`` turns into a build failure naming category,
kind, slab and ``as_of``, so a corpus typo can never masquerade as the
three-category cap working as designed.

**Slab bounds are not order totals.** Amazon bands each fee on its own figure,
and the two banded kinds band on two different ones (``SlabBasis``). Feeding a
row's ``Order.principal_paise`` to either one is wrong whenever the row is
multi-unit or the seller charged shipping, and wrong by a whole band: three
shirts at 400 rupees band as 40000 paise, not as the row's 120000. Every banded
rule therefore carries the basis its bounds are read on, and the caller computes
the band key.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Any

from leakproof.contract import Disposition, LineKind, Paise
from leakproof.types import Citation, CoverageDeclaration, LookupMiss, RateLookup, RateRule

#: Files under ``corpus/`` are rule documents, except this one.
COVERAGE_FILE = "coverage.json"

_MONEY_FIELDS = ("percent_bp", "fixed_paise", "slab_min_paise", "slab_max_paise")


class SlabBasis(StrEnum):
    """The figure a banded rule's slab bounds are read on.

    Amazon states each one on the page the bands come from, and they differ:
    the referral-fee table bands on the price of one item, the closing-fee
    table on what the buyer paid for it. ``types.RateRule`` gains this as a
    typed field at the wave close; until then the loader carries it beside the
    rule and the corpus states it per rule and in ``coverage.json``.
    """

    #: Referral fee: the item's own price, i.e. the row's principal divided by
    #: its quantity. A three-unit row bands on one unit, never on the total.
    UNIT_ITEM_PRICE = "unit-item-price"
    #: Fixed closing fee: "item price that is paid by the buyer (including any
    #: shipping or gift-wrap charges charged by the seller)", quoted from the
    #: closing-fee section of the fee schedule.
    BUYER_PAID_ITEM_PRICE = "buyer-paid-item-price"


class CorpusError(ValueError):
    """The corpus on disk is not loadable. Distinct from CONFIG_ERROR, which is
    a well-formed corpus that cannot answer a question inside its coverage."""


class SlabBandRequiredError(LookupError):
    """``lookup`` was asked for a banded kind without a band key.

    Its own type, and deliberately not a ``ValueError``: ``CorpusError`` and
    ``LineKind(value)`` both raise that, and a caller catching this one is
    catching a fixable mistake of its own (compute the band key
    ``band_basis(kind)`` names) rather than a broken corpus. The kinds that
    need one are ``RateCardCorpus.slabbed_kinds``.
    """

    def __init__(self, kind: LineKind, category_id: str | None, as_of: date, bands: int) -> None:
        super().__init__(
            f"{kind.value} for category {category_id!r} at {as_of.isoformat()} is priced in "
            f"{bands} bands; lookup needs band_key_paise to choose one"
        )
        self.kind = kind
        self.category_id = category_id
        self.as_of = as_of


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


def _parse_slab_basis(raw: dict[str, Any], rule: RateRule, *, where: str) -> SlabBasis | None:
    """Required on a banded rule, forbidden on an unbanded one.

    Forbidden rather than ignored: a basis on a rule with no bounds would imply
    a band that does not exist, and the fee GST, TCS and TDS rules ride on
    whatever the fee or the supply was, not on a price band.
    """
    declared = raw.get("slab_basis")
    banded = rule.slab_min_paise is not None or rule.slab_max_paise is not None
    if not banded:
        if declared is not None:
            raise CorpusError(f"{where}: slab_basis on a rule with no slab bounds")
        return None
    if declared is None:
        raise CorpusError(
            f"{where}: a banded rule must name the slab_basis its bounds are read on "
            f"({', '.join(b.value for b in SlabBasis)})"
        )
    try:
        return SlabBasis(declared)
    except ValueError as exc:
        raise CorpusError(f"{where}: {declared!r} is not a slab basis") from exc


def _parse_rule(
    raw: dict[str, Any], *, source: Citation, where: str
) -> tuple[RateRule, SlabBasis | None]:
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
    # A rate out of range loads clean, passes every slab and window check and
    # sweeps green, then produces a negative expected fee that reads as money
    # owed to the seller. A negative slab bound is worse than wrong: the gate
    # probes band keys from zero up, so nothing ever reaches it.
    if rule.percent_bp is not None and not 0 <= rule.percent_bp <= 10_000:
        raise CorpusError(
            f"{at}: percent_bp {rule.percent_bp} is outside 0..10000 basis points (0..100%)"
        )
    for field in ("fixed_paise", "slab_min_paise", "slab_max_paise"):
        amount = getattr(rule, field)
        if amount is not None and amount < 0:
            raise CorpusError(f"{at}: {field} {amount} is negative; paise are unsigned here")
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
    return rule, _parse_slab_basis(raw, rule, where=at)


def _slab_contains(rule: RateRule, band_key_paise: Paise) -> bool:
    """Slab bounds are inclusive on both ends; ``None`` is an open end."""
    if rule.slab_min_paise is not None and band_key_paise < rule.slab_min_paise:
        return False
    return not (rule.slab_max_paise is not None and band_key_paise > rule.slab_max_paise)


def _slab_text(rule: RateRule) -> str:
    low = "open" if rule.slab_min_paise is None else str(rule.slab_min_paise)
    high = "open" if rule.slab_max_paise is None else str(rule.slab_max_paise)
    return f"[{low}, {high}] paise"


@dataclass(frozen=True, slots=True)
class RateCardCorpus:
    """A loaded corpus. Implements ``types.RateCard``.

    ``lookup`` takes one argument the frozen Protocol does not name,
    ``band_key_paise``, because a fee slab is a function of a price and the
    seam has no other way to select a band. It is optional so the
    three-argument Protocol call still type-checks and still works for every
    kind whose rule spans the whole range (fee GST, TCS, TDS, every
    acknowledgement). Asking for a banded kind without a band key is a caller
    bug and raises ``SlabBandRequiredError``, rather than silently returning the
    lowest band: a wrong band is a wrong rupee amount, and deterministic money
    does not guess. An interface change request for the seam is in the lane
    report.
    """

    rules: tuple[RateRule, ...]
    declaration: CoverageDeclaration
    source_path: Path
    #: rule_id -> the figure that rule's bounds are read on. A side table only
    #: until ``types.RateRule`` gains the field at the wave close.
    slab_bases: tuple[tuple[str, SlabBasis], ...] = ()

    # ---------------------------------------------------------------- seam --

    def coverage(self) -> CoverageDeclaration:
        return self.declaration

    def lookup(
        self,
        kind: LineKind,
        category_id: str | None,
        as_of: date,
        band_key_paise: Paise | None = None,
    ) -> RateLookup:
        """The rule in force, or the miss that explains why there is none.

        ``band_key_paise`` is the **band key**, not the order total: the figure
        this kind's slab bounds are read on, which ``band_basis(kind)`` names
        and ``SlabBasis`` defines. For ``COMMISSION`` that is one unit's item
        price (``order.principal_paise // order.quantity``); for
        ``FIXED_CLOSING_FEE`` it is what the buyer paid for the item, seller
        shipping and gift wrap included. Passing a multi-unit row's principal
        to the first, or an item price without seller shipping to the second,
        selects a neighbouring band and produces a fee that is wrong by more
        than the materiality floor.
        """
        uncovered = self._coverage_miss(kind, category_id, as_of) or self._kind_miss(
            kind, category_id, as_of
        )
        if uncovered is not None:
            return uncovered

        candidates = self.rules_for(kind, category_id, as_of)
        if not candidates:
            # The kind is declared, so the corpus claims to answer for it and
            # this cell is a hole in that claim: a missing window, or a
            # category the schedule was never encoded for.
            return self._config_error(
                kind,
                category_id,
                as_of,
                band_key_paise,
                "the corpus declares this kind but has no rule in force here",
            )

        if band_key_paise is None:
            # One band in force is no choice to make, whether or not it is
            # bounded: the earlier version demanded both ends open and so
            # raised on an unambiguous half-open band. A key outside a lone
            # band is a hole in the corpus, which the gate reports as a
            # CONFIG_ERROR, not a caller mistake to raise on here.
            if len(candidates) == 1:
                return candidates[0]
            raise SlabBandRequiredError(kind, category_id, as_of, len(candidates))

        matches = [r for r in candidates if _slab_contains(r, band_key_paise)]
        if len(matches) == 1:
            return matches[0]
        if not matches:
            return self._config_error(
                kind,
                category_id,
                as_of,
                band_key_paise,
                "slab gap: "
                + ", ".join(f"{r.rule_id} {_slab_text(r)}" for r in candidates)
                + " cover neither side of it",
            )
        return self._config_error(
            kind,
            category_id,
            as_of,
            band_key_paise,
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

    def slab_basis(self, rule_id: str) -> SlabBasis | None:
        """The figure one rule's bounds are read on; None when it has none."""
        return dict(self.slab_bases).get(rule_id)

    def band_basis(self, kind: LineKind) -> SlabBasis | None:
        """What a caller must compute to look this kind up, or None when the
        kind is not banded and any band key does. The loader has already
        checked that every banded rule of a kind agrees on it."""
        bases = dict(self.slab_bases)
        for rule in self.rules:
            if rule.kind is kind and rule.rule_id in bases:
                return bases[rule.rule_id]
        return None

    @property
    def slabbed_kinds(self) -> tuple[LineKind, ...]:
        """Kinds a caller must always pass a band key for. Discoverable rather
        than docstring-only: ``lookup`` raises ``SlabBandRequiredError`` without one,
        and ``band_basis(kind)`` says what figure to compute."""
        banded = {rule_id for rule_id, _ in self.slab_bases}
        kinds = {r.kind for r in self.rules if r.rule_id in banded}
        return tuple(k for k in LineKind if k in kinds)

    @property
    def category_scoped_kinds(self) -> tuple[LineKind, ...]:
        """Kinds the corpus prices per category, so a lookup with no category
        cannot resolve one. Derived: a kind qualifies when it has rules and
        every one of them names a category."""
        scoped = {r.kind for r in self.rules if r.category_id is not None}
        wide = {r.kind for r in self.rules if r.category_id is None}
        return tuple(k for k in LineKind if k in scoped - wide)

    @property
    def audited_kinds(self) -> tuple[LineKind, ...]:
        return self.declaration.audited_kinds

    @property
    def acknowledged_kinds(self) -> tuple[LineKind, ...]:
        return self.declaration.acknowledged_kinds

    def covers(self, category_id: str | None, as_of: date) -> bool:
        return self._coverage_miss(LineKind.UNCLASSIFIED, category_id, as_of) is None

    def declares(self, kind: LineKind) -> bool:
        """Whether the corpus claims to answer for this kind at all, audited or
        acknowledged. The structural test behind the class-8 hole: a caller
        holding only the frozen seam reads the same fact off ``coverage()``."""
        d = self.declaration
        return kind in d.audited_kinds or kind in d.acknowledged_kinds

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

    def _kind_miss(self, kind: LineKind, category_id: str | None, as_of: date) -> LookupMiss | None:
        """Coverage misses that depend on the kind, kept out of ``covers``.

        Both are limitations, not corpus bugs, and both must stay out of
        CONFIG_ERROR: the gate fails the build on that disposition, and a build
        that fails for a hole the corpus never claimed to fill would make the
        gate unrunnable rather than informative.
        """
        d = self.declaration
        if not self.declares(kind):
            # ADR-0005 decision 2: a kind with neither rule nor acknowledgement
            # is the deliberate class-8 hole (code-known-no-rule), reached
            # through this miss. Callers tell it apart from an unknown category
            # by testing the kind against coverage(), never by reading detail.
            return LookupMiss(
                disposition=Disposition.UNCOVERED,
                kind=kind,
                category_id=category_id,
                as_of=as_of,
                detail=(
                    f"{kind.value} is outside the declared coverage: the corpus declares "
                    f"neither an audited rule nor an acknowledgement for it"
                ),
            )
        # A settlement line whose order is absent from the seller's export (the
        # orphan case D5 and D7 model) carries a COMMISSION deduction and no
        # category at all, and the caller passes None. That is a limitation of
        # the inputs, not a corpus bug: UNCOVERED, never CONFIG_ERROR.
        if category_id is None and kind in self.category_scoped_kinds:
            return LookupMiss(
                disposition=Disposition.UNCOVERED,
                kind=kind,
                category_id=None,
                as_of=as_of,
                detail=(
                    f"{kind.value} is priced per category and no category is known for "
                    f"this line; the corpus prices it for {', '.join(d.categories)}"
                ),
            )
        return None

    def _config_error(
        self,
        kind: LineKind,
        category_id: str | None,
        as_of: date,
        band_key_paise: Paise | None,
        why: str,
    ) -> LookupMiss:
        band_key = "unspecified" if band_key_paise is None else f"{band_key_paise} paise"
        return LookupMiss(
            disposition=Disposition.CONFIG_ERROR,
            kind=kind,
            category_id=category_id,
            as_of=as_of,
            detail=(
                f"category={category_id or 'marketplace-wide'} kind={kind.value} "
                f"band_key={band_key} as_of={as_of.isoformat()}: {why}"
            ),
        )


def _applies_on(rule: RateRule, on: date) -> bool:
    if on < rule.valid_from:
        return False
    return not (rule.valid_to is not None and on > rule.valid_to)


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
    for field in ("categories", "valid_from", "audited_kinds", "acknowledged_kinds"):
        if field not in coverage_raw:
            raise CorpusError(f"{COVERAGE_FILE}: {field!r} is required")
    rules: list[RateRule] = []
    bases: dict[str, SlabBasis] = {}
    seen: dict[str, str] = {}
    for file in sorted(root.glob("*.json")):
        if file.name == COVERAGE_FILE:
            continue
        doc = _read_json(file)
        if "source" not in doc:
            raise CorpusError(f"{file.name}: every rule document needs a 'source' citation (D14)")
        source = _parse_citation(doc["source"], where=file.name)
        for raw in doc.get("rules", ()):
            rule, basis = _parse_rule(raw, source=source, where=file.name)
            if rule.rule_id in seen:
                raise CorpusError(
                    f"duplicate rule_id {rule.rule_id!r} in {file.name} and {seen[rule.rule_id]}"
                )
            seen[rule.rule_id] = file.name
            rules.append(rule)
            if basis is not None:
                bases[rule.rule_id] = basis

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
        audited_kinds=_declared_kinds(coverage_raw, "audited_kinds"),
        acknowledged_kinds=_declared_kinds(coverage_raw, "acknowledged_kinds"),
    )
    overlap = set(declaration.audited_kinds) & set(declaration.acknowledged_kinds)
    if overlap:
        raise CorpusError(
            "a kind is either audited or acknowledged, never both: "
            + ", ".join(sorted(k.value for k in overlap))
        )
    _check_declared_kinds(ordered, declaration)
    _check_slab_bases(ordered, bases, coverage_raw)
    return RateCardCorpus(
        rules=ordered,
        declaration=declaration,
        source_path=root,
        slab_bases=tuple(sorted(bases.items())),
    )


def _declared_kinds(coverage_raw: dict[str, Any], field: str) -> tuple[LineKind, ...]:
    """One of ``coverage.json``'s two kind lists, in ``LineKind`` order."""
    raw = coverage_raw[field]
    if not isinstance(raw, list):
        raise CorpusError(f"{COVERAGE_FILE}.{field}: expected a list of kinds, got {raw!r}")
    kinds = {_parse_kind(str(v), where=f"{COVERAGE_FILE}.{field}") for v in raw}
    if len(kinds) != len(raw):
        raise CorpusError(f"{COVERAGE_FILE}.{field}: a kind is listed twice")
    return tuple(k for k in LineKind if k in kinds)


def _check_declared_kinds(rules: tuple[RateRule, ...], declaration: CoverageDeclaration) -> None:
    """The declared kinds and the kinds the rules carry must be the same set.

    Deriving the declaration from the rules alone made the D17 gate
    tautological on kinds: ``sweep`` walks the declared kinds, so deleting a
    whole rule document deleted the claim along with the rules and the gate
    stayed green while every lookup of that kind missed at runtime. Two
    statements, checked against each other, is the same shape ``_check_slab_bases``
    already uses.
    """
    priced, acknowledged = _kinds(rules, audited=True), _kinds(rules, audited=False)
    both = set(priced) & set(acknowledged)
    if both:
        raise CorpusError(
            "a kind is either audited or acknowledged, never both: "
            + ", ".join(sorted(k.value for k in both))
        )
    problems: list[str] = []
    for label, declared, derived in (
        ("audited", declaration.audited_kinds, priced),
        ("acknowledged", declaration.acknowledged_kinds, acknowledged),
    ):
        missing = sorted(k.value for k in set(declared) - set(derived))
        extra = sorted(k.value for k in set(derived) - set(declared))
        if missing:
            problems.append(
                f"{COVERAGE_FILE} declares {label} kind(s) no rule carries: {', '.join(missing)}"
            )
        if extra:
            problems.append(
                f"rules carry {label} kind(s) {COVERAGE_FILE} does not declare: {', '.join(extra)}"
            )
    if problems:
        raise CorpusError("; ".join(problems))


def _check_slab_bases(
    rules: tuple[RateRule, ...], bases: dict[str, SlabBasis], coverage_raw: dict[str, Any]
) -> None:
    """One basis per banded kind, and the same one ``coverage.json`` declares.

    The per-rule field is what a reader of a rule document sees; the coverage
    block is what the dashboard shows and what a caller reads before computing
    a band key. Two statements of the same fact only help if they are checked
    against each other.
    """
    per_kind: dict[LineKind, SlabBasis] = {}
    for rule in rules:
        basis = bases.get(rule.rule_id)
        if basis is None:
            continue
        held = per_kind.setdefault(rule.kind, basis)
        if held is not basis:
            raise CorpusError(
                f"{rule.kind.value} bands on {held.value} and on {basis.value} "
                f"({rule.rule_id}); one kind is read on one figure"
            )
    declared_raw = coverage_raw.get("slab_bases")
    if declared_raw is None and not per_kind:
        return
    if declared_raw is None:
        raise CorpusError(
            f"{COVERAGE_FILE}: 'slab_bases' is required; name the figure each banded "
            "kind's bounds are read on"
        )
    try:
        declared = {LineKind(k): SlabBasis(v) for k, v in declared_raw.items()}
    except ValueError as exc:
        raise CorpusError(f"{COVERAGE_FILE}.slab_bases: {exc}") from exc
    if declared != per_kind:
        raise CorpusError(
            f"{COVERAGE_FILE}.slab_bases declares "
            + (", ".join(f"{k.value}={v.value}" for k, v in sorted(declared.items())) or "nothing")
            + " but the rules band "
            + (", ".join(f"{k.value}={v.value}" for k, v in sorted(per_kind.items())) or "nothing")
        )


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
