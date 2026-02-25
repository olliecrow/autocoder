from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from autocoder._runner import CmdResult, CommandError
from autocoder.codex import CodexOutput
from autocoder.gh import (
    IssueComment,
    IssueDetail,
    PullRequestComment,
    PullRequestDetail,
    PullRequestReview,
)
from autocoder.run import (
    _find_or_adopt_pr,
    _issue_author_attachment_urls,
    _maybe_run_codex,
    _prepare_trusted_thread_context,
    _sync_issue_author_attachments,
)
from autocoder.state import IssueState


class _GitStub:
    def __init__(self, *, base_sha: str, head_sha: str) -> None:
        self._base_sha = base_sha
        self._head_sha = head_sha
        self.pushed: list[tuple[str, str]] = []

    def status_porcelain(self, *, cwd: Path) -> str:
        return ""

    def add_all(self, *, cwd: Path) -> None:
        raise AssertionError("unexpected git add in this test")

    def commit(self, *, cwd: Path, message: str) -> None:
        raise AssertionError("unexpected git commit in this test")

    def push(self, *, cwd: Path, branch: str) -> None:
        self.pushed.append((str(cwd), branch))

    def rev_parse(self, *, cwd: Path, rev: str) -> str:
        if rev == "HEAD":
            return self._head_sha
        if rev.startswith("origin/"):
            return self._base_sha
        return self._head_sha


class _GhStub:
    def __init__(self) -> None:
        self.issue_comments: list[tuple[int, str]] = []
        self.created_pr_calls = 0

    def issue_comment(self, *, number: int, body: str) -> None:
        self.issue_comments.append((number, body))

    def issue_remove_labels(self, *, number: int, labels) -> None:  # type: ignore[no-untyped-def]
        return None

    def list_prs(self, *, state: str = "open", head: str | None = None, limit: int = 50):  # type: ignore[no-untyped-def]
        raise AssertionError("unexpected list_prs in this test")

    def create_pr(self, *, title: str, body: str, base: str, head: str):  # type: ignore[no-untyped-def]
        self.created_pr_calls += 1
        raise AssertionError("unexpected create_pr in this test")

    def edit_pr(self, *, number: int, title: str | None = None, body: str | None = None) -> None:
        raise AssertionError("unexpected edit_pr in this test")

    def pr_comment(self, *, number: int, body: str) -> None:
        raise AssertionError("unexpected pr_comment in this test")


class _CodexStub:
    def __init__(self, *, output: CodexOutput) -> None:
        self._output = output

    def run_exec(self, *, workdir: Path, prompt: str, schema_path: Path, output_path: Path) -> CodexOutput:
        return self._output


def test_maybe_run_codex_skips_pr_create_when_branch_matches_default(tmp_path: Path) -> None:
    worktree = tmp_path / "worktree"
    plan_dir = worktree / ".autocoder" / "plan"
    plan_dir.mkdir(parents=True, exist_ok=True)

    base_sha = "abc123"
    head_sha = "abc123"

    git = _GitStub(base_sha=base_sha, head_sha=head_sha)
    gh = _GhStub()
    codex = _CodexStub(
        output=CodexOutput(
            decision="ready",
            issue_comment_markdown="merge sync complete",
            pr_comment_markdown=None,
            pr_title="t",
            pr_body_markdown="b",
            commit_message="m",
            tests_ran=(),
        )
    )

    rt = SimpleNamespace(
        repo=SimpleNamespace(full_name="owner/repo"),
        cfg=SimpleNamespace(mentions=()),
        default_branch="main",
        managed_dir=tmp_path / "managed",
        state_path=tmp_path / "state.json",
        git=git,
        gh=gh,
        codex=codex,
    )

    issue_state = IssueState(branch="autocoder/issue-1-test", pr=None)
    issue = IssueDetail(
        number=1,
        title="t",
        url="https://example.test/issues/1",
        state="OPEN",
        updated_at="2026-02-13T00:00:00Z",
        author="olliecrow",
        body="",
        labels=("autocoder", "autocoder:claimed"),
        comments=(
            IssueComment(
                id="c1",
                author="olliecrow",
                body="implement merge sync",
                created_at="2026-02-13T00:00:00Z",
                updated_at="2026-02-13T00:00:00Z",
                url="https://example.test/issues/1#issuecomment-c1",
            ),
        ),
    )

    _maybe_run_codex(
        rt=rt,
        issue_state=issue_state,
        issue=issue,
        pr=None,
        worktree_dir=worktree,
        trigger_reasons=("default_branch_advanced",),
    )

    assert gh.created_pr_calls == 0
    assert len(gh.issue_comments) == 1
    assert "merge sync complete" in gh.issue_comments[0][1]


