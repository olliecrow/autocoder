# Docs Directory

This directory holds long-term, agent-focused documentation for this repo. It is committed to git.

Entry points:
- `AGENTS.md` (repo root): contributor/agent operating instructions.
- `docs/spec.md`: canonical product/workflow spec for autocoder.
- `docs/workflows.md`: how we do work in this repo (notes, promotion, orchestration).
- `docs/decisions.md`: durable decision log with context/rationale/trade-offs/enforcement.
- `docs/project-preferences.md`: maintenance preferences and quality/security expectations.
- `docs/untrusted-third-party-repos.md`: strict policy for cloning/analyzing third-party repos safely.

Principles:
- Keep content evergreen and aligned with the codebase.
- Avoid time- or date-dependent language.
- Prefer updating existing docs over adding new files unless the content is clearly distinct.
- Use docs for cross-cutting context or rationale that does not belong in code comments or tests.
- Keep entries concise and high-signal.
- Keep `README.md` focused on onboarding/quickstart; keep behavior contracts in `docs/spec.md`.
- Treat docs as future-public artifacts; never include secrets or confidential internal data.

Relationship to `/plan/`:
See `docs/workflows.md` for the full note-routing and promotion workflow.
