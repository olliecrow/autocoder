# Decision Capture Policy

This document defines how to record fixes and important decisions so future work does not re-litigate the same questions. It is written to stay accurate over time; avoid time-specific language.

Contract boundary:
- `docs/spec.md` is the canonical behavior contract.
- `docs/decisions.md` captures durable rationale and trade-offs behind that behavior.

## When to record
- Record non-obvious, cross-cutting decisions that future work could reasonably reopen.
- Prefer clear code and focused tests for local bug fixes, behavior, and invariants.
- Do not record routine implementation choices or duplicate facts already canonical elsewhere.

## Where to record
Use the smallest, most local place that makes the decision obvious:
- Code comments near the behavior when the rationale is not obvious.
- Tests with names/assertions that encode the invariant.
- Docs (this file or another focused doc) when the decision is cross-cutting.

Prefer updating an existing note over creating a new file.

## What to record
Keep entries short and focused:
- Decision: what was chosen.
- Context: what problem or risk it addresses.
- Rationale: why this choice was made.
- Trade-offs: what we are not doing.
- Enforcement: which tests or code paths lock it in.
- References (optional): file paths, tests, or PRs that embody the decision.

## Template
```
Decision:
Context:
Rationale:
Trade-offs:
Enforcement:
References:
```

## Recorded decisions

Decision:
Maintain public-project documentation and security hygiene at all times.
Context:
The repository is public. Committed docs, notes, comments, examples, automation, and history are externally visible.
Rationale:
Treating the whole repository as a public surface reduces disclosure risk and keeps contributions suitable for external readers.
Trade-offs:
Requires extra care to sanitize examples and avoid convenience shortcuts that include sensitive internal details.
Enforcement:
README/AGENTS/workflow/spec documents require public-project hygiene; runtime/docs guidance keeps credentials local and forbids printing secrets in issue/PR comments or logs.
References:
`README.md`, `AGENTS.md`, `docs/workflows.md`, `docs/spec.md`

Decision:
Support multiple opted-in issues in a single repo session, processed sequentially (one codex run per issue worktree at a time).
Context:
Humans may label multiple issues `autocoder` simultaneously; each issue must remain isolated (worktree/branch/PR) and codex runs are fresh/stateless.
Rationale:
Keeps a single long-running terminal session per repo while still making progress across multiple issues, without cross-issue context leakage or parallel worktree contention.
Trade-offs:
Work is still single-threaded; a long codex run for one issue delays others.
Enforcement:
The poller owns multiple issues but iterates them sequentially in the poll loop.
References:
`src/autocoder/state.py`, `src/autocoder/run.py`, `docs/spec.md`

Decision:
Keep the trust boundary strict, but source the allowlisted GitHub logins from config and deny by default until they are explicitly configured.
Context:
Hard-coding an operator-specific GitHub username in source breaks the project's reusable/open-source-ready posture and makes the trust boundary harder to adapt per installation.
Rationale:
`allowed_github_logins` in global/per-repo config preserves the same strict trust model while keeping operator identity out of source. Deny-by-default is the safest fallback when config is missing.
Trade-offs:
Requires a minimal config step before autocoder will claim any issue. Misconfiguration can leave autocoder idle until corrected.
Enforcement:
Runtime loads `allowed_github_logins` from config, logs the effective set, and passes it into security checks, trusted digests, prompt metadata, mentions filtering, issue claiming, and PR mutation safety.
References:
`src/autocoder/config.py`, `src/autocoder/security.py`, `src/autocoder/run.py`, `tests/test_config.py`, `docs/spec.md`

Decision:
For allowlisted-author issues, include the trusted initial issue-body snapshot plus issue-author comments/reviews, and ignore all other users' thread content.
Context:
The operator wants maximum prompt-injection resistance: if another user comments on their issue, that content must not enter codex context.
Rationale:
Single-author context gives a strong prompt-injection boundary. Capturing the initial issue body once preserves the common GitHub pattern where the issue body contains the primary spec, without turning later mutable body edits into a live instruction channel.
Trade-offs:
Collaboration comments from other users are intentionally ignored by codex and may require the issue author to restate relevant points. Later issue-body edits, PR body text, and edits to existing comments/reviews are ignored for instruction triggering, so updates must be posted as new issue-author comments/reviews.
Enforcement:
Issue state persists the trusted initial issue body, trusted issue digests include that snapshot plus issue-author comment IDs, codex prompt context-fetch filters are pinned to issue-author login only, and runtime attachment extraction is limited to issue-author comments/reviews with a local manifest under `.autocoder/artifacts/attachments-manifest.json`.
References:
`src/autocoder/security.py`, `src/autocoder/run.py`, `src/autocoder/state.py`, `tests/test_security.py`, `tests/test_run_prompt.py`, `tests/test_run_recovery.py`, `docs/spec.md`

