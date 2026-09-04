Lane B · Wave 1 · GitHub issue #5 · role `lp-core` (Fable, max effort) · worktree branch `lane/B-generator`

## Mission
Write the synthetic-data generator and its manifest. It produces every input
file the pipeline consumes (orders CSV, one Amazon Settlement V2 flat file per
cycle, bank CSV, seller profile) plus a manifest that records, for every
seeded discrepancy, the scenario, the order, the lines touched, and the amount
a correct detector must compute. The manifest is the ground truth every
published accuracy number is measured against, so its amounts must be exact
and its independence from the detector side must be real: your fee arithmetic
is one encoding of the public rate card, lane C's corpus is the other, and
they may never share a file.

## Governing sections (read first)
- Design doc: D9 (batches), D12 (anti-circularity; two encodings), D18
  (as_of), D20 (cycles and coverage window), D3 (paise, floor), D6 (bank leg),
  D7 (quarantine), "Detected error classes", "Inputs".
- Strategy §3 (Wave 1, lane B), §4 (seams), §8 (risks).
- `docs/specs/amazon-settlement-v2.md` (the layout you write; note every
  `verified: false` row and follow it anyway, corrections come from the
  integrator).
- `docs/research/ratecard-sources.md` (URLs only, by design). Fetch the fee
  numbers from those primary or secondary sources yourself, with the browse
  skill (run browse with the sandbox disabled; it cannot bind a port inside
  it), and record for each number the URL and as-of date in your module's
  docstring. That record is what makes "two independent encodings" auditable.
- `docs/plans/briefs/README.md`, "Decisions carried into every brief": the
  three category identifiers are pinned to one Amazon.in fee-category node
  each (`contract.CATEGORY_NODES`); encode that node's tiers. Three 2026
  effective dates exist; the demo batch's `as_of` (late August 2026) falls
  between the June 10 and September 7 changes, so encode the schedule in
  force on `as_of` and say which one in the manifest's `generator_version`.
- `docs/research/amazon-v2-sample.md` (RS1) §1 and §4: write amounts with `.`
  as the decimal separator and dates as `YYYY-MM-DD`, keep `transaction-type`
  strings exactly as the contract tables give them, and expect the parser to
  case-fold.

## Files you own
- `src/leakproof/generator/` (everything under it)
- `tests/generator/`

## Files you must not read, open, grep, or import
- `src/leakproof/ratecard/`, `src/leakproof/labels/`, `src/leakproof/evidence/`,
  `src/leakproof/detect/`. The D12 test walks your import graph statically
  and fails the build on any path to them. The reviewer greps for the names.

## Interfaces you consume (frozen)
- `contract.py`: `Paise`, `apply_bp` (the one rounding rule; use it for every
  percentage), `MATERIALITY_FLOOR_PAISE`, `make_line_id`, `DEFAULT_CYCLE_DAYS`,
  `LINE_VOCABULARY` / `AMOUNT_TYPE_VOCABULARY` / `TransactionType` (write the
  raw strings by inverting these tables so lane D's parser and your writer
  agree by construction), `RefundInitiator`.
- `scenarios.py`: `Scenario`, `SCENARIOS`, `SEEDED_ERROR_SCENARIOS`.
- `types.py`: `Manifest`, `SeededError`, `CoverageWindow`, `SellerProfile`,
  `CapabilityFact`.
- `serialize.py`: `dumps` for the manifest and profile JSON.

## Deliverables
1. `generate_batch(*, batch_id, seed, order_count, errors_per_class, out_dir, as_of=None) -> Manifest`
   (signature in the stub), writing into `out_dir`:
   `orders.csv`, `settlement_<end-date>.txt` per cycle, `bank.csv`,
   `seller_profile.json`, `manifest.json`.
2. Presets, as a small registry the CLI can call by name:
   `demo` (150 orders, about 20 seeded errors, 4 cycles),
   `measure` (500 orders, 20 per class × 6 classes, seeds 1–5),
   `throughput` (10,000 orders, seeded errors at the measure ratio),
   `malformed` (the demo batch with its settlement file saved as CSV),
   `uncovered` (every order in categories outside the declared three),
   `clean` (zero seeded errors, zero material discrepancies).
3. `load_manifest(path) -> Manifest` and `write_manifest(manifest, path)`.
4. Scenario coverage: every `SEEDED_ERROR_SCENARIOS` member appears in the
   measure batch; true negatives (`C5_REVERSED_LATER_CYCLE`,
   `C6_PAID_LATER_CYCLE`), dispositions (`C6_OUT_OF_WINDOW`, `BELOW_MATERIALITY`,
   `QUARANTINE_MALFORMED` in the malformed preset, `UNCOVERED_CATEGORY`) and
   `DUPLICATE_UTR` are seeded and listed in the manifest with
   `expected_class = None`.
5. Realism that matters to detectors: fees carry GST as a separate `FEE_TAX`
   line; refunds post a commission reversal and a refund administration fee;
   TCS and TDS lines per order; promotions and shipping fees as acknowledged
   deductions; a reserve line per settlement; each settlement file's summary
   row `total-amount` equals the sum of its lines; each bank credit equals one
   settlement's total (except the duplicate-UTR case); class-6 orders are
   delivered inside the coverage window and absent from every file.
6. `as_of` defaults to the batch's max settlement posted-date; the manifest
   records it and the coverage window; C5 "awaiting cycle" and C6 "paid later
   cycle" cases are placed relative to `as_of` and `cycle_days` so the D20
   rules have something to bite on.

## Tests required (in `tests/generator/`)
- `test_determinism`: same seed → byte-identical files and manifest.
- `test_seeded_amounts_are_material`: every `expected_amount_paise` ≥ 2× floor.
- `test_scenario_coverage`: measure batch contains every seeded-error scenario;
  per-class counts equal `errors_per_class`.
- `test_v2_layout`: header row, summary row, 24 tab-separated columns on every
  transaction row, raw strings from the contract tables, dates in the spec's
  formats, amounts with two decimals and no thousands separator.
- `test_totals_reconcile`: per file, sum of line amounts == summary
  `total-amount`; bank credits match payout totals; the duplicate-UTR case is
  the only exception and is listed in the manifest.
- `test_as_of_and_coverage`: default `as_of` rule; every non-out-of-window
  delivery inside the window; the out-of-window case outside it.
- `test_presets`: each preset generates; `malformed` produces a single-column
  file; `clean` produces no material discrepancy.
- The existing `tests/test_anticircularity.py` must stay green.

## Exit criteria
`uv sync`, then `make lint` and `make verify` green in your worktree. No new
dependency. Integer paise everywhere; percentages only through `apply_bp`. No
`date.today()`. Conventional Commits with scope `generator`. Do not push.

## Report format
1. Summary · 2. Files · 3. Tests (pasted `make lint && make verify` tail) ·
4. Interface change requests (anything you needed in `contract.py`, `types.py`,
`scenarios.py`, or the spec; state it precisely) · 5. What broke and how you
got out (or "nothing broke") · 6. Open questions (include: which fee numbers
you could only get from secondary sources, with URLs).
