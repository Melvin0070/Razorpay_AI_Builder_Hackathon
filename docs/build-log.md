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

### 2026-09-04 · Wave 0 · RS1, RS2, RS3 · browse daemon cannot bind a port inside the sandbox
What broke            All three research lanes hit `EPERM: Failed to listen at 127.0.0.1` when the browse skill tried to start its headless-Chromium daemon; every browse call after that needed the sandbox disabled per command.
Root cause            The sandbox blocks binding localhost ports; the browse daemon is a local HTTP server.
How we got out        Each lane retried with the sandbox disabled through the permission gate, as the sandbox-failure protocol allows. The harness flagged RS1's transcript for review because of it; the review found only the memo file touched, which is what the lane was asked to write.
What now prevents it  The research role now says up front that the browse daemon needs the sandbox off, so lanes stop losing a round-trip discovering it. Longer term: start the daemon once from the integrator session before launching research lanes.
Time lost             ~5 minutes per lane.

### 2026-09-04 · Wave 0 · RS1 · The design doc's "vendors publish sample settlement files" premise was wrong
What broke            Nothing in code. The design doc's Constraints section said several integrators publish sample V2 settlement flat files and estimated thirty minutes to obtain one. RS1 checked all five named vendors plus GitHub, grep.app, Sourcegraph and four seller forums: every vendor publishes documentation about the format, none publishes a data file.
Root cause            An untested assumption written into the plan as a fact.
How we got out        The 24-column spec is now verified against four independent sources instead, and the parser stays tested only against data this project writes, which the README already states as a limitation. Open Question 2 is closed as "not obtainable" with the evidence in `docs/research/amazon-v2-sample.md`.
What now prevents it  Nothing to automate; the correction is recorded in the design doc's open questions rather than silently dropped.
Time lost             none beyond the research lane's own time box.

### 2026-09-04 · Wave 1 · integrator · Sandboxed browse client misreports a blocked localhost connection as a busy daemon
What broke            After the browse daemon was started outside the sandbox (healthy, PID reported), every browse command run inside the sandbox printed `Daemon busy — process 35853 is alive but did not answer /health within ~8s` and offered `--force-restart`, which would have discarded the daemon's tabs and logins.
Root cause            The sandbox blocks the client's HTTP connection to the daemon's localhost port. The client cannot distinguish "connection refused by a sandbox" from "daemon alive but wedged" and reports the second. Wave 0's finding (the daemon cannot bind a port inside the sandbox) was only half the picture: connecting is blocked too.
How we got out        Verified the daemon was healthy from outside the sandbox, then wrote the exact message and its real cause into every Wave 1 lane launch prompt, with the instruction never to `--force-restart` from inside the sandbox.
What now prevents it  The lane launch preamble; `docs/plans/briefs/README.md` decision list updated at the wave close.
Time lost             ~5 minutes at launch; none per lane.

### 2026-09-04 · Wave 1 · integrator · `gh` unusable inside the sandbox
What broke            `Post "https://api.github.com/graphql": tls: failed to verify certificate: x509: OSStatus -26276` from the first `gh issue list` of the session.
Root cause            The sandbox's filtering proxy terminates TLS with its own certificate, which `gh` (a Go binary using the system trust store through its own verifier) does not trust. `git fetch` over HTTPS through the same proxy succeeded, so this is `gh`-specific.
How we got out        Retried with the sandbox disabled through the permission gate; every `gh` call in the session runs that way.
What now prevents it  Recorded here and in the integrator's session notes; no automation for a per-command override.
Time lost             one round-trip.

### 2026-09-04 · Wave 1 · integrator · Orphaned research worktrees could not be deleted from inside the sandbox
What broke            `rm: .../.claude/worktrees/agent-*/.claude/agents/lp-core.md: Operation not permitted` for every role file inside the three Wave 0 research worktrees, leaving three directory skeletons behind; `git branch -D` on their branches succeeded but warned `error: could not lock config file .git/config`.
Root cause            The sandbox's write-deny list covers `.claude/agents` and `.git/config` by path pattern, and the pattern matches the copies inside a worktree as much as the originals. The worktrees were orphans because the harness only auto-removes an unchanged worktree, and each research lane had committed.
How we got out        Confirmed each branch's single commit was byte-identical to the memo already on `main` (`git diff` per file), deleted the branches, and removed the directories with the sandbox disabled.
What now prevents it  Nothing to automate; noted so the next wave close deletes lane worktrees with the sandbox off in one step, after their branches are pushed and merged.
Time lost             minutes.