Decision:
Only trigger default-branch merge-sync when the issue branch ref can be resolved (local branch or `origin/<branch>`), to avoid false "default branch advanced" triggers for not-yet-created branches.
Context:
Newly claimed issues may have a branch name assigned before the local branch exists; naive ancestry checks would treat missing refs as "behind".
Rationale:
Reduces confusing trigger reasons and avoids unnecessary codex runs for brand-new branches.
Trade-offs:
Requires an extra ref-existence check before ancestry evaluation.
Enforcement:
Default-sync trigger uses a resolved descendant ref (local or remote) before calling `git merge-base --is-ancestor`.
References:
`src/autocoder/run.py`

Decision:
Do not adopt or mutate PRs unless they are same-repo, authored by an allowlisted login, and authored by the same login as the issue author.
Context:
Non-allowlisted users must not be able to influence autocoder behavior. Adopting their PRs/branches would effectively make their changes an input channel.
Rationale:
Maintains a strict trust boundary: issue-owner-only execution context and mutation rights. Avoids confusing states where autocoder "adopts" a PR but cannot safely push to it.
Trade-offs:
If a non-allowlisted PR already exists, autocoder will ask the allowlisted human to close it or otherwise clarify desired behavior before proceeding.
Enforcement:
PR adoption paths in the poller reject cross-repository PRs, PRs authored by non-allowlisted logins, and PRs whose author does not match the issue author. The only exception is autocoder's own PR: authored by the authenticated `gh` login on the claimed `autocoder/issue-<n>-*` branch. Without it, autocoder rejected its own PR when a different allowlisted login opened the issue. Push safety uses the same guard. Trusted instructions still come only from the issue author.
References:
`src/autocoder/run.py`, `docs/spec.md`

Decision:
Bound Codex CLI runtime with a timeout; on Codex invocation failure (including timeout), post a clear issue update and label `autocoder:needs-info`.
Context:
`codex exec` is an external subprocess. A hang or long-running call should not stall the entire single-process repo session indefinitely.
Rationale:
A bounded timeout keeps the polling loop responsive and makes failures visible to the human via GitHub (the primary interface).
Trade-offs:
Very large changes may require multiple runs or a longer timeout value. Timeouts can surface as transient failures; humans may need to retrigger after fixing local auth/tooling.
Enforcement:
Codex runs are executed via the shared runner with a wall-clock timeout (default 36000s / 10h; override with `AUTOCODER_CODEX_TIMEOUT_S`). The runtime catches Codex invocation errors and posts an `[autocoder]` issue comment with retrigger instructions and applies `autocoder:needs-info` best-effort.
References:
`src/autocoder/_runner.py`, `src/autocoder/codex.py`, `src/autocoder/run.py`, `docs/spec.md`

Decision:
Make one merge-sync attempt per default-branch SHA. If the issue branch is still behind after the run, post one notice and wait for new issue-author input or a newer default-branch SHA.
Context:
An earlier rule kept the cursor back until the merge landed. When a merge could not land (sandboxed Codex cannot write Git metadata, or a conflict stayed unresolved), every 60-second poll started another full Codex run.
Rationale:
A bounded attempt plus a visible notice keeps humans in charge of hard conflicts without unbounded worker runs.
Trade-offs:
A conflict that Codex does not resolve waits for a human (fix the branch, or reply `retrigger`).
Enforcement:
After every run, autocoder sets `last_seen_default_branch_sha` to the fetched SHA and checks ancestry (`origin/<default-branch>` is an ancestor of the issue branch); if not, it posts a `default-sync:<sha>` notice once.
References:
`src/autocoder/run.py`

Decision:
Treat GitHub comments starting with `[autocoder]` as bot/status output only (never human instructions), even though they are authored by the locally authenticated GitHub login.
Context:
Autocoder interacts with GitHub as the local `gh` user. This means autocoder's own comments can appear authored by an allowlisted login, so Codex must distinguish bot output from human instructions by content prefix, not author login alone. Also, autocoder may post a newer status comment after a human instruction comment; Codex must not ignore earlier instructions just because a newer `[autocoder]` comment exists.
Rationale:
Prevents self-generated status updates from becoming an instruction channel and avoids "burying" real instructions behind newer bot/status comments.
Trade-offs:
Humans must not prefix instruction comments with `[autocoder]`; those comments will be ignored as instruction sources.
Enforcement:
Codex prompt explicitly instructs skipping `[autocoder]` comments when extracting requirements, and tests assert the prompt includes this rule.
References:
`src/autocoder/run.py`, `tests/test_run_prompt.py`, `docs/spec.md`

