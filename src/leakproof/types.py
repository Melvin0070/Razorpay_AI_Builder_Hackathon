"""Seam types. Integrator-owned, frozen for the duration of a wave.

Every record that crosses a lane boundary is defined here so that a lane can be
coded against the seam before its neighbour exists. Producer and consumers are
named on each type; the strategy doc §4 has the same table.

Conventions: frozen dataclasses with slots; tuples, never lists, so a record is
hashable and cannot be mutated by a downstream lane; money is ``Paise``
(signed int); dates are ``datetime.date`` and every date computation takes
``as_of`` as an argument (D18).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Protocol

from leakproof.contract import (
    AuditAction,
    BlockerKind,
    Disposition,
    ErrorClass,
    EvidenceSource,
    EvidenceStatus,
    LineKind,
    Mechanism,
    NotClaimableReason,
    Paise,
    RefundInitiator,
    RupeeLine,
    State,
    TransactionType,
    UnexplainedBasis,
    WindowStatus,
)
from leakproof.scenarios import Scenario

# --------------------------------------------------------------------------- #
# Shared small records
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class Citation:
    """Every rule, rate and label carries one (D14, D17): where it came from,
    when it was read, and whether the primary source was reached."""

    label: str
    url: str
    as_of: date
    verified: bool


@dataclass(frozen=True, slots=True)
class CapabilityFact:
    """A seller capability with a validity window: GST registration, programme
    enrolment, a compliant VMS. One shape for all of them (precedence step 4)."""

    name: str
    holds: bool
    valid_from: date | None = None
    valid_to: date | None = None

    def applies_on(self, on: date) -> bool:
        if self.valid_from is not None and on < self.valid_from:
            return False
        return not (self.valid_to is not None and on > self.valid_to)


@dataclass(frozen=True, slots=True)
class SellerProfile:
    """Seller-profile config (design doc, Inputs). Producer: config file via
    lane D's loader. Consumers: K (step 4 / step 5 degrade), M (drafter)."""

    seller_id: str
    display_name: str
    capabilities: tuple[CapabilityFact, ...] = ()

    def capability(self, name: str, on: date) -> bool | None:
        """True/False when a fact covers ``on``; None when nothing is declared,
        which lane K must surface as "permanence unknown", never as False."""
        for fact in self.capabilities:
            if fact.name == name and fact.applies_on(on):
                return fact.holds
        return None


# --------------------------------------------------------------------------- #
# Parsed inputs. Producer: lane D. Consumers: H, I, L.
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class Order:
    """One row of the seller's own order export."""

    order_id: str
    sku: str
    category_id: str
    quantity: int
    principal_paise: Paise  # total pre-tax sale value for the row
    tax_paise: Paise  # total GST collected on the item
    order_date: date
    delivery_date: date | None
    refund_initiated_by: RefundInitiator
    source_line_id: str


@dataclass(frozen=True, slots=True)
class SettlementHeader:
    """The summary row that opens every V2 settlement file."""

    settlement_id: str
    start_date: date
    end_date: date
    deposit_date: date
    total_amount_paise: Paise
    currency: str
    source_line_id: str


@dataclass(frozen=True, slots=True)
class SettlementLine:
    """One transaction row. ``kind`` says what the line is; ``txn_type`` says
    under which event it was posted (contract.LineKind)."""

    line_id: str
    settlement_id: str
    txn_type: TransactionType
    kind: LineKind
    amount_type: str  # raw, kept for citation and for CODE_UNSEEN reporting
    amount_description: str  # raw
    amount_paise: Paise  # signed, exactly as written
    posted_date: date
    order_id: str | None
    sku: str | None = None
    quantity: int | None = None
    adjustment_id: str | None = None


@dataclass(frozen=True, slots=True)
class BankCredit:
    line_id: str
    credit_date: date
    utr: str
    amount_paise: Paise
    narration: str


@dataclass(frozen=True, slots=True)
class QuarantinedRow:
    """A malformed row with its reason. Stays in the match-rate denominator (D7)."""

    line_id: str
    reason: str


@dataclass(frozen=True, slots=True)
class SettlementFileParse:
    source_file: str
    header: SettlementHeader | None
    lines: tuple[SettlementLine, ...]
    quarantined: tuple[QuarantinedRow, ...] = ()
    hint: str | None = None  # the one actionable guess (wireframe frame 4)


@dataclass(frozen=True, slots=True)
class OrdersParse:
    source_file: str
    orders: tuple[Order, ...]
    quarantined: tuple[QuarantinedRow, ...] = ()
    hint: str | None = None


@dataclass(frozen=True, slots=True)
class BankParse:
    source_file: str
    credits: tuple[BankCredit, ...]
    quarantined: tuple[QuarantinedRow, ...] = ()
    hint: str | None = None


