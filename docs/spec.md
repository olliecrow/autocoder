# autocoder spec

This document captures the current intended behavior of autocoder (the tool) at a product/spec level. It is expected to evolve; keep it evergreen and consistent with actual behavior.

## Current decisions
- **opt-in label starts work**: a human applies a label to an issue to make it eligible; no extra approval gate beyond that label.
- **gh CLI only**: all GitHub interactions are done via `gh` (no bespoke direct API client).
- **local user identity**: GitHub actions (comments/labels/PRs) and git commits are performed as the locally authenticated user (whatever `gh` and local git config are set to).
- **allowlisted human (security)**: autocoder accepts instructions from a small, hard-coded allowlist of GitHub logins (for this repo, `olliecrow`). It only claims issues authored by allowlisted users. For those issues, codex context is restricted to content authored by that same issue author: issue-author comments/reviews only. All other users' content (even if allowlisted) is ignored for codex input to reduce prompt-injection risk. Runtime must prepare a trusted local thread-context artifact containing only this filtered content, and codex must use that artifact as its instruction source instead of reading raw issue/PR comment bodies from live `gh` output. Issue/PR body text is not a trusted instruction channel. Operationally, instruction updates must be posted as new issue-author comments/reviews; edits to existing comments/reviews are intentionally ignored as triggers. If an owned issue becomes disallowed (for example the issue author changes to a non-allowlisted login), autocoder stops work, removes lock labels best-effort, and cleans up local state. PR title/body edits are not treated as instruction updates; use issue-author PR comments/reviews for PR-side instruction updates. Even structured metadata (for example claim comments) must be ignored unless authored by an allowlisted login. Bot-authored comments are identified by the `[autocoder]` prefix and do not trigger new codex runs. Codex must also treat `[autocoder]` comments as status output (not instructions) and must scan earlier non-`[autocoder]` issue-author comments for actionable requirements and acceptance criteria.
- **comment prefix**: every automated GitHub comment starts with `[autocoder]` on its own line, then a blank line, then the message.
- **locking**: when autocoder takes an issue, it applies a lock/claim label and posts a claim comment (human-readable; may include machine-readable metadata).
- **claim label is not a stop signal**: removing `autocoder:claimed` alone does not stop work; autocoder may re-add it best-effort while the issue remains opted-in. to stop work, remove the `autocoder` label.
- **workspace isolation**: autocoder maintains its own repo checkout under `~/autocoder/` and uses **`git worktree` per issue** (one worktree/branch/PR per issue).
- **no pushing to base branch**: autocoder never pushes directly to the base branch (for example `main`) and never auto-merges PRs. It only pushes to its issue branches and opens/updates PRs.
- **stay up to date**: autocoder should regularly sync with the latest remote base branch and integrate updates into its issue branch (prefer merge over history rewrite).
- **startup sync first**: each run should start by fetching `origin` and checking for interrupted local work in the issue worktree before taking new feature actions.
- **codex-owned merge execution**: runtime may detect/trigger merge-sync work, but codex is responsible for performing and resolving branch merges.
- **extreme merge care**: when integrating latest `origin/<default-branch>` into an issue branch/PR branch, autocoder must act conservatively, verify thoroughly, and avoid regressions on both the issue branch and default-branch expectations.
- **attachments are in scope**: issue/PR attachments (docs/images/files) are part of the request; autocoder must fetch and incorporate them into the work.
- **post-merge cleanup**: after a PR is merged, autocoder should delete its local worktree(s) and delete local/remote issue branches.
- **sequential multi-issue per repo session**: within a single target repo, autocoder may own multiple issues at once, but it processes them sequentially (one codex run per issue worktree at a time) with strict per-issue isolation (branch/worktree/PR and fresh codex context per run).
- **multi-project via multi-process**: multiple repos are supported by running multiple autocoder sessions (for example, separate terminals), one per repo.
- **per-repo session lock**: autocoder creates a local lock file for the target repo while running to prevent accidental concurrent sessions against the same repo (and cleans up stale locks on restart).
- **no local system changes**: autocoder must not intentionally modify system files or global configuration; all actions should be confined to its managed workspace and the target repo.
- **open-source-ready hygiene**: treat project artifacts as future-public even while the repo is private; do not commit secrets or confidential data.
- **no command allow/deny list**: do not introduce an explicit per-command allowlist/denylist system.
- **codex runs headless with pinned runtime profile**: run codex via Codex CLI in non-interactive mode with pinned model/reasoning and yolo execution posture configured by autocoder.
- **stop signal**: autocoder must only act on issues that have the opt-in label `autocoder`; if `autocoder` is removed, autocoder must stop working on that issue.
- **issue close is authoritative**: if a human closes an issue, autocoder should stop and run cleanup (including closing its PR and deleting its branch/worktree).
- **poll interval is fixed**: polling runs every 1 minute (hard-coded default).
- **base branch default**: autocoder targets the repo's default branch and must stay up-to-date with `origin/<default-branch>`.
- **global + per-repo config**: support a global config file with optional per-repo overrides, but keep available options minimal.
- **instance id**: autocoder uses a local-only opaque UUID stored under `~/autocoder/instance_id` for claim comments/log correlation.
- **attachment size cap**: cap downloaded attachments at 200MB per issue (local-only); exceed => skip download and ask the human for an alternative.
- **start command**: autocoder is started with `autocoder run <repo-ssh-url>` (no extra required flags).
- **doctor helper command**: `autocoder doctor <repo-ssh-url>` runs non-mutating preflight checks for local tools, auth state, and remote reachability.
- **dry-run helper command**: `autocoder dry-run <repo-ssh-url>` prints the planned execution order and paths without mutating state.
- **label removal cleanup**: when `autocoder` is removed from an issue, autocoder stops and cleans up local state (delete local worktree/branch/artifacts). It should also remove lock labels (`autocoder:claimed`, `autocoder:needs-info`) best-effort. It must not close PRs, close issues, or delete remote branches.

