# Untrusted Third-Party Repository Policy

This project allows cloning external repositories for static research only, with strict safety controls.

## Allowed Use
- External repositories may be cloned only when useful for analysis (for example competition research).
- Preferred locations are ephemeral project paths such as:
  - `plan/scratch/upstream/<source-repo>`
  - `plan/artifacts/external/<source-repo>`

## Mandatory Sanitization Immediately After Clone
1. Resolve and verify the exact `<clone-path>` is an external snapshot under `plan/`, not this repository or another working copy.
2. Remove every remote from that clone immediately.
3. Delete only `<clone-path>/.git`, using a recoverable trash operation when available. If Git metadata must be retained briefly for static comparison, keep it remote-free and remove it as soon as the comparison ends.
4. Persistent remotes in this working copy must match its configured repository owner and target.

## Hard Safety Constraint
- Treat all third-party code as untrusted.
- Never execute third-party code from these clones, including:
  - scripts
  - binaries
  - tests
  - build systems
  - package installers
  - containers
- Only static analysis is allowed (read/search/diff/review).

## Scope Boundary
- Do not mix third-party snapshots into normal project source trees.
- Keep external snapshots in ephemeral locations and remove them when no longer needed.
