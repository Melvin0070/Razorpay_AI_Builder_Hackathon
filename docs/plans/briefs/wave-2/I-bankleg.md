Lane I · Wave 2 · GitHub issue #12 · role `lp-build` (Sonnet, high effort) · worktree branch `lane/I-bankleg`

## Mission
Two independent, small deliverables. First, the bank leg (D6): reconcile each
settlement payout total against a bank UTR credit, honestly, and keep it out of
the match rate. Second, the parser for `evidence.csv` — the fifth input, spec'd
this wave, which the SAFE-T path is currently blocked without.

## Governing sections (read first)
- Design doc: D6 (payout-level only; reported as a demonstrated reconciliation
  step, **excluded from the match-rate denominator**, because the generator
  writes both sides; duplicate UTR credits at the same amount on the same day
  must not double-satisfy one payout), D7 (quarantine with row-level reasons).
- `docs/specs/evidence-supply.md` — the whole spec, it is short and it is new.
- `docs/plans/wave-1-handoff.md` §"Must-carry-forward facts" item 6.
- Existing parsers `src/leakproof/ingest/orders.py` and `ingest/bank.py`: your
  evidence parser matches their shape, error vocabulary and hint rule. Copy the
  house style rather than inventing a fifth one.

## Files you own
- `src/leakproof/bankleg/`, `tests/bankleg/`
- `src/leakproof/ingest/evidence.py`, `tests/ingest/test_evidence.py` (new
  files only — do not edit the Wave 1 parsers; if one needs a change, file it
  as an interface change request instead)

## Files you must not read
- None.

## Interfaces you consume (frozen)
- `types.SettlementHeader`, `BankCredit`, `BankParse`, `BankLegResult`,
  `EvidenceSupply`, `EvidenceParse`, `QuarantinedRow`.
- `contract.EvidenceStatus`, `make_line_id`, `Paise`, `compare_paise`,
  `TOLERANCE_PAISE`.
- The stub signature in `bankleg/__init__.py`.

## Deliverables — bank leg
1. `reconcile_payouts(headers, credits) -> BankLegResult`. A payout matches a
   credit when the amounts agree within `TOLERANCE_PAISE` and the credit date
   is on or after the settlement's `deposit_date`; never on narration text.
2. **One credit satisfies at most one payout.** Duplicate UTRs at the same
   amount on the same day are the case D6 names explicitly: report them in
   `duplicate_credit_utrs` and let them satisfy exactly one payout, not two.
   The matching must be deterministic under input reordering — a greedy pass
   over an unsorted list is not.
3. `unmatched_settlement_ids` for payouts with no credit. Never invent a
   partial match; a payout is matched or it is not.
4. The result is reported beside the match rate and never inside it. Add a test
   whose name says so, so a later lane cannot quietly fold it in.

## Deliverables — evidence parser
5. `parse_evidence(path_or_text, source_file) -> EvidenceParse` following
   `docs/specs/evidence-supply.md` exactly: four columns, `line_id` on every
   row, `status` from `EvidenceStatus`, `supplied_on` **required** when
   `satisfied` and **forbidden** otherwise, duplicate `(order_id, requirement)`
   pairs quarantining the whole duplicate set, `requirement` preserved
   byte-for-byte, one actionable `hint` per file at most.
6. Every quarantine reason quotes the literal offending value. A row is never
   dropped and never coerced (D7).

## Tests required
- Bank leg: exact match; within-tolerance match; duplicate UTR same
  amount/day satisfying exactly one payout; unmatched payout; determinism
  under shuffled input; a test asserting the result is absent from every
  match-rate computation.
- Evidence parser: each of the six quarantine conditions in the spec, one test
  each, asserting the reason names the offending value; a clean three-row file;
  a duplicate-pair file; an empty file (header only) parsing to zero supplies
  and no quarantine; `requirement` with surrounding whitespace and internal
  double spaces surviving verbatim.

## Exit criteria
`make lint` and `make verify` green. No new dependency. No system clock. No
float on the money path. Conventional Commits with scopes `bankleg` and
`ingest`, **committed as you go** — small atomic commits through the work, not
one tidy commit at the end. Do not push.

## Report format
1. Summary · 2. Files · 3. Tests · 4. Interface change requests ·
5. What broke and how you got out · 6. Open questions.
