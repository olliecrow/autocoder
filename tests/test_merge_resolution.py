from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_run_pr_flow import _GhMergeStub

from autocoder._runner import SubprocessRunner
from autocoder.codex import CodexOutput
from autocoder.gh import IssueComment, IssueDetail
from autocoder.git import GitClient, ensure_local_excludes
from autocoder.run import _maybe_run_codex
from autocoder.state import IssueState, RepoState, load_repo_state, save_repo_state


def _git_identity(monkeypatch) -> None:
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    for key in ("GIT_AUTHOR_NAME", "GIT_COMMITTER_NAME"):
        monkeypatch.setenv(key, "test")
    for key in ("GIT_AUTHOR_EMAIL", "GIT_COMMITTER_EMAIL"):
        monkeypatch.setenv(key, "test@example.com")


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


class _MarkerCodex:
    """Leave Git's markers in place. Optionally stage them, the way a worker or hook might."""

    def __init__(self, *, stage: bool) -> None:
        self._stage = stage

    def run_exec(self, *, workdir: Path, prompt: str, schema_path: Path, output_path: Path) -> CodexOutput:
        if self._stage:
            _git(workdir, "add", "f.txt")
        return CodexOutput(
            decision="ready",
            issue_comment_markdown="merged main",
            pr_comment_markdown=None,
            pr_title="t",
            pr_body_markdown="b",
            commit_message="Merge main",
            tests_ran=(),
        )


def _ready_runtime(tmp_path: Path, *, managed: Path, git: GitClient, codex):
    return SimpleNamespace(
        repo=SimpleNamespace(full_name="owner/repo"),
        cfg=SimpleNamespace(mentions=(), allowed_github_logins=("trusted-user",)),
        default_branch="main",
        managed_dir=managed,
        state_path=tmp_path / "state.json",
        git=git,
        gh=_GhMergeStub(),
        codex=codex,
    )


def _issue() -> IssueDetail:
    request = IssueComment("c1", "trusted-user", "sync main", "now", "now", "https://example.test/c1")
    return IssueDetail(
        1, "t", "https://example.test/issues/1", "OPEN", "now", "trusted-user", "",
        ("autocoder", "autocoder:claimed"), (request,),
    )


@pytest.mark.parametrize("stage", [False, True])
def test_ready_run_does_not_publish_wide_or_staged_markers(tmp_path: Path, monkeypatch, stage: bool) -> None:
    _git_identity(monkeypatch)
    branch = "autocoder/issue-1-test"
    origin, managed, worktree = tmp_path / "origin.git", tmp_path / "managed", tmp_path / "worktree"
    _git(tmp_path, "init", "-q", "--bare", "-b", "main", str(origin))
    _git(tmp_path, "clone", "-q", str(origin), str(managed))
    (managed / "f.txt").write_text("base\n")
    (managed / ".gitattributes").write_text("f.txt conflict-marker-size=10\n")
    _git(managed, "add", "-A")
    _git(managed, "commit", "-qm", "base")
    _git(managed, "push", "-q", "origin", "main")
    _git(managed, "worktree", "add", "-q", "-b", branch, str(worktree), "origin/main")
    (worktree / "f.txt").write_text("issue\n")
    _git(worktree, "commit", "-qam", "issue change")
    _git(worktree, "push", "-q", "origin", f"HEAD:refs/heads/{branch}")
    _git(managed, "fetch", "-q", "origin")
    (managed / "f.txt").write_text("main\n")
    _git(managed, "commit", "-qam", "main change")
    _git(managed, "push", "-q", "origin", "main")
    _git(worktree, "config", "merge.conflictStyle", "diff3")
    git = GitClient(runner=SubprocessRunner())
    assert git.merge(cwd=worktree, ref="origin/main") is False
    ensure_local_excludes(repo_dir=managed, patterns=[".autocoder/"])
    (worktree / ".autocoder" / "plan").mkdir(parents=True)
    text = (worktree / "f.txt").read_text(encoding="utf-8")
    assert "<<<<<<<<<<" in text and "||||||||||" in text
    remote_before = _git(origin, "rev-parse", branch)

    rt = _ready_runtime(tmp_path, managed=managed, git=git, codex=_MarkerCodex(stage=stage))
    issue_state = IssueState(branch=branch, pr=7)
    _maybe_run_codex(
        rt=rt, issue_state=issue_state, issue=_issue(), pr=None, worktree_dir=worktree,
        trigger_reasons=("default_branch_advanced",),
    )

    assert git.merge_in_progress(cwd=worktree)
    assert _git(origin, "rev-parse", branch) == remote_before
    assert len(rt.gh.issue_comments) == 1
    assert "Push blocked" in rt.gh.issue_comments[0][1] and "`f.txt`" in rt.gh.issue_comments[0][1]
    assert issue_state.merge_conflict_paths == ("f.txt",)

    # The next poll loads the saved paths. Staging no longer lists the file as unmerged.
    _git(worktree, "add", "f.txt")
    save_repo_state(rt.state_path, RepoState(issues={1: issue_state}))
    restored = load_repo_state(rt.state_path).issues[1]
    rt.gh = _GhMergeStub()
    rt.codex = _MarkerCodex(stage=True)
    _maybe_run_codex(
        rt=rt, issue_state=restored, issue=_issue(), pr=None, worktree_dir=worktree,
        trigger_reasons=("default_branch_advanced",),
    )
    assert git.merge_in_progress(cwd=worktree)
    assert _git(origin, "rev-parse", branch) == remote_before
    assert "Push blocked" in rt.gh.issue_comments[0][1]


