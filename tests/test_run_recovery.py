from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from autocoder.gh import IssueComment, IssueDetail
import autocoder.run as runmod
from autocoder.security import issue_allowed_human_activity_digest
from autocoder.state import IssueState, RepoState


class _GitStub:
    def __init__(self, *, default_sha: str, branch: str, dirty_status: str) -> None:
        self._default_sha = default_sha
        self._branch = branch
        self._dirty_status = dirty_status

    def fetch(self, *, cwd: Path) -> None:
        return None

    def rev_parse(self, *, cwd: Path, rev: str) -> str:
        if rev.startswith("origin/"):
            return self._default_sha
        if rev == "HEAD":
            return "head123"
        return self._default_sha

    def branch_exists(self, *, cwd: Path, branch: str) -> bool:
        return branch == self._branch

    def remote_branch_exists(self, *, cwd: Path, remote: str, branch: str) -> bool:
        return branch == self._branch

    def has_in_progress_operation(self, *, cwd: Path) -> bool:
        return False

    def status_porcelain(self, *, cwd: Path) -> str:
        return self._dirty_status

    def current_branch(self, *, cwd: Path) -> str:
        return self._branch


class _GhStub:
    def __init__(self, *, issue: IssueDetail) -> None:
        self._issue = issue
        self.issue_comments: list[tuple[int, str]] = []

    def list_open_issues(self, *, label: str, limit: int = 100):  # type: ignore[no-untyped-def]
        return []

    def view_issue(self, *, number: int, include_comments: bool = False) -> IssueDetail:
        assert number == self._issue.number
        return self._issue

    def list_prs(self, *, state: str = "all", head: str | None = None, limit: int = 5):  # type: ignore[no-untyped-def]
        return []

    def search_open_prs_by_body_snippet(self, *, query: str, limit: int = 5):  # type: ignore[no-untyped-def]
        return []

    def issue_comment(self, *, number: int, body: str) -> None:
        self.issue_comments.append((number, body))


def test_run_one_iteration_triggers_codex_for_local_recovery(tmp_path: Path, monkeypatch) -> None:
    issue = IssueDetail(
        number=1,
        title="t",
        url="https://example.test/issues/1",
        state="OPEN",
        updated_at="2026-02-13T00:00:00Z",
        author="olliecrow",
        body="",
        labels=("autocoder", "autocoder:claimed"),
        comments=(),
    )
    branch = "autocoder/issue-1-test"
    default_sha = "abc123"
    git = _GitStub(default_sha=default_sha, branch=branch, dirty_status=" M src/file.py")
    gh = _GhStub(issue=issue)

    rt = SimpleNamespace(
        repo=SimpleNamespace(owner="owner", name="repo", full_name="owner/repo"),
        cfg=SimpleNamespace(mentions=()),
        default_branch="main",
        managed_dir=tmp_path / "managed",
        git=git,
        gh=gh,
    )

    state = RepoState(
        issues={
            1: IssueState(
                branch=branch,
                pr=None,
                last_seen_issue_updated_at=issue.updated_at,
                last_seen_pr_updated_at=None,
                last_seen_default_branch_sha=default_sha,
                last_seen_allowed_issue_digest="issue-digest",
                last_seen_allowed_pr_digest=None,
            )
        }
    )

    worktree_dir = tmp_path / "worktrees" / "issue-1"
    worktree_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(runmod, "issue_worktree_dir", lambda repo, issue_number: worktree_dir)

    seen_triggers: list[tuple[str, ...]] = []

    def _fake_maybe_run_codex(**kwargs):  # type: ignore[no-untyped-def]
        seen_triggers.append(kwargs["trigger_reasons"])

    monkeypatch.setattr(runmod, "_maybe_run_codex", _fake_maybe_run_codex)

    runmod._run_one_iteration(rt=rt, state=state)

    assert seen_triggers == [("local_recovery_needed",)]
    assert gh.issue_comments == []


def test_run_one_iteration_posts_quick_ack_for_issue_author_update(tmp_path: Path, monkeypatch) -> None:
    issue = IssueDetail(
        number=1,
        title="t",
        url="https://example.test/issues/1",
        state="OPEN",
        updated_at="2026-02-13T00:10:00Z",
        author="olliecrow",
        body="please update behavior",
        labels=("autocoder", "autocoder:claimed"),
        comments=(),
    )
    branch = "autocoder/issue-1-test"
    default_sha = "abc123"
    git = _GitStub(default_sha=default_sha, branch=branch, dirty_status="")
    gh = _GhStub(issue=issue)

    rt = SimpleNamespace(
        repo=SimpleNamespace(owner="owner", name="repo", full_name="owner/repo"),
        cfg=SimpleNamespace(mentions=()),
        default_branch="main",
        managed_dir=tmp_path / "managed",
        git=git,
        gh=gh,
    )

    state = RepoState(
        issues={
            1: IssueState(
                branch=branch,
                pr=None,
                last_seen_issue_updated_at="2026-02-13T00:00:00Z",
                last_seen_pr_updated_at=None,
                last_seen_default_branch_sha=default_sha,
                last_seen_allowed_issue_digest="old-digest",
                last_seen_allowed_pr_digest=None,
            )
        }
    )

    worktree_dir = tmp_path / "worktrees" / "issue-1"
    worktree_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(runmod, "issue_worktree_dir", lambda repo, issue_number: worktree_dir)
    monkeypatch.setattr(runmod, "_ensure_worktree", lambda **kwargs: worktree_dir)

    seen_triggers: list[tuple[str, ...]] = []

    def _fake_maybe_run_codex(**kwargs):  # type: ignore[no-untyped-def]
        seen_triggers.append(kwargs["trigger_reasons"])

    monkeypatch.setattr(runmod, "_maybe_run_codex", _fake_maybe_run_codex)

    runmod._run_one_iteration(rt=rt, state=state)

    assert seen_triggers == [("issue_updated",)]
    assert len(gh.issue_comments) == 1
    assert ":eyes: update received. reviewing now." in gh.issue_comments[0][1]


