"""One batch: cycles, orders, seeded scenarios, files and the manifest (D9, D20).

Everything is drawn from one ``random.Random(seed)`` in a fixed order, so the
same spec yields byte-identical files. Money is integer paise throughout and
every percentage goes through ``contract.apply_bp``.

Order shape. An order is ``quantity`` units of one SKU at one unit price;
``principal`` is ``quantity × unit price``. A share of orders also charge the
buyer shipping and gift wrap, both per unit, because the fee bands are keyed
per unit (``fees.py``): the referral fee on the unit price, the closing fee on
the unit price including shipping and gift wrap. Every seeded amount is
computed on that basis.

Timeline conventions (all relative to the cycles, never to a clock):

* ``cycle_count`` weekly settlement cycles end on ``as_of``; each cycle's
  file is ``settlement_<end-date>.txt`` and its bank credit lands
  ``DEPOSIT_LAG_DAYS`` after the cycle end. Every settlement pays out:
  ordinary sales are steered to whichever cycle the seeded refunds have
  pushed below ``NET_MARGIN_PAISE``, and a spec too small to cover them is
  refused with a ``ValueError`` naming the cycle.
* ``as_of`` is the batch's maximum posted-date by construction (D18): the
  reserve row posted on the last cycle's end date pins it there, and an
  explicit ``as_of`` moves the whole timeline so the last cycle ends on it.
* the coverage window opens two cycles before the first cycle and closes on
  the last cycle's end: a delivery inside it is one this batch's settlements
  are expected to carry, so absence is evidence (D20); a delivery before it
  takes OUT-OF-WINDOW.
* class-5 placement is relative to the last cycle (the detector's cycle rule
  compares refund and max settlement dates) and to ``as_of`` (the SAFE-T
  window). A refund with an "open" window sits 8..13 days before ``as_of``:
  at least one full cycle back under either reading of "at least", and
  inside the shortest filing-window figure the policy sources give (15 days,
  RS2 open item 6; the labels and rules lanes were told to encode that
  figure). "Awaiting cycle" sits 0..6 days back. "Expired" sits in the first
  cycle, 21 days or more back with four cycles: expired under the 15-day
  figure, not under 30. The generator never encodes the window length.
* when ``C5_GST_UNREGISTERED`` is seeded, the seller's ``gst_registered``
  capability turns on ``cycle_days + 4`` days before ``as_of``. Every date of
  the unregistered order precedes that boundary and every date of every
  other seeded class-5 order that must read as registered follows it, so the
  verdict holds whichever of the order's own dates the capability is
  evaluated on. It cannot hold if the capability is evaluated on ``as_of``
  (one seller, one ``as_of``, two verdicts); the report says so.
"""

from __future__ import annotations

import random
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Final

