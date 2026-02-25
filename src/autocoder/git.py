from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
from typing import Iterable, Sequence

from ._runner import Runner


@dataclass(frozen=True)
class GitWorktree:
    path: Path
    branch: str


class GitClient:
    def __init__(self, *, runner: Runner):
        self._runner = runner

    def _git(self, args: Sequence[str], *, cwd: Path, check: bool = True) -> str:
        res = self._runner.run(["git", *args], cwd=cwd, check=check)
        return res.stdout

    def is_git_repo(self, path: Path) -> bool:
        return (path / ".git").exists()

    def clone(self, *, repo_url: str, dest: Path) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        self._runner.run(["git", "clone", repo_url, str(dest)], check=True)

    def fetch(self, *, cwd: Path) -> None:
        self._git(["fetch", "--prune", "origin"], cwd=cwd)

    def remote_set_url(self, *, cwd: Path, name: str, url: str) -> None:
        self._git(["remote", "set-url", name, url], cwd=cwd)

    def remote_get_url(self, *, cwd: Path, name: str) -> str:
        out = self._git(["remote", "get-url", name], cwd=cwd)
        return out.strip()

    def rev_parse(self, *, cwd: Path, rev: str) -> str:
        return self._git(["rev-parse", rev], cwd=cwd).strip()

    def branch_exists(self, *, cwd: Path, branch: str) -> bool:
        res = self._runner.run(
            ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"],
            cwd=cwd,
            check=False,
        )
        return res.returncode == 0

    def remote_branch_exists(self, *, cwd: Path, remote: str, branch: str) -> bool:
        res = self._runner.run(
            ["git", "show-ref", "--verify", "--quiet", f"refs/remotes/{remote}/{branch}"],
            cwd=cwd,
            check=False,
        )
        return res.returncode == 0

    def worktree_add(
        self,
        *,
        repo_dir: Path,
        worktree_path: Path,
        branch: str,
        base_ref: str,
    ) -> GitWorktree:
        worktree_path.parent.mkdir(parents=True, exist_ok=True)
        if self.branch_exists(cwd=repo_dir, branch=branch):
            self._git(["worktree", "add", str(worktree_path), branch], cwd=repo_dir)
        else:
            # If a remote branch already exists (resume case), base the new local branch on it.
            start_ref = base_ref
            if self.remote_branch_exists(cwd=repo_dir, remote="origin", branch=branch):
                start_ref = f"origin/{branch}"
            self._git(["worktree", "add", "-b", branch, str(worktree_path), start_ref], cwd=repo_dir)
        return GitWorktree(path=worktree_path, branch=branch)

    def worktree_remove(self, *, repo_dir: Path, worktree_path: Path) -> None:
        # `git worktree remove` expects the path to be registered.
        self._git(["worktree", "remove", "--force", str(worktree_path)], cwd=repo_dir)

    def worktree_prune(self, *, repo_dir: Path) -> None:
        self._git(["worktree", "prune"], cwd=repo_dir)

    def delete_local_branch(self, *, cwd: Path, branch: str) -> None:
        self._git(["branch", "-D", branch], cwd=cwd)

    def delete_remote_branch(self, *, cwd: Path, branch: str) -> None:
        self._git(["push", "origin", "--delete", branch], cwd=cwd)

    def current_branch(self, *, cwd: Path) -> str:
        return self._git(["branch", "--show-current"], cwd=cwd).strip()

    def status_porcelain(self, *, cwd: Path) -> str:
        return self._git(["status", "--porcelain"], cwd=cwd)

    def has_in_progress_operation(self, *, cwd: Path) -> bool:
        """
        Return True when a merge/rebase/cherry-pick/revert is in progress.
        """
        for ref in ("MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "REBASE_HEAD"):
            res = self._runner.run(["git", "rev-parse", "-q", "--verify", ref], cwd=cwd, check=False)
            if res.returncode == 0:
                return True

        git_dir = self._git(["rev-parse", "--git-dir"], cwd=cwd).strip()
        git_path = Path(git_dir)
        if not git_path.is_absolute():
            git_path = cwd / git_path

        return (git_path / "rebase-apply").exists() or (git_path / "rebase-merge").exists()

    def add_all(self, *, cwd: Path) -> None:
        self._git(["add", "-A"], cwd=cwd)

    def commit(self, *, cwd: Path, message: str) -> None:
        self._git(["commit", "-m", message], cwd=cwd)

    def push(self, *, cwd: Path, branch: str) -> None:
        self._git(["push", "-u", "origin", branch], cwd=cwd)

    def is_ancestor(self, *, cwd: Path, ancestor: str, descendant: str) -> bool:
        """
        Return True if `ancestor` is an ancestor of `descendant`.

        Uses `git merge-base --is-ancestor` and treats all non-zero return codes as False.
        """
        res = self._runner.run(
            ["git", "merge-base", "--is-ancestor", ancestor, descendant],
            cwd=cwd,
            check=False,
        )
        return res.returncode == 0


def ensure_local_excludes(*, repo_dir: Path, patterns: Iterable[str]) -> None:
    exclude_path = repo_dir / ".git" / "info" / "exclude"
    exclude_path.parent.mkdir(parents=True, exist_ok=True)
    existing = ""
    if exclude_path.exists():
        existing = exclude_path.read_text(encoding="utf-8")

    lines = {ln.strip() for ln in existing.splitlines() if ln.strip()}
    to_add = [p for p in patterns if p.strip() and p.strip() not in lines]
    if not to_add:
        return

    with exclude_path.open("a", encoding="utf-8") as f:
        if existing and not existing.endswith("\n"):
            f.write("\n")
        for pat in to_add:
            f.write(pat.strip() + "\n")


def ensure_worktree_env(*, managed_clone_dir: Path, worktree_dir: Path) -> None:
    src = managed_clone_dir / ".env"
    dst = worktree_dir / ".env"
    if dst.exists() or not src.exists():
        return
    shutil.copyfile(src, dst)
