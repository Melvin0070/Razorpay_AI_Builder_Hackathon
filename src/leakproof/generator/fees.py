"""The generator's encoding of the Amazon.in fee schedule and the statutory
withholding rates. Lane B's half of the two independent encodings (D12); the
detector side's half lives in ``ratecard/`` and this module never reads it.

Every number below was read from the source named beside it on the date
given. ``verified: false`` marks a figure that could only be read from a
secondary source; the report lists those.

Basis for every percentage and slab: the order's pre-tax principal
(``types.Order.principal_paise``), which is what ``types.RateRule`` bounds
its slabs on. The public page bands on "item price including shipping
charges", i.e. the GST-inclusive customer price; that difference is a
deliberate simplification shared with the seam, not an encoding of the
page. Quantity is fixed at one unit per order for the same reason: a unit
price and an order principal are then the same number, so neither encoding
has to decide which one a band applies to.

Referral (commission) fee
    Source: https://sell.amazon.in/fees-and-pricing/fee-schedule (read
    2026-09-04; not login-walled), section "Changes in existing fee
    categories", columns "Current Referral Fee" and "New Referral Fee
    (Effective 16th March)". The main page
    https://sell.amazon.in/fees-and-pricing (read 2026-09-04) shows only the
    16 March column and agrees with it for all three nodes. The page's June
    10, 2026 revision names only "Automotive - Tyres & Rims" and "Fans and
    Robotic Vacuums", so the three nodes here carry the 16 March 2026 tiers
    unchanged on any ``as_of`` from that date on. ``verified: true``.

    ``apparel`` → node "Apparel - Shirts":
        from 2026-03-16: 0.00% ≤ ₹1,000; 21.00% > ₹1,000.
        until 2026-03-15 ("Current" column, kept only to author a
        realistic wrong rate): 0% ≤ 300; 4.50% 300–500; 12.00% 500–1,000;
        21.00% > 1,000.
    ``home-kitchen`` → node "Kitchen - Cookware, Tableware & Dinnerware"
    (listed as "Cookware, Tableware & Dinnerware" under the group "Kitchen,
    Large & Small Appliances"):
        from 2026-03-16: 0.00% ≤ ₹1,000; 12.50% > ₹1,000.
        until 2026-03-15: 0% ≤ 300; 5.00% 300–500; 9.00% 500–1,000;
        12.50% > 1,000.
    ``electronics-accessories`` → node "Accessories - Electronics, PC and
    Wireless" under the group "Electronics (Camera, Mobile, PC, Wireless) &
    Accessories". The literal node name ``contract.CATEGORY_NODES`` pins,
    "Electronics Accessories", does not appear on either page on
    2026-09-04 (the only near match, "Car Electronics Accessories", is an
    automotive node); this is the node RS3 §1 describes. Recorded as an
    interface change request.
        from 2026-03-16: 0.00% ≤ ₹300; 5.00% 300–1,000; 17.00% > ₹1,000.
        until 2026-03-15: 0% ≤ 300; 17.00% 300–500; 15.50% 500–1,000;
        17.00% > 1,000.
    Bands are inclusive at the upper bound exactly as the page writes them
    ("<= 1,000", "> 1,000").

Closing fee (fixed, per unit), Easy Ship channel
    The design's seller is seller-fulfilled (SAFE-T covers Easy Ship,
    Self-Ship and Seller Flex); Easy Ship is the channel encoded here. The
    contract does not pin a channel; recorded as an interface change
    request, since the detector side must pick the same one.
    Source: the "Closing Fee for Easy ship/Easy ship prime" table, an image
    on both pages (https://m.media-amazon.com/images/G/31/amazonservices/
    Easy_ship_Closing_fee2026.jpg on the main page, "Effective from March
    16, 2026", and .../Closing_Fee_for_Easy_ship_Sept2026.png on the
    fee-schedule page with columns "Current Fee" and "Effective September
    7th, 2026"), both read 2026-09-04. ``verified: true``.
        2026-03-16 .. 2026-09-06: ₹1 (0–300); ₹22 (301–500); ₹45
        (501–1,000); ₹76 (above 1,000).
        from 2026-09-07: ₹2; ₹23; ₹48; ₹79 (the page's own "+₹1 up to
        ₹500, +₹3 above ₹500").
    No Easy Ship table is encoded before 2026-03-16.

GST on fees
    18%: https://sell.amazon.in/fees-and-pricing/fee-schedule footnote,
    "We will apply 18% (eighteen percent) GST to all fees displayed above",
    read 2026-09-04. ``verified: true``.

TCS, Section 52 CGST Act
    Notification 52/2018-Central Tax (20-09-2018): "a rate of half per
    cent. of the net value of intra-State taxable supplies"; Notification
    15/2024-Central Tax (10-07-2024): "for the words 'half per cent.', the
    figure and word '0.25 per cent.' shall be substituted", in force from
    publication. Both read as the PDFs linked from
    https://gstcouncil.gov.in/node/4059 and https://gstcouncil.gov.in/node/5015
    on 2026-09-04. ``verified: true`` for the CGST leg. The SGST leg mirrors
    it under the state Acts and the IGST leg (inter-State) is 0.5% from the
    same date, from a secondary source only:
    https://www.nyca.in/cbic-reduces-tcs-rate-from-1-to-0-5-for-e-commerce-operators-effective-july-10-2024/
    (2024-07-12). ``verified: false`` for SGST and IGST.
    Base: the order principal (the "net value of taxable supplies",
    excluding GST). Monthly netting of returns is not modelled: TCS is
    withheld on the sale and never adjusted on a refund.

TDS, Section 194-O Income-tax Act
    0.1% of the gross amount from 2024-10-01 (1% before). The primary,
    Gazette of India Finance (No. 2) Act 2024 at
    https://egazette.gov.in/WriteReadData/2024/256436.pdf, could not be
    opened (TLS certificate rejected by the fetch tool; the headless
    browser cannot render a PDF). Secondary sources:
    https://taxguru.in/income-tax/change-tds-rate-effective-01st-october-2024.html
    (2024-10-27) and
    https://www.terra-insight.com/insights/section-194o-tds-0-1-percent-current-rate-history-india/
    (2026-06-23). ``verified: false``.
    Base: the order principal, the same simplification as TCS; the ₹5 lakh
    individual/HUF threshold does not apply to a registered business seller
    and is not modelled.

Refund commission (India term, RS3 §5)
    The Help Hub pages are login-walled and the public forum post
    https://sellercentral.amazon.in/seller-forums/discussions/t/d18ac900-0473-44dc-911c-5038547ad53c
    (read 2026-09-04) names the fee and says it is based on item price
    without giving a figure. Encoded as 20% of the referral fee being
    reversed, from the only secondary figure found:
    https://swcybernetics.in/knowledge-base/amazon-seller-fees-india-complete-breakdown
    ("Refund admin fee: ₹50 or 20% of referral fee", 2026-05-15).
    ``verified: false``. No detector audits this amount (class 5 pairs
    events), so the figure only shapes realism.

Categories outside coverage
    Orders tagged ``books``, ``beauty``, ``toys`` or ``grocery`` are charged
    a flat 10% commission that encodes nothing: they exist so the
    UNCOVERED disposition has rows to land on.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Final

from leakproof.contract import CATEGORY_NODES, Paise, apply_bp

COVERED_CATEGORIES: Final[tuple[str, ...]] = ("electronics-accessories", "home-kitchen", "apparel")
UNCOVERED_CATEGORIES: Final[tuple[str, ...]] = ("books", "beauty", "toys", "grocery")

if set(COVERED_CATEGORIES) != set(CATEGORY_NODES):  # pragma: no cover - contract drift guard
    raise RuntimeError("generator categories drifted from contract.CATEGORY_NODES")

#: The node each identifier's tiers were read from, as the page names it.
SOURCE_NODES: Final[dict[str, str]] = {
    "electronics-accessories": "Accessories - Electronics, PC and Wireless",
    "home-kitchen": "Cookware, Tableware & Dinnerware",
    "apparel": "Apparel - Shirts",
}

#: (inclusive upper bound on the principal in paise, or None for open; basis points)
Tier = tuple[Paise | None, int]

REFERRAL_VALID_FROM: Final[date] = date(2026, 3, 16)

REFERRAL_TIERS: Final[dict[str, tuple[Tier, ...]]] = {
    "electronics-accessories": ((30_000, 0), (100_000, 500), (None, 1_700)),
    "home-kitchen": ((100_000, 0), (None, 1_250)),
    "apparel": ((100_000, 0), (None, 2_100)),
}

#: The page's "Current Referral Fee" column (in force until 2026-03-15). Never
#: used to compute a correct fee; only to author a realistic wrong one.
LEGACY_REFERRAL_TIERS: Final[dict[str, tuple[Tier, ...]]] = {
    "electronics-accessories": ((30_000, 0), (50_000, 1_700), (100_000, 1_550), (None, 1_700)),
    "home-kitchen": ((30_000, 0), (50_000, 500), (100_000, 900), (None, 1_250)),
    "apparel": ((30_000, 0), (50_000, 450), (100_000, 1_200), (None, 2_100)),
}

UNCOVERED_REFERRAL_BP: Final[int] = 1_000


@dataclass(frozen=True, slots=True)
class ClosingSchedule:
    valid_from: date
    valid_to: date | None
    bands: tuple[Tier, ...]  # (inclusive upper bound, fixed fee in paise)

    def covers(self, on: date) -> bool:
        return self.valid_from <= on and (self.valid_to is None or on <= self.valid_to)


CLOSING_SCHEDULES: Final[tuple[ClosingSchedule, ...]] = (
    ClosingSchedule(
        date(2026, 3, 16),
        date(2026, 9, 6),
        ((30_000, 100), (50_000, 2_200), (100_000, 4_500), (None, 7_600)),
    ),
    ClosingSchedule(
        date(2026, 9, 7),
        None,
        ((30_000, 200), (50_000, 2_300), (100_000, 4_800), (None, 7_900)),
    ),
)

FEE_GST_BP: Final[int] = 1_800

TCS_VALID_FROM: Final[date] = date(2024, 7, 10)
TCS_CGST_BP: Final[int] = 25
TCS_SGST_BP: Final[int] = 25
TCS_IGST_BP: Final[int] = 50
LEGACY_TCS_CGST_BP: Final[int] = 50
LEGACY_TCS_SGST_BP: Final[int] = 50
LEGACY_TCS_IGST_BP: Final[int] = 100

TDS_VALID_FROM: Final[date] = date(2024, 10, 1)
TDS_BP: Final[int] = 10
LEGACY_TDS_BP: Final[int] = 100

REFUND_COMMISSION_BP: Final[int] = 2_000

TCS_CGST_DESCRIPTION: Final[str] = "TCS-CGST"
TCS_SGST_DESCRIPTION: Final[str] = "TCS-SGST"
TCS_IGST_DESCRIPTION: Final[str] = "TCS-IGST"


def tier_value(tiers: tuple[Tier, ...], principal: Paise) -> int:
    """The value of the first tier whose inclusive upper bound holds the principal."""
    if principal < 0:
        raise ValueError(f"principal must be non-negative, got {principal}")
    for upper, value in tiers:
        if upper is None or principal <= upper:
            return value
    raise AssertionError("tier table must end with an open band")


def referral_bp(category_id: str, principal: Paise, on: date) -> int:
    if on < REFERRAL_VALID_FROM:
        raise ValueError(f"no referral schedule encoded before {REFERRAL_VALID_FROM}: {on}")
    tiers = REFERRAL_TIERS.get(category_id)
    if tiers is None:
        if category_id in UNCOVERED_CATEGORIES:
            return UNCOVERED_REFERRAL_BP
        raise ValueError(f"unknown category {category_id!r}")
    return tier_value(tiers, principal)


def legacy_referral_bp(category_id: str, principal: Paise) -> int:
    return tier_value(LEGACY_REFERRAL_TIERS[category_id], principal)


def commission_paise(category_id: str, principal: Paise, on: date) -> Paise:
    """Magnitude of the referral fee; the writer negates it."""
    return apply_bp(principal, referral_bp(category_id, principal, on))


def closing_schedule(on: date) -> ClosingSchedule:
    for schedule in CLOSING_SCHEDULES:
        if schedule.covers(on):
            return schedule
    raise ValueError(f"no Easy Ship closing-fee schedule encoded for {on}")


def closing_fee_paise(principal: Paise, on: date) -> Paise:
    return tier_value(closing_schedule(on).bands, principal)


def fee_gst_paise(fees: Paise) -> Paise:
    return apply_bp(fees, FEE_GST_BP)


def tcs_legs(principal: Paise, *, intra_state: bool, on: date) -> tuple[tuple[str, Paise], ...]:
    """The withheld-tax lines a sale carries: two legs intra-State, one inter-State."""
    if on >= TCS_VALID_FROM:
        cgst, sgst, igst = TCS_CGST_BP, TCS_SGST_BP, TCS_IGST_BP
    else:
        cgst, sgst, igst = LEGACY_TCS_CGST_BP, LEGACY_TCS_SGST_BP, LEGACY_TCS_IGST_BP
    if intra_state:
        return (
            (TCS_CGST_DESCRIPTION, apply_bp(principal, cgst)),
            (TCS_SGST_DESCRIPTION, apply_bp(principal, sgst)),
        )
    return ((TCS_IGST_DESCRIPTION, apply_bp(principal, igst)),)


def legacy_tcs_legs(principal: Paise, *, intra_state: bool) -> tuple[tuple[str, Paise], ...]:
    """The pre-2024-07-10 legs, used only to author a wrong withholding."""
    return tcs_legs(principal, intra_state=intra_state, on=TCS_VALID_FROM.replace(day=9))


def tds_paise(principal: Paise, on: date) -> Paise:
    return apply_bp(principal, TDS_BP if on >= TDS_VALID_FROM else LEGACY_TDS_BP)


def legacy_tds_paise(principal: Paise) -> Paise:
    return apply_bp(principal, LEGACY_TDS_BP)


def refund_commission_paise(commission: Paise) -> Paise:
    return apply_bp(commission, REFUND_COMMISSION_BP)


def schedule_label(as_of: date) -> str:
    """Which schedule was in force on ``as_of``; written into the manifest."""
    closing = closing_schedule(as_of)
    closing_to = closing.valid_to.isoformat() if closing.valid_to else "open"
    return (
        f"referral=sell.amazon.in 'New Referral Fee (Effective 16th March)' "
        f"[{REFERRAL_VALID_FROM.isoformat()}..open, June 10 revision not touching these nodes]; "
        f"closing=Easy Ship [{closing.valid_from.isoformat()}..{closing_to}]; "
        f"fee-gst={FEE_GST_BP}bp; tcs=0.5% [{TCS_VALID_FROM.isoformat()}..]; "
        f"tds=0.1% [{TDS_VALID_FROM.isoformat()}..]"
    )