Decision:
When autocoder stops work on an issue (opt-out or disallowed), remove lock labels (`autocoder:claimed`, `autocoder:needs-info`) best-effort and clean up local state.
Context:
Issues can end up looking "stuck" (claimed/needs-info) even after the operator opted out by removing the `autocoder` label, or if the issue becomes disallowed by allowlist rules.
Rationale:
Keeps GitHub state aligned with reality: no active worker means no lock labels. Reduces human confusion and reduces accidental coordination issues.
Trade-offs:
Label removals still update the issue metadata, but autocoder does not treat label changes as instructions and will not spam codex runs due to label churn.
Enforcement:
The poll loop removes lock labels before dropping local ownership for opt-out/disallowed issues.
References:
`src/autocoder/run.py`, `docs/spec.md`

Decision:
Trigger codex recovery when an owned issue worktree has unfinished local state (dirty files or in-progress git operation), even if GitHub metadata did not change.
Context:
Prior codex runs can fail mid-edit/merge, leaving local worktree state that would otherwise be ignored until a new GitHub event arrives.
Rationale:
Makes restarts self-healing and keeps progress moving without requiring manual retrigger comments for local-only interruption cases.
Trade-offs:
Local changes left by a completed run (for example after `needs_info`) wait for new issue-author input; otherwise each poll would start the same run again.
Enforcement:
Each poll inspects owned issue worktrees for dirty/in-progress git state and adds a `local_recovery_needed` trigger reason for codex invocation, unless a completed run left that state (`local_changes_after_run`). A clean worktree clears the flag.
References:
`src/autocoder/run.py`, `src/autocoder/git.py`, `tests/test_run_recovery.py`, `docs/spec.md`

Decision:
autocoder runs every Git write (fetch, merge, commit, push) outside the Codex sandbox. Codex resolves conflicted file contents and verifies.
Context:
The default `workspace-write` sandbox has no network and keeps Git metadata read-only, so Codex cannot fetch, merge, commit, or push there.
Rationale:
One owner for Git writes works the same in both sandbox modes, and keeps the push guard in front of every push.
Trade-offs:
Codex cannot make several checkpoint commits in one run; autocoder makes one commit per `ready` run.
Enforcement:
Before each run, autocoder merges `origin/<default-branch>` into a clean worktree (`git merge --no-edit`; conflicts and `MERGE_HEAD` stay for Codex). The prompt forbids Git writes. After `ready`, `git add -A` and `git commit` complete any merge, then autocoder pushes.
References:
`src/autocoder/run.py`, `tests/test_run_prompt.py`, `docs/spec.md`

Decision:
Post an immediate lightweight acknowledgment on issue-author updates before starting a codex run.
Context:
Humans need quick confirmation that autocoder noticed their new instruction/comment; waiting for the full codex run can feel silent even when work started.
Rationale:
An immediate `[autocoder]` comment with `:eyes:` provides fast feedback while preserving issue-thread visibility and without waiting for codex completion.
Trade-offs:
Adds one extra issue comment per actionable issue-author update; to avoid noise, this is skipped for initial claim/bootstrap and for non-human-triggered runs (for example local recovery/default sync only).
Enforcement:
When issue-author activity digest changes and the issue has already been processed at least once, runtime posts an acknowledgment comment before invoking codex.
References:
`src/autocoder/run.py`, `tests/test_run_recovery.py`, `docs/spec.md`

Decision:
Runtime generates a trusted thread-context artifact and codex must use it as the only issue/PR thread instruction source.
Context:
Prompt-only instructions to self-filter `gh` issue/PR thread reads are not a sufficient prompt-injection boundary when codex has broad shell access. We need runtime-enforced filtering before instruction content reaches codex.
Rationale:
Shifts security filtering from model behavior to runtime behavior: autocoder writes `.autocoder/artifacts/trusted-thread-context.json` containing only issue-author, non-`[autocoder]` issue comments, PR comments, and PR reviews. Codex prompt then requires reading that artifact and explicitly forbids direct raw thread-body reads via `gh`.
Trade-offs:
Not a full sandbox boundary because codex still has general command execution ability; however, this materially reduces accidental ingestion of untrusted GitHub thread content and provides deterministic filtered context for every run.
Enforcement:
`_prepare_trusted_thread_context` builds and writes trusted context before each codex execution, prompt constraints require consuming that artifact, and tests assert both prompt requirements and filtering behavior.
References:
`src/autocoder/run.py`, `tests/test_run_prompt.py`, `tests/test_run_pr_flow.py`, `docs/spec.md`

