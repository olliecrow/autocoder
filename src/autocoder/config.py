from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tomllib

from .security import normalize_login


@dataclass(frozen=True)
class Config:
    # GitHub handles (without @) to mention when autocoder needs info.
    mentions: tuple[str, ...] = ()
    # GitHub handles allowed to author trusted issues/PRs for this autocoder instance.
    allowed_github_logins: tuple[str, ...] = ()


def _load_toml(path: Path) -> dict:
    if not path.exists():
        return {}
    return tomllib.loads(path.read_text(encoding="utf-8"))


def _load_login_list(raw: object, *, key: str, source: Path | None) -> tuple[str, ...]:
    if raw is None:
        values: list[object] = []
    elif isinstance(raw, str):
        values = [raw]
    elif isinstance(raw, list):
        values = raw
    else:
        location = f" in {source}" if source is not None else ""
        raise ValueError(f"invalid config key {key}{location}: expected a string or list of strings")

    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, str):
            location = f" in {source}" if source is not None else ""
            raise ValueError(f"invalid config key {key}{location}: expected only strings")
        login = normalize_login(value)
        if not login or login in seen:
            continue
        seen.add(login)
        out.append(login)
    return tuple(out)


def load_config(*, global_path: Path, repo_path: Path) -> Config:
    g = _load_toml(global_path)
    r = _load_toml(repo_path)

    mentions_source = repo_path if "mentions" in r else global_path if "mentions" in g else None
    allowed_source = (
        repo_path
        if "allowed_github_logins" in r
        else global_path if "allowed_github_logins" in g else None
    )
    mentions = _load_login_list(
        r.get("mentions", g.get("mentions")),
        key="mentions",
        source=mentions_source,
    )
    allowed_github_logins = _load_login_list(
        r.get("allowed_github_logins", g.get("allowed_github_logins")),
        key="allowed_github_logins",
        source=allowed_source,
    )

    return Config(
        mentions=mentions,
        allowed_github_logins=allowed_github_logins,
    )
