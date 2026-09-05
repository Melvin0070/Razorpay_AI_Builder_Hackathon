"""Detectors 1, 2, 5, 6, 7, 8. Lane J · Tier A · issue #13.

Governed by D23, D1, D3, D19 (claimed line), D20 (cycle rules for 5 and 6),
and the class table in contract. Owns this package. Must not read generator/
or labels/. Every detector emits through make_finding(), which raises on an
empty source set, a claimed line outside it, or a class/mechanism pair the
class table forbids.
"""

from __future__ import annotations

from typing import Protocol

from leakproof.contract import (
    ALLOWED_MECHANISMS,
    PRIMARY_MECHANISM,
    Disposition,
    ErrorClass,
    LineKind,
    Mechanism,
    TransactionType,
    UnexplainedBasis,
    apply_bp,
    is_material,
    paise_within,
)
from leakproof.types import (
    DetectorContext,
    Finding,
    FoldedOrder,
    LookupMiss,
    RecomputationRow,
    SlabBasis,
)


class Detector(Protocol):
    def __call__(self, folded: FoldedOrder, ctx: DetectorContext) -> list[Finding]: ...


def make_finding(
    *,
    error_class: ErrorClass,
    order_id: str,
    source_line_ids: tuple[str, ...],
    claimed_line_id: str | None,
    amount_paise: int,
    mechanism: Mechanism,
    basis: str,
    recomputation: tuple[RecomputationRow, ...] = (),
    unexplained_basis: UnexplainedBasis | None = None,
    event_date: object = None,
    category_id: str | None = None,
    sku: str | None = None,
) -> Finding:
    if not source_line_ids:
        raise ValueError("finding needs source_line_ids")
    if claimed_line_id is not None and claimed_line_id not in source_line_ids:
        raise ValueError("claimed line must be cited")
    if mechanism not in ALLOWED_MECHANISMS[error_class]:
        raise ValueError("mechanism is not allowed")
    if amount_paise <= 0:
        raise ValueError("finding amount must be positive")
    return Finding(
        error_class,
        order_id,
        source_line_ids,
        claimed_line_id,
        amount_paise,
        mechanism,
        basis,
        recomputation,
        unexplained_basis,
        event_date,
        category_id,
        sku,
    )  # type: ignore[arg-type]


def _rule(ctx: DetectorContext, kind: LineKind, item: FoldedOrder):
    if item.order is None:
        return None
    basis = ctx.rate_card.band_basis(kind)
    if basis is SlabBasis.UNIT_ITEM_PRICE:
        key = item.order.principal_paise // item.order.quantity
    elif basis is SlabBasis.BUYER_PAID_ITEM_PRICE:
        # Settlement rows carry the buyer-paid shipping / gift-wrap components;
        # a rate card decides whether this basis applies, never a detector literal.
        key = item.order.principal_paise + sum(
            x.amount_paise
            for x in item.lines
            if x.kind in (LineKind.SHIPPING_CHARGE, LineKind.GIFT_WRAP) and x.amount_paise > 0
        )
    else:
        key = None
    result = ctx.rate_card.lookup(kind, item.order.category_id, ctx.as_of, key)
    if isinstance(result, LookupMiss):
        if result.disposition is Disposition.CONFIG_ERROR:
            raise ValueError(result.detail)
        return None
    return result


def _fee(item: FoldedOrder, ctx: DetectorContext, kind: LineKind, cls: ErrorClass) -> list[Finding]:
    rule = _rule(ctx, kind, item)
    if not rule or not item.order:
        return []
    expected = (
        rule.fixed_paise
        if rule.fixed_paise is not None
        else apply_bp(item.order.principal_paise, rule.percent_bp or 0)
    )
    out = []
    for line in item.select(kind=kind):
        delta = -line.amount_paise - expected
        if delta > 0 and is_material(delta) and not paise_within(-line.amount_paise, expected):
            out.append(
                make_finding(
                    error_class=cls,
                    order_id=item.order_id,
                    source_line_ids=(line.line_id,),
                    claimed_line_id=line.line_id,
                    amount_paise=delta,
                    mechanism=PRIMARY_MECHANISM[cls],
                    basis=f"{kind.value} exceeds rate-card rule {rule.rule_id}",
                    recomputation=(
                        RecomputationRow("expected", expected),
                        RecomputationRow("difference", delta),
                    ),
                    category_id=item.order.category_id,
                    sku=item.order.sku,
                )
            )
    return out


