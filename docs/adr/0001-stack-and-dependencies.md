# ADR-0001: Stack and dependencies

Date: 2026-09-04 · Status: accepted

## Decision
Python 3.12 managed by uv, with a stdlib-only runtime path for everything
`make verify` touches. Dev dependencies: pytest, hypothesis, ruff. Optional
extras: `serve` (fastapi, uvicorn) for the live approve interaction only;
`triage` (anthropic) for the opt-in LLM job only. Build backend `uv_build`,
src layout, `uv.lock` committed, CI installs with `--locked`.

## Why
The design commits to "stdlib-first" and to a judge who clones and runs
`make verify` with no key and no network. Keeping the runtime path
dependency-free makes that promise checkable: the lockfile has nothing a verify
path could import. Hypothesis is the one addition worth its weight, because
three of the hard gates are stated as properties (both additivity identities,
exactly-one-state) and property tests are the honest way to assert them.

## Consequences
No new dependency without an interface change request and a line here. The
reviewer flags any change to `pyproject.toml` or `uv.lock` in a lane PR.
