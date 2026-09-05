# Wave 2–5 handoff — demo-priority build

Written 2026-09-05 for whoever (or whichever model) picks this up next; assume
no memory of prior sessions. `main` = `e5ab144`. `make verify` is green today
(911+ tests) on an **empty pipeline**: everything below "fold" is
`NotImplementedError`. This file plus the six lane briefs already on disk are
the complete spec — you should not need to re-derive anything from the design
doc except to double-check a detail.

Read in this order before writing code:
1. This file.
2. `docs/designs/leakproof-evidence-completeness.md` — at minimum the
   "Recommended Approach" section (pipeline, error classes, evidence-state
   model, rupee partition) and "Resolved Decisions" D1–D23.
3. The lane brief for whatever you're building (§2 below has the map).
4. `src/leakproof/contract.py` and `types.py` — read, never edit. Every
   dataclass and enum you need already exists.

## 0. What already works — do not rebuild any of this

- `make gen --preset demo` writes real orders/settlement/bank CSVs + a
  `manifest.json` for a 150-order batch with ~20 seeded errors
  (`src/leakproof/generator/`, 1400+ lines, real).
- `src/leakproof/ingest/` — real V2 settlement parser, orders parser, bank
  parser, seller-profile loader, all with quarantine handling. `BatchInputs`'s
  fields (`orders`, `settlements`, `profile`, `bank`, `evidence`) are what
  these parsers produce.
- `src/leakproof/ratecard/` — a real 651-line rate-card loader implementing
  the `RateCard` protocol (`lookup`, `band_basis`, `coverage`), three
  categories, dated and cited.
- `src/leakproof/labels/` — frozen claimability labels + 26-case holdout,
  checksum pinned in `contract.py`. Do not edit; changing it needs an ADR-0003
  amendment.
- `src/leakproof/audit/` — the hash-chained log (`AuditLog`, `verify_chain`,
  `audit_chain_gate`), fully real. Lane O just calls it.
- `src/leakproof/dashboard/` — **rendering is fully real**: `render(report,
  mode=...)`, `write_demo_html(report, path)` (self-contained `demo.html`
  with the JSON inlined), and `serve.py`'s FastAPI shell with
  `dispatch_gate_action` already wired to call `leakproof.gate.*` — it
  currently 501s because `gate/` raises `NotImplementedError`. **Once gate/
  is real, `make serve` and `make demo` need no dashboard work at all.**
- `src/leakproof/gates.py` — the hard-gate registry mechanism (integrator-
  owned; lanes register callables, wired into `cli.hard_gates()`).

## 1. What is missing — one pipeline, stub to real, in dependency order

```
ingest (done) → ledger.fold_batch/match (H) → detect.run_detectors (J)
  → evidence.assess (K) → triage.run_batch (L, orchestrates H+J+K itself)
  → draft.run_triage_job (M) → gate.approve/override/reject/flag (O)
  → cli.py wiring (integrator) → dashboard.write_demo_html (done)
bankleg.reconcile_payouts (I) and ingest.evidence parser (I) plug into
BatchInputs/BatchReport, no ordering dependency on the chain above.
metrics.score/score_holdout (N, trimmed) reads a finished BatchReport.
```

Every stub already has its real signature committed in `main` — implement to
match it exactly, do not change it (a signature change is an interface-change
request in your report, not a silent edit).

### Lane H — `src/leakproof/ledger/__init__.py`
Brief: `docs/plans/briefs/wave-2/H-ledger.md` (complete, ready to run as-is).
```python
def fold_batch(inputs: BatchInputs) -> tuple[FoldedOrder, ...]: ...
def match(inputs: BatchInputs, folded: tuple[FoldedOrder, ...]) -> MatchResult: ...
```
D20 (cross-cycle fold, deterministic tiebreak, coverage window), D7
(quarantine stays in the match-rate denominator), D10 (match-rate defs). Note
lane L calls `match` a *second* time with `class6_flagged` once detectors have
run (see the brief — this is intentional, not a seam bug).

### Lane I — `src/leakproof/bankleg/__init__.py` + `src/leakproof/ingest/evidence.py`
Brief: `docs/plans/briefs/wave-2/I-bankleg.md` (complete, ready to run as-is).
```python
def reconcile_payouts(headers: tuple[SettlementHeader, ...], credits: tuple[BankCredit, ...]) -> BankLegResult: ...
```
Plus a new `parse_evidence(path_or_text, source_file) -> EvidenceParse`
following `docs/specs/evidence-supply.md`. D6 (bank leg excluded from match
rate; duplicate UTR same amount/day satisfies exactly one payout). Lowest risk
lane — descope rung 2 if you run out of time (delete `bankleg/`, drop
`BatchInputs.bank`/`BatchReport.bank_leg` to `None`, nothing else breaks).

