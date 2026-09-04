# ADR-0004: Audit action `flag` for the UNEXPLAINED gate

Date: 2026-09-04 · Status: accepted

## Context
D21 lists eight audit actions. The revised wireframe (2026-09-04) gives
UNEXPLAINED exceptions their own gate, FLAG FOR FOLLOW-UP and DISMISS, because
with mechanism `none` there is no claim to draft and no pack to write.

## Decision
`AuditAction.FLAG` is added; it writes one audit entry carrying the basis
(`code-unseen` / `code-known-no-rule`) and no artifact. DISMISS records as
`reject` with `state_before = UNEXPLAINED`; it is the same human decision
("do not pursue") and gets the same action name.
