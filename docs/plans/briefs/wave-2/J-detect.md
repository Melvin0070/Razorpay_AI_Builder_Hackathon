Lane J · Wave 2 · GitHub issue #13 · role `lp-core` (Fable, max effort) · worktree branch `lane/J-detect`

## Mission
The six detectors and the one constructor they all emit through. This is the
money path: a silent error here publishes a wrong rupee amount with a citation
attached to it, which is worse than finding nothing. Every number you emit
traces to a source row, and every rate comes from the rate card at `as_of` —
never from a literal in your code.

## Governing sections (read first)
- Design doc: D23 (detector shape, `make_finding` invariants, the class table
  as executable code), the class table itself, D1, D3 (materiality floor,
  tolerance, integer paise), D19 (one exception per discrepancy; dedup keys on
  `(order_id, class, claimed_line_id | null)`; **referencing a line is free,
  claiming it is not**; the per-order sum invariant), D20 (cycle rules for 5
  and 6).
- **ADR-0008** — TCS is the 0.5% aggregate; the design doc's 1% is stale and
  is the statutory ceiling, not a recomputation basis. Read it before writing
  detector 7. Do not "fix" the code to match the doc.
- **ADR-0005** — line vocabulary; class-6 amount is principal **+ tax**, not
  principal alone; the `audited` / acknowledged split that keeps class 8 from
  flooding with every expected deduction.
- ADR-0002 (`Finding`, never `Exception`).
- `docs/plans/wave-1-handoff.md` — the whole file, before writing any code.

## Files you own
- `src/leakproof/detect/` (including a new `registry.py`)
- `tests/detect/`

## Files you must not read
- `src/leakproof/generator/` — the D12 wall. It encodes the same public rate
  card you are checking against; reading it makes your detector agree with the
  data by construction and destroys the ₹-agreement metric.
- `src/leakproof/labels/` — ground truth. Same reason.
- The import test `tests/test_anticircularity.py` enforces both statically.

## Interfaces you consume (frozen)
- `types.FoldedOrder`, `DetectorContext`, `Finding`, `RecomputationRow`,
  `RateCard`, `RateRule`, `LookupMiss`, `SlabBasis`.
- `contract.ErrorClass`, `Mechanism`, `ALLOWED_MECHANISMS`,
  `PRIMARY_MECHANISM`, `LineKind`, `TransactionType`, `UnexplainedBasis`,
  `apply_bp`, `compare_paise`, `is_material`, `MATERIALITY_FLOOR_PAISE`,
  `TOLERANCE_PAISE`, `DEFAULT_CYCLE_DAYS`.
- The `Detector` protocol and stub signatures in `detect/__init__.py`.

## Deliverables
1. **`make_finding(...)`, typed, the only way a `Finding` is constructed.**
   Raises on: empty `source_line_ids`; a `claimed_line_id` not among them; a
   mechanism the class table forbids (`ALLOWED_MECHANISMS`); a non-positive
   `amount_paise`; a `recomputation` that does not arrive at `amount_paise`.
   The stub's `**fields: object` signature is a placeholder — give it real
   parameters. One test per raise.
2. **The rate card is the only source of rates.** For a banded kind, ask
   `ctx.rate_card.band_basis(kind)` for the figure the band is read on and
   compute the band key from the order — `UNIT_ITEM_PRICE` is
   `principal // quantity`, `BUYER_PAID_ITEM_PRICE` is what the buyer paid
   including seller shipping and gift wrap. Never hard-code which kind uses
   which; the seam answers it. A rate literal anywhere in `detect/` is a
   review rejection.
3. **Lookup misses are not findings.** A `LookupMiss` with `UNCOVERED` means
   this order is outside declared coverage: emit nothing and let lane L count
   the disposition. `CONFIG_ERROR` is a build failure, not a finding — surface
   it, never swallow it.
4. **Detector 1, commission overcharge.** Rate-card percentage vs charged, on
   the commission lines the fold carries. Mechanism `support-ticket`
   (ADR-0006 — **not** SAFE-T). Claims the commission line.
