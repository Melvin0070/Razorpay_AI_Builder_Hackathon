# Spec: Amazon Settlement Flat File V2, as LeakProof reads and writes it

Status: reviewed against RS1's research (`docs/research/amazon-v2-sample.md`,
2026-09-04). The 24-column list and order are **verified** against four
independent sources. No public sample data file exists, so value vocabulary is
verified only where RS1 found the literal string in a source it read; India
tax and fee-GST strings remain unverified. The generator (lane B) writes this
layout; the parser (lane D) reads it. The executable form is
`contract.LINE_VOCABULARY`, `contract.AMOUNT_TYPE_VOCABULARY` and
`contract.TRANSACTION_VOCABULARY`; this file is the human-readable one and
carries the verification status. Integrator-owned: corrections land between
waves.

Three traps RS1 confirmed, which the parser must treat as first-class:

1. **The decimal separator is locale-dependent.** Amazon's own docs show a
   comma-as-decimal European example. The parser detects or is configured
   per marketplace; it never hard-codes `.`, and it quarantines any amount
   it cannot parse with the literal string.
2. **`transaction-type` is an open vocabulary**, like `amount-description`
   (`Order_Retrocharge` observed first-hand). Unknown values map to
   `TransactionType.OTHER` and the raw string is kept on the line.
3. **Date and timestamp formats are unconfirmed for the flat file.** The
   parser accepts the formats listed below and quarantines anything else
   with the literal string; the generator writes the first listed form.

Vocabulary comparisons are case-insensitive (`Other-Transaction` and
`other-transaction` both appear in sources).

## File conventions

| Aspect | Value | verified |
|---|---|---|
| Report type | `GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2` | true (SP-API docs, RS1 §1) |
| Encoding | UTF-8, tab-separated, `\n` line endings, no quoting | tab-separated: true (RS1 §1, seller forum "24 columns A–X"); encoding and quoting: false |
| Row 1 | header line with the 24 column names below | true |
| Row 2 | settlement summary: `settlement-id`, dates, `total-amount`, `currency` populated; every other column empty | false |
| Rows 3+ | one transaction line each | true |
| Dates | accepted: `YYYY-MM-DD`; `YYYY-MM-DD HH:MM:SS UTC`; ISO-8601 with numeric offset (`2022-03-22T21:21:31+00:00`, seen in the XML sibling report). The generator writes the first two. | false (RS1 §1, trap 2) |
| Amounts | decimal with two places, no thousands separator, `-` prefix for negatives; **decimal separator detected per file** (`.` or `,`), parsed to integer paise | separator locale-dependence: true (Amazon docs, RS1 §1 trap 1); India uses `.`: false |
| Signs | sales positive, fees and refunds negative, reversals positive; carried exactly as written | false |
| Currency | `INR` for the India marketplace | false |
| One file per settlement cycle | yes; the generator names files `settlement_<end-date>.txt` | n/a (project convention) |

## Columns (24, in order)

1. settlement-id
2. settlement-start-date
3. settlement-end-date
4. deposit-date
5. total-amount
6. currency
7. transaction-type
8. order-id
9. merchant-order-id
10. adjustment-id
11. shipment-id
12. marketplace-name
13. amount-type
14. amount-description
15. amount
16. fulfillment-id
17. posted-date
18. posted-date-time
19. order-item-code
20. merchant-order-item-id
21. merchant-adjustment-item-id
22. sku
23. quantity-purchased
24. promotion-id

A row with a different column count is quarantined with the reason
`expected 24 tab-separated columns, found N` (D7). A file whose every row has
one column gets the actionable hint "the file was saved as CSV; Amazon
Settlement Flat File V2 is tab-separated" (wireframe, frame 4).

## Transaction types → `contract.TransactionType`

