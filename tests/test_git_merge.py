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
