from __future__ import annotations

import os
import re
import shutil
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from ._runner import CommandError, Runner

_MAX_BLOB_BYTES = 100 * 1024 * 1024  # GitHub rejects larger files.
_DEFAULT_MARKER_WIDTH = 7


def _marker_pattern(minimum: int) -> re.Pattern[bytes]:
    # Git writes exactly conflict-marker-size characters (default 7). Honor a
    # shorter configured size. Any longer run still matches, so a wide marker
    # cannot hide. diff3 and zdiff3 add a ||||||| base section of the same width.
    # A line of only "=" is a heading underline, not a marker.
    least = minimum if minimum > 0 else _DEFAULT_MARKER_WIDTH
    text = rf"^(?:<{{{least},}}|>{{{least},}}|\|{{{least},}})(?: |$)"
    return re.compile(text.encode("ascii"), re.MULTILINE)


def _has_conflict_markers(path: Path, *, minimum: int = _DEFAULT_MARKER_WIDTH) -> bool:
    # A deleted file or a symlink has no marker text to check.
    if path.is_symlink() or not path.is_file():
        return False
    return _marker_pattern(minimum).search(path.read_bytes().replace(b"\r\n", b"\n")) is not None


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
        if self.merge_in_progress(cwd=cwd):
            return False
        raise CommandError(result=res)

    def merge_in_progress(self, *, cwd: Path) -> bool:
        res = self._runner.run(["git", "rev-parse", "-q", "--verify", "MERGE_HEAD"], cwd=cwd, check=False)
        return res.returncode == 0

    def unmerged_paths(self, *, cwd: Path) -> list[str]:
        out = self._git(["diff", "--name-only", "-z", "--diff-filter=U"], cwd=cwd)
        return sorted({p for p in out.split("\0") if p})

    def _marker_minimum(self, *, cwd: Path, rel: str) -> int:
        out = self._git(["check-attr", "-z", "conflict-marker-size", "--", rel], cwd=cwd)
        parts = out.split("\0")
        raw = parts[2] if len(parts) >= 3 else ""
        width = int(raw) if raw.isdigit() else _DEFAULT_MARKER_WIDTH
        if width < 1:
            width = _DEFAULT_MARKER_WIDTH
        # A configured width of 10 still matches; a width below 7 must match too.
        return min(width, _DEFAULT_MARKER_WIDTH)

    def unresolved_conflict_paths(self, *, cwd: Path, also: Sequence[str] = ()) -> list[str]:
        """
        Return conflict paths that are not safe to commit.

        During a merge, a conflicted file counts as resolved once it has no conflict marker lines.
        `also` keeps the paths that were conflicted at the start of the run, so staging them does
        not hide markers. A lone `=======` line (for example a heading underline) is not a marker.
        Outside a merge, every unmerged path is unsafe.
        """
        paths = self.unmerged_paths(cwd=cwd)
        if not self.merge_in_progress(cwd=cwd):
            return paths
        inspect = sorted(set(paths) | {p for p in also if p})
        return [p for p in inspect if _has_conflict_markers(cwd / p, minimum=self._marker_minimum(cwd=cwd, rel=p))]

    def add_all(self, *, cwd: Path) -> None:
        self._git(["add", "-A"], cwd=cwd)

    def staged_paths(self, *, cwd: Path) -> list[str]:
        out = self._git(["diff", "--cached", "--name-only", "-z"], cwd=cwd)
        return sorted({p for p in out.split("\0") if p})

    def _cached_added(self, *, cwd: Path) -> set[str]:
        out = self._git(["diff", "--cached", "--name-only", "-z", "--diff-filter=A"], cwd=cwd)
        return {p for p in out.split("\0") if p}

    def _unwanted_merge_staged(self, *, cwd: Path, allowed: set[str]) -> list[str]:
        added = self._cached_added(cwd=cwd)
        return sorted(added - allowed)

    def stage_merge_resolution(
        self,
        *,
        cwd: Path,
        conflict_paths: Sequence[str],
        already_staged: Sequence[str],
    ) -> None:
        """
        Stage a resolved merge without publishing unrelated untracked files.

        Conflict paths and tracked edits are staged. Paths already staged when the
        conflict was recorded stay staged, including a new file from the other branch.
        Only additions outside that snapshot and the conflict paths are removed.
        Ignore rules never remove tracked merge content.
        """
        if conflict_paths:
            self._git(["add", "--", *conflict_paths], cwd=cwd)
        self._git(["add", "-u"], cwd=cwd)
        allowed = set(conflict_paths) | set(already_staged)
        extras = self._unwanted_merge_staged(cwd=cwd, allowed=allowed)
        if extras:
            self._git(["restore", "--staged", "--", *extras], cwd=cwd)
        if self._unwanted_merge_staged(cwd=cwd, allowed=allowed):
            raise RuntimeError(
                "merge staging left paths that are not part of the resolution; "
                "restore the worktree and reply retrigger"
            )

    def commit(self, *, cwd: Path, message: str) -> None:
        self._git(["commit", "-m", message], cwd=cwd)

    def outgoing_scan_text(self, *, cwd: Path, exclude_refs: Sequence[str]) -> Iterable[str]:
        """
        Yield metadata and each new blob for scanning, one blob at a time.

        Blobs are read as latin-1, which decodes any bytes, so binary files are scanned
        without a bypass (secret patterns are ASCII). UTF-8 text is decoded as UTF-8 too.
        """
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
            if int(size) > _MAX_BLOB_BYTES:
                raise RuntimeError("push blocked: an outgoing file exceeds GitHub's 100 MiB file limit")
            raw = self._runner.run(["git", "cat-file", "blob", oid], cwd=cwd, check=True, encoding="latin-1").stdout
            yield raw
            if not raw.isascii():
                try:
                    yield raw.encode("latin-1").decode("utf-8")
                except UnicodeDecodeError:
                    pass

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
