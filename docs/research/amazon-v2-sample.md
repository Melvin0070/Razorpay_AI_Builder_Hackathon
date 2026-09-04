# Amazon Settlement Report V2 — sample file & vocabulary research (RS1)

Wave 0, research lane RS1. Answers design-doc Open Question 2 ("Is a real
Amazon V2 sample settlement file publicly obtainable?") and the Constraints
item "No real settlement file in hand." Governing sections read first:
`docs/designs/leakproof-evidence-completeness.md` Constraints, Open Question 2,
premise P1, D4, D7.

All URLs were reached with the `browse` skill (headless Chromium) unless
marked otherwise; WebSearch was used only to discover candidate URLs, never
cited as a source by itself. Access date for everything below is **2026-09-04**
unless a different as-of date is given for the source's own content. Every
claim is marked `verified: true` (I read the primary page myself and it says
this) or `verified: false` (secondary, contradicted, or not reached — reason
given). Literal schema tokens (column names, enum-like values) are given in
`code font` as data, not as prose quotations; explanations from sources are
paraphrased rather than quoted.

---

## 1. Column spec — confirmed, no correction needed

The integrator's 24-column, tab-separated layout is correct in name, count,
and order. Cross-checked against independent sources that do not cite each
other:

- **Amazon's own SP-API docs** list the report attributes for
  `GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2` in exactly this order:
  `settlement-id, settlement-start-date, settlement-end-date, deposit-date,
  total-amount, currency, transaction-type, order-id, merchant-order-id,
  adjustment-id, shipment-id, marketplace-name, amount-type,
  amount-description, amount, fulfillment-id, posted-date, posted-date-time,
  order-item-code, merchant-order-item-id, merchant-adjustment-item-id, sku,
  quantity-purchased, promotion-id`. `verified: true`.
  Source: https://developer-docs.amazon.com/sp-api/docs/report-type-values-settlement
  (page self-reports "updated 9 days ago" at access time, so as-of ≈2026-08-26).

- **Intentwise's V1→V2 mapping guide** (independent commercial integrator)
  lists the same 20 "direct passthrough" columns plus `amount-type` /
  `amount-description` / `amount`, and states they are unchanged from V1.
  I extracted the page's own HTML table via script rather than trusting the
  rendered text dump, which garbles multi-row (`rowspan`) cells into a
  run-on. Same 24 names, same order. `verified: true`.
  Source: https://help.intentwise.com/amazon-settlement-report-v1-to-v2-mapping-guide
  (no publish date shown on page).

- **A real seller's forum post** (not a vendor) describes the file as
  spanning spreadsheet columns A through X in normal operation, before a
  2022 Amazon-side glitch briefly widened it — A-through-X is 24 columns,
  an independent count from someone looking at an actual downloaded file,
  though the thread does not name the columns. `verified: true` (count
  only).
  Source: https://sellercentral.amazon.com/seller-forums/discussions/t/192180948debffbbba86ede4354d5615
  (thread timestamped "4 years ago" relative to a 2026-09-04 access, so
  as-of ≈2022).

- **Nova Analytics' 2026 seller guide** states the same count in passing
  (no column list). `verified: true`, lower weight.
  Source: https://novadata.io/resources/blog/amazon-settlement-report-guide
  (dated 2026-07-20).

**Correction to the design doc's Constraints text:** the claim that "several
integrator vendors already cited here (A2X, Openbridge, Intentwise,
DataChannel, Celigo) publish sample settlement flat files" did not hold up.
All five publish *documentation describing* the format (prose, and in
Intentwise's case one worked-example table with invented numbers). None of
the five publishes a downloadable sample data file. See §3.

### Traps found, not previously known

1. **Decimal/thousands separator is locale-dependent — confirmed by Amazon
   itself, not a hypothesis.** The official SP-API page states amounts print
   in local currency format and gives a European example using a comma as
   the decimal separator instead of a period. `verified: true`. Source: same
   official page as above. It is not confirmed which separator the India
   marketplace uses (no India sample reached — see §3), so the parser should
   treat the separator as a value to detect or configure per marketplace,
   never a hard-coded `.`.

2. **`posted-date-time`'s literal format is not confirmed for the flat
   file.** The one literal timestamp found, `2022-03-22T21:21:31+00:00`, is
   from the **XML** sibling report (`GET_V2_SETTLEMENT_REPORT_DATA_XML`), not
   the flat file. The developer who posted it said the flat file's date
   looked like a different format and he wasn't sure it was the same value.
   `verified: true` only that the XML report uses ISO-8601 with a numeric
   UTC offset; `verified: false` that the flat file matches it. Source:
   https://github.com/amzn/selling-partner-api-models/issues/2345 (opened
   2022-03-29, key reply 2022-07-09). No source gave a literal example of
   `settlement-start-date`, `settlement-end-date`, `deposit-date`, or
   `posted-date` (date-only) formatting either — all `verified: false`.

3. **`transaction-type` is not a small closed enum.** The same GitHub issue
   has a first-hand report (not vendor-derived) of the literal value
   `Order_Retrocharge` appearing in a real downloaded flat file's
   transaction-type column, underscore-separated, distinct in shape from the
   short single-word values elsewhere. `verified: true` — this is the single
   most trustworthy data point in this memo because it is someone describing
   their own file rather than a vendor's summary of the spec. It means D4's
   "unknown code → unclassified, never silently dropped" treatment should
   probably extend from `amount-description` to `transaction-type` as well,
   since the vocabulary is evidently open-ended there too.

---

## 2. Value vocabulary

No single source gives an exhaustive, authoritative list of every
`transaction-type` / `amount-type` / `amount-description` value — Amazon's
own docs describe the *columns* but not their *value sets* (by design: new
fee types are meant to appear as new rows without a schema change). What
follows is every value I found stated by a source I read directly, with
attribution. Treat this as a floor, not a ceiling.

### `transaction-type`

| Value | Source(s) | Verified |
|---|---|---|
| `Order`, `Refund` | Nova Analytics (used in P&L formulas), DigitalAdBlog | true (2 independent sources) |
| `Adjustment`, `ServiceFee` | DigitalAdBlog | true (single source) |
| `Transfer`, `Liquidations` | DigitalAdBlog | false — single source, and "Transfer" is also a real term in the *unrelated* Amazon Pay settlement product (see trap below); not cross-confirmed for the marketplace flat file specifically |
| `other-transaction` (lowercase, hyphenated) | Nova Analytics; Oracle NetSuite Connector docs describe fees "labelled as other-transaction" | true that the string exists somewhere in this ecosystem; false on which *column* it lives in — see contradiction below |
| `Order_Retrocharge` | GitHub issue #2345, first-hand seller report | true (see §1.3) |

**Contradiction found, unresolved:** Intentwise's table (§2, amount-type
section below) shows `Other-Transaction` (title case) as an **amount-type**
value. Nova Analytics and the Oracle/NetSuite docs describe `other-transaction`
(lowercase) as a **transaction-type** value. These may be the same string
loosely paraphrased by different authors, or genuinely two different values
in two different columns. I could not resolve this without a real file.
Recommend the parser case-fold all vocabulary comparisons and not assume a
single canonical casing for anything in this report.

