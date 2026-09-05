# ADR-0007: Six fixed override labels, not four

Date: 2026-09-05 · Status: accepted

## Context
The wireframe's decision 4A names four fixed labels for the override action, so
that a human who overrides a block says in fixed words what they are overriding
and the audit trail records it (D8). The four are keyed on `BlockerKind`, which
has three values, plus the evidence-unobtainable case.

The evidence-state ladder emits NOT-CLAIMABLE at three steps, not one: step 1
(an eligibility rule excludes the claim), step 2 (the filing window has closed)
and step 4 (the evidence can never exist). Only step 4 has a label. Lane G
therefore mapped the other two onto the nearest fit, and its reviewer found the
result says the opposite of the truth: a row whose why-line reads
`window expired 21 Aug — SAFE-T, 7 days ago` renders a button reading
`DRAFT BEFORE WINDOW RESOLVES`, and a row excluded by the A-to-z rule renders
`Drafts without: A-to-z Guarantee refund (SAFET-01)`, which reads as a missing
document rather than a policy exclusion.

## Decision
Six labels, a total function over (state, blocker kind or not-claimable reason):

| state · kind or reason | label |
|---|---|
| BLOCKED · seller-action | DRAFT WITHOUT EVIDENCE |
| BLOCKED · timing | DRAFT BEFORE WINDOW RESOLVES |
| BLOCKED · professional-review | DRAFT WITHOUT CA REVIEW |
| NOT-CLAIMABLE · evidence-unobtainable | DRAFT WITHOUT EVIDENCE THAT CANNOT EXIST |
| NOT-CLAIMABLE · rule | DRAFT DESPITE EXCLUSION |
| NOT-CLAIMABLE · window-expired | DRAFT AFTER WINDOW CLOSED |

The mapping raises on any combination outside the table rather than falling back
to a nearest fit, so a new state or reason fails loudly instead of shipping a
label that misdescribes what the operator is agreeing to.

## Consequences
- The count in decision 4A changes from four to six; the property that mattered
  was that the set is *fixed and named*, not that it has four members, and that
  property is preserved and now total.
- The override still never enters ₹ claim-ready, still marks the pack
  OVERRIDDEN, and still records `approve_override` with `state_before` (D8).
  Nothing about the gate's behaviour changes; only what the button says.
- An override label is the last thing a human reads before agreeing to file a
  claim they were told not to file. A label that inverts the reason is worse
  than no label, because it invents a justification — which is the failure this
  project's whole architecture is built to avoid.
