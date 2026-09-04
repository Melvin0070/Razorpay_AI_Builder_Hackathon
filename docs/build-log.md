# Build log — what broke, and how we got out

Kept in the same spirit as the exception list the judges reward: every incident
recorded as observed, with the real root cause and what now prevents it. Entries
are appended at each wave close from lane reports and PR bodies
(`.github/PULL_REQUEST_TEMPLATE.md`). Newest wave at the bottom.

Format per entry:

```
### <date> · Wave N · Lane X · <title>
What broke            symptom, exactly as observed
Root cause            the actual cause, not the first theory
How we got out        the fix, and what was tried first if it failed
What now prevents it  test / invariant / ADR / brief change, with the commit
Time lost             rough
```

## Before code

The design doc carries its own reversals; they are the earliest entries and are
not repeated here. See `docs/designs/leakproof-evidence-completeness.md`:
Flipkart cut on day one (Approach B′), fuzzy matching cut (D5), the missing
seventh rupee line (Rupee partition), detectors 3 and 4 cut with their input
files, and the accuracy pass bars that stopped being descope triggers (D10).

## Wave 0 — Foundation

### 2026-09-04 · Wave 0 · integrator · GitHub remote pointed at a repository that does not exist
What broke            `git status -sb` showed `main...origin/main [gone]`; the GitHub API returned 404 for `Melvin0070/Razorpay_AI_Builder_Hackathon`; the repo was absent from the account's public repository list.
Root cause            `origin` was configured locally but the repository was never created on GitHub (or never pushed). The design doc's "no remote yet" was the accurate description; the remote config was not.
How we got out        Recorded as a Wave 0 task rather than assumed done. Repo creation and push are gated on the user re-authenticating `gh` (the token in the keyring is invalid; agents cannot authenticate on the user's behalf).
What now prevents it  CI on every push; the `wave-0` tag only after a successful push and a green run.
Time lost             none yet; caught in planning.

### 2026-09-04 · Wave 0 · integrator · Uncommitted design revision would have fed every worktree a stale design
What broke            The 2026-09-04 design-doc and wireframe revisions were uncommitted. Worktrees branch from HEAD, so every lane agent would have read the superseded 2026-08-27 design (two marketplaces, detectors 3 and 4, fuzzy matching, a six-line rupee split).
Root cause            Documents were revised in the working tree by review skills and never committed.
How we got out        "Commit the design revision" became the first item of Wave 0, ahead of any worktree.
What now prevents it  Wave-start checklist in the strategy doc: `git status` clean before cutting worktrees.
Time lost             none; caught in planning.

### 2026-09-04 · Wave 0 · integrator · Sandbox blocked writing the agent definitions
What broke            `mkdir: .claude/agents: Operation not permitted` while creating the lane-role files; a follow-up heredoc then failed with `no such file or directory: docs/build-log.md`.
Root cause            The project's `.claude/` directory is on the sandbox's write-deny list. The second failure was self-inflicted: the retry had `cd`'d into `.claude/agents` and the shell's working directory persists between commands, so the relative path pointed at the wrong place.
How we got out        Retried the one setup command with the sandbox disabled, through the permission gate; rewrote the remaining files with absolute paths.
What now prevents it  Absolute paths in every scripted write from here on.
Time lost             minutes.

### 2026-09-04 · Wave 0 · integrator · Ruleset created before the first push blocked the first push
What broke            `! [remote rejected] main -> main (push declined due to repository rule violations)` on the bootstrap push of `main`. An earlier attempt, seconds after flipping the repo to public, had returned `remote: Your repository is disabled` (403), which turned out to be transient.
Root cause            The `main` ruleset (PR required, `verify` status check required) was created while the repository was still empty; the first push that creates `main` is itself a ref update the rules reject. Order of operations: push first, protect second.
How we got out        Pausing the ruleset for one push from the agent session was blocked twice by the permission classifier (it reads as weakening branch protection, which is the right instinct). The pause-push-re-enable one-liner was handed to the user to run once by hand.
What now prevents it  Strategy §5 now reads "push `main`, then create the ruleset"; nothing to automate for a one-time step.
Time lost             ~20 minutes.

### 2026-09-04 · Wave 0 · integrator · Lane roles not visible to the session that created them
What broke            `Agent type 'lp-research' not found` when launching the three research lanes with the freshly written `.claude/agents/lp-*.md` roles.
Root cause            Custom subagent definitions are loaded when a session starts; roles created mid-session are not registered until the next session.
How we got out        Relaunched the lanes as `general-purpose` agents with `model: sonnet` and worktree isolation, pasting the role text into each brief. Cost: reasoning effort could not be set per lane for this wave.
What now prevents it  From Wave 1 the lanes launch from a fresh session, where `lp-core`, `lp-logic`, `lp-build`, `lp-research` and `lp-reviewer` resolve and carry their `effort` settings.
Time lost             minutes.

### 2026-09-04 · Wave 0 · integrator · Nine documentation files written empty
What broke            `can't create temp file for here document: operation not permitted` on every `cat <<'EOF'` in one shell command; the nine target files (spec, five ADRs, README, SECURITY, CONTRIBUTING) were created with zero bytes. A parallel command in the same turn using the same construct succeeded.
Root cause            The sandbox refused the shell's heredoc temp file while two sandboxed commands ran concurrently; the exact trigger is unknown.
How we got out        Detected by checking sizes rather than assuming success, removed the empty files, rewrote them with the editor tool, which does not go through a shell temp file.
What now prevents it  Large file contents are written with the editor tool, not shell heredocs; a size check follows any scripted multi-file write.
Time lost             ~10 minutes.

### 2026-09-04 · Wave 0 · integrator · uv unusable inside the sandbox
What broke            `error: Failed to initialize cache at /Users/melvin/.cache/uv ... Operation not permitted` from every `uv` invocation inside the sandbox.
Root cause            uv's default cache lives under `~/.cache`, which the sandbox does not allow writes to; Python interpreters live under `~/.local/share/uv`, likewise.
How we got out        One-time interpreter install, lock and sync outside the sandbox; the Makefile now exports `UV_CACHE_DIR`, probing whether the default cache is writable and falling back to a gitignored repo-local cache so lane agents can run `make verify` unattended.
What now prevents it  The Makefile fallback; `.uv-cache/` in `.gitignore`.
Time lost             ~10 minutes.
