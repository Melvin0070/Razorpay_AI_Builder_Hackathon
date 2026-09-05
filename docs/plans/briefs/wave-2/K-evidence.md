Lane K · Wave 2 · GitHub issue #14 · role `lp-core` (Fable, max effort) · worktree branch `lane/K-evidence`

## Mission
Decide, for one finding, what the seller must be able to show, whether any rule
excludes the claim outright, and how many calendar days are left to file. This
is the second independent reading of the same policy text that
`labels/claimability.json` encodes — you are a different agent from lane F by
construction, and you must stay one. Your output is what the precedence ladder
(lane L, Wave 3) turns into a state; get a window off by a day and a claim that
was filable is published as expired.

## Governing sections (read first)
- Design doc: the evidence-state model in full (mechanism, eligibility,
  `evidence[]`, `blocker_kind`, deadline), precedence steps 1–5 and exactly
  what each one consumes, D14 (policy-verification fallback: encode from
  secondary sources with `verified: false` + URL + as-of, surfaced in UI and
  README — unverified-but-labeled beats blocked), D18 (**calendar days**
  against `as_of`, never the system clock; month-end and leap-day tests).
- **ADR-0006** — SAFE-T is scoped to class 5 only. Class 1 files through a
  support ticket and has **no filing window**: a fee overcharge on an
  un-refunded sale has no return or refund event to start one from. Write
  SAFE-T eligibility and window rules for class 5 only.
- ADR-0007 (the six fixed override labels the gate will use).
- `docs/research/safe-t.md` — the **source list**. Read the primary pages
  yourself. Do not read anyone's digest of the numbers.
- `docs/specs/evidence-supply.md` — the fifth input, new this wave.
- `docs/plans/wave-1-handoff.md` — the whole file, before writing any code.

## Files you own
- `src/leakproof/evidence/`
- `tests/evidence/`

## Files you must not read
- `src/leakproof/labels/` — the D12 wall, and the reason this lane exists as a
  separate agent. Reading the frozen labels would make your rules agree with
  ground truth by construction and destroy the only independence metric the
  project publishes. Enforced statically by `tests/test_anticircularity.py`.
- `src/leakproof/generator/`.

## Interfaces you consume (frozen)
- `types.Finding`, `FoldedOrder`, `SellerProfile`, `CapabilityFact`,
  `Assessment`, `EligibilityCheck`, `EvidenceItem`, `Deadline`, `Citation`,
  `EvidenceSupply`, `EvidenceParse`.
- `contract.Mechanism`, `MECHANISMS_WITH_WINDOW`, `EvidenceSource`,
  `EvidenceStatus`, `WindowStatus`, `BlockerKind`, `RefundInitiator`,
  `DEFAULT_CYCLE_DAYS`.
- The two stub signatures in `evidence/__init__.py`. **You may extend them**
  with keyword parameters carrying defaults (you will need `cycle_days` and the
  seller's `EvidenceParse`); they live in a file you own, so this is not a seam
  change and needs no request.

## Deliverables
1. **Eligibility rules, cited, non-window only.** Window arithmetic is its own
   step and is never an eligibility rule. At minimum, per the premises: the
   A-to-Z exclusion (P2) and the seller-issued-refund exclusion (P3) for
   SAFE-T, each an `EligibilityCheck` with `rule_id`, a description a human can
   read on screen, and a `Citation` carrying `verified`.
2. **Where sources disagree, encode the shortest figure**, mark it
   `verified: false`, and record the alternatives in the rule's docstring. The
   SAFE-T filing window is contradicted across secondary sources (30, 60, 15
   and a 50-day figure) and the primary page is login-walled — this is the
   documented tie-break, and lane F used the same one from its own reading.
3. **Evidence table per mechanism**: `EvidenceItem(requirement, source, status,
   source_line_ids, note)`. `source` is the load-bearing field —
   `report-derivable` items you satisfy from the fold, `seller-suppliable`
   items the seller must produce, `unobtainable` items that can never exist for
   this seller (ladder step 4). `requirement` strings are a join key: the
   evidence file names them verbatim, so choose them once and keep them stable.
4. **Consume the seller's supply file.** An `EvidenceSupply` row matching
   `(order_id, requirement)` sets that item's status. An **absent file is
   "nothing asserted", not "nothing supplied"** — both land on
   BLOCKED(seller-action), but only one is a claim about the seller's filing
   cabinet, and the audit trail must be able to tell them apart later.
5. **Capability facts with validity windows.** `SellerProfile.capabilities`
   carries GST registration, program enrolment and the like, each with
   `valid_from` / `valid_to`. A requirement that depends on a capability the
   seller lacks **permanently** is `unobtainable` (step 4). Without the profile
   config, step 4 is unreachable and the case must degrade **honestly** to
   step 5 as BLOCKED(seller-action, "<item> — permanence unknown"), never
   silently to something cleaner.
6. **The awaiting-cycle case, settled.** Detector 5 emits a finding whenever
   the fee reversal is absent, including when the refund is too recent for one
   to have landed (lane J's brief says the same thing, so the two of you agree
   without talking). When `finding.event_date` is less than one full cycle
   before `folded.as_of`, the reversal item is **pending**, not missing — that
   is what puts the case at ladder step 5 as BLOCKED(timing) rather than
   letting it reach CLAIM-READY on an incomplete cycle.
7. **`deadline_for(mechanism, event_date, as_of)` → `Deadline`.** Calendar
   days, inclusive-exclusive stated explicitly in the docstring.
   `WindowStatus.NOT_APPLICABLE` for mechanisms outside
   `MECHANISMS_WITH_WINDOW`; `EXPIRED` when it has closed;
   **`START_DATE_MISSING` when a window exists but its start date does not** —
   that is data for ladder step 3 and is emphatically **not** `None` and not
   `NOT_APPLICABLE`. Collapsing those three is the single most likely way this
   lane publishes a wrong state.
8. **`assess(...)` → `Assessment`** composing 1–7, deterministic and pure: same
   inputs, same output, no clock, no network, no I/O.

## Tests required (in `tests/evidence/`)
- Hand-authored findings and folds. Never import `labels/`.
- One test per eligibility rule, firing and not firing, asserting the citation
  is present and its `verified` flag is what you claim.
- Deadline arithmetic: month-end (31 Jan + 30 days), leap day (29 Feb 2028 in
  the window), the exact expiry boundary and one day either side, and a
  `days_left` of zero.
- All four `WindowStatus` values, with a dedicated test that a missing start
  date is `START_DATE_MISSING` and not `NOT_APPLICABLE`.
- Capability permanence: unobtainable with the profile present; degraded to
  BLOCKED(seller-action, "permanence unknown") with it absent.
- Evidence supply: satisfied / pending / missing joins; a supply row for an
  unknown requirement changing nothing; an absent file leaving items at their
  default status.
- The awaiting-cycle case as pending, and the matured case as missing, on the
  same fold shape with only `as_of` moved.

## Exit criteria
`make lint` and `make verify` green. No new dependency. No system clock (D18).
No float. Conventional Commits with scope `evidence`, **committed as you go** —
small atomic commits through the work, not one tidy commit at the end. Do not
push.

## Report format
1. Summary · 2. Files · 3. Tests · 4. Interface change requests ·
5. What broke and how you got out · 6. Open questions.