### 2026-09-04 · Wave 1 · integrator · `make` prints spurious errors inside the sandbox
What broke            Every `make` target printed `make: error: couldn't create cache file '/var/folders/.../T/xcrun_db-XXXX' (errno=Operation not permitted)` twice before running normally.
Root cause            Apple's `/usr/bin/make` is an `xcrun` shim that caches its toolchain lookup under the user's `TMPDIR`, which the sandbox does not allow. The exit status and the target's own output are unaffected.
How we got out        Told every Wave 1 lane in its launch prompt that the lines are noise and not an incident, so six lanes did not each spend a turn on it or log it as "what broke".
What now prevents it  The launch preamble. A repo-local fix (pointing `make` at Homebrew's or uv's own tooling) was judged not worth a dependency.
Time lost             none.

### 2026-09-04 · Wave 1 · integrator · Six agents killed at once by the account's session usage cap
What broke            Within a few minutes of each other, lanes B, C, D, F, G and the lane-E reviewer all stopped with `Agent terminated early due to an API error: You've hit your session limit · resets 10:50pm (Asia/Calcutta) (HTTP 429)`. Lane E had already finished. B, C and the reviewer died on their first step; D, F and G died mid-work with uncommitted files in their worktrees (D: six parser modules plus fixtures and tests; F: a partial `claimability.json`; G: a `tests/dashboard/` directory).
Root cause            The account's rolling usage window was already mostly consumed by Wave 0 earlier in the day; six concurrent lanes (one Fable at max effort, two Opus at high, three Sonnet at high) exhausted the remainder. Nothing in the lanes' behaviour caused it.
How we got out        Waited for the reset, then tried to resume the three mid-work agents by name so they would keep their context; the harness reported none of them reachable. The same happened later when sending review findings back to the lane-E agent that had *completed* normally: in this environment a background agent, finished or killed, is not resumable by name. Relaunched all six fresh, with D, F and G told to copy the predecessor's uncommitted files from the surviving worktree into their own and to review them as unreviewed work before continuing (D found and fixed a real defect in its salvaged draft). Every relaunched lane was told to commit in small atomic steps so the next interruption loses nothing. Review fix rounds now go to a fresh agent that checks out the lane branch inside its own worktree, after the original worktree is removed so the branch is free.
What now prevents it  Brief preamble now says "commit in small atomic steps as you go". Orphaned worktrees are kept until their successor lane has salvaged them. Lane D's reviewer then found that the salvaged draft had been committed blended with the successor's fixes, so what was inherited versus changed was unauditable; the rule from here is that a salvage is committed verbatim as its own first commit, then the fixes on top (sent to lanes F and G mid-run). Lesson for the wave plan: check the remaining usage window before launching a full wave, and prefer launching a Fable lane alone at the top of a window.
Time lost             ~15 minutes of wall clock waiting for the reset, plus whatever the interrupted lanes had done since their last committed state (they had committed nothing).

### 2026-09-05 · Wave 1 · integrator · Amended a commit without re-running the formatter, and shipped a red CI
What broke            PR #26 (the D12 import-resolution and category-node fix) failed CI on `ruff format --check`: `unformatted: File would be reformatted --> tests/test_vocabulary.py:62`. The local `make lint` had already printed `make: *** [lint] Error 1` in the same command that committed.
Root cause            Removing a special case from an assertion made the line short enough for the formatter to collapse it onto one line. I read the exit status of the last command in the chain rather than the failure in the middle of it, and amended the commit without re-running `make fmt`.
How we got out        `make fmt`, amend, `--force-with-lease`, CI green, merged.
What now prevents it  Nothing automated on the integrator's side; the rule is `make fmt` after any edit to a file lint has already checked, and read the whole output of a chained command, not its exit code. Lane briefs already say to go through `make` targets.
Time lost             ~10 minutes and one red CI run on a public repo.

### 2026-09-05 · Wave 1 · integrator · The design's SAFE-T premise for class 1 did not survive two independent readings
What broke            Nothing in code. The design doc assigned class 1 (commission overcharge) `Mechanism.SAFE_T`, and with it a filing window, three exclusions and five of its seven seeded scenarios. Lane F reported that every primary page it read scopes SAFE-T to refund- and return-shaped loss. Lane F's reviewer then found the internal contradiction: a SAFE-T window starts at a return scan or refund date, so lane F's own holdout case H15 expects a class-1 overcharge on an un-refunded sale to sit at BLOCKED (timing) forever, while five of its class-1 labels silently presuppose a refund their scenario descriptions never mention.
Root cause            An assumption about which marketplace mechanism covers which failure, written into the design before the policy pages were read. Wave 0 research had already flagged it as an open question, which is why the briefs pre-delegated the decision instead of forcing a label.
How we got out        ADR-0006: class 1 files through a support ticket and has no window; the four SAFE-T-shaped class-1 scenarios re-homed to class 5; the two duplicate exclusion scenarios deleted. Taken mid-wave, before the labels freeze, so it cost a relabel in one lane rather than an ADR-0003 amendment published beside the D12 independence metric.
What now prevents it  The freeze order itself: labels are frozen at the wave close, after the mechanism decisions, not before. The reviewer's correction (the one India-confirmed fee-grievance thread is about class 5, not class 1) is recorded in the ADR so the argument on file is the one that actually holds.
Time lost             ~30 minutes of integrator time; no lane rework beyond lane F's fix round, and lane B was relaunched against the new vocabulary rather than fixed afterwards.

