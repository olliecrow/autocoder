from __future__ import annotations

from pathlib import Path
import uuid


def ensure_instance_id(path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    inst = str(uuid.uuid4())
    path.write_text(inst + "\n", encoding="utf-8")
    return inst

