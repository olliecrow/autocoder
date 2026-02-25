from __future__ import annotations

from pathlib import Path

from autocoder.git import ensure_local_excludes


def test_ensure_local_excludes_appends_and_dedupes(tmp_path: Path) -> None:
    repo_dir = tmp_path / "repo"
    (repo_dir / ".git" / "info").mkdir(parents=True)
    exclude = repo_dir / ".git" / "info" / "exclude"
    exclude.write_text(".env\n", encoding="utf-8")

    ensure_local_excludes(repo_dir=repo_dir, patterns=[".env", ".autocoder/", ""])

    content = exclude.read_text(encoding="utf-8").splitlines()
    assert ".env" in content
    assert ".autocoder/" in content
    assert content.count(".env") == 1

