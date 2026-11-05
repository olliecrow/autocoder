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
    assert _process_ends(int(path.read_text().strip()))


def _process_ends(pid, timeout_s=5.0):
    """True once `pid` is gone or a zombie; a killed orphan waits for the host init process to reap it."""
    import os
    import time
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            state = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()[0]
        except FileNotFoundError:
            state = None
        if state is None:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return True
        elif state == 'Z':
            return True
        time.sleep(0.02)
    return False


@pytest.mark.parametrize("stop", ["interrupt", "timeout"])
def test_runner_stops_whole_group_gracefully(tmp_path, stop):
    import signal

    from autocoder._runner import CommandTimeout, SubprocessRunner
    lock, child_pid = tmp_path / 'index.lock', tmp_path / 'child.pid'
    # Like git: clean up the lock on SIGTERM. The background sleep stands in for ssh.
    script = (f'trap \'rm -f "{lock}"; exit 143\' TERM; : > "{lock}"; '
              f'sleep 30 & echo $! > "{child_pid}"; wait')

    def interrupt(*_args):
        raise KeyboardInterrupt  # what autocoder's SIGTERM handler does

    previous = signal.signal(signal.SIGALRM, interrupt)
    try:
        if stop == "interrupt":
            signal.setitimer(signal.ITIMER_REAL, 0.5)
            with pytest.raises(KeyboardInterrupt):
                SubprocessRunner().run(['sh', '-c', script])
        else:
            with pytest.raises(CommandTimeout):
                SubprocessRunner().run(['sh', '-c', script], timeout_s=0.5)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)
    assert not lock.exists()
    assert _process_ends(int(child_pid.read_text()))
