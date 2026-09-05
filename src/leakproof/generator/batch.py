"""One batch: cycles, orders, seeded scenarios, files and the manifest (D9, D20).

Everything is drawn from one ``random.Random(seed)`` in a fixed order, so the
same spec yields byte-identical files. Money is integer paise throughout and
every percentage goes through ``contract.apply_bp``.

Timeline conventions (all relative to the cycles, never to a clock):

* ``cycle_count`` weekly settlement cycles end on ``last_cycle_end``; each
  cycle's file is ``settlement_<end-date>.txt`` and its bank credit lands
  ``DEPOSIT_LAG_DAYS`` after the cycle end.
* ``as_of`` defaults to the batch's maximum posted-date (D18), which the reserve
  row posted on the last cycle's end date pins to that date.
* the coverage window opens two cycles before the first cycle and closes on
  the last cycle's end: a delivery inside it is one this batch's settlements
  are expected to carry, so absence is evidence (D20); a delivery before it
  takes OUT-OF-WINDOW.
* the seller's ``gst_registered`` capability turns on at the last cycle's
  start whenever ``C1_GST_UNREGISTERED`` is seeded: that order's dates all
  precede the boundary, and the orders that must read as registered
  (``C1_PLAIN``, ``C1_INVOICE_PENDING``) are dated entirely after it, so the
  verdict does not depend on which of the order's dates the capability is
  evaluated on.
* SAFE-T window placement: an "open" window puts the refund inside the last
  two cycles (at most 13 days before ``as_of``); an "expired" one puts it in
  the first cycle, which is 21 days or more before ``as_of`` once there are
  four cycles. The generator does not encode the window length itself; the
  labels and rules lanes read it from the policy sources.
"""

from __future__ import annotations

import random
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Final

from leakproof.contract import (
    DEFAULT_CYCLE_DAYS,
    MATERIALITY_FLOOR_PAISE,
    TOLERANCE_PAISE,
    ErrorClass,
    LineKind,
    Paise,
    RefundInitiator,
    TransactionType,
    apply_bp,
    make_line_id,
)
from leakproof.generator import fees, v2
from leakproof.generator.manifest import write_manifest
from leakproof.generator.money import format_paise
from leakproof.scenarios import SCENARIOS, SEEDED_ERROR_SCENARIOS, Scenario, ScenarioKind
from leakproof.serialize import dumps
from leakproof.types import CapabilityFact, CoverageWindow, Manifest, SeededError, SellerProfile

GENERATOR_NAME: Final[str] = "leakproof-generator/0.1"
DEFAULT_LAST_CYCLE_END: Final[date] = date(2026, 8, 21)
DEFAULT_CYCLE_COUNT: Final[int] = 4
#: Scenario placement needs a first cycle three weeks before the last one.
MIN_CYCLES_WITH_SCENARIOS: Final[int] = 4
DEPOSIT_LAG_DAYS: Final[int] = 2
RESERVE_BP: Final[int] = 500
#: D10: every seeded error is at least twice the materiality floor.
MATERIAL_SEED_FLOOR: Final[Paise] = 2 * MATERIALITY_FLOOR_PAISE

SELLER_ID: Final[str] = "A2LEAKPROOFIN1"
SELLER_NAME: Final[str] = "Leakproof Demo Traders"
GST_CAPABILITY: Final[str] = "gst_registered"
SAFE_T_CAPABILITY: Final[str] = "safe_t_enrolled"
INVOICE_REQUIREMENT: Final[str] = "gst_tax_invoice"

ORDER_PREFIXES: Final[tuple[int, ...]] = (171, 403, 404, 405, 406, 407, 408)
SKU_WORDS: Final[dict[str, tuple[str, str, ...]]] = {
    "electronics-accessories": ("ELEC", "CBL", "HDP", "CHG", "SPK", "EAR", "MSE", "KBD", "PWB"),
    "home-kitchen": ("KTCH", "PAN", "KNF", "JAR", "POT", "PLT", "BWL", "KTL", "CUP"),
    "apparel": ("APRL", "SHT", "FRM", "CAS", "LIN", "DNM", "OXF", "CHK", "PLD"),
    "books": ("BOOK", "NVL", "TXT", "REF"),
    "beauty": ("BEAU", "SRM", "LTN", "MSK"),
    "toys": ("TOYS", "BLK", "PZL", "CAR"),
    "grocery": ("GROC", "OIL", "TEA", "NUT"),
}
#: Pre-tax unit prices in rupees, spanning both sides of every referral tier.
PRICE_POINTS: Final[dict[str, tuple[int, ...]]] = {
    "electronics-accessories": (
        *(199, 249, 299, 349, 399, 449, 499, 599, 699, 799, 899, 999),
        *(1199, 1299, 1499, 1799, 1999, 2499, 2999, 3499, 3999, 4999),
    ),
    "home-kitchen": (
        *(249, 299, 349, 449, 499, 599, 699, 799, 899, 999),
        *(1099, 1249, 1499, 1799, 1999, 2499, 2999, 3499, 4499, 5999, 6999),
    ),
    "apparel": (
        *(299, 349, 399, 449, 499, 549, 599, 699, 799, 899, 999),
        *(1099, 1199, 1299, 1499, 1699, 1999, 2299, 2499, 2999, 3499),
    ),
    "books": (199, 299, 399, 499, 699, 899, 1299),
    "beauty": (249, 349, 499, 699, 999, 1499),
    "toys": (299, 499, 799, 1299, 1999, 2999),
    "grocery": (199, 299, 449, 599, 899, 1199),
}
#: GST on the item itself. No detector audits it; it only makes the tax column real.
ITEM_GST_BP: Final[dict[str, int]] = {
    "electronics-accessories": 1_800,
    "home-kitchen": 1_200,
    "apparel": 500,
    "books": 0,
    "beauty": 1_800,
    "toys": 1_200,
    "grocery": 500,
}
#: Easy Ship weight-handling fee, an acknowledged deduction (not audited).
SHIPPING_FEES: Final[tuple[Paise, ...]] = (4_500, 5_500, 6_500, 8_000, 11_200)
PROMOTION_BPS: Final[tuple[int, ...]] = (300, 500, 1_000)
UNSEEN_CODES: Final[tuple[str, ...]] = (
    "MISC-ADJ-7",
    "PolicyViolationFee",
    "NonCompliantPackagingFee",
    "ShippingHBAdjustment",
)
WRONG_RATE_EXTRA_BPS: Final[tuple[int, ...]] = (300, 500, 800)

