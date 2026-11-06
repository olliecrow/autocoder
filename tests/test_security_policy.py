from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest
from test_git_merge import _git
from test_git_merge import repo as repo

ROOT = Path(__file__).resolve().parents[1]


def scan(path):
    return subprocess.run(["bash", str(ROOT / "scripts/security/check-sensitive-text.sh"), str(path)],
                          capture_output=True)


@pytest.mark.parametrize("text,allowed", [
    ("/Users/" + "YOU/project", True),
    ("/home/" + "user/project", True),
    ("/Users/" + "YOUNG/project", False),
    ("/home/" + "userbob/project", False),
    ("/Users/" + "YOU /home/" + "someone/project", False),
    ("C:" + "\\Users\\someone\\project", False),
    ("C:" + "/Users/" + "someone/project", False),
])
def test_path_policy_checks_each_complete_match(tmp_path, text, allowed):
    target = tmp_path / "input"
    target.write_text(text)
    assert (scan(target).returncode == 0) == allowed


def test_missing_policy_input_fails(tmp_path):
    assert scan(tmp_path / "absent").returncode != 0


@pytest.mark.parametrize("text,blocked", [
    ("sk-ant-oat01-" + "a" * 20, True),
    ("sk-ant-api03-" + "b" * 20, True),
    ("sk-proj-" + "c" * 20, True),
    ("eyJ" + "a" * 10 + ".eyJ" + "b" * 10 + "." + "c" * 10, True),
    ("ghp_" + "a" * 20, True),
    ("gho_" + "a" * 20, True),
    ("ghu_" + "a" * 20, True),
    ("ghs_" + "a" * 20, True),
    ("ghr_" + "a" * 20, True),
    ("github_pat_" + "a" * 20, True),
    ("sk-projection-matrix-helper", False),
    ("eyJ" + "abc.eyJ" + "abc.abc", False),
    ("sk-" + "a" * 19, False),
])
def test_shell_policy_matches_provider_tokens_and_not_ordinary_identifiers(tmp_path, text, blocked):
    target = tmp_path / "input"
    target.write_text("value " + text + "\n", encoding="utf-8")
    assert (scan(target).returncode != 0) is blocked


def setup_scripts(repo):
    shutil.copytree(ROOT / "scripts", repo / "scripts")
    return repo / "scripts/security/check-push-range.sh"


def check_range(repo, script, base, tip):
    return subprocess.run(["bash", str(script), "--from", base, "--to", tip],
                          cwd=repo, capture_output=True)


@pytest.mark.parametrize("invalid_base", [True, False])
def test_bad_revision_fails_closed(repo, invalid_base):
    script = setup_scripts(repo)
    head = _git(repo, "rev-parse", "HEAD").strip()
    invalid = "a" * 40
    result = check_range(repo, script, invalid if invalid_base else head, head if invalid_base else invalid)
    assert result.returncode != 0


def test_push_range_scans_file_diffs_and_plus_lines(repo):
    script = setup_scripts(repo)
    base = _git(repo, "rev-parse", "HEAD").strip()
    (repo / "bad").write_text("++ local: /home/" + "someone/project\n")
    _git(repo, "add", "bad")
    _git(repo, "commit", "-qm", "change")
    tip = _git(repo, "rev-parse", "HEAD").strip()
    assert check_range(repo, script, base, tip).returncode != 0


def run_ci_range(repo, tmp_path, *, event, before, tip, scanner=None):
    """Run the CI wrapper with a fake gitleaks that records its arguments, or a real scanner."""
    fakebin = tmp_path / "bin"
    fakebin.mkdir(exist_ok=True)
    fake = fakebin / "gitleaks"
    fake.write_text(f'#!/bin/sh\nprintf "%s\\n" "$@" > "$SCAN_ARGS"\n{scanner or ""}\n')
    fake.chmod(0o700)
    args_file = tmp_path / "args"
    env = {**os.environ, "PATH": str(fakebin) + os.pathsep + os.environ["PATH"],
           "GITHUB_EVENT_NAME": event, "PUSH_BEFORE_SHA": before,
           "GITHUB_SHA": tip, "SCAN_ARGS": str(args_file)}
    result = subprocess.run(["bash", "scripts/security/check-ci-range.sh"], cwd=repo, env=env,
                            capture_output=True)
    return result, args_file.read_text() if args_file.exists() else ""