**Trap: do not confuse with Amazon Pay.** Amazon Pay (the checkout product
other websites embed, documented at `developer.amazon.com/docs/amazon-pay-reports`
and `pay.amazon.com`) has its own, differently-shaped settlement report with
transaction types like `Capture`, `Carryover`, `Reserve`. This is a different
product from the Seller Central marketplace settlement report
(`GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2`) this memo is about. Search
results mix the two freely because both use the word "settlement"; I did not
carry any Amazon Pay-only vocabulary into this memo's `verified: true` rows.

### `amount-type`

Extracted programmatically from Intentwise's table (rowspans preserved), the
one source that lists these systematically:

| amount-type | amount-descriptions under it | Verified |
|---|---|---|
| `ItemFees` | `Commission`, `FBAPerUnitFulfillmentFee`, `FBAWeightBasedFee`, `GiftwrapChargeback`, `RefundCommission`, `ShippingChargeback`, `VariableClosingFee` | true (single source, but internally consistent — full 7-row `rowspan` group) |
| `ItemPrice` | `GiftWrap`, `Goodwill`, `Principal`, `RestockingFee`, `Shipping` | true (single source) |

Below that point, Intentwise's own table is almost certainly miscopied: the
`rowspan` structure puts `Current Reserve Amount` inside the `ItemPrice`
group and puts `Previous Reserve Amount Balance`, `Refund Reimbursal`,
`Storage Fee`, and a second `Shipping` row (defined as a shipping *promotion*,
which reads like it belongs to a `Promotion` type) inside an
`Other-Transaction` group, then a row literally pairs amount-type `Promotion`
with description `FBAperOrderFulfillmentFee` (a fulfillment fee, not a
promotion) and amount-type `Shipment-Fees` with description
`FBATransportationFee`. That pairing does not make semantic sense — it reads
like the source table lost a row of alignment partway through, a classic
`rowspan`-editing bug. I'm reporting the raw extraction because the
*description strings themselves* (`Current Reserve Amount`,
`Previous Reserve Amount Balance`, `Refund Reimbursal`, `Storage Fee`,
`FBAperOrderFulfillmentFee`, `FBATransportationFee`) are still plausibly real
amount-description values seen in real files — I just do not trust which
amount-type Intentwise says they sit under. `verified: false` for every
type↔description pairing from this point in their table onward; `verified:
false` (unconfirmed elsewhere) but plausible for the description strings
existing at all.
Source: https://help.intentwise.com/amazon-settlement-report-v1-to-v2-mapping-guide

