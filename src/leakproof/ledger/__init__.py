"""Order-keyed fold, coverage window, tiebreak, exact matcher. Lane H · Tier B · issue #11.

Governed by D20, D7, D10 (match-rate definitions). Owns this package.
"""

from __future__ import annotations

from leakproof.contract import LineKind
from leakproof.types import BatchInputs, FoldedOrder, MatchRates, MatchResult


def fold_batch(inputs: BatchInputs) -> tuple[FoldedOrder, ...]:
    orders = {o.order_id: o for o in inputs.orders.orders}
    headers = {s.header.settlement_id: s.header for s in inputs.settlements if s.header}
    grouped: dict[str, list] = {key: [] for key in orders}
    for parsed in inputs.settlements:
        for line in parsed.lines:
            if line.order_id:
                grouped.setdefault(line.order_id, []).append(line)
    kind_order = {kind: index for index, kind in enumerate(LineKind)}

    def line_key(line: object) -> tuple:
        header = headers.get(line.settlement_id)  # type: ignore[attr-defined]
        cycle = header.start_date if header else line.posted_date  # type: ignore[attr-defined]
        return (line.posted_date, cycle, kind_order[line.kind], line.line_id)  # type: ignore[attr-defined]

    result = []
    for order_id in sorted(grouped):
        lines = tuple(sorted(grouped[order_id], key=line_key))
        settlement_ids = tuple(
            dict.fromkeys(line.settlement_id for line in sorted(lines, key=line_key))
        )
        order = orders.get(order_id)
        in_coverage = (
            order is None
            or order.delivery_date is None
            or inputs.coverage.contains(order.delivery_date)
        )
        result.append(
            FoldedOrder(order_id, order, lines, settlement_ids, in_coverage, inputs.as_of)
        )
    return tuple(result)


def match(
    inputs: BatchInputs, folded: tuple[FoldedOrder, ...], *, class6_flagged: int = 0
) -> MatchResult:
    """Exact order-id join.  Triage calls this again after class 6 detection."""
    exported = {o.order_id for o in inputs.orders.orders}
    with_lines = {item.order_id for item in folded if item.lines}
    matched = tuple(sorted(exported & with_lines))
    unmatched = tuple(sorted(exported - with_lines))
    orphan = tuple(sorted(with_lines - exported))
    quarantined = len(inputs.orders.quarantined) + sum(
        len(s.quarantined) for s in inputs.settlements
    )
    if inputs.bank:
        quarantined += len(inputs.bank.quarantined)
    if inputs.evidence:
        quarantined += len(inputs.evidence.quarantined)
    return MatchResult(
        matched,
        unmatched,
        orphan,
        MatchRates(len(exported), len(matched), class6_flagged, quarantined),
    )
