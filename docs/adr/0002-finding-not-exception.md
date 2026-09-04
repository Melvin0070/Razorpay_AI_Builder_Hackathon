# ADR-0002: The design doc's "Exception" record is `Finding` in code

Date: 2026-09-04 · Status: accepted

## Decision
The record the design doc calls an exception (a detector result carrying
class, cited rows, amount and mechanism) is `types.Finding`. The word
"exception" stays in prose, in the UI ("exception queue") and in the audit
log's `exception_id` field (D21), whose value is the finding id.

## Why
`Exception` is a Python builtin. Shadowing it inside a package that also raises
real exceptions is the kind of trap that costs an hour under deadline and
reads as carelessness to a reviewer.
