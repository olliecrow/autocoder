from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Any

from ._runner import Runner


_CODEX_MODEL = "gpt-5.4"
_CODEX_REASONING_EFFORT = "high"
_CODEX_SANDBOX = "danger-full-access"
_CODEX_APPROVAL_POLICY = "never"


def _read_timeout_s() -> int:
    raw = (os.environ.get("AUTOCODER_CODEX_TIMEOUT_S") or "").strip()
    if not raw:
        return 36000
    try:
        v = int(raw)
        if v <= 0:
            return 36000
        return v
    except ValueError:
        return 36000


_CODEX_TIMEOUT_S = _read_timeout_s()


@dataclass(frozen=True)
class CodexOutput:
    decision: str
    issue_comment_markdown: str | None
    pr_comment_markdown: str | None
    pr_title: str | None
    pr_body_markdown: str | None
    commit_message: str | None
    tests_ran: tuple[str, ...]


_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "decision": {
            "type": "string",
            "enum": ["needs_info", "ready", "no_action"],
        },
        "issue_comment_markdown": {"type": ["string", "null"]},
        "pr_comment_markdown": {"type": ["string", "null"]},
        "pr_title": {"type": ["string", "null"]},
        "pr_body_markdown": {"type": ["string", "null"]},
        "commit_message": {"type": ["string", "null"]},
        "tests_ran": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "decision",
        "issue_comment_markdown",
        "pr_comment_markdown",
        "pr_title",
        "pr_body_markdown",
        "commit_message",
        "tests_ran",
    ],
}


class CodexClient:
    def __init__(self, *, runner: Runner):
        self._runner = runner

    def run_exec(
        self,
        *,
        workdir: Path,
        prompt: str,
        schema_path: Path,
        output_path: Path,
    ) -> CodexOutput:
        schema_path.parent.mkdir(parents=True, exist_ok=True)
        schema_path.write_text(json.dumps(_OUTPUT_SCHEMA, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.unlink(missing_ok=True)

        # Use stdin for the prompt to avoid shell quoting issues.
        self._runner.run(
            [
                "codex",
                "-a",
                _CODEX_APPROVAL_POLICY,
                "-m",
                _CODEX_MODEL,
                "-c",
                f'model_reasoning_effort="{_CODEX_REASONING_EFFORT}"',
                "exec",
                "-s",
                _CODEX_SANDBOX,
                "-C",
                str(workdir),
                "--output-schema",
                str(schema_path),
                "--output-last-message",
                str(output_path),
                "-",
            ],
            input_text=prompt,
            timeout_s=float(_CODEX_TIMEOUT_S),
            check=True,
        )

        raw = output_path.read_text(encoding="utf-8").strip()
        data = json.loads(raw)
        return CodexOutput(
            decision=data["decision"],
            issue_comment_markdown=data["issue_comment_markdown"],
            pr_comment_markdown=data["pr_comment_markdown"],
            pr_title=data["pr_title"],
            pr_body_markdown=data["pr_body_markdown"],
            commit_message=data["commit_message"],
            tests_ran=tuple(data.get("tests_ran") or []),
        )
