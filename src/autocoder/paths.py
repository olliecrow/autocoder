from __future__ import annotations

from pathlib import Path

from .repo import RepoSpec


def autocoder_home() -> Path:
    return Path.home() / "autocoder"


def instance_id_path() -> Path:
    return autocoder_home() / "instance_id"


def repo_root_dir(repo: RepoSpec) -> Path:
    return autocoder_home() / "repos" / repo.owner / repo.name


def managed_clone_dir(repo: RepoSpec) -> Path:
    return repo_root_dir(repo) / "repo"


def worktrees_dir(repo: RepoSpec) -> Path:
    return repo_root_dir(repo) / "worktrees"


def issue_worktree_dir(repo: RepoSpec, issue_number: int) -> Path:
    return worktrees_dir(repo) / f"issue-{issue_number}"


def repo_state_dir(repo: RepoSpec) -> Path:
    return repo_root_dir(repo) / "state"


def global_config_path() -> Path:
    return autocoder_home() / "config.toml"


def repo_config_path(repo: RepoSpec) -> Path:
    return repo_root_dir(repo) / "config.toml"