5. **Detector 2, fixed/closing fee.** Slab lookup vs charged, band key per
   deliverable 2. `C2_SLAB_BOUNDARY` exists because a band edge is where this
   detector is wrong; test both sides of an edge and the edge itself.
6. **Detector 5, refund without fee reversal.** A refund event with no matching
   fee reversal anywhere in the fold, across every cycle. **Emit the finding
   whenever the reversal is absent, including when the refund is too recent for
   a reversal to have landed** — the immaturity is not yours to suppress. Set
   `event_date` to the refund date and let lane K express the cycle question as
   a *pending* evidence item; the frozen label for `C5_AWAITING_CYCLE` expects
   BLOCKED(timing) at ladder step 5, which only exists if you emitted a
   finding. (Integrator's reading of D20's "fires only when"; it is settled,
   build to it.) Mechanism SAFE-T. This is an absence-type finding: it may have
   `claimed_line_id = None` (D19).
7. **Detector 6, unpaid order past cycle.** A delivered order absent from every
   settlement more than two cycles (`2 × ctx.cycle_days`) after delivery,
   measured against `ctx.batch_max_settlement_date`. Amount is **principal +
   tax** (ADR-0005 §5). Pure absence: `source_line_ids` cannot be settlement
   lines, so cite the order row. Mechanism `support-ticket`.
8. **Detector 7, TCS/TDS mismatch.** Per ADR-0008: sum every `LineKind.TCS`
   line on the order and compare the **aggregate** against the rate in force at
   `as_of`; do not check CGST/SGST legs individually, because the settlement
   file does not state place of supply and LeakProof does not infer it. TDS
   (194-O) the same way against its own rule. Mechanism `CA-review`, which
   ladder step 0b turns into BLOCKED — class 7 never reaches CLAIM-READY.
9. **Detector 8, unexplained deduction.** A deduction with no rule basis, above
   the floor. `unexplained_basis` is `CODE_UNSEEN` when the vocabulary does not
   know the code (`LineKind.UNCLASSIFIED`) and `CODE_KNOWN_NO_RULE` when the
   rate card declares the kind but has no audited rule for it. An
   *acknowledged* kind (ADR-0005) is a known deduction and fires nothing.
   Mechanism `none`.
10. **`registry.py`** exporting `DETECTORS` in a fixed order and
    `run_detectors(folded, ctx)`. Register your gate callables here for the
    integrator to wire into `cli.hard_gates()` — **never** into
    `leakproof/gates.py`, which is imported by every walled package and would
    fail the wall test (this bit lane C for real; the rule is in `gates.py`'s
    docstring).
11. **Materiality.** Below `MATERIALITY_FLOOR_PAISE`, a discrepancy is never
    queued. Whether it is counted is lane L's problem; yours is not to emit it
    as a finding.

## Tests required (in `tests/detect/`)
- Hand-authored `FoldedOrder`s only. Do not import the generator or a manifest.
- One `make_finding` test per raise condition.
- Per detector: one firing case, one near-miss inside tolerance that must **not**
  fire, one below-materiality case, one `UNCOVERED` case emitting nothing.
- Detector 2 at a slab edge, both sides plus the edge.
- Detector 5 with the reversal present in a later cycle (no finding) and absent
  (finding), on the same fold shape.
- Detector 6 at exactly two cycles and one day past (the boundary is where an
  absence detector is wrong).
- Detector 7 with an intra-state two-leg order and an inter-state single-leg
  order both at the correct aggregate → no finding; one leg perturbed → finding
  whose amount is the aggregate difference.
- A test asserting no module under `detect/` contains a rate literal, or a
  documented reason why the check cannot be written that way.
- Property test: for any folded order, Σ finding amounts ≤
  `folded.deductions_paise` (the per-order sum invariant, D19), with class 6
  bounded by the order's own value instead.

## Exit criteria
`make lint` and `make verify` green. No new dependency. No system clock (D18);
everything reads `ctx.as_of`. No float on the money path. Conventional Commits
with scope `detect`, **committed as you go** — small atomic commits through the
work, not one tidy commit at the end. Do not push.

## Report format
1. Summary · 2. Files · 3. Tests · 4. Interface change requests ·
5. What broke and how you got out · 6. Open questions.