@dataclass(frozen=True, slots=True)
class CoverageWindow:
    """The batch's declared cycle coverage (D20). Deliveries outside it take
    the OUT_OF_WINDOW disposition. Both ends inclusive."""

    start: date
    end: date

    def contains(self, on: date) -> bool:
        return self.start <= on <= self.end


@dataclass(frozen=True, slots=True)
class BatchInputs:
    """Everything the deterministic pipeline consumes for one batch.
    Producer: cli / lane L assembly from lane D parsers. Consumers: H, I, J, K, L."""

    batch_id: str
    marketplace: str
    as_of: date
    cycle_days: int
    coverage: CoverageWindow
    orders: OrdersParse
    settlements: tuple[SettlementFileParse, ...]
    profile: SellerProfile
    bank: BankParse | None = None


# --------------------------------------------------------------------------- #
# Rate-card lookups. Producer: lane C. Consumers: J, L (coverage summary).
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class RateRule:
    """One dated, cited rule. ``category_id`` None means marketplace-wide (fee
    GST, refund administration fee, TCS, TDS). Percentages are basis points;
    fixed amounts are paise; slabs bound the order principal, inclusive, None
    for an open end. ``audited`` False means "known and acknowledged, not
    audited" (a shipping fee, a promotion), which is what keeps class 8 from
    flooding with every expected deduction (ADR-0005)."""

    rule_id: str
    kind: LineKind
    category_id: str | None
    percent_bp: int | None
    fixed_paise: Paise | None
    slab_min_paise: Paise | None
    slab_max_paise: Paise | None
    valid_from: date
    valid_to: date | None
    citation: Citation
    audited: bool = True


@dataclass(frozen=True, slots=True)
class LookupMiss:
    """Outside declared coverage: UNCOVERED. Inside it: CONFIG_ERROR, which
    fails verify naming category, slab and as_of (D17)."""

    disposition: Disposition
    kind: LineKind
    category_id: str | None
    as_of: date
    detail: str


RateLookup = RateRule | LookupMiss


@dataclass(frozen=True, slots=True)
class CoverageDeclaration:
    """What the corpus says it covers, shown on the dashboard (frame 4)."""

    categories: tuple[str, ...]
    valid_from: date
    valid_to: date | None
    audited_kinds: tuple[LineKind, ...]
    acknowledged_kinds: tuple[LineKind, ...]


class RateCard(Protocol):
    """What lane C provides and lanes J and L consume. Defined here, not in
    ``ratecard/``, so detectors are coded against the seam and never import
    the corpus (D12 import test)."""

    def lookup(self, kind: LineKind, category_id: str | None, as_of: date) -> RateLookup: ...

    def coverage(self) -> CoverageDeclaration: ...


@dataclass(frozen=True, slots=True)
class DetectorContext:
    """Everything a detector may consult besides the folded order (D23). No
    manifest, no labels, no system clock."""

    rate_card: RateCard
    profile: SellerProfile
    as_of: date
    cycle_days: int
    batch_max_settlement_date: date


# --------------------------------------------------------------------------- #
# Folded ledger. Producer: lane H. Consumers: J, K, F (holdout fixtures).
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class FoldedOrder:
    """One order with every settlement line that references it, across cycles,
    in cycle order with a deterministic tiebreak (D20). Detectors consume this
    and never a raw line. ``order`` is None when settlement lines reference an
    order absent from the seller's export."""

    order_id: str
    order: Order | None
    lines: tuple[SettlementLine, ...]
    settlement_ids: tuple[str, ...]  # cycle order, oldest first
    in_coverage: bool
    as_of: date

    def select(
        self,
        *,
        txn_type: TransactionType | None = None,
        kind: LineKind | None = None,
    ) -> tuple[SettlementLine, ...]:
        return tuple(
            ln
            for ln in self.lines
            if (txn_type is None or ln.txn_type is txn_type) and (kind is None or ln.kind is kind)
        )

    @property
    def deductions_paise(self) -> Paise:
        """Absolute sum of every negative line. The bound in the per-order sum
        invariant (D19) for classes 1, 2, 5, 7 and 8; class 6 is bounded by the
        order's own value instead, since an unpaid order has no lines."""
        return -sum(ln.amount_paise for ln in self.lines if ln.amount_paise < 0)


@dataclass(frozen=True, slots=True)
class MatchResult:
    """Exact join outcome (D5 cut: order id equality only). Producer: H.
    Consumers: L (report), N (match rates)."""

    matched_order_ids: tuple[str, ...]
    unmatched_order_ids: tuple[str, ...]  # in the seller's export, absent from every settlement
    orphan_order_ids: tuple[str, ...]  # in a settlement, absent from the seller's export
    rates: MatchRates


