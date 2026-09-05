# LeakProof — Agent-Team Build Strategy

Status: PROPOSED (awaiting go)
Written: 2026-09-04
Governs: how `docs/designs/leakproof-evidence-completeness.md` (the approved design,
revision of 2026-09-04) gets built by a team of Claude Code subagents working in
waves of file-disjoint lanes, with one integrator.
Companion files: `.claude/agents/*.md` (lane roles: model + reasoning effort),
`docs/build-log.md` (what broke, and how we got out),
`.github/PULL_REQUEST_TEMPLATE.md`.

The design doc decides *what* is built and *why*. This document decides *who builds
which file, in what order, on which model, and how the pieces are merged without
breaking the two things the design refuses to compromise*: deterministic money and
the D12 independence of ground truth from the detector.

---

## 0. Ground truth on 2026-09-04

| Item | State | Consequence |
|---|---|---|
| `src/` | empty; no `pyproject.toml`, `Makefile`, tests, or CI | Wave 0 is a real scaffold, not a formality |
| Design doc + wireframe revision | **uncommitted** in the working tree | Must be committed before any worktree is cut, or every lane agent reads the stale 08-27 design |
| `TODOS.md` | untracked, referenced by the design doc | Commit in Wave 0 |
| `field-guide.md` | untracked, generic reference, 35 KB | Keep out of the repo (`.gitignore`) unless told otherwise |
| GitHub remote | `origin` set to `Melvin0070/Razorpay_AI_Builder_Hackathon`; API returns **404**; `origin/main` is **gone** | The repo does not exist publicly (or was never pushed). Repo setup is a Wave 0 task, not a done thing |
| `gh` CLI | token in keyring **invalid** | User must run `gh auth refresh -h github.com`; I cannot authenticate on their behalf |
| Toolchain | uv 0.12.1, node 24, python 3.14 system; uv can pin 3.12 | Stack per design: Python 3.12 + uv |
| Submission date | **unconfirmed** (design doc Open Question 1) | Waves are date-agnostic; the descope ladder trigger is not |

---

## 1. Orchestration model

**One integrator, many lanes, strict seams.**

- **Integrator** (this session, Fable): writes Wave 0 (the seams everyone codes
  against), writes every lane brief, cuts worktrees, reviews, merges, keeps
  `contract.py` and `types.py`, and maintains the build log. The integrator never
  edits a file a running lane owns.
- **Lane** = one subagent, one module, one branch `lane/<id>-<slug>`, one worktree
  (`isolation: worktree`), one PR. A lane owns a disjoint set of paths and is told
  which paths it must not read (the D12 walls). Lanes never talk to each other.
- **Wave** = the set of lanes with no data dependency among them. A wave closes when
  every lane PR has passed a fresh-context review, merged `--no-ff` into `main`,
  `make lint` and `make verify` are green on `main`, CI is green, the wave is
  tagged `wave-N`, and the build-log entries from every lane report are merged.
- **Seams are frozen for the duration of a wave.** A lane needing a contract change
  works around it inside its own files and files an "interface change request" in
  its report; the integrator applies it on `main` between waves. Emergency mid-wave
  changes go on `main` and affected lanes are told to rebase, by message, once.
- **Reviews**: every lane diff gets the `reviewer` agent (fresh context, read-only,
  reports correctness gaps against the lane brief). Anything on the money path
  (Tier A below) also gets the integrator's own read before merge.
- **Why the Agent tool and not the Workflow tool**: wave boundaries need judgement
  (conflict resolution, contract amendments, which review findings are real). A
  deterministic workflow script is the wrong tool for that; it stays available for
  the one mechanical step, fanning reviewers over N diffs, if wanted.

### Why agent teams strengthen this design specifically

D12 requires two independent encodings of the same public rate card (generator
fee logic vs detector rate-card config) and, more weakly, of the same policy text
(manifest claimability labels vs eligibility rules). The design doc records that
with a solo builder this independence is "nominal" because one person reads the
source twice within 48 hours. With lanes, the four encodings are written by four
different agents that are forbidden from reading each other's files, from a shared
list of **source URLs only**, never a shared digest of the numbers. The ₹-agreement
metric then measures something real. The README limitation should be reworded
accordingly once this is done.