_ORDER = v2.raw_transaction(TransactionType.ORDER)
_REFUND = v2.raw_transaction(TransactionType.REFUND)
_ATOZ = v2.raw_transaction(TransactionType.ATOZ_REFUND)
_ADJUSTMENT = v2.raw_transaction(TransactionType.ADJUSTMENT)
_PRINCIPAL = v2.raw_pair(LineKind.PRINCIPAL)
_ITEM_TAX = v2.raw_pair(LineKind.ITEM_TAX)
_COMMISSION = v2.raw_pair(LineKind.COMMISSION)
_CLOSING = v2.raw_pair(LineKind.FIXED_CLOSING_FEE)
_SHIPPING = v2.raw_pair(LineKind.SHIPPING_FEE)
_FEE_TAX = v2.raw_pair(LineKind.FEE_TAX)
_REFUND_FEE = v2.raw_pair(LineKind.REFUND_ADMIN_FEE)
_TECH_FEE = v2.raw_pair(LineKind.TECHNOLOGY_FEE)
_TDS = v2.raw_pair(LineKind.TDS)
_TCS_TYPE = v2.raw_pair(LineKind.TCS, description=fees.TCS_CGST_DESCRIPTION)[0]
_RESERVE_CURRENT = v2.raw_pair(LineKind.RESERVE, description="Current Reserve Amount")
_RESERVE_PREVIOUS = v2.raw_pair(LineKind.RESERVE, description="Previous Reserve Amount Balance")
_PROMOTION = v2.raw_pair(LineKind.PROMOTION, description="Principal")

_TRUE_NEGATIVES_AND_DISPOSITIONS: Final[tuple[Scenario, ...]] = (
    Scenario.C5_REVERSED_LATER_CYCLE,
    Scenario.C6_PAID_LATER_CYCLE,
    Scenario.C6_OUT_OF_WINDOW,
    Scenario.BELOW_MATERIALITY,
    Scenario.UNCOVERED_CATEGORY,
)


@dataclass(frozen=True, slots=True)
class BatchSpec:
    """What ``generate`` builds. ``scenario_counts`` is exact: that many orders
    carry each scenario; the rest of ``order_count`` is ordinary traffic."""

    batch_id: str
    seed: int
    order_count: int
    scenario_counts: Mapping[Scenario, int]
    cycle_count: int = DEFAULT_CYCLE_COUNT
    cycle_days: int = DEFAULT_CYCLE_DAYS
    last_cycle_end: date = DEFAULT_LAST_CYCLE_END
    as_of: date | None = None
    categories: tuple[str, ...] = fees.COVERED_CATEGORIES
    malformed_last_settlement: bool = False

    def count(self, scenario: Scenario) -> int:
        return self.scenario_counts.get(scenario, 0)

    @property
    def scenario_orders(self) -> int:
        return sum(
            n
            for s, n in self.scenario_counts.items()
            if s not in (Scenario.DUPLICATE_UTR, Scenario.QUARANTINE_MALFORMED)
        )