class _GhAdoptStub:
    def __init__(self, *, pr: PullRequestDetail) -> None:
        self._pr = pr
        self.issue_comments: list[tuple[int, str]] = []

    def view_pr(self, *, number: int, include_comments: bool = False) -> PullRequestDetail:
        assert number == self._pr.number
        assert include_comments is False
        return self._pr

    def issue_comment(self, *, number: int, body: str) -> None:
        self.issue_comments.append((number, body))

    def list_prs(self, *, state: str = "open", head: str | None = None, limit: int = 50):  # type: ignore[no-untyped-def]
        raise AssertionError("unexpected list_prs in this test")

    def search_open_prs_by_body_snippet(self, *, query: str, limit: int = 50):  # type: ignore[no-untyped-def]
        raise AssertionError("unexpected search_open_prs_by_body_snippet in this test")


def test_find_or_adopt_pr_rejects_non_allowlisted_pr_author() -> None:
    pr = PullRequestDetail(
        number=123,
        title="t",
        url="https://example.test/pr/123",
        state="OPEN",
        updated_at="2026-02-13T00:00:00Z",
        author="someoneelse",
        head_ref_name="branch",
        base_ref_name="main",
        is_cross_repository=False,
        merged_at=None,
        body="",
        comments=(),
        reviews=(),
    )
    gh = _GhAdoptStub(pr=pr)
    rt = SimpleNamespace(gh=gh)
    issue_state = IssueState(branch="autocoder/issue-1-test", pr=123)

    adopted = _find_or_adopt_pr(rt=rt, issue_state=issue_state, issue_number=1, issue_author="olliecrow")

    assert adopted is None
    assert issue_state.pr is None
    assert issue_state.branch == "autocoder/issue-1-test"
    assert len(gh.issue_comments) == 1
    assert "not allowlisted" in gh.issue_comments[0][1]


def test_find_or_adopt_pr_rejects_cross_repository_pr() -> None:
    pr = PullRequestDetail(
        number=123,
        title="t",
        url="https://example.test/pr/123",
        state="OPEN",
        updated_at="2026-02-13T00:00:00Z",
        author="olliecrow",
        head_ref_name="branch",
        base_ref_name="main",
        is_cross_repository=True,
        merged_at=None,
        body="",
        comments=(),
        reviews=(),
    )
    gh = _GhAdoptStub(pr=pr)
    rt = SimpleNamespace(gh=gh)
    issue_state = IssueState(branch="autocoder/issue-1-test", pr=123)

    adopted = _find_or_adopt_pr(rt=rt, issue_state=issue_state, issue_number=1, issue_author="olliecrow")

    assert adopted is None
    assert issue_state.pr is None
    assert len(gh.issue_comments) == 1
    assert "cross-repository" in gh.issue_comments[0][1]


def test_find_or_adopt_pr_rejects_pr_author_mismatch_with_issue_author() -> None:
    pr = PullRequestDetail(
        number=123,
        title="t",
        url="https://example.test/pr/123",
        state="OPEN",
        updated_at="2026-02-13T00:00:00Z",
        author="olliecrow",
        head_ref_name="branch",
        base_ref_name="main",
        is_cross_repository=False,
        merged_at=None,
        body="",
        comments=(),
        reviews=(),
    )
    gh = _GhAdoptStub(pr=pr)
    rt = SimpleNamespace(gh=gh)
    issue_state = IssueState(branch="autocoder/issue-1-test", pr=123)

    adopted = _find_or_adopt_pr(
        rt=rt,
        issue_state=issue_state,
        issue_number=1,
        issue_author="different-user",
    )

    assert adopted is None
    assert issue_state.pr is None
    assert len(gh.issue_comments) == 1
    assert "does not match issue author" in gh.issue_comments[0][1]


