# Project Preferences (Going Forward)

These preferences define how `autocoder` should be maintained as an open-source-ready project.

## Quality and Scope

- Keep changes simple, surgical, and clearly testable.
- Preserve existing behavior unless a change is explicitly intended.
- Prefer robust, reusable behavior over one-off local customizations.

## Security and Confidentiality

- Never commit secrets, credentials, tokens, API keys, or private key material.
- Never commit private/sensitive machine paths; use placeholders such as `/path/to/project`, `/Users/YOU`, `/home/user`, or `C:\\Users\\USERNAME`.
- Keep local runtime state untracked (`.env*`, `.claude/`, `.codex/`, virtualenvs, temp artifacts).
- If sensitive data is found in history, rotate credentials and scrub history before publication.

## Documentation Expectations

- Keep `README.md` current with project aim, behavior, requirements, auth, quick start, getting started, local state, and debugging guidance.
- Keep docs aligned with actual behavior and remove stale instructions quickly.

## Verification Expectations

- Run relevant tests/checks before merge.
- Run `autocoder doctor <repo-ssh-url>` and `autocoder dry-run <repo-ssh-url>` before long polling sessions.
- Record verification evidence in PRs/issues when practical.

## Collaboration Preferences

- Preserve accurate author/committer attribution for each contributor.
- Prefer commit author identities tied to genuine human GitHub accounts, not fabricated bot names/emails.
- Avoid destructive history rewrites unless required for secret/confidentiality remediation.