| transaction-type | enum | verified |
|---|---|---|
| Order | ORDER | true (two independent sources, RS1 §2) |
| Refund | REFUND | true |
| Chargeback Refund | CHARGEBACK_REFUND | false |
| A-to-z Guarantee Refund | ATOZ_REFUND | false (A2X names the category; the literal column value is A2X's decomposition, RS1 §2) |
| Adjustment | ADJUSTMENT | true (single source) |
| ServiceFee | SERVICE_FEE | true (single source) |
| Order_Retrocharge | ORDER_RETROCHARGE | true (first-hand seller report, RS1 §1 trap 3) |
| Transfer | TRANSFER | false (single source; may be Amazon Pay bleed-through) |
| SAFE-T Reimbursement | SAFET_REIMBURSEMENT | false |
| anything else | OTHER, raw string kept on the line | n/a |

## (amount-type, amount-description) → `contract.LineKind`

| amount-type | amount-description | LineKind | audited? | verified |
|---|---|---|---|---|
| ItemPrice | Principal | PRINCIPAL | n/a (income) | true (≥2 sources) |
| ItemPrice | Tax | ITEM_TAX | n/a | false |
| ItemPrice | Shipping | SHIPPING_CHARGE | n/a | true (single source) |
| ItemPrice | ShippingTax | SHIPPING_CHARGE_TAX | n/a | false |
| ItemPrice | GiftWrap | GIFT_WRAP | acknowledged | true (single source) |
| ItemPrice | Goodwill | GOODWILL | acknowledged | true (single source) |
| ItemPrice | RestockingFee | RESTOCKING_FEE | acknowledged | true (single source) |
| ItemFees | Commission | COMMISSION | yes, detector 1 | true (≥2 sources) |
| ItemFees | FixedClosingFee | FIXED_CLOSING_FEE | yes, detector 2 | false (India term unconfirmed; US shows `VariableClosingFee`) |
| ItemFees | ShippingChargeback | SHIPPING_FEE | acknowledged, not audited (detector 3 cut) | true (single source) |
| ItemFees | RefundCommission | REFUND_ADMIN_FEE | yes, detector 5 | true (≥2 sources; RS3 §5 confirms "Refund Commission" as the India term) |
| ItemFees | FBAPerUnitFulfillmentFee / FBAWeightBasedFee / FBAPerOrderFulfillmentFee | FULFILMENT_FEE | acknowledged | true (first two ≥2 sources; third single source, casing varies) |
| ItemFees | GiftwrapChargeback | GIFT_WRAP | acknowledged | true (single source) |
| ItemFees | StorageFee / LongTermStorageFee | STORAGE_FEE | acknowledged | true (single source) |
| ItemFees | TechnologyFee | TECHNOLOGY_FEE | known; whether a rule exists is the rate card's call | false |
| ItemFees | TaxOnFees | FEE_TAX | yes, GST on fees | **false, name uncertain** (no source shows how GST on fees appears) |
| Promotion | (any) | PROMOTION | acknowledged | false |
| ItemWithheldTax | TCS-CGST / TCS-SGST / TCS-IGST | TCS | yes, detector 7 | **false** (not found verbatim anywhere; pattern-matched from the US `MarketplaceFacilitatorTax-*` form, RS1 §2) |
| ItemWithheldTax | TDS (Section 194-O) | TDS | yes, detector 7 | **false** (same) |
| ItemWithheldTax | MarketplaceFacilitatorTax-Principal / MarketplaceFacilitatorTax-Shipping | MARKETPLACE_FACILITATOR_TAX | acknowledged (US marketplace) | true (three independent sources) |
| other-transaction | Current Reserve Amount / Previous Reserve Amount Balance | RESERVE | acknowledged | strings true, amount-type pairing false (RS1 §2) |
| other-transaction | SAFE-T Reimbursement | SAFET_REIMBURSEMENT | acknowledged | false |
| anything else | anything else | UNCLASSIFIED | class 8, basis code-unseen (D4) | n/a |

The kind says what a line is; the transaction type says under which event it
was posted. A refund's commission reversal is therefore `(REFUND, COMMISSION,
positive amount)` and the retained refund administration fee is
`(REFUND, REFUND_ADMIN_FEE, negative amount)`.

"Audited" and "acknowledged" are declared by the rate card (lane C), not here:
this column records the intent so lanes B, C and D agree on the shape. A known
kind for which the rate card declares neither a rule nor an acknowledgement is
class 8 with basis `code-known-no-rule` (ADR-0005).

## Companion inputs (project conventions, not Amazon formats)

**Orders CSV** (the seller's own export), header row then one row per order
line: `order_id, sku, category_id, quantity, principal_paise, tax_paise,
order_date, delivery_date, refund_initiated_by`. `delivery_date` may be empty;
`refund_initiated_by ∈ {none, seller, amazon}`.

**Bank CSV**: `date, utr, amount, narration`. Amount in rupees with two
decimals; parsed to paise.

**Seller profile** (JSON): `seller_id, display_name, capabilities: [{name,
holds, valid_from, valid_to}]`. Capability names in use: `gst_registered`,
`safe_t_enrolled`.