## Definitions
- **autocoder**: the local automation/orchestrator being built in this repo.
- **codex**: OpenAI Codex, used as the coding agent that edits code, runs tests, etc.
- **target repo**: the single GitHub repo + local working copy that a given autocoder instance is allowed to operate on.
- **human**: one or more repo contributors collaborating with autocoder via GitHub Issues and PRs.

## Naming conventions
- The project/tool name is always written as `autocoder` (all lowercase, one word) in docs, labels, branches, and automated comments.
- User text may contain variants or typos (for example `AutoCoder`, `auto-coder`, `autocoder`); autocoder should be tolerant when interpreting human intent, but it should emit the canonical spelling in its own communications.

## Goal
Use GitHub Issues and Pull Requests as the primary interface for human-agent collaboration on a target repo, while codex runs locally to implement changes end-to-end (build/test/commit/PR).

## Non-negotiable properties
- **repo-scoped**: an autocoder instance works on exactly one target repo; it must not modify or operate on other repos on disk.
- **issue-driven**: work starts from GitHub Issues (or explicit PR events tied back to an issue).
- **single work item mapping**: one issue -> one working branch -> one PR.
- **explicit locking**: when an issue is being handled, it enters a lock/claimed state to avoid multiple agents colliding.
- **async-friendly**: autocoder can pause/wait for human responses, CI, or reviews; it should be able to recover after laptop sleep/restart by re-scanning GitHub state.

## High-level workflow
1. **detect**: discover candidate issues/PR events that require action.
2. **claim/lock**: atomically (best-effort) mark an issue as claimed so other agents back off.
3. **spec phase**:
   - read the issue, relevant code, prior issues/PRs, and tests.
   - ask clarifying questions via issue comments (tag/mention the human when input is needed).
   - continue until requirements are sufficiently clear to proceed end-to-end.
4. **implementation phase**:
   - ensure there is exactly one working branch for the issue (create one if needed; otherwise resume the existing one).
   - run codex locally to implement the change end-to-end, including verification (tests/checks).
   - keep the issue updated with explicit progress.
5. **PR phase**:
   - ensure there is exactly one PR associated with the issue (open one if needed; otherwise resume the existing one).
   - monitor/respond to CI failures and review comments; iterate until merge-ready.
6. **complete/unlock**:
   - once merged (or explicitly closed), post a final summary.
   - ensure the issue is closed (prefer automatic closure by including `Fixes #<n>` in the PR body).
   - remove/clear lock state and any “in progress” labels.

