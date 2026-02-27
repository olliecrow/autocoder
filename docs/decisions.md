# Decision Capture Policy

This document defines how to record fixes and important decisions so future work does not re-litigate the same questions. It is written to stay accurate over time; avoid time-specific language.

## When to record
- Any fix for a confirmed bug, regression, or safety issue.
- Any deliberate behavior choice that differs from intuitive defaults.
- Any trade-off decision that affects modeling or behavior.
- Any change that affects external behavior, invariants, or public APIs.

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
Operate with an open-source-ready documentation and security posture even while the repository is private.
Context:
The project is transitioning toward open source. Current private visibility does not remove long-term risk of accidental leakage through committed docs, notes, comments, or examples.
Rationale:
Treating all written artifacts as potentially public reduces future cleanup risk and avoids retroactive secret scrubbing when visibility changes.
Trade-offs:
Requires extra care to sanitize examples and avoid convenience shortcuts that include sensitive internal details.
Enforcement:
README/AGENTS/workflow/spec documents require open-source-ready hygiene; runtime/docs guidance keeps credentials local and forbids printing secrets in issue/PR comments or logs.
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
For allowlisted-author issues, include issue-author comments/reviews only (ignore issue/PR bodies) and ignore all other users' thread content.
Context:
The operator wants maximum prompt-injection resistance: if another user comments on their issue, that content must not enter codex context.
Rationale:
Single-author, comment/review-only context gives a stronger prompt-injection boundary and avoids relying on body/edit provenance.
Trade-offs:
Collaboration comments from other users are intentionally ignored by codex and may require the issue author to restate relevant points. Issue/PR body text and edits to existing comments/reviews are ignored for instruction triggering, so updates must be posted as new issue-author comments/reviews.
Enforcement:
Issue/PR activity digests include only issue-author activity when `issue_author` is provided and are keyed to stable comment/review IDs (not edits), codex prompt context-fetch filters are pinned to issue-author login only, and runtime attachment extraction is limited to issue-author comments/reviews with a local manifest under `.autocoder/artifacts/attachments-manifest.json`.
References:
`src/autocoder/security.py`, `src/autocoder/run.py`, `tests/test_security.py`, `tests/test_run_prompt.py`, `docs/spec.md`

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
PR adoption paths in the poller reject cross-repository PRs, PRs authored by non-allowlisted logins, and PRs whose author does not match the issue author. Push safety uses the same guard.
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
Do not mark the default-branch SHA as "seen" for an issue after a merge-sync-triggered Codex run unless the issue branch actually contains `origin/<default-branch>`.
Context:
If a default-branch sync run fails to merge (conflicts, errors, or no push), updating the cursor would incorrectly suppress further merge-sync attempts.
Rationale:
Ensures merge-sync remains self-healing: the `default_branch_advanced` trigger keeps firing until the issue branch is genuinely up to date.
Trade-offs:
May cause repeated merge-sync attempts on persistent conflicts until a human resolves the conflict or opts out.
Enforcement:
After a Codex run triggered by `default_branch_advanced`, autocoder checks ancestry (`origin/<default-branch>` is ancestor of issue branch) before advancing `last_seen_default_branch_sha`.
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
Can cause repeated recovery attempts on persistent local conflicts until codex resolves them or asks for human input.
Enforcement:
Each poll inspects owned issue worktrees for dirty/in-progress git state and adds a `local_recovery_needed` trigger reason for codex invocation.
References:
`src/autocoder/run.py`, `src/autocoder/git.py`, `tests/test_run_recovery.py`, `docs/spec.md`

Decision:
Codex owns issue-branch merge execution; autocoder runtime only detects/schedules merge-sync work.
Context:
Merge behavior must stay adaptable to per-repo workflows and conflict handling, while still enforcing regular sync with the default branch.
Rationale:
Keeping merge execution in codex avoids brittle fixed-command runtime behavior and lets codex resolve merge conflicts with full repository context.
Trade-offs:
Relies on prompt/runtime contracts and codex behavior quality; poor codex runs may require retrigger or human clarification.
Enforcement:
Runtime triggers codex when default branch advances or local recovery is needed, and prompt policy requires codex to perform merge-sync and recovery first.
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
