# Spec: `evidence.csv`, the seller's evidence-supply companion file

Status: **new in Wave 2**, integrator-owned. Verified against nothing external —
this is a LeakProof-defined file, not an Amazon report, so there is no primary
source to check it against and no row here is marked `verified`. The generator
(lane B) does not write it yet; lane I writes the parser, lane K consumes the
parsed records, and the demo batch gains a hand-authored one at the Wave 3
assembly.

## Why this file exists

The four spec'd inputs (orders CSV, Settlement V2 flat file, bank CSV,
seller-profile config) say what the marketplace did. None of them says what the
**seller** holds. So every claim whose evidence table contains a
`seller-suppliable` requirement blocks at precedence step 5 forever, and
`C5_PLAIN` (nothing missing, should reach CLAIM-READY) is indistinguishable
from `C5_INVOICE_PENDING` (a tax invoice the seller has not produced). Wave 1
closed with that gap open and the whole SAFE-T path pinned at BLOCKED.

The file is the seller's **assertion**, deliberately not a derived fact.
`supplied_on` is a date the seller stands behind; LeakProof cannot recompute it
and does not try. That asymmetry is the point: a claim reaching CLAIM-READY on
the strength of this file is one where a human said "I have the invoice", and
the audit trail records which row said so.

## Layout

Comma-separated, UTF-8, one header row, `\n` line endings. Four columns, in
this order:

| Column | Type | Required | Meaning |
|---|---|---|---|
| `order_id` | string | yes | Joins to `Order.order_id`. An id absent from the orders export is **not** checked here: like every other parser in `ingest/`, this one reads one file and knows nothing of the others (`bank.py` does not know the settlements either). The unknown-id quarantine belongs to batch assembly, which is the first place both files are in hand — see "Where the cross-file check lives" below. |
| `requirement` | string | yes | Matches `EvidenceItem.requirement` **verbatim**, byte for byte. This is the join key lane K uses, and a near-miss is a silent no-op, so the parser preserves the string exactly (no case folding, no whitespace normalisation beyond stripping the surrounding field) and lane K's join is exact. |
| `status` | enum | yes | One of `satisfied`, `missing`, `pending` — the three values of `contract.EvidenceStatus`, spelled as the enum's own values. Anything else quarantines the row naming the literal string. |
| `supplied_on` | date or empty | conditional | `YYYY-MM-DD`. **Required when `status` is `satisfied`**, and empty otherwise. A satisfied requirement with no date is quarantined: an undated assertion cannot be checked against a filing window, and silently accepting it would push a claim to CLAIM-READY on evidence of unknown age. A date on a `missing` or `pending` row is also quarantined — it means the file disagrees with itself. |

### Where the cross-file check lives

A supply row naming an order that appears in no export cannot be attached to
any finding, so it must be quarantined and counted — D7 puts the quarantine
count on screen beside the match rate, and a row that silently survives into
lane K's join is a row missing from that count.

It is quarantined at **batch assembly** (lane L, Wave 3), not in the parser.
The parser takes one file and one file only, which is the house style every
Wave 1 parser follows, and it has no way to know what the orders export
contains. The earlier wording of the `order_id` row above said the parser did
this; it never could, and lane I's parser correctly does not. Assembly holds
both parses, so the check is one set membership there, with the reason string
naming the unknown id.

Until that lands, an unknown-id row parses cleanly and then matches nothing:
a no-op in lane K rather than a wrong claim, which is why this is a Wave 3
item and not a Wave 2 defect.

Example:

```
order_id,requirement,status,supplied_on
403-1234567-1234567,Tax invoice for the returned item,satisfied,2026-08-14
403-7654321-7654321,Tax invoice for the returned item,pending,
403-1111111-2222222,Proof of delivery,missing,
```

## Parser requirements (lane I)

Same shape as the three Wave 1 parsers (`ingest/orders.py`, `ingest/bank.py`),
because a fifth input that behaves differently from the other four is a trap
for every downstream lane:

- Returns `types.EvidenceParse` — `supplies`, `quarantined`, `hint`.
- Every row gets a `line_id` in the `contract.make_line_id` format, so a claim
  pack can cite the row a supply statement came from.
- Malformed rows are quarantined with a row-level reason quoting the literal
  offending value, never dropped and never coerced (D7).
- One actionable `hint` per file at most (wireframe frame 4), on the same rule
  the other parsers use.
- An absent file is not an error anywhere: `BatchInputs.evidence` is `None`,
  which lane K reads as "the seller asserted nothing", not "the seller holds
  nothing". Both land on BLOCKED(seller-action); only one of them is a claim
  about the seller's filing cabinet, and only the audit trail can tell them
  apart later.
- Duplicate `(order_id, requirement)` pairs: **the file is wrong, not the last
  row right.** Quarantine every row of the duplicate set naming the pair, and
  let lane K see none of them. Last-write-wins would make the claim state
  depend on row order in a file a human edited by hand.
