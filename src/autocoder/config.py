from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tomllib


@dataclass(frozen=True)
class Config:
    # GitHub handles (without @) to mention when autocoder needs info.
    mentions: tuple[str, ...] = ()


def _load_toml(path: Path) -> dict:
    if not path.exists():
        return {}
    return tomllib.loads(path.read_text(encoding="utf-8"))


def load_config(*, global_path: Path, repo_path: Path) -> Config:
    g = _load_toml(global_path)
    r = _load_toml(repo_path)

    mentions = r.get("mentions", g.get("mentions", []))
    if mentions is None:
        mentions = []
    if isinstance(mentions, str):
        mentions = [mentions]
    if not isinstance(mentions, list):
        mentions = []

    # Normalize to logins without leading '@'
    norm = []
    for m in mentions:
        if not isinstance(m, str):
            continue
        s = m.strip()
        if not s:
            continue
        if s.startswith("@"):
            s = s[1:]
        norm.append(s)

    return Config(mentions=tuple(norm))