## Issue selection and locking
Desired behavior:
- issues autocoder may act on should be explicitly opt-in (via label).
- when an issue is claimed, it should be visibly “owned” by a specific autocoder instance to prevent collisions.

Lock representation options:
- a lock/claim label (recommended)
- a structured claim comment (recommended; include who/where claimed it)

Collision handling:
- if autocoder observes an issue already claimed, it must not proceed.
- if a claim race occurs, autocoder should detect it and back off.

Issue selection:
- within a repo session, multiple issues may be claimed/owned concurrently, but they are processed sequentially.
- when multiple open issues have label `autocoder` and are not `autocoder:claimed`, claim them deterministically (default: lowest issue number first). each issue gets its own worktree/branch/PR.
- when multiple owned issues have actionable triggers in the same poll, run codex sequentially for each issue (fresh context each run).

Existing issues:
- issues may have substantial prior human discussion before `autocoder` is applied.
- on claim, autocoder must read existing context from the issue author only (issue-author comments/reviews and issue-author attachments) and then proceed as normal.

### Labels
Minimal label set:
- `autocoder`: opt-in / queued by a human.
- `autocoder:claimed`: issue is actively owned by an autocoder instance.

Optional status labels:
- `autocoder:needs-info`: autocoder is waiting on human clarification.
- `autocoder:blocked`: autocoder is blocked on an external dependency (CI outage, cluster queue, etc).

Bootstrap behavior:
- on first run for a repo, autocoder creates missing labels (name, color, description) via `gh` if the authenticated user has permission.

### Claim comment
Requirements:
- posted immediately after successfully claiming an issue.
- must be human-readable.
- must not include sensitive local machine details (avoid hostnames and absolute local paths).

Suggested minimal content:
- reference to the issue branch name (for example `autocoder/issue-123-short-slug`)
- an opaque instance id (random UUID stored locally) to disambiguate concurrent sessions
- current state (`claimed`, `needs-info`, etc)

Suggested format:
```
[autocoder]

claimed by autocoder (instance: <opaque-id>).
branch: <branch-name>
next: reading context and asking any clarification questions (if needed).
```

## State machine
Represented on GitHub via labels (names TBD) and/or structured comments.

Core states:
- `queued`: eligible for autocoder to pick up.
- `claimed`: locked to a specific autocoder instance; no other agent should work it.
- `needs-info`: waiting for human clarification.
- `ready`: spec is sufficiently clear; implementation can start.
- `in-progress`: actively implementing in local workspace.
- `pr-open`: PR exists; work continues via PR review/CI loop.
- `blocked`: waiting on an external blocker (human input, CI infra, etc).
- `done`: merged/closed and summarized.

## Triggers and catch-up
Autocoder should support a polling-based baseline:
- poll GitHub every N minutes for new events (issues/PRs/comments/CI signals as needed).
- on startup (or wake), perform a catch-up scan so missed events during sleep are processed.

Optional future enhancement:
- GitHub webhooks (requires a publicly reachable endpoint or tunnel); still keep polling as a fallback.

### Polling
Default:
- poll interval: 1 minute.

Token-awareness requirement:
- the polling loop must not require starting a codex session unless there is actionable work.
- use `gh`-based metadata checks (labels, updated timestamps, new comments) to decide whether to invoke codex.

## Config
Autocoder should keep configuration simple.

Layering:
- global defaults: `~/autocoder/config.toml`
- per-repo overrides: `~/autocoder/repos/<owner>/<repo>/config.toml`

Prefer hard-coded defaults where possible; only introduce config when it removes real friction (for example: who to @mention when input is needed).

## Git defaults
- base branch: repo default branch
- remote base ref: `origin/<default-branch>` (fetch regularly)
- branch naming: `autocoder/issue-<n>-<slug>`
- PR title: `issue #<n>: <issue title>`

## Issue-branch-PR mapping
Invariant:
- one issue -> one branch -> one PR.

If an issue already has an open PR at the moment it is labeled `autocoder`, autocoder should resume that PR rather than creating a second one (when it is safe to adopt: same-repo PR, allowlisted PR author, and `pr.author == issue.author`).
Adoption discovery should prioritize GitHub's linked-closing relationship (`closingIssuesReferences`) so autocoder can resume valid existing PRs even when branch names differ or PR body text does not use an exact `Fixes #<n>` phrase.