def _refund(item: FoldedOrder) -> list[Finding]:
    refunds = item.select(txn_type=TransactionType.REFUND, kind=LineKind.PRINCIPAL)
    reversals = [
        x
        for x in item.lines
        if x.txn_type is TransactionType.REFUND
        and x.kind is LineKind.COMMISSION
        and x.amount_paise > 0
    ]
    original_fees = [
        x
        for x in item.select(kind=LineKind.COMMISSION)
        if x.txn_type is not TransactionType.REFUND and x.amount_paise < 0
    ]
    amount = -sum(x.amount_paise for x in original_fees)
    if not refunds or reversals or not is_material(amount):
        return []
    x = refunds[0]
    return [
        make_finding(
            error_class=ErrorClass.REFUND_NO_FEE_REVERSAL,
            order_id=item.order_id,
            source_line_ids=(x.line_id,),
            claimed_line_id=None,
            amount_paise=amount,
            mechanism=Mechanism.SAFE_T,
            basis="refund has no commission reversal",
            event_date=x.posted_date,
        )
    ]


def _unpaid(item: FoldedOrder, ctx: DetectorContext) -> list[Finding]:
    o = item.order
    if (
        not o
        or not o.delivery_date
        or item.lines
        or (ctx.batch_max_settlement_date - o.delivery_date).days <= 2 * ctx.cycle_days
    ):
        return []
    return [
        make_finding(
            error_class=ErrorClass.UNPAID_PAST_CYCLE,
            order_id=o.order_id,
            source_line_ids=(o.source_line_id,),
            claimed_line_id=None,
            amount_paise=o.principal_paise + o.tax_paise,
            mechanism=Mechanism.SUPPORT_TICKET,
            basis="delivered order unpaid beyond two cycles",
            category_id=o.category_id,
            sku=o.sku,
        )
    ]


def _tax(item: FoldedOrder, ctx: DetectorContext, kind: LineKind) -> list[Finding]:
    rule = _rule(ctx, kind, item)
    if not rule or not item.order:
        return []
    lines = item.select(kind=kind)
    actual = -sum(x.amount_paise for x in lines)
    expected = apply_bp(item.order.principal_paise, rule.percent_bp or 0)
    delta = abs(actual - expected)
    if not lines or not is_material(delta) or paise_within(actual, expected):
        return []
    return [
        make_finding(
            error_class=ErrorClass.TAX_MISMATCH,
            order_id=item.order_id,
            source_line_ids=tuple(x.line_id for x in lines),
            claimed_line_id=lines[0].line_id,
            amount_paise=delta,
            mechanism=Mechanism.CA_REVIEW,
            basis=f"aggregate {kind.value} differs from rate-card",
            recomputation=(
                RecomputationRow("expected", expected),
                RecomputationRow("difference", delta),
            ),
        )
    ]


def _unknown(item: FoldedOrder) -> list[Finding]:
    return [
        make_finding(
            error_class=ErrorClass.UNEXPLAINED_DEDUCTION,
            order_id=item.order_id,
            source_line_ids=(x.line_id,),
            claimed_line_id=x.line_id,
            amount_paise=-x.amount_paise,
            mechanism=Mechanism.NONE,
            basis="unrecognised deduction code",
            unexplained_basis=UnexplainedBasis.CODE_UNSEEN,
        )
        for x in item.lines
        if x.amount_paise < 0 and x.kind is LineKind.UNCLASSIFIED and is_material(-x.amount_paise)
    ]


DETECTORS: tuple[Detector, ...] = ()


def run_detectors(folded: tuple[FoldedOrder, ...], ctx: DetectorContext) -> list[Finding]:
    out = []
    for item in folded:
        if not item.in_coverage:
            continue
        out += (
            _fee(item, ctx, LineKind.COMMISSION, ErrorClass.COMMISSION_OVERCHARGE)
            + _fee(item, ctx, LineKind.FIXED_CLOSING_FEE, ErrorClass.FIXED_FEE_ERROR)
            + _refund(item)
            + _unpaid(item, ctx)
            + _tax(item, ctx, LineKind.TCS)
            + _tax(item, ctx, LineKind.TDS)
            + _unknown(item)
        )
    return out
