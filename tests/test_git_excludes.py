from __future__ import annotations

import os
from pathlib import Path

from autocoder.git import ensure_local_excludes, ensure_worktree_env


def test_ensure_local_excludes_appends_and_dedupes(tmp_path: Path) -> None:
    repo_dir = tmp_path / "repo"
    (repo_dir / ".git" / "info").mkdir(parents=True)
    exclude = repo_dir / ".git" / "info" / "exclude"
    exclude.write_text(".env\n", encoding="utf-8")

    ensure_local_excludes(repo_dir=repo_dir, patterns=[".env", ".autocoder/", ""])

    content = exclude.read_text(encoding="utf-8").splitlines()
    assert ".env" in content
    assert ".autocoder/" in content
    assert content.count(".env") == 1


def test_ensure_worktree_env_copies_with_owner_only_permissions(tmp_path: Path) -> None:
    managed_clone = tmp_path / "repo"
    worktree = tmp_path / "worktree"
    managed_clone.mkdir()
    worktree.mkdir()
    source = managed_clone / ".env"
    source.write_text("EXAMPLE=value\n", encoding="utf-8")
    source.chmod(0o600)

    ensure_worktree_env(managed_clone_dir=managed_clone, worktree_dir=worktree)

    destination = worktree / ".env"
    assert destination.read_text(encoding="utf-8") == "EXAMPLE=value\n"
    assert os.stat(destination).st_mode & 0o077 == 0


def test_ensure_worktree_env_preserves_existing_destination(tmp_path: Path) -> None:
    managed_clone = tmp_path / "repo"
    worktree = tmp_path / "worktree"
    managed_clone.mkdir()
    worktree.mkdir()
    (managed_clone / ".env").write_text("new\n", encoding="utf-8")
    destination = worktree / ".env"
    destination.write_text("existing\n", encoding="utf-8")

    ensure_worktree_env(managed_clone_dir=managed_clone, worktree_dir=worktree)

    assert destination.read_text(encoding="utf-8") == "existing\n"
