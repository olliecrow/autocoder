from __future__ import annotations

import fcntl
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class SessionLock:
    path: Path
    fd: int | None

    def release(self) -> None:
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None


def acquire_session_lock(*, path: Path, metadata: dict[str, Any] | None = None) -> SessionLock:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        os.fchmod(fd, 0o600)
        data = {**(metadata or {}), 'pid': os.getpid(), 'created_at_epoch': int(time.time())}
        os.ftruncate(fd, 0)
        os.write(fd, (json.dumps(data, sort_keys=True) + '\n').encode())
    except BlockingIOError as exc:
        os.close(fd)
        raise RuntimeError('autocoder session already running for this repo') from exc
    except BaseException:
        os.close(fd)
        raise
    return SessionLock(path=path, fd=fd)