Two more amount-type values, from two independent, mutually-corroborating
2026 sources that were not scraped from Intentwise:

| amount-type | Description | Verified |
|---|---|---|
| `ItemWithheldTax` | Marketplace-facilitator sales tax Amazon collects and remits (US context); paired example `MarketplaceFacilitatorTax-Principal` and `MarketplaceFacilitatorTax-Shipping` | true — confirmed independently by Nova Analytics (2026-07-20) and DigitalAdBlog (2026-08-08), and the exact string `MarketplaceFacilitatorTax-Principal` additionally appears in the unrelated 2022 GitHub issue as an XML `<Charge><Type>` value, which is strong triangulation across three unrelated authors and four years |
| `other-amount` | Catch-all, named only in passing | false — single source (Nova Analytics), not cross-confirmed |

Sources: https://novadata.io/resources/blog/amazon-settlement-report-guide
(2026-07-20); https://digitaladblog.com/2026/08/08/understanding-amazon-settlement-reports-line-by-line/
(2026-08-08); https://github.com/amzn/selling-partner-api-models/issues/2345
(2022, XML variant).

**Why `ItemWithheldTax` matters for this project:** it is the best lead for
where India's GST/TCS/TDS lines live, by pattern (a "withheld tax" bucket,
with description values that look like `<TaxKind>-<Component>`), but this is
my inference from a US example, not a direct India observation — see below.

### `amount-description` (generic, non-India)

Multi-source-confirmed (`verified: true`, ≥2 independent sources each):
`Principal`, `Commission`, `FBAPerUnitFulfillmentFee`, `FBAWeightBasedFee`,
`RefundCommission`. Note capitalization is inconsistent across sources for
the per-order fulfillment fee — Intentwise writes `FBAperOrderFulfillmentFee`,
Nova Analytics writes `FBAPerOrderFulfillmentFee` — almost certainly the same
value, cased differently by two different authors; treat as unconfirmed
exact casing.

