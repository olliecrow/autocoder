#!/usr/bin/env bash
set -euo pipefail

context="text"
if [[ "${1:-}" == --context=* ]]; then
  context="${1#--context=}"
  shift
fi

if [[ "$#" -lt 1 ]]; then
  echo "usage: check-sensitive-text.sh [--context=<label>] <file> [file...]" >&2
  exit 2
fi

local_path_regex='(/Users/[A-Za-z0-9._-]+|/home/[A-Za-z0-9._-]+|[A-Za-z]:\\+Users\\+[A-Za-z0-9._-]+)'
allowed_path_placeholder_regex='(/Users/(YOU|USER|username)|/home/(user|USER|username)|[A-Za-z]:\\+Users\\+(YOU|USER|USERNAME|username))'
secret_assignment_regex='([Aa][Pp][Ii][_-]?[Kk][Ee][Yy]|[Tt][Oo][Kk][Ee][Nn]|[Pp][Aa][Ss][Ss][Ww][Oo][Rr][Dd]|[Ss][Ee][Cc][Rr][Ee][Tt])[[:space:]]*[:=][[:space:]]*(["'"'"'][A-Za-z0-9_./+=-]{12,}["'"'"']|[A-Za-z0-9_./+=-]{12,})([[:space:]#;,}]|$)'
known_token_regex='((ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[0-9A-Z]{16}|sk-[A-Za-z0-9]{20,})'

# Print the line numbers that match an extended regex. Exit non-zero if
# grep itself fails, so a broken scan never reads as a clean one.
search_line_numbers() {
  local pattern="$1"
  local file_path="$2"
  local matches status=0
  matches="$(grep -anE -e "$pattern" -- "$file_path")" || status=$?
  if [[ "$status" -gt 1 ]]; then
    echo "error: unable to scan $(display_name "$file_path")" >&2
    return 2
  fi
  if [[ -n "$matches" ]]; then
    printf '%s\n' "$matches" | cut -d: -f1
  fi
}

# Check each local-path match on its own. A placeholder such as /Users/YOU
# is allowed only as a whole path segment. A longer name that starts with a
# placeholder, or a real path on the same line as one, is still reported.
# The regexes go through ENVIRON because awk -v would rewrite backslashes.
search_disallowed_path_line_numbers() {
  local file_path="$1"
  LOCAL_PATH_REGEX="$local_path_regex" \
    ALLOWED_PATH_REGEX="^${allowed_path_placeholder_regex}\$" \
    awk '{
      rest = $0
      while (match(rest, ENVIRON["LOCAL_PATH_REGEX"])) {
        if (substr(rest, RSTART, RLENGTH) !~ ENVIRON["ALLOWED_PATH_REGEX"]) {
          print NR
          next
        }
        rest = substr(rest, RSTART + RLENGTH)
      }
    }' "$file_path"
}

display_name() {
  local file_path="$1"
  case "$file_path" in
    /* | [A-Za-z]:[\\/]*)
      basename "$file_path"
      ;;
    *)
      printf '%s\n' "$file_path"
      ;;
  esac
}

report_lines() {
  local label="$1"
  local line_numbers="$2"
  if [[ -n "$line_numbers" ]]; then
    printf '  %s on line(s): %s\n' "$label" "$(printf '%s\n' "$line_numbers" | paste -sd, -)" >&2
  fi
}

failed=0
for target in "$@"; do
  if [[ ! -f "$target" ]]; then
    echo "error: file not found: $(display_name "$target")" >&2
    exit 2
  fi

  path_matches="$(search_disallowed_path_line_numbers "$target")"

  secret_assignment_matches="$(search_line_numbers "$secret_assignment_regex" "$target")"
  known_token_matches="$(search_line_numbers "$known_token_regex" "$target")"

  if [[ -n "$path_matches" || -n "$secret_assignment_matches" || -n "$known_token_matches" ]]; then
    echo "policy violation in ${context}: $(display_name "$target")" >&2
    report_lines "rule=local-path" "$path_matches"
    report_lines "rule=secret-assignment" "$secret_assignment_matches"
    report_lines "rule=known-token" "$known_token_matches"
    failed=1
  fi
done

if [[ "$failed" -ne 0 ]]; then
  cat >&2 <<'EOF'
Blocked by sensitive-text policy.
- Remove or redact secrets and credential-like values.
- Replace local absolute paths with repo-relative paths or placeholders like /path/to/project.
EOF
fi

exit "$failed"
