#!/usr/bin/env bash
# Scan commit messages and added lines in a push range for sensitive text.
# Any git failure or bad input exits non-zero, so an error never passes.
set -euo pipefail

usage() {
  cat >&2 <<'EOF'
usage: check-push-range.sh [--from <sha>] --to <sha>

Scans every commit in <from>..<to>. Without --from, or with an all-zero
--from, scans the commits in <to> that are not on any remote, or <to>
alone when all of them are. Merge commits are scanned against their
first parent. With no flags, reads the range that pre-commit sets for
pre-push hooks.
EOF
}

zero_ref="0000000000000000000000000000000000000000"
object_id_regex='^([0-9a-f]{40}|[0-9a-f]{64})$'
local_ref_regex='^(HEAD|refs/[A-Za-z0-9._/+-]+)$'
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

die() {
  echo "error: $*" >&2
  exit 1
}

if [[ "$#" -eq 0 ]]; then
  from_ref="${PRE_COMMIT_FROM_REF:-}"
  to_ref="${PRE_COMMIT_TO_REF:-}"
  # pre-commit sets no range when the push includes the root commit.
  # It still names the local ref, so resolve that ref to a commit.
  local_ref="${PRE_COMMIT_LOCAL_BRANCH:-}"
  if [[ -z "$to_ref" && -n "$local_ref" ]]; then
    [[ "$local_ref" =~ $local_ref_regex ]] || die "invalid local ref for the push"
    to_ref="$(git rev-parse --verify --quiet "${local_ref}^{commit}")" ||
      die "unable to resolve the local ref for the push"
  fi
else
  from_ref=""
  to_ref=""
  while [[ "$#" -gt 0 ]]; do
    case "$1" in
      --from | --to)
        [[ "$#" -ge 2 ]] || { usage; exit 2; }
        if [[ "$1" == "--from" ]]; then from_ref="$2"; else to_ref="$2"; fi
        shift 2
        ;;
      -h | --help)
        usage
        exit 0
        ;;
      *)
        usage
        exit 2
        ;;
    esac
  done
fi

[[ -n "$to_ref" ]] || exit 0
[[ "$to_ref" =~ $object_id_regex ]] || die "push target is not a full commit ID"
if [[ -n "$from_ref" ]]; then
  [[ "$from_ref" =~ $object_id_regex ]] || die "push base is not a full commit ID"
fi

# An all-zero target means the push deletes a ref. Nothing new is sent.
[[ "$to_ref" == "$zero_ref" ]] && exit 0

if [[ -z "$from_ref" || "$from_ref" == "$zero_ref" ]]; then
  commit_list="$(git rev-list "$to_ref" --not --remotes)" ||
    die "unable to list commits for the push range"
  [[ -n "$commit_list" ]] || commit_list="$to_ref"
else
  commit_list="$(git rev-list "${from_ref}..${to_ref}")" ||
    die "unable to list commits for the push range"
fi

[[ -n "$commit_list" ]] || exit 0

tmp_dir="$(mktemp -d)"
trap 'rm -rf -- "${tmp_dir}"' EXIT

commit_msg_file="${tmp_dir}/commit_messages.txt"
added_lines_file="${tmp_dir}/added_lines.txt"

printf '%s\n' "$commit_list" |
  git log --stdin --no-walk=unsorted --format='%H%n%s%n%b%n' >"${commit_msg_file}"

# Print only "+" lines inside hunks, so an added line that itself starts
# with "++" is kept. --no-ext-diff and --no-textconv make git print the
# real content instead of running a diff driver from the repo config.
printf '%s\n' "$commit_list" |
  git log --stdin --no-walk=unsorted -m --first-parent --format= --patch \
    --no-color --unified=0 --no-ext-diff --no-textconv |
  awk '/^diff / { in_hunk = 0; next } /^@@ / { in_hunk = 1; next } in_hunk && /^\+/ { sub(/^\+/, ""); print }' \
    >"${added_lines_file}"

bash "${script_dir}/check-sensitive-text.sh" --context=push-commit-message "${commit_msg_file}"
bash "${script_dir}/check-sensitive-text.sh" --context=push-added-lines "${added_lines_file}"