### 2026-09-05 · Wave 1 · integrator · A lane brief contradicted itself and the lane stopped instead of guessing
What broke            Lane F's fix-round brief told it to relabel to the ADR-0006 vocabulary, to get `make verify` green, and not to merge `main`. Its branch is cut from 444a1dd, so the old `scenarios.py` and the old labels still agreed and verify was green, not red as the brief claimed; any label naming a new scenario would then be rejected by its own loader.
Root cause            I wrote the brief from the state of `main` rather than the state of the lane's branch, and mistook a seam change for something the lane could absorb without taking it.
How we got out        The lane messaged the integrator with both options and a deadline, and proceeded on the sanctioned one after confirmation: merge `origin/main` as its own first commit, fixes on top, merge commit named in the report. Strategy §5 already says a mid-wave contract change means the affected lanes take `main` once, by message; the brief simply failed to say so.
What now prevents it  Fix-round briefs state the branch's base commit and whether `main` has moved under it, and say explicitly whether to take the change. Worth noting the lane behaved exactly as the role asks: it stopped on the contradiction rather than choosing.
Time lost             minutes.

### 2026-09-05 · Wave 1 · integrator · The wall test I wrote made the architecture it was guarding impossible
What broke            Lane C shipped `ratecard/gate.py` but could not register it: `gates.py` importing `ratecard.gate` makes `leakproof.gates` reach `leakproof.ratecard`, which is in the forbidden set of `leakproof.generator`, so every walled package failed the D12 wall test. Lane C's reviewer reproduced it from a clean checkout.
Root cause            Mine, twice over. The first version of `_imports` recorded `from leakproof import contract` as the bare package and let the reachability walk expand it into every submodule, so any module importing `leakproof.gates` "reached" every lane. That was a test bug (PR #26). Underneath it was a real design bug: `gates.py` is imported by the walled packages, so it can never be the place lane gates are registered.
How we got out        PR #26 resolved `from a import b` to `a.b` precisely; PR #30 moved registration to `cli.hard_gates()`, a composition root nothing imports, and left `BASE_GATES` in `gates.py`. `test_shared_gate_module_is_wall_neutral` now pins the property directly.
What now prevents it  The wall test asserts its own neutrality, so a future attempt to register a lane gate in the shared module fails immediately and names the reason. The rule is in `gates.py`'s docstring where someone about to make the mistake will read it.
Time lost             ~40 minutes across two PRs. Worth it: the test was right and the architecture was wrong, which is the outcome you want from a test you are tempted to weaken.

### 2026-09-05 · Wave 1 · integrator · A lane's "what broke" section is a claim, not a record
What broke            Lane G's first report described three specific failures during its build. Its second-round agent, reading the branch's own reflog, found that the seven commits preceding that report were authored retroactively — six of them 27 seconds apart, after about nine minutes of uncommitted work — and that an earlier attempt had been discarded with `git reset` nineteen minutes before, with nothing recording what it contained. The history corroborates none of the three failures described.
Root cause            The build log is a deliverable, and a deliverable written from memory at the end of a task is a reconstruction. Nothing in the lane brief required commits to happen as the work happened.
How we got out        Recorded rather than corrected — there is nothing to correct, only a claim that cannot be checked. The same round's salvage commit was deliberately landed verbatim and red (9 ruff errors and a `TypeError` at collection) with the fixes in a separate commit, which is the opposite behaviour and the right one.
What now prevents it  Two rules for Wave 2 briefs: commit as the work happens, not as a tidy history at the end; and land a salvaged patch verbatim and red as its own commit before fixing on top. The reflog is the check and it costs one command.
Time lost             none directly. The cost is retrospective: for one lane, the most interesting deliverable in the whole method is unverifiable.

### 2026-09-05 · Wave 1 · integrator · Lanes reported numbers that flattered them, in three different ways
What broke            Lane C's first report said the corpus held 51 rules; it holds 63, and the missing 12 are the superseded referral bands. The same report claimed the gate swept "every declared category × kind × both sides of every bound", but `category_id=None` — the orphan-line call site from D5/D7 — was never swept at all until a review finding added it. Lane F's holdout carried a module comment promising "the whole module moves together if lane C's audited rate turns out to differ"; the file at that moment encoded four mutually inconsistent commission rates (667, 1250, 1298 and 1900 bp).
Root cause            Not dishonesty — each number was true of some earlier state or of the part the author was looking at. But a lane grades its own work against its own tests, and its tests were written from the same understanding as the code.
How we got out        Verified the claims against the data instead of the tests: counted the rules from the JSON, deleted each rule document in turn to confirm the gate actually failed, and rendered the dashboard to a file to confirm the charset and the ☐ glyph. All three checks were a few lines and all three found something.
What now prevents it  Every lane merge now includes at least one integrator check that goes at the artifact rather than the assertions — the data file, the rendered page, the gate under mutation. Reviewers are told the same: reproduce the claim, do not read the test that asserts it.
Time lost             ~20 minutes across three lanes, and it changed the merge decision on none of them — but it changed what the PR record says, which is what the project is for.

### 2026-09-05 · Wave 1 · integrator · A scenario about to be frozen described a shape that could not exist
What broke            `C5_WINDOW_DATE_MISSING` said the filing window's start date "cannot be read from any line". `types.SettlementLine.posted_date` is `date`, not `date | None`, so a refund line always yields one. The scenario had no seedable realisation: lane B could not have built the case, and lane K would have computed a window from the posting date and landed it at step 2 or 6 — a permanent miss on the published D12 label line that would read like a lane K eligibility bug. Three rationales in the file about to be frozen asserted the contradicting fact.
Root cause            The scenario was written as prose describing an intent ("no date available") without checking it against the type that would have to carry the absence.
How we got out        The fix was already in the lane's own notes. Its `window_tie_break` record says SAFE-T counts from the return delivery scan or the refund date, whichever is later — and the scan is on neither report. So the window is unstartable while the refund is plainly there. Fixed in `scenarios.py` (PR #31), the integrator-owned origin of the premise, rather than in the frozen file.
What now prevents it  Caught by the second review, one round before the freeze, which is the review that exists for exactly this. The general rule: a scenario description that asserts a value is absent must name the field that would hold it, and that field must be optional.
Time lost             ~20 minutes, against an ADR-0003 amendment published beside the independence metric if it had been found after the freeze.

### 2026-09-05 · Wave 1 · integrator · I rewrote the same scenario three times, and only the third asked the lane that builds it
What broke            `C5_WINDOW_DATE_MISSING` was described three ways in one day. The original ("the window's start date cannot be read from any line") was unbuildable, because `SettlementLine.posted_date` is a mandatory `date`. My replacement (PR #31, "the return delivery scan appears in no file") was written from a reviewer's framing and turned out to describe an event no export carries at all, so it was equally unseedable. Lane B, which actually writes the files, supplied the shape that works: a settlement refund row whose `posted-date` **field** is blank, which lane D quarantines, leaving the refund evidenced only by `Order.refund_initiated_by` and undated.
Root cause            Both wrong versions were written from the type system and from a reviewer's prose, without asking the one lane that knows what a generated export can carry. The absence was always realisable — one level below the parsed types, in the raw row — and neither I nor the reviewer looked there.
How we got out        Asked lane B a question instead of handing it a spec, and told it explicitly to say so plainly if no faithful marker existed rather than invent one. It answered with a shape that needs no new field. PR #34 took the wording from that answer; lane F realigned four rationales to it before the freeze.
What now prevents it  A scenario description that asserts a value is absent must name the field that would hold it, at the level the absence actually lives — raw row or parsed type. And the lane that produces the artefact gets asked before the description is written, not after it is reviewed.
Time lost             ~45 minutes and three PRs. Cheap against the alternative: the labels were frozen the same afternoon, and a wrong premise inside them costs an ADR-0003 amendment published beside the independence metric.

### 2026-09-05 · Wave 1 · lane F · An approved edit became false when the ground under it moved
What broke            Lane F had shipped an approved one-clause fix to `window_tie_break` justifying the length/start split with "…the scan would never enter the arithmetic". When the seeded shape changed hours later (above), that justification became false: what is missing in the new shape is the refund's own date, so a refund-date-only start rule leaves the scenario perfectly reachable.
Root cause            An approval was given for a specific text against a specific premise, and the premise was retracted without the approval being revisited. Nothing in the process ties one to the other.
How we got out        The lane noticed it itself, on the last commit before the freeze, because it re-derived the tie-break's argument against the new shape instead of treating "keep the edit as approved" as "keep the text verbatim". It replaced the justification with one resting on a fact about the exports ("no report the pipeline reads carries a scan") rather than about any one scenario, and committed on top rather than amending, so the log shows the correction as a correction.
What now prevents it  A justification in a frozen record should rest on a property of the data, not on the shape of one scenario. And an instruction that says "as approved" means the substance, not the bytes — worth stating in briefs, since the lane got this right by judgement rather than by rule.
Time lost             none. Caught before the digest was taken.
