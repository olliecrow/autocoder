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
# Gitleaks can log a git error, report zero commits, and still exit 0.
log_file="$(mktemp)"
trap 'rm -- "$log_file"' EXIT
status=0
gitleaks git --verbose --redact --no-banner --no-color --config .gitleaks.toml \
  --log-opts="--text --no-ext-diff --no-textconv --diff-merges=first-parent ${range}" \
  >"$log_file" 2>&1 || status=$?
cat "$log_file"
if [[ "$status" -ne 0 ]]; then
  exit "$status"
fi
if grep -qE '(^|[[:space:]])(ERR|FTL)[[:space:]]' "$log_file"; then
  echo "gitleaks logged an error" >&2
  exit 2
fi
# Gitleaks reports zero for deletion-only, rename-only, mode-only, and empty
# commits. Require a non-zero count only if some commit in the range adds lines.
if ! grep -qE '[1-9][0-9]* commits? scanned' "$log_file"; then
  has_additions="$(git log --text --no-ext-diff --no-textconv --diff-merges=first-parent \
    --format= --patch "$range" | awk '
      /^diff --git / { in_hunk=0 }
      /^@@ / { in_hunk=1; next }
      in_hunk && /^\+/ { found=1 }
      END { print found+0 }
    ')"
  if [[ "$has_additions" == 1 ]]; then
    echo "gitleaks scanned no commits in a range with added lines" >&2
    exit 2
  fi
fi
bash scripts/security/check-push-range.sh --from "$base" --to "$tip"