---

## 2. Model and reasoning tiers

Tier by the **blast radius of a silent error**, not by task size. The question for
each lane: if this agent is subtly wrong and every test still passes, what gets
published wrong?

| Tier | Model | Effort | Use when | Lanes |
|---|---|---|---|---|
| **A** | Fable | max | A silent error corrupts a published number or a state assignment | Wave 0 seams (integrator), B generator, J detectors, K eligibility+deadlines, L triage pipeline, N metrics |
| **B** | Opus | high | Substantial logic, fully specified by the design, crisp tests | C rate card, F labels+holdout, H fold+matcher, M drafter, O gate |
| **C** | Sonnet | high | Format, UI, plumbing with a reference to copy from | D parsers, E audit log, G dashboard, I bank leg, P/Q artifact runs, R docs |
| **Research** | Sonnet | medium | Read-only web research producing cited memos | RS1–RS3 |
| **Reviewer** | Opus | high | Fresh-context diff review, read-only tools | every lane PR |

Concurrency caps: at most 6 lanes per wave, at most 2 Fable lanes at once.
Haiku is not used on the build.

The roles live in `.claude/agents/` as `lp-core` (A), `lp-logic` (B), `lp-build`
(C), `lp-research`, `lp-reviewer`, each carrying the shared preamble (architecture
invariant, ownership rules, report format) so a lane brief only has to say what is
specific to that lane.

---

## 3. Waves and lanes

Package: `src/leakproof/`. Every lane owns whole directories; shared files
(`contract.py`, `types.py`, `scenarios.py`, `cli.py`, `Makefile`, `pyproject.toml`,
`tests/conftest.py`, CI) are integrator-owned. A lane that needs a hook in a shared
file registers through a file it owns (e.g. `detect/registry.py`) and the integrator
wires it at merge.

```
src/leakproof/
  contract.py    D22 shared vocabulary: enums, Paise, compare_paise, floor,
                 tolerance, line_id format, as_of semantics, class→mechanism
                 table, FROZEN_LABELS_SHA256
  types.py       frozen dataclasses for every seam
  scenarios.py   seeded-error scenario IDs (vocabulary only: no labels, no amounts)
  ingest/        D   parsers + quarantine
  ratecard/      C   corpus + declared coverage + lookup
  generator/     B   synthetic batches + manifest (never imports ratecard/)
  labels/        F   claimability labels (frozen) + holdout/ 26 cases
  audit/         E   hash-chained log
  ledger/        H   fold + coverage window + tiebreak + exact matcher
  bankleg/       I   payout ↔ UTR
  detect/        J   Detector protocol, make_finding, c1 c2 c5 c6 c7 c8
  evidence/      K   eligibility rules, evidence requirements, deadline arithmetic
  triage/        L   dedup, overlap matrix, 7-step ladder, rupee partition, report
  draft/         M   LLM drafter, placeholders, resumable artifacts, D2 checks
  gate/          O   approve / override / reject → claim pack
  metrics/       N   accuracy harness, both match rates, holdout, throughput
  dashboard/     G   template from the wireframe, demo.html emitter, FastAPI serve
  cli.py         integrator: `python -m leakproof <verify|triage|demo|serve|...>`
tests/           mirrors the package; tests/fixtures/ holds hand-authored inputs
docs/adr/        one file per irreversible build-time decision
docs/research/   cited memos from the research lanes
docs/build-log.md
```

Naming trap, decided now: the design doc's `Exception` record is a Python builtin.
It is `Finding` in code (ADR-0002). Every lane brief uses that name.

### Wave 0 — Foundation (integrator, Fable) with research in parallel

Deliverables, in order:

1. Commit the revised design doc, wireframe, `TODOS.md`, and the planning files
   already in the tree (`docs/plans/`, `docs/build-log.md`, `.claude/agents/`,
   `.github/PULL_REQUEST_TEMPLATE.md`); `.gitignore` (venvs, `.env`, caches,
   `field-guide.md`, and `.claude/worktrees/`, where lane worktrees are cut).
2. Repo setup on GitHub (§5): create/confirm the repo, push, protection rules,
   PR template, issue per lane, milestone per wave, CI.