Decision:
If trusted issue-author activity arrives while codex is running, keep issue/PR cursors behind and run codex again on the next poll.
Context:
Autocoder computes trusted digests before invoking codex. Without a post-run digest check, a new issue-author comment/review arriving mid-run can advance `last_seen_*_updated_at` past unprocessed trusted input, causing the next poll to idle.
Rationale:
Cursor advancement must represent "processed trusted input", not just "latest metadata timestamp". By comparing pre-run and post-run trusted digests, runtime can detect mid-run trusted updates and force a deterministic follow-up run.
Trade-offs:
Can produce an extra codex run when issue-author updates arrive during a long run; this is intentional and bounded by actual trusted-input changes.
Enforcement:
After codex returns, runtime refreshes issue/PR trusted digests. If a digest differs from the pre-run digest, it logs follow-up scheduling and does not advance that cursor. A regression test covers issue-comment mid-run arrival behavior.
References:
`src/autocoder/run.py`, `tests/test_run_recovery.py`, `docs/spec.md`

Decision:
Treat merge-sync from latest default branch into issue/PR branches as a high-risk operation that requires extra care and explicit verification.
Context:
Autocoder continuously integrates `origin/<default-branch>` into long-running issue branches. Merge mistakes can silently break either issue changes or expectations inherited from mainline code.
Rationale:
Merge-sync is required for freshness, but correctness is more important than speed. A conservative merge posture with conflict scrutiny and post-merge verification reduces regression risk for both branch-specific behavior and baseline behavior from default branch.
Trade-offs:
Adds extra verification time during merge-sync runs and may delay pushes when confidence is low; this is intentional to protect branch and mainline stability.
Enforcement:
Spec requires conservative merge handling, careful conflict resolution, and relevant post-merge checks before pushing merge results.
References:
`docs/spec.md`, `src/autocoder/run.py`

Decision:
Expose explicit `doctor` and `dry-run` helper commands for setup validation and execution preview.
Context:
Operators need a fast way to validate auth and tooling, and to preview the run order before starting long polling sessions.
Rationale:
Dedicated non-mutating helpers reduce onboarding friction and make failures easier to diagnose without starting the main loop.
Trade-offs:
Slightly larger CLI surface area to maintain and document.
Enforcement:
CLI command parser includes `doctor` and `dry-run`; preflight checks run with pass/fail output; dry-run prints deterministic stage order and confirms no mutation.
References:
`src/autocoder/cli.py`, `src/autocoder/preflight.py`, `tests/test_cli.py`, `tests/test_preflight.py`, `docs/spec.md`

Decision:
Ship a first-class completion command and richer CLI help examples.
Context:
Operators rely on command-line usage for setup and troubleshooting; missing completion and thin help text slow onboarding.
Rationale:
`autocoder completion [bash|zsh]` plus explicit examples in `--help` makes common command flows easier to discover and reduces typing errors.
Trade-offs:
Adds a small maintenance surface for static shell completion templates.
Enforcement:
CLI includes `completion` subcommand, root help includes install examples, and tests cover completion output plus help text references.
References:
`src/autocoder/cli.py`, `tests/test_cli.py`, `README.md`

Decision:
Use only official, reputable, and well-supported third-party dependencies and services by default.
Context:
Public dependencies and integrations create supply-chain, maintenance, license, and trust risk.
Rationale:
Authoritative publishers, active maintenance, established adoption, and compatible licenses reduce those risks and keep the project maintainable.
Trade-offs:
Niche or experimental options are skipped unless their trust signals improve or a concrete need justifies explicit review.
Enforcement:
`AGENTS.md` requires dependency trust checks before adoption or upgrades. Project dependencies remain pinned in `pyproject.toml` and `uv.lock`.
References:
`AGENTS.md`, `pyproject.toml`, `uv.lock`

Decision: Plain English and clear naming are the default for this repository.
Context:
The owner wants this repository to stay easy to understand in future chat sessions, docs work, code review, and day-to-day code changes.
Rationale:
Plain English cuts down confusion and makes work faster to read. Clear names in code reduce guessing and make the code easier to change safely later.
Trade-offs:
Some technical ideas need a short extra explanation, and some older names may stay in place until the code around them is touched safely.
Enforcement:
`AGENTS.md` requires plain English in chat and written project material. When touching code, prefer clear descriptive names for files, folders, flags, config keys, functions, classes, types, variables, tests, and examples, and rename confusing names when the change is safe and worth it.
References:
`AGENTS.md`