def test_issue_author_attachment_urls_filters_to_issue_author_only() -> None:
    issue = IssueDetail(
        number=1,
        title="t",
        url="https://example.test/issues/1",
        state="OPEN",
        updated_at="2026-02-13T00:00:00Z",
        author="olliecrow",
        body="body https://example.com/body.png",
        labels=("autocoder",),
        comments=(
            IssueComment(
                id="c1",
                author="olliecrow",
                body="allowed https://example.com/issue-author-comment.png",
                created_at="2026-02-13T00:00:00Z",
                updated_at="2026-02-13T00:00:00Z",
                url="https://example.test/issues/1#issuecomment-1",
            ),
            IssueComment(
                id="c2",
                author="other",
                body="blocked https://example.com/other-comment.png",
                created_at="2026-02-13T00:00:00Z",
                updated_at="2026-02-13T00:00:00Z",
                url="https://example.test/issues/1#issuecomment-2",
            ),
            IssueComment(
                id="c3",
                author="olliecrow",
                body="[autocoder]\nhttps://example.com/bot-comment.png",
                created_at="2026-02-13T00:00:00Z",
                updated_at="2026-02-13T00:00:00Z",
                url="https://example.test/issues/1#issuecomment-3",
            ),
        ),
    )
    pr = PullRequestDetail(
        number=2,
        title="t",
        url="https://example.test/pr/2",
        state="OPEN",
        updated_at="2026-02-13T00:00:00Z",
        author="olliecrow",
        head_ref_name="autocoder/issue-1-test",
        base_ref_name="main",
        is_cross_repository=False,
        merged_at=None,
        body="",
        comments=(
            PullRequestComment(
                id="pc1",
                author="olliecrow",
                body="allowed https://example.com/pr-comment.png",
                created_at="2026-02-13T00:00:00Z",
                updated_at="2026-02-13T00:00:00Z",
                url="https://example.test/pr/2#issuecomment-1",
            ),
            PullRequestComment(
                id="pc2",
                author="other",
                body="blocked https://example.com/other-pr-comment.png",
                created_at="2026-02-13T00:00:00Z",
                updated_at="2026-02-13T00:00:00Z",
                url="https://example.test/pr/2#issuecomment-2",
            ),
        ),
        reviews=(
            PullRequestReview(
                id="r1",
                author="olliecrow",
                body="allowed https://example.com/pr-review.png",
                submitted_at="2026-02-13T00:00:00Z",
                state="COMMENTED",
            ),
            PullRequestReview(
                id="r2",
                author="other",
                body="blocked https://example.com/other-pr-review.png",
                submitted_at="2026-02-13T00:00:00Z",
                state="COMMENTED",
            ),
        ),
    )

    urls = _issue_author_attachment_urls(issue=issue, pr=pr)

    assert urls == (
        "https://example.com/issue-author-comment.png",
        "https://example.com/pr-comment.png",
        "https://example.com/pr-review.png",
    )