### Lane J — `src/leakproof/detect/__init__.py` (+ new `registry.py`)
Brief: `docs/plans/briefs/wave-2/J-detect.md` (complete, ready to run as-is).
```python
def make_finding(**fields: object) -> Finding: ...   # give it real typed params
DETECTORS: tuple[Detector, ...] = ()
def run_detectors(folded: tuple[FoldedOrder, ...], ctx: DetectorContext) -> list[Finding]: ...
```
**D12 wall: never import `generator/` or `labels/`.** Six detectors (classes
1,2,5,6,7,8), each described in full in the brief. Read ADR-0008 (TCS is
0.5% aggregate, not the design doc's stale 1%) and ADR-0005 (class-6 amount is
principal+tax) before writing anything — both contradict the design doc's
literal text and the ADRs are what's correct.

### Lane K — `src/leakproof/evidence/__init__.py`
Brief: `docs/plans/briefs/wave-2/K-evidence.md` (complete, ready to run as-is).
```python
def assess(finding: Finding, folded: FoldedOrder, profile: SellerProfile, as_of: date) -> Assessment: ...
def deadline_for(mechanism: Mechanism, event_date: date | None, as_of: date) -> Deadline: ...
```
**D12 wall: never import `labels/` or `generator/`.** Read ADR-0006 (SAFE-T is
class 5 only), ADR-0007 (six override labels — you produce the
`BlockerKind`/`NotClaimableReason` these key off), `docs/research/safe-t.md`,
`docs/specs/evidence-supply.md`. The `WindowStatus.START_DATE_MISSING` vs
`NOT_APPLICABLE` distinction is the single easiest way to publish a wrong
state — get it right.

