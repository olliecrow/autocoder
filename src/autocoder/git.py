from __future__ import annotations

import os
import shutil
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from ._runner import CommandError, Runner


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

    def merge(self, *, cwd: Path, ref: str) -> bool:
        """
        Merge `ref` into the current branch without rewriting history.

        Return False when the merge stopped on conflicts (left in place for resolution).
        """
        res = self._runner.run(["git", "merge", "--no-edit", ref], cwd=cwd, check=False)
        if res.returncode == 0:
            return True
        conflicted = self._runner.run(["git", "rev-parse", "-q", "--verify", "MERGE_HEAD"], cwd=cwd, check=False)
        if conflicted.returncode == 0:
            return False
        raise CommandError(result=res)

    def has_unresolved_conflicts(self, *, cwd: Path) -> bool:
        if self._git(["ls-files", "--unmerged"], cwd=cwd).strip():
            return True
        for args in (["diff", "--check"], ["diff", "--cached", "--check"]):
            result = self._runner.run(["git", *args], cwd=cwd, check=False)
            if result.returncode not in (0, 2):
                raise CommandError(result=result)
            if "leftover conflict marker" in result.stdout:
                return True
        return False

    def add_all(self, *, cwd: Path) -> None:
        self._git(["add", "-A"], cwd=cwd)

    def commit(self, *, cwd: Path, message: str) -> None:
        self._git(["commit", "-m", message], cwd=cwd)

    def outgoing_scan_text(self, *, cwd: Path, exclude_refs: Sequence[str]) -> Iterable[str]:
        """Scan metadata and each new blob, with a bounded per-blob read."""
        revisions = ["HEAD", "--not", *exclude_refs, "--"]
        yield self._git(["log", "--format=%B", "--name-only", "--diff-merges=first-parent", *revisions], cwd=cwd)
        objects = self._git(["rev-list", "--objects", *revisions], cwd=cwd)
        yield objects  # Includes filenames even for empty or binary files.
        ids = [line.split(" ", 1)[0] for line in objects.splitlines()]
        if not ids:
            return
        metadata = self._runner.run(
            ["git", "cat-file", "--batch-check=%(objectname) %(objecttype) %(objectsize)"],
            cwd=cwd, input_text="\n".join(ids) + "\n", check=True,
        ).stdout
        for line in metadata.splitlines():
            oid, kind, size = line.split()
            if kind != "blob":
                continue
            if int(size) > 1024 * 1024:
                raise RuntimeError("push blocked: outgoing blob exceeds the 1 MiB scan limit; operator review required")
            try:
                yield self._git(["cat-file", "blob", oid], cwd=cwd)
            except UnicodeError:
                raise RuntimeError("push blocked: outgoing binary blob is not UTF-8; operator review required") from None

    def push(self, *, cwd: Path, branch: str) -> None:
        self._git(["push", "-u", "origin", f"HEAD:refs/heads/{branch}"], cwd=cwd)

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

    # Never make a secret-bearing .env file more permissive than owner read/write.
    mode = src.stat().st_mode & 0o600 or 0o600
    try:
        fd = os.open(dst, os.O_CREAT | os.O_EXCL | os.O_WRONLY, mode)
    except FileExistsError:
        return
    try:
        with src.open("rb") as source, os.fdopen(fd, "wb") as destination:
            shutil.copyfileobj(source, destination)
        os.chmod(dst, mode)
    except BaseException:
        dst.unlink(missing_ok=True)
        raise
