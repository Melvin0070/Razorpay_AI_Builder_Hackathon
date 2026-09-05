"""The CONFIG_ERROR hard gate (D17). Appended to ``gates.HARD_GATES`` by cli.py.

The registration lives in the composition root rather than in ``gates.py``: the
shared gate module must stay wall-neutral (``tests/test_anticircularity.py``
asserts it reaches no lane package), so it cannot import this one.

D17's whole point is that the two miss dispositions must not be confusable. A
lookup miss outside the declared coverage is `UNCOVERED`, a limitation the
README states. A miss inside it is a corpus bug, and a corpus bug that only
showed up as a slightly lower recall number would look exactly like the
three-category cap working as designed. So the sweep below probes every place a
corpus typo can hide -- both sides of every slab bound, both sides of every
validity edge, every declared category, every kind the corpus claims -- and
fails the build naming the category, slab and ``as_of`` of the first miss.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from leakproof.contract import Disposition, LineKind, Paise
from leakproof.gates import GateResult
from leakproof.ratecard.loader import RateCardCorpus, load_rate_card
from leakproof.types import LookupMiss

GATE_NAME = "ratecard-config-error"


#: How far past the last dated edge to probe an open-ended validity window. Ten
#: years, so the sweep reaches beyond any plausible batch without reading a
#: clock (D18 bans the system clock outside cli.py).
_OPEN_WINDOW_PROBE_DAYS = 3_650

#: Probed in every slab sweep so a corpus that forgot its lowest band fails even
#: if every bound it does declare is consistent.
_FLOOR_PROBE_PAISE: Paise = 0

_DAY = timedelta(days=1)


def config_error_gate(path: Path | None = None) -> GateResult:
    """Sweep the corpus and fail on any CONFIG_ERROR inside declared coverage."""
    card = load_rate_card(path)
    problems = [m.detail for m in sweep(card)]
    if problems:
        head = problems[0]
        detail = f"{len(problems)} config error(s); first: {head}"
        return GateResult(GATE_NAME, False, detail)
    covered = ", ".join(card.coverage().categories)
    return GateResult(
        GATE_NAME,
        True,
        f"no config error across {covered} x {len(card.audited_kinds)} audited kinds "
        f"and {len(card.acknowledged_kinds)} acknowledged kinds",
    )


def sweep(card: RateCardCorpus) -> tuple[LookupMiss, ...]:
    """Every CONFIG_ERROR the corpus can produce inside its declared coverage.

    Acknowledged kinds are swept alongside audited ones: an acknowledgement
    that fails to resolve would send an ordinary shipping fee to class 8, which
    is the flood ADR-0005 exists to prevent, so it is a build failure too.
    """
    misses: list[LookupMiss] = []
    kinds = (*card.audited_kinds, *card.acknowledged_kinds)
    for as_of in _probe_dates(card):
        for category_id in card.coverage().categories:
            for kind in kinds:
                for principal in _probe_band_keys(card, kind, category_id, as_of):
                    result = card.lookup(kind, category_id, as_of, principal)
                    if isinstance(result, LookupMiss) and (
                        result.disposition is Disposition.CONFIG_ERROR
                    ):
                        misses.append(result)
    return tuple(misses)


def _probe_dates(card: RateCardCorpus) -> tuple[date, ...]:
    """Both sides of every validity edge, clipped into the declared window."""
    d = card.coverage()
    edges: set[date] = {d.valid_from}
    if d.valid_to is not None:
        edges.add(d.valid_to)
    for rule in card.rules:
        edges.add(rule.valid_from)
        if rule.valid_to is not None:
            edges.add(rule.valid_to)
    probes: set[date] = set()
    for edge in edges:
        probes.update({edge - _DAY, edge, edge + _DAY})
    if d.valid_to is None:
        probes.add(max(edges) + timedelta(days=_OPEN_WINDOW_PROBE_DAYS))
    end = d.valid_to
    inside = [p for p in probes if p >= d.valid_from and (end is None or p <= end)]
    return tuple(sorted(inside))


def _probe_band_keys(
    card: RateCardCorpus, kind: LineKind, category_id: str | None, as_of: date
) -> tuple[Paise, ...]:
    """Both sides of every slab bound the corpus declares for this cell."""
    probes: set[Paise] = {_FLOOR_PROBE_PAISE}
    highest = _FLOOR_PROBE_PAISE
    for rule in card.rules_for(kind, category_id, as_of):
        for bound in (rule.slab_min_paise, rule.slab_max_paise):
            if bound is None:
                continue
            probes.update({bound - 1, bound, bound + 1})
            highest = max(highest, bound)
    # One probe above every declared bound, so a corpus whose top band is
    # bounded rather than open fails instead of silently stopping there.
    probes.add(highest + 1_000_000)
    return tuple(sorted(p for p in probes if p >= 0))
