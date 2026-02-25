# autocoder

autocoder is a local orchestrator that turns GitHub Issues into implemented Pull Requests by running Codex CLI against one target repository at a time.

## Project Aim

Provide a reliable issue-driven automation loop for one repository:

- humans manage work in GitHub issues and PRs
- autocoder claims opted-in issues and runs implementation locally
- autocoder opens or updates PRs with verification evidence
- humans review and merge

## What autocoder Does

- watches for opted-in issues (`autocoder` label)
- claims work with explicit lock labels/comments
- prepares isolated per-issue worktrees and branches
- runs Codex non-interactively for implementation and verification
- pushes issue branches and creates/updates PRs
- reports status back to issue/PR threads
- cleans up local state after completion

## Requirements

- Python `3.11+`
- `git`
- GitHub CLI (`gh`) authenticated for the target repo
- Codex CLI installed and authenticated
- SSH access to target repositories (`git@github.com:OWNER/REPO.git`)

## Authentication

autocoder reuses your local authenticated sessions:

- GitHub auth from `gh auth login`
- Codex auth from your local Codex CLI setup

autocoder does not run an OAuth flow itself.

## Quick Start

1. Authenticate local tools:

```bash
gh auth login
gh auth status
```

2. Install dependencies:

```bash
uv sync
```

3. Run autocoder for one repository:

```bash
uv run python -m autocoder run git@github.com:OWNER/REPO.git
```

Alternative entrypoints:

```bash
python -m autocoder run git@github.com:OWNER/REPO.git
autocoder run git@github.com:OWNER/REPO.git
```

## Getting Started Workflow

1. Add label `autocoder` to an issue authored by an allowed user.
2. autocoder claims the issue and creates/resumes an issue worktree.
3. autocoder runs Codex to implement and validate the requested change.
4. autocoder pushes branch updates and opens/updates the PR.
5. Human reviews and merges the PR.
6. To stop work, remove label `autocoder`.

## Local State and Directory Layout

autocoder keeps all managed runtime state under `~/autocoder/`:

- managed clone: `~/autocoder/repos/<owner>/<repo>/repo`
- per-issue worktrees: `~/autocoder/repos/<owner>/<repo>/worktrees/issue-<n>`
- runtime state: `~/autocoder/repos/<owner>/<repo>/state`
- per-repo config: `~/autocoder/repos/<owner>/<repo>/config.toml`
- local issue artifacts: `.autocoder/` inside issue worktrees (gitignored)

## Logging and Debugging

- logs are emitted to stderr with timestamps and issue/repo context
- set `AUTOCODER_LOG_LEVEL=debug` for verbose diagnostics
- a per-repo session lock prevents concurrent autocoder instances on the same repo

## Documentation Map

- `README.md`: human-facing overview and operator quickstart
- `AGENTS.md`: contributor/agent operating guidelines
- `docs/spec.md`: canonical behavior and runtime/security contracts
- `docs/workflows.md`: execution and note-routing conventions
- `docs/decisions.md`: durable rationale and decision log
- `docs/project-preferences.md`: durable project maintenance preferences