3. `pyproject.toml` (Python 3.12, uv; dev: pytest, hypothesis, ruff; extras:
   `serve` = fastapi+uvicorn, `triage` = anthropic), `uv.lock`, `Makefile`
   (`lint verify triage demo serve gen metrics throughput`), CI running lint +
   verify on push and PR.
4. `contract.py`, `types.py`, `scenarios.py` — the frozen seams (§4).
5. Stub packages with `NotImplementedError` bodies and the ownership map in each
   `__init__.py` docstring, so `import leakproof.*` works in every worktree.
6. `tests/fixtures/batch_report.demo.json`: a `BatchReport` matching the wireframe's
   numbers exactly, so the dashboard lane can start on day one.
7. D12 anti-circularity import test (fails if `generator/` reaches `ratecard/`);
   D18 clock test (bans `date.today()` / `datetime.now()` outside `cli.py`).
8. `docs/specs/amazon-settlement-v2.md`: the 24 tab-separated V2 columns and the
   `amount-type` / `amount-description` vocabulary the generator writes and the
   parser reads, marked `verified: false` until RS1 confirms.
9. ADR-0001 (stack + deps), ADR-0002 (`Finding`), ADR-0003 (label amendment
   procedure after freeze, §6), `docs/build-log.md` seeded with what is already
   known (§6).
10. `make verify` green on the empty pipeline; tag `wave-0`.

Research lanes start with Wave 0 (Sonnet, read-only + browse skill; each owns one
file under `docs/research/`):

- **RS1** Is a real Amazon Settlement V2 flat file publicly obtainable (A2X,
  Openbridge, Intentwise, DataChannel, Celigo, GitHub)? Verify the 24-column spec
  against SP-API docs. If a sample exists, record its licence before copying a
  byte. Output: `docs/research/amazon-v2-sample.md` (+ fixture if allowed).
- **RS2** SAFE-T India: filing-window arithmetic, exclusions (A-to-Z, seller-issued
  refund), evidence requirements, 2–3 winning claim examples from seller forums.
  Output: **source list with URLs and as-of dates, plus the claim examples for the
  drafter.** Not a rules digest: lanes F and K derive rules from the primary pages
  themselves (§1).
- **RS3** Amazon India referral-commission and closing-fee sources for three
  categories (recommend `electronics-accessories`, `home-kitchen`, `apparel`, as
  the wireframe already names them), including the 2026 changes; TCS s.52 (1%) and
  TDS 194-O facts. Output: **URLs, as-of dates, coverage decision. No numbers.**
  Lanes B and C each encode from the sources independently.

Exit: CI green on `main`, `wave-0` tag, research memos merged.

### Wave 1 — Fan-out on the contract (6 lanes)

