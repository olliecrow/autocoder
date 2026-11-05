from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
import os
from pathlib import Path
import tempfile


@dataclass
class IssueState:
    branch: str | None = None
    pr: int | None = None
    last_notice: str | None = None
    pr_search_done: bool = False
    run_failed: bool = False
    trusted_issue_body: str | None = None
    last_seen_issue_updated_at: str | None = None
    last_seen_pr_updated_at: str | None = None
    last_seen_default_branch_sha: str | None = None
    # Digests of allowlisted human activity (used to ignore noise from other users).
    last_seen_allowed_issue_digest: str | None = None
    last_seen_allowed_pr_digest: str | None = None


@dataclass
class RepoState:
    """
    Per-repo persistent state.

    `issues` contains per-issue cursors/digests for issues currently owned by this autocoder instance.
    """

    issues: dict[int, IssueState] = field(default_factory=dict)


def _optional_string(value: object, *, field_name: str) -> str | None:
    if value is None or isinstance(value, str):
        return value
    raise ValueError(f"invalid state field {field_name}: expected a string or null")


def _optional_integer(value: object, *, field_name: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"invalid state field {field_name}: expected an integer or null")
    return value


def _issue_state_from_mapping(data: dict[str, object], *, field_prefix: str) -> IssueState:
    return IssueState(
        last_notice=_optional_string(data.get("last_notice"), field_name="last_notice"),
        pr_search_done=bool(data.get("pr_search_done", False)),
        run_failed=bool(data.get("run_failed", False)),
        branch=_optional_string(data.get("branch"), field_name=f"{field_prefix}.branch"),
        pr=_optional_integer(data.get("pr"), field_name=f"{field_prefix}.pr"),
        trusted_issue_body=_optional_string(
            data.get("trusted_issue_body"),
            field_name=f"{field_prefix}.trusted_issue_body",
        ),
        last_seen_issue_updated_at=_optional_string(
            data.get("last_seen_issue_updated_at"),
            field_name=f"{field_prefix}.last_seen_issue_updated_at",
        ),
        last_seen_pr_updated_at=_optional_string(
            data.get("last_seen_pr_updated_at"),
            field_name=f"{field_prefix}.last_seen_pr_updated_at",
        ),
        last_seen_default_branch_sha=_optional_string(
            data.get("last_seen_default_branch_sha"),
            field_name=f"{field_prefix}.last_seen_default_branch_sha",
        ),
        last_seen_allowed_issue_digest=_optional_string(
            data.get("last_seen_allowed_issue_digest"),
            field_name=f"{field_prefix}.last_seen_allowed_issue_digest",
        ),
        last_seen_allowed_pr_digest=_optional_string(
            data.get("last_seen_allowed_pr_digest"),
            field_name=f"{field_prefix}.last_seen_allowed_pr_digest",
        ),
    )


def load_repo_state(path: Path) -> RepoState:
    if not path.exists():
        return RepoState()
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("invalid state: expected a JSON object")

    # Legacy schema: single active issue.
    if "issues" not in data:
        issue_number = data.get("active_issue")
        if issue_number is None:
            return RepoState()
        try:
            issue_number_int = int(issue_number)
        except (TypeError, ValueError):
            raise ValueError("invalid legacy state field active_issue: expected an integer") from None
        if issue_number_int <= 0:
            raise ValueError("invalid legacy state field active_issue: expected a positive integer")

        return RepoState(
            issues={
                issue_number_int: _issue_state_from_mapping(
                    {
                        "branch": data.get("active_branch"),
                        "pr": data.get("active_pr"),
                        "trusted_issue_body": data.get("trusted_issue_body"),
                        "last_seen_issue_updated_at": data.get("last_seen_issue_updated_at"),
                        "last_seen_pr_updated_at": data.get("last_seen_pr_updated_at"),
                        "last_seen_default_branch_sha": data.get("last_seen_default_branch_sha"),
                        "last_seen_allowed_issue_digest": data.get("last_seen_allowed_issue_digest"),
                        "last_seen_allowed_pr_digest": data.get("last_seen_allowed_pr_digest"),
                    },
                    field_prefix="legacy",
                )
            }
        )

    raw_issues = data.get("issues")
    if not isinstance(raw_issues, dict):
        raise ValueError("invalid state field issues: expected an object")

    issues: dict[int, IssueState] = {}
    for key, value in raw_issues.items():
        try:
            issue_number = int(key)
        except (TypeError, ValueError):
            raise ValueError(f"invalid state issue key {key!r}: expected an integer") from None
        if issue_number <= 0:
            raise ValueError(f"invalid state issue key {key!r}: expected a positive integer")
        if not isinstance(value, dict):
            raise ValueError(f"invalid state field issues.{key}: expected an object")
        issues[issue_number] = _issue_state_from_mapping(
            value,
            field_prefix=f"issues.{key}",
        )

    return RepoState(issues=issues)


def save_repo_state(path: Path, state: RepoState) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "issues": {str(k): asdict(v) for k, v in sorted(state.issues.items(), key=lambda it: it[0])},
    }
    serialized = json.dumps(data, indent=2, sort_keys=True) + "\n"
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temp_file:
            temp_path = Path(temp_file.name)
            temp_file.write(serialized)
            temp_file.flush()
            os.fsync(temp_file.fileno())
        temp_path.replace(path)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
