from __future__ import annotations

import json
from pathlib import Path

from autocoder.state import IssueState, RepoState, load_repo_state, save_repo_state


def test_state_roundtrip(tmp_path: Path) -> None:
    p = tmp_path / "state.json"
    s = RepoState(
        issues={
            123: IssueState(
                branch="autocoder/issue-123-test",
                pr=456,
                last_seen_issue_updated_at="2020-01-01T00:00:00Z",
                last_seen_pr_updated_at="2020-01-02T00:00:00Z",
                last_seen_default_branch_sha="abc999",
                last_seen_allowed_issue_digest="abc123",
                last_seen_allowed_pr_digest="def456",
            ),
            124: IssueState(
                branch="autocoder/issue-124-test",
                pr=None,
                last_seen_issue_updated_at=None,
                last_seen_pr_updated_at=None,
                last_seen_default_branch_sha=None,
                last_seen_allowed_issue_digest=None,
                last_seen_allowed_pr_digest=None,
            ),
        }
    )
    save_repo_state(p, s)
    loaded = load_repo_state(p)
    assert loaded == s


def test_state_missing_file_defaults(tmp_path: Path) -> None:
    p = tmp_path / "missing.json"
    loaded = load_repo_state(p)
    assert loaded == RepoState()


def test_state_migrates_legacy_v1_single_issue(tmp_path: Path) -> None:
    p = tmp_path / "legacy.json"
    legacy = {
        "active_issue": 123,
        "active_branch": "autocoder/issue-123-test",
        "active_pr": 456,
        "last_seen_issue_updated_at": "2020-01-01T00:00:00Z",
        "last_seen_pr_updated_at": "2020-01-02T00:00:00Z",
        "last_seen_default_branch_sha": "abc999",
        "last_seen_allowed_issue_digest": "abc123",
        "last_seen_allowed_pr_digest": "def456",
    }
    p.write_text(json.dumps(legacy) + "\n", encoding="utf-8")

    loaded = load_repo_state(p)
    assert loaded == RepoState(
        issues={
            123: IssueState(
                branch="autocoder/issue-123-test",
                pr=456,
                last_seen_issue_updated_at="2020-01-01T00:00:00Z",
                last_seen_pr_updated_at="2020-01-02T00:00:00Z",
                last_seen_default_branch_sha="abc999",
                last_seen_allowed_issue_digest="abc123",
                last_seen_allowed_pr_digest="def456",
            )
        }
    )
