from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True)
class LocalSkill:
    name: str
    description: str
    path: Path


def _candidate_skill_roots(*, env: Mapping[str, str] | None = None, home: Path | None = None) -> tuple[Path, ...]:
    env_map = os.environ if env is None else env
    home_dir = Path.home() if home is None else home

    roots: list[Path] = []

    codex_home = (env_map.get("CODEX_HOME") or "").strip()
    if codex_home:
        roots.append(Path(codex_home).expanduser() / "skills")

    roots.append(home_dir / ".codex" / "skills")

    out: list[Path] = []
    seen: set[str] = set()
    for r in roots:
        key = str(r.resolve(strict=False))
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return tuple(out)


def _parse_skill_metadata(path: Path) -> tuple[str, str]:
    name = path.parent.name
    description = ""

    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return name, description

    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return name, description

    for line in lines[1:]:
        stripped = line.strip()
        if stripped == "---":
            break
        if ":" not in line:
            continue
        key, raw_val = line.split(":", 1)
        key = key.strip().lower()
        val = raw_val.strip().strip('"').strip("'")
        if key == "name" and val:
            name = val
        elif key == "description" and val:
            description = val
    return name, description


def discover_local_skills(
    *,
    env: Mapping[str, str] | None = None,
    home: Path | None = None,
    max_scan: int = 400,
) -> tuple[LocalSkill, ...]:
    found: list[LocalSkill] = []
    seen_paths: set[str] = set()

    for root in _candidate_skill_roots(env=env, home=home):
        if not root.is_dir():
            continue
        for skill_file in sorted(root.rglob("SKILL.md")):
            key = str(skill_file.resolve(strict=False))
            if key in seen_paths:
                continue
            seen_paths.add(key)

            name, description = _parse_skill_metadata(skill_file)
            found.append(LocalSkill(name=name, description=description, path=skill_file))

            if len(found) >= max_scan:
                break
        if len(found) >= max_scan:
            break

    found.sort(key=lambda s: (s.name.casefold(), str(s.path)))
    return tuple(found)


def render_skills_for_prompt(skills: tuple[LocalSkill, ...], *, max_items: int = 200) -> str:
    if not skills:
        return "\n".join(
            [
                "- Local skills are assumed to exist on this machine.",
                "- If discovery appears empty, inspect and use `~/.codex/skills` (and `$CODEX_HOME/skills` if set).",
            ]
        )

    lines: list[str] = []
    for s in skills[:max_items]:
        if s.description:
            lines.append(f"- {s.name}: {s.description} (path: {s.path})")
        else:
            lines.append(f"- {s.name} (path: {s.path})")

    hidden = len(skills) - len(skills[:max_items])
    if hidden > 0:
        lines.append(f"- ... plus {hidden} more locally available skills")

    return "\n".join(lines)