Single-source (`verified: true` for the string existing, not cross-checked):
`GiftwrapChargeback`, `ShippingChargeback`, `VariableClosingFee`, `GiftWrap`,
`Goodwill`, `RestockingFee`, `Shipping`, `MarketplaceFacilitatorTax-Principal`,
`MarketplaceFacilitatorTax-Shipping` (this pair independently triangulated
across three sources as noted above), `advertising` (on-account ad spend,
Nova Analytics only), `StorageFee`, `LongTermStorageFee` (Nova Analytics
only).

`RefundCommission` — the mission's specific ask — is defined consistently by
both sources that mention it as the reversal of the referral-fee commission
that happened when the original sale's commission is refunded back to the
seller alongside the returned item price. This is the literal string to use
for detector class c1-style "refund without a matching commission reversal"
logic. `verified: true` (Intentwise + Nova Analytics, worded independently).

### India-specific vocabulary — the weak point of this research

**No source I could reach gave a literal, directly-observed amount-type or
amount-description string for GST-on-fees, TCS, or TDS as they appear in a
real Amazon.in settlement file.** This is the one item in the mission I could
not close. What I found instead:

- **ReconPe** (an Indian marketplace-reconciliation SaaS, reviewed 2026-07-02)
  glosses — not quotes — the file's rows in a table headed "Amount type /
  What it means for you", listing entries it labels `TCS (CGST/SGST/IGST)`
  and `TDS (Sec 194-O)` alongside `Principal`, `Commission`,
  `Closing / fixed fee`, and `Adjustments (A-to-Z, SAFE-T, chargebacks)`.
  This reads as ReconPe's own human-readable paraphrase of the underlying
  raw values for a marketing page, not a screenshot or a literal quote of
  the `amount-type`/`amount-description` columns, so I am marking the exact
  strings `verified: false` even though the underlying concepts (TCS under
  CGST Act s.52, TDS under s.194-O, A-to-Z and SAFE-T as separate
  adjustment-cycle rows kept out of the per-order net, and a reserve that
  explains bank-deposit-short-of-settlement-total) are well corroborated
  elsewhere. Source: https://reconpe.com/amazon-india-reconciliation/
  (reviewed 2026-07-02).
- Two chartered-accountant-audience sources (LogiRecon/Logibricks,
  2026-07-17 and 2026-07-19) describe the same concepts at the same level —
  a labelled section for TCS and TDS exists in the report — without giving
  literal strings either.
  Sources: https://logibricks.com/blog/marketplace-reconciliation-a-cas-step-by-step-playbook-for-reading-amazon-flipka;
  https://logibricks.com/blog/amazon-settlement-report-format-explained
- Two real, public (no login required) Amazon seller-forum threads — one on
  the India forum, one on the UK forum discussing an India seller's account —
  confirm TCS-vs-TDS reconciliation is a live, painful, real problem
  (mismatches against Form 26AS / Form 16A), but neither thread pastes a raw
  report row.
  Sources: https://sellercentral.amazon.in/seller-forums/discussions/t/77859d779facd8b12ed4dec21ecbba3e
  (≈2023); https://sellercentral.amazon.co.uk/seller-forums/discussions/t/e9b3bdbc-7000-4e3b-962d-1e9f0203d6e6
  (≈2023).
- The design doc's example forms (`TCS-CGST`, `TDS (Section 194-O)`) were
  **not found verbatim anywhere**. They are a plausible guess consistent
  with the `ItemWithheldTax` / `<TaxKind>-<Component>` pattern confirmed for
  the US (`MarketplaceFacilitatorTax-Principal`), but that is pattern-matching
  from a different marketplace, not a citation. `verified: false`.

