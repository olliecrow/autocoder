from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from autocoder import run


def test_run_session_releases_lock_when_initialization_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    released = False

    class _Lock:
        def release(self) -> None:
            nonlocal released
            released = True

    def fail_initialization(**kwargs) -> None:
        raise RuntimeError("initialization failed")

    monkeypatch.setattr(run.signal, "signal", lambda *args: None)
    monkeypatch.setattr(run, "ensure_instance_id", lambda path: "instance-id")
    monkeypatch.setattr(
        run,
        "load_config",
        lambda **kwargs: SimpleNamespace(allowed_github_logins=(), mentions=()),
    )
    monkeypatch.setattr(run, "managed_clone_dir", lambda repo: tmp_path / "repo")
    monkeypatch.setattr(run, "repo_state_dir", lambda repo: tmp_path / "state")
    monkeypatch.setattr(run, "acquire_session_lock", lambda **kwargs: _Lock())
    monkeypatch.setattr(run, "_ensure_managed_clone", fail_initialization)

    with pytest.raises(RuntimeError, match="initialization failed"):
        run.run_session(repo_ssh_url="git@github.com:owner/repo.git")

    assert released
