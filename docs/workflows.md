# Operating Workflow

This document defines how work is tracked so progress compounds without context bloat.

## Core mode
- Keep active, disposable notes in `/plan/current/`.
- Promote durable guidance into `/docs/`.
- Capture important rationale in the smallest durable place (code comments, tests, or docs).
- Keep the canonical product/workflow spec in `docs/spec.md` aligned with reality.
- Keep the workflow spartan: short notes, clear routing, minimal ceremony.
- Keep an open-source-ready posture across docs/notes: write as if content may become public.

## Note routing
- `/plan/current/notes.md`: running task notes, key findings, and next actions (create as needed).
- `/plan/current/notes-index.md`: compact index of active workstreams and pointers to detailed notes (create as needed).
- `/plan/current/orchestrator-status.md`: packet/status board for parallel or subagent work (create as needed).
- `/plan/handoffs/`: sequential handoff summaries for staged automation workflows.
- Never place secrets, raw credentials, or confidential internal data in plan notes; use sanitized summaries.

## Parallel and subagent workflows
- Use isolated worktrees or dedicated working directories when streams are independent.
- Track each stream with owner, scope, status, blocker, and last update.
- Require each stream to produce a concise handoff summary before merge.

## Promotion cycle
- During execution: write concise notes to `/plan/current/`.
- At meaningful milestones: consolidate and de-duplicate active notes.
- Before finishing: promote durable learnings to `/docs/` and trim stale `/plan/` artifacts.

## Stop conditions
- Stop when acceptance checks pass, risks are documented, and no unresolved blockers remain.
- If no new evidence appears, avoid repeating the same loop; report completion instead.
