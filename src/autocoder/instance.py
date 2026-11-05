from __future__ import annotations

import os
import uuid
from pathlib import Path


def ensure_instance_id(path: Path) -> str:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.parent.chmod(0o700)
    if path.exists():
        path.chmod(0o600)
        return path.read_text(encoding="utf-8").strip()
    inst = str(uuid.uuid4())
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as output:
        output.write(inst + "\n")
    return inst

