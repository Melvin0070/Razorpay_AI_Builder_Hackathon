# Lane briefs

One file per lane, filled in from the template in
`docs/plans/agent-team-build-strategy.md` §7. The integrator pastes the brief
into the Agent launch and into the lane's GitHub issue as a comment.

## Launching a wave

Custom roles in `.claude/agents/` load when a session starts, so **launch each
wave from a fresh session** (the Wave 0 build log records what happens
otherwise). Then, for every lane in the wave, in one message:

```
Agent(subagent_type = lp-core | lp-logic | lp-build, name = "<lane>-<slug>",
      isolation = worktree, run_in_background = true, prompt = <brief file>)
```

Concurrency caps: at most six lanes per wave, at most two `lp-core` lanes at once.

## Before cutting worktrees

- `git status` clean on `main`, `main` pushed, CI green.
- `contract.py`, `types.py`, `scenarios.py` reflect every interface change
  request accepted from the previous wave.
- Research memos the wave depends on are merged.

## Decisions carried into every Wave 1 and Wave 2 brief (from the Wave 0 research)

- **Category identifiers are pinned to one Amazon.in fee-category node each**
  (`contract.CATEGORY_NODES`): `electronics-accessories` → "Accessories -
  Electronics, PC and Wireless" (corrected 2026-09-04: no node named "Electronics
  Accessories" exists on the live page, RS3 §1 was wrong on that name; lanes B and
  C confirmed); `home-kitchen` → "Kitchen - Cookware, Tableware & Dinnerware";
  `apparel` → "Apparel - Shirts". Lanes B and C encode that node's own tiers,
  never an umbrella (RS3 §1).
- **Three 2026 fee effective dates exist**: March 16, June 10, September 7.
  Rules carry validity windows; a batch's `as_of` selects the schedule in
  force (RS3 §2, §3).
- **The SAFE-T filing window is contradicted across secondary sources** (30,
  60, 15 and a 50-day figure) and the primary page is login-walled (RS2 open
  item 6). Lanes F and K each read the sources independently; where sources
  disagree, both encode the **shortest** figure, mark it `verified: false`,
  and record the alternatives (in the label rationale, in the rule docstring).
  Same tie-break, independent readings.
- **Fee overcharges are not SAFE-T-shaped; decided 2026-09-05 (ADR-0006).**
  Lane F's reading of the primary pages and its reviewer's independent check
  both landed there, and a commission overcharge on an un-refunded sale has no
  return event to start a window from. `PRIMARY_MECHANISM` for class 1 is now
  `SUPPORT_TICKET` with no filing window; the SAFE-T-shaped class-1 scenarios
  moved to class 5 (`C5_WINDOW_EXPIRED`, `C5_WINDOW_DATE_MISSING`,
  `C5_GST_UNREGISTERED`, `C5_INVOICE_PENDING`) and the two duplicate exclusion
  scenarios were deleted. The demo drills a class-5 claim. Lane K writes SAFE-T
  eligibility and window rules for class 5 only.
- **Refund fee terminology**: the India term is "Refund Commission"; the US
  "Refund Administration Fee" is a different mechanism (RS3 §5). Cite the
  India forum post RS3 names when the Help Hub page is login-walled.
- **Statutory sources**: `incometaxindia.gov.in` and `pib.gov.in` are
  bot-blocked; cite the Gazette of India Finance (No. 2) Act 2024 PDF for the
  194-O change and the GST Council notifications for TCS (RS3 §6).
- **Research lanes**: the browse daemon cannot bind a port inside the sandbox;
  run browse commands with the sandbox disabled from the first call.

## Decisions carried into every Wave 2 brief (settled at the wave open)

- **TCS is the 0.5% aggregate (ADR-0008).** The design doc's 1% is the
  statutory ceiling under s.52(1), not the notified rate. Both Wave 1
  encodings, written independently, agree on 0.5% from 2024-07-10. A detector
  "fixing" the code to match the doc would fire a spurious class-7 finding on
  most of the batch.
- **Detector 5 emits whenever the reversal is absent**, including when the
  refund is too recent for one to have landed. The immaturity is expressed by
  lane K as a *pending* evidence item, which puts the case at ladder step 5 as
  BLOCKED(timing) — matching the frozen `C5_AWAITING_CYCLE` label. D20's
  "fires only when" is loose phrasing; this is the integrator's reading and it
  is settled. Lanes J and K were each told it, so they agree without talking.
- **The seam grew four things at the Wave 1 close**, from lane C's and lane F's
  interface change requests: `types.SlabBasis`, `RateRule.slab_basis`,
  `RateCard.lookup(band_key_paise=...)` and `RateCard.band_basis(kind)`, plus
  `HoldoutCase.batch_max_settlement_date`. A detector asks the seam which
  figure a band is read on; it never hard-codes the mapping.
- **`evidence.csv` is the fifth input** (`docs/specs/evidence-supply.md`).
  Without it every SAFE-T claim blocks forever on a seller-suppliable item and
  `C5_PLAIN` is indistinguishable from `C5_INVOICE_PENDING`. Lane I parses it,
  lane K consumes it.
- **A lane's signature stubs live in files the lane owns**, so extending one
  with a defaulted keyword is not a seam change and needs no request. Lanes H
  and K both need this; they are told so explicitly.
- **Commit as you go.** A retroactively-written incident log corroborated none
  of its own reflog in Wave 1. Small atomic commits through the work.

## Closing a lane

1. Read the lane report. Copy its "What broke" entries into `docs/build-log.md`.
2. Push the worktree branch, open the PR with the template, `Closes #N`.
3. Run `lp-reviewer` on the PR diff with the brief attached. Fix or push back.
4. Merge `--no-ff`. Confirm `make lint && make verify` green on `main`.

## Closing a wave

Integration tests that span lanes (owned by the integrator), tag `wave-N`,
build-log entries merged, interface change requests applied to the seams on
`main` before the next wave's worktrees are cut.
