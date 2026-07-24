# Operating Workflow

This document defines how work is tracked without carrying unnecessary task history.

## Core mode
- Keep active, disposable notes in `/plan/current/`.
- Promote durable guidance into `/docs/`.
- Capture important rationale in the smallest durable place (code comments, tests, or docs).
- Keep the canonical product/workflow spec in `docs/spec.md` aligned with reality.
- Keep notes short, routing clear, and process proportional to the work.
- Treat docs and notes as public; never include secrets or confidential data.

## Note routing
- `/plan/current/notes.md`: running task notes, key findings, and next actions (create as needed).
- `/plan/current/notes-index.md`: compact index of active workstreams and pointers to detailed notes (create as needed).
- `/plan/current/orchestrator-status.md`: packet/status board for parallel or subagent work (create as needed).
- `/plan/handoffs/`: sequential handoff summaries for staged automation workflows.
- Runtime issue-worktree scratch uses `.autocoder/plan/` (for example `.autocoder/plan/current/...`); keep that local to the issue worktree.
- Never place secrets, raw credentials, or confidential internal data in plan notes; use sanitized summaries.

## Parallel and subagent workflows
- Parallelize only genuinely separate work that benefits from it.
- Keep one implementation owner. Give other workers narrow scopes, inputs, acceptance checks, and a synthesis point.
- Use isolated worktrees only when workers will make independent edits. Shared read-only audits may use one working tree.
- Create a handoff only when work is staged, interrupted, or transferred.

## Promotion cycle
- During execution: write concise notes to `/plan/current/`.
- At meaningful milestones: consolidate and de-duplicate active notes.
- Before finishing: promote only durable knowledge to `/docs/` and delete stale or completed `/plan/` artifacts.

## Stop conditions
- Stop when acceptance checks pass, risks are documented, and no unresolved blockers remain.
- If no new evidence appears, avoid repeating the same loop; report completion instead.
