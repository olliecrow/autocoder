# Repository Guidelines

## Project Overview (autocoder)
- autocoder runs locally and works on exactly one GitHub repo / working copy at a time.
- work is coordinated via GitHub Issues and Pull Requests (issues are the main human-agent interface).
- workflow is specs-first: for non-trivial work, clarify requirements in the issue (and/or in `docs/spec.md`) before implementation.
- `docs/spec.md` is the canonical source of truth for current behavior; keep it consistent with the code.

## Repository Ownership
- This repository belongs under the personal GitHub account `olliecrow`.
- Do not move it to a GitHub organization or a different personal account unless Ollie explicitly asks for that change.
- When docs, remotes, automation, releases, or publishing steps need the owning GitHub account, use `olliecrow`.

## Public Project Posture
- Treat every tracked artifact, commit, branch, pull request, and release as public.
- Never commit secrets, credentials, tokens, private keys, or confidential internal information.
- Redact or generalize sensitive details in docs, notes, logs, tests, examples, and metadata.
- Keep authentication material in local environment/secret stores, not in committed files.
- If uncertain whether content is sensitive, treat it as sensitive until explicitly confirmed safe.
- Keep shared work portable. Use runtime discovery, configuration, explicit inputs, or placeholders instead of personal or machine-specific paths, aliases, or account details unless the repository contract genuinely requires them.

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
- `plan/experiments/`
- `plan/artifacts/`
- `plan/scratch/`
- `plan/handoffs/`

## Operating Principles
- Prioritize correctness, clarity, pragmatism, and rigor.
- Think before coding: state assumptions, identify risks, and clarify ambiguity early.
- Keep solutions simple and surgical; avoid overengineering and avoid hacky workarounds.
- Stay tightly in scope: change only what is required for the task.
- Resolve context from available evidence. Ask only when a missing decision materially changes behavior, authority, cost, or risk.
- Match planning, testing, review, and documentation effort to risk and uncertainty.
- Keep one clear current path. Remove stale, duplicate, completed, temporary, and superseded material within scope.
- Capture only durable behavior, rationale, constraints, or operating knowledge that code and tests cannot express clearly.

## Multi-Agent Collaboration
- Use multiple agents only when work is long, risky, genuinely separable, or benefits from independent evidence.
- Keep one implementation owner. Give other agents narrow packets with inputs, acceptance checks, and a synthesis step.
- Use single-agent execution when scope is small or coordination overhead outweighs gains.

## Execution Workflow
1. Understand the request and constraints.
2. If non-trivial, create a verifiable plan with checkpoints.
3. Execute end-to-end without unnecessary pauses when confidence is high.
4. Persist until complete; do not stop at partial handoffs.
5. After implementation, compare the result once against the request and acceptance checks.
6. Stop when the outcome is proven and no actionable in-scope work remains.

## Verification Standards
- Verify behavior with tests/checks, not assumptions.
- Broaden checks around edge cases, regressions, and invariants in proportion to the change's risk.
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
- An authorized implementation includes standing authority to commit coherent checkpoints and push the current task branch to its configured remote.
- Before pushing, verify the exact remote, branch, divergence, and full outgoing range. Never force-push or batch unrelated refs.
- Pull requests, releases, deployment, live operations, and destructive actions need separate authority.
- After pushing, monitor required remote checks for the exact commit and fix in-scope failures with forward-only commits.

## Documentation and Decisions
- Capture durable rationale for non-obvious decisions in the most local durable place (tests/code/docs).
- Keep long-lived docs aligned with actual behavior; keep scratch notes out of committed docs.
- Compound knowledge and learnings over time.

## Communication
- Provide brief progress updates during work.
- In the final response, include: what changed; why; verification evidence (tests/checks run); open risks or unknowns; and concise next steps when useful.
- If there are decisions to be made, always state your recommendation.

## Repository Skills
- When a non-trivial repository procedure has recurred or is explicitly expected to recur, capture or improve it under `.agents/skills/<name>/SKILL.md`.
- Do not create skills for one-off, trivial, speculative, or already-obvious work. Consolidate overlaps and remove stale skills.
- Keep skills concise and portable, with trigger-oriented `name` and `description` frontmatter.

## Third-Party Dependency Trust Policy
- Prefer official packages, libraries, SDKs, frameworks, and services from authoritative sources.
- Prefer options that are reputable, well-maintained, popular, and well-supported.
- Before adopting or upgrading third-party dependencies, verify ownership/publisher authenticity, maintenance activity, security history, license fit, and ecosystem adoption.
- Avoid low-trust, obscure, or weakly maintained dependencies when a stronger alternative exists.
- Pin versions and keep lockfiles current for reproducibility and supply-chain safety.
- If trust signals are unclear, do not adopt the dependency until explicitly approved.

<!-- third-party-policy:start -->
## Third-Party Repository Handling
- External repositories may be cloned for static analysis only.
- Clone them only into ephemeral `plan/` locations such as `plan/scratch/upstream/` or `plan/artifacts/external/`.
- Resolve and verify the exact clone path before cleanup. Remove every clone remote immediately, then delete only that clone's Git metadata, using a recoverable operation when available.
- Never execute third-party code (no scripts, tests, builds, package installs, binaries, or containers).
- Persistent remotes in this working copy must match the configured repository owner and target. External-clone remotes must never persist.
<!-- third-party-policy:end -->

## Plain English Default
- Use plain English in chat, session replies, docs, notes, comments, reports, commit messages, issue text, and review text.
- Prefer short words, short sentences, and direct statements.
- If a technical term is needed for correctness, explain it in simple words the first time.
- In code, prefer clear descriptive names for files, folders, flags, config keys, functions, classes, types, variables, tests, and examples.
- Avoid vague names, short cryptic names, and cute internal code names unless an old established name is already clearer than changing it.
- When touching old code, rename confusing names if the change is low risk and clearly improves readability.
- Keep the durable why for this rule in `docs/decisions.md`.
