Lane G · Wave 1 · GitHub issue #10 · role `lp-build` (Sonnet, high effort) · worktree branch `lane/G-dashboard`

## Mission
Turn the wireframe into the product's dashboard, rendered from a
`BatchReport`. The wireframe is the starting markup, not a picture of it: lift
its CSS and structure, make every number data-driven, and keep its decisions
(four states, four fill patterns, tabular numerals, one primary action per
state, the result shown instead of a dead button in the static export). The
same renderer serves two paths, `make demo` (self-contained HTML, keyless) and
`make serve` (FastAPI, live gate), and a test asserts they render identically
above the gate (D16).

## Governing sections (read first)
- Design doc: "UI" (the four load-bearing requirements), D16, D8 (what the
  gate does, for labels and consequences text), "Queue sort", "Rupee
  partition" (the seven lines and the not-claimable breakdown), D7 and D17
  (counts beside match rate).
- `docs/designs/leakproof-exception-review-wireframe.html`: every frame, and
  the header comment, which documents decisions 2A, 3A, 4A, 5A, 6A and the
  "subtle, do not fix" note about the class-7 row.
- `tests/fixtures/batch_report.demo.json` and `tests/fixtures/build_demo_report.py`:
  your input. Its docstring lists three places where the wireframe was
  internally inconsistent and the fixture follows the design instead.
- ADR-0004. Strategy §3 (lane G), §4.

## Files you own
- `src/leakproof/dashboard/` (renderer, template, `serve.py`, inline assets)
- `tests/dashboard/`

## Files you must not read
- None.

## Interfaces you consume (frozen)
- `types.BatchReport` and everything it contains; `serialize.to_jsonable`.
- `contract.State`, `STATE_ORDER`, `RupeeLine`, `BlockerKind`, `WindowStatus`,
  `AuditAction`.
- `leakproof.gate` stubs (they raise `NotImplementedError` until Wave 4; the
  served endpoints must return HTTP 501 with the lane and issue number until
  then).

## Deliverables
1. `render(report, *, mode: "static" | "served") -> str`, full HTML, no
   external resources of any kind (no CDN scripts, no web fonts; citation
   links are the only URLs allowed). Inline CSS from the wireframe; inline JS
   only for row selection, filter chips, and the served gate calls.
2. Metrics strip, all four tiers from the data: identified; the additivity
   bar with widths as proportions; legend with the not-claimable breakdown
   by all three reasons (rule, window expired, evidence unobtainable); tier
   3 lines with counts; tier 4 with both match rates, the delta explained,
   and the four not-processed counts.
3. Queue: filter chips with counts from queue states (so "Blocked 7" counts
   the class-7 row while the rupee line says 6); table grouped by state in
   `STATE_ORDER`, already sorted by the report; evidence-status column ahead
   of the deadline column; "File by" from `assessment.deadline`: `Nd · DD Mon`
   when open, `expired` when expired, `watch` when BLOCKED on timing,
   `—` when not applicable or start date missing; four state chips with
   the four fills and the `why` line.
4. Detail pane, top to bottom: source rows (cited `line_id`s), recomputation
   rows, evidence checklist with ☑/☐ and the `rule unverified` tag when a
   citation is `verified: false`, drafted claim (rendered text, or "not
   drafted" when absent), then the gate.
5. Gate per state (frame 2): CLAIM-READY → APPROVE & QUEUE + REJECT with the
   consequences text; BLOCKED / NOT-CLAIMABLE → one of the four fixed
   override labels chosen by blocker kind or reason + REJECT; UNEXPLAINED →
   FLAG FOR FOLLOW-UP + DISMISS. In static mode no buttons render: the
   static note appears instead, and an item with a `gate` record shows the
   approved-result block (frame 3). A single `<!-- gate -->` marker separates
   the two regions for the parity test.
6. Empty and boundary states (frame 4) from the data alone: zero exceptions
   (strip still renders, lists what was checked), every row uncovered (names
   the declared categories and the batch's categories from
   `rate_card_coverage` and the dispositions), nothing parsed (quarantine
   reasons, first two plus "…N more", the hint).
7. `write_demo_html(report, path)`: renders static mode with the report JSON
   inlined in a `<script type="application/json">` block.
8. `serve.py`: `create_app(report_path) -> FastAPI` with `GET /` (served
   mode) and `POST /gate/{action}/{finding_id}` for approve, override,
   reject, flag, calling `leakproof.gate.*` and translating
   `NotImplementedError` into 501. Import FastAPI lazily so `make verify`
   never needs the `serve` extra.
9. Indian digit grouping for rupees (`₹1,23,456`), paise dropped in the queue
   and shown in recomputation rows; tabular numerals everywhere digits align.

## Tests required (in `tests/dashboard/`)
- Renders the fixture in both modes without error; both outputs are byte-identical
  above `<!-- gate -->`.
- The strip shows `₹47,230`, `₹19,400`, `₹21,600`, `₹6,230`, `₹380`, `₹1,975`,
  `₹212`, `94.0%`, `97.9%`, and the counts 3 / 4 / 2 / 0.
- Filter chip counts 20 / 7 / 7 / 2 / 4; queue groups appear in `STATE_ORDER`.
- Static mode contains no `<button` and contains the static note; served
  mode contains exactly one primary button per selected state.
- The approved fixture row renders the frame-3 block with its audit seq.
- Each frame-4 state from a hand-built report.
- No `http://` or `https://` in `<script src>` or `<link href>`.
- Rupee formatter: `124000 → ₹1,240`, `12345678900 → ₹12,34,56,789`.
- `write_demo_html` output parses back to the same report JSON.

## Exit criteria
`make lint` and `make verify` green with the `serve` extra NOT installed.
No new dependency. Conventional Commits with scope `dashboard`. Do not push.

## Report format
1. Summary · 2. Files · 3. Tests · 4. Interface change requests (fields the
UI needed that `BatchReport` lacks) · 5. What broke and how you got out ·
6. Open questions (include: anything in the wireframe you chose not to carry
over, with the reason).
