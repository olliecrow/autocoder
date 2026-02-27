# Repository Guidelines

## Project Overview (autocoder)
- autocoder runs locally and works on exactly one GitHub repo / working copy at a time.
- work is coordinated via GitHub Issues and Pull Requests (issues are the main human-agent interface).
- workflow is specs-first: for non-trivial work, clarify requirements in the issue (and/or in `docs/spec.md`) before implementation.
- `docs/spec.md` is the canonical source of truth for current behavior; keep it consistent with the code.

## Open-Source Transition Posture
- Treat the project as open-source-ready, even while the repository is private.
- Never commit secrets, credentials, tokens, private keys, or confidential internal information.
- Write docs and notes as if they may become public artifacts; redact or generalize sensitive details.
- Keep authentication material in local environment/secret stores, not in committed files.
- If uncertain whether content is sensitive, treat it as sensitive until explicitly confirmed safe.

## Docs, Plans, and Decisions (agent usage)
- `docs/` is long-lived, agent-focused, committed to git, and evergreen.
- `plan/` is short-lived scratch space for agents and is not committed (ignored by git).
- Decision capture policy lives in `docs/decisions.md`.
- Operating workflow conventions live in `docs/workflows.md`.

## README and Instructions Maintenance
- Keep user-facing quickstart and orientation guidance in `README.md`.
- Keep canonical behavior and runtime/security contracts in `docs/spec.md`.
- Keep process/routing conventions in `docs/workflows.md`.
- Keep non-obvious durable rationale in `docs/decisions.md`.
- When behavior changes, update the relevant docs in the same workstream to avoid drift.

## Note Routing (agent usage)
- Active notes: `plan/current/notes.md`
- Workstream index: `plan/current/notes-index.md`
- Orchestration status: `plan/current/orchestrator-status.md`
- Sequential handoffs: `plan/handoffs/`

## Plan Directory Structure (agent usage)
- `plan/current/`
- `plan/backlog/`
- `plan/complete/`
- `plan/experiments/`
- `plan/artifacts/`
- `plan/scratch/`
- `plan/handoffs/`

## Operating Principles
- Prioritize correctness, clarity, pragmatism, and rigor.
- Think before coding: state assumptions, identify risks, and clarify ambiguity early.
- Keep solutions simple and surgical; avoid overengineering and avoid hacky workarounds.
- Stay tightly in scope: change only what is required for the task.
- Be proactive. Be helpful and always consider 1 step ahead (for example: what the next obvious instruction might be).
- Compound knowledge over time. This is often done by making good notes/docs.
- Don't be afraid of long running jobs/tasks. It's ok for a plan to take hours to complete, provided that the plan and codebase are moving in the right direction.

## Multi-Agent Collaboration
- Use multiple agents/subagents when it is likely to improve speed, quality, or confidence.
- Split work into clear packets with owner, inputs, acceptance checks, and a synthesis step when parallelizing.
- Use single-agent execution when scope is small or coordination overhead outweighs gains.

## Execution Workflow
1. Understand the request and constraints.
2. If non-trivial, create a verifiable plan with checkpoints.
3. Execute end-to-end without unnecessary pauses when confidence is high.
4. Persist until complete; do not stop at partial handoffs.
5. After implementation, do a final comb-through against the plan and requirements.
6. Be proactive, and repeat until all items have been completed and verified fully.

## Verification Standards
- Verify behavior with tests/checks, not assumptions.
- Battle-test meaningful changes from multiple angles (edge cases, regressions, invariants).
- Before commit/merge/push-related actions, ensure relevant tests/pre-commit/CI checks pass when available.
- If something is not fully verified, explicitly say what remains and why.
- If there is a next obvious thing to do, then do it rather than waiting for confirmation/instruction.

## Code Quality
- Preserve existing patterns unless change is required.
- Remove redundancy, dead code introduced by your changes, and temporary artifacts.
- Clean up as you go.
- Keep comments concise and only where they add real value.
- Avoid silent fallbacks for invalid states; fail clearly where appropriate.

## Git and Safety
- Never use destructive git operations unless explicitly requested.
- Do not rewrite history unless explicitly requested.
- Do not revert unrelated user changes. There might be multiple people/agents working on the same copy of the codebase.
- Commit little and often in small logical units; prefer several focused commits over one large commit.

## Documentation and Decisions
- Capture durable rationale for non-obvious decisions in the most local durable place (tests/code/docs).
- Keep long-lived docs aligned with actual behavior; keep scratch notes out of committed docs.
- Compound knowledge and learnings over time.

## Communication
- Provide brief progress updates during work.
- In the final response, include: what changed; why; verification evidence (tests/checks run); open risks or unknowns; and concise next steps when useful.
- If there are decisions to be made, always state your recommendation.

## Dictation-Aware Input Handling
- The user often dictates prompts, so minor transcription errors and homophone substitutions are expected.
- Infer intent from local context and repository state; ask a concise clarification only when ambiguity changes execution risk.
- Keep explicit typo dictionaries at workspace level (do not duplicate repo-local typo maps).