Branch ownership and safety:
- prefer branches matching `autocoder/issue-<n>-*`.
- autocoder must not push to branches that it cannot verify are safe to mutate (for example, a PR from a fork).
- autocoder only pushes to PR branches when the PR is not cross-repository, the PR author is allowlisted, and `pr.author == issue.author`; otherwise it should skip pushing and ask for clarification.
- autocoder must not adopt or mutate PRs authored by non-allowlisted logins or by an author different from the issue author; it should leave a note on the issue and proceed with an autocoder-owned branch/PR.
- if autocoder cannot safely determine a single PR/branch to use (for example, multiple open PRs), it should ask a single clear question in the issue and stop until answered.

Resuming after stop:
- if an issue is re-labeled after a prior stop, autocoder should attempt to find and resume the existing open PR/branch for that issue.
- if an issue is already `autocoder:claimed`, autocoder should only resume it when the claim comment indicates the same local instance id; otherwise it must back off.

## Default branch discovery
Autocoder should determine the repo default branch using the most reliable source available.

Preferred approach:
- use `gh repo view --json defaultBranchRef` and read `.defaultBranchRef.name`.

Fallback (if `gh` is unavailable/offline):
- use `git remote show origin` and parse `HEAD branch: <name>`.

## Codex integration
Codex is run locally via Codex CLI (not the desktop app) and uses the local user's authentication/subscription.

Invocation principles:
- codex runs non-interactively for discrete steps (for example: spec questions, implementation, PR fixes).
- avoid invoking codex during idle polling; only invoke it when there is new actionable input.
- run codex with explicit execution posture defined by autocoder (non-interactive, pinned model, pinned reasoning, yolo mode).
- pin codex model to `gpt-5.3-codex` with reasoning effort `xhigh` for every autocoder invocation.
- run codex in yolo mode for execution (`--ask-for-approval never` + `--sandbox danger-full-access`).
- bound codex exec time: each codex invocation has a wall-clock timeout (default 36000s / 10h) to prevent a single run from blocking the whole repo session indefinitely. override with `AUTOCODER_CODEX_TIMEOUT_S` (integer seconds; non-positive/invalid values fall back to default).
- treat each codex invocation as fresh/stateless; codex must re-acquire context each run via the prompt's memory/context map (docs, local state/artifacts, and GitHub issue/PR threads).
- include a local Codex skill catalog in each codex prompt and instruct codex to prefer skill-driven workflows whenever relevant.
- assume autocoder is running on the local machine where skills are installed; if skill discovery is temporarily empty, codex should inspect local skill roots (`~/.codex/skills`, `$CODEX_HOME/skills`) and proceed with skill-driven workflows.
- instruct codex to run the `prime` skill at the start of each codex conversation.
- prefer comprehensive prompts that front-load analysis, assumptions, risks, and decision framing instead of minimal prompts.
- prioritize autonomous resolution when confidence is high; interrupt humans only for true blockers or material trade-offs.
- when requesting human input, ask batched, decision-grade questions with clear context, options, and recommendations.
- ensure humans stay in the loop: every codex invocation should produce a clear GitHub status update (issue comment, and PR comment when relevant) so a human can understand what happened and what comes next by reading the thread.
- when issue-author instructions change and autocoder is about to invoke codex, post an immediate lightweight acknowledgment comment (for example `:eyes:`) before the longer codex run completes.
- status updates should be explicit about current state, context (branch/PR), what triggered the run, what was checked/done, and what happens next.
- keep prompt injection minimal: include identifiers/refs (issue number, branch, PR number, trigger reason, skills), and require codex to consume runtime-generated trusted issue/PR thread context instead of raw live thread bodies.
- include a memory/context map in every codex prompt so codex is reminded where durable and ephemeral context lives, and can proactively fetch/read it.
- treat default-branch advancement as a codex trigger: when `origin/<default-branch>` moves ahead of the active issue branch, invoke codex to perform merge-sync work and push updates.
- treat local interrupted work as a codex trigger: if an owned issue worktree is dirty or has an in-progress git operation after restart/failure, invoke codex to recover and continue.
- if new trusted issue-author comments/reviews arrive while codex is running, do not advance issue/PR "last seen" cursors past that newer trusted activity; schedule a follow-up codex run so the new input is processed.
- prefer frequent checkpoint commits/pushes whenever meaningful changes exist; do not create empty commits.
- codex should assume each run may be the last before interruption; preserve durable context in repo docs and preserve code state via commits/pushes before finishing.

