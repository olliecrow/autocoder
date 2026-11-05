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
        lambda **kwargs: SimpleNamespace(allowed_github_logins=("trusted-user",), mentions=()),
    )
    monkeypatch.setattr(run, "managed_clone_dir", lambda repo: tmp_path / "repo")
    monkeypatch.setattr(run, "repo_state_dir", lambda repo: tmp_path / "state")
    monkeypatch.setattr(run, "acquire_session_lock", lambda **kwargs: _Lock())
    monkeypatch.setattr(run, "_ensure_managed_clone", fail_initialization)

    with pytest.raises(RuntimeError, match="initialization failed"):
        run.run_session(repo_ssh_url="git@github.com:owner/repo.git")

    assert released


@pytest.mark.parametrize('case', ['url', 'empty', 'toml', 'timeout', 'state'])
def test_setup_errors_are_clear_before_external_actions(tmp_path, monkeypatch, capsys, case):
    from autocoder.config import Config
    monkeypatch.setattr(run, 'instance_id_path', lambda: tmp_path / 'home' / 'instance_id')
    monkeypatch.setattr(run, 'repo_state_dir', lambda repo: tmp_path / 'state')
    monkeypatch.setattr(run, 'load_config', lambda **kwargs: Config(allowed_github_logins=('trusted-user',)))
    if case == 'empty':
        monkeypatch.setattr(run, 'load_config', lambda **kwargs: Config())
    if case == 'toml':
        def bad_config(**kwargs):
            raise ValueError('invalid TOML')
        monkeypatch.setattr(run, 'load_config', bad_config)
    if case == 'timeout':
        monkeypatch.setenv('AUTOCODER_CODEX_TIMEOUT_S', 'bad')
    if case == 'state':
        (tmp_path / 'state').mkdir()
        (tmp_path / 'state' / 'state.json').write_text('{')
    monkeypatch.setattr(run, 'acquire_session_lock', lambda **kwargs: pytest.fail('must fail before lock'))
    url = 'bad' if case == 'url' else 'git@github.com:owner/repo.git'
    assert run.run_session(repo_ssh_url=url) == 2
    err = capsys.readouterr().err
    assert err.startswith('autocoder: error: ')
    assert 'Traceback' not in err


def test_instance_directory_is_private(tmp_path):
    from autocoder.instance import ensure_instance_id
    path = tmp_path / 'home' / 'instance_id'
    path.parent.mkdir(mode=0o755)
    ensure_instance_id(path)
    assert path.parent.stat().st_mode & 0o777 == 0o700
    assert path.stat().st_mode & 0o777 == 0o600
