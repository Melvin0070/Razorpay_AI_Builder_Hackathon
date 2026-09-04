## What

<!-- One paragraph. Lane ID and wave, e.g. "Wave 2 · Lane J · detectors". Closes #N. -->

## Why

<!-- The design-doc decisions this implements, by D-number, and any ADR added. -->

## Tests

<!-- Named tests and the property each proves. Paste the tail of `make lint && make verify`. -->

## Interface change requests

<!-- Changes needed in contract.py / types.py / scenarios.py / Makefile / CI, or "none". -->

## What broke, and how I got out

<!-- One entry per incident, or "nothing broke". Copied into docs/build-log.md at wave close.
What broke:
Root cause:
How I got out:
What now prevents it:
-->

## Checklist

- [ ] Only owned paths touched; no integrator-owned file edited
- [ ] No path from the "must not read" list read or imported (D12)
- [ ] Integer paise only; no `float` on an amount; no `date.today()` / `datetime.now()`
- [ ] No network on any `make verify` path; no new dependency
- [ ] Conventional Commits, package scope, no attribution trailers