# --------------------------------------------------------------------------- #
# Findings. Producer: lane J via make_finding(). Consumers: K, L, M, O.
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class RecomputationRow:
    """One line of the detail pane's recomputation block. The label may carry
    a percentage as text; the money is in ``amount_paise``."""

    label: str
    amount_paise: Paise | None
    note: str = ""


@dataclass(frozen=True, slots=True)
class Finding:
    """A deterministic detector result (D1, D23). No state yet, no prose."""

    error_class: ErrorClass
    order_id: str
    source_line_ids: tuple[str, ...]
    claimed_line_id: str | None  # null for absence-type findings (D19)
    amount_paise: Paise  # the discrepancy, positive
    mechanism: Mechanism
    basis: str  # deterministic explanation of what fired
    recomputation: tuple[RecomputationRow, ...] = ()
    unexplained_basis: UnexplainedBasis | None = None  # class 8 only
    event_date: date | None = None  # window start event (refund / return scan)
    category_id: str | None = None
    sku: str | None = None

    @property
    def finding_id(self) -> str:
        """The D19 dedup key: (order_id, class, claimed_line_id | null)."""
        return f"{self.order_id}|{int(self.error_class)}|{self.claimed_line_id or '-'}"


# --------------------------------------------------------------------------- #
# Assessment. Producer: lane K. Consumer: L.
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class EvidenceItem:
    requirement: str
    source: EvidenceSource
    status: EvidenceStatus
    source_line_ids: tuple[str, ...] = ()
    note: str = ""  # e.g. "permanence unknown" (step 5 degrade)


@dataclass(frozen=True, slots=True)
class EligibilityCheck:
    """A non-window rule check with a citation (step 1). Window arithmetic is
    its own step and is not an eligibility rule."""

    rule_id: str
    description: str
    passed: bool
    citation: Citation


@dataclass(frozen=True, slots=True)
class Deadline:
    """Filing-window arithmetic in calendar days against as_of (D18)."""

    mechanism: Mechanism
    status: WindowStatus
    window_days: int | None = None
    starts_on: date | None = None
    expires_on: date | None = None
    days_left: int | None = None
    citation: Citation | None = None


@dataclass(frozen=True, slots=True)
class Assessment:
    finding_id: str
    eligibility: tuple[EligibilityCheck, ...]
    evidence: tuple[EvidenceItem, ...]
    deadline: Deadline


# --------------------------------------------------------------------------- #
# Triage output. Producer: lane L. Consumers: G, M, N, O.
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class StateResult:
    finding_id: str
    state: State
    precedence_step: int  # 0, 1, 2, 3, 4, 5, 6 as in the design's ladder
    reason: str  # the named blocker, rule, basis, shown on screen
    rupee_line: RupeeLine
    blocker_kind: BlockerKind | None = None
    not_claimable_reason: NotClaimableReason | None = None


@dataclass(frozen=True, slots=True)
class Draft:
    """LLM output with placeholders in and substituted out (D2). Producer: M."""

    finding_id: str
    template_text: str  # what the model wrote: {{amt:<line_id>}} placeholders, no amounts
    rendered_text: str  # after deterministic substitution
    magnitude: str  # minor | moderate | major, bucketed deterministically
    model: str
    model_version: str
    placeholders: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class GateRecord:
    """What the human did (D8). Producer: O."""

    action: AuditAction
    audit_seq: int
    state_before: State
    artifact_path: str | None = None
    overridden: bool = False


@dataclass(frozen=True, slots=True)
class TriagedFinding:
    """One queue row: finding, assessment, state, optional draft and gate."""

    finding: Finding
    assessment: Assessment
    state: StateResult
    draft: Draft | None = None
    gate: GateRecord | None = None


@dataclass(frozen=True, slots=True)
class RupeeLines:
    """The seven-line partition (design doc, "Rupee partition"). The two sums
    are derived, never stored, so they cannot disagree with their parts."""

    claim_ready: Paise
    blocked: Paise
    not_claimable: Paise
    tax_review: Paise
    unexplained: Paise
    below_materiality: Paise
    not_claimable_rule: Paise = 0
    not_claimable_window_expired: Paise = 0
    not_claimable_evidence_unobtainable: Paise = 0
    claim_ready_count: int = 0
    blocked_count: int = 0
    not_claimable_count: int = 0
    tax_review_count: int = 0
    unexplained_count: int = 0
    below_materiality_rows: int = 0

    @property
    def identified(self) -> Paise:
        return self.claim_ready + self.blocked + self.not_claimable

    @property
    def total(self) -> Paise:
        return self.identified + self.tax_review + self.unexplained + self.below_materiality


