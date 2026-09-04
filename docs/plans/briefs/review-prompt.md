# Reviewer launch prompt (lp-reviewer)

Fill in and launch as `Agent(subagent_type = lp-reviewer, run_in_background = true)`
after a lane's branch is pushed and its PR is open. One reviewer per lane PR.

```
Review lane <X> · Wave <N> · PR #<pr> · branch `lane/<X>-<slug>` against `main`.

The lane's brief is `docs/plans/briefs/wave-<N>/<X>-<slug>.md`; read it first,
then `docs/plans/agent-team-build-strategy.md` §3 and §4 for the seams.

Diff to review: `git diff main...lane/<X>-<slug>` (the three-dot form). Run
`uv sync` and `make lint && make verify` on the branch; paste the tail.

Work the checklist in your role definition in order (ownership, D12 walls,
money, clock, network, dependencies, fidelity, tests, brief coverage). For the
D12 step, the forbidden packages for this lane are: <list from the brief>.

Report correctness gaps only, ranked by severity, each with a concrete failure
scenario. Then the mandatory final section: "What broke and how you got out"
entries visible in the diff or commit history that the lane report did not
mention. The lane report is pasted below.

--- lane report ---
<paste>
```