**A-to-Z Guarantee.** A2X, a major accredited SP-API integrator (distinct
from the ReconPe/Logibricks tier above), names `A-to-z Guarantee Refund` as
one of its own recognized transaction categories, and separately shows a
composite display label `A-to-z Guarantee Refund Item Price Principal` in
its own transaction-mapping table — A2X builds these composite labels itself
by concatenating (transaction-type, amount-type, amount-description), so the
compound string is A2X's UI convention, not a literal single-column value.
My best-supported decomposition guess is transaction-type ≈
`A-to-z Guarantee Refund`, amount-type `ItemPrice`, amount-description
`Principal` — `verified: false` on the decomposition, `verified: true` only
that A2X names an A-to-Z-guarantee-specific transaction category distinct
from an ordinary refund. Source:
https://www.a2xaccounting.com/ecommerce-accounting-hub/amazon-order-revenue-accounting
(no publish date shown; author bio present).

**Reserve / transfer rows.** Best support is Intentwise's `Current Reserve
Amount` / `Previous Reserve Amount Balance` description strings (§2,
amount-type table, flagged `verified: false` on type-pairing above) plus
three independent sources (Nova Analytics, DigitalAdBlog, A2X's own
"Amazon Reserve Balances" companion article, and ReconPe for the India
angle) all describing the same underlying mechanic in prose: the gap between
a settlement's `total-amount` and the actual bank deposit is a reserve held
against A-to-Z claims, chargebacks, and pending refunds, released in a later
cycle. No literal amount-type/description string for the *release* side was
found beyond Intentwise's `Previous Reserve Amount Balance`.

---

## 3. Sample files — every candidate source checked

| Source | Checked | Sample found | URL | Licence | India marketplace | Flat file V2 or other |
|---|---|---|---|---|---|---|
| Amazon SP-API official docs | yes | no — schema only, no example data file | https://developer-docs.amazon.com/sp-api/docs/report-type-values-settlement | n/a (no file to license) | n/a | V2 (schema only) |
| A2X | yes (2 articles) | no — prose documentation and one invented worked example, no downloadable file | https://support.a2xaccounting.com/en/articles/1828440-amazon-settlement-formats-v1-and-v2-flat-file ; https://www.a2xaccounting.com/ecommerce-accounting-hub/amazon-order-revenue-accounting | n/a | not specified | V2 |
| Openbridge | yes | no — process documentation only | https://docs.openbridge.com/en/articles/5150091-understanding-amazon-settlement-reports | n/a | not specified | V2 |
| Intentwise | yes | no — one V1-vs-V2 worked example with invented numbers (`order-id 123456`), not a real file | https://help.intentwise.com/amazon-settlement-report-v1-to-v2-mapping-guide | n/a | not specified | V2 |
| DataChannel | yes | no — pipeline/ETL configuration documentation only | https://docs.datachannel.co/getting-started/1.0.0/applications/cloud_application/amazon-seller-central/pipelines/flat-file-v2-settlement.html | n/a | not specified | V2 |
| Celigo | attempted, blocked | unknown — could not reach the page | https://docs.celigo.com/hc/en-us/articles/19152560872475-Understand-Amazon-settlement-reports ; https://docs.celigo.com/hc/en-us/articles/115001350932-Understand-the-Amazon-settlement-reports | unknown | unknown | unknown |
| GitHub code search (site-wide) | attempted, blocked | not reached | https://github.com/search?q=%22settlement-id%22+%22amount-description%22... | n/a | n/a | n/a |
| grep.app (GitHub code mirror, no login) | yes | no relevant hits for `amount-description`, `RefundCommission` | https://grep.app/search?q=amount-description ; https://grep.app/search?q=RefundCommission | n/a | n/a | n/a |
| Sourcegraph (public code search) | attempted, blocked | not reached | https://sourcegraph.com/search?q=... | unknown | n/a | n/a |
| `jedistev/AmazonStatement_Project` (GitHub) | yes | no — PHP/MySQL app for importing a seller's own downloaded file; ships schema/import code, not sample data; UK/EU-market oriented | https://github.com/jedistev/AmazonStatement_Project | repo has no LICENSE file (all-rights-reserved by default) — moot, no data to copy | no | V2 (per README) |
| `amzn/selling-partner-api-models` (GitHub, official) | yes | no — repo has the Reports-API request/response OpenAPI model only; the settlement file's own content is opaque to that schema (it's delivered as a document, not modeled as JSON) | https://github.com/amzn/selling-partner-api-models/tree/main/models/reports-api-model | Apache-2.0 (repo-wide) — moot, no sample data present | n/a | n/a |
| `amzn/selling-partner-api-models` Discussions #3626, #3744 | yes | no — both are API-access troubleshooting threads, no pasted data | https://github.com/amzn/selling-partner-api-models/discussions/3626 ; .../discussions/3744 | n/a | n/a | n/a |
| `amzn/selling-partner-api-models` Issue #2345 | yes | no full sample, but **one real first-hand fragment**: literal `transaction-type` value `Order_Retrocharge` and literal XML `<Type>` values `MarketplaceFacilitatorTax-Shipping` / `MarketplaceFacilitatorTax-Principal`, quoted by the reporting developer from their own downloaded report | https://github.com/amzn/selling-partner-api-models/issues/2345 | n/a (forum text, not a redistributable file) | not specified (developer didn't say) | V2 (flat file) + XML sibling |
| Nova Analytics blog | yes | no — guide/blog, no downloadable file | https://novadata.io/resources/blog/amazon-settlement-report-guide | n/a | not specified (guide is marketplace-agnostic) | V2 |
| DigitalAdBlog | yes | no — blog, one fully-invented worked example (`$49.99 unit`), not a real file | https://digitaladblog.com/2026/08/08/understanding-amazon-settlement-reports-line-by-line/ | n/a | US (worked example uses USD, "marketplace facilitator" sales tax) | V2 |
| ReconPe | yes | no — India-specific SaaS marketing page with one fully-invented worked example (`₹2,199.00` order), not a real file | https://reconpe.com/amazon-india-reconciliation/ | n/a | yes (India-specific product, but example is illustrative, explicitly labelled so) | V2 |
| Amazon seller forums (India, UK, US) | yes (4 threads) | no — text complaints/discussion, no pasted rows or attached files | see URLs throughout §1–2 | n/a | one thread is India forum | n/a |

**Bottom line on Open Question 2: the schema is public and well-verified (see
§1); an actual sample *data* file, redacted or otherwise, is not obtainable**
through any of the seven named channels (A2X, Openbridge, Intentwise,
DataChannel, Celigo, GitHub, Amazon's own docs) or the three additional
channels checked (grep.app, Sourcegraph, seller forums). Every integrator
publishes prose documentation and at most one small invented worked example;
none publishes a real seller's redacted export. This matches the pattern you'd
expect: a settlement report is one seller's private financial data pulled via
an authenticated SP-API call or an authenticated Seller Central session —
there is no public corpus of them, and no vendor has an incentive to publish
one. **No fixture file was added to `tests/fixtures/external/`** — nothing
found was both real and redistributable.

---

## 4. Recommendation for the parser lane (D)

1. Trust the 24-column name/order list as-is — four independent sources
   agree byte-for-byte; this is the most solid finding in this memo.
2. Do not hard-code `.` as the decimal separator or assume any date format
   for the five date/timestamp columns — both are confirmed-real traps, not
   hypothetical (Amazon's own docs on separators; a developer's own
   contradicting report on the flat file's date format). Fail unparseable
   rows into quarantine with the literal string that didn't parse, per D7.
3. Treat `transaction-type` the same way D4 already treats
   `amount-description` — an open vocabulary, unknown values routed to
   "unclassified", never dropped — since `Order_Retrocharge` proves the
   "known" list in this memo is a floor, not a ceiling.
4. Do not encode the India TCS/TDS/GST literal strings this memo could not
   verify (`TCS-CGST` etc.) as if confirmed; encode them as best-guess,
   `verified: false`, and log-and-flag (not silently accept) the first time
   a generated or real row doesn't match the guess.
5. `RefundCommission` and the `ItemWithheldTax` amount-type are the two
   highest-confidence pieces of vocabulary this memo found — safe to build
   detector logic against by name.