def commit_bad_ancestor(repo):
    (repo / "bad").write_text("/home/" + "someone/project\n")
    _git(repo, "add", "bad")
    _git(repo, "commit", "-qm", "change")
    (repo / "later").write_text("clean\n")
    _git(repo, "add", "later")
    _git(repo, "commit", "-qm", "later")
    return _git(repo, "rev-parse", "HEAD").strip()


@pytest.mark.parametrize("event,before", [("schedule", ""), ("push", ""), ("push", "0" * 40), ("push", "b" * 40)])
def test_ci_missing_base_scans_full_history_as_text(repo, event, before, tmp_path):
    setup_scripts(repo)
    tip = commit_bad_ancestor(repo)  # the secret is below the tip
    result, args = run_ci_range(repo, tmp_path, event=event, before=before, tip=tip)
    assert result.returncode != 0  # shell scan backs up the gitleaks home-path blind spot
    assert "--log-opts=--text --no-ext-diff --no-textconv --diff-merges=first-parent " + tip + "\n" in args
    assert 'cron: "23 6 * * 1"' in (ROOT / ".github/workflows/security-policy.yml").read_text()


@pytest.mark.parametrize("hide", ["nul", "diffattr"])
def test_push_range_scans_binary_and_diff_disabled_files(repo, hide):
    script = setup_scripts(repo)
    base = _git(repo, "rev-parse", "HEAD").strip()
    content = b"local: /home/" + b"someone/project\n"
    if hide == "nul":
        content += b"\x00"
    else:
        (repo / ".gitattributes").write_text("f.txt -diff\n")
    (repo / "f.txt").write_bytes(content)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "change")
    tip = _git(repo, "rev-parse", "HEAD").strip()
    assert check_range(repo, script, base, tip).returncode != 0


def test_push_range_without_base_scans_every_reachable_commit(repo):
    script = setup_scripts(repo)
    tip = commit_bad_ancestor(repo)
    # A remote-tracking ref at the tip used to hide every commit from a zero-base scan.
    _git(repo, "update-ref", "refs/remotes/origin/main", tip)
    assert check_range(repo, script, "0" * 40, tip).returncode != 0


def test_push_range_scans_paths(repo):
    script = setup_scripts(repo)
    base = _git(repo, "rev-parse", "HEAD").strip()
    (repo / ("ghp_" + "A" * 30)).write_text("clean\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "change")
    tip = _git(repo, "rev-parse", "HEAD").strip()
    assert check_range(repo, script, base, tip).returncode != 0


@pytest.mark.parametrize("hide", ["nul", "diffattr"])
def test_ci_gitleaks_scans_binary_and_diff_disabled_files(repo, hide, tmp_path):
    scanner = shutil.which("gitleaks")
    if scanner is None:
        pytest.skip("gitleaks is checked in security CI")
    setup_scripts(repo)
    shutil.copy(ROOT / ".gitleaks.toml", repo / ".gitleaks.toml")
    base = _git(repo, "rev-parse", "HEAD").strip()
    content = b"token: ghp_" + b"A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8" + b"\n"
    if hide == "nul":
        content += b"\x00"
    else:
        (repo / ".gitattributes").write_text("f.txt -diff\n")
    (repo / "f.txt").write_bytes(content)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "change")
    tip = _git(repo, "rev-parse", "HEAD").strip()
    # The fake records arguments, then runs the real scanner with them.
    result, _ = run_ci_range(repo, tmp_path, event="push", before=base, tip=tip,
                             scanner=f'exec "{scanner}" "$@"')
    assert result.returncode != 0
    assert b"leaks found" in result.stdout + result.stderr