Default sandbox posture:
- `codex exec --sandbox danger-full-access --ask-for-approval never`

Notes:
- autocoder itself still uses `gh` and `git` outside the codex sandbox; keep those operations repo-scoped.
- if codex cannot be invoked or errors (including timeout), autocoder must post a clear issue status update (as `[autocoder]`) explaining the failure and how to retrigger; it should best-effort apply `autocoder:needs-info`.

## Long-running and iterative work
Not all issues can be completed in a single codex run. Example: submitting a cluster job and waiting for completion.

Required behavior:
- autocoder may run in a loop: act -> wait -> re-check -> act, until exit criteria are met.
- waiting should be cheap: prefer polling external state (cluster status, CI status, new GitHub comments) without invoking codex unless reasoning/edits are required.
- on restart/catch-up, autocoder must be able to resume long-running work by re-deriving current state from GitHub + local workspace state.

## Workspace model
Autocoder needs a reliable way to operate on the target repo:
- maintain its own managed checkout under `~/autocoder/` (not the human's checkout).
- create per-issue branches and per-issue worktrees (`git worktree`).
- avoid stepping on unrelated local changes (prefer a clean, autocoder-owned workspace).

Decision:
- maintain a dedicated autocoder-managed checkout and use worktrees per issue.

### Repo bootstrap
How a session starts:
- the user launches autocoder for a repo by providing the repo clone URL (SSH form recommended).

Managed checkout behavior:
- if an autocoder-managed checkout already exists for that repo, reuse it and do not reset/overwrite it.
- if no checkout exists, clone it under `~/autocoder/` and use that directory going forward.

Note:
- multiple repos are handled by running multiple autocoder sessions, each with its own managed checkout and polling loop.

### Suggested local directory layout
Goal: predictable structure while avoiding leaking local machine details into GitHub comments.

Suggested layout:
- `~/autocoder/repos/<owner>/<repo>/repo/` (the managed clone)
- `~/autocoder/repos/<owner>/<repo>/worktrees/issue-<n>/` (per-issue worktrees)
- `~/autocoder/repos/<owner>/<repo>/state/` (local state, cursors, caches)

Do not include these absolute paths in issue/PR comments.

## Local artifacts and attachments
Autocoder needs per-issue local scratch space for:
- downloaded issue/PR attachments
- codex transcripts / prompts (optional)
- derived notes and intermediate artifacts

Decision:
- store these under a per-worktree directory named `.autocoder/` inside the issue worktree.
- ensure `.autocoder/` is ignored by git in the autocoder-managed checkout so it is never accidentally committed.

Ignore mechanism:
- do not require changing the tracked `.gitignore` of the target repo.
- prefer adding `.autocoder/` to the local exclude file in the autocoder-managed checkout (for example via `.git/info/exclude`) so it remains local-only.

Attachment handling requirements:
- detect and download attachments linked from issue-author comments/reviews into `.autocoder/artifacts/`; ignore attachment links from issue/PR bodies and from other users.
- perform attachment extraction/filtering in runtime (not prompt-only behavior), and persist a deterministic local manifest at `.autocoder/artifacts/attachments-manifest.json`.
- on each sync, prune stale manifest entries and delete stale attachment files under `.autocoder/artifacts/` when they are no longer referenced by trusted issue-author content.
- treat attachments as part of the requirements/spec for the issue.
- do not commit attachments unless they are explicitly needed for the change (treat them as inputs by default).
- when attachments may contain sensitive or confidential data, keep them local-only and avoid quoting raw sensitive contents in issue/PR comments.
- enforce a per-issue download limit (200MB total).

Allowed attachment types:
- download any file type that is linked and retrievable via `gh`/HTTP.
- for safety, only auto-download from GitHub-hosted HTTPS URLs by default (repo host + known GitHub attachment hosts).
- skip external URLs and ask the human to re-attach via GitHub when needed.
- never execute attachments.
- do not automatically extract archives unless the issue explicitly requires it.

Retention:
- `.autocoder/` contents are local-only and are deleted on local cleanup (PR merged, issue closed, or stop via label removal).

Sharing outputs:
- default: summarize results in issue/PR comments.
- attach raw files only when they belong in the repo (commit them) or when a repo-specific workflow provides an explicit storage location.

Suggested `.autocoder/` layout:
- `.autocoder/artifacts/`: downloaded inputs and output artifacts (local-only).
  - include trusted thread context at `.autocoder/artifacts/trusted-thread-context.json` (runtime-generated, filtered to issue-author non-bot comments/reviews only).
- `.autocoder/plan/`: ephemeral working notes and orchestration state (local-only).
  - `.autocoder/plan/current/notes.md`
  - `.autocoder/plan/current/notes-index.md`
  - `.autocoder/plan/current/orchestrator-status.md`

## Terminal logging
Autocoder should emit structured, high-signal logs to stderr so an operator can understand what it's doing while polling.

Requirements:
- include timestamp, severity level, and key context (repo, issue, branch, PR, trigger reasons) when applicable.
- log at least one line per poll iteration, including explicit idle/skip reasons.
- default verbosity should be useful but not spammy; increase verbosity via `AUTOCODER_LOG_LEVEL=debug`.
- never print `.env` contents into logs.
- avoid logging large free-form text bodies (for example issue/PR comment bodies); prefer passing them via stdin to `gh` using `--body-file -` when supported.

## Environment variables and `.env` propagation
Many repos rely on local `.env` files that are intentionally not committed. `git worktree` does not copy untracked files into new worktrees.

Requirements:
- autocoder inherits the local process environment by default (shell env vars, login session, etc).
- when creating a new issue worktree, autocoder should ensure a `.env` file exists in the worktree root if one is available.
- autocoder must never print `.env` contents into issue/PR comments or logs.
- `.env` must never be committed.

Proposed simple behavior:
- treat the managed clone's `.env` file (if present) as the canonical source for the repo session.
- on worktree creation:
  - if `<worktree>/.env` already exists, do nothing.
  - else if `<managed-clone>/.env` exists, copy it into `<worktree>/.env`.
  - else do nothing (and allow downstream commands to fail normally; autocoder may then ask the human to provide `.env` setup instructions if needed).

Ignoring:
- ensure `.env` is locally ignored via the managed clone's local exclude mechanism (same approach as `.autocoder/`), so it cannot be accidentally committed.

## Syncing with humans' work
Assumptions:
- humans may be committing and merging PRs to the base branch while autocoder is working.

Required behavior:
- autocoder periodically fetches from remote and integrates the latest base branch changes into its issue branch.
- prefer merge from base branch into the issue branch over rebasing/history rewrite (keeps history stable for a long-running PR).
- if merges produce conflicts, autocoder resolves them and reports the resolution clearly in the PR/issue.
- when merge-syncing from base branch, treat it as high risk: inspect conflicts carefully, run relevant verification after merge, and do not push a merge result unless confidence is high that neither the issue branch behavior nor merged base-branch behavior regressed.

## Communication contract
Goals:
- be explicit about current state, what was tried, what remains, and what input is needed.
- ask high-leverage questions only (educated by the codebase and prior context).

Minimum communication behaviors:
- all automated comments are prefixed with:
  - first line: `[autocoder]`
  - second line: empty
- when waiting for human input: tag/mention the configured human(s).
- when starting implementation: post a short plan and checkpoints.
- when opening a PR: link it from the issue and summarize what changed and how it was verified.
- keep PR title/body aligned with the current state and scope; update them when scope materially changes (avoid spam edits).
- include an issue-closing reference in the PR body by default:
  - `Fixes #<issue-number>`
- do not include sensitive local machine details in GitHub comments (hostnames, absolute local paths, secrets).
- avoid posting confidential or sensitive business/user data in issue/PR comments; summarize at a safe level when possible.

## Safety boundaries
- operate only within the configured target repo root.
- never run destructive operations without explicit configuration/approval semantics.
- keep credentials local; do not print secrets into issue/PR comments.
- do not commit secrets, tokens, private keys, or confidential internal information into repo files, docs, or notes.

## Out of scope
- coordinating multiple target repos from one instance.
- multiple PRs per issue (unless explicitly allowed later).
- non-GitHub forges (GitLab, etc).

## Open Questions (to resolve before implementation)
No blocking items listed.
