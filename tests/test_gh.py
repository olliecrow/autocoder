from __future__ import annotations

import json
from pathlib import Path

from autocoder._runner import CmdResult, Runner
from autocoder.gh import GhClient


class _RecordingRunner(Runner):
    def __init__(self) -> None:
        self.calls: list[tuple[list[str], str | None]] = []

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
        self.calls.append((argv, input_text))

        if argv[:3] == ["gh", "pr", "create"]:
            return CmdResult(args=argv, returncode=0, stdout="https://example.test/pr/123\n", stderr="")
        if argv[:3] == ["gh", "repo", "view"]:
            return CmdResult(args=argv, returncode=0, stdout="main\n", stderr="")
        if argv[:3] == ["gh", "pr", "view"]:
            payload = {
                "number": 123,
                "title": "t",
                "url": "https://example.test/pr/123",
                "state": "OPEN",
                "updatedAt": "2026-02-13T00:00:00Z",
                "author": {"login": "olliecrow"},
                "headRefName": "branch",
                "baseRefName": "main",
                "isCrossRepository": False,
                "mergedAt": None,
                "body": "b",
            }
            return CmdResult(args=argv, returncode=0, stdout=json.dumps(payload), stderr="")

        return CmdResult(args=argv, returncode=0, stdout="", stderr="")


def test_issue_comment_uses_body_file_stdin() -> None:
    runner = _RecordingRunner()
    gh = GhClient(runner=runner, repo="owner/repo")

    body = "line1\nline2\n"
    gh.issue_comment(number=1, body=body)

    assert len(runner.calls) == 1
    argv, input_text = runner.calls[0]
    assert argv == ["gh", "issue", "comment", "1", "--body-file", "-", "-R", "owner/repo"]
    assert input_text == body


def test_repo_default_branch_uses_positional_repo_arg() -> None:
    runner = _RecordingRunner()
    gh = GhClient(runner=runner, repo="owner/repo")

    b = gh.repo_default_branch()

    assert b == "main"
    assert len(runner.calls) == 1
    argv, input_text = runner.calls[0]
    assert argv[:4] == ["gh", "repo", "view", "owner/repo"]
    assert "-R" not in argv
    assert input_text is None


def test_pr_comment_uses_body_file_stdin() -> None:
    runner = _RecordingRunner()
    gh = GhClient(runner=runner, repo="owner/repo")

    body = "hello\n"
    gh.pr_comment(number=2, body=body)

    assert len(runner.calls) == 1
    argv, input_text = runner.calls[0]
    assert argv == ["gh", "pr", "comment", "2", "--body-file", "-", "-R", "owner/repo"]
    assert input_text == body


def test_create_pr_uses_body_file_stdin() -> None:
    runner = _RecordingRunner()
    gh = GhClient(runner=runner, repo="owner/repo")

    body = "body\n"
    pr = gh.create_pr(title="t", body=body, base="main", head="branch")

    assert pr.number == 123
    assert len(runner.calls) == 2

    argv0, input_text0 = runner.calls[0]
    assert argv0[:3] == ["gh", "pr", "create"]
    assert "--body-file" in argv0
    assert "-" in argv0
    assert input_text0 == body

    argv1, input_text1 = runner.calls[1]
    assert argv1[:3] == ["gh", "pr", "view"]
    assert input_text1 is None


def test_edit_pr_uses_body_file_stdin_when_body_is_set() -> None:
    runner = _RecordingRunner()
    gh = GhClient(runner=runner, repo="owner/repo")

    body = "new body\n"
    gh.edit_pr(number=3, title="new title", body=body)

    assert len(runner.calls) == 1
    argv, input_text = runner.calls[0]
    assert argv[:4] == ["gh", "pr", "edit", "3"]
    assert "--title" in argv
    assert "--body-file" in argv
    assert input_text == body