def test_run_one_iteration_skips_codex_for_issue_body_only_change(tmp_path: Path, monkeypatch) -> None:
    issue = IssueDetail(
        number=1,
        title="t",
        url="https://example.test/issues/1",
        state="OPEN",
        updated_at="2026-02-13T00:10:00Z",
        author="olliecrow",
        body="edited body only",
        labels=("autocoder", "autocoder:claimed"),
        comments=(),
    )
    branch = "autocoder/issue-1-test"
    default_sha = "abc123"
    git = _GitStub(default_sha=default_sha, branch=branch, dirty_status="")
    gh = _GhStub(issue=issue)

    rt = SimpleNamespace(
        repo=SimpleNamespace(owner="owner", name="repo", full_name="owner/repo"),
        cfg=SimpleNamespace(mentions=()),
        default_branch="main",
        managed_dir=tmp_path / "managed",
        git=git,
        gh=gh,
    )

    state = RepoState(
        issues={
            1: IssueState(
                branch=branch,
                pr=None,
                last_seen_issue_updated_at="2026-02-13T00:00:00Z",
                last_seen_pr_updated_at=None,
                last_seen_default_branch_sha=default_sha,
                last_seen_allowed_issue_digest=issue_allowed_human_activity_digest(
                    issue_author="olliecrow",
                    comments=[],
                ),
                last_seen_allowed_pr_digest=None,
            )
        }
    )

    worktree_dir = tmp_path / "worktrees" / "issue-1"
    worktree_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(runmod, "issue_worktree_dir", lambda repo, issue_number: worktree_dir)

    seen_triggers: list[tuple[str, ...]] = []

    def _fake_maybe_run_codex(**kwargs):  # type: ignore[no-untyped-def]
        seen_triggers.append(kwargs["trigger_reasons"])

    monkeypatch.setattr(runmod, "_maybe_run_codex", _fake_maybe_run_codex)

    runmod._run_one_iteration(rt=rt, state=state)

    assert seen_triggers == []
    assert gh.issue_comments == []


def test_run_one_iteration_skips_codex_for_issue_author_comment_edit_only(tmp_path: Path, monkeypatch) -> None:
    comments_before = (
        IssueComment(
            id="c1",
            author="olliecrow",
            body="initial instruction",
            created_at="2026-02-13T00:00:00Z",
            updated_at="2026-02-13T00:00:00Z",
            url="https://example.test/issues/1#issuecomment-c1",
        ),
    )
    comments_after = (
        IssueComment(
            id="c1",
            author="olliecrow",
            body="edited instruction text",
            created_at="2026-02-13T00:00:00Z",
            updated_at="2026-02-13T00:10:00Z",
            url="https://example.test/issues/1#issuecomment-c1",
        ),
    )
    issue = IssueDetail(
        number=1,
        title="t",
        url="https://example.test/issues/1",
        state="OPEN",
        updated_at="2026-02-13T00:10:00Z",
        author="olliecrow",
        body="",
        labels=("autocoder", "autocoder:claimed"),
        comments=comments_after,
    )
    branch = "autocoder/issue-1-test"
    default_sha = "abc123"
    git = _GitStub(default_sha=default_sha, branch=branch, dirty_status="")
    gh = _GhStub(issue=issue)

    rt = SimpleNamespace(
        repo=SimpleNamespace(owner="owner", name="repo", full_name="owner/repo"),
        cfg=SimpleNamespace(mentions=()),
        default_branch="main",
        managed_dir=tmp_path / "managed",
        git=git,
        gh=gh,
    )

    state = RepoState(
        issues={
            1: IssueState(
                branch=branch,
                pr=None,
                last_seen_issue_updated_at="2026-02-13T00:00:00Z",
                last_seen_pr_updated_at=None,
                last_seen_default_branch_sha=default_sha,
                last_seen_allowed_issue_digest=issue_allowed_human_activity_digest(
                    issue_author="olliecrow",
                    comments=[(c.id, c.author, c.updated_at, c.body) for c in comments_before],
                ),
                last_seen_allowed_pr_digest=None,
            )
        }
    )

    worktree_dir = tmp_path / "worktrees" / "issue-1"
    worktree_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(runmod, "issue_worktree_dir", lambda repo, issue_number: worktree_dir)

    seen_triggers: list[tuple[str, ...]] = []

    def _fake_maybe_run_codex(**kwargs):  # type: ignore[no-untyped-def]
        seen_triggers.append(kwargs["trigger_reasons"])

    monkeypatch.setattr(runmod, "_maybe_run_codex", _fake_maybe_run_codex)

    runmod._run_one_iteration(rt=rt, state=state)

    assert seen_triggers == []
    assert gh.issue_comments == []


