# Wave 1 → Wave 2 handoff brief

Written for whoever (or whichever model) picks up next — assume no memory of
prior sessions. Verified against the repo at `main` = `d673b2a`, tagged
`wave-1`, 2026-09-05. `make verify`: 911 passed, 4 skipped (skipped only
because the optional `fastapi`/`uvicorn` extras aren't installed — install the
`serve` extra to un-skip them), 2 hard gates green.

Read `docs/designs/leakproof-evidence-completeness.md` (the design doc),
`docs/plans/agent-team-build-strategy.md` (the lane/wave method), and
`docs/build-log.md` (Wave 0 + Wave 1 incidents) before writing any code. This
file is a pointer into those, not a replacement for them.

## What Wave 1 actually built

Ingest → detectors → rate card → labels/eligibility → the seed-data generator
(`gen`) → audit/ledger scaffolding. Six lanes (B generator, C rate card, D
parsers, E audit, F labels/holdout, G dashboard), issues #5–#10, all merged.

## What is NOT built yet — confirmed by reading `src/leakproof/cli.py`

```python
NOT_BUILT: dict[str, tuple[str, int]] = {
    "demo": ("G", 10),
    "serve": ("G", 10),
    "triage": ("M", 16),
    "metrics": ("N", 17),
    "throughput": ("N", 17),
}
```

Concretely: there is no runnable path from a settlement batch to a triaged
claim list. `triage/__init__.py` and `metrics/__init__.py` exist but are stubs
(37 and 20 lines). Nothing downstream of detection works end-to-end today —
this is the actual gap for a demo, not a cosmetic one. `audit_chain_gate`
stays unregistered until something writes an audit log; don't register it
early, it would pass vacuously.

## Must-carry-forward facts (get these wrong and you corrupt a published number)

1. **TCS rate: the design doc is wrong, the code is right.** The doc's class-7
   row says 1%. Notification 15/2024 (read first-hand, independently, by two
   lanes) says 0.25% CGST + 0.25% SGST intra-state, 0.5% IGST inter-state. The
   generator and the rate-card corpus both follow the notification. If a new
   lane "fixes" the code to match the doc, every ordinary order will fire a
   spurious class-7 finding. Settle this in an ADR before touching detectors,
   don't silently pick one.
2. **Detector 5 (`C5_WINDOW_DATE_MISSING`) needs a specific, non-obvious
   shape**: a settlement refund row whose `posted-date` *field* is blank
   (quarantined by the parser), leaving the refund evidenced only by
   `Order.refund_initiated_by` with no date at all. `SettlementLine.posted_date`
   is a mandatory `date` in the parsed type — the absence only exists one level
   below, in the raw row. Two earlier attempts to describe this scenario from
   the type system or from prose were both unseedable; only asking the lane
   that writes the generator (lane B) produced a shape that actually exists.
   Lesson generalizes: **a "value is absent" scenario must name the field that
   holds the absence, at the level the absence actually lives** — ask the
   producing lane before writing the description, not after.
3. **SAFE-T is scoped to class 5 only (ADR-0006).** Class 1 (commission
   overcharge) files through a support ticket with no filing window — it has
   no return/refund event to start a window from. This flipped mid-Wave-1
   after two independent readings of the primary policy pages contradicted the
   design doc's original assignment. Read `docs/adr/0006-class-1-files-through-support-ticket.md`
   before writing eligibility/window logic for any class.
4. **Class-6 amount is principal + tax** (ADR-0005 §5), not principal-only.
   Principal-only gives fine recall and zero rupee-agreement against the
   published total.
5. **The labels file is frozen and checksummed.** `contract.FROZEN_LABELS_SHA256`
   pins `src/leakproof/labels/claimability.json` (25492 bytes). Any change now
   needs an ADR-0003 amendment published beside the D12 independence metric —
   read `docs/adr/0003-label-amendment-after-freeze.md` first. Only that one
   file is checksummed; `cases.py` and `ladder.py` are not frozen.
