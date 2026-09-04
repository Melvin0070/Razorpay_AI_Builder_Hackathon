# Contributing

Solo hackathon project built by one integrator and a team of coding agents,
but run like a small team's repo.

- Read `CLAUDE.md`, then `docs/plans/agent-team-build-strategy.md`.
- `uv sync`, then `make lint` and `make verify` must be green before a PR.
- Trunk-based: branch from `main`, keep it short-lived, rebase before the PR.
  `main` requires a PR and a green `verify` check.
- Conventional Commits with the package as scope: `feat(detect): …`,
  `test(triage): …`, `docs(build-log): …`. No attribution trailers.
- Fill in the PR template, including "What broke, and how I got out".
- Integer paise for money. No `float` on an amount. No `date.today()`.
- No new dependency without an ADR.
