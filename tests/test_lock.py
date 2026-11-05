from __future__ import annotations

import json
import os

import pytest

from autocoder.lock import acquire_session_lock


def test_lock_excludes_second_holder_and_releases(tmp_path):
    path = tmp_path / 'session.lock'
    lock = acquire_session_lock(path=path, metadata={'repo': 'owner/repo'})
    try:
        assert json.loads(path.read_text())['pid'] == os.getpid()
        assert path.stat().st_mode & 0o777 == 0o600
        with pytest.raises(RuntimeError, match='already running'):
            acquire_session_lock(path=path)
    finally:
        lock.release()
    lock.release()
    second = acquire_session_lock(path=path)
    second.release()


@pytest.mark.parametrize('content', ['', 'malformed', '{"pid": 1}'])
def test_stale_file_does_not_block_acquisition(tmp_path, content):
    path = tmp_path / 'session.lock'
    path.write_text(content)
    lock = acquire_session_lock(path=path)
    lock.release()