| Lane | Owns | Tier | Governed by | Must not read | Ships |
|---|---|---|---|---|---|
| **B** generator + manifest | `generator/`, `tests/generator/` | A Fable | D9, D12, D18, D20, D3 | `ratecard/`, `labels/` | orders CSV, per-cycle V2 settlement files, bank CSV, `manifest.json` (as_of, cycle coverage window, seeded errors with `scenario_id` and expected paise ≥ 2× floor); measurement batch 500/120 × 5 seeds; demo batch 150/~20; 10k throughput batch; malformed-file variant (saved-as-CSV) for the D7 demo; duplicate-UTR case for D6 |
| **C** rate-card corpus | `ratecard/` | B Opus | D17, D14, D3 | `generator/` | 3 categories, every rule dated + URL-cited + `verified` flag; coverage declaration; `lookup(category, as_of) -> Rate \| UNCOVERED \| CONFIG_ERROR`; CONFIG_ERROR inside coverage fails verify naming category, slab, as_of |
| **D** parsers | `ingest/` | C Sonnet | D4, D7, spec doc | — | V2 TSV parser (24 cols), orders CSV, bank CSV; quarantine with row-level reasons and the one actionable guess (Frame 4); unknown `amount-description` → unclassified deduction; every line gets a `line_id` in the contract format |
| **E** audit log | `audit/` | C Sonnet | D21, D8 (ordering) | — | append, canonical JSON, `hash = H(canonical(entry − hash) + prev_hash)`, chain recompute (never byte compare), tamper test, orphan-pack detection (entry's `artifact_path` must exist) |
| **F** labels + holdout | `labels/` | B Opus | D12, P2, P3 | `evidence/`, `ratecard/`, `generator/` | one claimability label per `scenarios.py` ID with citation + as-of + `verified`; 25 adversarial holdout cases in canonical `FoldedOrder` form with expected (class, state, reason), including the SPF/VMS-shaped case exercising precedence step 4 |
| **G** dashboard | `dashboard/` | C Sonnet | D16, UI section, wireframe header comment | — | template lifted from the wireframe (not redesigned), render from `BatchReport` JSON, `demo.html` emitter with JSON inlined, FastAPI serve shell with approve/override/reject/flag endpoints calling a `gate` interface stub, parity test above the gate, Frame 2 gate variants, Frame 4 empty states, tabular numerals, four fills |

Wave-1 merge tasks (integrator): generator → parser round-trip integration test;
compute the labels checksum and write `FROZEN_LABELS_SHA256` into `contract.py`
(the freeze); D12 import test still green; fixture dashboard renders; tag `wave-1`.

### Wave 2 — Ledger, detectors, evidence (4 lanes)

| Lane | Owns | Tier | Governed by | Must not read | Ships |
|---|---|---|---|---|---|
| **H** fold + matcher | `ledger/` | B Opus | D20, D7, D10 (match-rate definitions) | — | `fold(lines, as_of) -> FoldedOrder`, cycle-ordered, deterministic tiebreak (posted-date, then line-kind order, then line_id); coverage-window check → OUT-OF-WINDOW; exact join on order id; strict match-rate numerator/denominator with quarantine kept in the denominator |
| **I** bank leg | `bankleg/` | C Sonnet | D6 | — | payout total ↔ UTR credit; duplicate UTR at same amount/day cannot double-satisfy; reported separately, never in match rate |
| **J** detectors | `detect/` | A Fable | D23, D1, D3, D19 (claimed line), D20 (cycle rules for 5 and 6), class table | `generator/`, `labels/` | `Detector` protocol; `make_finding()` raising on empty `source_line_ids`, on `claimed_line_id` outside them, on class/mechanism disagreement; c1 c2 c5 c6 c7 c8 each with unit tests on hand-authored `FoldedOrder`s; `registry.py` |
| **K** eligibility + evidence + deadlines | `evidence/` | A Fable | D14, D18, precedence steps 1–5 inputs, evidence-state model | `labels/` (D12 wall) | rules with citations and `verified` flags; evidence table per mechanism (`requirement, source, status, source_line_ids`); capability facts with validity windows (GST registration, program enrolment); deadline in calendar days against `as_of` with month-end and leap-day tests; "window exists but start date missing" surfaced as data for step 3 |

Lane K's agent is a different agent from Lane F's, by construction. Exit: findings
flow end to end on the demo batch (no states yet); reviewer pass; tag `wave-2`.

### Wave 3 — Assembly, drafting, measurement (3 lanes)

| Lane | Owns | Tier | Governed by | Ships |
|---|---|---|---|---|
| **L** triage pipeline | `triage/`, `cli.py` wiring (with integrator) | A Fable | D19, D10, D3, D4, state ladder, rupee partition, queue sort | dedup on `(order_id, class, claimed_line_id \| null)`; 15-pair overlap matrix, executable; per-order sum invariant; 7-step ladder as ordered code; partition as a pure function of (class-bucket, state); property tests (hypothesis): both additivity identities, exactly-one-state, sum invariant, partition purity; `BatchReport` assembly; `run_batch()` |
| **M** LLM drafter | `draft/` | B Opus | D2, D11, D1 | prompt with `{{amt:<line_id>}}` placeholders and magnitude bucket only; substitution layer; per-finding resumable artifacts recording model + version; checks (a) (a′) (b) as verify-time tests over committed artifacts; zero network in verify; provider per ADR-0004 |
| **N** metrics + throughput | `metrics/` | A Fable | D10, D12 (holdout line), D13, D9 | recall, per-class recall, precision, value-weighted recall, ₹-agreement with every disagreement listed, strict + adjusted match rate with the delta reconciled, holdout line, baseline row, N=5 mean ± range, `metrics.json`, README table generator; 10k throughput measured and asserted at ~3× measured |

Exit: `make verify` reproduces every published number with no network and no key;
tag `wave-3`.

### Wave 4 — Gate, artifacts, demo (3 lanes)

| Lane | Owns | Tier | Governed by | Ships |
|---|---|---|---|---|
| **O** gate + claim pack | `gate/`, and now `dashboard/serve.py` (ownership transfers from G) | B Opus | D8, D21, D16 | approve idempotent; override names the blocker kind (four fixed labels), marks pack OVERRIDDEN, records `approve_override` + `state_before`, never enters ₹ claim-ready; FLAG for UNEXPLAINED writes an audit entry only; **pack first, audit entry second**; claim pack = claim text + cited rows CSV + recomputation CSV; no-network test |
| **P** triage run + demo artifacts | `artifacts/` | integrator + Sonnet | D16, D11 | `make triage` on the demo batch with the user's key in env (never read by any agent), commit artifacts, `make demo` end to end keyless, D2 checks green, parity test green |
| **Q** measurement runs | `metrics/results/` | C Sonnet | D9, D13 | N=5 measurement runs published as measured; 10k throughput on this machine; CI threshold set; README tables |

Exit: judge path (`clone`, `make demo`, double-click) works with nothing installed;
tag `wave-4`.

### Wave 5 — Ship

- README (Sonnet): limitations verbatim from the design doc, reproduction steps,
  metrics tables, architecture diagram (`/diagram`), pointer to the build log.
- Integrator runs `/review` on the full diff, `/qa` on `make serve`, `/design-review`
  on the dashboard, `/cso` for a security pass (no secrets, no network in verify,
  path handling in claim-pack writes, audit-chain claims worded as tamper-evident).
- Descope ladder if needed: rung 0 = delete `detect/c7.py` and its partition line;
  rung 2 = delete `bankleg/`. Each rung is one lane's directory, by design.
- TODOS.md deferred design passes only if time remains.
- Video storyboard and recording checklist against the 5-minute script (the user
  records). Tag `v1.0.0`; GitHub release with `demo.html` and `metrics.json` attached.

Wall-clock estimate, assuming lanes take one to three hours and waves merge cleanly:
roughly two to three working days, leaving buffer inside a one-week window. Treat as
an estimate; the build log records the actuals.

---

## 4. Frozen seams (what Wave 0 pins, and who consumes it)

| Seam | Producer | Consumers |
|---|---|---|
| `contract.py` enums: `ErrorClass {1,2,5,6,7,8}`, `Mechanism {SAFE_T, SUPPORT_TICKET, CA_REVIEW, NONE}`, `State {CLAIM_READY, BLOCKED, UNEXPLAINED, NOT_CLAIMABLE}`, `BlockerKind {SELLER_ACTION, TIMING, PROFESSIONAL_REVIEW}`, `Disposition {QUARANTINE, UNCOVERED, OUT_OF_WINDOW, CONFIG_ERROR}`, `AuditAction` (8 values), `UnexplainedBasis {CODE_UNSEEN, CODE_KNOWN_NO_RULE}` | integrator | all |
| `Paise = int`, `compare_paise`, `MATERIALITY_FLOOR = 1000`, `TOLERANCE = 100`, `line_id` = `<file>:<row>` | integrator | all |
| class → allowed mechanisms table | integrator | J (enforced in `make_finding`), L |
| `types.Order`, `SettlementLine` (24 V2 columns + `line_id` + `kind`), `BankCredit`, `ParseResult` | integrator | D produces; H, I, L consume |
| `types.FoldedOrder` (order + cycle-ordered lines + coverage verdict) | integrator | H produces; J, K, F (holdout fixtures) consume |
| `types.Finding` (class, order_id, `source_line_ids`, `claimed_line_id`, amount, mechanism, evidence[], detector basis) | integrator | J produces; K enriches; L, M, O consume |
| `types.EvidenceItem`, `Eligibility`, `Deadline` | integrator | K produces; L consumes |
| `types.StateResult`, `RupeeLines` (7), `BatchReport` (the dashboard JSON, versioned) | integrator | L produces; G, N, O consume |
| `types.Manifest`, `SeededError` (with `scenario_id`) | integrator | B produces; N, F consume |
| `types.AuditEntry`, `ClaimPack` | integrator | E, O |
| `scenarios.py`: the seeded-error vocabulary (initial list below) | integrator | B seeds, F labels, K encodes rules, N scores |

Initial scenario vocabulary (IDs only; amounts and labels live elsewhere):
`C1_PLAIN, C1_WINDOW_EXPIRED, C1_WINDOW_DATE_MISSING, C1_GST_UNREGISTERED,
C1_ATOZ_EXCLUDED, C1_SELLER_REFUND_EXCLUDED, C1_INVOICE_PENDING, C2_PLAIN,
C2_SLAB_BOUNDARY, C5_PLAIN, C5_AWAITING_CYCLE, C5_SELLER_ISSUED, C5_ATOZ,
C5_REVERSED_LATER_CYCLE (true negative), C6_PLAIN, C6_PAID_LATER_CYCLE (true
negative), C6_OUT_OF_WINDOW, C7_TCS_MISMATCH, C7_TDS_MISMATCH, C8_CODE_UNSEEN,
C8_CODE_KNOWN_NO_RULE, BELOW_MATERIALITY, QUARANTINE_MALFORMED, UNCOVERED_CATEGORY,
DUPLICATE_UTR`. `CONFIG_ERROR` exists only as a test fixture that must fail verify.

---

## 5. GitHub: setup, maintenance, practices

The repo is the hiring artifact as much as the code. The load-bearing practices,
and nothing decorative:

**Setup (Wave 0, after the user re-authenticates `gh`)**
- Create (or confirm) the repository; recommend **public from day one**: the
  buildathon requires a public repo at submission, there are no secrets in the tree,
  and branch-protection rulesets are only available on public repos under the free
  plan. Push `main` **before** creating any ruleset: the rules reject the ref
  update that creates the branch, and pausing them afterwards is exactly the
  kind of action an automated session should not be allowed to take (build log,
  2026-09-04).
- Ruleset on `main`, created after the first push: pull request required
  (0 approvals, solo), status check `verify` required, force-push and deletion
  blocked. The integrator's Wave 0 goes in as a PR too.
- Files: `README.md`, `LICENSE` (MIT unless told otherwise), `.gitignore`,
  `.github/workflows/ci.yml`, `.github/PULL_REQUEST_TEMPLATE.md`, `SECURITY.md`
  (short: key via env only, zero network in verify, audit log tamper-evident not
  tamper-proof), `CONTRIBUTING.md` (twenty lines: run, test, commit convention).
- One GitHub issue per lane carrying the brief, labelled `wave:N`, `lane:X`,
  `tier:A|B|C`; one milestone per wave; every PR says `Closes #N`.

**Maintenance (every wave)**
- Trunk-based: `main` always green; lane branches live for hours, not days; rebase
  onto `main` before opening the PR; never rewrite `main`.
- Conventional Commits with package scopes
  (`feat(detect): …`, `test(triage): …`, `docs(build-log): …`). No attribution
  trailers, no co-author lines.
- PRs merged with `--no-ff` merge commits so each lane's history stays bisectable;
  PR title is the conventional summary; PR body follows the template, including the
  build-log section.
- CI on every push and PR: `make lint` (ruff) and `make verify`; the throughput job
  publishes seconds and asserts the D13 threshold; `metrics.json` and `demo.html`
  uploaded as build artifacts.
- Tags `wave-0` … `wave-4`, then `v1.0.0` with a release carrying `demo.html` and
  `metrics.json`.
- ADR per irreversible build-time decision in `docs/adr/`. The design doc's
  D-numbers are the product decisions; ADRs are the build ones.

---

## 6. "What broke, and how you got out"

`docs/build-log.md` is a first-class deliverable, kept honest in the same spirit as
the exception list the judges reward. One entry per incident:

```
### <date> · Wave N · Lane X · <one-line title>
What broke   symptom, exactly as observed (error text in a code block)
Root cause   the actual cause, not the first theory
How we got out   the fix, and what was tried first if it failed
What now prevents it   test / invariant / ADR / brief change, with the commit
Time lost   rough
```

Mechanics that make it happen rather than hoped for:
- Every lane's final report has a mandatory "What broke and how you got out"
  section (empty allowed, but must say "nothing broke" explicitly).
- The PR template carries the same section; the integrator moves entries into the
  log at wave close, citing the merge commit.
- The log opens with a "Before code" section pointing at the design doc's own
  reversals (Flipkart cut, fuzzy match cut, the seventh rupee line) and with the
  three things already found while planning: the dead remote, the invalid `gh`
  token, and the uncommitted design revision that would have fed every worktree a
  stale design.
- It closes, at Wave 5, with a short retrospective on the wave/lane method itself:
  where seams held, where they leaked, what the reviewer caught.

The label amendment procedure the design doc says does not exist (its "known limit
of the freeze") is ADR-0003: a post-freeze label change requires a build-log entry
stating what the rule work revealed, an ADR line, the checksum bump in
`contract.py`, and it may never be made in the same PR as an eligibility rule.

---

## 7. Lane brief template

Every lane receives exactly this, filled in:

1. **Mission** — one paragraph, in the design doc's words.
2. **Governing sections** — D-numbers and design-doc headings to read first.
3. **Files you own / files you must not read** — absolute paths; the D12 walls.
4. **Interfaces you consume** — `contract.py`, `types.py`, `scenarios.py`; frozen.
5. **Deliverables** — files, functions, fixtures.
6. **Tests required** — named, with the property each proves.
7. **Exit criteria** — `make lint` and `make verify` green in the worktree,
   conventional commits, no new dependencies without an interface change request,
   integer paise everywhere, no system clock, no network in verify.
8. **Report format** — Summary · Files · Tests and their results (pasted) ·
   Interface change requests · **What broke and how you got out** · Open questions.

---

## 8. Risks specific to agent-team execution

| Risk | Mitigation |
|---|---|
| Contract drift mid-wave | seams frozen per wave; integrator-only edits; change requests via report |
| Two "independent" encodings converge because agents read each other's files | read walls in briefs; D12 import test; ₹-agreement metric makes convergence visible |
| Shared-file merge conflicts (`Makefile`, `cli.py`, `conftest.py`) | integrator-owned; lanes register through files they own |
| Agent redesigns the wireframe or adds a dependency "to help" | explicit prohibitions in brief; reviewer checks; `uv.lock` diff visible in PR |
| System clock leaks into window arithmetic | verify-time test bans `date.today()` / `datetime.now()` outside `cli.py` |
| Worktree lacks a venv | every brief starts with `uv sync`; `.venv` ignored |
| Rate limits from parallel Fable lanes | cap 2 Fable, 6 lanes per wave |
| Real submission date shorter than assumed | descope rungs map to single directories; metrics harness, evidence model, audit trail never cut |
| API key exposure | key only in `.env` (sandbox-denied to agents) or shell env; `make triage` is the only reader; verify never needs it |

---

## 9. Decisions needed before Wave 0

Blocking:
1. Run `gh auth refresh -h github.com` in a terminal (authentication cannot be done
   by the agent).
2. Repo visibility: **public now** (recommended) or private until submission.

Non-blocking, defaults applied unless overridden:
3. Licence: MIT.
4. `make triage` provider: Anthropic API via the `anthropic` SDK, key in
   `ANTHROPIC_API_KEY`; model chosen at Lane M time from the claude-api reference.
5. Dev dependencies: pytest, hypothesis, ruff. Extras: fastapi + uvicorn (`serve`),
   anthropic (`triage`).
6. Baseline row in the accuracy table: yes (naive "flag every deduction above the
   floor"), so precision has something to beat.
7. AI-visibility gap (design doc Open Question 5): keep the drafter as the
   meaningful AI use and show `make triage` running live in the video; do not move
   class-8 interpretation to the LLM.
8. `field-guide.md`: gitignored, not committed.
9. Submission date: still unconfirmed; please read it out of the application flow.