## Private state and setup validation

Create the autocoder home directory with mode `0700` and the instance ID with `0600`; tighten existing modes. Reject invalid repo URLs, config, timeout, state, and empty allowlists before locking or external actions. Return status 2 with a short error. Read the timeout when the client starts, so help works with an invalid timeout.

## PR trust, retries, and branch safety

Ignore fork and non-allowlisted PRs without GitHub comments. Filter candidates before counting them. Search issue references once per ownership state; check exact issue numbers and the issue author. Report trusted conflicts and closed PRs once per situation.

Never adopt the branch currently checked out by Codex. Before committing or pushing, require the expected issue branch (or a trusted PR head), never the default branch. Push `HEAD:refs/heads/<expected-branch>`.

Consume input before post-run actions and cursor refresh. An interrupt (Ctrl-C or SIGTERM) during a run restores the input cursors, so a restart handles the same input. If these actions fail, keep a failure flag and require new issue-author input (`retrigger`) before another run, even with dirty files or pending base sync. Report the failure once per run (polls without new input stay quiet) and add needs-info on a best-effort basis.

## Attachment URL boundary

Fetch only GitHub attachment paths and image hosts. Raw content must belong to the target repo. Allow the GitHub user-asset S3 host only as a redirect target. Strip credentials across hosts; send tokens only to the initial repo host or same-repo raw content. Never fetch issue, PR, or documentation HTML links. Record skipped URLs and reasons in the attachment manifest. Private attachment authentication is unverified; commit inaccessible files to the issue branch instead.

## Redact outgoing text

Redact known token and private-key formats in every GitHub title, body, and comment. Also redact exact values of at least eight characters from secret-named environment variables and all assignments in the managed clone `.env`. Apply the same filter to generated commit messages. Redaction is defense in depth; never give the worker unrelated credentials.

Scan outgoing added lines before each push and block likely secrets. Committed files were not checked before, and Codex can read every file the host user can read. The scan skips merged-in default-branch history so upstream test fixtures do not block a push. It is defense in depth; a dedicated OS user is the main control.

## Execution isolation default

Default to `codex_sandbox = "workspace-write"`. Keep unrestricted execution as an explicit `danger-full-access` opt-in for isolated workers. This changes earlier behavior: sandboxed tasks can fail when they need network or external filesystem access. autocoder performs its own commit and push outside the sandbox. Use a single-repo fine-grained GitHub token, a repo deploy key, and default-branch protection. Trust repo writers and allowlisted issue authors at code-execution level. No live Codex run was used to validate sandbox-dependent task capabilities.

## Bounded worker output and process lifetime

Stream worker output to `.autocoder/plan/codex-run.log` with mode `0600`, replacing the previous log. Never send the log to GitHub. Run the worker and every `git`/`gh` command in a new session (own process group, no controlling terminal; stdin is empty unless autocoder sends input, so commands cannot prompt). On timeout or interruption, send SIGTERM to the group so git can remove its lock files, wait (10 s for the worker, 5 s otherwise), then SIGKILL what remains. This bounds output memory and prevents abandoned commands and stale locks after a cancelled run. A lock left after the SIGKILL fallback is not removed automatically.

## Claims converge before execution

Post the claim comment before adding the claimed label, so a failed comment cannot leave a labelled orphan. Read claims back after claiming and before worker execution. If another instance owns the latest valid allowlisted claim, stop local work without changing shared labels or PRs. Accept only issue-specific autocoder branch names from claim comments.

## Local lock and bootstrap

Use a kernel file lock for the session lifetime. Keep the lock file after release; its content is diagnostic only. A stale PID never blocks startup. Discover the fallback default branch from the local `origin/HEAD` symbolic ref. Create missing labels only; preserve existing colors and descriptions.

## Doctor setup checks

Doctor fails on invalid or empty trust config, disabled issues, insufficient repo permission, or missing Git identity. It warns on classic broad token scopes without printing tokens or identity values. Warnings do not change the exit status. All checks are read-only.

## State schema

Only the multi-issue `issues` state schema is supported. Reject legacy single-issue files with a clear setup error; remove the old state file to start fresh. Validate retry and PR-search flags as booleans. Aggregate trusted PR author conflicts into one notice per candidate set.

PR discovery skips head lookups when the remote branch does not exist. PR summaries include trust fields, so untrusted candidates need no detail request. The issue-reference search runs once per ownership state.
