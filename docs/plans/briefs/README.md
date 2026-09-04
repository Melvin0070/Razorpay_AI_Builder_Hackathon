# Lane briefs

One file per lane, filled in from the template in
`docs/plans/agent-team-build-strategy.md` §7. The integrator pastes the brief
into the Agent launch and into the lane's GitHub issue as a comment.

## Launching a wave

Custom roles in `.claude/agents/` load when a session starts, so **launch each
wave from a fresh session** (the Wave 0 build log records what happens
otherwise). Then, for every lane in the wave, in one message:

```
Agent(subagent_type = lp-core | lp-logic | lp-build, name = "<lane>-<slug>",
      isolation = worktree, run_in_background = true, prompt = <brief file>)
```

Concurrency caps: at most six lanes per wave, at most two `lp-core` lanes at once.

## Before cutting worktrees

- `git status` clean on `main`, `main` pushed, CI green.
- `contract.py`, `types.py`, `scenarios.py` reflect every interface change
  request accepted from the previous wave.
- Research memos the wave depends on are merged.

## Closing a lane

1. Read the lane report. Copy its "What broke" entries into `docs/build-log.md`.
2. Push the worktree branch, open the PR with the template, `Closes #N`.
3. Run `lp-reviewer` on the PR diff with the brief attached. Fix or push back.
4. Merge `--no-ff`. Confirm `make lint && make verify` green on `main`.

## Closing a wave

Integration tests that span lanes (owned by the integrator), tag `wave-N`,
build-log entries merged, interface change requests applied to the seams on
`main` before the next wave's worktrees are cut.
