# ADR-0006: Class 1 files through a support ticket; SAFE-T is for refund-shaped claims

Date: 2026-09-05 · Status: accepted

## Context
The design doc gave class 1 (commission overcharge) `Mechanism.SAFE_T` as its
primary mechanism, and therefore a filing window, three SAFE-T exclusions, and
five of its seven seeded scenarios. Wave 0 research (`docs/research/safe-t.md`)
already flagged that SAFE-T might not cover fee overcharges at all, and the
briefs pre-delegated the call: lanes F and K were told to say so rather than
force a label, and the integrator would decide.

Two independent readings now agree. Lane F, reading the primary pages, found
SAFE-T scoped throughout to refund- and return-shaped loss: Amazon.in's seller
blog defines it as claims for losses on in-transit or customer-damaged returns,
the 2025-08-01 announcement is a damage-reimbursement policy scoped by return
reason, and the staff eligible/ineligible write-up describes it as appealing
refunds Amazon issued. Nothing found describes a fee-arithmetic dispute as
SAFE-T-eligible.

Lane F's reviewer corrected one leg of that argument, and the correction
strengthens the conclusion: the single India-confirmed "fee grievance routes to
Seller Support" thread is about commission not reversed on a refund, which is
class 5, not class 1. So the direct evidence about class 1 is absence of
evidence — but it is joined by an internal-consistency argument the reviewer
found independently. A SAFE-T window starts at a return scan or refund date. A
commission overcharge on a plain, un-refunded sale has no such event, so under
the old assignment lane F's own holdout case H15 expects class 1 to sit at
BLOCKED (timing) forever, while five of its seven class-1 labels silently
presuppose a refund that the scenario descriptions never mention. The mechanism
did not fit the class.

## Decision
- `ALLOWED_MECHANISMS[COMMISSION_OVERCHARGE]` and
  `PRIMARY_MECHANISM[COMMISSION_OVERCHARGE]` become `SUPPORT_TICKET`.
  `MECHANISMS_WITH_WINDOW` is unchanged: SAFE-T alone carries a window, so
  class 1 now has none, and ladder steps 2 and 3 cannot fire for it.
- The SAFE-T-shaped class-1 scenarios move to class 5, where the mechanism and
  the evidence actually bite: `C1_WINDOW_EXPIRED` → `C5_WINDOW_EXPIRED`,
  `C1_WINDOW_DATE_MISSING` → `C5_WINDOW_DATE_MISSING`, `C1_GST_UNREGISTERED` →
  `C5_GST_UNREGISTERED`, `C1_INVOICE_PENDING` → `C5_INVOICE_PENDING`.
- `C1_ATOZ_EXCLUDED` and `C1_SELLER_REFUND_EXCLUDED` are deleted: they encoded
  SAFE-T exclusions, and `C5_ATOZ` and `C5_SELLER_ISSUED` already carry them.
- Class 1 keeps `C1_PLAIN`, which lands CLAIM-READY at step 6 with
  report-derivable evidence and no window.
- The demo drills a class-5 claim, as `docs/plans/briefs/README.md` anticipated.

## Consequences
- The ladder is still exercised end to end: steps 2 and 3 now fire on class 5,
  which has a real window-start event, and the class-5 scenario set grows from
  five to nine. This also closes lane F's change request (c), that class 5 had
  no window-expired scenario.
- Made **before** the labels freeze, so it costs a relabel in lane F's fix
  round rather than an ADR-0003 amendment published beside the independence
  metric. This is the reason the decision was taken mid-wave rather than
  deferred: the freeze is the point of no return.
- Lane B encodes the new vocabulary from the start; no generator fix round.
- Lane K (Wave 2) writes eligibility rules for SAFE-T against class 5 only, and
  must not give class 1 a window.
- The design doc's class table row 1 and the video script's claim walk-through
  change with it.
- If a primary SAFE-T terms page is ever read (it is login-walled today) and it
  turns out to cover fee overcharges, this ADR is reversed by moving the
  mechanism back and re-homing the four scenarios; the labels would then need
  ADR-0003 treatment, because by then they are frozen.
