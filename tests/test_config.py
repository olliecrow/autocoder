from __future__ import annotations

from pathlib import Path

import pytest

from autocoder.config import load_config


def test_load_config_defaults_to_empty_allowlist_and_mentions(tmp_path: Path) -> None:
    cfg = load_config(
        global_path=tmp_path / "global.toml",
        repo_path=tmp_path / "repo.toml",
    )

    assert cfg.allowed_github_logins == ()
    assert cfg.mentions == ()


def test_load_config_repo_overrides_global_login_lists(tmp_path: Path) -> None:
    global_path = tmp_path / "global.toml"
    repo_path = tmp_path / "repo.toml"
    global_path.write_text(
        '\n'.join(
            [
                'allowed_github_logins = ["@alice", "bob"]',
                'mentions = ["@alice"]',
                "",
            ]
        ),
        encoding="utf-8",
    )
    repo_path.write_text(
        '\n'.join(
            [
                'allowed_github_logins = ["@carol", "carol", ""]',
                'mentions = ["@dave"]',
                "",
            ]
        ),
        encoding="utf-8",
    )

    cfg = load_config(global_path=global_path, repo_path=repo_path)

    assert cfg.allowed_github_logins == ("carol",)
    assert cfg.mentions == ("dave",)


@pytest.mark.parametrize(
    "line",
    [
        "allowed_github_logins = 3",
        'allowed_github_logins = ["alice", 3]',
        "mentions = true",
    ],
)
def test_load_config_rejects_invalid_login_lists(tmp_path: Path, line: str) -> None:
    global_path = tmp_path / "global.toml"
    global_path.write_text(line + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="invalid config key"):
        load_config(global_path=global_path, repo_path=tmp_path / "repo.toml")
