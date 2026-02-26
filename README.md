# autocoder

autocoder runs an issue to pull request loop for one GitHub repository at a time.
You add a label, it works in isolated worktrees, and it reports status back to GitHub.

## What this project is trying to achieve

Give teams a simple and reliable way to automate issue handling while keeping humans in charge of review and merge.

## What you experience as a user

1. You add the `autocoder` label to an issue.
2. autocoder claims the issue and starts work in an isolated worktree.
3. It runs Codex to implement and verify the requested change.
4. It pushes a branch and opens or updates a pull request.
5. It posts progress and outcomes in the issue and pull request.
6. You review and merge when ready.
7. To stop work, remove the `autocoder` label.

## Quick start

1. Authenticate local tools.

```bash
gh auth login
gh auth status
```

2. Install dependencies.

```bash
uv sync
```

3. Run autocoder for one repository.

```bash
uv run python -m autocoder run git@github.com:OWNER/REPO.git
```

Alternative entrypoints.

```bash
python -m autocoder run git@github.com:OWNER/REPO.git
autocoder run git@github.com:OWNER/REPO.git
```

## Requirements

- Python `3.11+`
- `git`
- GitHub CLI `gh`, authenticated for the target repo
- Codex CLI, installed and authenticated
- SSH access to target repositories, for example `git@github.com:OWNER/REPO.git`

## Authentication

autocoder reuses your local authenticated sessions.

- GitHub auth from `gh auth login`
- Codex auth from your local Codex CLI setup

autocoder does not run its own OAuth flow.

## Helpful tips

- Set `AUTOCODER_LOG_LEVEL=debug` when you need verbose diagnostics.
- autocoder keeps a per-repo lock, so you do not get two runs on the same repo at once.

## Local state and directory layout

autocoder keeps managed runtime state under `~/autocoder/`.

- managed clone: `~/autocoder/repos/<owner>/<repo>/repo`
- per-issue worktrees: `~/autocoder/repos/<owner>/<repo>/worktrees/issue-<n>`
- runtime state: `~/autocoder/repos/<owner>/<repo>/state`
- per-repo config: `~/autocoder/repos/<owner>/<repo>/config.toml`
- local issue artifacts: `.autocoder/` inside issue worktrees, gitignored

## Documentation map

- `README.md`: human-facing overview and quick start
- `AGENTS.md`: contributor and agent operating guidelines
- `docs/spec.md`: canonical behavior and runtime security contracts
- `docs/workflows.md`: execution and note routing conventions
- `docs/decisions.md`: durable rationale and decision log
- `docs/project-preferences.md`: durable project maintenance preferences
