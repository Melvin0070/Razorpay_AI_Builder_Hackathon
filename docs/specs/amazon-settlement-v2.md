# Spec: Amazon Settlement Flat File V2, as LeakProof reads and writes it

Status: `verified: false` on every row below until RS1 (issue #1) confirms it
against SP-API documentation and, if one exists, a public sample. The
generator (lane B) writes this layout; the parser (lane D) reads it. The
executable form is `contract.LINE_VOCABULARY`, `contract.AMOUNT_TYPE_VOCABULARY`
and `contract.TRANSACTION_VOCABULARY`; this file is the human-readable one and
carries the verification status. Integrator-owned: corrections land between
waves.

## File conventions

| Aspect | Value | verified |
|---|---|---|
| Report type | `GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2` | false |
| Encoding | UTF-8, tab-separated, `\n` line endings, no quoting | false |
| Row 1 | header line with the 24 column names below | false |
| Row 2 | settlement summary: `settlement-id`, dates, `total-amount`, `currency` populated; every other column empty | false |
| Rows 3+ | one transaction line each | false |
| Dates | `posted-date` as `YYYY-MM-DD`; `posted-date-time` as `YYYY-MM-DD HH:MM:SS UTC`; header dates `YYYY-MM-DD` | false |
| Amounts | decimal with two places, `.` separator, no thousands separator, `-` prefix for negatives; parsed to integer paise | false |
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
| Order | ORDER | false |
| Refund | REFUND | false |
| Chargeback Refund | CHARGEBACK_REFUND | false |
| A-to-z Guarantee Refund | ATOZ_REFUND | false |
| Adjustment | ADJUSTMENT | false |
| Transfer | TRANSFER | false |
| SAFE-T Reimbursement | SAFET_REIMBURSEMENT | false |
| anything else | OTHER | n/a |

## (amount-type, amount-description) → `contract.LineKind`

| amount-type | amount-description | LineKind | audited? | verified |
|---|---|---|---|---|
| ItemPrice | Principal | PRINCIPAL | n/a (income) | false |
| ItemPrice | Tax | ITEM_TAX | n/a | false |
| ItemPrice | Shipping | SHIPPING_CHARGE | n/a | false |
| ItemPrice | ShippingTax | SHIPPING_CHARGE_TAX | n/a | false |
| ItemFees | Commission | COMMISSION | yes, detector 1 | false |
| ItemFees | FixedClosingFee | FIXED_CLOSING_FEE | yes, detector 2 | false |
| ItemFees | ShippingChargeback | SHIPPING_FEE | acknowledged, not audited (detector 3 cut) | false |
| ItemFees | RefundCommission | REFUND_ADMIN_FEE | yes, detector 5 | false |
| ItemFees | TechnologyFee | TECHNOLOGY_FEE | known; whether a rule exists is the rate card's call | false |
| ItemFees | TaxOnFees | FEE_TAX | yes, GST on fees | **false, name uncertain** |
| Promotion | (any) | PROMOTION | acknowledged | false |
| ItemWithheldTax | TCS-CGST / TCS-SGST / TCS-IGST | TCS | yes, detector 7 | false |
| ItemWithheldTax | TDS (Section 194-O) | TDS | yes, detector 7 | false |
| other-transaction | Current Reserve Amount / Previous Reserve Amount Balance | RESERVE | acknowledged | false |
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