@dataclass(frozen=True, slots=True)
class MatchRates:
    """Strict = matched / all orders; adjusted = matched / (all − class-6
    flagged). Quarantined orders stay in both denominators (D7). The bank leg
    contributes to neither (D6)."""

    total_orders: int
    matched: int
    class6_flagged: int
    quarantined_rows: int

    @property
    def strict(self) -> float:
        return self.matched / self.total_orders if self.total_orders else 0.0

    @property
    def adjusted(self) -> float:
        denom = self.total_orders - self.class6_flagged
        return self.matched / denom if denom > 0 else 0.0


@dataclass(frozen=True, slots=True)
class DispositionCounts:
    quarantine: int
    uncovered: int
    out_of_window: int
    config_error: int
    quarantine_reasons: tuple[QuarantinedRow, ...] = ()
    hint: str | None = None


@dataclass(frozen=True, slots=True)
class BankLegResult:
    """Reported as a demonstrated step, never in match rate (D6)."""

    payouts: int
    matched: int
    unmatched_settlement_ids: tuple[str, ...] = ()
    duplicate_credit_utrs: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class BatchReport:
    """The dashboard's JSON and the metrics harness's input. Producer: L.
    Consumers: G (render), N (score), O (serve). ``mode`` distinguishes the
    static export from the served path; everything above the gate must render
    identically on both (D16)."""

    batch_id: str
    marketplace: str
    as_of: date
    cycle_days: int
    coverage: CoverageWindow
    settlement_ids: tuple[str, ...]
    order_count: int
    rupee_lines: RupeeLines
    match_rates: MatchRates
    dispositions: DispositionCounts
    rate_card_coverage: CoverageDeclaration
    queue: tuple[TriagedFinding, ...]
    generated_by: str
    mode: str = "static"
    schema_version: int = 1
    bank_leg: BankLegResult | None = None
    audit_head_seq: int | None = None
    audit_head_hash: str | None = None


# --------------------------------------------------------------------------- #
# Generator manifest. Producer: lane B. Consumers: N (scoring), F (labels join).
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class SeededError:
    """Ground truth for one seeded discrepancy. Amount is what the detector
    should compute, within ±₹1 (₹-agreement, D10). ``line_ids`` are the lines
    the generator perturbed or omitted, for the disagreement listing."""

    scenario: Scenario
    order_id: str
    expected_class: ErrorClass | None
    expected_amount_paise: Paise | None
    line_ids: tuple[str, ...] = ()
    note: str = ""


@dataclass(frozen=True, slots=True)
class Manifest:
    batch_id: str
    seed: int
    as_of: date
    cycle_days: int
    coverage: CoverageWindow
    order_count: int
    categories: tuple[str, ...]
    seeded: tuple[SeededError, ...]
    files: dict[str, str] = field(default_factory=dict)  # role -> file name
    materiality_floor_paise: Paise = 1_000
    generator_version: str = ""


# --------------------------------------------------------------------------- #
# Ground truth for claimability. Producer: lane F (frozen). Consumer: N.
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class ClaimabilityLabel:
    """Hand-authored against cited policy text BEFORE any eligibility rule is
    coded (D12). Says what state a scenario must land in and why."""

    scenario: Scenario
    expected_state: State
    expected_precedence_step: int
    rationale: str
    citation: Citation
    expected_blocker_kind: BlockerKind | None = None
    expected_not_claimable_reason: NotClaimableReason | None = None


@dataclass(frozen=True, slots=True)
class HoldoutCase:
    """One adversarial case the generator never produces, in canonical form.
    Scored as its own published line, never merged into headline metrics."""

    case_id: str
    description: str
    folded: FoldedOrder
    profile: SellerProfile
    expected_class: ErrorClass | None
    expected_state: State | None
    expected_reason: str
    expected_amount_paise: Paise | None = None


# --------------------------------------------------------------------------- #
# Audit and claim pack. Producers: E, O. Consumer: verify (chain recompute).
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class AuditEntry:
    """D21. ``hash = H(canonical_json(entry − hash) + prev_hash)``. ``ts`` is an
    ISO-8601 string supplied by the caller (cli.py owns the clock)."""

    seq: int
    prev_hash: str
    hash: str
    ts: str
    as_of: date
    actor: str
    action: AuditAction
    exception_id: str | None
    state_before: State | None
    state_after: State | None
    amount_paise: Paise | None
    artifact_path: str | None


@dataclass(frozen=True, slots=True)
class ClaimPack:
    """Written to disk BEFORE its audit entry is appended (D8)."""

    exception_id: str
    path: str
    claim_text: str
    cited_rows_csv: str
    recomputation_csv: str
    state_before: State
    audit_seq: int
    overridden: bool = False
