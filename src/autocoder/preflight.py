from __future__ import annotations

from dataclasses import dataclass
import shutil
import sys
from typing import TextIO

from ._runner import CommandTimeout, Runner, SubprocessRunner
from .paths import (
    global_config_path,
    managed_clone_dir,
    repo_config_path,
    repo_state_dir,
)
from .repo import RepoSpec, parse_repo_ssh_url


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    detail: str


def _first_line(text: str) -> str:
    raw = (text or "").strip()
    if not raw:
        return "no output"
    line = raw.splitlines()[0].strip()
    return line or "no output"


def _run_command_check(
    *,
    runner: Runner,
    name: str,
    argv: list[str],
    timeout_s: float = 20.0,
    pass_detail: str = "ok",
) -> CheckResult:
    try:
        res = runner.run(argv, check=False, timeout_s=timeout_s)
    except CommandTimeout:
        return CheckResult(name=name, ok=False, detail=f"timed out: {' '.join(argv)}")
    except Exception as exc:
        return CheckResult(name=name, ok=False, detail=str(exc))
    if res.returncode == 0:
        return CheckResult(name=name, ok=True, detail=pass_detail)
    detail = _first_line(res.stderr) if (res.stderr or "").strip() else _first_line(res.stdout)
    return CheckResult(name=name, ok=False, detail=detail)


def _tool_check(tool: str) -> CheckResult:
    path = shutil.which(tool)
    if not path:
        return CheckResult(name=f"tool available: {tool}", ok=False, detail="not found on PATH")
    return CheckResult(name=f"tool available: {tool}", ok=True, detail=path)


def _doctor_checks(*, repo: RepoSpec, runner: Runner) -> list[CheckResult]:
    checks: list[CheckResult] = []

    checks.append(_tool_check("git"))
    checks.append(_tool_check("gh"))
    checks.append(_tool_check("codex"))

    checks.append(
        _run_command_check(
            runner=runner,
            name="gh auth status",
            argv=["gh", "auth", "status"],
            pass_detail="authenticated",
        )
    )
    checks.append(
        _run_command_check(
            runner=runner,
            name="codex login status",
            argv=["codex", "login", "status"],
            pass_detail="authenticated",
        )
    )
    checks.append(
        _run_command_check(
            runner=runner,
            name="remote repository reachable",
            argv=["git", "ls-remote", "--heads", repo.ssh_url],
            timeout_s=30.0,
            pass_detail=repo.ssh_url,
        )
    )
    return checks


def run_doctor(*, repo_ssh_url: str, runner: Runner | None = None, out: TextIO = sys.stdout) -> int:
    try:
        repo = parse_repo_ssh_url(repo_ssh_url)
    except ValueError as exc:
        print(f"autocoder doctor error: {exc}", file=out)
        return 2

    rt = runner or SubprocessRunner()
    checks = _doctor_checks(repo=repo, runner=rt)
    all_ok = True

    print("autocoder doctor", file=out)
    print(f"repo: {repo.full_name}", file=out)
    print(f"repo ssh url: {repo.ssh_url}", file=out)
    print(file=out)

    for check in checks:
        state = "ok" if check.ok else "fail"
        print(f"[{state}] {check.name} - {check.detail}", file=out)
        if not check.ok:
            all_ok = False

    if all_ok:
        print("\ndoctor result: PASS", file=out)
        return 0
    print("\ndoctor result: FAIL", file=out)
    return 1


def run_dry_run(*, repo_ssh_url: str, out: TextIO = sys.stdout) -> int:
    try:
        repo = parse_repo_ssh_url(repo_ssh_url)
    except ValueError as exc:
        print(f"autocoder dry-run error: {exc}", file=out)
        return 2

    managed_dir = managed_clone_dir(repo)
    state_dir = repo_state_dir(repo)
    state_path = state_dir / "state.json"
    lock_path = state_dir / "session.lock"
    global_cfg = global_config_path()
    repo_cfg = repo_config_path(repo)

    print("autocoder dry-run", file=out)
    print(f"repo: {repo.full_name}", file=out)
    print(f"repo ssh url: {repo.ssh_url}", file=out)
    print(f"managed clone path: {managed_dir}", file=out)
    print(f"state path: {state_path}", file=out)
    print(f"lock path: {lock_path}", file=out)
    print(file=out)

    print("planned order:", file=out)
    print("1. parse repo and load global plus repo config", file=out)
    print(f"   - global config: {global_cfg}", file=out)
    print(f"   - repo config: {repo_cfg}", file=out)
    print("2. acquire per-repo session lock", file=out)
    print("3. ensure managed clone is present and synced", file=out)
    print("4. discover default branch and ensure required labels", file=out)
    print("5. load repo state and start polling loop", file=out)
    print("6. each loop scans open opted-in issues and processes one issue worktree at a time", file=out)
    print("7. codex results are applied, branch updates are pushed, and PR status is updated", file=out)
    print("8. state is persisted and loop sleeps before next poll", file=out)
    print("9. loop exits only on interrupt", file=out)
    print(file=out)
    print("dry-run only: no clone, no codex execution, no commit, no push, and no PR update was performed.", file=out)
    return 0


__all__ = ["run_doctor", "run_dry_run", "CheckResult"]