def default_scenario_counts(errors_per_class: int) -> dict[Scenario, int]:
    """``errors_per_class`` per class, dealt round-robin over the class's
    scenarios in ``scenarios.py`` order, plus the true negatives, dispositions
    and the duplicate credit so a batch always exercises them."""
    counts: dict[Scenario, int] = {}
    if errors_per_class <= 0:
        return counts
    for cls in ErrorClass:
        members = [s for s in SEEDED_ERROR_SCENARIOS if SCENARIOS[s].expected_class is cls]
        for i in range(errors_per_class):
            scenario = members[i % len(members)]
            counts[scenario] = counts.get(scenario, 0) + 1
    extra = max(1, errors_per_class // 2)
    for scenario in _TRUE_NEGATIVES_AND_DISPOSITIONS:
        counts[scenario] = extra
    counts[Scenario.DUPLICATE_UTR] = 1
    return counts


def validate_spec(spec: BatchSpec) -> None:
    problems: list[str] = []
    if spec.order_count < 1:
        problems.append("order_count must be positive")
    if spec.cycle_count < 1:
        problems.append("cycle_count must be positive")
    if spec.cycle_days < 1:
        problems.append("cycle_days must be positive")
    for scenario, n in spec.scenario_counts.items():
        if n < 0:
            problems.append(f"negative count for {scenario}")
        if scenario is Scenario.CONFIG_ERROR and n:
            problems.append("CONFIG_ERROR is a test fixture, not a seedable scenario")
        if scenario is Scenario.QUARANTINE_MALFORMED and n:
            problems.append("QUARANTINE_MALFORMED is seeded by malformed_last_settlement")
        if scenario is Scenario.DUPLICATE_UTR and n > 1:
            problems.append("at most one DUPLICATE_UTR per batch")
    if spec.scenario_orders > spec.order_count:
        problems.append(f"{spec.scenario_orders} scenario orders exceed order_count")
    if spec.scenario_orders and (
        spec.cycle_count < MIN_CYCLES_WITH_SCENARIOS or spec.cycle_days < DEFAULT_CYCLE_DAYS
    ):
        problems.append(
            f"seeding needs at least {MIN_CYCLES_WITH_SCENARIOS} cycles of "
            f"{DEFAULT_CYCLE_DAYS}+ days"
        )
    if not spec.categories:
        problems.append("categories must not be empty")
    for category in spec.categories:
        if category not in PRICE_POINTS:
            problems.append(f"unknown category {category!r}")
    if problems:
        raise ValueError("; ".join(problems))


@dataclass(frozen=True, slots=True)
class Cycle:
    index: int
    settlement_id: str
    start: date
    end: date
    deposit: date
    file_name: str


@dataclass(slots=True)
class OrderPlan:
    order_id: str
    sku: str
    category_id: str
    principal: Paise
    tax: Paise
    order_date: date
    delivery_date: date | None
    refund_initiated_by: RefundInitiator
    intra_state: bool
    shipment_id: str
    order_item_code: str
    commission_charged: Paise = 0
    blocks: list[v2.Block] = field(default_factory=list)
    scenario: Scenario | None = None
    expected_amount: Paise | None = None
    cites: tuple[tuple[str, str], ...] = ()  # (block tag, line tag)
    cite_order_row: bool = False
    note: str = ""
    evidence: tuple[tuple[str, str, date | None], ...] = ()


def _pct(bp: int) -> str:
    return f"{bp / 100:.2f}%"


class _Builder:
    def __init__(self, spec: BatchSpec) -> None:
        validate_spec(spec)
        self.spec = spec
        self.rng = random.Random(spec.seed)
        self.cycles = self._build_cycles()
        self.first = self.cycles[0]
        self.last = self.cycles[-1]
        self.coverage = CoverageWindow(
            self.first.start - timedelta(days=2 * spec.cycle_days), self.last.end
        )
        self.as_of = spec.as_of if spec.as_of is not None else self.last.end
        self.gst_boundary = self.last.start
        self.orders: list[OrderPlan] = []
        self.used_ids: set[str] = set()

    # ------------------------------------------------------------------ world

    def _build_cycles(self) -> tuple[Cycle, ...]:
        spec = self.spec
        base = 20_850_000_000 + (spec.seed % 10_000) * 100
        cycles = []
        for k in range(spec.cycle_count):
            end = spec.last_cycle_end - timedelta(days=(spec.cycle_count - 1 - k) * spec.cycle_days)
            start = end - timedelta(days=spec.cycle_days - 1)
            cycles.append(
                Cycle(
                    k,
                    str(base + k),
                    start,
                    end,
                    end + timedelta(days=DEPOSIT_LAG_DAYS),
                    v2.settlement_file_name(end),
                )
            )
        return tuple(cycles)

    def _cycle_for(self, on: date) -> Cycle:
        for cycle in self.cycles:
            if cycle.start <= on <= cycle.end:
                return cycle
        raise AssertionError(f"{on} is outside every cycle")

    def _order_id(self) -> str:
        while True:
            oid = (
                f"{self.rng.choice(ORDER_PREFIXES)}-{self.rng.randrange(10**7):07d}"
                f"-{self.rng.randrange(10**7):07d}"
            )
            if oid not in self.used_ids:
                self.used_ids.add(oid)
                return oid

    def _sku(self, category: str) -> str:
        prefix, *words = SKU_WORDS[category]
        return f"{prefix}-{self.rng.choice(words)}-{self.rng.randrange(1, 60):02d}"

    def _alnum(self, n: int) -> str:
        return "".join(self.rng.choice("ABCDEFGHJKLMNPQRSTUVWXYZ0123456789") for _ in range(n))

    def _posted_time(self) -> str:
        return (
            f"{self.rng.randrange(6, 22):02d}:{self.rng.randrange(60):02d}:"
            f"{self.rng.randrange(60):02d}"
        )

    def _pick_price(
        self,
        category: str,
        *,
        minimum: Paise = 0,
        maximum: Paise | None = None,
        min_commission: Paise = 0,
    ) -> Paise:
        on = self.last.end
        candidates = [
            p * 100
            for p in PRICE_POINTS[category]
            if p * 100 >= minimum
            and (maximum is None or p * 100 <= maximum)
            and fees.commission_paise(category, p * 100, on) >= min_commission
        ]
        if not candidates:
            raise ValueError(f"no price point for {category} within the constraints")
        return self.rng.choice(candidates)

    def _category_for(self, predicate) -> str:  # noqa: ANN001 - internal callable
        options = [c for c in fees.COVERED_CATEGORIES if predicate(c)]
        return self.rng.choice(options)

    def _item_tax(self, category: str, principal: Paise) -> Paise:
        return apply_bp(principal, ITEM_GST_BP[category])

    def _new_plan(
        self,
        category: str,
        principal: Paise,
        order_date: date,
        delivery: date | None,
        *,
        refund_by: RefundInitiator = RefundInitiator.NONE,
        scenario: Scenario | None = None,
    ) -> OrderPlan:
        plan = OrderPlan(
            order_id=self._order_id(),
            sku=self._sku(category),
            category_id=category,
            principal=principal,
            tax=self._item_tax(category, principal),
            order_date=order_date,
            delivery_date=delivery,
            refund_initiated_by=refund_by,
            intra_state=self.rng.random() < 0.6,
            shipment_id=self._alnum(9),
            order_item_code=f"{self.rng.randrange(10**14):014d}",
            scenario=scenario,
        )
        self.orders.append(plan)
        return plan

    def _sale_dates(
        self, cycle: Cycle, *, posted_min: date | None = None, posted_max: date | None = None
    ) -> tuple[date, date, date]:
        lo = max(cycle.start, posted_min) if posted_min else cycle.start
        hi = min(cycle.end, posted_max) if posted_max else cycle.end
        if hi < lo:
            raise AssertionError(f"empty posted-date range in cycle {cycle.index}")
        posted = lo + timedelta(days=self.rng.randint(0, (hi - lo).days))
        delivery = posted - timedelta(days=self.rng.randint(1, 3))
        order_date = delivery - timedelta(days=self.rng.randint(2, 5))
        return order_date, delivery, posted

    def _date_in(self, lo: date, hi: date) -> date:
        if hi < lo:
            raise AssertionError(f"empty date range {lo}..{hi}")
        return lo + timedelta(days=self.rng.randint(0, (hi - lo).days))

    # ----------------------------------------------------------------- blocks

    def _sale_block(
        self,
        plan: OrderPlan,
        posted: date,
        *,
        commission: Paise | None = None,
        closing: Paise | None = None,
        tcs: tuple[tuple[str, Paise], ...] | None = None,
        tds: Paise | None = None,
        promotion: Paise = 0,
        extra: tuple[v2.Line, ...] = (),
    ) -> v2.Block:
        """The Order transaction. Every ``None`` override means "the correct
        amount"; a value means "what Amazon actually posted"."""
        cycle = self._cycle_for(posted)
        p = plan.principal
        charged_commission = (
            fees.commission_paise(plan.category_id, p, posted) if commission is None else commission
        )
        charged_closing = fees.closing_fee_paise(p, posted) if closing is None else closing
        shipping = self.rng.choice(SHIPPING_FEES)
        fee_tax = fees.fee_gst_paise(charged_commission + charged_closing + shipping)
        tcs_legs = fees.tcs_legs(p, intra_state=plan.intra_state, on=posted) if tcs is None else tcs
        tds_amount = fees.tds_paise(p, posted) if tds is None else tds
        plan.commission_charged = charged_commission
        lines = [
            v2.Line(*_PRINCIPAL, p, "principal"),
            v2.Line(*_ITEM_TAX, plan.tax, "tax"),
            v2.Line(*_COMMISSION, -charged_commission, "commission"),
            v2.Line(*_CLOSING, -charged_closing, "closing"),
            v2.Line(*_SHIPPING, -shipping, "shipping"),
        ]
        if promotion:
            promo_id = f"SELLER-COUPON-{self.rng.randrange(10**6):06d}"
            lines.append(v2.Line(*_PROMOTION, -promotion, "promotion", promo_id))
        lines.append(v2.Line(*_FEE_TAX, -fee_tax, "fee_tax"))
        for description, amount in tcs_legs:
            lines.append(v2.Line(_TCS_TYPE, description, -amount, f"tcs:{description}"))
        lines.append(v2.Line(*_TDS, -tds_amount, "tds"))
        lines.extend(extra)
        block = v2.Block(
            _ORDER,
            plan.order_id,
            plan.sku,
            1,
            posted,
            self._posted_time(),
            cycle.index,
            "sale",
            tuple(lines),
            shipment_id=plan.shipment_id,
            order_item_code=plan.order_item_code,
        )
        plan.blocks.append(block)
        return block

    def _refund_block(
        self, plan: OrderPlan, posted: date, *, txn_type: str = _REFUND, reverse: bool = True
    ) -> v2.Block:
        """The refund event. ``reverse=False`` omits the commission reversal
        and its GST: the class-5 shape."""
        cycle = self._cycle_for(posted)
        charged = plan.commission_charged
        refund_fee = fees.refund_commission_paise(charged)
        lines = [
            v2.Line(*_PRINCIPAL, -plan.principal, "principal"),
            v2.Line(*_ITEM_TAX, -plan.tax, "tax"),
        ]
        fee_tax = -fees.fee_gst_paise(refund_fee)
        if reverse:
            lines.append(v2.Line(*_COMMISSION, charged, "commission"))
            fee_tax += fees.fee_gst_paise(charged)
        if refund_fee:
            lines.append(v2.Line(*_REFUND_FEE, -refund_fee, "refund_commission"))
        if fee_tax:
            lines.append(v2.Line(*_FEE_TAX, fee_tax, "fee_tax"))
        block = v2.Block(
            txn_type,
            plan.order_id,
            plan.sku,
            1,
            posted,
            self._posted_time(),
            cycle.index,
            "refund",
            tuple(lines),
            shipment_id=plan.shipment_id,
            order_item_code=plan.order_item_code,
        )
        plan.blocks.append(block)
        return block

    def _reversal_block(self, plan: OrderPlan, posted: date) -> v2.Block:
        """A commission reversal posted on its own in a later cycle."""
        cycle = self._cycle_for(posted)
        charged = plan.commission_charged
        block = v2.Block(
            _REFUND,
            plan.order_id,
            plan.sku,
            1,
            posted,
            self._posted_time(),
            cycle.index,
            "reversal",
            (
                v2.Line(*_COMMISSION, charged, "commission"),
                v2.Line(*_FEE_TAX, fees.fee_gst_paise(charged), "fee_tax"),
            ),
            shipment_id=plan.shipment_id,
            order_item_code=plan.order_item_code,
        )
        plan.blocks.append(block)
        return block

    def _adjustment_block(self, plan: OrderPlan, posted: date, line: v2.Line) -> v2.Block:
        cycle = self._cycle_for(posted)
        block = v2.Block(
            _ADJUSTMENT,
            plan.order_id,
            plan.sku,
            1,
            posted,
            self._posted_time(),
            cycle.index,
            "adjustment",
            (line,),
            shipment_id=plan.shipment_id,
            order_item_code=plan.order_item_code,
            adjustment_id=f"ADJ{self._alnum(10)}",
        )
        plan.blocks.append(block)
        return block

    def _refund_after(self, plan: OrderPlan, sale_posted: date, lo: date, hi: date) -> date:
        """A refund date in ``[lo, hi]`` strictly after the sale posted."""
        return self._date_in(max(lo, sale_posted + timedelta(days=1)), hi)

    # ------------------------------------------------------------- ordinary

    def _background_order(self, category: str | None = None) -> OrderPlan:
        if category is None:
            weights = [4 if c == "electronics-accessories" else 3 for c in self.spec.categories]
            category = self.rng.choices(self.spec.categories, weights=weights)[0]
        principal = self._pick_price(category)
        cycle = self.rng.choice(self.cycles)
        order_date, delivery, posted = self._sale_dates(cycle)
        plan = self._new_plan(category, principal, order_date, delivery)
        promotion = 0
        if self.rng.random() < 0.15:
            promotion = apply_bp(principal, self.rng.choice(PROMOTION_BPS))
        self._sale_block(plan, posted, promotion=promotion)
        if posted < self.last.end and self.rng.random() < 0.08:
            seller_issued = self.rng.random() < 0.3
            plan.refund_initiated_by = (
                RefundInitiator.SELLER if seller_issued else RefundInitiator.AMAZON
            )
            self._refund_block(plan, self._refund_after(plan, posted, posted, self.last.end))
        if category not in fees.COVERED_CATEGORIES:
            plan.scenario = Scenario.UNCOVERED_CATEGORY
            plan.cites = (("sale", "principal"),)
            plan.cite_order_row = True
            plan.note = f"category {category!r} is outside the declared coverage"
        return plan

    # --------------------------------------------------------------- class 1

    def _overcharge(self, plan: OrderPlan, on: date) -> tuple[Paise, str]:
        """A commission above the schedule by at least twice the floor, either
        the pre-March-2026 tier (a stale rate) or a few hundred bp too many."""
        p = plan.principal
        correct_bp = fees.referral_bp(plan.category_id, p, on)
        correct = apply_bp(p, correct_bp)
        candidates: list[tuple[int, str]] = []
        legacy_bp = fees.legacy_referral_bp(plan.category_id, p)
        if legacy_bp > correct_bp:
            candidates.append((legacy_bp, "the pre-2026-03-16 tier"))
        candidates.extend((correct_bp + extra, "an inflated rate") for extra in WRONG_RATE_EXTRA_BPS)
        viable = [
            (bp, why) for bp, why in candidates if apply_bp(p, bp) - correct >= MATERIAL_SEED_FLOOR
        ]
        bp, why = self.rng.choice(viable)
        charged = apply_bp(p, bp)
        node = fees.SOURCE_NODES[plan.category_id]
        note = (
            f"commission {_pct(bp)} charged ({why}) vs {_pct(correct_bp)} for {node!r} "
            f"on principal {format_paise(p)}; overcharge excludes the GST that follows it"
        )
        return charged, note

    def _seed_c1(self, scenario: Scenario) -> None:
        category = self._category_for(lambda c: True)
        principal = self._pick_price(category, minimum=60_000)
        refund_by = RefundInitiator.AMAZON
        refund_txn = _REFUND
        if scenario is Scenario.C1_SELLER_REFUND_EXCLUDED:
            refund_by = RefundInitiator.SELLER
        if scenario is Scenario.C1_ATOZ_EXCLUDED:
            refund_txn = _ATOZ
        if scenario is Scenario.C1_WINDOW_DATE_MISSING:
            refund_by = RefundInitiator.NONE

        if scenario in (Scenario.C1_PLAIN, Scenario.C1_INVOICE_PENDING):
            # Every date on or after the GST boundary (the last cycle's start).
            order_date = self.gst_boundary + timedelta(days=self.rng.randint(0, 1))
            delivery = order_date + timedelta(days=2)
            posted = delivery + timedelta(days=1)
            refund = min(posted + timedelta(days=self.rng.randint(1, 2)), self.last.end)
        elif scenario is Scenario.C1_GST_UNREGISTERED:
            cycle = self.cycles[-2]
            order_date, delivery, posted = self._sale_dates(
                cycle, posted_max=cycle.end - timedelta(days=2)
            )
            refund = self._refund_after(self, posted, cycle.start, cycle.end)
        elif scenario is Scenario.C1_WINDOW_EXPIRED:
            cycle = self.first
            order_date, delivery, posted = self._sale_dates(
                cycle, posted_max=cycle.end - timedelta(days=1)
            )
            refund = self._refund_after(self, posted, cycle.start, cycle.end)
        else:
            cycle = self.rng.choice(self.cycles[1:-1])
            order_date, delivery, posted = self._sale_dates(
                cycle, posted_max=cycle.end - timedelta(days=1)
            )
            refund = self._refund_after(self, posted, posted, self.last.end)

        plan = self._new_plan(
            category, principal, order_date, delivery, refund_by=refund_by, scenario=scenario
        )
        charged, note = self._overcharge(plan, posted)
        correct = fees.commission_paise(category, principal, posted)
        self._sale_block(plan, posted, commission=charged)
        plan.expected_amount = charged - correct
        plan.cites = (("sale", "commission"), ("sale", "principal"))
        if scenario is Scenario.C1_WINDOW_DATE_MISSING:
            plan.note = f"{note}; no refund or return event on any line, so no window start date"
            plan.evidence = ((INVOICE_REQUIREMENT, "supplied", posted),)
            return
        self._refund_block(plan, refund, txn_type=refund_txn, reverse=True)
        plan.cites += (("refund", "principal"),)
        days = (self.as_of - refund).days
        detail = {
            Scenario.C1_PLAIN: "GST tax invoice supplied (evidence.csv)",
            Scenario.C1_INVOICE_PENDING: "GST tax invoice requested, not yet supplied (evidence.csv)",
            Scenario.C1_GST_UNREGISTERED: (
                f"every date precedes the seller's GST registration on {self.gst_boundary}"
            ),
            Scenario.C1_WINDOW_EXPIRED: "refund in the first cycle, so the window has expired",
            Scenario.C1_ATOZ_EXCLUDED: "the refund is an A-to-z Guarantee refund",
            Scenario.C1_SELLER_REFUND_EXCLUDED: "the refund was issued by the seller",
        }[scenario]
        plan.note = f"{note}; refund posted {refund} ({days} days before as_of); {detail}"
        if scenario is Scenario.C1_INVOICE_PENDING:
            plan.evidence = ((INVOICE_REQUIREMENT, "pending", None),)
        elif scenario is not Scenario.C1_GST_UNREGISTERED:
            plan.evidence = ((INVOICE_REQUIREMENT, "supplied", min(refund, self.as_of)),)

    # --------------------------------------------------------------- class 2

    def _seed_c2(self, scenario: Scenario) -> None:
        category = self._category_for(lambda c: True)
        cycle = self.rng.choice(self.cycles)
        order_date, delivery, posted = self._sale_dates(cycle)
        bands = fees.closing_schedule(posted).bands
        if scenario is Scenario.C2_SLAB_BOUNDARY:
            principal = self.rng.choice([upper for upper, _ in bands if upper is not None])
        else:
            principal = self._pick_price(category, maximum=bands[-2][0] or 0)
        correct = fees.closing_fee_paise(principal, posted)
        higher = [fee for _, fee in bands if fee - correct >= MATERIAL_SEED_FLOOR]
        charged = higher[0] if scenario is Scenario.C2_SLAB_BOUNDARY else self.rng.choice(higher)
        plan = self._new_plan(category, principal, order_date, delivery, scenario=scenario)
        self._sale_block(plan, posted, closing=charged)
        plan.expected_amount = charged - correct
        plan.cites = (("sale", "closing"), ("sale", "principal"))
        edge = " (principal exactly at the band's inclusive upper bound)" if (
            scenario is Scenario.C2_SLAB_BOUNDARY
        ) else ""
        plan.note = (
            f"closing fee {format_paise(charged)} charged vs {format_paise(correct)} for the "
            f"Easy Ship band holding principal {format_paise(principal)}{edge}"
        )

    # --------------------------------------------------------------- class 5

    def _seed_c5(self, scenario: Scenario) -> None:
        category = self._category_for(lambda c: True)
        principal = self._pick_price(category, min_commission=MATERIAL_SEED_FLOOR)
        refund_by = RefundInitiator.AMAZON
        refund_txn = _REFUND
        if scenario is Scenario.C5_SELLER_ISSUED:
            refund_by = RefundInitiator.SELLER
        if scenario is Scenario.C5_ATOZ:
            refund_txn = _ATOZ
        penultimate = self.cycles[-2]
        if scenario is Scenario.C5_AWAITING_CYCLE:
            sale_cycle = self.rng.choice(self.cycles)
            order_date, delivery, posted = self._sale_dates(
                sale_cycle, posted_max=self.last.end - timedelta(days=1)
            )
            refund = self._refund_after(self, posted, self.last.start, self.last.end)
        elif scenario is Scenario.C5_PLAIN:
            sale_cycle = self.rng.choice(self.cycles[:-1])
            order_date, delivery, posted = self._sale_dates(
                sale_cycle, posted_max=penultimate.end - timedelta(days=1)
            )
            refund = self._refund_after(self, posted, penultimate.start, penultimate.end)
        else:
            sale_cycle = self.rng.choice(self.cycles[:-1])
            order_date, delivery, posted = self._sale_dates(
                sale_cycle, posted_max=penultimate.end - timedelta(days=1)
            )
            refund = self._refund_after(self, posted, posted, penultimate.end)
        plan = self._new_plan(
            category, principal, order_date, delivery, refund_by=refund_by, scenario=scenario
        )
        self._sale_block(plan, posted)
        self._refund_block(plan, refund, txn_type=refund_txn, reverse=False)
        days = (self.as_of - refund).days
        commission = plan.commission_charged
        plan.cites = (("refund", "principal"), ("sale", "commission"))
        if scenario is Scenario.C5_REVERSED_LATER_CYCLE:
            reversal_cycle = self.rng.choice(self.cycles[self._cycle_for(refund).index + 1 :])
            reversal = self._date_in(reversal_cycle.start, reversal_cycle.end)
            self._reversal_block(plan, reversal)
            plan.cites += (("reversal", "commission"),)
            plan.note = (
                f"refund posted {refund}; commission {format_paise(commission)} reversed on "
                f"{reversal} in a later cycle inside the batch; nothing should fire"
            )
            return
        plan.expected_amount = commission
        detail = {
            Scenario.C5_PLAIN: "no reversal in any later cycle",
            Scenario.C5_AWAITING_CYCLE: "less than one full cycle before the max settlement date",
            Scenario.C5_SELLER_ISSUED: "refund issued by the seller; no reversal since",
            Scenario.C5_ATOZ: "A-to-z Guarantee refund; no reversal since",
        }[scenario]
        plan.note = (
            f"refund posted {refund} ({days} days before as_of); commission "
            f"{format_paise(commission)} charged on the sale never reversed; {detail}; "
            f"amount excludes the GST reversal that follows it"
        )

    # --------------------------------------------------------------- class 6

    def _seed_c6(self, scenario: Scenario) -> None:
        category = self._category_for(lambda c: True)
        principal = self._pick_price(category)
        cd = self.spec.cycle_days
        if scenario is Scenario.C6_OUT_OF_WINDOW:
            delivery = self._date_in(
                self.coverage.start - timedelta(days=21), self.coverage.start - timedelta(days=1)
            )
        elif scenario is Scenario.C6_PAID_LATER_CYCLE:
            delivery = self._date_in(
                self.coverage.start, self.coverage.start + timedelta(days=cd - 1)
            )
        else:
            delivery = self._date_in(self.coverage.start, self.as_of - timedelta(days=2 * cd + 2))
        order_date = delivery - timedelta(days=self.rng.randint(2, 5))
        plan = self._new_plan(category, principal, order_date, delivery, scenario=scenario)
        plan.cite_order_row = True
        if scenario is Scenario.C6_PAID_LATER_CYCLE:
            cycle = self.rng.choice(self.cycles[1:])
            posted = self._date_in(cycle.start, cycle.end)
            self._sale_block(plan, posted)
            plan.cites = (("sale", "principal"),)
            plan.note = (
                f"delivered {delivery}, paid on {posted} in cycle {cycle.index + 1} of the "
                f"batch ({(posted - delivery).days} days later); nothing should fire"
            )
        elif scenario is Scenario.C6_OUT_OF_WINDOW:
            plan.note = (
                f"delivered {delivery}, before the coverage window opens on "
                f"{self.coverage.start}; absent from every file; OUT-OF-WINDOW, not class 6"
            )
        else:
            plan.expected_amount = principal + plan.tax
            plan.note = (
                f"delivered {delivery} ({(self.as_of - delivery).days} days before as_of, more "
                f"than two {cd}-day cycles) and absent from every settlement; amount is the "
                f"order's principal plus tax (ADR-0005 bound)"
            )

    # --------------------------------------------------------------- class 7

    def _seed_c7(self, scenario: Scenario) -> None:
        if scenario is Scenario.C7_TCS_MISMATCH:
            minimum = 400_000
        else:
            minimum = 250_000
        category = self._category_for(lambda c: max(PRICE_POINTS[c]) * 100 >= minimum)
        principal = self._pick_price(category, minimum=minimum)
        cycle = self.rng.choice(self.cycles)
        order_date, delivery, posted = self._sale_dates(cycle)
        plan = self._new_plan(category, principal, order_date, delivery, scenario=scenario)
        if scenario is Scenario.C7_TCS_MISMATCH:
            wrong = fees.legacy_tcs_legs(principal, intra_state=plan.intra_state)
            correct = fees.tcs_legs(principal, intra_state=plan.intra_state, on=posted)
            self._sale_block(plan, posted, tcs=wrong)
            withheld = sum(v for _, v in wrong)
            expected_total = sum(v for _, v in correct)
            plan.expected_amount = withheld - expected_total
            plan.cites = tuple(("sale", f"tcs:{d}") for d, _ in wrong) + (("sale", "principal"),)
            plan.note = (
                f"TCS withheld {format_paise(withheld)} at the pre-2024-07-10 rate vs "
                f"{format_paise(expected_total)} at 0.5% of principal {format_paise(principal)}"
            )
        else:
            wrong = fees.legacy_tds_paise(principal)
            correct_tds = fees.tds_paise(principal, posted)
            self._sale_block(plan, posted, tds=wrong)
            plan.expected_amount = wrong - correct_tds
            plan.cites = (("sale", "tds"), ("sale", "principal"))
            plan.note = (
                f"TDS withheld {format_paise(wrong)} at the pre-2024-10-01 rate vs "
                f"{format_paise(correct_tds)} at 0.1% of principal {format_paise(principal)}"
            )

    # --------------------------------------------------------------- class 8

    def _seed_c8(self, scenario: Scenario) -> None:
        category = self._category_for(lambda c: True)
        principal = self._pick_price(category)
        cycle = self.rng.choice(self.cycles)
        order_date, delivery, posted = self._sale_dates(cycle)
        plan = self._new_plan(category, principal, order_date, delivery, scenario=scenario)
        if scenario is Scenario.C8_CODE_UNSEEN:
            amount = self.rng.randrange(3_500, 45_000, 50)
            code = self.rng.choice(UNSEEN_CODES)
            self._sale_block(plan, posted)
            adjusted = self._date_in(posted, cycle.end)
            self._adjustment_block(
                plan, adjusted, v2.Line(v2.OTHER_TRANSACTION, code, -amount, "unseen")
            )
            plan.cites = (("adjustment", "unseen"),)
            plan.note = (
                f"deduction {format_paise(amount)} under amount-description {code!r}, "
                f"which is not in the vocabulary"
            )
        else:
            amount = self.rng.randrange(3_000, 30_000, 50)
            self._sale_block(
                plan, posted, extra=(v2.Line(*_TECH_FEE, -amount, "technology_fee"),)
            )
            plan.cites = (("sale", "technology_fee"),)
            plan.note = (
                f"deduction {format_paise(amount)} under {_TECH_FEE[1]!r}, a known code the "
                f"rate card neither audits nor acknowledges"
            )
        plan.expected_amount = amount

    # ------------------------------------------------------- outside classes

    def _seed_below_materiality(self) -> None:
        category = self._category_for(lambda c: True)
        principal = self._pick_price(category)
        cycle = self.rng.choice(self.cycles)
        order_date, delivery, posted = self._sale_dates(cycle)
        plan = self._new_plan(
            category, principal, order_date, delivery, scenario=Scenario.BELOW_MATERIALITY
        )
        correct = fees.commission_paise(category, principal, posted)
        delta = self.rng.randint(2 * TOLERANCE_PAISE, MATERIALITY_FLOOR_PAISE - TOLERANCE_PAISE)
        self._sale_block(plan, posted, commission=correct + delta)
        plan.expected_amount = delta
        plan.cites = (("sale", "commission"), ("sale", "principal"))
        plan.note = (
            f"commission over the schedule by {format_paise(delta)}: above the ₹1 tolerance, "
            f"below the ₹10 floor; aggregated, never queued"
        )

    def _seed_scenarios(self) -> None:
        for scenario in Scenario:
            for _ in range(self.spec.count(scenario)):
                self._seed_one(scenario)

    def _seed_one(self, scenario: Scenario) -> None:
        cls = SCENARIOS[scenario].expected_class
        if scenario.name.startswith("C1_"):
            self._seed_c1(scenario)
        elif scenario.name.startswith("C2_"):
            self._seed_c2(scenario)
        elif scenario.name.startswith("C5_"):
            self._seed_c5(scenario)
        elif scenario.name.startswith("C6_"):
            self._seed_c6(scenario)
        elif scenario.name.startswith("C7_"):
            self._seed_c7(scenario)
        elif scenario.name.startswith("C8_"):
            self._seed_c8(scenario)
        elif scenario is Scenario.BELOW_MATERIALITY:
            self._seed_below_materiality()
        elif scenario is Scenario.UNCOVERED_CATEGORY:
            self._background_order(self.rng.choice(fees.UNCOVERED_CATEGORIES))
        elif scenario is Scenario.DUPLICATE_UTR:
            return  # applied when the bank file is written
        else:
            raise ValueError(f"{scenario} cannot be seeded by the generator")
        if cls is not None and (self.orders[-1].expected_amount or 0) < MATERIAL_SEED_FLOOR:
            raise AssertionError(f"{scenario}: seeded amount below twice the floor")

    # --------------------------------------------------------------- output

    def _reserve_blocks(self) -> list[v2.Block]:
        blocks = []
        previous = 0
        for cycle in self.cycles:
            gross = sum(
                line.amount
                for plan in self.orders
                for block in plan.blocks
                if block.cycle_index == cycle.index and block.tag == "sale"
                for line in block.lines
                if line.tag == "principal"
            )
            current = apply_bp(gross, RESERVE_BP)
            lines = [v2.Line(*_RESERVE_CURRENT, -current, "reserve_current")]
            if cycle.index > 0:
                lines.insert(0, v2.Line(*_RESERVE_PREVIOUS, previous, "reserve_previous"))
            blocks.append(
                v2.Block(
                    v2.OTHER_TRANSACTION,
                    None,
                    None,
                    None,
                    cycle.end,
                    "23:59:59",
                    cycle.index,
                    "reserve",
                    tuple(lines),
                )
            )
            previous = current
        return blocks

    def _profile(self) -> SellerProfile:
        if self.spec.count(Scenario.C1_GST_UNREGISTERED):
            gst = (
                CapabilityFact(
                    GST_CAPABILITY, False, None, self.gst_boundary - timedelta(days=1)
                ),
                CapabilityFact(GST_CAPABILITY, True, self.gst_boundary, None),
            )
        else:
            gst = (CapabilityFact(GST_CAPABILITY, True),)
        return SellerProfile(SELLER_ID, SELLER_NAME, (*gst, CapabilityFact(SAFE_T_CAPABILITY, True)))

    def build(self, out_dir: Path) -> Manifest:
        spec = self.spec
        self._seed_scenarios()
        for _ in range(spec.order_count - len(self.orders)):
            self._background_order()
        reserves = self._reserve_blocks()
        max_posted = max(b.posted for plan in self.orders for b in plan.blocks)
        max_posted = max(max_posted, *(b.posted for b in reserves))
        if spec.as_of is None and max_posted != self.as_of:
            raise AssertionError("as_of default must be the max posted-date")

        out_dir.mkdir(parents=True, exist_ok=True)
        line_ids: dict[tuple[str, str, str], str] = {}
        files: dict[str, str] = {
            "orders": v2.ORDERS_FILE,
            "bank": v2.BANK_FILE,
            "seller_profile": v2.PROFILE_FILE,
            "evidence": v2.EVIDENCE_FILE,
        }
        totals: list[tuple[Cycle, Paise]] = []
        for cycle in self.cycles:
            blocks = [b for plan in self.orders for b in plan.blocks if b.cycle_index == cycle.index]
            blocks.append(reserves[cycle.index])
            rendered = v2.render_settlement(
                settlement_id=cycle.settlement_id,
                start=cycle.start,
                end=cycle.end,
                deposit=cycle.deposit,
                blocks=blocks,
                file_name=cycle.file_name,
            )
            if rendered.total <= 0:
                raise AssertionError(f"settlement {cycle.settlement_id} total is not positive")
            malformed = spec.malformed_last_settlement and cycle is self.last
            v2.write_settlement(
                out_dir / cycle.file_name, rendered, delimiter="," if malformed else "\t"
            )
            line_ids.update(rendered.line_ids)
            files[f"settlement:{cycle.settlement_id}"] = cycle.file_name
            totals.append((cycle, rendered.total))

        order_rows: dict[str, str] = {}
        ordered = sorted(self.orders, key=lambda o: (o.order_date, o.order_id))
        rows = []
        for i, plan in enumerate(ordered):
            order_rows[plan.order_id] = make_line_id(v2.ORDERS_FILE, i + 2)
            rows.append(
                (
                    plan.order_id,
                    plan.sku,
                    plan.category_id,
                    "1",
                    str(plan.principal),
                    str(plan.tax),
                    plan.order_date.isoformat(),
                    plan.delivery_date.isoformat() if plan.delivery_date else "",
                    plan.refund_initiated_by.value,
                )
            )
        v2.write_csv(out_dir / v2.ORDERS_FILE, v2.ORDERS_COLUMNS, rows)

        bank_rows: list[tuple[str, str, str, str]] = []
        duplicate_rows: tuple[str, ...] = ()
        duplicate_of = (
            self.rng.choice(self.cycles) if spec.count(Scenario.DUPLICATE_UTR) else None
        )
        for cycle, total in totals:
            utr = f"UTIBN{self.rng.randrange(10**11):011d}"
            row = (
                cycle.deposit.isoformat(),
                utr,
                format_paise(total),
                f"NEFT-AMAZON SELLER SERVICES PVT LTD-{cycle.settlement_id}",
            )
            bank_rows.append(row)
            if cycle is duplicate_of:
                bank_rows.append(row)
                first = len(bank_rows)  # header is row 1, so the original is at len
                duplicate_rows = (
                    make_line_id(v2.BANK_FILE, first),
                    make_line_id(v2.BANK_FILE, first + 1),
                )
        v2.write_csv(out_dir / v2.BANK_FILE, v2.BANK_COLUMNS, bank_rows)

        evidence_rows = [
            (
                plan.order_id,
                requirement,
                status,
                supplied_on.isoformat() if supplied_on else "",
            )
            for plan in ordered
            for requirement, status, supplied_on in plan.evidence
        ]
        v2.write_csv(out_dir / v2.EVIDENCE_FILE, v2.EVIDENCE_COLUMNS, evidence_rows)

        (out_dir / v2.PROFILE_FILE).write_text(dumps(self._profile()), encoding="utf-8")

        seeded: list[SeededError] = []
        for plan in self.orders:
            if plan.scenario is None:
                continue
            ids = [line_ids[(plan.order_id, block_tag, tag)] for block_tag, tag in plan.cites]
            if plan.cite_order_row:
                ids.insert(0, order_rows[plan.order_id])
            seeded.append(
                SeededError(
                    plan.scenario,
                    plan.order_id,
                    SCENARIOS[plan.scenario].expected_class,
                    plan.expected_amount,
                    tuple(ids),
                    plan.note,
                )
            )
        if duplicate_of is not None:
            seeded.append(
                SeededError(
                    Scenario.DUPLICATE_UTR,
                    duplicate_of.settlement_id,
                    None,
                    None,
                    duplicate_rows,
                    "the same credit appears twice in bank.csv; only one may satisfy the payout",
                )
            )
        if spec.malformed_last_settlement:
            seeded.append(
                SeededError(
                    Scenario.QUARANTINE_MALFORMED,
                    self.last.settlement_id,
                    None,
                    None,
                    (make_line_id(self.last.file_name, 1), make_line_id(self.last.file_name, 2)),
                    f"{self.last.file_name} was saved as CSV: every row is a single tab-column",
                )
            )

        manifest = Manifest(
            batch_id=spec.batch_id,
            seed=spec.seed,
            as_of=self.as_of,
            cycle_days=spec.cycle_days,
            coverage=self.coverage,
            order_count=len(self.orders),
            categories=tuple(sorted({plan.category_id for plan in self.orders})),
            seeded=tuple(seeded),
            files=files,
            materiality_floor_paise=MATERIALITY_FLOOR_PAISE,
            generator_version=(
                f"{GENERATOR_NAME}; channel=Easy Ship; quantity=1; "
                f"{fees.schedule_label(self.as_of)}"
            ),
        )
        write_manifest(manifest, out_dir / v2.MANIFEST_FILE)
        return manifest


def generate(spec: BatchSpec, out_dir: Path) -> Manifest:
    """Write every input file for ``spec`` into ``out_dir`` and return the manifest."""
    return _Builder(spec).build(out_dir)


def scenario_kind(scenario: Scenario) -> ScenarioKind:
    return SCENARIOS[scenario].kind
