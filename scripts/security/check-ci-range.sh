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
[[ -z "$base" || "$base" =~ ^[0-9a-f]{40}$ ]] || exit 2
# A missing, zero, or unknown base (schedule, new branch, force push) scans
# all history reachable from the tip.
if [[ -z "$base" || "$base" == "0000000000000000000000000000000000000000" ]] ||
   ! git cat-file -e "${base}^{commit}" 2>/dev/null; then
  echo "push base missing or unknown; scanning all history reachable from ${tip}" >&2
  range="$tip"
  base=""
else
  range="${base}..${tip}"
fi
# Verify before scanning: invalid revisions must never count as a clean range.
git rev-list "$range" >/dev/null
# --text and --no-textconv scan binary and `-diff` files as text.
gitleaks git --redact --config .gitleaks.toml \
  --log-opts="--text --no-ext-diff --no-textconv --diff-merges=first-parent ${range}"
bash scripts/security/check-push-range.sh --from "$base" --to "$tip"
