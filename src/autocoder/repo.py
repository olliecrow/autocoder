from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class RepoSpec:
    host: str
    owner: str
    name: str
    ssh_url: str

    @property
    def full_name(self) -> str:
        return f"{self.owner}/{self.name}"


_SSH_SCPLIKE_RE = re.compile(r"^(?P<user>[^@]+)@(?P<host>[^:]+):(?P<path>.+)$")
_SSH_URL_RE = re.compile(r"^ssh://(?P<user>[^@]+)@(?P<host>[^/]+)/(?P<path>.+)$")
_HTTPS_URL_RE = re.compile(r"^https?://(?P<host>[^/]+)/(?P<path>.+)$")
_GITHUB_HOST = "github.com"
_GITHUB_OWNER_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$")
_GITHUB_REPO_RE = re.compile(r"^[A-Za-z0-9._-]{1,100}$")


def _is_valid_repo_path(*, owner: str, name: str) -> bool:
    return bool(
        _GITHUB_OWNER_RE.fullmatch(owner)
        and _GITHUB_REPO_RE.fullmatch(name)
        and name not in {".", ".."}
    )


def parse_repo_ssh_url(repo_ssh_url: str) -> RepoSpec:
    """
    Parse common SSH clone URL formats:
    - git@github.com:owner/repo.git
    - ssh://git@github.com/owner/repo.git
    """

    for rx in (_SSH_SCPLIKE_RE, _SSH_URL_RE):
        m = rx.match(repo_ssh_url.strip())
        if not m:
            continue
        host = m.group("host").lower()
        if host != _GITHUB_HOST:
            break
        path = m.group("path")
        if path.endswith(".git"):
            path = path[:-4]
        if path.count("/") != 1:
            break
        owner, name = path.split("/", 1)
        if not _is_valid_repo_path(owner=owner, name=name):
            break
        return RepoSpec(host=host, owner=owner, name=name, ssh_url=repo_ssh_url.strip())

    raise ValueError(f"unsupported repo SSH URL format: {repo_ssh_url!r}")


def remote_matches_repo(repo: RepoSpec, remote_url: str) -> bool:
    """
    Best-effort guardrail: confirm a git remote URL points at the same `owner/name`.

    Supports common git remote URL formats (ssh scp-like, ssh://, https://).
    """
    u = (remote_url or "").strip()
    if not u:
        return False

    for rx in (_SSH_SCPLIKE_RE, _SSH_URL_RE, _HTTPS_URL_RE):
        m = rx.match(u)
        if not m:
            continue
        host = m.group("host").lower()
        if host != repo.host.lower():
            return False
        path = m.group("path")
        if path.endswith(".git"):
            path = path[:-4]
        path = path.lstrip("/")
        return path.casefold() == f"{repo.owner}/{repo.name}".casefold()

    return False


def slugify(text: str, *, max_len: int = 50) -> str:
    """
    Produce a conservative branch-safe slug.
    """
    s = text.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    if not s:
        return "issue"
    return s[:max_len].rstrip("-")