from leakproof.contract import (
    CATEGORY_NODES,
    DEFAULT_CYCLE_DAYS,
    MATERIALITY_FLOOR_PAISE,
    TOLERANCE_PAISE,
    ErrorClass,
    EvidenceStatus,
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
from leakproof.scenarios import SCENARIOS, SEEDED_ERROR_SCENARIOS, Scenario
from leakproof.serialize import dumps
from leakproof.types import CapabilityFact, CoverageWindow, Manifest, SeededError, SellerProfile

GENERATOR_NAME: Final[str] = "leakproof-generator/0.2"
DEFAULT_LAST_CYCLE_END: Final[date] = date(2026, 8, 21)
DEFAULT_CYCLE_COUNT: Final[int] = 4
#: Scenario placement needs a first cycle three weeks before the last one.
MIN_CYCLES_WITH_SCENARIOS: Final[int] = 4
DEPOSIT_LAG_DAYS: Final[int] = 2
RESERVE_BP: Final[int] = 500
#: A settlement must pay out (one bank credit per cycle, D6), so ordinary
#: traffic is steered to any cycle whose running total sits below this.
NET_MARGIN_PAISE: Final[Paise] = 25_000
#: D10: every seeded error is at least twice the materiality floor.
MATERIAL_SEED_FLOOR: Final[Paise] = 2 * MATERIALITY_FLOOR_PAISE
#: Sale dates precede the refund by this many days at most in a seeded refund case.
MAX_SALE_TO_REFUND_DAYS: Final[int] = 10

SELLER_ID: Final[str] = "A2LEAKPROOFIN1"
SELLER_NAME: Final[str] = "Leakproof Demo Traders"
GST_CAPABILITY: Final[str] = "gst_registered"
SAFE_T_CAPABILITY: Final[str] = "safe_t_enrolled"
INVOICE_REQUIREMENT: Final[str] = "gst_tax_invoice"

ORDER_PREFIXES: Final[tuple[int, ...]] = (171, 403, 404, 405, 406, 407, 408)
SKU_WORDS: Final[dict[str, tuple[str, ...]]] = {
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
#: Units per order, weighted: most orders are single-unit.
QUANTITY_WEIGHTS: Final[dict[int, int]] = {1: 15, 2: 3, 3: 2}
#: Shipping the buyer pays, per unit, in rupees, on the orders that charge it.
SHIPPING_CHARGES: Final[tuple[int, ...]] = (29, 49, 79, 99)
SHIPPED_SHARE: Final[float] = 0.25
#: Gift wrap the buyer pays, per unit, in rupees, on the orders that add it.
GIFT_WRAP_CHARGES: Final[tuple[int, ...]] = (30, 50)
WRAPPED_SHARE: Final[float] = 0.08
#: Weight-handling fee Amazon deducts, an acknowledged deduction (not audited).
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
_SHIPPING_CHARGE = v2.raw_pair(LineKind.SHIPPING_CHARGE)
_SHIPPING_CHARGE_TAX = v2.raw_pair(LineKind.SHIPPING_CHARGE_TAX)
_GIFT_WRAP = v2.raw_pair(LineKind.GIFT_WRAP, description="GiftWrap")
_GIFT_WRAP_CHARGEBACK = v2.raw_pair(LineKind.GIFT_WRAP, description="GiftwrapChargeback")
_COMMISSION = v2.raw_pair(LineKind.COMMISSION)
_CLOSING = v2.raw_pair(LineKind.FIXED_CLOSING_FEE)
_SHIPPING_FEE = v2.raw_pair(LineKind.SHIPPING_FEE)
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

#: Class-5 cases whose refund sits inside an open SAFE-T window and at least
#: one full cycle before the last settlement date.
_C5_OPEN_WINDOW: Final[frozenset[Scenario]] = frozenset(
    {
        Scenario.C5_PLAIN,
        Scenario.C5_SELLER_ISSUED,
        Scenario.C5_ATOZ,
        Scenario.C5_WINDOW_DATE_MISSING,
        Scenario.C5_GST_UNREGISTERED,
        Scenario.C5_INVOICE_PENDING,
    }
)
#: Class-5 cases whose verdict needs the seller to read as GST-registered.
_C5_REGISTERED: Final[frozenset[Scenario]] = frozenset(
    {
        Scenario.C5_PLAIN,
        Scenario.C5_AWAITING_CYCLE,
        Scenario.C5_SELLER_ISSUED,
        Scenario.C5_ATOZ,
        Scenario.C5_WINDOW_DATE_MISSING,
        Scenario.C5_INVOICE_PENDING,
    }
)


@dataclass(frozen=True, slots=True)
class BatchSpec:
    """What ``generate`` builds. ``scenario_counts`` is exact: that many orders
    carry each scenario; the rest of ``order_count`` is ordinary traffic.
    ``as_of`` is the date the batch is cut, i.e. the last cycle's end."""

    batch_id: str
    seed: int
    order_count: int
    scenario_counts: Mapping[Scenario, int]
    cycle_count: int = DEFAULT_CYCLE_COUNT
    cycle_days: int = DEFAULT_CYCLE_DAYS
    as_of: date | None = None
    categories: tuple[str, ...] = fees.COVERED_CATEGORIES
    malformed_last_settlement: bool = False

    def count(self, scenario: Scenario) -> int:
        return self.scenario_counts.get(scenario, 0)

    @property
    def last_cycle_end(self) -> date:
        return self.as_of if self.as_of is not None else DEFAULT_LAST_CYCLE_END

    @property
    def first_cycle_start(self) -> date:
        return self.last_cycle_end - timedelta(days=self.cycle_count * self.cycle_days - 1)

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
    if spec.cycle_count >= 1 and spec.first_cycle_start < fees.REFERRAL_VALID_FROM:
        problems.append(
            f"first cycle starts {spec.first_cycle_start}, before the encoded fee "
            f"schedule ({fees.REFERRAL_VALID_FROM})"
        )
    if not spec.categories:
        problems.append("categories must not be empty")
    for category in spec.categories:
        if category not in PRICE_POINTS or not fees.is_known_category(category):
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
    quantity: int
    unit_price: Paise
    principal: Paise
    tax: Paise
    shipping: Paise  # what the buyer paid for shipping, all units
    shipping_tax: Paise
    gift_wrap: Paise  # what the buyer paid for gift wrap, all units
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
    evidence: tuple[tuple[str, EvidenceStatus, date | None], ...] = ()

    @property
    def closing_key(self) -> Paise:
        return fees.closing_key(self.principal, self.shipping, self.gift_wrap, self.quantity)


def _pct(bp: int) -> str:
    return f"{bp / 100:.2f}%"


def _units(plan: OrderPlan) -> str:
    return f"{plan.quantity} x {format_paise(plan.unit_price)}"


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
        self.as_of = self.last.end
        self.gst_boundary: date | None = (
            self.as_of - timedelta(days=spec.cycle_days + 4)
            if spec.count(Scenario.C5_GST_UNREGISTERED)
            else None
        )
        self.orders: list[OrderPlan] = []
        self.used_ids: set[str] = set()
        #: Running total per cycle, reserve included, kept as blocks are posted.
        self.net: dict[int, Paise] = {c.index: 0 for c in self.cycles}

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

    def _date_in(self, lo: date, hi: date) -> date:
        if hi < lo:
            raise AssertionError(f"empty date range {lo}..{hi}")
        return lo + timedelta(days=self.rng.randint(0, (hi - lo).days))

    def _pick_quantity(self) -> int:
        return self.rng.choices(list(QUANTITY_WEIGHTS), weights=list(QUANTITY_WEIGHTS.values()))[0]

    def _pick_unit_price(
        self, category: str, *, minimum: Paise = 0, maximum: Paise | None = None
    ) -> Paise:
        candidates = [
            p * 100
            for p in PRICE_POINTS[category]
            if p * 100 >= minimum and (maximum is None or p * 100 <= maximum)
        ]
        if not candidates:
            raise ValueError(f"no price point for {category} within [{minimum}, {maximum}]")
        return self.rng.choice(candidates)

    def _category_with_price(self, minimum: Paise) -> str:
        options = [c for c in fees.COVERED_CATEGORIES if max(PRICE_POINTS[c]) * 100 >= minimum]
        return self.rng.choice(options)

    def _any_category(self) -> str:
        return self.rng.choice(fees.COVERED_CATEGORIES)

    def _pick_extras(self, *, shipped: bool | None = None, wrapped: bool | None = None) -> tuple:
        """Per-unit shipping and gift wrap in paise; ``None`` draws them."""
        if shipped is None:
            shipped = self.rng.random() < SHIPPED_SHARE
        if wrapped is None:
            wrapped = self.rng.random() < WRAPPED_SHARE
        shipping = self.rng.choice(SHIPPING_CHARGES) * 100 if shipped else 0
        gift_wrap = self.rng.choice(GIFT_WRAP_CHARGES) * 100 if wrapped else 0
        return shipping, gift_wrap

    def _new_plan(
        self,
        category: str,
        unit_price: Paise,
        quantity: int,
        order_date: date,
        delivery: date | None,
        *,
        shipping_per_unit: Paise = 0,
        gift_wrap_per_unit: Paise = 0,
        refund_by: RefundInitiator = RefundInitiator.NONE,
        scenario: Scenario | None = None,
    ) -> OrderPlan:
        principal = unit_price * quantity
        shipping = shipping_per_unit * quantity
        plan = OrderPlan(
            order_id=self._order_id(),
            sku=self._sku(category),
            category_id=category,
            quantity=quantity,
            unit_price=unit_price,
            principal=principal,
            tax=apply_bp(principal, ITEM_GST_BP[category]),
            shipping=shipping,
            shipping_tax=apply_bp(shipping, ITEM_GST_BP[category]),
            gift_wrap=gift_wrap_per_unit * quantity,
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
        """Order, delivery and posted dates for a sale settled in ``cycle``."""
        lo = max(cycle.start, posted_min) if posted_min else cycle.start
        hi = min(cycle.end, posted_max) if posted_max else cycle.end
        if hi < lo:
            raise AssertionError(f"empty posted-date range in cycle {cycle.index}")
        posted = lo + timedelta(days=self.rng.randint(0, (hi - lo).days))
        delivery = posted - timedelta(days=self.rng.randint(1, 3))
        order_date = delivery - timedelta(days=self.rng.randint(2, 5))
        return order_date, delivery, posted

    def _dates_before_refund(
        self, refund: date, *, earliest_order: date
    ) -> tuple[date, date, date]:
        """Order, delivery and posted dates for a sale refunded on ``refund``:
        posted inside a cycle, 1..10 days earlier, nothing before
        ``earliest_order``."""
        posted = max(
            self.first.start,
            earliest_order + timedelta(days=1),
            refund - timedelta(days=self.rng.randint(1, MAX_SALE_TO_REFUND_DAYS)),
        )
        delivery = max(
            earliest_order + timedelta(days=1), posted - timedelta(days=self.rng.randint(0, 2))
        )
        order_date = max(earliest_order, delivery - timedelta(days=self.rng.randint(1, 4)))
        if not posted < refund:
            raise AssertionError(f"sale posted {posted} not before refund {refund}")
        return order_date, delivery, posted

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
        charged_commission = (
            fees.commission_paise(plan.category_id, plan.unit_price, plan.quantity, posted)
            if commission is None
            else commission
        )
        charged_closing = (
            fees.closing_fee_paise(plan.category_id, plan.closing_key, plan.quantity, posted)
            if closing is None
            else closing
        )
        shipping_fee = self.rng.choice(SHIPPING_FEES)
        fee_tax = fees.fee_gst_paise(charged_commission + charged_closing + shipping_fee)
        tcs_legs = (
            fees.tcs_legs(plan.principal, intra_state=plan.intra_state, on=posted)
            if tcs is None
            else tcs
        )
        tds_amount = fees.tds_paise(plan.principal, posted) if tds is None else tds
        plan.commission_charged = charged_commission
        lines = [
            v2.Line(*_PRINCIPAL, plan.principal, "principal"),
            v2.Line(*_ITEM_TAX, plan.tax, "tax"),
        ]
        if plan.shipping:
            lines.append(v2.Line(*_SHIPPING_CHARGE, plan.shipping, "shipping_charge"))
            lines.append(v2.Line(*_SHIPPING_CHARGE_TAX, plan.shipping_tax, "shipping_charge_tax"))
        if plan.gift_wrap:
            lines.append(v2.Line(*_GIFT_WRAP, plan.gift_wrap, "gift_wrap"))
        lines.append(v2.Line(*_COMMISSION, -charged_commission, "commission"))
        lines.append(v2.Line(*_CLOSING, -charged_closing, "closing"))
        if plan.gift_wrap:
            lines.append(v2.Line(*_GIFT_WRAP_CHARGEBACK, -plan.gift_wrap, "gift_wrap_chargeback"))
        lines.append(v2.Line(*_SHIPPING_FEE, -shipping_fee, "shipping_fee"))
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
            plan.quantity,
            posted,
            self._posted_time(),
            cycle.index,
            "sale",
            tuple(lines),
            shipment_id=plan.shipment_id,
            order_item_code=plan.order_item_code,
        )
        return self._post(plan, block)

    def _refund_block(
        self,
        plan: OrderPlan,
        posted: date,
        *,
        txn_type: str = _REFUND,
        reverse: bool = True,
        undated: bool = False,
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
        if plan.shipping:
            lines.append(v2.Line(*_SHIPPING_CHARGE, -plan.shipping, "shipping_charge"))
            lines.append(v2.Line(*_SHIPPING_CHARGE_TAX, -plan.shipping_tax, "shipping_charge_tax"))
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
            plan.quantity,
            posted,
            self._posted_time(),
            cycle.index,
            "refund",
            tuple(lines),
            shipment_id=plan.shipment_id,
            order_item_code=plan.order_item_code,
            undated=undated,
        )
        return self._post(plan, block)

    def _reversal_block(self, plan: OrderPlan, posted: date) -> v2.Block:
        """A commission reversal posted on its own in a later cycle."""
        cycle = self._cycle_for(posted)
        charged = plan.commission_charged
        block = v2.Block(
            _REFUND,
            plan.order_id,
            plan.sku,
            plan.quantity,
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
        return self._post(plan, block)

    def _adjustment_block(self, plan: OrderPlan, posted: date, line: v2.Line) -> v2.Block:
        cycle = self._cycle_for(posted)
        block = v2.Block(
            _ADJUSTMENT,
            plan.order_id,
            plan.sku,
            plan.quantity,
            posted,
            self._posted_time(),
            cycle.index,
            "adjustment",
            (line,),
            shipment_id=plan.shipment_id,
            order_item_code=plan.order_item_code,
            adjustment_id=f"ADJ{self._alnum(10)}",
        )
        return self._post(plan, block)

    def _post(self, plan: OrderPlan, block: v2.Block) -> v2.Block:
        """Attach a block to its order and keep the per-cycle running total.
        A sale's principal feeds this cycle's reserve and the next cycle's
        release, so the running total tracks the file total to within the
        reserve's rounding."""
        plan.blocks.append(block)
        k = block.cycle_index
        self.net[k] += sum(line.amount for line in block.lines)
        if block.tag == "sale":
            reserve = apply_bp(plan.principal, RESERVE_BP)
            self.net[k] -= reserve
            if k + 1 in self.net:
                self.net[k + 1] += reserve
        return block

    def _background_cycle(self) -> Cycle:
        """The cycle with the lowest running total while any sits below the
        margin, otherwise a random one. The scenarios concentrate refunds in
        the last cycles; ordinary sales have to cover them or the settlement
        cannot pay out."""
        lowest = min(self.cycles, key=lambda c: (self.net[c.index], c.index))
        if self.net[lowest.index] < NET_MARGIN_PAISE:
            return lowest
        return self.rng.choice(self.cycles)

    # ------------------------------------------------------------- ordinary

    def _background_order(self, category: str | None = None) -> OrderPlan:
        if category is None:
            weights = [4 if c == "electronics-accessories" else 3 for c in self.spec.categories]
            category = self.rng.choices(self.spec.categories, weights=weights)[0]
        unit_price = self._pick_unit_price(category)
        quantity = self._pick_quantity()
        shipping, gift_wrap = self._pick_extras()
        cycle = self._background_cycle()
        order_date, delivery, posted = self._sale_dates(cycle)
        plan = self._new_plan(
            category,
            unit_price,
            quantity,
            order_date,
            delivery,
            shipping_per_unit=shipping,
            gift_wrap_per_unit=gift_wrap,
        )
        promotion = 0
        if self.rng.random() < 0.15:
            promotion = apply_bp(plan.principal, self.rng.choice(PROMOTION_BPS))
        self._sale_block(plan, posted, promotion=promotion)
        if posted < self.last.end and self.rng.random() < 0.08:
            seller_issued = self.rng.random() < 0.3
            plan.refund_initiated_by = (
                RefundInitiator.SELLER if seller_issued else RefundInitiator.AMAZON
            )
            self._refund_block(plan, self._date_in(posted + timedelta(days=1), self.last.end))
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
        u, q = plan.unit_price, plan.quantity
        correct_bp = fees.referral_bp(plan.category_id, u, on)
        correct = fees.commission_at_bp(u, q, correct_bp)
        candidates: list[tuple[int, str]] = []
        legacy_bp = fees.legacy_referral_bp(plan.category_id, u)
        if legacy_bp > correct_bp:
            candidates.append((legacy_bp, "the pre-2026-03-16 tier"))
        candidates.extend(
            (correct_bp + extra, "an inflated rate") for extra in WRONG_RATE_EXTRA_BPS
        )
        viable = [
            (bp, why)
            for bp, why in candidates
            if fees.commission_at_bp(u, q, bp) - correct >= MATERIAL_SEED_FLOOR
        ]
        bp, why = self.rng.choice(viable)
        charged = fees.commission_at_bp(u, q, bp)
        note = (
            f"commission {_pct(bp)} charged ({why}) vs {_pct(correct_bp)} for "
            f"{CATEGORY_NODES[plan.category_id]!r} on {_units(plan)} (unit price band); "
            f"overcharge excludes the GST that follows it"
        )
        return charged, note

    def _seed_c1(self, scenario: Scenario) -> None:
        category = self._any_category()
        quantity = self._pick_quantity()
        unit_price = self._pick_unit_price(category, minimum=40_000)
        shipping, gift_wrap = self._pick_extras()
        cycle = self.rng.choice(self.cycles)
        order_date, delivery, posted = self._sale_dates(cycle)
        plan = self._new_plan(
            category,
            unit_price,
            quantity,
            order_date,
            delivery,
            shipping_per_unit=shipping,
            gift_wrap_per_unit=gift_wrap,
            scenario=scenario,
        )
        charged, note = self._overcharge(plan, posted)
        correct = fees.commission_paise(category, unit_price, quantity, posted)
        self._sale_block(plan, posted, commission=charged)
        plan.expected_amount = charged - correct
        plan.cites = (("sale", "commission"), ("sale", "principal"))
        plan.note = f"{note}; support ticket, no refund event and no filing window (ADR-0006)"

    # --------------------------------------------------------------- class 2

    def _seed_c2(self, scenario: Scenario) -> None:
        category = self._any_category()
        quantity = self._pick_quantity()
        shipping, gift_wrap = self._pick_extras()
        cycle = self.rng.choice(self.cycles)
        order_date, delivery, posted = self._sale_dates(cycle)
        bands = fees.closing_band_fees(category, posted)
        top_bounded = fees.CLOSING_BAND_UPPER[-1]
        if scenario is Scenario.C2_SLAB_BOUNDARY:
            # The key lands exactly on the highest bounded band's inclusive
            # upper bound; the charge is the open band's fee.
            unit_price = top_bounded - shipping - gift_wrap
        else:
            unit_price = self._pick_unit_price(category, maximum=top_bounded - shipping - gift_wrap)
        plan = self._new_plan(
            category,
            unit_price,
            quantity,
            order_date,
            delivery,
            shipping_per_unit=shipping,
            gift_wrap_per_unit=gift_wrap,
            scenario=scenario,
        )
        key = plan.closing_key
        band = fees.closing_band(key)
        correct_unit = bands[band]
        if scenario is Scenario.C2_SLAB_BOUNDARY:
            if key != top_bounded:
                raise AssertionError(f"boundary key {key} != {top_bounded}")
            wrong_unit = bands[-1]
        else:
            higher = [
                fee
                for i, fee in enumerate(bands)
                if i != band and quantity * (fee - correct_unit) >= MATERIAL_SEED_FLOOR
            ]
            wrong_unit = self.rng.choice(higher)
        charged = quantity * wrong_unit
        correct = quantity * correct_unit
        self._sale_block(plan, posted, closing=charged)
        plan.expected_amount = charged - correct
        cites = [("sale", "closing"), ("sale", "principal")]
        if plan.shipping:
            cites.append(("sale", "shipping_charge"))
        if plan.gift_wrap:
            cites.append(("sale", "gift_wrap"))
        plan.cites = tuple(cites)
        edge = (
            " (exactly at the band's inclusive upper bound)"
            if (scenario is Scenario.C2_SLAB_BOUNDARY)
            else ""
        )
        plan.note = (
            f"closing fee {format_paise(charged)} charged vs {format_paise(correct)}: "
            f"{quantity} unit(s) keyed at {format_paise(key)}{edge} = unit price "
            f"{format_paise(plan.unit_price)} + shipping {format_paise(plan.shipping // quantity)} "
            f"+ gift wrap {format_paise(plan.gift_wrap // quantity)}, Fulfilment Centre "
            f"{fees.closing_group(category)} group; the fee charged is that of a different band; "
            f"amount excludes the GST that follows it"
        )

    # --------------------------------------------------------------- class 5

    def _c5_refund_window(self, scenario: Scenario) -> tuple[date, date, date]:
        """(earliest refund, latest refund, earliest order date) for a class-5 case."""
        cd = self.spec.cycle_days
        last = self.last.end
        open_lo, open_hi = last - timedelta(days=2 * cd - 1), last - timedelta(days=cd + 1)
        earliest_order = self.coverage.start
        if scenario is Scenario.C5_AWAITING_CYCLE:
            lo, hi = last - timedelta(days=cd - 1), last
        elif scenario is Scenario.C5_WINDOW_EXPIRED:
            lo, hi = self.first.start + timedelta(days=1), self.first.end
        elif scenario is Scenario.C5_GST_UNREGISTERED:
            assert self.gst_boundary is not None
            lo, hi = open_lo, self.gst_boundary - timedelta(days=1)
        elif scenario in _C5_OPEN_WINDOW:
            lo, hi = open_lo, open_hi
        else:
            raise AssertionError(f"no refund window for {scenario}")
        if self.gst_boundary is not None and scenario in _C5_REGISTERED:
            earliest_order = self.gst_boundary
            lo = max(lo, self.gst_boundary + timedelta(days=2))
        return lo, hi, earliest_order

    def _seed_c5(self, scenario: Scenario) -> None:
        category = self._any_category()
        quantity = self._pick_quantity()
        shipping, gift_wrap = self._pick_extras()
        # The commission itself is the seeded amount, so it must clear the floor.
        unit_price = self._pick_unit_price(category, minimum=100_100)
        refund_by = RefundInitiator.AMAZON
        refund_txn = _REFUND
        if scenario is Scenario.C5_SELLER_ISSUED:
            refund_by = RefundInitiator.SELLER
        if scenario is Scenario.C5_ATOZ:
            refund_txn = _ATOZ

        if scenario is Scenario.C5_REVERSED_LATER_CYCLE:
            refund_cycle = self.rng.choice(self.cycles[:-1])
            refund = self._date_in(refund_cycle.start + timedelta(days=1), refund_cycle.end)
            earliest_order = self.coverage.start
        else:
            lo, hi, earliest_order = self._c5_refund_window(scenario)
            refund = self._date_in(lo, hi)
        order_date, delivery, posted = self._dates_before_refund(
            refund, earliest_order=earliest_order
        )
        plan = self._new_plan(
            category,
            unit_price,
            quantity,
            order_date,
            delivery,
            shipping_per_unit=shipping,
            gift_wrap_per_unit=gift_wrap,
            refund_by=refund_by,
            scenario=scenario,
        )
        self._sale_block(plan, posted)
        undated = scenario is Scenario.C5_WINDOW_DATE_MISSING
        self._refund_block(plan, refund, txn_type=refund_txn, reverse=False, undated=undated)
        commission = plan.commission_charged
        if commission < MATERIAL_SEED_FLOOR:
            raise AssertionError(f"{scenario}: commission {commission} below twice the floor")
        days = (self.as_of - refund).days
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
        cd = self.spec.cycle_days
        detail = {
            Scenario.C5_PLAIN: (
                f"at least one full {cd}-day cycle before the max settlement date; SAFE-T "
                f"window open; GST tax invoice supplied (evidence.csv)"
            ),
            Scenario.C5_AWAITING_CYCLE: (
                f"less than one full {cd}-day cycle before the max settlement date"
            ),
            Scenario.C5_SELLER_ISSUED: "refund issued by the seller (orders.csv), a SAFE-T exclusion",
            Scenario.C5_ATOZ: "an A-to-z Guarantee refund, a SAFE-T exclusion",
            Scenario.C5_WINDOW_EXPIRED: (
                "refund in the first cycle, so the SAFE-T window has closed at as_of under the "
                "shortest published figure"
            ),
            Scenario.C5_WINDOW_DATE_MISSING: (
                "the refund rows carry no posted-date, so no line gives the window's start date; "
                "the parser quarantines those rows (bad posted-date) and the refund is then known "
                "only from orders.csv refund_initiated_by"
            ),
            Scenario.C5_GST_UNREGISTERED: (
                f"every date of the order precedes the seller's GST registration on "
                f"{self.gst_boundary} (seller_profile.json), so the tax invoice can never exist"
            ),
            Scenario.C5_INVOICE_PENDING: (
                "GST-registered seller; the tax invoice is requested and not yet supplied "
                "(evidence.csv)"
            ),
        }[scenario]
        plan.note = (
            f"refund posted {refund} ({days} days before as_of); commission "
            f"{format_paise(commission)} charged on the sale ({_units(plan)}) never reversed; "
            f"{detail}; amount excludes the GST reversal that follows it"
        )
        if scenario is Scenario.C5_INVOICE_PENDING:
            plan.evidence = ((INVOICE_REQUIREMENT, EvidenceStatus.PENDING, None),)
        elif scenario is not Scenario.C5_GST_UNREGISTERED:
            supplied = min(refund + timedelta(days=1), self.as_of)
            plan.evidence = ((INVOICE_REQUIREMENT, EvidenceStatus.SATISFIED, supplied),)

    # --------------------------------------------------------------- class 6

    def _seed_c6(self, scenario: Scenario) -> None:
        category = self._any_category()
        unit_price = self._pick_unit_price(category)
        quantity = self._pick_quantity()
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
        plan = self._new_plan(
            category, unit_price, quantity, order_date, delivery, scenario=scenario
        )
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
            plan.expected_amount = plan.principal + plan.tax
            plan.note = (
                f"delivered {delivery} ({(self.as_of - delivery).days} days before as_of, more "
                f"than two {cd}-day cycles) and absent from every settlement; amount is the "
                f"order's principal plus tax from orders.csv (ADR-0005 bound)"
            )

    # --------------------------------------------------------------- class 7

    def _seed_c7(self, scenario: Scenario) -> None:
        # The withheld-vs-recomputed delta is 0.5% (TCS) or 0.9% (TDS) of the
        # principal, so the principal must clear ₹4,000 or ₹2,223.
        minimum = 400_000 if scenario is Scenario.C7_TCS_MISMATCH else 225_000
        quantity = self._pick_quantity()
        unit_minimum = -(-minimum // quantity)
        category = self._category_with_price(unit_minimum)
        unit_price = self._pick_unit_price(category, minimum=unit_minimum)
        shipping, gift_wrap = self._pick_extras()
        cycle = self.rng.choice(self.cycles)
        order_date, delivery, posted = self._sale_dates(cycle)
        plan = self._new_plan(
            category,
            unit_price,
            quantity,
            order_date,
            delivery,
            shipping_per_unit=shipping,
            gift_wrap_per_unit=gift_wrap,
            scenario=scenario,
        )
        principal = plan.principal
        if scenario is Scenario.C7_TCS_MISMATCH:
            wrong = fees.legacy_tcs_legs(principal, intra_state=plan.intra_state)
            correct = fees.tcs_legs(principal, intra_state=plan.intra_state, on=posted)
            self._sale_block(plan, posted, tcs=wrong)
            withheld = sum(v for _, v in wrong)
            expected_total = sum(v for _, v in correct)
            plan.expected_amount = withheld - expected_total
            plan.cites = (*(("sale", f"tcs:{d}") for d, _ in wrong), ("sale", "principal"))
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
        category = self._any_category()
        unit_price = self._pick_unit_price(category)
        quantity = self._pick_quantity()
        shipping, gift_wrap = self._pick_extras()
        cycle = self.rng.choice(self.cycles)
        order_date, delivery, posted = self._sale_dates(cycle)
        plan = self._new_plan(
            category,
            unit_price,
            quantity,
            order_date,
            delivery,
            shipping_per_unit=shipping,
            gift_wrap_per_unit=gift_wrap,
            scenario=scenario,
        )
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
            self._sale_block(plan, posted, extra=(v2.Line(*_TECH_FEE, -amount, "technology_fee"),))
            plan.cites = (("sale", "technology_fee"),)
            plan.note = (
                f"deduction {format_paise(amount)} under {_TECH_FEE[1]!r}, a known code the "
                f"rate card neither audits nor acknowledges"
            )
        plan.expected_amount = amount

    # ------------------------------------------------------- outside classes

    def _seed_below_materiality(self) -> None:
        category = self._any_category()
        unit_price = self._pick_unit_price(category)
        quantity = self._pick_quantity()
        shipping, gift_wrap = self._pick_extras()
        cycle = self.rng.choice(self.cycles)
        order_date, delivery, posted = self._sale_dates(cycle)
        plan = self._new_plan(
            category,
            unit_price,
            quantity,
            order_date,
            delivery,
            shipping_per_unit=shipping,
            gift_wrap_per_unit=gift_wrap,
            scenario=Scenario.BELOW_MATERIALITY,
        )
        correct = fees.commission_paise(category, unit_price, quantity, posted)
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
        if self.gst_boundary is not None:
            gst = (
                CapabilityFact(GST_CAPABILITY, False, None, self.gst_boundary - timedelta(days=1)),
                CapabilityFact(GST_CAPABILITY, True, self.gst_boundary, None),
            )
        else:
            gst = (CapabilityFact(GST_CAPABILITY, True),)
        return SellerProfile(
            SELLER_ID, SELLER_NAME, (*gst, CapabilityFact(SAFE_T_CAPABILITY, True))
        )

    def build(self, out_dir: Path) -> Manifest:
        spec = self.spec
        self._seed_scenarios()
        for _ in range(spec.order_count - len(self.orders)):
            self._background_order()
        reserves = self._reserve_blocks()
        max_posted = max(b.posted for plan in self.orders for b in plan.blocks)
        max_posted = max(max_posted, *(b.posted for b in reserves))
        if max_posted != self.as_of:
            raise AssertionError("as_of must be the max posted-date")

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
            blocks = [
                b for plan in self.orders for b in plan.blocks if b.cycle_index == cycle.index
            ]
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
                raise ValueError(
                    f"settlement {cycle.settlement_id} ({cycle.file_name}) totals "
                    f"{format_paise(rendered.total)}: order_count {spec.order_count} is too "
                    f"small to cover the refunds seeded in that cycle; raise order_count or "
                    f"lower the scenario counts"
                )
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
                    str(plan.quantity),
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
        duplicate_of = self.rng.choice(self.cycles) if spec.count(Scenario.DUPLICATE_UTR) else None
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
                status.value,
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
                f"{GENERATOR_NAME}; {fees.schedule_label(self.as_of)}; "
                "class-1/2/5 amounts exclude fee GST; class-6 amount=principal+tax"
            ),
        )
        write_manifest(manifest, out_dir / v2.MANIFEST_FILE)
        return manifest


def generate(spec: BatchSpec, out_dir: Path) -> Manifest:
    """Write every input file for ``spec`` into ``out_dir`` and return the manifest."""
    return _Builder(spec).build(out_dir)
