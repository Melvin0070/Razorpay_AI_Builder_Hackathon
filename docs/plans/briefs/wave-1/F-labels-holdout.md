Lane F · Wave 1 · GitHub issue #9 · role `lp-logic` (Opus, high effort) · worktree branch `lane/F-labels-holdout`

## Mission
Author the ground truth for claimability, before any eligibility rule exists
in code (D12): one label per seeded-error scenario saying which state it must
land in, at which precedence step, and why, each with a citation to the policy
page you read. Then author the 25-case adversarial holdout: cases the
generator never produces, in canonical `FoldedOrder` form, with expected
outcomes. Your file is frozen at the Wave 1 close; the integrator records its
checksum in `contract.py`, and changing it afterwards takes ADR-0003.

You are policy reader number one. Lane K (eligibility rules, Wave 2) is a
different agent and will read the same primary pages without seeing your
labels. Do not summarise the rules anywhere outside the label rationales.

## Governing sections (read first)
- Design doc: D12 (all of it, including the known limit), premises P2 and P3,
  "Evidence-state model" (the seven-step ladder: your labels name steps),
  D14, D18 (calendar days), D19, D20.
- `docs/research/safe-t.md` (RS2): the source list and claim examples. Read the
  primary pages it lists yourself, with the browse skill. Never enter
  credentials; login-walled pages get `verified: false` with the secondary
  source you used instead.
- ADR-0003, ADR-0005. Strategy §1, §3 (lane F), §4.

## Files you own
- `src/leakproof/labels/` (`claimability.json`, `holdout/`, loaders)
- `tests/labels/`

## Files you must not read
- `src/leakproof/evidence/`, `src/leakproof/ratecard/`, `src/leakproof/generator/`,
  `docs/research/ratecard-sources.md`. The D12 test walks your imports; the
  reviewer greps for the names.

## Interfaces you consume (frozen)
- `scenarios.py`: `Scenario`, `SCENARIOS`, `SEEDED_ERROR_SCENARIOS`.
- `types.ClaimabilityLabel`, `HoldoutCase`, `FoldedOrder`, `SettlementLine`,
  `Order`, `SellerProfile`, `CapabilityFact`, `Citation`.
- `contract.State`, `BlockerKind`, `NotClaimableReason`, `ErrorClass`,
  `Mechanism`, `LineKind`, `TransactionType`, `make_line_id`, `rupee_line_for`.

## Deliverables
1. `src/leakproof/labels/claimability.json`: one entry per member of
   `SEEDED_ERROR_SCENARIOS` with `scenario`, `expected_state`,
   `expected_precedence_step`, `expected_blocker_kind` (BLOCKED only),
   `expected_not_claimable_reason` (NOT-CLAIMABLE only), `rationale` (two or
   three sentences, in your words, naming the policy fact that decides it),
   `citation {label, url, as_of, verified}`.
2. `load_labels(path=None) -> dict[Scenario, ClaimabilityLabel]` with
   validation: every seeded scenario present, no extras, step/state/reason
   combinations consistent with the ladder (step 0 ⇒ UNEXPLAINED; 0b ⇒ BLOCKED
   professional-review; 1 ⇒ NOT-CLAIMABLE rule; 2 ⇒ NOT-CLAIMABLE
   window-expired; 3 ⇒ BLOCKED timing; 4 ⇒ NOT-CLAIMABLE evidence-unobtainable;
   5 ⇒ BLOCKED; 6 ⇒ CLAIM-READY).
3. `src/leakproof/labels/holdout/cases.py`: 25 `HoldoutCase` literals,
   `load_holdout()`. Each case is a `FoldedOrder` (lines with real
   `line_id`s, `as_of` explicit) plus a `SellerProfile`, and expected
   `class`, `state`, `reason`, `amount`. Cover at least: amount exactly at
   the ±₹1 tolerance on both sides; a discrepancy exactly at the ₹10 floor;
   a reversal split across two lines; a cycle-3 reversal that must cancel a
   cycle-1 finding (D20); an order that co-fires class 1 and class 5 with
   additive amounts (D19); an order absent from the seller's export; a
   capability whose validity window ended before the event (step 4 with
   validity, the SPF/VMS-shaped case in Amazon-native terms); GST
   registration present but the invoice pending (step 5); window expiring on
   `as_of` itself; a leap-day window (2028-02-29) and a month-end window;
   TCS on a refund; a SAFE-T reimbursement already received (true negative);
   duplicated identical lines; a zero-amount line; a class-8 known code with
   no rule; a class-8 unseen code; an A-to-z refund; a seller-issued refund.
4. Report the SHA-256 of `claimability.json` in your final message; the
   integrator freezes it.

## Tests required (in `tests/labels/`)
- Labels load; every seeded scenario has exactly one label; combinations
  consistent with the ladder table above; every citation has a URL and
  as-of; `rupee_line_for(class, expected_state)` never raises.
- Holdout: exactly 25 cases, unique ids, every case's `folded.as_of` set,
  every `line_id` parses, expected class/state consistent with the contract.
- A test that fails if any label's `verified` flag is missing (present and
  false is fine).

## Exit criteria
`make lint` and `make verify` green. No new dependency. Conventional Commits
with scope `labels`. Do not push.

## Report format
1. Summary · 2. Files · 3. Tests · 4. Interface change requests (a scenario
you believe is mislabelled by its description, a missing scenario, a missing
enum value) · 5. What broke and how you got out · 6. Open questions (include:
the checksum; pages you could not reach; labels you are least sure of).
