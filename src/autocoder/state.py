from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path


@dataclass
class IssueState:
    branch: str | None = None
    pr: int | None = None
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


def load_repo_state(path: Path) -> RepoState:
    if not path.exists():
        return RepoState()
    data = json.loads(path.read_text(encoding="utf-8"))

    # Legacy schema: single active issue.
    if "issues" not in data:
        issue_number = data.get("active_issue")
        if issue_number is None:
            return RepoState()
        try:
            issue_number_int = int(issue_number)
        except (TypeError, ValueError):
            return RepoState()

        return RepoState(
            issues={
                issue_number_int: IssueState(
                    branch=data.get("active_branch"),
                    pr=data.get("active_pr"),
                    last_seen_issue_updated_at=data.get("last_seen_issue_updated_at"),
                    last_seen_pr_updated_at=data.get("last_seen_pr_updated_at"),
                    last_seen_default_branch_sha=data.get("last_seen_default_branch_sha"),
                    last_seen_allowed_issue_digest=data.get("last_seen_allowed_issue_digest"),
                    last_seen_allowed_pr_digest=data.get("last_seen_allowed_pr_digest"),
                )
            }
        )

    raw_issues = data.get("issues") or {}
    issues: dict[int, IssueState] = {}
    if isinstance(raw_issues, dict):
        for k, v in raw_issues.items():
            try:
                issue_number_int = int(k)
            except (TypeError, ValueError):
                continue
            if not isinstance(v, dict):
                continue
            issues[issue_number_int] = IssueState(
                branch=v.get("branch"),
                pr=v.get("pr"),
                last_seen_issue_updated_at=v.get("last_seen_issue_updated_at"),
                last_seen_pr_updated_at=v.get("last_seen_pr_updated_at"),
                last_seen_default_branch_sha=v.get("last_seen_default_branch_sha"),
                last_seen_allowed_issue_digest=v.get("last_seen_allowed_issue_digest"),
                last_seen_allowed_pr_digest=v.get("last_seen_allowed_pr_digest"),
            )

    return RepoState(issues=issues)


def save_repo_state(path: Path, state: RepoState) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "issues": {str(k): asdict(v) for k, v in sorted(state.issues.items(), key=lambda it: it[0])},
    }
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