def test_run_one_iteration_retries_when_issue_author_comment_arrives_during_codex_run(
    tmp_path: Path,
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    comments_before = (
        IssueComment(
            id="c1",
            author="olliecrow",
            body="first instruction",
            created_at="2026-02-13T00:00:00Z",
            updated_at="2026-02-13T00:00:00Z",
            url="https://example.test/issues/1#issuecomment-c1",
        ),
    )
    comments_after = (
        IssueComment(
            id="c1",
            author="olliecrow",
            body="first instruction",
            created_at="2026-02-13T00:00:00Z",
            updated_at="2026-02-13T00:00:00Z",
            url="https://example.test/issues/1#issuecomment-c1",
        ),
        IssueComment(
            id="c2",
            author="olliecrow",
            body="second instruction during run",
            created_at="2026-02-13T00:01:00Z",
            updated_at="2026-02-13T00:01:00Z",
            url="https://example.test/issues/1#issuecomment-c2",
        ),
    )
    issue_before = IssueDetail(
        number=1,
        title="t",
        url="https://example.test/issues/1",
        state="OPEN",
        updated_at="2026-02-13T00:00:00Z",
        author="olliecrow",
        body="",
        labels=("autocoder", "autocoder:claimed"),
        comments=comments_before,
    )
    issue_after = IssueDetail(
        number=1,
        title="t",
        url="https://example.test/issues/1",
        state="OPEN",
        updated_at="2026-02-13T00:01:00Z",
        author="olliecrow",
        body="",
        labels=("autocoder", "autocoder:claimed"),
        comments=comments_after,
    )

    class _GhMidRunStub:
        def __init__(self) -> None:
            self._use_after = False
            self.issue_comments: list[tuple[int, str]] = []

        def list_open_issues(self, *, label: str, limit: int = 100):  # type: ignore[no-untyped-def]
            return []

        def view_issue(self, *, number: int, include_comments: bool = False) -> IssueDetail:
            assert number == 1
            return issue_after if self._use_after else issue_before

        def list_prs(self, *, state: str = "all", head: str | None = None, limit: int = 5):  # type: ignore[no-untyped-def]
            return []

        def search_open_prs_by_body_snippet(self, *, query: str, limit: int = 5):  # type: ignore[no-untyped-def]
            return []

        def issue_comment(self, *, number: int, body: str) -> None:
            self.issue_comments.append((number, body))

    gh = _GhMidRunStub()
    branch = "autocoder/issue-1-test"
    default_sha = "abc123"
    git = _GitStub(default_sha=default_sha, branch=branch, dirty_status="")

    rt = SimpleNamespace(
        repo=SimpleNamespace(owner="owner", name="repo", full_name="owner/repo"),
        cfg=SimpleNamespace(mentions=()),
        default_branch="main",
        managed_dir=tmp_path / "managed",
        git=git,
        gh=gh,
    )

    state = RepoState(
        issues={
            1: IssueState(
                branch=branch,
                pr=None,
                last_seen_issue_updated_at="2026-02-12T23:59:00Z",
                last_seen_pr_updated_at=None,
                last_seen_default_branch_sha=default_sha,
                last_seen_allowed_issue_digest=issue_allowed_human_activity_digest(
                    issue_author="olliecrow",
                    comments=[],
                ),
                last_seen_allowed_pr_digest=None,
            )
        }
    )

    worktree_dir = tmp_path / "worktrees" / "issue-1"
    worktree_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(runmod, "issue_worktree_dir", lambda repo, issue_number: worktree_dir)
    monkeypatch.setattr(runmod, "_ensure_worktree", lambda **kwargs: worktree_dir)

    seen_triggers: list[tuple[str, ...]] = []

    def _fake_maybe_run_codex(**kwargs):  # type: ignore[no-untyped-def]
        seen_triggers.append(kwargs["trigger_reasons"])
        gh._use_after = True

    monkeypatch.setattr(runmod, "_maybe_run_codex", _fake_maybe_run_codex)

    runmod._run_one_iteration(rt=rt, state=state)
    runmod._run_one_iteration(rt=rt, state=state)
    runmod._run_one_iteration(rt=rt, state=state)

    assert seen_triggers == [("issue_updated",), ("issue_updated",)]
    assert state.issues[1].last_seen_issue_updated_at == issue_after.updated_at
    assert state.issues[1].last_seen_allowed_issue_digest == issue_allowed_human_activity_digest(
        issue_author="olliecrow",
        comments=[(c.id, c.author, c.updated_at, c.body) for c in comments_after],
    )
