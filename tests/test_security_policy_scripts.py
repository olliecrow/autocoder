from __future__ import annotations

from pathlib import Path
import subprocess


REPO_ROOT = Path(__file__).resolve().parents[1]
CHECK_SCRIPT = REPO_ROOT / "scripts" / "security" / "check-sensitive-text.sh"


def _run_check(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(CHECK_SCRIPT), "--context=test", str(path)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_sensitive_text_check_accepts_function_assignment(tmp_path: Path) -> None:
    source = tmp_path / "source.py"
    source.write_text("token = _github_auth_token(runtime=runtime)\n", encoding="utf-8")

    result = _run_check(source)

    assert result.returncode == 0


def test_sensitive_text_check_redacts_secret_value(tmp_path: Path) -> None:
    source = tmp_path / "message.txt"
    fake_secret = "".join(("abc123", "456789XYZ"))
    source.write_text(f"token = {fake_secret}\n", encoding="utf-8")

    result = _run_check(source)

    assert result.returncode == 1
    assert "rule=secret-assignment" in result.stderr
    assert fake_secret not in result.stderr


def test_sensitive_text_check_redacts_private_path(tmp_path: Path) -> None:
    source = tmp_path / "message.txt"
    private_path = "/" + "Users/sensitive-person/project"
    source.write_text(f"worked in {private_path}\n", encoding="utf-8")

    result = _run_check(source)

    assert result.returncode == 1
    assert "rule=local-path" in result.stderr
    assert private_path not in result.stderr
    assert "sensitive-person" not in result.stderr