6. **New companion input needed: `evidence.csv`** (`order_id, requirement,
   status, supplied_on`). None of the four spec'd inputs distinguish
   `C5_PLAIN` from `C5_INVOICE_PENDING`, so every SAFE-T claim currently blocks
   on a seller-suppliable item with no way to say it was supplied. Needs a
   spec row in `docs/specs/`, a lane D–style parser, and lane K consumption.
7. **Seam batch deferred from Wave 1 close** — small typed additions other
   lanes will want to build against: `RateRule.slab_basis` typed field (and
   its docstring needs to stop saying slabs bound the order principal),
   `RateCard.lookup(band_key_paise=...)` optional param, `HoldoutCase.expected`
   as a tuple plus `verified`, `HoldoutCase.batch_max_settlement_date`,
   out-of-coverage category ids on `BatchReport`.

## Architecture invariants that will bite a new contributor

- **Deterministic money, probabilistic language.** The LLM parses, explains,
  classifies, drafts. It never computes a rupee amount and never files
  anything. Every number traces to a source row; every claim is human-approved.
- **The wall test (D12).** `leakproof.gates` is imported by every walled lane
  package, so it can never be where a lane registers its own gate — that
  makes every walled package "reach" every other lane and fails the wall test.
  Register lane gates in `cli.hard_gates()` (nothing imports `cli`), keep only
  `BASE_GATES` in `gates.py`. This bit lane C for real; the rule is now in
  `gates.py`'s docstring.
- **`cli.py` is the only module allowed to read the system clock (D18).**
  Everything else takes `as_of` as an argument; a verify-time test enforces it.

## Method lessons (how Wave 1 actually went, so you don't repeat it)

- **A lane's "what broke" section is a claim, not a record** unless it commits
  as the work happens. One lane's retroactively-written incident log
  corroborated none of its own reflog. Require small atomic commits through
  the work, not a tidy history written at the end.
- **A salvaged patch (from a killed/interrupted lane) lands verbatim and red
  as its own commit, fixes on top as a separate commit** — so the log shows
  what was inherited versus what changed.
- **Verify lane claims against the artifact, not the lane's own tests.**
  Numbers get reported that flatter their author without anyone lying — a
  rule count, a sweep's actual coverage, a comment about invariants the file
  doesn't hold. Count the rules from the JSON yourself; delete a rule and
  confirm the gate actually fails; render the dashboard to a file and read it.
- **A finished background agent is resumable by name (via SendMessage,
  continues from its transcript). A killed one is not** — remove its worktree
  and relaunch fresh on the branch, feeding it the predecessor's uncommitted
  work to review as unreviewed input.
- **Check the account's usage window before launching a full wave of
  concurrent lanes** — six lanes running at once exhausted a session cap
  mid-Wave-1 and killed all six simultaneously.

## Sandbox/tooling facts that cost time in Wave 0–1

- `gh` and the browse-skill daemon both need the sandbox disabled per call
  (TLS cert mismatch for `gh`; can't bind/connect to a localhost port for
  browse) — retry with sandbox off rather than treating it as a real failure.
- Worktree removal after a merge needs the sandbox off (`.claude/agents` and
  `.git/config` are on the write-deny list, and the pattern matches worktree
  copies too).
- Always go through `make` targets, never bare `uv run` (uv's cache lives
  under `~/.cache`, which the sandbox blocks; the Makefile has a fallback).
- `make fmt` after editing any file that `make lint` already checked — an
  amend without re-running the formatter shipped red CI once.
- Bash cannot write into this project's Claude memory directory — use the
  Write tool for that.
- Apple's `/usr/bin/make` prints two spurious `xcrun` cache errors per
  invocation inside the sandbox; harmless, ignore them.

## If you're handing lanes to a different model (e.g. Gemini/Antigravity) for Wave 2/3

Format/plumbing-shaped work (parsers against a written spec, a lane-K-style
consumer of an already-defined type, docs, glue) is reasonable to delegate —
that's this project's own `lp-build` tier. Money-path logic (detectors,
eligibility, rate lookups, anything that changes what a published number
means) is riskier to delegate without the same second-reviewer step this
project already uses: a fresh-context review against the design doc and
primary sources, not against the lane's own tests. Every near-miss in the
"must-carry-forward" section above was caught that way, not by a test suite
the same author wrote.