def test_sync_issue_author_attachments_downloads_once_and_reuses_manifest(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    worktree = tmp_path / "worktree"
    worktree.mkdir(parents=True, exist_ok=True)
    issue = IssueDetail(
        number=1,
        title="t",
        url="https://example.test/issues/1",
        state="OPEN",
        updated_at="2026-02-13T00:00:00Z",
        author="olliecrow",
        body="",
        labels=("autocoder",),
        comments=(
            IssueComment(
                id="c1",
                author="olliecrow",
                body="https://example.com/body.png",
                created_at="2026-02-13T00:00:00Z",
                updated_at="2026-02-13T00:00:00Z",
                url="https://example.test/issues/1#issuecomment-1",
            ),
        ),
    )
    rt = SimpleNamespace(
        repo=SimpleNamespace(host="github.com"),
        gh=SimpleNamespace(),
        runner=SimpleNamespace(),
    )

    calls: list[dict[str, object]] = []

    def _fake_download(**kwargs):  # type: ignore[no-untyped-def]
        calls.append(kwargs)
        dest_dir = kwargs["dest_dir"]
        out_path = dest_dir / "body.png"
        out_path.write_bytes(b"123")
        return SimpleNamespace(
            downloaded=[SimpleNamespace(url="https://example.com/body.png", path=out_path, size_bytes=3)],
            skipped_urls=[],
        )

    monkeypatch.setattr("autocoder.run._github_auth_token", lambda rt: None)
    monkeypatch.setattr("autocoder.run.allowed_attachment_hosts_for_repo_host", lambda host: {"example.com"})
    monkeypatch.setattr("autocoder.run.download_attachments", _fake_download)

    _sync_issue_author_attachments(rt=rt, issue=issue, pr=None, worktree_dir=worktree)
    _sync_issue_author_attachments(rt=rt, issue=issue, pr=None, worktree_dir=worktree)

    assert len(calls) == 1
    assert calls[0]["urls"] == ["https://example.com/body.png"]
    assert calls[0]["allowed_hosts"] == {"example.com"}
    assert calls[0]["auth_host"] == "github.com"

    manifest_path = worktree / ".autocoder" / "artifacts" / "attachments-manifest.json"
    manifest = manifest_path.read_text(encoding="utf-8")
    assert "https://example.com/body.png" in manifest


def test_sync_issue_author_attachments_prunes_manifest_when_url_removed(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    worktree = tmp_path / "worktree"
    worktree.mkdir(parents=True, exist_ok=True)
    issue_with_url = IssueDetail(
        number=1,
        title="t",
        url="https://example.test/issues/1",
        state="OPEN",
        updated_at="2026-02-13T00:00:00Z",
        author="olliecrow",
        body="",
        labels=("autocoder",),
        comments=(
            IssueComment(
                id="c1",
                author="olliecrow",
                body="https://example.com/body.png",
                created_at="2026-02-13T00:00:00Z",
                updated_at="2026-02-13T00:00:00Z",
                url="https://example.test/issues/1#issuecomment-1",
            ),
        ),
    )
    issue_without_url = IssueDetail(
        number=1,
        title="t",
        url="https://example.test/issues/1",
        state="OPEN",
        updated_at="2026-02-13T00:01:00Z",
        author="olliecrow",
        body="",
        labels=("autocoder",),
        comments=(
            IssueComment(
                id="c1",
                author="olliecrow",
                body="",
                created_at="2026-02-13T00:01:00Z",
                updated_at="2026-02-13T00:01:00Z",
                url="https://example.test/issues/1#issuecomment-1",
            ),
        ),
    )
    rt = SimpleNamespace(
        repo=SimpleNamespace(host="github.com"),
        gh=SimpleNamespace(),
        runner=SimpleNamespace(),
    )

    def _fake_download(**kwargs):  # type: ignore[no-untyped-def]
        dest_dir = kwargs["dest_dir"]
        out_path = dest_dir / "body.png"
        out_path.write_bytes(b"123")
        return SimpleNamespace(
            downloaded=[SimpleNamespace(url="https://example.com/body.png", path=out_path, size_bytes=3)],
            skipped_urls=[],
        )

    monkeypatch.setattr("autocoder.run._github_auth_token", lambda rt: None)
    monkeypatch.setattr("autocoder.run.allowed_attachment_hosts_for_repo_host", lambda host: {"example.com"})
    monkeypatch.setattr("autocoder.run.download_attachments", _fake_download)

    _sync_issue_author_attachments(rt=rt, issue=issue_with_url, pr=None, worktree_dir=worktree)
    attachment_path = worktree / ".autocoder" / "artifacts" / "body.png"
    assert attachment_path.exists()
    _sync_issue_author_attachments(rt=rt, issue=issue_without_url, pr=None, worktree_dir=worktree)

    manifest_path = worktree / ".autocoder" / "artifacts" / "attachments-manifest.json"
    manifest = manifest_path.read_text(encoding="utf-8")
    assert "https://example.com/body.png" not in manifest
    assert not attachment_path.exists()


def test_sync_issue_author_attachments_does_not_delete_files_outside_artifacts(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    worktree = tmp_path / "worktree"
    artifacts_dir = worktree / ".autocoder" / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    outside_path = worktree / "outside.txt"
    outside_path.write_text("keep", encoding="utf-8")
    manifest_path = artifacts_dir / "attachments-manifest.json"
    manifest_path.write_text(
        (
            '{\n'
            '  "issue_author": "olliecrow",\n'
            '  "issue_number": 1,\n'
            '  "downloaded": [\n'
            '    {"url": "https://example.com/old.png", "path": "../outside.txt", "size_bytes": 4}\n'
            "  ],\n"
            '  "skipped_urls": []\n'
            "}\n"
        ),
        encoding="utf-8",
    )
    issue = IssueDetail(
        number=1,
        title="t",
        url="https://example.test/issues/1",
        state="OPEN",
        updated_at="2026-02-13T00:00:00Z",
        author="olliecrow",
        body="",
        labels=("autocoder",),
        comments=(),
    )
    rt = SimpleNamespace(
        repo=SimpleNamespace(host="github.com"),
        gh=SimpleNamespace(),
        runner=SimpleNamespace(),
    )

    monkeypatch.setattr("autocoder.run._github_auth_token", lambda rt: None)
    monkeypatch.setattr("autocoder.run.allowed_attachment_hosts_for_repo_host", lambda host: {"example.com"})
    monkeypatch.setattr(
        "autocoder.run.download_attachments",
        lambda **kwargs: SimpleNamespace(downloaded=[], skipped_urls=[]),
    )

    _sync_issue_author_attachments(rt=rt, issue=issue, pr=None, worktree_dir=worktree)

    assert outside_path.exists()


def test_sync_issue_author_attachments_keeps_existing_rows_when_pr_context_fetch_fails(
    tmp_path: Path,
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    worktree = tmp_path / "worktree"
    artifacts_dir = worktree / ".autocoder" / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    pr_attachment_path = artifacts_dir / "pr-note.png"
    pr_attachment_path.write_bytes(b"123")

    manifest_path = artifacts_dir / "attachments-manifest.json"
    manifest_path.write_text(
        (
            '{\n'
            '  "issue_author": "olliecrow",\n'
            '  "issue_number": 1,\n'
            '  "downloaded": [\n'
            '    {"url": "https://example.com/pr-note.png", "path": ".autocoder/artifacts/pr-note.png", "size_bytes": 3}\n'
            "  ],\n"
            '  "skipped_urls": []\n'
            "}\n"
        ),
        encoding="utf-8",
    )

    issue = IssueDetail(
        number=1,
        title="t",
        url="https://example.test/issues/1",
        state="OPEN",
        updated_at="2026-02-13T00:00:00Z",
        author="olliecrow",
        body="",
        labels=("autocoder",),
        comments=(),
    )
    pr = PullRequestDetail(
        number=2,
        title="t",
        url="https://example.test/pr/2",
        state="OPEN",
        updated_at="2026-02-13T00:00:00Z",
        author="olliecrow",
        head_ref_name="autocoder/issue-1-test",
        base_ref_name="main",
        is_cross_repository=False,
        merged_at=None,
        body="",
        comments=(),
        reviews=(),
    )

    def _raise_view_pr(*, number: int, include_comments: bool) -> PullRequestDetail:
        assert number == 2
        assert include_comments is True
        raise CommandError(
            result=CmdResult(
                args=["gh", "pr", "view", "2", "--json", "comments,reviews"],
                returncode=1,
                stdout="",
                stderr="boom",
            )
        )

    rt = SimpleNamespace(
        repo=SimpleNamespace(host="github.com"),
        gh=SimpleNamespace(view_pr=_raise_view_pr),
        runner=SimpleNamespace(),
    )

    monkeypatch.setattr("autocoder.run._github_auth_token", lambda rt: None)
    monkeypatch.setattr("autocoder.run.allowed_attachment_hosts_for_repo_host", lambda host: {"example.com"})
    monkeypatch.setattr(
        "autocoder.run.download_attachments",
        lambda **kwargs: SimpleNamespace(downloaded=[], skipped_urls=[]),
    )

    _sync_issue_author_attachments(rt=rt, issue=issue, pr=pr, worktree_dir=worktree)

    updated_manifest = manifest_path.read_text(encoding="utf-8")
    assert "https://example.com/pr-note.png" in updated_manifest
    assert pr_attachment_path.exists()


def test_prepare_trusted_thread_context_filters_to_issue_author_non_bot_content(tmp_path: Path) -> None:
    worktree = tmp_path / "worktree"
    worktree.mkdir(parents=True, exist_ok=True)
    issue = IssueDetail(
        number=1,
        title="t",
        url="https://example.test/issues/1",
        state="OPEN",
        updated_at="2026-02-13T00:00:00Z",
        author="olliecrow",
        body="body must not be treated as instruction",
        labels=("autocoder",),
        comments=(
            IssueComment(
                id="c1",
                author="olliecrow",
                body="trusted issue comment",
                created_at="2026-02-13T00:00:00Z",
                updated_at="2026-02-13T00:00:00Z",
                url="https://example.test/issues/1#issuecomment-1",
            ),
            IssueComment(
                id="c2",
                author="other",
                body="untrusted issue comment",
                created_at="2026-02-13T00:00:00Z",
                updated_at="2026-02-13T00:00:00Z",
                url="https://example.test/issues/1#issuecomment-2",
            ),
            IssueComment(
                id="c3",
                author="olliecrow",
                body="  [AutoCoder]\n\nbot status",
                created_at="2026-02-13T00:00:00Z",
                updated_at="2026-02-13T00:00:00Z",
                url="https://example.test/issues/1#issuecomment-3",
            ),
        ),
    )
    pr = PullRequestDetail(
        number=2,
        title="t",
        url="https://example.test/pr/2",
        state="OPEN",
        updated_at="2026-02-13T00:00:00Z",
        author="olliecrow",
        head_ref_name="autocoder/issue-1-test",
        base_ref_name="main",
        is_cross_repository=False,
        merged_at=None,
        body="untrusted body",
        comments=(
            PullRequestComment(
                id="pc1",
                author="olliecrow",
                body="trusted pr comment",
                created_at="2026-02-13T00:00:00Z",
                updated_at="2026-02-13T00:00:00Z",
                url="https://example.test/pr/2#issuecomment-1",
            ),
            PullRequestComment(
                id="pc2",
                author="other",
                body="untrusted pr comment",
                created_at="2026-02-13T00:00:00Z",
                updated_at="2026-02-13T00:00:00Z",
                url="https://example.test/pr/2#issuecomment-2",
            ),
            PullRequestComment(
                id="pc3",
                author="olliecrow",
                body="[autocoder]\n\nbot output",
                created_at="2026-02-13T00:00:00Z",
                updated_at="2026-02-13T00:00:00Z",
                url="https://example.test/pr/2#issuecomment-3",
            ),
        ),
        reviews=(
            PullRequestReview(
                id="r1",
                author="olliecrow",
                body="trusted pr review",
                submitted_at="2026-02-13T00:00:00Z",
                state="COMMENTED",
            ),
            PullRequestReview(
                id="r2",
                author="other",
                body="untrusted pr review",
                submitted_at="2026-02-13T00:00:00Z",
                state="COMMENTED",
            ),
            PullRequestReview(
                id="r3",
                author="olliecrow",
                body=" [autocoder]\n\nbot review",
                submitted_at="2026-02-13T00:00:00Z",
                state="COMMENTED",
            ),
        ),
    )

    rt = SimpleNamespace(
        gh=SimpleNamespace(view_pr=lambda *, number, include_comments: pr),
    )
    out_path = _prepare_trusted_thread_context(rt=rt, issue=issue, pr=pr, worktree_dir=worktree)
    payload = json.loads(out_path.read_text(encoding="utf-8"))

    assert payload["issue_author"] == "olliecrow"
    assert [c["id"] for c in payload["issue"]["comments"]] == ["c1"]
    assert [c["id"] for c in payload["pr"]["comments"]] == ["pc1"]
    assert [r["id"] for r in payload["pr"]["reviews"]] == ["r1"]
    assert payload["pr"]["context_complete"] is True