### Lane L — `src/leakproof/triage/__init__.py`
Brief: `docs/plans/briefs/wave-3/L-triage.md` (written 2026-09-05, ready to
run) — **but note the brief's §"Deliverables" item 6 describes a different
`run_batch` shape than what's actually committed.** The real, committed
signature is:
```python
def dedup(findings: list[Finding]) -> tuple[Finding, ...]: ...
def derive_state(finding: Finding, assessment: Assessment) -> StateResult: ...
def partition(queue: tuple[TriagedFinding, ...], below_materiality: tuple[Finding, ...]) -> RupeeLines: ...
def run_batch(inputs: BatchInputs, rate_card: RateCard) -> BatchReport: ...
```
**`run_batch` takes raw `BatchInputs` + a `RateCard` and must itself call
`ledger.fold_batch`/`match`, `detect.run_detectors`, `evidence.assess` for
every finding, then `dedup`/`derive_state`/`partition`, then assemble the
`BatchReport`.** So lane L is not walled from H/J/K/I — it is the integration
point that calls all of them. Use the brief for the ladder-steps-as-code, the
rupee-partition rules, and the overlap matrix; ignore its `run_batch`
paragraph and match the signature above instead. Leave `queue[i].draft` and
`.gate` as `None` — M and O fill those in over the same `TriagedFinding` list
in a second pass (you'll need a small merge helper, e.g. `apply_drafts(report,
drafts) -> BatchReport` and `apply_gate(report, finding_id, gate_record) ->
BatchReport`, both simple `dataclasses.replace` walks over `report.queue`;
put them in `triage/` since you own `BatchReport` assembly).

### Lane M — `src/leakproof/draft/__init__.py`
Brief: `docs/plans/briefs/wave-3/M-draft.md` (written 2026-09-05, ready to
run, signatures already match what's committed):
```python
def draft_finding(item: TriagedFinding, *, model: str) -> Draft: ...
def run_triage_job(report: BatchReport, out_dir: Path, *, model: str, resume: bool = True) -> None: ...
def check_drafts(report: BatchReport, artifacts_dir: Path) -> list[str]: ...  # D2 (a)(a′)(b)
```
D2 (no rupee amounts in the prompt, three checks over committed artifacts,
zero network in verify), D11 (resumable). Model: `claude-sonnet-5` via the
`anthropic` SDK (already an extra in `pyproject.toml`), key from
`ANTHROPIC_API_KEY` at call time only. **Only `make triage` calls the network;
`make verify` must mock/skip it entirely.**

### Lane O — `src/leakproof/gate/__init__.py` (+ `dashboard/serve.py` ownership)
No brief exists yet; write one or work from this directly. Issue #18.
```python
def approve(exception_id, report, log, out_dir, *, actor, ts, as_of) -> ClaimPack: ...
def override(exception_id, report, log, out_dir, *, actor, ts, as_of) -> ClaimPack: ...
def reject(exception_id, report, log, *, actor, ts, as_of) -> None: ...
def flag(exception_id, report, log, *, actor, ts, as_of) -> None: ...
```
Governing: D8 (approval artifact: claim pack = claim text + cited-rows CSV +
recomputation CSV; **pack written first, audit entry appended second**;
approve is idempotent — a second approve returns the existing pack, no second
audit entry; approving a non-CLAIM-READY exception must go through `override`
instead, which marks the pack `overridden=True`, records action
`approve_override` with `state_before`, and never touches `rupee_lines.claim_ready`).
ADR-0004 (`AuditAction.FLAG` for UNEXPLAINED — no artifact, just an audit
entry naming the `unexplained_basis`; DISMISS on a CLAIM-READY/BLOCKED row is
`reject` with `state_before` recorded, same audit action, different button
label). ADR-0007 (the six fixed override-button labels — a total function
over `(state, blocker_kind | not_claimable_reason)`, raise on anything outside
the table). `reject` writes only an audit entry (`state_before` = current
state, action `reject`), no artifact, no claim pack. Use
`leakproof.audit.AuditLog` (`next_seq()` to get the seq for the pack before
appending, `append(...)` after the pack file is written) exactly as its
module docstring describes. Ownership of `dashboard/serve.py` transfers to
you — replace `PLACEHOLDER_TS` with a real clock threaded in from `cli.py`
(never read the system clock inside `gate/` itself; take `ts`/`as_of` as
parameters, same as every other module).

Tests: idempotent approve (call twice, one audit entry, same pack path);
override marks `overridden=True` and never adds to `claim_ready`; reject/flag
audit-only, no file written; pack-then-entry ordering (kill the process
between the two — or just assert the pack file exists before `append` is
called — and confirm `audit_chain_gate`'s orphan-pack check would catch a pack
written without its entry); the six-label mapping raises on an out-of-table
combination.

### Integrator work (not a lane — do this yourself, or as one more agent pass)

1. **`cli.py` wiring** (`demo`, `serve`, `triage`, `metrics`, `throughput`,
   removed from `NOT_BUILT` one at a time as each becomes real):
   - `cmd_demo`: `gen`-preset "demo" already on disk (or generate it), build
     `BatchInputs` from the parsed files, call `triage.run_batch(inputs,
     rate_card)`, optionally `draft.run_triage_job` if committed artifacts
     exist (they should, from lane M's demo fixtures / a real `make triage`
     run), write `out/demo.html` via `dashboard.write_demo_html`. Keyless —
     never call `draft`'s live API path.
   - `cmd_serve`: load a `BatchReport` (via `dashboard.load.load_report`) into
     `dashboard.serve.create_app`, run with uvicorn.
   - `cmd_triage`: the opt-in LLM job — build the demo batch's `BatchReport`,
     call `draft.run_triage_job` for real (needs `ANTHROPIC_API_KEY`), then
     re-assemble the report with drafts attached and commit the artifacts
     under `tests/fixtures/drafts/` (or wherever lane M's brief lands them)
     so `make demo`/`make verify` stay keyless afterward.
   - Register `audit_chain_gate` in `hard_gates()` now that something writes
     an audit log (the Wave 1 handoff explicitly said not to register it
     early — that condition is now met).
2. **Regenerate the demo-batch draft fixtures for real** once H/J/K/L/M have
   all merged — lane M's committed artifacts were built from its own
   hand-authored fixtures (parallel build, no shared demo batch yet), not the
   real 150-order demo batch. Run `make triage` once against the real demo
   batch and commit the result.
3. Full `make verify` green, `make demo` opens and shows real numbers,
   `make serve` supports a live approve/override/reject/flag click in the
   browser.

### Wave 5, trimmed hard — issue #17 (N), skip Q entirely

Do **not** build the full N=5-seed measurement harness, throughput
benchmarking, or `metrics/results/`. Instead, inside `metrics/__init__.py`,
implement just enough to publish honest numbers next to the demo:
```python
def score(report: BatchReport, manifest: Manifest, labels: dict[Scenario, ClaimabilityLabel]) -> dict[str, object]: ...
def score_holdout(cases: tuple[HoldoutCase, ...]) -> dict[str, object]: ...
```
Compute, on the one demo batch (not N=5 seeds): recall, per-class recall,
precision, ₹-agreement (with every disagreement listed per D10's definition),
strict + adjusted match rate. Score the 26-case holdout once, report as its
own line, never merged into headline recall. Skip the CI throughput
regression gate and the 10k-order run — state in the README that throughput
was not benchmarked in this build, rather than fabricating a number.

### README (issue #21, R) — write this yourself, ~30 minutes
Copy the "README limitations (verbatim)" section from the design doc
word-for-word (it's already written, don't rephrase it), add `make gen`/`make
demo`/`make triage`/`make serve` reproduction steps, and paste whatever
`metrics.score` prints for the demo batch. Skip the architecture-diagram
polish pass if short on time.

## 2. Suggested lane grouping if you're running this as agent-team lanes again

Same six-lane parallel round this session already tried once (H, I, J, K, L,
M — H/I/J/K from existing wave-2 briefs, L/M from the new wave-3 briefs), then
one more round for O + the integrator cli-wiring/metrics/README work described
above. Model tiers per `docs/plans/agent-team-build-strategy.md` §2 if you
want to keep that convention (Fable/max for J and K — money path with no
generator/labels to cross-check against; Opus/high for H, L, M, O; Sonnet/high
for I); collapse to a single tier if the other model doesn't support per-lane
model selection.

If you'd rather not run parallel isolated-worktree lanes at all: the
dependency order in §1 (H, J, K, I → L → M → O → cli wiring → metrics/README)
works fine as a single straight-through build too — nothing here structurally
requires parallelism, it's just faster wall-clock time when it works.

## 3. The pitch deck — what goes in slides vs what the demo has to show live

Recommendation: **build both.** The demo is the only thing that proves
"deterministic money, probabilistic language" is real — a slide claiming it
is just a claim. The deck carries the parts a 5-minute live run can't: market
framing, business case, what's deliberately cut and why, roadmap. Don't
duplicate the dashboard's own numbers onto a slide from memory — screenshot
the actual rendered `demo.html` once it exists, or re-export the real
`metrics.score()` output; a slide with an invented number undermines the one
thing this product is selling.

The design doc already has a **"Demo script (5 minutes)"** section
(`docs/designs/leakproof-evidence-completeness.md`, search for that heading) —
use it as the live-demo storyboard verbatim, it's already written for this
exact purpose:

- **Minute 1 — the problem** (deck slide, not live): a settlement screenshot,
  the "sellers lose 2-5% of settlement value to uncontested fee/refund errors
  and recover almost none of it" framing, one sentence on why (no one reads a
  24-column TSV by hand). This is the only slide that needs a market number —
  cite it, don't invent it.
- **Minute 2 — live**: `make demo`, keyless, 150 orders in. Say the two match
  rates (strict vs adjusted) and the delta out loud. Say ₹ identified vs
  claim-ready vs blocked vs not-claimable as four different numbers — this
  is the core selling point ("we tell you exactly what blocks the rest," not
  just "we found leakage").
- **Minute 3 — live**: drill one commission overcharge end to end — source
  rows → recomputation → the LLM-drafted SAFE-T claim with its deadline
  countdown → the approve gate → the resulting claim pack on disk. This is
  where "the LLM only writes prose, never a number" actually gets shown, not
  just claimed.
- **Minute 4 — live or slide**: the honesty beat. Precision/recall/₹-agreement
  vs seeded truth, the holdout line reported separately, the unexplained list
  on screen, and — the most persuasive shot in the whole demo — the agent
  **declining** to mark a BLOCKED(needs GST invoice) claim ready. A tool that
  admits what it can't do is the pitch, not a caveat on the pitch.
- **Minute 5 — deck**: the malformed-file quarantine (handled, not silently
  dropped), whatever throughput number you actually measured (or "not
  benchmarked this build" — see Wave 5 note above, never fabricate this),
  Razorpay strategic fit (this is a Razorpay AI Buildathon submission — make
  the fit to Razorpay's own settlement/payouts business explicit), one
  architecture diagram, close on "deterministic money, probabilistic
  language."

Deck-only content beyond the demo script (no live equivalent, build these as
slides): title/problem framing, market sizing if you have a real source for
it, business model (who pays, what's the wedge — the design doc's "Target
User & Narrowest Wedge" section already has this framed), competitive
positioning ("not 'we find leakage' like every incumbent — we tell you what's
actually recoverable and what blocks the rest"), the descope ladder as an
honesty slide (what was cut and why: Flipkart, catalog-dims-dependent
detectors, fuzzy matching — all in the design doc's "Approaches Considered"
and "Descope ladder" sections), roadmap (real-data ingestion, more
marketplaces, the fuzzy-matcher rebuild the design doc already flags as "the
first requirement of any future real-data run").
