# TODOS

## Architecture

### Adapter conformance suite for a second marketplace

**What:** A parser-adapter interface plus a conformance test suite that any
marketplace adapter must pass, with Amazon Settlement Flat File V2 as the one
passing implementation, and a written contract stating what a second adapter must
supply (line-type vocabulary, date semantics, order-key mapping, fee attribution).

**Why:** The "one canonical schema, many marketplaces" generalization claim is
currently unevidenced. A conformance suite converts it from an assertion into a
testable interface, and is the cheapest first step whenever a real second-market
schema becomes available.

**Context:** Descope rung 4 (drop Flipkart) was pulled on 2026-09-04 during
`/plan-eng-review`, for integrity reasons rather than schedule ones: with seller
outreach cut and Open Question 2 unresolved, a Flipkart parser would have meant
inventing a format, generating synthetic data in that invented format, and parsing
it back. That proves nothing about generalization, and it is the same circularity
D12 works to avoid on the rules side reappearing on the schema side. Premises P2
and P3 in `docs/designs/leakproof-evidence-completeness.md` explain why a second
marketplace mattered. The SPF/VMS story survives meanwhile as a labeled
hand-authored case in the D12 adversarial holdout, in canonical form, exercising
precedence step 4 without any claim to Flipkart support. Start by extracting the
Amazon parser's implicit contract into an explicit Protocol, then write the
conformance tests against it.

**Effort:** M
**Priority:** P3
**Depends on:** A real, verified Flipkart Seller Hub settlement-sheet structure
(Open Question 2). Do not start this against an inferred schema — that is the
failure the rung-4 cut was made to avoid.

## Design

### Deferred design passes: keyboard nav, touch targets, motion, mobile

**What:** Specify keyboard navigation and focus order across the queue/detail
split (selecting a row changes the other pane, so focus management is not
obvious), 44px minimum touch targets, entrance motion for the metrics bar, and
mobile/tablet layout for the two-pane view.

**Why:** These are the last unspecified user-visible behaviours in the dashboard.
Keyboard order matters most: a two-pane layout where one pane drives the other is
the classic case where tab order becomes incoherent without a deliberate decision.

**Context:** Deferred 2026-09-04 during `/plan-design-review` by explicit scope
choice, which ran Passes 1 (information architecture), 2 (interaction states) and
4 (AI slop) and skipped 3, 5, 6 and 7. Colour contrast was already fixed under
decision 3A (every failing value lifted to at least 4.5:1, several to 7.0:1), so
the remaining accessibility gap is keyboard and touch only, not colour. Empty and
boundary states were also deferred initially but then built in the same session
and now live in Frame 4 of the wireframe. None of this deferred work appears in
the pitch video: the demo batch carries 20 exceptions by construction and the
recording is a desktop screen capture. Start from
`docs/designs/leakproof-exception-review-wireframe.html`, whose header comment
documents every design decision this file implements.

**Effort:** S
**Priority:** P3
**Depends on:** None. Best done once the dashboard exists in code rather than as
a wireframe, since focus order is easier to reason about against a real DOM.
