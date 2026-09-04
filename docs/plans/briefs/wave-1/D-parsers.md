Lane D · Wave 1 · GitHub issue #7 · role `lp-build` (Sonnet, high effort) · worktree branch `lane/D-parsers`

## Mission
Write the parsers for the four inputs (Amazon Settlement V2 flat file, orders
CSV, bank CSV, seller profile JSON) with quarantine instead of exceptions:
every malformed row is kept, cited by its physical line, and given a reason a
person can act on. Quarantined rows stay in the match-rate denominator (D7),
and unknown fee codes become unclassified lines rather than disappearing (D4).

## Governing sections (read first)
- Design doc: D4, D7, D3, "Inputs", wireframe frame 4 ("Nothing parsed").
- `docs/specs/amazon-settlement-v2.md`: the layout, the vocabulary tables, and
  the companion-input formats. This is your reference; follow it even where
  rows are `verified: false`. If `docs/research/amazon-v2-sample.md` (RS1) has
  merged and disagrees, follow the spec and list the disagreement under
  "Interface change requests".
- Strategy §3 (Wave 1, lane D), §4.

## Files you own
- `src/leakproof/ingest/`
- `tests/ingest/` and `tests/fixtures/ingest/` (small hand-authored files)

## Files you must not read
- None. You have no ground-truth wall.

## Interfaces you consume (frozen)
- `contract.classify_line`, `classify_transaction`, `make_line_id`, `Paise`.
- `types.SettlementHeader`, `SettlementLine`, `SettlementFileParse`, `Order`,
  `OrdersParse`, `BankCredit`, `BankParse`, `QuarantinedRow`, `SellerProfile`,
  `CapabilityFact`.

## Deliverables
1. `parse_settlement_file(path) -> SettlementFileParse`: tab-split, header
   row validated against the 24 column names, summary row into
   `SettlementHeader`, each transaction row into `SettlementLine` with
   `line_id = make_line_id(path.name, physical_row)` (header is row 1),
   amounts parsed from the decimal string straight to integer paise (no
   float; reject thousands separators), dates parsed per the spec, `kind`
   via `classify_line`, `txn_type` via `classify_transaction`.
2. Quarantine reasons, each exact and stable (they are shown on screen):
   `expected 24 tab-separated columns, found N`; `amount not numeric: '...'`;
   `bad date in <column>: '...'`; `missing order-id on Order row`; `unknown
   header layout`; plus whatever else you find necessary, listed in a module
   docstring.
3. `hint`: when every data row has one column, "the file was saved as CSV;
   Amazon Settlement Flat File V2 is tab-separated". When the header is
   missing or unknown, a hint naming the expected first column.
4. `parse_orders(path) -> OrdersParse` and `parse_bank(path) -> BankParse`
   per the companion formats, with the same quarantine discipline
   (`delivery_date before order_date` is a quarantine reason; empty
   `delivery_date` is not).
5. `load_profile(path) -> SellerProfile`.
6. A `discover_batch(dir) -> BatchInputs`-style helper is NOT yours; the
   integrator assembles `BatchInputs` in `cli.py`. Keep your functions pure
   file-in, record-out.

## Tests required (in `tests/ingest/`)
- Golden parse of a hand-authored four-row settlement file: header, summary,
  two lines, with every field asserted, including `line_id` row numbers.
- One test per quarantine reason.
- Saved-as-CSV file → every row quarantined, `hint` set, header still
  reported.
- Unknown `amount-description` → `LineKind.UNCLASSIFIED` with raw strings
  retained; unknown `transaction-type` → `TransactionType.OTHER`.
- Amount strings: `-487.50` → `-48750`; `0.00` → `0`; `1,240.00` →
  quarantined; `12.345` → quarantined.
- Orders and bank parsers: golden files plus one quarantine each.
- Profile: capability windows round-trip.

## Exit criteria
`make lint` and `make verify` green. No new dependency (stdlib `csv` is
fine). No float on any amount. Conventional Commits with scope `ingest`. Do
not push.

## Report format
1. Summary · 2. Files · 3. Tests · 4. Interface change requests ·
5. What broke and how you got out · 6. Open questions.