def test_gitleaks_path_allowlist_is_per_secret_and_anchored(tmp_path):
    import tomllib
    config = tomllib.loads((ROOT / ".gitleaks.toml").read_text())
    rules = {rule["id"]: rule for rule in config["rules"]}
    assert set(rules) == {"local-system-paths", "local-windows-paths"}
    unix = rules["local-system-paths"]
    assert unix["secretGroup"] == 1
    assert unix["regex"].startswith("/(")
    for rule in rules.values():
        assert rule["secretGroup"] == 1
        allow = rule["allowlists"][0]
        assert allow["regexTarget"] == "secret"
        assert all(pattern.startswith("^") and pattern.endswith("$") for pattern in allow["regexes"])
    scanner = shutil.which("gitleaks")
    if scanner is None:
        pytest.skip("gitleaks is checked in security CI")
    (tmp_path / "bad.txt").write_text("/Users/" + "YOU /Users/" + "YOUNG/project")
    result = subprocess.run([scanner, "dir", "--redact", "--no-banner", "--config",
                             str(ROOT / ".gitleaks.toml"), str(tmp_path)], capture_output=True)
    assert result.returncode == 1


@pytest.mark.parametrize("text,expected", [
    ("/home/" + "someone/project", 1),
    ("/Users/" + "someone/project", 1),
    ("C:" + "\\Users\\someone\\project", 1),
    ("C:" + "/Users/" + "someone/project", 1),
    ("/home/" + "user/project", 0),
    ("/Users/" + "YOU/project", 0),
    ("C:" + "\\Users\\YOU\\project", 0),
    ("/home/" + "userbob/project", 1),
    ("/Users/" + "YOUNG/project", 1),
    ("/home/" + "user /home/" + "someone/project", 1),
    ("prefix /home/" + "someone", 1),
])
def test_gitleaks_reports_real_local_paths_and_allows_placeholders(tmp_path, text, expected):
    scanner = shutil.which("gitleaks")
    if scanner is None:
        pytest.skip("gitleaks is checked in security CI")
    (tmp_path / "bad.txt").write_text(text + "\n", encoding="utf-8")
    result = subprocess.run([scanner, "dir", "--redact", "--no-banner", "--config",
                             str(ROOT / ".gitleaks.toml"), str(tmp_path)], capture_output=True)
    assert result.returncode == expected


def test_scanner_command_failure_is_not_clean(tmp_path, monkeypatch):
    target = tmp_path / "input"
    target.write_text("safe")
    fakebin = tmp_path / "bin"
    fakebin.mkdir()
    fake = fakebin / "grep"
    fake.write_text("#!/bin/sh\nexit 2\n")
    fake.chmod(0o700)
    monkeypatch.setenv("PATH", str(fakebin) + os.pathsep + os.environ["PATH"])
    assert scan(target).returncode == 2


def test_merge_added_line_is_scanned(repo):
    script = setup_scripts(repo)
    _git(repo, "checkout", "-q", "main")
    (repo / "f.txt").write_text("main\n")
    _git(repo, "add", "f.txt")
    _git(repo, "commit", "-qm", "main change")
    _git(repo, "checkout", "-q", "issue")
    (repo / "f.txt").write_text("issue\n")
    _git(repo, "add", "f.txt")
    _git(repo, "commit", "-qm", "issue change")
    base = _git(repo, "rev-parse", "HEAD").strip()
    result = subprocess.run(["git", "merge", "--no-edit", "main"], cwd=repo, capture_output=True)
    assert result.returncode == 1
    (repo / "f.txt").write_text("++ /home/" + "someone/project\n")
    _git(repo, "add", "f.txt")
    _git(repo, "commit", "-qm", "resolve")
    tip = _git(repo, "rev-parse", "HEAD").strip()
    assert check_range(repo, script, base, tip).returncode != 0
