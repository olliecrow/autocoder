from __future__ import annotations

import json
from pathlib import Path

from autocoder._runner import CmdResult, Runner
from autocoder import codex as codex_mod
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
    ) -> CmdResult:
        argv = list(args)
        self.calls.append((argv, str(cwd) if cwd else None, input_text, timeout_s, check))

        out_idx = argv.index("--output-last-message")
        out_path = Path(argv[out_idx + 1])
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(self.payload), encoding="utf-8")

        return CmdResult(args=argv, returncode=0, stdout="", stderr="")


def test_run_exec_pins_model_reasoning_and_yolo(tmp_path: Path) -> None:
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
    assert argv[:6] == ["codex", "-a", "never", "-m", "gpt-5.4", "-c"]
    assert 'model_reasoning_effort="high"' in argv
    assert "exec" in argv
    assert "-s" in argv
    assert "danger-full-access" in argv
    assert cwd is None
    assert input_text == "do work"
    assert timeout_s is not None and timeout_s > 0
    assert check is True


def test_read_timeout_s_default_is_ten_hours(monkeypatch) -> None:
    monkeypatch.delenv("AUTOCODER_CODEX_TIMEOUT_S", raising=False)
    assert codex_mod._read_timeout_s() == 36000


def test_read_timeout_s_invalid_falls_back_to_ten_hours(monkeypatch) -> None:
    monkeypatch.setenv("AUTOCODER_CODEX_TIMEOUT_S", "not-a-number")
    assert codex_mod._read_timeout_s() == 36000
    monkeypatch.setenv("AUTOCODER_CODEX_TIMEOUT_S", "0")
    assert codex_mod._read_timeout_s() == 36000
