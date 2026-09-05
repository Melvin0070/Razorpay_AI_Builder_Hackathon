Lane L · Wave 3 · GitHub issue #15 · role `lp-logic` (Opus, high effort) ·
worktree branch `lane/L-triage`

**Demo-priority note (2026-09-05):** this build is compressing waves 2-5 into
one push toward a working `make demo` for a pitch video. Keep the hard
invariants (both additivity identities, exactly-one-state, the per-order sum
invariant) real and property-tested — they are what makes the published
numbers trustworthy on camera. Where the brief below asks for an exhaustive
edge-case matrix beyond that, use judgement to trim it if it costs you more
than about twenty minutes; a smaller green suite that ships beats a stalled
lane. Skip filing an elaborate interface-change-request writeup — a one-line
note in your report is enough.

## Mission
Turn a batch of `Finding` + `Assessment` pairs into the dashboard's actual
payload: dedup discrepancies onto one exception per `(order_id, class,
claimed_line_id | null)`, resolve the overlap matrix for findings that share an
order, run every exception through the seven-step precedence ladder to get a
`StateResult`, partition every rupee into exactly one of seven lines, sort the
queue, and assemble the `BatchReport`. This is the module every other Wave 3/4
piece and the dashboard read from — get the ladder or the partition wrong and
every number on screen is wrong, silently.

