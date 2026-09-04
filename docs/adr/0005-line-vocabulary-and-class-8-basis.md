# ADR-0005: Line vocabulary, fee GST, primary mechanism, and what class 8 means

Date: 2026-09-04 · Status: accepted

## Decisions
1. **Kind and transaction type are separate axes.** `LineKind` says what a
   settlement line is; `TransactionType` says under which event it was posted.
   A refund's commission reversal is `(REFUND, COMMISSION, positive)`. This
   follows how the V2 file itself reuses `amount-description` across
   transaction types and keeps the enum small.
2. **Class 8 has two bases with exact meanings.** `code-unseen`: the
   (amount-type, amount-description) pair is not in the vocabulary.
   `code-known-no-rule`: the pair is known, but the rate card declares neither
   an audited rule nor an acknowledgement for that kind. Kinds the rate card
   acknowledges (shipping fee, promotion, reserve) are expected deductions and
   never class 8, which is what keeps the queue from flooding with every
   ordinary fee.
3. **GST on fees is a line, `FEE_TAX`, and a rate-card rule.** The generator
   writes it so totals reconcile; detectors 1 and 2 report the fee delta
   excluding GST and note that GST on the delta follows the fee. The raw
   amount-description for it is `verified: false` pending RS1.
4. **A class with two allowed mechanisms files under its primary.** The
   design's precedence ladder has no "try the next mechanism" step; modelling
   a fallback would add a state transition the design never specified.
   `PRIMARY_MECHANISM` records the choice; the alternative stays documented in
   the class table.
5. **Detector 6's bound in the per-order sum invariant is the order value.**
   An unpaid order has no settlement lines, so "sum of exception amounts never
   exceeds that order's total deductions" is stated per bucket: classes 1, 2,
   5, 7, 8 against `FoldedOrder.deductions_paise`; class 6 against the order's
   own principal plus tax.
