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


@pytest.mark.parametrize("event,before", [("schedule", ""), ("push", ""), ("push", "0" * 40)])
def test_ci_missing_base_scans_tip_and_file_diffs(repo, event, before, tmp_path):
    setup_scripts(repo)
    (repo / "bad").write_text("/home/" + "someone/project\n")
    _git(repo, "add", "bad")
    _git(repo, "commit", "-qm", "change")
    tip = _git(repo, "rev-parse", "HEAD").strip()
    fakebin = tmp_path / "bin"
    fakebin.mkdir()
    fake = fakebin / "gitleaks"
    fake.write_text('#!/bin/sh\nprintf "%s\\n" "$@" > "$SCAN_ARGS"\n')
    fake.chmod(0o700)
    args_file = tmp_path / "args"
    env = {**os.environ, "PATH": str(fakebin) + os.pathsep + os.environ["PATH"],
           "GITHUB_EVENT_NAME": event, "PUSH_BEFORE_SHA": before,
           "GITHUB_SHA": tip, "SCAN_ARGS": str(args_file)}
    result = subprocess.run(["bash", "scripts/security/check-ci-range.sh"], cwd=repo, env=env,
                            capture_output=True)
    assert result.returncode != 0  # shell scan backs up the gitleaks home-path blind spot
    assert "--diff-merges=first-parent " + tip + "^!" in args_file.read_text()
    assert 'cron: "23 6 * * 1"' in (ROOT / ".github/workflows/security-policy.yml").read_text()


def test_gitleaks_path_allowlist_is_per_secret_and_anchored(tmp_path):
    import tomllib
    config = tomllib.loads((ROOT / ".gitleaks.toml").read_text())
    allow = config["rules"][0]["allowlists"][0]
    assert allow["regexTarget"] == "secret"
    assert all(pattern.startswith("^") and pattern.endswith("$") for pattern in allow["regexes"])
    scanner = shutil.which("gitleaks")
    if scanner is None:
        pytest.skip("gitleaks is checked in security CI")
    (tmp_path / "bad.txt").write_text("/Users/" + "YOU /Users/" + "YOUNG/project")
    result = subprocess.run([scanner, "dir", "--redact", "--no-banner", "--config",
                             str(ROOT / ".gitleaks.toml"), str(tmp_path)], capture_output=True)
    assert result.returncode == 1
