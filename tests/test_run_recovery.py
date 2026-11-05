from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import autocoder.run as runmod
from autocoder.gh import IssueComment, IssueDetail
from autocoder.security import issue_allowed_human_activity_digest
from autocoder.state import IssueState, RepoState

ALLOWED = ("trusted-user",)


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
        author="trusted-user",
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
        cfg=SimpleNamespace(mentions=(), allowed_github_logins=ALLOWED),
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
        author="trusted-user",
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
        cfg=SimpleNamespace(mentions=(), allowed_github_logins=ALLOWED),
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


def test_run_one_iteration_skips_codex_for_later_issue_body_edit_only(tmp_path: Path, monkeypatch) -> None:
    issue = IssueDetail(
        number=1,
        title="t",
        url="https://example.test/issues/1",
        state="OPEN",
        updated_at="2026-02-13T00:10:00Z",
        author="trusted-user",
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
        cfg=SimpleNamespace(mentions=(), allowed_github_logins=ALLOWED),
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
                trusted_issue_body="initial body snapshot",
                last_seen_issue_updated_at="2026-02-13T00:00:00Z",
                last_seen_pr_updated_at=None,
                last_seen_default_branch_sha=default_sha,
                last_seen_allowed_issue_digest=issue_allowed_human_activity_digest(
                    issue_author="trusted-user",
                    allowed_logins=ALLOWED,
                    comments=[],
                    trusted_issue_body="initial body snapshot",
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


def test_run_one_iteration_triggers_codex_for_initial_issue_body_snapshot_only(
    tmp_path: Path,
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    issue = IssueDetail(
        number=1,
        title="t",
        url="https://example.test/issues/1",
        state="OPEN",
        updated_at="2026-02-13T00:10:00Z",
        author="trusted-user",
        body="initial trusted body",
        labels=("autocoder", "autocoder:claimed"),
        comments=(),
    )
    branch = "autocoder/issue-1-test"
    default_sha = "abc123"
    git = _GitStub(default_sha=default_sha, branch=branch, dirty_status="")
    gh = _GhStub(issue=issue)

    rt = SimpleNamespace(
        repo=SimpleNamespace(owner="owner", name="repo", full_name="owner/repo"),
        cfg=SimpleNamespace(mentions=(), allowed_github_logins=ALLOWED),
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
                last_seen_issue_updated_at=None,
                last_seen_pr_updated_at=None,
                last_seen_default_branch_sha=default_sha,
                last_seen_allowed_issue_digest=None,
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
    assert state.issues[1].trusted_issue_body == "initial trusted body"


def test_run_one_iteration_skips_codex_for_issue_author_comment_edit_only(tmp_path: Path, monkeypatch) -> None:
    comments_before = (
        IssueComment(
            id="c1",
            author="trusted-user",
            body="initial instruction",
            created_at="2026-02-13T00:00:00Z",
            updated_at="2026-02-13T00:00:00Z",
            url="https://example.test/issues/1#issuecomment-c1",
        ),
    )
    comments_after = (
        IssueComment(
            id="c1",
            author="trusted-user",
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
        author="trusted-user",
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
        cfg=SimpleNamespace(mentions=(), allowed_github_logins=ALLOWED),
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
                    issue_author="trusted-user",
                    allowed_logins=ALLOWED,
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
            author="trusted-user",
            body="first instruction",
            created_at="2026-02-13T00:00:00Z",
            updated_at="2026-02-13T00:00:00Z",
            url="https://example.test/issues/1#issuecomment-c1",
        ),
    )
    comments_after = (
        IssueComment(
            id="c1",
            author="trusted-user",
            body="first instruction",
            created_at="2026-02-13T00:00:00Z",
            updated_at="2026-02-13T00:00:00Z",
            url="https://example.test/issues/1#issuecomment-c1",
        ),
        IssueComment(
            id="c2",
            author="trusted-user",
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
        author="trusted-user",
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
        author="trusted-user",
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
        cfg=SimpleNamespace(mentions=(), allowed_github_logins=ALLOWED),
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
                    issue_author="trusted-user",
                    allowed_logins=ALLOWED,
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
        issue_author="trusted-user",
        allowed_logins=ALLOWED,
        comments=[(c.id, c.author, c.updated_at, c.body) for c in comments_after],
    )


def test_post_codex_failure_requires_new_author_input(tmp_path, monkeypatch):
    from dataclasses import replace
    issue = IssueDetail(1, 't', 'https://example.test/issues/1', 'OPEN', 'now',
                        'trusted-user', '', ('autocoder', 'autocoder:claimed'), ())
    branch = 'autocoder/issue-1-test'
    gh = _GhStub(issue=issue)
    labels = []
    gh.issue_add_labels = lambda **kwargs: labels.extend(kwargs['labels'])
    git = _GitStub(default_sha='base', branch=branch, dirty_status=' M file')
    git.is_ancestor = lambda **kwargs: True
    rt = SimpleNamespace(repo=SimpleNamespace(owner='owner', name='repo', full_name='owner/repo'),
                         cfg=SimpleNamespace(allowed_github_logins=ALLOWED, mentions=()),
                         managed_dir=tmp_path, default_branch='main', gh=gh, git=git)
    state = RepoState(issues={1: IssueState(branch=branch)})
    worktree = tmp_path / 'worktree'
    worktree.mkdir()
    monkeypatch.setattr(runmod, 'issue_worktree_dir', lambda *args: worktree)
    calls = []
    def fail(**kwargs):
        calls.append(1)
        raise RuntimeError('push rejected')
    monkeypatch.setattr(runmod, '_maybe_run_codex', fail)
    for _ in range(3):
        runmod._run_one_iteration(rt=rt, state=state)
    assert calls == [1]
    assert len(gh.issue_comments) == 1
    assert labels == ['autocoder:needs-info']
    comment = IssueComment('new', 'trusted-user', 'retrigger', 'later', 'later', '')
    gh._issue = replace(issue, updated_at='later', comments=(comment,))
    runmod._run_one_iteration(rt=rt, state=state)
    assert calls == [1, 1]


def test_foreign_latest_claim_stops_before_codex(tmp_path, monkeypatch):
    body = '[autocoder]\n\ninstance: 12345678-1234-1234-1234-123456789abc\nbranch: autocoder/issue-1-test'
    comment = IssueComment('claim', 'trusted-user', body, 'now', 'now', '')
    issue = IssueDetail(1, 't', '', 'OPEN', 'now', 'trusted-user', '',
                        ('autocoder', 'autocoder:claimed'), (comment,))
    gh = _GhStub(issue=issue)
    git = _GitStub(default_sha='base', branch='autocoder/issue-1-test', dirty_status='')
    rt = SimpleNamespace(repo=SimpleNamespace(owner='owner', name='repo', full_name='owner/repo'),
                         cfg=SimpleNamespace(allowed_github_logins=ALLOWED, mentions=()),
                         instance_id='aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee',
                         managed_dir=tmp_path, default_branch='main', gh=gh, git=git)
    state = RepoState(issues={1: IssueState(branch='autocoder/issue-1-test', last_seen_default_branch_sha='base')})
    monkeypatch.setattr(runmod, '_maybe_run_codex', lambda **kwargs: (_ for _ in ()).throw(AssertionError('must not run')))
    monkeypatch.setattr(runmod, '_cleanup_local', lambda **kwargs: None)
    runmod._run_one_iteration(rt=rt, state=state)
    assert state.issues == {}
    assert gh.issue_comments == []


def test_closed_pr_posts_one_notice_over_three_polls(tmp_path):
    from autocoder.gh import PullRequestDetail
    issue = IssueDetail(1, 't', '', 'OPEN', 'now', 'trusted-user', '', ('autocoder', 'autocoder:claimed'), ())
    branch = 'autocoder/issue-1-test'
    pr = PullRequestDetail(7, 't', '', 'CLOSED', 'now', 'trusted-user', branch, 'main', False, None, '', (), ())
    gh = _GhStub(issue=issue)
    gh.view_pr = lambda **kwargs: pr
    git = _GitStub(default_sha='base', branch=branch, dirty_status='')
    rt = SimpleNamespace(repo=SimpleNamespace(owner='owner', name='repo', full_name='owner/repo'),
                         cfg=SimpleNamespace(allowed_github_logins=ALLOWED, mentions=()),
                         managed_dir=tmp_path, default_branch='main', gh=gh, git=git)
    state = RepoState(issues={1: IssueState(branch=branch, pr=7)})
    for _ in range(3):
        runmod._run_one_iteration(rt=rt, state=state)
    assert len(gh.issue_comments) == 1
    assert 'not merged' in gh.issue_comments[0][1]
