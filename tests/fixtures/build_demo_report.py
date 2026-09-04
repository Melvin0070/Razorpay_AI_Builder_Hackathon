"""Builds the committed demo ``BatchReport`` fixture.

The numbers reproduce the wireframe's metrics strip exactly (₹47,230 identified
= ₹19,400 + ₹21,600 + ₹6,230; ₹380 tax-review; ₹1,975 unexplained; ₹212 below
materiality over 18 rows; match rate 94.0% strict / 97.9% adjusted; 9 rows not
processed). The 20 queue rows are authored so every identity the real pipeline
is gated on holds here too. Where the hand-drawn wireframe is internally
inconsistent, the fixture follows the design doc:

* support-ticket mechanisms carry no filing window, so class 2 and class 6 rows
  show no deadline (the wireframe drew one on a closing-fee row);
* the not-claimable breakdown has three reasons (rule, window expired,
  evidence unobtainable), one per emitting precedence step;
* the class-7 row is BLOCKED but its rupees sit on the tax-review line, so the
  rupee-line ``blocked_count`` is 6 while the state chip says 7.

Regenerate with ``uv run python -m tests.fixtures.build_demo_report``. A test
asserts the committed JSON equals this builder's output.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from leakproof.contract import (
    AuditAction,
    BlockerKind,
    ErrorClass,
    EvidenceSource,
    EvidenceStatus,
    LineKind,
    Mechanism,
    NotClaimableReason,
    RupeeLine,
    State,
    UnexplainedBasis,
    WindowStatus,
    rupee_line_for,
)
from leakproof.serialize import dumps
from leakproof.types import (
    Assessment,
    BankLegResult,
    BatchReport,
    Citation,
    CoverageDeclaration,
    CoverageWindow,
    Deadline,
    DispositionCounts,
    Draft,
    EligibilityCheck,
    EvidenceItem,
    Finding,
    GateRecord,
    MatchRates,
    QuarantinedRow,
    RecomputationRow,
    RupeeLines,
    StateResult,
    TriagedFinding,
)

AS_OF = date(2026, 8, 28)
SAFE_T_WINDOW_DAYS = (
    60  # illustrative for the fixture; lane K encodes the real value with a citation
)

RATECARD_CITE = Citation(
    "ratecard v2026-03", "https://sell.amazon.in/fees-and-pricing", date(2026, 3, 1), True
)
SAFET_CITE = Citation(
    "SAFE-T policy (secondary source)",
    "https://sellercentral.amazon.in/help/hub/reference/G200850160",
    date(2026, 8, 20),
    False,
)
ATOZ_CITE = Citation(
    "A-to-z Guarantee exclusion",
    "https://sellercentral.amazon.in/help/hub/reference/G1781",
    date(2026, 8, 20),
    False,
)

SETTLEMENTS = ("S-88228", "S-88229", "S-88230", "S-88231")
FILES = (
    "settlement_2026-07-31.txt",
    "settlement_2026-08-07.txt",
    "settlement_2026-08-14.txt",
    "settlement_2026-08-21.txt",
)


def _deadline(mechanism: Mechanism, event: date | None, *, missing: bool = False) -> Deadline:
    if mechanism is not Mechanism.SAFE_T:
        return Deadline(mechanism, WindowStatus.NOT_APPLICABLE)
    if missing or event is None:
        return Deadline(
            mechanism,
            WindowStatus.START_DATE_MISSING,
            window_days=SAFE_T_WINDOW_DAYS,
            citation=SAFET_CITE,
        )
    expires = event + timedelta(days=SAFE_T_WINDOW_DAYS)
    status = WindowStatus.EXPIRED if expires < AS_OF else WindowStatus.OPEN
    return Deadline(
        mechanism,
        status,
        window_days=SAFE_T_WINDOW_DAYS,
        starts_on=event,
        expires_on=expires,
        days_left=(expires - AS_OF).days if status is WindowStatus.OPEN else None,
        citation=SAFET_CITE,
    )


def _evidence(*items: tuple[str, EvidenceSource, EvidenceStatus, str]) -> tuple[EvidenceItem, ...]:
    return tuple(EvidenceItem(req, src, st, note=note) for req, src, st, note in items)


OK = EvidenceStatus.SATISFIED
RD = EvidenceSource.REPORT_DERIVABLE
SS = EvidenceSource.SELLER_SUPPLIABLE

BASE_EVIDENCE = (
    ("Order + settlement row refs", RD, OK, ""),
    ("Rate card citation, dated", RD, OK, ""),
)


def _row(
    *,
    order_id: str,
    cls: ErrorClass,
    amount: int,
    state: State,
    step: int,
    reason: str,
    sku: str,
    category: str,
    file_ix: int,
    row: int,
    basis: str,
    recomp: tuple[tuple[str, int | None, str], ...],
    event: date | None = None,
    window_missing: bool = False,
    blocker: BlockerKind | None = None,
    nc_reason: NotClaimableReason | None = None,
    unexplained: UnexplainedBasis | None = None,
    eligibility: tuple[EligibilityCheck, ...] = (),
    evidence: tuple[EvidenceItem, ...] = (),
    claimed: bool = True,
    extra_sources: tuple[str, ...] = (),
    draft: Draft | None = None,
    gate: GateRecord | None = None,
) -> TriagedFinding:
    settlement_line = f"{FILES[file_ix]}:{row}"
    sources = (settlement_line, f"orders_aug.csv:{row % 140 + 2}", *extra_sources)
    mechanism = {
        ErrorClass.COMMISSION_OVERCHARGE: Mechanism.SAFE_T,
        ErrorClass.FIXED_FEE_ERROR: Mechanism.SUPPORT_TICKET,
        ErrorClass.REFUND_NO_FEE_REVERSAL: Mechanism.SAFE_T,
        ErrorClass.UNPAID_PAST_CYCLE: Mechanism.SUPPORT_TICKET,
        ErrorClass.TAX_MISMATCH: Mechanism.CA_REVIEW,
        ErrorClass.UNEXPLAINED_DEDUCTION: Mechanism.NONE,
    }[cls]
    finding = Finding(
        error_class=cls,
        order_id=order_id,
        source_line_ids=sources if cls is not ErrorClass.UNPAID_PAST_CYCLE else (sources[1],),
        claimed_line_id=settlement_line
        if claimed and cls is not ErrorClass.UNPAID_PAST_CYCLE
        else None,
        amount_paise=amount,
        mechanism=mechanism,
        basis=basis,
        recomputation=tuple(RecomputationRow(label, paise, note) for label, paise, note in recomp),
        unexplained_basis=unexplained,
        event_date=event,
        category_id=category,
        sku=sku,
    )
    assessment = Assessment(
        finding_id=finding.finding_id,
        eligibility=eligibility,
        evidence=evidence,
        deadline=_deadline(mechanism, event, missing=window_missing),
    )
    state_result = StateResult(
        finding_id=finding.finding_id,
        state=state,
        precedence_step=step,
        reason=reason,
        rupee_line=rupee_line_for(cls, state),
        blocker_kind=blocker,
        not_claimable_reason=nc_reason,
    )
    return TriagedFinding(
        finding=finding, assessment=assessment, state=state_result, draft=draft, gate=gate
    )


def _commission_recomp(
    principal: int, charged_bp: int, card_bp: int, delta: int
) -> tuple[tuple[str, int | None, str], ...]:
    return (
        (f"charged {charged_bp / 100:.1f}%", -(principal * charged_bp // 10_000), ""),
        (f"rate card {card_bp / 100:.1f}%", -(principal * card_bp // 10_000), ""),
        ("overcharge", delta, "GST on the fee delta follows the fee and is not claimed separately"),
    )


def build() -> BatchReport:
    c1, c2, c5, c6, c7, c8 = (
        ErrorClass.COMMISSION_OVERCHARGE,
        ErrorClass.FIXED_FEE_ERROR,
        ErrorClass.REFUND_NO_FEE_REVERSAL,
        ErrorClass.UNPAID_PAST_CYCLE,
        ErrorClass.TAX_MISMATCH,
        ErrorClass.UNEXPLAINED_DEDUCTION,
    )
    passed = lambda rid, desc, cite: EligibilityCheck(rid, desc, True, cite)  # noqa: E731
    failed = lambda rid, desc, cite: EligibilityCheck(rid, desc, False, cite)  # noqa: E731
    safe_t_ok = (
        passed("SAFET-01", "Not an A-to-z Guarantee refund", ATOZ_CITE),
        passed("SAFET-02", "Not a seller-issued refund", SAFET_CITE),
    )
    complete = _evidence(*BASE_EVIDENCE, ("Not an A-to-z or seller-issued refund", RD, OK, ""))

    approved_draft = Draft(
        finding_id="171-8823391-4471214|1|settlement_2026-08-21.txt:1204",
        template_text=(
            "Commission was charged at a rate above the published Cookware rate (rate card v2026-03). "
            "Recomputation attached; the affected unit is on settlement #S-88231. Requesting an "
            "adjustment of {{amt:settlement_2026-08-21.txt:1204}} to the referral fee."
        ),
        rendered_text=(
            "Commission was charged at a rate above the published Cookware rate (rate card v2026-03). "
            "Recomputation attached; the affected unit is on settlement #S-88231. Requesting an "
            "adjustment of ₹1,240.00 to the referral fee."
        ),
        magnitude="moderate",
        model="claude-sonnet-5",
        model_version="2026-06-01",
        placeholders=("settlement_2026-08-21.txt:1204",),
    )
    approved_gate = GateRecord(
        AuditAction.APPROVE,
        audit_seq=118,
        state_before=State.CLAIM_READY,
        artifact_path="claims/E-042/",
    )

    ready = [
        _row(
            order_id="171-8823391-4471214",
            cls=c1,
            amount=124_000,
            state=State.CLAIM_READY,
            step=6,
            reason="evidence complete",
            sku="KTCH-PAN-28",
            category="home-kitchen",
            file_ix=3,
            row=1204,
            basis="commission 16.0% charged vs rate card 12.0% (Cookware, ≤ ₹35,000)",
            recomp=_commission_recomp(3_100_000, 1_600, 1_200, 124_000),
            event=date(2026, 7, 4),
            eligibility=safe_t_ok,
            evidence=complete,
            extra_sources=("ratecard:v2026-03/home-kitchen/cookware",),
            draft=approved_draft,
            gate=approved_gate,
        ),
        _row(
            order_id="403-2261950-9014402",
            cls=c5,
            amount=498_000,
            state=State.CLAIM_READY,
            step=6,
            reason="evidence complete",
            sku="ELEC-CBL-11",
            category="electronics-accessories",
            file_ix=2,
            row=644,
            basis="refund posted 2026-07-06; no commission reversal in any later cycle",
            recomp=(
                ("commission on refunded units", -498_000, ""),
                ("reversal received", 0, ""),
                ("owed", 498_000, ""),
            ),
            event=date(2026, 7, 6),
            eligibility=safe_t_ok,
            evidence=complete,
        ),
        _row(
            order_id="171-5568301-7723019",
            cls=c1,
            amount=376_000,
            state=State.CLAIM_READY,
            step=6,
            reason="evidence complete",
            sku="APRL-JKT-04",
            category="apparel",
            file_ix=3,
            row=1377,
            basis="commission 20.0% charged vs rate card 12.0% (Apparel)",
            recomp=_commission_recomp(4_700_000, 2_000, 1_200, 376_000),
            event=date(2026, 7, 11),
            eligibility=safe_t_ok,
            evidence=complete,
        ),
        _row(
            order_id="408-1176243-0089207",
            cls=c5,
            amount=290_000,
            state=State.CLAIM_READY,
            step=6,
            reason="evidence complete",
            sku="KTCH-KNF-07",
            category="home-kitchen",
            file_ix=3,
            row=1502,
            basis="refund posted 2026-07-15; no commission reversal in any later cycle",
            recomp=(
                ("commission on refunded units", -290_000, ""),
                ("reversal received", 0, ""),
                ("owed", 290_000, ""),
            ),
            event=date(2026, 7, 15),
            eligibility=safe_t_ok,
            evidence=complete,
        ),
        _row(
            order_id="171-6620117-3348870",
            cls=c6,
            amount=315_000,
            state=State.CLAIM_READY,
            step=6,
            reason="evidence complete",
            sku="ELEC-HDP-02",
            category="electronics-accessories",
            file_ix=0,
            row=91,
            basis="delivered 2026-07-14; absent from all four cycles, > 2 cycles after delivery",
            recomp=(
                ("expected net payout", 315_000, ""),
                ("settled", 0, ""),
                ("owed", 315_000, ""),
            ),
            evidence=_evidence(
                ("Order + delivery confirmation", RD, OK, ""),
                ("Absence across cycles 21–24", RD, OK, ""),
            ),
            claimed=False,
        ),
        _row(
            order_id="171-3095574-1200256",
            cls=c2,
            amount=276_000,
            state=State.CLAIM_READY,
            step=6,
            reason="evidence complete",
            sku="APRL-SHO-19",
            category="apparel",
            file_ix=1,
            row=402,
            basis="closing fee ₹65 charged on 24 units priced in the ≤ ₹250 slab",
            recomp=(
                ("charged", -156_000, "₹65 × 24"),
                ("rate card slab", 120_000, "₹50 × 24"),
                ("overcharge", 276_000, ""),
            ),
            evidence=_evidence(*BASE_EVIDENCE),
        ),
        _row(
            order_id="171-0041877-2280091",
            cls=c2,
            amount=61_000,
            state=State.CLAIM_READY,
            step=6,
            reason="evidence complete",
            sku="KTCH-JAR-12",
            category="home-kitchen",
            file_ix=3,
            row=1261,
            basis="closing fee charged from the wrong slab",
            recomp=(
                ("charged", -100_000, ""),
                ("rate card slab", -39_000, ""),
                ("overcharge", 61_000, ""),
            ),
            evidence=_evidence(*BASE_EVIDENCE),
        ),
    ]

    blocked = [
        _row(
            order_id="171-9088412-5560331",
            cls=c1,
            amount=460_000,
            state=State.BLOCKED,
            step=5,
            reason="seller-action — GST tax invoice pending",
            sku="ELEC-SPK-09",
            category="electronics-accessories",
            file_ix=3,
            row=1188,
            basis="commission 15.0% charged vs rate card 12.0%",
            recomp=_commission_recomp(15_333_300, 1_500, 1_200, 460_000),
            event=date(2026, 8, 20),
            blocker=BlockerKind.SELLER_ACTION,
            eligibility=safe_t_ok,
            evidence=_evidence(
                *BASE_EVIDENCE,
                ("GST tax invoice", SS, EvidenceStatus.PENDING, "requested from seller"),
            ),
        ),
        _row(
            order_id="403-1150422-8817702",
            cls=c5,
            amount=432_000,
            state=State.BLOCKED,
            step=5,
            reason="timing — awaiting settlement cycle 3",
            sku="KTCH-MIX-03",
            category="home-kitchen",
            file_ix=3,
            row=1420,
            basis="refund posted 2026-08-24; less than one full cycle before batch max settlement date",
            recomp=(
                ("commission on refunded units", -432_000, ""),
                ("reversal received", 0, "cycle 3 not yet settled"),
                ("owed if unreversed", 432_000, ""),
            ),
            event=date(2026, 8, 24),
            blocker=BlockerKind.TIMING,
            eligibility=safe_t_ok,
            evidence=_evidence(
                *BASE_EVIDENCE,
                (
                    "Reversal absent after one full cycle",
                    RD,
                    EvidenceStatus.PENDING,
                    "awaiting cycle 3",
                ),
            ),
        ),
        _row(
            order_id="408-7741009-2036611",
            cls=c5,
            amount=215_000,
            state=State.BLOCKED,
            step=5,
            reason="timing — awaiting settlement cycle 3",
            sku="APRL-TSH-31",
            category="apparel",
            file_ix=3,
            row=1466,
            basis="refund posted 2026-08-26; less than one full cycle before batch max settlement date",
            recomp=(
                ("commission on refunded units", -215_000, ""),
                ("reversal received", 0, ""),
                ("owed if unreversed", 215_000, ""),
            ),
            event=date(2026, 8, 26),
            blocker=BlockerKind.TIMING,
            eligibility=safe_t_ok,
            evidence=_evidence(
                *BASE_EVIDENCE,
                (
                    "Reversal absent after one full cycle",
                    RD,
                    EvidenceStatus.PENDING,
                    "awaiting cycle 3",
                ),
            ),
        ),
        _row(
            order_id="171-7720931-4419233",
            cls=c6,
            amount=518_000,
            state=State.BLOCKED,
            step=5,
            reason="timing — awaiting settlement cycle 2",
            sku="ELEC-CAM-14",
            category="electronics-accessories",
            file_ix=0,
            row=37,
            basis="delivered 2026-08-13; absent from cycles since, threshold of 2 cycles not yet reached",
            recomp=(
                ("expected net payout", 518_000, ""),
                ("settled", 0, ""),
                ("owed if unpaid", 518_000, ""),
            ),
            blocker=BlockerKind.TIMING,
            evidence=_evidence(
                ("Order + delivery confirmation", RD, OK, ""),
                ("Absence > 2 cycles", RD, EvidenceStatus.PENDING, "1 cycle so far"),
            ),
            claimed=False,
        ),
        _row(
            order_id="171-4480276-6671920",
            cls=c6,
            amount=390_000,
            state=State.BLOCKED,
            step=5,
            reason="timing — awaiting settlement cycle 2",
            sku="KTCH-PAN-30",
            category="home-kitchen",
            file_ix=0,
            row=58,
            basis="delivered 2026-08-15; threshold of 2 cycles not yet reached",
            recomp=(
                ("expected net payout", 390_000, ""),
                ("settled", 0, ""),
                ("owed if unpaid", 390_000, ""),
            ),
            blocker=BlockerKind.TIMING,
            evidence=_evidence(
                ("Order + delivery confirmation", RD, OK, ""),
                ("Absence > 2 cycles", RD, EvidenceStatus.PENDING, "1 cycle so far"),
            ),
            claimed=False,
        ),
        _row(
            order_id="171-2214590-9902118",
            cls=c1,
            amount=145_000,
            state=State.BLOCKED,
            step=3,
            reason="timing — window start date missing",
            sku="APRL-DRS-22",
            category="apparel",
            file_ix=2,
            row=713,
            basis="commission 15.0% charged vs rate card 12.0%; no refund or return-scan date on any line",
            recomp=_commission_recomp(4_833_300, 1_500, 1_200, 145_000),
            window_missing=True,
            blocker=BlockerKind.TIMING,
            eligibility=safe_t_ok,
            evidence=complete,
        ),
        _row(
            order_id="171-4362204-1188008",
            cls=c7,
            amount=38_000,
            state=State.BLOCKED,
            step=0,
            reason="professional-review — CA review",
            sku="ELEC-CHG-05",
            category="electronics-accessories",
            file_ix=3,
            row=1299,
            basis="TCS withheld ₹1,380 vs 1% recompute ₹1,000 on taxable value ₹100,000",
            recomp=(
                ("TCS withheld", -138_000, ""),
                ("Section 52 recompute at 1%", -100_000, ""),
                ("difference", 38_000, ""),
            ),
            blocker=BlockerKind.PROFESSIONAL_REVIEW,
            evidence=_evidence(
                ("Settlement TCS lines", RD, OK, ""),
                ("GSTR-2A / 8A reconciliation", SS, EvidenceStatus.PENDING, "CA export"),
            ),
        ),
    ]

    unexplained = [
        _row(
            order_id="171-9013380-4451127",
            cls=c8,
            amount=134_000,
            state=State.UNEXPLAINED,
            step=0,
            reason="basis: code-unseen — MISC-ADJ-7 not in fee vocabulary",
            sku="KTCH-BLD-01",
            category="home-kitchen",
            file_ix=3,
            row=1391,
            basis="amount-description 'MISC-ADJ-7' under other-transaction is not in the vocabulary",
            recomp=(("deduction", -134_000, "MISC-ADJ-7"),),
            unexplained=UnexplainedBasis.CODE_UNSEEN,
            evidence=_evidence(("Settlement row", RD, OK, "")),
        ),
        _row(
            order_id="408-0027741-6538800",
            cls=c8,
            amount=63_500,
            state=State.UNEXPLAINED,
            step=0,
            reason="basis: code-known-no-rule — TechnologyFee has no rate-card rule",
            sku="ELEC-CBL-12",
            category="electronics-accessories",
            file_ix=2,
            row=690,
            basis="TechnologyFee is in the vocabulary; the rate card declares no rule and no acknowledgement for it",
            recomp=(("deduction", -63_500, "TechnologyFee"),),
            unexplained=UnexplainedBasis.CODE_KNOWN_NO_RULE,
            evidence=_evidence(("Settlement row", RD, OK, "")),
        ),
    ]

    not_claimable = [
        _row(
            order_id="408-5510028-3170455",
            cls=c5,
            amount=110_000,
            state=State.NOT_CLAIMABLE,
            step=2,
            reason="window expired 15 Aug — SAFE-T, 13 days ago",
            sku="APRL-JNS-08",
            category="apparel",
            file_ix=0,
            row=112,
            basis="refund posted 2026-06-16; no commission reversal in any later cycle",
            recomp=(
                ("commission on refunded units", -110_000, ""),
                ("reversal received", 0, ""),
                ("owed", 110_000, ""),
            ),
            event=date(2026, 6, 16),
            nc_reason=NotClaimableReason.WINDOW_EXPIRED,
            eligibility=safe_t_ok,
            evidence=complete,
        ),
        _row(
            order_id="171-3380044-2216065",
            cls=c1,
            amount=121_000,
            state=State.NOT_CLAIMABLE,
            step=2,
            reason="window expired 21 Aug — SAFE-T, 7 days ago",
            sku="KTCH-PAN-19",
            category="home-kitchen",
            file_ix=0,
            row=140,
            basis="commission 15.0% charged vs rate card 12.0%",
            recomp=_commission_recomp(4_033_300, 1_500, 1_200, 121_000),
            event=date(2026, 6, 22),
            nc_reason=NotClaimableReason.WINDOW_EXPIRED,
            eligibility=safe_t_ok,
            evidence=complete,
        ),
        _row(
            order_id="403-6690123-7208814",
            cls=c5,
            amount=103_000,
            state=State.NOT_CLAIMABLE,
            step=1,
            reason="excluded by rule — A-to-z Guarantee refund (SAFET-01)",
            sku="ELEC-EAR-21",
            category="electronics-accessories",
            file_ix=1,
            row=455,
            basis="A-to-z Guarantee refund posted 2026-08-01; no commission reversal since",
            recomp=(
                ("commission on refunded units", -103_000, ""),
                ("reversal received", 0, ""),
                ("owed", 103_000, ""),
            ),
            event=date(2026, 8, 1),
            nc_reason=NotClaimableReason.RULE,
            eligibility=(
                failed("SAFET-01", "Not an A-to-z Guarantee refund", ATOZ_CITE),
                passed("SAFET-02", "Not a seller-issued refund", SAFET_CITE),
            ),
            evidence=complete,
        ),
        _row(
            order_id="171-5560987-0110008",
            cls=c1,
            amount=289_000,
            state=State.NOT_CLAIMABLE,
            step=4,
            reason="evidence unobtainable — GST tax invoice, seller not GST-registered",
            sku="APRL-SAR-02",
            category="apparel",
            file_ix=2,
            row=735,
            basis="commission 15.0% charged vs rate card 12.0%",
            recomp=_commission_recomp(9_633_300, 1_500, 1_200, 289_000),
            event=date(2026, 8, 3),
            nc_reason=NotClaimableReason.EVIDENCE_UNOBTAINABLE,
            eligibility=safe_t_ok,
            evidence=_evidence(
                *BASE_EVIDENCE,
                (
                    "GST tax invoice",
                    EvidenceSource.UNOBTAINABLE,
                    EvidenceStatus.MISSING,
                    "seller_profile.gst_registered = false",
                ),
            ),
        ),
    ]

    def sort_key(item: TriagedFinding):
        from leakproof.contract import STATE_ORDER

        expires = item.assessment.deadline.expires_on
        return (
            STATE_ORDER.index(item.state.state),
            expires is None,
            expires or date.min,
            -item.finding.amount_paise,
        )

    queue = tuple(sorted(ready + blocked + unexplained + not_claimable, key=sort_key))

    lines = RupeeLines(
        claim_ready=1_940_000,
        blocked=2_160_000,
        not_claimable=623_000,
        tax_review=38_000,
        unexplained=197_500,
        below_materiality=21_200,
        not_claimable_rule=103_000,
        not_claimable_window_expired=231_000,
        not_claimable_evidence_unobtainable=289_000,
        claim_ready_count=7,
        blocked_count=6,
        not_claimable_count=4,
        tax_review_count=1,
        unexplained_count=2,
        below_materiality_rows=18,
    )
    for line in RupeeLine:
        if line is RupeeLine.BELOW_MATERIALITY:
            continue
        total = sum(i.finding.amount_paise for i in queue if i.state.rupee_line is line)
        stored = {
            RupeeLine.CLAIM_READY: lines.claim_ready,
            RupeeLine.BLOCKED: lines.blocked,
            RupeeLine.NOT_CLAIMABLE: lines.not_claimable,
            RupeeLine.TAX_REVIEW: lines.tax_review,
            RupeeLine.UNEXPLAINED: lines.unexplained,
        }[line]
        assert total == stored, (line, total, stored)

    return BatchReport(
        batch_id="2026-08-W3",
        marketplace="amazon-in",
        as_of=AS_OF,
        cycle_days=7,
        coverage=CoverageWindow(date(2026, 7, 10), date(2026, 8, 21)),
        settlement_ids=SETTLEMENTS,
        order_count=150,
        rupee_lines=lines,
        match_rates=MatchRates(total_orders=150, matched=141, class6_flagged=6, quarantined_rows=3),
        dispositions=DispositionCounts(
            quarantine=3,
            uncovered=4,
            out_of_window=2,
            config_error=0,
            quarantine_reasons=(
                QuarantinedRow("settlement_2026-08-14.txt:812", "amount not numeric: '1,240.00'"),
                QuarantinedRow(
                    "settlement_2026-08-14.txt:813", "expected 24 tab-separated columns, found 23"
                ),
                QuarantinedRow("orders_aug.csv:97", "delivery_date before order_date"),
            ),
        ),
        rate_card_coverage=CoverageDeclaration(
            categories=("electronics-accessories", "home-kitchen", "apparel"),
            valid_from=date(2026, 3, 1),
            valid_to=None,
            audited_kinds=(
                LineKind.COMMISSION,
                LineKind.FIXED_CLOSING_FEE,
                LineKind.REFUND_ADMIN_FEE,
                LineKind.FEE_TAX,
                LineKind.TCS,
                LineKind.TDS,
            ),
            acknowledged_kinds=(
                LineKind.SHIPPING_FEE,
                LineKind.PROMOTION,
                LineKind.RESERVE,
                LineKind.SAFET_REIMBURSEMENT,
            ),
        ),
        queue=queue,
        generated_by="tests/fixtures/build_demo_report.py (hand-authored fixture, not pipeline output)",
        mode="static",
        bank_leg=BankLegResult(payouts=4, matched=4),
        audit_head_seq=118,
        audit_head_hash="a41c9f2e7b0d4c6e8a1f3b5d7c9e0a2b4d6f8a0c2e4b6d8f0a1c3e5b7d9f1a3c",
    )


def main() -> None:
    out = Path(__file__).with_name("batch_report.demo.json")
    out.write_text(dumps(build()), encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
