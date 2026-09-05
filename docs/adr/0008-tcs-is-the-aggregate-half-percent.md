# ADR-0008: Detector 7 recomputes TCS as the 0.5% aggregate; the design doc's 1% is stale

Date: 2026-09-05 · Status: accepted

## Context
The design doc's class table (§"Detected error classes", class 7) says
"simplified Sec-52 TCS (1%)". Two Wave 1 lanes, forbidden from reading each
other's files, each read the primary notifications and each encoded something
else:

- Lane B (`generator/fees.py`): `TCS_CGST_BP = 25`, `TCS_SGST_BP = 25`,
  `TCS_IGST_BP = 50`, from 2024-07-10; legacy 50/50/100 before that. It writes
  an intra-State supply as two withheld lines (`TCS-CGST` + `TCS-SGST`) and an
  inter-State one as a single `TCS-IGST` line.
- Lane C (`ratecard/corpus/cgst-section-52-tcs.json`): one rule per window on
  the **aggregate**, `percent_bp = 50` from 2024-07-10, `percent_bp = 100`
  before it.

The two agree exactly: 0.25% + 0.25% intra-State and 0.5% inter-State both
aggregate to 0.5%. The doc's 1% is the pre-2024 aggregate, correct until
notification 15/2024-Central Tax substituted "0.25 per cent." for "half per
cent." with effect from 10 July 2024 (published, in force from publication).
Section 52(1) of the CGST Act sets only a ceiling — one per cent — which is
where the doc's figure comes from; the collected rate is fixed by notification,
and each notification fixes one leg.

This matters more than a stale sentence usually would. Every ordinary order in
every generated batch carries TCS at the notified rate. A detector that
recomputed at 1% would disagree with each of them by 0.5% of principal, which
is above the ₹10 materiality floor on any order over ₹2,000 — so "fixing" the
code to match the doc would fire a spurious class-7 finding on most of the
batch, and precision would collapse for a reason that looks like a tax bug.

## Decision
Detector 7 recomputes TCS as **the aggregate withheld across all TCS legs on
the order**, against the rate-card rule in force at `as_of` — 0.5% of the
order principal from 2024-07-10. It sums every `LineKind.TCS` line rather than
checking legs individually: the CGST/SGST split is a function of the supply's
place, which the settlement file does not state and LeakProof does not infer.

`LineKind.TCS` is the seam. The three `amount-description` values
(`TCS-CGST`, `TCS-SGST`, `TCS-IGST`) all map to it in
`contract.LINE_VOCABULARY`, which is what makes the aggregate the only figure
both sides can compare without inferring place of supply.

The design doc is **not** amended; this ADR governs, as ADR-0006 does for the
class-1 mechanism. Lane briefs name it directly.

## Consequences
- Lane J codes detector 7 against `ctx.rate_card.lookup(LineKind.TCS, None,
  as_of)` and never against a literal. A rate literal in `detect/` is a review
  rejection.
- The recomputation row shows the aggregate and the legs it summed, so a CA
  reading the export sees which lines were compared.
- Both TCS rules carry `verified: false` on the number they encode: the
  aggregate is the CGST leg doubled, and the mirroring SGST and IGST
  notifications were not read first-hand. That is the D14 fallback working as
  designed, and it must stay surfaced in the UI and the README.
- If someone later reads those two notifications, the rules flip to
  `verified: true` with no number changing.
- The 1% figure remains correct as the statutory **ceiling** and may be quoted
  as such; it is never a recomputation basis.
