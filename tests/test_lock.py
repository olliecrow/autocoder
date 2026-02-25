from __future__ import annotations

import json
from pathlib import Path

import pytest

from autocoder.lock import acquire_session_lock


def test_lock_acquire_and_release(tmp_path: Path) -> None:
    p = tmp_path / "session.lock"
    lock = acquire_session_lock(
        path=p,
        pid=123,
        metadata={"repo": "x/y"},
        is_pid_alive=lambda _: False,
    )
    assert p.exists()
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data["pid"] == 123
    assert data["repo"] == "x/y"

    lock.release()
    assert not p.exists()


def test_lock_rejects_live_pid(tmp_path: Path) -> None:
    p = tmp_path / "session.lock"
    p.write_text('{"pid": 999}\n', encoding="utf-8")
    with pytest.raises(RuntimeError):
        acquire_session_lock(path=p, pid=123, is_pid_alive=lambda pid: pid == 999)


def test_lock_replaces_stale_pid(tmp_path: Path) -> None:
    p = tmp_path / "session.lock"
    p.write_text('{"pid": 999}\n', encoding="utf-8")
    lock = acquire_session_lock(path=p, pid=123, is_pid_alive=lambda _: False)
    assert lock.pid == 123
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data["pid"] == 123

