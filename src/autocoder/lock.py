from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import time
from typing import Any, Callable


def _default_is_pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


@dataclass(frozen=True)
class SessionLock:
    path: Path
    pid: int

    def release(self) -> None:
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return
        if data.get("pid") != self.pid:
            return
        self.path.unlink(missing_ok=True)


def acquire_session_lock(
    *,
    path: Path,
    metadata: dict[str, Any] | None = None,
    pid: int | None = None,
    is_pid_alive: Callable[[int], bool] = _default_is_pid_alive,
) -> SessionLock:
    """
    Acquire an exclusive per-repo session lock.

    This prevents accidentally running multiple autocoder processes against the same
    repo concurrently (which can cause collisions and "rogue" background sessions).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    pid = int(os.getpid() if pid is None else pid)
    data = {
        "pid": pid,
        "created_at_epoch": int(time.time()),
        **(metadata or {}),
    }

    def _write_exclusive() -> None:
        fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(json.dumps(data, indent=2, sort_keys=True) + "\n")

    try:
        _write_exclusive()
    except FileExistsError:
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(
                f"autocoder session lock is unreadable or malformed: {path}"
            ) from exc
        if not isinstance(existing, dict):
            raise RuntimeError(f"autocoder session lock is malformed: {path}")

        ex_pid = existing.get("pid")
        if isinstance(ex_pid, bool) or not isinstance(ex_pid, int) or ex_pid <= 0:
            raise RuntimeError(f"autocoder session lock has no valid pid: {path}")
        if is_pid_alive(ex_pid):
            raise RuntimeError(f"autocoder session already running (pid {ex_pid})")

        # A valid lock owned by a dead process is stale and safe to replace.
        path.unlink(missing_ok=True)
        _write_exclusive()

    return SessionLock(path=path, pid=pid)
