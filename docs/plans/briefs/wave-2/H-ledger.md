Lane H · Wave 2 · GitHub issue #11 · role `lp-logic` (Opus, high effort) · worktree branch `lane/H-ledger`

## Mission
Build the canonical ledger: fold every settlement line onto its order across
cycles, in cycle order with a deterministic tiebreak, check the batch's
declared coverage window, and join orders to settlements exactly. Detectors
consume `FoldedOrder` and never a raw line (D20), so a fold that loses a line,
orders two lines nondeterministically, or drops an order with no lines at all
silently deletes findings downstream — three of the four detector classes read
your output as their only input.

## Governing sections (read first)
- Design doc: D20 (cross-cycle composition, cycle-ordered list, deterministic
  tiebreak, coverage window, the three false positives it prevents), D7
  (quarantined rows stay in the match-rate denominator), D10 (match-rate
  definitions), the D5-CUT note (the matcher is an **exact** join on order id;
  do not reintroduce fuzzy matching, blocking, or an AMBIGUOUS disposition).
- Strategy §3 (Wave 2, lane H), §4.
- `docs/plans/wave-1-handoff.md` — the whole file, before writing any code.

## Files you own
- `src/leakproof/ledger/`
- `tests/ledger/`

## Files you must not read
- None. (`generator/` is readable, but note that reading it teaches you the
  answer to your own tests; prefer hand-authored fixtures.)

## Interfaces you consume (frozen)
- `types.BatchInputs`, `SettlementFileParse`, `SettlementLine`, `OrdersParse`,
  `Order`, `CoverageWindow`, `FoldedOrder`, `MatchResult`, `MatchRates`.
- `contract.LineKind`, `TransactionType`, `DEFAULT_CYCLE_DAYS`, `Paise`.
- The two stub signatures in `ledger/__init__.py`.

## Deliverables
1. `fold_batch(inputs) -> tuple[FoldedOrder, ...]`, deterministic and total:
   every settlement line in every file lands on exactly one `FoldedOrder`, and
   the union of all `lines` is the input line set. Prove it with a test, not a
   docstring.
2. **Three order populations, all folded, none dropped:**
   - order in the export with settlement lines → normal fold;
   - order in the export with **no** settlement lines → `FoldedOrder` with
     `lines = ()` and `order` set. Detector 6 is an absence detector; if you
     drop these, class 6 can never fire and you will not find out until Wave 3.
   - settlement lines whose `order_id` is absent from the export → `order =
     None` (orphan). These populate `MatchResult.orphan_order_ids`.
   A line with no `order_id` at all belongs to no order: exclude it from the
   fold, and say in your report how the batch-level lines (transfers, reserves)
   are reached later, since nothing else in the pipeline holds them yet.
3. **Cycle order and the tiebreak.** `lines` sorted by `(posted_date,
   settlement cycle index, LineKind declaration order, line_id)`;
   `settlement_ids` in cycle order, oldest first, deduplicated. The cycle index
   comes from the settlement header's `start_date` (files are not guaranteed to
   arrive in order). The tiebreak must be total — a property test asserts that
   shuffling the input files and the lines within them yields a byte-identical
   fold.
4. **Coverage window (D20).** `in_coverage` is False when the order's
   `delivery_date` falls outside `inputs.coverage`; an order with no
   `delivery_date` is in coverage (absence of a date is not evidence of being
   outside the window — say so in the docstring). Lane L counts the
   `OUT_OF_WINDOW` disposition off this flag; you do not build
   `DispositionCounts`.
5. `match(inputs, folded, *, class6_flagged: int = 0) -> MatchResult`. The
   keyword is yours to add — the seam type `MatchRates` carries
   `class6_flagged`, but detectors have not run when you are called, so lane L
   calls you a second time with the count. Document that in the docstring;
   do not file a seam change for it.
6. **Match rates exactly as D7 and D10 define them.** `total_orders` counts
   orders in the seller's export (orphans are reported, never a denominator);
   `quarantined_rows` is the sum of every parse's quarantine and **stays in the
   denominator**; strict = matched / total; adjusted = matched / (total −
   class6_flagged). Both are on `MatchRates` already — your job is to populate
   its four integers correctly, and a test must pin the denominator question
   with a batch that has quarantined rows.

## Tests required (in `tests/ledger/`)
- Line conservation: folded line multiset == input line multiset.
- Shuffle-invariance property test (hypothesis): file order and within-file row
  order do not change the fold.
- Three-population test: export-only order, orphan-only order, and the normal
  case, in one batch.
- Tiebreak test: two lines, same `posted_date`, different kinds → the kind
  order decides; same kind → `line_id` decides.
- Cross-cycle test: a refund in cycle 1 and its reversal in cycle 3 fold onto
  one order in that order (this is the false positive D20 exists to prevent).
- Coverage-window test: delivery inside, outside, and `None`.
- Match-rate test with quarantined rows in the denominator, and a second with
  `class6_flagged` set, pinning both rates as fractions you compute by hand.

## Exit criteria
`make lint` and `make verify` green. No new dependency. No system clock (D18);
`as_of` comes from `inputs`. No float on the money path. Conventional Commits
with scope `ledger`, **committed as you go** — small atomic commits through the
work, not one tidy commit at the end. Do not push.

## Report format
1. Summary · 2. Files · 3. Tests · 4. Interface change requests ·
5. What broke and how you got out · 6. Open questions.
