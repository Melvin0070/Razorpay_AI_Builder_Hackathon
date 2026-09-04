# ADR-0003: Amending a claimability label after the freeze

Date: 2026-09-04 · Status: accepted

## Context
D12 freezes the hand-authored claimability labels before any eligibility rule
is coded, recording their SHA-256 in `contract.FROZEN_LABELS_SHA256`. The
design doc records that no procedure existed for "while coding the rules I
found a label I believe is wrong", and that under a compressed schedule this
is near-certain.

## Decision
A label may change after the freeze only through all of the following, in one
PR that touches nothing else:
1. a `docs/build-log.md` entry stating which label, what the rule work
   revealed, and the primary source that settles it;
2. a line appended to this ADR's amendment table;
3. the new checksum written into `contract.py` by the integrator;
4. never in the same PR as a change to `evidence/`, and never authored by the
   agent that owns `evidence/`.

The metrics harness publishes the count of post-freeze amendments beside the
holdout line, so a reader can weigh the independence claim accordingly.

## Amendments
| Date | Label | Reason | Source | Commit |
|---|---|---|---|---|
