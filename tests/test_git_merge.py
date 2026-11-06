from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from autocoder._runner import SubprocessRunner
from autocoder.git import GitClient


@pytest.fixture
def repo(tmp_path: Path, monkeypatch) -> Path:
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    for key in ("GIT_AUTHOR_NAME", "GIT_COMMITTER_NAME"):
        monkeypatch.setenv(key, "test")
    for key in ("GIT_AUTHOR_EMAIL", "GIT_COMMITTER_EMAIL"):
        monkeypatch.setenv(key, "test@example.com")
    path = tmp_path / "repo"
    path.mkdir()
    _git(path, "init", "-q", "-b", "main")
    (path / "f.txt").write_text("base\n", encoding="utf-8")
    _git(path, "add", "-A")
    _git(path, "commit", "-q", "-m", "base")
    _git(path, "branch", "issue")
    return path


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout


def _commit_file(repo: Path, branch: str, name: str, text: str) -> None:
    _git(repo, "checkout", "-q", branch)
    (repo / name).write_text(text, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", f"{branch} change")


def test_merge_creates_merge_commit_when_clean(repo: Path) -> None:
    _commit_file(repo, "main", "main.txt", "main\n")
    _commit_file(repo, "issue", "issue.txt", "issue\n")
    git = GitClient(runner=SubprocessRunner())

    assert git.merge(cwd=repo, ref="main") is True
    assert len(_git(repo, "rev-list", "--parents", "-n1", "HEAD").split()) == 3
    assert git.is_ancestor(cwd=repo, ancestor="main", descendant="issue")


def test_merge_leaves_conflicts_for_resolution_then_commit_completes_it(repo: Path) -> None:
    _commit_file(repo, "main", "f.txt", "main\n")
    _commit_file(repo, "issue", "f.txt", "issue\n")
    git = GitClient(runner=SubprocessRunner())

    assert git.merge(cwd=repo, ref="main") is False
    assert git.has_in_progress_operation(cwd=repo)
    # Codex edits the file content only; autocoder stages and commits outside the sandbox.
    (repo / "f.txt").write_text("resolved\n", encoding="utf-8")
    git.add_all(cwd=repo)
    git.commit(cwd=repo, message="resolve")

    assert not git.has_in_progress_operation(cwd=repo)
    assert git.is_ancestor(cwd=repo, ancestor="main", descendant="issue")


def test_scan_excludes_upstream_blobs_but_keeps_conflict_resolutions(repo: Path) -> None:
    _commit_file(repo, "main", "f.txt", "from main\n")
    _commit_file(repo, "main", "upstream.txt", "already on the default branch\n")
    _commit_file(repo, "issue", "f.txt", "from issue\n")
    _git(repo, "branch", "pushed")  # what the remote issue branch already has
    _commit_file(repo, "issue", "new.txt", "new outgoing line\n")
    git = GitClient(runner=SubprocessRunner())
    assert git.merge(cwd=repo, ref="main") is False
    (repo / "f.txt").write_text("resolved line\n", encoding="utf-8")
    git.add_all(cwd=repo)
    git.commit(cwd=repo, message="merge main")

    added = "\n".join(git.outgoing_scan_text(cwd=repo, exclude_refs=["main", "pushed"])).splitlines()

    assert "new outgoing line" in added
    assert "resolved line" in added
    assert "already on the default branch" not in added
    assert "from issue" not in added


def test_conflict_guard_accepts_codex_edits_without_staging(repo):
    _commit_file(repo, "main", "f.txt", "main\n")
    _commit_file(repo, "issue", "f.txt", "issue\n")
    git = GitClient(runner=SubprocessRunner())
    assert not git.merge(cwd=repo, ref="main")
    assert git.unresolved_conflict_paths(cwd=repo) == ["f.txt"]
    # Sandboxed Codex edits file contents only; the index stays unmerged.
    (repo / "f.txt").write_text("Title\n=======\nissue\nmain\n")  # a lone ======= is a heading underline
    assert git.unresolved_conflict_paths(cwd=repo) == []
    for leftover in ("<<<<<<< HEAD\n", ">>>>>>> main\r\n", "||||||| base\n", "<<<<<<<\n"):
        (repo / "f.txt").write_text("issue\n" + leftover)
        assert git.unresolved_conflict_paths(cwd=repo) == ["f.txt"], leftover
    (repo / "f.txt").write_text("resolved\n")
    git.add_all(cwd=repo)
    assert git.unresolved_conflict_paths(cwd=repo) == []
    git.commit(cwd=repo, message="merge main")
    assert len(_git(repo, "rev-list", "--parents", "-n1", "HEAD").split()) == 3


def test_conflict_guard_blocks_wide_diff3_markers(repo):
    # The marker size has to be on the branch that is merged into. Git reads it
    # from that worktree while it writes the conflict.
    (repo / ".gitattributes").write_text("f.txt conflict-marker-size=10\n", encoding="utf-8")
    _git(repo, "add", ".gitattributes")
    _git(repo, "commit", "-qm", "attrs")
    _git(repo, "checkout", "-q", "issue")
    _git(repo, "checkout", "main", "--", ".gitattributes")
    _git(repo, "commit", "-qm", "attrs")
    _git(repo, "checkout", "-q", "main")
    _git(repo, "config", "merge.conflictStyle", "diff3")
    _commit_file(repo, "main", "f.txt", "main\n")
    _commit_file(repo, "issue", "f.txt", "issue\n")
    git = GitClient(runner=SubprocessRunner())

    assert not git.merge(cwd=repo, ref="main")
    text = (repo / "f.txt").read_text(encoding="utf-8")
    assert "||||||||||" in text  # diff3 base marker at the configured width
    assert git.unresolved_conflict_paths(cwd=repo) == ["f.txt"]
    # Six marker characters are below the default and this file's configured size.
    (repo / "f.txt").write_text("issue\n<<<<<< note\n", encoding="utf-8")
    assert git.unresolved_conflict_paths(cwd=repo) == []
    (repo / "f.txt").write_text(text, encoding="utf-8")
    _git(repo, "add", "f.txt")  # staging must not hide the original conflict path
    assert git.unresolved_conflict_paths(cwd=repo, also=["f.txt"]) == ["f.txt"]


def test_conflict_guard_ignores_heading_underlines_outside_a_merge(repo):
    (repo / "README.md").write_text("Install\n=======\n\nRun it.\n")
    _git(repo, "add", "README.md")
    assert GitClient(runner=SubprocessRunner()).unresolved_conflict_paths(cwd=repo) == []


@pytest.mark.parametrize("location", ["filename", "message", "binary", "text"])
def test_outgoing_scan_catches_secret_in_each_surface(repo, location):
    from autocoder.security import contains_likely_secret
    base = _git(repo, "rev-parse", "HEAD").strip()
    token = "ghp_" + "A" * 30
    name = token if location == "filename" else "new"
    content = b"\x00" + token.encode() if location == "binary" else (
        token.encode() if location == "text" else b"base\n")
    (repo / name).write_bytes(content)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", token if location == "message" else "change")
    git = GitClient(runner=SubprocessRunner())
    assert any(contains_likely_secret(text) for text in git.outgoing_scan_text(cwd=repo, exclude_refs=[base]))


@pytest.mark.parametrize("prefix", [b"\xff\x00", b"x" * (2 * 1024 * 1024)])
def test_outgoing_scan_reads_binary_and_large_blobs(repo, prefix, monkeypatch):
    from autocoder.security import contains_likely_secret
    base = _git(repo, "rev-parse", "HEAD").strip()
    (repo / "image.bin").write_bytes(prefix + b"\x89PNG\x00\xfe")
    (repo / "secret.bin").write_bytes(prefix + b"\x00" + ("ghp_" + "A" * 30).encode())
    (repo / "notes.txt").write_text("caf\u00e9 " + "pass\u00e9-value-123\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "change")
    texts = list(GitClient(runner=SubprocessRunner()).outgoing_scan_text(cwd=repo, exclude_refs=[base]))
    assert sum(contains_likely_secret(text) for text in texts) == 1
    monkeypatch.setenv("NOTES_PASSWORD", "pass\u00e9-value-123")  # a non-ASCII value still matches UTF-8 text
    assert sum(contains_likely_secret(text) for text in texts) == 2


def test_outgoing_scan_blocks_files_over_github_limit(repo, monkeypatch):
    import autocoder.git as git_module
    monkeypatch.setattr(git_module, "_MAX_BLOB_BYTES", 10)
    base = _git(repo, "rev-parse", "HEAD").strip()
    (repo / "new").write_bytes(b"x" * 11)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "change")
    with pytest.raises(RuntimeError, match="100 MiB"):
        list(GitClient(runner=SubprocessRunner()).outgoing_scan_text(cwd=repo, exclude_refs=[base]))


def test_outgoing_scan_fails_on_git_error(repo):
    from autocoder._runner import CommandError
    with pytest.raises(CommandError):
        list(GitClient(runner=SubprocessRunner()).outgoing_scan_text(cwd=repo, exclude_refs=["missing-ref"]))


@pytest.mark.parametrize("name", ["*.txt", "[ab].txt"])
def test_merge_staging_treats_glob_names_as_literal_paths(repo, name):
    (repo / "a.txt").write_text("a\n", encoding="utf-8")
    (repo / "keep.txt").write_text("base\n", encoding="utf-8")
    _git(repo, "add", "a.txt", "keep.txt")
    _git(repo, "commit", "-qm", "base files")
    _git(repo, "branch", "-f", "issue")
    _commit_file(repo, "main", "f.txt", "main\n")
    _commit_file(repo, "main", "a.txt", "a-main\n")
    _commit_file(repo, "main", "keep.txt", "main\n")
    _git(repo, "checkout", "-q", "issue")
    (repo / "f.txt").write_text("issue\n", encoding="utf-8")
    _git(repo, "commit", "-qam", "issue change")
    git = GitClient(runner=SubprocessRunner())
    assert git.merge(cwd=repo, ref="main") is False
    conflict = git.unmerged_paths(cwd=repo)
    already = [path for path in git.staged_paths(cwd=repo) if path not in set(conflict)]
    (repo / "f.txt").write_text("resolved\n", encoding="utf-8")
    (repo / name).write_text("junk\n", encoding="utf-8")
    _git(repo, "add", "--", f":(literal){name}")
    git.stage_merge_resolution(cwd=repo, conflict_paths=conflict, already_staged=already)
    git.commit(cwd=repo, message="merge main")
    assert _git(repo, "show", "HEAD:f.txt") == "resolved\n"
    assert _git(repo, "show", "HEAD:a.txt") == "a-main\n"
    assert _git(repo, "show", "HEAD:keep.txt") == "main\n"
    assert name not in _git(repo, "ls-tree", "-r", "--name-only", "HEAD").splitlines()
    assert (repo / "f.txt").read_text(encoding="utf-8") == "resolved\n"
    assert (repo / name).read_text(encoding="utf-8") == "junk\n"
    assert _git(repo, "status", "--porcelain=v1", "-uall").splitlines() == [f"?? {name}"]
    assert len(_git(repo, "rev-list", "--parents", "-n1", "HEAD").split()) == 3
