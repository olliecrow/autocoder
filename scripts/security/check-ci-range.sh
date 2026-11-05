#!/usr/bin/env bash
set -euo pipefail

if [[ "${GITHUB_EVENT_NAME}" == "pull_request" ]]; then
  base="${PR_BASE_SHA:?}"
  tip="${PR_HEAD_SHA:?}"
else
  base="${PUSH_BEFORE_SHA:-}"
  tip="${GITHUB_SHA:?}"
fi
[[ "$tip" =~ ^[0-9a-f]{40}$ ]] || exit 2
if [[ -z "$base" || "$base" == "0000000000000000000000000000000000000000" ]]; then
  range="${tip}^!"
  base=""
else
  [[ "$base" =~ ^[0-9a-f]{40}$ ]] || exit 2
  range="${base}..${tip}"
fi
# Verify before scanning: invalid revisions must never count as a clean range.
git rev-list "$range" >/dev/null
gitleaks git --redact --config .gitleaks.toml --log-opts="--diff-merges=first-parent ${range}"
bash scripts/security/check-push-range.sh --from "$base" --to "$tip"