class _NoisyCodex:
    """Resolve the conflict, edit a tracked file, and stage unrelated untracked files."""

    def run_exec(self, *, workdir: Path, prompt: str, schema_path: Path, output_path: Path) -> CodexOutput:
        (workdir / "f.txt").write_text("resolved\n", encoding="utf-8")
        (workdir / "tracked.txt").write_text("tracked-edit\n", encoding="utf-8")
        (workdir / "build-output.txt").write_text("build junk\n", encoding="utf-8")
        (workdir / "credentials.json").write_text("local note\n", encoding="utf-8")
        (workdir / "build").mkdir()
        (workdir / "build" / "out.txt").write_text("ignored\n", encoding="utf-8")
        _git(workdir, "add", "-A")
        _git(workdir, "add", "-f", "build/out.txt")
        return CodexOutput(
            decision="ready",
            issue_comment_markdown="merged main",
            pr_comment_markdown=None,
            pr_title="t",
            pr_body_markdown="b",
            commit_message="Merge main",
            tests_ran=(),
        )


def test_ready_merge_does_not_publish_unrelated_untracked_files(tmp_path: Path, monkeypatch) -> None:
    _git_identity(monkeypatch)
    branch = "autocoder/issue-1-test"
    origin, managed, worktree = tmp_path / "origin.git", tmp_path / "managed", tmp_path / "worktree"
    _git(tmp_path, "init", "-q", "--bare", "-b", "main", str(origin))
    _git(tmp_path, "clone", "-q", str(origin), str(managed))
    (managed / "f.txt").write_text("base\n", encoding="utf-8")
    (managed / "other.txt").write_text("other\n", encoding="utf-8")
    (managed / "tracked.txt").write_text("tracked\n", encoding="utf-8")
    (managed / ".gitignore").write_text("build/\n", encoding="utf-8")
    _git(managed, "add", "-A")
    _git(managed, "commit", "-qm", "base")
    _git(managed, "push", "-q", "origin", "main")
    _git(managed, "worktree", "add", "-q", "-b", branch, str(worktree), "origin/main")
    (worktree / "f.txt").write_text("issue\n", encoding="utf-8")
    _git(worktree, "commit", "-qam", "issue change")
    _git(worktree, "push", "-q", "origin", f"HEAD:refs/heads/{branch}")
    _git(managed, "fetch", "-q", "origin")
    (managed / "f.txt").write_text("main\n", encoding="utf-8")
    (managed / "other.txt").write_text("other-main\n", encoding="utf-8")
    (managed / "from-main.txt").write_text("from-main\n", encoding="utf-8")
    _git(managed, "add", "-A")
    _git(managed, "commit", "-qm", "main change")
    _git(managed, "push", "-q", "origin", "main")
    git = GitClient(runner=SubprocessRunner())
    assert git.merge(cwd=worktree, ref="origin/main") is False
    ensure_local_excludes(repo_dir=managed, patterns=[".autocoder/"])
    (worktree / ".autocoder" / "plan").mkdir(parents=True)

    rt = _ready_runtime(tmp_path, managed=managed, git=git, codex=_NoisyCodex())
    issue_state = IssueState(branch=branch, pr=7)
    _maybe_run_codex(
        rt=rt, issue_state=issue_state, issue=_issue(), pr=None, worktree_dir=worktree,
        trigger_reasons=("default_branch_advanced",),
    )

    names = set(_git(worktree, "ls-tree", "-r", "--name-only", "HEAD").splitlines())
    assert {"f.txt", "other.txt", "tracked.txt", "from-main.txt", ".gitignore"} <= names
    assert "build-output.txt" not in names
    assert "credentials.json" not in names
    assert "build/out.txt" not in names
    assert (worktree / "f.txt").read_text(encoding="utf-8") == "resolved\n"
    assert (worktree / "tracked.txt").read_text(encoding="utf-8") == "tracked-edit\n"
    assert (worktree / "other.txt").read_text(encoding="utf-8") == "other-main\n"
    assert (worktree / "from-main.txt").read_text(encoding="utf-8") == "from-main\n"
    assert (worktree / "build-output.txt").read_text(encoding="utf-8") == "build junk\n"
    assert (worktree / "credentials.json").read_text(encoding="utf-8") == "local note\n"
    assert (worktree / "build" / "out.txt").read_text(encoding="utf-8") == "ignored\n"
    assert not git.merge_in_progress(cwd=worktree)
    assert len(_git(worktree, "rev-list", "--parents", "-n", "1", "HEAD").split()) == 3
    assert _git(origin, "rev-parse", branch) == _git(worktree, "rev-parse", "HEAD")
    assert issue_state.merge_conflict_paths == ()
    assert issue_state.merge_staged_paths == ()
