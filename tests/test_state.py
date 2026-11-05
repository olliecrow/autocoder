from __future__ import annotations

import json
from pathlib import Path

import pytest

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


def test_state_rejects_legacy_schema(tmp_path):
    path = tmp_path / "state.json"
    path.write_text('{"active_issue":123}')
    with pytest.raises(ValueError, match="unsupported state schema"):
        load_repo_state(path)


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ([], "expected a JSON object"),
        ({"issues": []}, "field issues"),
        ({"issues": {"bad": {}}}, "issue key"),
        ({"issues": {"1": []}}, "issues.1"),
        ({"issues": {"1": {"branch": 3}}}, "issues.1.branch"),
        ({"issues": {"1": {"pr": "3"}}}, "issues.1.pr"),
    ],
)
def test_state_rejects_invalid_shapes(tmp_path: Path, payload: object, message: str) -> None:
    path = tmp_path / "state.json"
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        load_repo_state(path)


def test_state_save_failure_preserves_previous_file(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "state.json"
    path.write_text('{"issues": {}}\n', encoding="utf-8")

    def fail_replace(self: Path, target: Path) -> Path:
        raise OSError("replace failed")

    monkeypatch.setattr(Path, "replace", fail_replace)

    with pytest.raises(OSError, match="replace failed"):
        save_repo_state(path, RepoState(issues={1: IssueState(branch="autocoder/issue-1-test")}))

    assert path.read_text(encoding="utf-8") == '{"issues": {}}\n'
    assert list(tmp_path.glob(".state.json.*.tmp")) == []