## Governing sections (read first)
- Design doc: the full "Evidence-state model" section (state derivation, the
  seven-step precedence ladder, verbatim), "Rupee partition (7 lines)", D19
  (dedup key, the 15-cell overlap matrix, the per-order sum invariant), D10
  (hard gates: both additivity identities, exactly-one-state property test,
  per-order sum invariant; match rate is lane H's, not yours to recompute).
- ADR-0004 (`AuditAction.FLAG` — UNEXPLAINED gets its own gate action, not a
  gate you build, but the state your ladder assigns must line up with it).
- ADR-0007 (six fixed override labels — you produce `not_claimable_reason` and
  `blocker_kind`; lane O's label table is a total function over what you emit,
  so use exactly `NotClaimableReason` and `BlockerKind` from `contract.py`,
  never a bespoke string).
- `docs/plans/wave-1-handoff.md`.

## Files you own
- `src/leakproof/triage/`
- `tests/triage/`

## Files you must not read
- None, but build against `types.py` and hand-authored fixtures rather than
  importing lanes H/J/K/M's implementations — they may still be mid-flight in
  this push. Your only real dependency is the frozen dataclass shapes.

## Interfaces you consume (frozen, in `types.py`)
- `Finding`, `Assessment`, `EligibilityCheck`, `Deadline`, `EvidenceItem`,
  `StateResult`, `RupeeLines`, `TriagedFinding`, `BatchReport`,
  `DispositionCounts`, `MatchRates`, `BankLegResult`, `Manifest`.
- `contract.State`, `BlockerKind`, `NotClaimableReason`, `RupeeLine`,
  `ErrorClass`, `Mechanism`, `is_material`, `MATERIALITY_FLOOR_PAISE`.
- The stub signatures in `triage/__init__.py`.

## Deliverables
1. **Dedup.** Group findings by `finding.finding_id` (already the D19 key).
   Where lane J or K's fixtures hand you two `Finding`s claiming the exact same
   key (should not happen if `make_finding` is correct upstream, but your code
   must not silently drop one) — keep the first by a documented, deterministic
   tie-break and note it.
2. **Overlap matrix.** A lookup covering all 15 unordered pairs among
   `{1,2,5,6,7,8}`, each `co-fire | mutually-exclusive | precedence(n)`.
   Default every pair to `co-fire` (they are independent discrepancy axes on
   the same order) unless you can show the two detectors' firing preconditions
   are logically incompatible on the same `FoldedOrder` — document your
   reasoning for every non-default pair in the module docstring, one line each.
   The matrix only needs to gate what happens when two exceptions from the
   same order and pair land in the queue together; it does not change either
   exception's own state.
3. **The precedence ladder, as ordered code, exactly this order:**
   ```
   0.  mechanism none            -> UNEXPLAINED(basis)
   0b. mechanism CA-review       -> BLOCKED(professional-review, "CA review")
   1.  any eligibility check failed          -> NOT-CLAIMABLE(rule)
   2.  deadline.status == EXPIRED            -> NOT-CLAIMABLE(window expired)
   3.  deadline.status == START_DATE_MISSING -> BLOCKED(timing, "window start date missing")
   4.  any evidence item source == unobtainable -> NOT-CLAIMABLE(evidence unobtainable)
   5.  any evidence item status in {missing, pending} -> BLOCKED(blocker_kind, named item)
   6.  otherwise                             -> CLAIM-READY
   ```
   First match wins. `precedence_step` on `StateResult` records which step
   fired (0-6). `reason` is a human-readable string naming the rule id, window
   fact, or evidence requirement — this is what renders on screen, so make it
   read like the design doc's own examples ("window expired 21 Aug — SAFE-T, 7
   days ago"), not an enum's repr.
4. **Rupee partition, pure function of (class-bucket, state):**
   ```
   class in {1,2,5,6}: CLAIM-READY -> claim_ready | BLOCKED -> blocked | NOT-CLAIMABLE -> not_claimable
   class 7:             any state  -> tax_review
   class 8:             UNEXPLAINED -> unexplained
   below materiality (any class):   -> below_materiality, never queued, never in identified
   ```
   Also populate `not_claimable_rule` / `not_claimable_window_expired` /
   `not_claimable_evidence_unobtainable` (the reason breakout the design doc
   calls "the most persuasive number in the product") and every `*_count`
   field on `RupeeLines`. `identified` and `total` are properties already —
   never store them separately.
5. **Queue sort.** Group by state (CLAIM-READY, BLOCKED, UNEXPLAINED,
   NOT-CLAIMABLE), then deadline ascending (nulls last), then rupees
   descending.
6. **`run_batch(findings, assessments, ...) -> BatchReport`** — the assembly
   function the integrator wires into `cli.py`. Accept `match_rates`,
   `dispositions`, `bank_leg`, `coverage`, and the batch-level fields
   (`batch_id`, `marketplace`, `as_of`, `cycle_days`, `settlement_ids`,
   `order_count`, `rate_card_coverage`) as parameters rather than computing
   them yourself — lanes H and the integrator own those. Leave `queue[i].draft`
   and `.gate` as `None`; lane M and O fill them in later passes over the same
   `TriagedFinding` list (document this two-pass shape in your docstring so the
   integrator knows to call your assembly again, or a merge helper, once drafts
   exist).

## Tests required (in `tests/triage/`, trim to the essentials under time pressure)
- One test per ladder step, hand-authored `Finding`+`Assessment` pairs, each
  asserting the exact `state`, `precedence_step` and `blocker_kind` /
  `not_claimable_reason`.
- Property test (hypothesis, or a handful of hand-picked cases if hypothesis
  is too slow to set up): every finding lands in exactly one state.
- Property test: `rupee_lines.identified + tax_review + unexplained +
  below_materiality == total` and `identified == claim_ready + blocked +
  not_claimable` — both additivity identities, on a batch of ≥ 10 mixed
  fixtures.
- Per-order sum invariant: sum of exception amounts on one order ≤ that
  order's total deductions (construct the deductions figure in the fixture).
- Dedup test: two findings with the same `finding_id` collapse to one.
- Overlap-matrix smoke test: assert all 15 pairs are present (no `KeyError` on
  any pair), not necessarily one test per pair.

## Exit criteria
`make lint` and `make verify` green. No new dependency. No system clock; take
`as_of` as a parameter throughout. No float on the money path. Conventional
Commits, scope `triage`, committed as you go. Do not push.

## Report format
1. Summary · 2. Files · 3. Tests · 4. Interface change requests ·
5. What broke and how you got out · 6. Open questions.
