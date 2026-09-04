Lane C · Wave 1 · GitHub issue #6 · role `lp-logic` (Opus, high effort) · worktree branch `lane/C-ratecard`

## Mission
Build the rate-card corpus: the detector side's encoding of Amazon India's
fee schedule for three categories, every rule dated and cited, with a coverage
declaration that turns a lookup miss into one of two honest outcomes. Outside
the declaration a miss is `UNCOVERED` (a documented limitation). Inside it a
miss is `CONFIG_ERROR`, a hard gate that fails the build naming category, slab
and `as_of`, so a corpus typo can never masquerade as the cap working as
designed (D17).

## Governing sections (read first)
- Design doc: D17, D14 (verified flags), D3, D12 (you are the second
  encoding; lane B is the first), class table rows 1, 2, 5, 7.
- Strategy §3 (Wave 1, lane C), §4.
- ADR-0005 (audited vs acknowledged kinds; class-8 semantics).
- `docs/research/ratecard-sources.md`: URLs and the coverage decision. Fetch
  the numbers from the sources yourself with the browse skill (run browse
  with the sandbox disabled; it cannot bind a port inside it); record the URL
  and as-of date on every rule as its `Citation`, `verified: true` only when
  the primary page was actually read.
- `docs/plans/briefs/README.md`, "Decisions carried into every brief": the
  category identifiers are pinned to one fee-category node each
  (`contract.CATEGORY_NODES`); cite the exact node name in every rule. Encode
  the March 16, June 10 and September 7, 2026 changes as validity windows
  where they touch your kinds. The refund fee's India term is "Refund
  Commission" and its Help Hub page is login-walled: cite the forum post RS3
  §5 names, `verified: false`. For TDS 194-O cite the Gazette PDF RS3 §6
  names; for TCS resolve the combined-vs-single-leg ambiguity from the
  primary notification, not from blog titles (RS3 open item 5).
- Acknowledge (`audited: false`) every `LineKind` that is neither audited nor
  `TECHNOLOGY_FEE` / `UNCLASSIFIED`: `SHIPPING_FEE`, `PROMOTION`, `RESERVE`,
  `SAFET_REIMBURSEMENT`, `FULFILMENT_FEE`, `STORAGE_FEE`, `GIFT_WRAP`,
  `GOODWILL`, `RESTOCKING_FEE`, `MARKETPLACE_FACILITATOR_TAX`, and the income
  kinds.

## Files you own
- `src/leakproof/ratecard/` (loader, corpus data files, gate function)
- `tests/ratecard/`

## Files you must not read
- `src/leakproof/generator/` (the other encoding). The reviewer greps.

## Interfaces you consume (frozen)
- `types.RateCard` (Protocol you implement), `RateRule`, `LookupMiss`,
  `CoverageDeclaration`, `Citation`.
- `contract.LineKind`, `Disposition`, `apply_bp`, `Paise`.

## Deliverables
1. Corpus as data under `src/leakproof/ratecard/corpus/` (JSON), one file per
   source document or category, each rule carrying `rule_id`, `kind`,
   `category_id` (or null for marketplace-wide), `percent_bp` or
   `fixed_paise`, slab bounds on order principal in paise (inclusive, null for
   open ends), `valid_from`, `valid_to`, `citation {label, url, as_of, verified}`,
   `audited`.
2. Rules for: `COMMISSION` per category (with price bands if the source has
   them); `FIXED_CLOSING_FEE` slabs; `FEE_TAX` (GST on fees) marketplace-wide;
   `REFUND_ADMIN_FEE`; `TCS`; `TDS` (with the rate history the statutory
   sources give, as separate validity windows). If the 2026 changes alter a
   rate, encode both windows.
3. Acknowledgements (`audited: false`) for kinds that are expected deductions
   with no audit rule: `SHIPPING_FEE`, `PROMOTION`, `RESERVE`,
   `SAFET_REIMBURSEMENT`. Do not acknowledge `TECHNOLOGY_FEE`; the
   `C8_CODE_KNOWN_NO_RULE` scenario depends on it having neither a rule nor an
   acknowledgement.
4. `load_rate_card(path=None) -> RateCard` with `lookup(kind, category_id, as_of)`
   and `coverage()`. Lookup semantics: category outside the declaration or
   `as_of` outside validity → `LookupMiss(UNCOVERED, ...)`; inside coverage
   but no rule matches (slab gap, missing kind) → `LookupMiss(CONFIG_ERROR, ...)`
   with a `detail` naming category, kind, principal slab and `as_of`; an
   acknowledged kind returns its `RateRule` with `audited=False`.
5. `config_error_gate() -> GateResult`-shaped callable (import `GateResult`
   from `leakproof.gates`): sweeps every declared category × audited kind ×
   slab boundary (both sides of every bound) × validity-window edge and fails
   on any `CONFIG_ERROR`. The integrator registers it in `HARD_GATES`.

## Tests required (in `tests/ratecard/`)
- Every declared category has a commission rule and closing-fee slabs with no
  gaps and no overlaps across the full principal range.
- `as_of` before `valid_from` or after `valid_to` → UNCOVERED; unknown
  category → UNCOVERED.
- A fixture corpus with a deliberate slab gap → `CONFIG_ERROR` from `lookup`
  and a failing gate result (this is the `CONFIG_ERROR` scenario's test).
- Every rule has a citation with a URL and as-of date; `percent_bp` and
  `fixed_paise` are ints; no floats anywhere.
- `coverage()` lists exactly the declared categories and the audited and
  acknowledged kinds.
- Marketplace-wide rules resolve for any category inside coverage.

## Exit criteria
`make lint` and `make verify` green in your worktree. No new dependency. No
`float`. Conventional Commits with scope `ratecard`. Do not push.

## Report format
1. Summary · 2. Files · 3. Tests · 4. Interface change requests ·
5. What broke and how you got out · 6. Open questions (include: every rule
you had to mark `verified: false` and why; sources that disagreed).
