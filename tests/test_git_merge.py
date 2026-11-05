from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from autocoder._runner import SubprocessRunner
from autocoder.git import GitClient


@pytest.fixture
def repo(tmp_path: Path, monkeypatch) -> Path:
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    for key in ("GIT_AUTHOR_NAME", "GIT_COMMITTER_NAME"):
        monkeypatch.setenv(key, "test")
    for key in ("GIT_AUTHOR_EMAIL", "GIT_COMMITTER_EMAIL"):
        monkeypatch.setenv(key, "test@example.com")
    path = tmp_path / "repo"
    path.mkdir()
    _git(path, "init", "-q", "-b", "main")
    (path / "f.txt").write_text("base\n", encoding="utf-8")
    _git(path, "add", "-A")
    _git(path, "commit", "-q", "-m", "base")
    _git(path, "branch", "issue")
    return path


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout


def _commit_file(repo: Path, branch: str, name: str, text: str) -> None:
    _git(repo, "checkout", "-q", branch)
    (repo / name).write_text(text, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", f"{branch} change")


def test_merge_creates_merge_commit_when_clean(repo: Path) -> None:
    _commit_file(repo, "main", "main.txt", "main\n")
    _commit_file(repo, "issue", "issue.txt", "issue\n")
    git = GitClient(runner=SubprocessRunner())

    assert git.merge(cwd=repo, ref="main") is True
    assert len(_git(repo, "rev-list", "--parents", "-n1", "HEAD").split()) == 3
    assert git.is_ancestor(cwd=repo, ancestor="main", descendant="issue")


def test_merge_leaves_conflicts_for_resolution_then_commit_completes_it(repo: Path) -> None:
    _commit_file(repo, "main", "f.txt", "main\n")
    _commit_file(repo, "issue", "f.txt", "issue\n")
    git = GitClient(runner=SubprocessRunner())

    assert git.merge(cwd=repo, ref="main") is False
    assert git.has_in_progress_operation(cwd=repo)
    # Codex edits the file content only; autocoder stages and commits outside the sandbox.
    (repo / "f.txt").write_text("resolved\n", encoding="utf-8")
    git.add_all(cwd=repo)
    git.commit(cwd=repo, message="resolve")

    assert not git.has_in_progress_operation(cwd=repo)
    assert git.is_ancestor(cwd=repo, ancestor="main", descendant="issue")


def test_scan_excludes_upstream_blobs_but_keeps_conflict_resolutions(repo: Path) -> None:
    _commit_file(repo, "main", "f.txt", "from main\n")
    _commit_file(repo, "main", "upstream.txt", "already on the default branch\n")
    _commit_file(repo, "issue", "f.txt", "from issue\n")
    _git(repo, "branch", "pushed")  # what the remote issue branch already has
    _commit_file(repo, "issue", "new.txt", "new outgoing line\n")
    git = GitClient(runner=SubprocessRunner())
    assert git.merge(cwd=repo, ref="main") is False
    (repo / "f.txt").write_text("resolved line\n", encoding="utf-8")
    git.add_all(cwd=repo)
    git.commit(cwd=repo, message="merge main")

    added = "\n".join(git.outgoing_scan_text(cwd=repo, exclude_refs=["main", "pushed"])).splitlines()

    assert "new outgoing line" in added
    assert "resolved line" in added
    assert "already on the default branch" not in added
    assert "from issue" not in added


def test_conflict_guard_checks_index_and_staged_markers(repo):
    _commit_file(repo, "main", "f.txt", "main\n")
    _commit_file(repo, "issue", "f.txt", "issue\n")
    git = GitClient(runner=SubprocessRunner())
    assert not git.merge(cwd=repo, ref="main")
    assert git.has_unresolved_conflicts(cwd=repo)
    git.add_all(cwd=repo)
    assert git.has_unresolved_conflicts(cwd=repo)
    (repo / "f.txt").write_text("resolved\n")
    assert git.has_unresolved_conflicts(cwd=repo)  # markers remain in the index
    git.add_all(cwd=repo)
    assert not git.has_unresolved_conflicts(cwd=repo)
    (repo / "f.txt").write_text("<<<<<<< HEAD\nleft\n=======\nright\n>>>>>>> main\n")
    assert git.has_unresolved_conflicts(cwd=repo)  # unstaged markers with a resolved index


@pytest.mark.parametrize("location", ["filename", "message", "binary", "text"])
def test_outgoing_scan_catches_secret_in_each_surface(repo, location):
    from autocoder.security import contains_likely_secret
    base = _git(repo, "rev-parse", "HEAD").strip()
    token = "ghp_" + "A" * 30
    name = token if location == "filename" else "new"
    content = b"\x00" + token.encode() if location == "binary" else (
        token.encode() if location == "text" else b"base\n")
    (repo / name).write_bytes(content)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", token if location == "message" else "change")
    git = GitClient(runner=SubprocessRunner())
    assert any(contains_likely_secret(text) for text in git.outgoing_scan_text(cwd=repo, exclude_refs=[base]))


@pytest.mark.parametrize("content", [b"\xff\x00", b"x" * (1024 * 1024 + 1)])
def test_outgoing_scan_blocks_unscannable_blobs(repo, content):
    base = _git(repo, "rev-parse", "HEAD").strip()
    (repo / "new").write_bytes(content)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "change")
    with pytest.raises(RuntimeError, match="push blocked"):
        list(GitClient(runner=SubprocessRunner()).outgoing_scan_text(cwd=repo, exclude_refs=[base]))


def test_outgoing_scan_fails_on_git_error(repo):
    from autocoder._runner import CommandError
    with pytest.raises(CommandError):
        list(GitClient(runner=SubprocessRunner()).outgoing_scan_text(cwd=repo, exclude_refs=["missing-ref"]))
