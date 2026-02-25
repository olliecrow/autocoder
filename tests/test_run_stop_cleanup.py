from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from autocoder.gh import IssueDetail
from autocoder.run import _run_one_iteration
from autocoder.state import IssueState, RepoState


class _GitStub:
    def fetch(self, *, cwd: Path) -> None:
        return None

    def rev_parse(self, *, cwd: Path, rev: str) -> str:
        return "abc123"

    def worktree_prune(self, *, repo_dir: Path) -> None:
        return None

    def delete_local_branch(self, *, cwd: Path, branch: str) -> None:
        return None


class _GhStub:
    def __init__(self, *, issue: IssueDetail) -> None:
        self._issue = issue
        self.removed: list[tuple[int, tuple[str, ...]]] = []

    def list_open_issues(self, *, label: str, limit: int = 100):  # type: ignore[no-untyped-def]
        return []

    def view_issue(self, *, number: int, include_comments: bool = False) -> IssueDetail:
        assert number == self._issue.number
        assert include_comments is False
        return self._issue

    def issue_remove_labels(self, *, number: int, labels):  # type: ignore[no-untyped-def]
        self.removed.append((number, tuple(labels)))


def test_run_one_iteration_removes_lock_labels_when_autocoder_label_removed(tmp_path: Path) -> None:
    issue = IssueDetail(
        number=1,
        title="t",
        url="https://example.test/issues/1",
        state="OPEN",
        updated_at="2026-02-13T00:00:00Z",
        author="olliecrow",
        body="",
        labels=("autocoder:claimed", "autocoder:needs-info"),
        comments=(),
    )
    gh = _GhStub(issue=issue)
    git = _GitStub()

    rt = SimpleNamespace(
        repo=SimpleNamespace(owner="owner", name="repo", full_name="owner/repo"),
        cfg=SimpleNamespace(mentions=()),
        default_branch="main",
        managed_dir=tmp_path / "managed",
        git=git,
        gh=gh,
    )

    state = RepoState(issues={1: IssueState(branch="autocoder/issue-1-test", pr=None)})

    _run_one_iteration(rt=rt, state=state)

    assert state.issues == {}
    assert gh.removed == [(1, ("autocoder:claimed", "autocoder:needs-info"))]


def test_run_one_iteration_removes_lock_labels_when_issue_author_not_allowlisted(tmp_path: Path) -> None:
    issue = IssueDetail(
        number=1,
        title="t",
        url="https://example.test/issues/1",
        state="OPEN",
        updated_at="2026-02-13T00:00:00Z",
        author="someoneelse",
        body="",
        labels=("autocoder", "autocoder:claimed", "autocoder:needs-info"),
        comments=(),
    )
    gh = _GhStub(issue=issue)
    git = _GitStub()

    rt = SimpleNamespace(
        repo=SimpleNamespace(owner="owner", name="repo", full_name="owner/repo"),
        cfg=SimpleNamespace(mentions=()),
        default_branch="main",
        managed_dir=tmp_path / "managed",
        git=git,
        gh=gh,
    )

    state = RepoState(issues={1: IssueState(branch="autocoder/issue-1-test", pr=None)})

    _run_one_iteration(rt=rt, state=state)

    assert state.issues == {}
    assert gh.removed == [(1, ("autocoder:claimed", "autocoder:needs-info"))]
