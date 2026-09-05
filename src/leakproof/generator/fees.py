"""The generator's encoding of the Amazon.in fee schedule and the statutory
withholding rates. Lane B's half of the two independent encodings (D12); the
detector side's half lives in ``ratecard/`` and this module never reads it.

Every number below was read from the source named beside it on the date
given. ``verified: true`` means the primary page was read directly on that
date; ``verified: false`` marks a figure that could only be read from a
secondary source, or that the previous run of this lane read and this run
could not re-read. The lane report lists every ``verified: false`` figure.

Basis of every band and percentage (the seam decision of 2026-09-05, which
the corpus encodes the same way):

* referral (commission): the band key is the **unit item price**,
  ``Order.principal_paise ÷ quantity``, and the fee is ``quantity ×`` the
  per-unit fee at that band. Shipping and gift wrap charged to the buyer
  are not commission-bearing.
* fixed closing fee: the band key is the **unit item price including the
  shipping and gift wrap the buyer pays**, the fee page's own wording
  ("Item price including shipping charges"), i.e.
  ``(Principal + Shipping + GiftWrap) ÷ quantity`` over the settlement's
  ItemPrice lines, and the fee is ``quantity ×`` the per-unit fee at that
  band. The generator charges shipping and gift wrap per unit, so that
  division is exact.
* TCS and TDS: the order principal (item value before GST, excluding
  shipping and gift wrap). Monthly netting of returns is not modelled: both
  are withheld on the sale and never adjusted on a refund.
* every percentage goes through ``contract.apply_bp``; fixed fees are paise.

The page bands on the GST-inclusive customer price; keying on the pre-tax
principal is a deliberate simplification shared with the seam, not an
encoding of the page.

Referral (commission) fee
    Source: https://sell.amazon.in/fees-and-pricing/fee-schedule, read
    2026-09-05 (public, not login-walled), the referral-fee table, one row
    per fee-category node. The page's June 10, 2026 revision names only
    "Automotive - Tyres & Rims" and "Fans and Robotic Vacuums" ("Until June
    9, 2026" / "From June 10, 2026" rows), so the three nodes carry the
    16 March 2026 tiers unchanged on any ``as_of`` from that date on.
    ``verified: true``.

    ``apparel`` → node "Apparel - Shirts":
        0.00% for item price <= 1,000; 21.00% for item price > 1,000.
    ``home-kitchen`` → node "Kitchen - Cookware, Tableware & Dinnerware"
    (the referral table lists it as "Cookware, Tableware & Dinnerware" under
    the group "Kitchen, Large & Small Appliances"; the closing-fee group
    lists carry the full name):
        0.00% for item price <= 1,000; 12.50% for item price > 1,000.
    ``electronics-accessories`` → node "Accessories - Electronics, PC and
    Wireless":
        0.00% <= 300; 5.00% > 300 and <= 1,000; 17.00% > 1,000.
    Bands are inclusive at the upper bound exactly as the page writes them.

    The pre-16-March tiers below were read by the previous run of this lane
    on 2026-09-04 from the page's then "Current Referral Fee" column, which
    the page no longer shows on 2026-09-05. ``verified: false``. They are
    never used to compute a correct fee, only to author a realistic
    stale-rate overcharge:
        apparel: 0% <= 300; 4.50% 300–500; 12.00% 500–1,000; 21.00% > 1,000
        home-kitchen: 0% <= 300; 5.00% 300–500; 9.00% 500–1,000; 12.50% > 1,000
        electronics-accessories: 0% <= 300; 17.00% 300–500; 15.50% 500–1,000;
        17.00% > 1,000

Closing fee (fixed, per unit), Fulfilment Centre channel
    Amazon prices closing fees per fulfilment channel and the settlement
    line does not name one, so both encodings pin the same channel: the
    Fulfilment Centre table ("Closing Fee for Fulfilment center (excluding
    Seller Flex)"), the integrator's seam decision of 2026-09-05. The
    settlement rows carry ``fulfillment-id`` AFN to match.
    Sources, read 2026-09-05: the table image
    https://m.media-amazon.com/images/G/31/amazonservices/Closing_fee_for_fullfilment_Sept2026V2.png
    on https://sell.amazon.in/fees-and-pricing/fee-schedule (columns
    "Current Fee" and "Effective September 7th, 2026"), cross-checked against
    https://m.media-amazon.com/images/G/31/amazonservices/FC_Closing_fee2026.jpg
    on https://sell.amazon.in/fees-and-pricing ("Effective from March 16,
    2026", identical to the "Current Fee" column), and the group membership
    lists under the fee-schedule page's closing-fee legend. ``verified: true``.
    Bands on "Item price including shipping charges", rupees: 0–300,
    301–500, 501–1,000, above 1,000.
        2026-03-16 .. 2026-09-06:
          standard (Group # for 0–300, Group ## for 301–500; both lists name
          "Apparel - Shirts" and "Kitchen - Cookware, Tableware &
          Dinnerware"): ₹26, ₹22, ₹27, ₹52.
          select (Group A for 0–300, Group C for 301–500; both lists name
          "Accessories - Electronics, PC and Wireless"): ₹20, ₹18, ₹27, ₹52.
        from 2026-09-07: standard ₹27, ₹23, ₹30, ₹55; select ₹21, ₹19, ₹30,
          ₹55.
        The above-1,000 "₹72*" (₹75 from September) applies only to the
        listed select categories (Chimneys, Refrigerators, Major Appliances –
        Other Products, Home Entertainment – Other products); none of the
        three nodes is among them. Group B (₹13) and Group D (₹14) list none
        of the three nodes either.
    Uncovered categories are charged the standard-group fee. That is not an
    encoding of the page; those rows exist only for the UNCOVERED disposition.

GST on fees
    18%: https://sell.amazon.in/fees-and-pricing/fee-schedule footnote, "We
    will apply 18% (eighteen percent) GST to all fees displayed above", read
    2026-09-05. ``verified: true``. Written on the referral fee, the closing
    fee and the shipping fee; the gift-wrap chargeback (a pass-through) and
    the technology fee (the class-8 known-code case) are written without it.

TCS, Section 52 CGST Act
    Notification 52/2018-Central Tax (20-09-2018): "a rate of half per
    cent. of the net value of intra-State taxable supplies"; Notification
    15/2024-Central Tax (10-07-2024): "for the words 'half per cent.', the
    figure and word '0.25 per cent.' shall be substituted", in force from
    publication. Both read as the PDFs linked from
    https://gstcouncil.gov.in/node/4059 and https://gstcouncil.gov.in/node/5015
    (previous run, 2026-09-04; the pages re-read 2026-09-05). ``verified:
    true`` for the CGST leg. The SGST leg mirrors it under the state Acts
    and the IGST leg (inter-State) is 0.5% from the same date, from a
    secondary source only:
    https://www.nyca.in/cbic-reduces-tcs-rate-from-1-to-0-5-for-e-commerce-operators-effective-july-10-2024/
    (2024-07-12). ``verified: false`` for SGST and IGST.

TDS, Section 194-O Income-tax Act
    0.1% of the gross amount from 2024-10-01 (1% before): Finance (No. 2)
    Act, 2024, section 61 ("for the words 'one per cent.', the figures and
    word '0.1 per cent.' shall be substituted with effect from the 1st day
    of October, 2024"), in the Gazette of India at
    https://egazette.gov.in/WriteReadData/2024/256436.pdf (page 43), read
    2026-09-05. ``verified: true``. The ₹5 lakh individual/HUF threshold does not apply
    to a registered business seller and is not modelled.

Refund commission (India term, RS3 §5)
    The Help Hub pages are login-walled and the public forum post
    https://sellercentral.amazon.in/seller-forums/discussions/t/d18ac900-0473-44dc-911c-5038547ad53c
    (read 2026-09-04 by the previous run) names the fee and says it is based
    on item price without giving a figure. Encoded as 20% of the referral
    fee being reversed, from the only secondary figure found:
    https://swcybernetics.in/knowledge-base/amazon-seller-fees-india-complete-breakdown
    ("Refund admin fee: ₹50 or 20% of referral fee", 2026-05-15).
    ``verified: false``. No detector audits this amount (class 5 pairs
    events), so the figure only shapes realism.

Categories outside coverage
    Orders tagged ``books``, ``beauty``, ``toys`` or ``grocery`` are charged
    a flat 10% commission that encodes nothing: they exist so the UNCOVERED
    disposition has rows to land on.
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

#: (inclusive upper bound on the band key in paise, or None for open; value)
Tier = tuple[Paise | None, int]

REFERRAL_VALID_FROM: Final[date] = date(2026, 3, 16)

#: Keyed on the unit item price.
REFERRAL_TIERS: Final[dict[str, tuple[Tier, ...]]] = {
    "electronics-accessories": ((30_000, 0), (100_000, 500), (None, 1_700)),
    "home-kitchen": ((100_000, 0), (None, 1_250)),
    "apparel": ((100_000, 0), (None, 2_100)),
}

#: The pre-2026-03-16 tiers. Never used to compute a correct fee; only to
#: author a realistic wrong one.
LEGACY_REFERRAL_TIERS: Final[dict[str, tuple[Tier, ...]]] = {
    "electronics-accessories": ((30_000, 0), (50_000, 1_700), (100_000, 1_550), (None, 1_700)),
    "home-kitchen": ((30_000, 0), (50_000, 500), (100_000, 900), (None, 1_250)),
    "apparel": ((30_000, 0), (50_000, 450), (100_000, 1_200), (None, 2_100)),
}

UNCOVERED_REFERRAL_BP: Final[int] = 1_000

#: Inclusive upper bounds of the closing-fee bands on the per-unit key; the
#: fourth band is open.
CLOSING_BAND_UPPER: Final[tuple[Paise, ...]] = (30_000, 50_000, 100_000)
STANDARD_GROUP: Final[str] = "standard"
SELECT_GROUP: Final[str] = "select"
CLOSING_GROUP: Final[dict[str, str]] = {
    "electronics-accessories": SELECT_GROUP,
    "home-kitchen": STANDARD_GROUP,
    "apparel": STANDARD_GROUP,
}


@dataclass(frozen=True, slots=True)
class ClosingSchedule:
    valid_from: date
    valid_to: date | None
    fees: dict[str, tuple[Paise, Paise, Paise, Paise]]  # group -> fee per band

    def covers(self, on: date) -> bool:
        return self.valid_from <= on and (self.valid_to is None or on <= self.valid_to)


CLOSING_SCHEDULES: Final[tuple[ClosingSchedule, ...]] = (
    ClosingSchedule(
        date(2026, 3, 16),
        date(2026, 9, 6),
        {
            STANDARD_GROUP: (2_600, 2_200, 2_700, 5_200),
            SELECT_GROUP: (2_000, 1_800, 2_700, 5_200),
        },
    ),
    ClosingSchedule(
        date(2026, 9, 7),
        None,
        {
            STANDARD_GROUP: (2_700, 2_300, 3_000, 5_500),
            SELECT_GROUP: (2_100, 1_900, 3_000, 5_500),
        },
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


def is_known_category(category_id: str) -> bool:
    return category_id in REFERRAL_TIERS or category_id in UNCOVERED_CATEGORIES


def per_unit(total: Paise, quantity: int) -> Paise:
    """``total ÷ quantity``, which the generator keeps exact by charging every
    per-unit amount times the quantity."""
    if quantity < 1:
        raise ValueError(f"quantity must be positive, got {quantity}")
    unit, remainder = divmod(total, quantity)
    if remainder:
        raise ValueError(f"{total} paise is not a whole number of paise per unit over {quantity}")
    return unit


def tier_value(tiers: tuple[Tier, ...], key: Paise) -> int:
    """The value of the first tier whose inclusive upper bound holds the key."""
    if key < 0:
        raise ValueError(f"band key must be non-negative, got {key}")
    for upper, value in tiers:
        if upper is None or key <= upper:
            return value
    raise AssertionError("tier table must end with an open band")


# --------------------------------------------------------------------------- #
# Referral fee
# --------------------------------------------------------------------------- #


def referral_bp(category_id: str, unit_price: Paise, on: date) -> int:
    if on < REFERRAL_VALID_FROM:
        raise ValueError(f"no referral schedule encoded before {REFERRAL_VALID_FROM}: {on}")
    tiers = REFERRAL_TIERS.get(category_id)
    if tiers is None:
        if category_id in UNCOVERED_CATEGORIES:
            return UNCOVERED_REFERRAL_BP
        raise ValueError(f"unknown category {category_id!r}")
    return tier_value(tiers, unit_price)


def legacy_referral_bp(category_id: str, unit_price: Paise) -> int:
    return tier_value(LEGACY_REFERRAL_TIERS[category_id], unit_price)


def commission_at_bp(unit_price: Paise, quantity: int, bp: int) -> Paise:
    """Magnitude of a referral fee charged per unit at ``bp``; the writer negates it."""
    return quantity * apply_bp(unit_price, bp)


def commission_paise(category_id: str, unit_price: Paise, quantity: int, on: date) -> Paise:
    """Magnitude of the correct referral fee for ``quantity`` units at ``unit_price``."""
    return commission_at_bp(unit_price, quantity, referral_bp(category_id, unit_price, on))


# --------------------------------------------------------------------------- #
# Closing fee
# --------------------------------------------------------------------------- #


def closing_group(category_id: str) -> str:
    group = CLOSING_GROUP.get(category_id)
    if group is not None:
        return group
    if category_id in UNCOVERED_CATEGORIES:
        return STANDARD_GROUP
    raise ValueError(f"unknown category {category_id!r}")


def closing_schedule(on: date) -> ClosingSchedule:
    for schedule in CLOSING_SCHEDULES:
        if schedule.covers(on):
            return schedule
    raise ValueError(f"no Fulfilment Centre closing-fee schedule encoded for {on}")


def closing_band(key: Paise) -> int:
    """Index of the band holding a per-unit key; bounds are inclusive at the top."""
    if key < 0:
        raise ValueError(f"band key must be non-negative, got {key}")
    for index, upper in enumerate(CLOSING_BAND_UPPER):
        if key <= upper:
            return index
    return len(CLOSING_BAND_UPPER)


def closing_band_fees(category_id: str, on: date) -> tuple[Paise, Paise, Paise, Paise]:
    """Per-unit fee of every band for a category on a date, lowest band first."""
    return closing_schedule(on).fees[closing_group(category_id)]


def closing_key(principal: Paise, shipping: Paise, gift_wrap: Paise, quantity: int) -> Paise:
    """The per-unit item price including what the buyer paid for shipping and
    gift wrap: the closing-fee band key."""
    return per_unit(principal + shipping + gift_wrap, quantity)


def closing_fee_per_unit(category_id: str, key: Paise, on: date) -> Paise:
    return closing_band_fees(category_id, on)[closing_band(key)]


def closing_fee_paise(category_id: str, key: Paise, quantity: int, on: date) -> Paise:
    """Magnitude of the correct closing fee for ``quantity`` units whose per-unit
    key is ``key``; the writer negates it."""
    return quantity * closing_fee_per_unit(category_id, key, on)


# --------------------------------------------------------------------------- #
# GST on fees, withholding, refund commission
# --------------------------------------------------------------------------- #


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
    """Which schedule was in force on ``as_of`` and on what basis; written into
    the manifest's ``generator_version``."""
    closing = closing_schedule(as_of)
    closing_to = closing.valid_to.isoformat() if closing.valid_to else "open"
    return (
        "referral=sell.amazon.in fee-schedule tiers effective 2026-03-16 "
        f"[{REFERRAL_VALID_FROM.isoformat()}..open; June 10 revision does not touch these nodes], "
        "basis=unit item price (principal / quantity), fee per unit; "
        f"closing=Fulfilment Centre channel [{closing.valid_from.isoformat()}..{closing_to}], "
        "basis=(principal + shipping + gift wrap) / quantity, fee per unit; "
        f"fee-gst={FEE_GST_BP}bp; tcs=0.5% of principal [{TCS_VALID_FROM.isoformat()}..]; "
        f"tds=0.1% of principal [{TDS_VALID_FROM.isoformat()}..]"
    )
