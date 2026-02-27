from __future__ import annotations

import pytest

from autocoder import cli


def test_cli_run_routes_to_run_session(monkeypatch) -> None:
    called: dict[str, str] = {}

    def _fake_run_session(*, repo_ssh_url: str) -> int:
        called["repo"] = repo_ssh_url
        return 17

    monkeypatch.setattr(cli, "run_session", _fake_run_session)

    rc = cli.main(["run", "git@github.com:owner/repo.git"])
    assert rc == 17
    assert called["repo"] == "git@github.com:owner/repo.git"


def test_cli_doctor_routes_to_run_doctor(monkeypatch) -> None:
    called: dict[str, str] = {}

    def _fake_doctor(*, repo_ssh_url: str) -> int:
        called["repo"] = repo_ssh_url
        return 23

    monkeypatch.setattr(cli, "run_doctor", _fake_doctor)

    rc = cli.main(["doctor", "git@github.com:owner/repo.git"])
    assert rc == 23
    assert called["repo"] == "git@github.com:owner/repo.git"


def test_cli_dry_run_routes_to_run_dry_run(monkeypatch) -> None:
    called: dict[str, str] = {}

    def _fake_dry_run(*, repo_ssh_url: str) -> int:
        called["repo"] = repo_ssh_url
        return 29

    monkeypatch.setattr(cli, "run_dry_run", _fake_dry_run)

    rc = cli.main(["dry-run", "git@github.com:owner/repo.git"])
    assert rc == 29
    assert called["repo"] == "git@github.com:owner/repo.git"


@pytest.mark.parametrize("shell", ["bash", "zsh"])
def test_cli_completion_prints_script(shell: str, capsys: pytest.CaptureFixture[str]) -> None:
    rc = cli.main(["completion", shell])
    out = capsys.readouterr().out
    assert rc == 0
    assert "autocoder" in out


def test_parser_help_mentions_completion_install() -> None:
    help_text = cli._build_parser().format_help()
    assert "completion" in help_text
    assert "autocoder completion zsh" in help_text
