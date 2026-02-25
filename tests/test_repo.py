from __future__ import annotations

import pytest

from autocoder.repo import parse_repo_ssh_url, remote_matches_repo, slugify


def test_parse_repo_ssh_url_scplike() -> None:
    r = parse_repo_ssh_url("git@github.com:owner/repo.git")
    assert r.host == "github.com"
    assert r.owner == "owner"
    assert r.name == "repo"
    assert r.full_name == "owner/repo"
    assert r.ssh_url == "git@github.com:owner/repo.git"
    assert remote_matches_repo(r, "git@github.com:owner/repo.git")
    assert remote_matches_repo(r, "ssh://git@github.com/owner/repo.git")
    assert remote_matches_repo(r, "https://github.com/owner/repo.git")
    assert not remote_matches_repo(r, "git@github.com:owner/repo-fork.git")


def test_parse_repo_ssh_url_ssh_scheme() -> None:
    r = parse_repo_ssh_url("ssh://git@github.com/owner/repo.git")
    assert r.host == "github.com"
    assert r.owner == "owner"
    assert r.name == "repo"


@pytest.mark.parametrize("bad", ["", "github.com/owner/repo", "git@github.com:owner/repo/extra.git"])
def test_parse_repo_ssh_url_rejects(bad: str) -> None:
    with pytest.raises(ValueError):
        parse_repo_ssh_url(bad)


def test_slugify() -> None:
    assert slugify("Hello, world!") == "hello-world"
    assert slugify("  $$$  ") == "issue"
    assert slugify("a" * 200, max_len=10) == "a" * 10
