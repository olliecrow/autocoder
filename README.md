# autocoder

autocoder runs an issue to pull request loop for one GitHub repository at a time.
You add a label, it works in isolated worktrees, and it reports status back to GitHub.

## Current status

This project is actively maintained and used for production issue-to-PR workflows.

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

## Security model

Codex uses `workspace-write` by default, with command approvals disabled. Network access and writes outside the worktree are restricted by Codex. autocoder commits and pushes after the run. A Git worktree alone is not a security boundary.

**Behavior change:** earlier releases used unrestricted execution. Tasks that need network access or writes outside the worktree can now fail. To restore that capability, set `codex_sandbox = "danger-full-access"` in your autocoder config. Use this only in a dedicated OS user, VM, or container with no unrelated credentials or private files.

### Recommended isolation

- Set `GH_TOKEN` to a fine-grained token limited to the single target repo. Grant Contents, Issues, and Pull requests read/write, plus Metadata read. Do not grant Workflows or Administration.
- Use a write-enabled SSH deploy key for that repo only. Configure the managed clone to use that key with `IdentitiesOnly=yes`; do not expose an agent with unrelated keys.
- Protect the default branch and require a pull request. The autocoder push guard does not constrain shell commands that Codex runs itself in unrestricted mode.
- Trust allowlisted issue authors and everyone with repo write access at code-execution level. Writers control repo files and can edit comments. Triage users can label an allowlisted author's issue. The allowlist filters thread input; it does not make repo code or attachments safe.
- Run autocoder as a dedicated OS user (or in a VM or container) in both sandbox modes. `workspace-write` limits writes and network access, not reads: Codex can read every file that user can read, including credential files and the copied `.env`.
- Keep unrelated secrets out of the worker environment. Outgoing text redaction and the pre-push scan (known token formats and values of secret-named variables) are a second line of defense. They cannot catch encoded or transformed secrets.

See `docs/spec.md` for runtime behavior and `SECURITY.md` for private reports.

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

3. Configure the GitHub logins autocoder is allowed to trust.

```toml
# ~/autocoder/config.toml
allowed_github_logins = ["your-github-login"]
```

4. Run autocoder for one repository.

```bash
uv run autocoder run git@github.com:OWNER/REPO.git
```

5. Optional quick checks before running.

```bash
uv run autocoder doctor git@github.com:OWNER/REPO.git
uv run autocoder dry-run git@github.com:OWNER/REPO.git
```

Show command help.

```bash
autocoder --help
autocoder run --help
```

Optional tab completion setup.

```bash
# bash
autocoder completion bash > ~/.local/share/bash-completion/completions/autocoder

# zsh
mkdir -p ~/.zsh/completions
autocoder completion zsh > ~/.zsh/completions/_autocoder
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

- Inspect `.autocoder/plan/codex-run.log` in the issue worktree for worker output. The next run replaces it.
- Set `AUTOCODER_CODEX_TIMEOUT_S` to a positive number of seconds (default: 36000).
- Set `mentions = ["<login>"]` in config for needs-info notifications. Only allowlisted logins are mentioned.
- Human comments must not start with `[autocoder]`; that prefix identifies bot output.
- Set `AUTOCODER_LOG_LEVEL=debug` when you need verbose diagnostics.
- autocoder keeps a per-repo lock, so you do not get two runs on the same repo at once.

## Known limitations

- One autocoder process manages one repository at a time.
- Within a repository session, opted-in issues are processed sequentially (not in parallel).
- It depends on local `gh` and `codex` authentication sessions.
- It requires SSH clone access to target repositories.

## Local state and directory layout

autocoder keeps managed runtime state under `~/autocoder/`.

- managed clone: `~/autocoder/repos/<owner>/<repo>/repo`
- per-issue worktrees: `~/autocoder/repos/<owner>/<repo>/worktrees/issue-<n>`
- runtime state: `~/autocoder/repos/<owner>/<repo>/state`
- global config: `~/autocoder/config.toml`
- per-repo config: `~/autocoder/repos/<owner>/<repo>/config.toml`
- local issue artifacts: `.autocoder/` inside issue worktrees, gitignored

## Documentation map

- `docs/README.md`: canonical index for repository documentation.
- `docs/spec.md`: canonical behavior and runtime/security contract.
- `AGENTS.md`: contributor and agent operating guidelines.
- `SECURITY.md`: vulnerability reporting policy.
- `LICENSE`: Apache-2.0 license.

<!-- third-party-policy:start -->
## Third-Party Code Policy
This repository allows external-code snapshots for static analysis only. Keep them in ignored `plan/` locations, remove every clone remote immediately, delete only the verified clone's Git metadata, and never execute the cloned code.

See `docs/untrusted-third-party-repos.md`.
<!-- third-party-policy:end -->
