from __future__ import annotations

from io import StringIO
from pathlib import Path

from autocoder._runner import CmdResult, Runner
from autocoder import preflight


class _FakeRunner(Runner):
    def __init__(self, mapping: dict[tuple[str, ...], CmdResult]) -> None:
        self.mapping = mapping

    def run(
        self,
        args,
        *,
        cwd: Path | None = None,
        env=None,
        input_text: str | None = None,
        timeout_s: float | None = None,
        check: bool = True,
    ) -> CmdResult:
        key = tuple(args)
        if key in self.mapping:
            return self.mapping[key]
        return CmdResult(args=list(args), returncode=0, stdout="", stderr="")


def test_run_doctor_passes_with_healthy_checks(monkeypatch) -> None:
    monkeypatch.setattr(preflight.shutil, "which", lambda tool: f"/usr/bin/{tool}")
    repo_url = "git@github.com:owner/repo.git"
    runner = _FakeRunner(
        mapping={
            ("gh", "auth", "status"): CmdResult(
                args=["gh", "auth", "status"], returncode=0, stdout="ok\n", stderr=""
            ),
            ("codex", "login", "status"): CmdResult(
                args=["codex", "login", "status"], returncode=0, stdout="ok\n", stderr=""
            ),
            ("git", "ls-remote", "--heads", repo_url): CmdResult(
                args=["git", "ls-remote", "--heads", repo_url],
                returncode=0,
                stdout="abc123\trefs/heads/main\n",
                stderr="",
            ),
        }
    )
    out = StringIO()
    rc = preflight.run_doctor(repo_ssh_url=repo_url, runner=runner, out=out)
    text = out.getvalue()
    assert rc == 0
    assert "autocoder doctor" in text
    assert "doctor result: PASS" in text


def test_run_dry_run_prints_plan() -> None:
    out = StringIO()
    rc = preflight.run_dry_run(repo_ssh_url="git@github.com:owner/repo.git", out=out)
    text = out.getvalue()
    assert rc == 0
    assert "autocoder dry-run" in text
    assert "planned order:" in text
    assert "dry-run only:" in text
