from __future__ import annotations

import json
from pathlib import Path

import pytest

from autocoder import codex as codex_mod
from autocoder._runner import CmdResult, Runner
from autocoder.codex import CodexClient


class _RecordingRunner(Runner):
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.calls: list[tuple[list[str], str | None, str | None, float | None, bool]] = []

    def run(
        self,
        args,
        *,
        cwd: Path | None = None,
        env=None,
        input_text: str | None = None,
        timeout_s: float | None = None,
        check: bool = True,
        log_path: Path | None = None,
    ) -> CmdResult:
        argv = list(args)
        self.calls.append((argv, str(cwd) if cwd else None, input_text, timeout_s, check))

        out_idx = argv.index("--output-last-message")
        out_path = Path(argv[out_idx + 1])
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(self.payload), encoding="utf-8")

        return CmdResult(args=argv, returncode=0, stdout="", stderr="")


def test_run_exec_pins_model_reasoning_and_safe_sandbox(tmp_path: Path) -> None:
    runner = _RecordingRunner(
        payload={
            "decision": "ready",
            "issue_comment_markdown": "ok",
            "pr_comment_markdown": None,
            "pr_title": "t",
            "pr_body_markdown": "b",
            "commit_message": "m",
            "tests_ran": ["uv run pytest -q"],
        }
    )
    client = CodexClient(runner=runner)

    workdir = tmp_path / "worktree"
    workdir.mkdir(parents=True, exist_ok=True)
    schema_path = tmp_path / "schema.json"
    output_path = tmp_path / "last.json"

    out = client.run_exec(
        workdir=workdir,
        prompt="do work",
        schema_path=schema_path,
        output_path=output_path,
    )

    assert out.decision == "ready"
    assert out.tests_ran == ("uv run pytest -q",)
    assert len(runner.calls) == 1

    argv, cwd, input_text, timeout_s, check = runner.calls[0]
    assert argv[:6] == ["codex", "-a", "never", "-m", "gpt-5.6-sol", "-c"]
    assert 'model_reasoning_effort="high"' in argv
    assert "exec" in argv
    assert "-s" in argv
    assert "workspace-write" in argv
    assert cwd is None
    assert input_text == "do work"
    assert timeout_s is not None and timeout_s > 0
    assert check is True


def test_read_timeout_s_default_is_ten_hours(monkeypatch) -> None:
    monkeypatch.delenv("AUTOCODER_CODEX_TIMEOUT_S", raising=False)
    assert codex_mod._read_timeout_s() == 36000


def test_read_timeout_s_rejects_invalid_values(monkeypatch) -> None:
    monkeypatch.setenv("AUTOCODER_CODEX_TIMEOUT_S", "not-a-number")
    with pytest.raises(ValueError, match="must be an integer"):
        codex_mod._read_timeout_s()
    monkeypatch.setenv("AUTOCODER_CODEX_TIMEOUT_S", "0")
    with pytest.raises(ValueError, match="greater than zero"):
        codex_mod._read_timeout_s()


def test_logged_runner_streams_and_times_out_process_group(tmp_path):
    import os
    import sys

    from autocoder._runner import CommandTimeout, SubprocessRunner
    path = tmp_path / 'run.log'
    runner = SubprocessRunner()
    runner.run([sys.executable, '-c', 'print("output")'], log_path=path)
    assert path.read_text().strip() == 'output'
    assert path.stat().st_mode & 0o777 == 0o600
    script = ('import subprocess,sys,time; '
              'p=subprocess.Popen([sys.executable,"-c","import time; time.sleep(60)"]); '
              'print(p.pid,flush=True); time.sleep(60)')
    with pytest.raises(CommandTimeout):
        runner.run([sys.executable, '-c', script], log_path=path, timeout_s=0.2)
    child = int(path.read_text().strip())
    stat = Path(f'/proc/{child}/stat')
    # A killed orphan can remain a zombie until the host init process reaps it.
    if stat.exists():
        assert stat.read_text().split()[2] == 'Z'
    else:
        with pytest.raises(ProcessLookupError):
            os.kill(child, 0)
