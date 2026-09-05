Lane M · Wave 3 · GitHub issue #16 · role `lp-logic` (Opus, high effort) ·
worktree branch `lane/M-draft`

**Demo-priority note (2026-09-05):** this build is compressing waves 2-5 into
one push toward a working `make demo` / `make triage` for a pitch video. The
drafter is the one place the LLM is visibly doing real work on camera, so the
prose quality and the D2 numeral-ban tests matter more than test-suite breadth
elsewhere. Trim exhaustive edge-case tests if they cost more than ~20 minutes;
the three D2 checks and one golden end-to-end draft are non-negotiable.

## Mission
Draft the human-readable claim text for a `CLAIM_READY` or `BLOCKED` exception,
using an LLM that never sees or emits a rupee amount. The prompt carries only
`{{amt:<line_id>}}` placeholders and a deterministically bucketed magnitude
label (`minor|moderate|major`); a deterministic substitution layer resolves the
placeholders afterward against that exception's own evidence line set. This is
the whole reason "deterministic money, probabilistic language" is provable: any
number the model emits is invented, and the D2 tests catch it before it
reaches the screen.

## Governing sections (read first)
- Design doc: **D2** (LLM numeral ban, the exact three checks (a)(a′)(b), all
  run at verify time against committed artifacts, zero network, zero key),
  D11 (`make triage` = opt-in, resumable, records model + version per
  exception; `make verify` never calls the network), the "Demo script" section
  minute 3 (what the drafted claim needs to show on screen: source rows →
  recomputation → drafted SAFE-T claim with deadline countdown).
- `docs/research/safe-t.md` — the 2-3 winning claim examples RS2 found; use
  them as the register/structure the prompt asks for, never copy their prose
  verbatim into your own prompt or fixtures (copyright).
- `docs/plans/wave-1-handoff.md`.

## Files you own
- `src/leakproof/draft/`
- `tests/draft/`
- `tests/fixtures/drafts/` — committed per-exception artifacts for the demo
  batch (placeholder-form and rendered-form), so `make verify` and `make demo`
  are both keyless (D16). You will not have real demo-batch exceptions yet
  (lanes H/J/K/L may still be mid-flight); build these from 3-4 hand-authored
  `Finding`+`Assessment` fixtures of your own instead, one per mechanism
  (SAFE-T, support-ticket, CA-review is never drafted — skip it, ADR-0006/
  design doc: class 7 never reaches CLAIM-READY so it never gets a claim
  drafted). The integrator regenerates the real demo-batch artifacts once
  every lane has merged.

## Interfaces you consume (frozen, in `types.py`)
- `Finding`, `Assessment`, `StateResult`, `Draft`.
- `contract.Mechanism`, `RupeeLine`, `MATERIALITY_FLOOR_PAISE`.
- The stub signatures in `draft/__init__.py`.

## Deliverables
1. **Prompt construction.** Given a `Finding` + `Assessment` (+ its
   `StateResult` for a BLOCKED claim, so the prompt can name the blocker), a
   deterministic bucketer maps `amount_paise` to `minor|moderate|major`
   (document your bucket boundaries — they are yours to choose, e.g. below
   ₹500, ₹500-5000, above ₹5000, adjusted to whatever reads sensibly against
   `MATERIALITY_FLOOR_PAISE`). The prompt text passed to the model contains:
   the mechanism, the class's plain-English description, the magnitude label,
   the evidence requirements and their status, the deadline days-left if any,
   and `{{amt:<line_id>}}` tokens for every line the exception cites — **never**
   a rendered amount, currency symbol, or digit standing in for a rupee value.
2. **Provider call.** `anthropic` SDK, model `claude-sonnet-5`, key from
   `ANTHROPIC_API_KEY` read at call time only (never logged, never written to
   an artifact). This code path is reached only by `make triage`, never by
   `make verify`.
3. **Substitution layer.** `render(template_text, finding) -> str` replaces
   every `{{amt:<line_id>}}` with the paise amount for that `line_id`,
   formatted as `₹` + comma-grouped rupees (paise floor per D3), raising if a
   placeholder's `line_id` is not among the exception's own
   `source_line_ids`/evidence `source_line_ids` — that raise is D2(b) made
   structural, not just tested.
4. **Resumable per-finding artifacts.** One committed file per `finding_id`
   under `tests/fixtures/drafts/` (JSON: template_text, rendered_text,
   magnitude, model, model_version, placeholders) so a `make triage` rerun
   skips exceptions that already have an artifact and a partial run (timeout
   mid-batch) reports what is missing rather than losing prior work.
5. **The three D2 checks, as `make verify` tests over the committed
   artifacts, zero network:**
   - (a) no currency-formatted token (`₹`, a bare number with 3+ digits, a
     comma-grouped number) appears anywhere in `template_text`.
   - (a′) no bare numeric token in `template_text` equals any line amount in
     that exception's own line set within `TOLERANCE_PAISE` — this is a
     tripwire on the substitution layer, vacuously true when template_text has
     no numbers in it at all, which is the expected case.
   - (b) every `{{amt:...}}` token in `template_text` resolves to a `line_id`
     inside that exception's own evidence set (already enforced structurally
     by deliverable 3, but write the verify-time test independently so it
     catches a fixture that was hand-edited after the fact).

## Tests required (in `tests/draft/`)
- Bucketer: one case per boundary, plus the boundary values themselves.
- Substitution: a template with 1, 2, and 0 placeholders; a bad `line_id`
  raises.
- The three D2 checks above, each with a fixture that is meant to fail it (a
  deliberately bad committed artifact used only inside the test, not among the
  real demo fixtures) proving the check actually catches something.
- One golden end-to-end test: hand-authored `Finding` → prompt string built →
  (mocked or recorded) model response → rendered claim text containing the
  right rupee figure and no invented one.

## Exit criteria
`make lint` and `make verify` green with **zero network calls** (mock or skip
the live API call in tests — never call `anthropic` from a test that
`make verify` runs). No new dependency beyond `anthropic` (already an extra
per `pyproject.toml`'s `triage` extra — if it is missing, that is your
interface change request, not a reason to add a different SDK). No system
clock. No float on the money path. Conventional Commits, scope `draft`,
committed as you go. Do not push.

## Report format
1. Summary · 2. Files · 3. Tests · 4. Interface change requests ·
5. What broke and how you got out · 6. Open questions.
