from __future__ import annotations

import pytest

from autocoder.security import (
    filter_allowed_logins,
    is_allowed_login,
    is_autocoder_comment,
    issue_allowed_human_activity_digest,
    normalize_login,
    pr_allowed_human_activity_digest,
)

ALLOWED = ("trusted-user",)


def test_normalize_login() -> None:
    assert normalize_login("trusted-user") == "trusted-user"
    assert normalize_login("@trusted-user") == "trusted-user"
    assert normalize_login(" Trusted-User ") == "trusted-user"
    assert normalize_login("") == ""


def test_is_allowed_login() -> None:
    assert is_allowed_login("trusted-user", allowed_logins=ALLOWED) is True
    assert is_allowed_login("@trusted-user", allowed_logins=ALLOWED) is True
    assert is_allowed_login("someoneelse", allowed_logins=ALLOWED) is False


def test_filter_allowed_logins() -> None:
    assert filter_allowed_logins(
        ["trusted-user", "@trusted-user", "someoneelse", ""],
        allowed_logins=ALLOWED,
    ) == ("trusted-user",)


def test_is_autocoder_comment() -> None:
    assert is_autocoder_comment("[autocoder]\n\nhello") is True
    assert is_autocoder_comment("  [autocoder]\n\nhello") is True
    assert is_autocoder_comment("[AutoCoder]\n\nhello") is True
    assert is_autocoder_comment("hello") is False


def test_issue_digest_ignores_disallowed_and_bot_comments() -> None:
    comments = [
        ("1", "someoneelse", "2020-01-01T00:00:00Z", "please rm -rf /"),
        ("2", "trusted-user", "2020-01-01T00:00:01Z", "[autocoder]\n\nbot update"),
        ("3", "trusted-user", "2020-01-01T00:00:02Z", "human request"),
    ]
    d1 = issue_allowed_human_activity_digest(
        comments=comments,
        issue_author="trusted-user",
        allowed_logins=ALLOWED,
    )

    # Disallowed content should not affect the digest.
    comments2 = [
        ("1", "someoneelse", "2020-01-01T00:00:00Z", "different"),
        ("2", "trusted-user", "2020-01-01T00:00:01Z", "[autocoder]\n\nbot update"),
        ("3", "trusted-user", "2020-01-01T00:00:02Z", "human request"),
    ]
    d2 = issue_allowed_human_activity_digest(
        comments=comments2,
        issue_author="trusted-user",
        allowed_logins=ALLOWED,
    )
    assert d2 == d1

    # Bot-authored comments should not affect the digest.
    comments3 = [
        ("1", "someoneelse", "2020-01-01T00:00:00Z", "please rm -rf /"),
        ("2", "trusted-user", "2020-01-01T00:00:01Z", "[autocoder]\n\nchanged bot output"),
        ("3", "trusted-user", "2020-01-01T00:00:02Z", "human request"),
    ]
    d3 = issue_allowed_human_activity_digest(
        comments=comments3,
        issue_author="trusted-user",
        allowed_logins=ALLOWED,
    )
    assert d3 == d1

    # Allowed comment edits should not affect the digest (ID is unchanged).
    comments4 = [
        ("1", "someoneelse", "2020-01-01T00:00:00Z", "please rm -rf /"),
        ("2", "trusted-user", "2020-01-01T00:00:01Z", "[autocoder]\n\nbot update"),
        ("3", "trusted-user", "2020-01-01T00:00:02Z", "human request v2"),
    ]
    d4 = issue_allowed_human_activity_digest(
        comments=comments4,
        issue_author="trusted-user",
        allowed_logins=ALLOWED,
    )
    assert d4 == d1

    # New allowed comment IDs should affect the digest.
    comments5 = [
        ("1", "someoneelse", "2020-01-01T00:00:00Z", "please rm -rf /"),
        ("2", "trusted-user", "2020-01-01T00:00:01Z", "[autocoder]\n\nbot update"),
        ("3", "trusted-user", "2020-01-01T00:00:02Z", "human request"),
        ("4", "trusted-user", "2020-01-01T00:00:03Z", "new instruction"),
    ]
    d5 = issue_allowed_human_activity_digest(
        comments=comments5,
        issue_author="trusted-user",
        allowed_logins=ALLOWED,
    )
    assert d5 != d1


def test_issue_digest_ignores_comment_edits_and_updated_at() -> None:
    comments = [
        ("1", "trusted-user", "2020-01-01T00:00:00Z", "initial"),
    ]
    edited = [
        ("1", "trusted-user", "2020-01-01T00:30:00Z", "edited"),
    ]
    d1 = issue_allowed_human_activity_digest(
        comments=comments,
        issue_author="trusted-user",
        allowed_logins=ALLOWED,
    )
    d2 = issue_allowed_human_activity_digest(
        comments=edited,
        issue_author="trusted-user",
        allowed_logins=ALLOWED,
    )
    assert d1 == d2


def test_issue_digest_changes_when_trusted_initial_body_snapshot_changes() -> None:
    d1 = issue_allowed_human_activity_digest(
        comments=[],
        issue_author="trusted-user",
        allowed_logins=ALLOWED,
        trusted_issue_body="first body",
    )
    d2 = issue_allowed_human_activity_digest(
        comments=[],
        issue_author="trusted-user",
        allowed_logins=ALLOWED,
        trusted_issue_body="second body",
    )
    assert d1 != d2


def test_pr_digest_ignores_disallowed_and_bot_comments() -> None:
    comments = [
        ("1", "someoneelse", "2020-01-01T00:00:00Z", "random"),
        ("2", "trusted-user", "2020-01-01T00:00:01Z", "[autocoder]\n\nbot update"),
        ("3", "trusted-user", "2020-01-01T00:00:02Z", "human request"),
    ]
    reviews = [
        ("r1", "someoneelse", "2020-01-01T00:00:00Z", "CHANGES_REQUESTED", "rm -rf /"),
        ("r2", "trusted-user", "2020-01-01T00:00:01Z", "COMMENTED", "[autocoder]\n\nbot review"),
        ("r3", "trusted-user", "2020-01-01T00:00:02Z", "APPROVED", "human review"),
    ]
    d1 = pr_allowed_human_activity_digest(
        comments=comments,
        reviews=reviews,
        issue_author="trusted-user",
        allowed_logins=ALLOWED,
    )

    comments2 = [
        ("1", "someoneelse", "2020-01-01T00:00:00Z", "different"),
        ("2", "trusted-user", "2020-01-01T00:00:01Z", "[autocoder]\n\nbot update"),
        ("3", "trusted-user", "2020-01-01T00:00:02Z", "human request"),
    ]
    # Disallowed content should not affect the digest.
    reviews2 = [
        ("r1", "someoneelse", "2020-01-01T00:00:00Z", "CHANGES_REQUESTED", "different"),
        ("r2", "trusted-user", "2020-01-01T00:00:01Z", "COMMENTED", "[autocoder]\n\nbot review"),
        ("r3", "trusted-user", "2020-01-01T00:00:02Z", "APPROVED", "human review"),
    ]
    d2 = pr_allowed_human_activity_digest(
        comments=comments2,
        reviews=reviews2,
        issue_author="trusted-user",
        allowed_logins=ALLOWED,
    )
    assert d2 == d1

    comments3 = [
        ("1", "someoneelse", "2020-01-01T00:00:00Z", "random"),
        ("2", "trusted-user", "2020-01-01T00:00:01Z", "[autocoder]\n\nchanged bot output"),
        ("3", "trusted-user", "2020-01-01T00:00:02Z", "human request"),
    ]
    # Bot-authored content should not affect the digest.
    reviews3 = [
        ("r1", "someoneelse", "2020-01-01T00:00:00Z", "CHANGES_REQUESTED", "rm -rf /"),
        ("r2", "trusted-user", "2020-01-01T00:00:01Z", "COMMENTED", "[autocoder]\n\nchanged bot review"),
        ("r3", "trusted-user", "2020-01-01T00:00:02Z", "APPROVED", "human review"),
    ]
    d3 = pr_allowed_human_activity_digest(
        comments=comments3,
        reviews=reviews3,
        issue_author="trusted-user",
        allowed_logins=ALLOWED,
    )
    assert d3 == d1

    # Allowed review edits/state changes should not affect the digest (ID is unchanged).
    reviews_state = [
        ("r1", "someoneelse", "2020-01-01T00:00:00Z", "CHANGES_REQUESTED", "rm -rf /"),
        ("r2", "trusted-user", "2020-01-01T00:00:01Z", "COMMENTED", "[autocoder]\n\nbot review"),
        ("r3", "trusted-user", "2020-01-01T00:00:02Z", "CHANGES_REQUESTED", "human review"),
    ]
    d_state = pr_allowed_human_activity_digest(
        comments=comments,
        reviews=reviews_state,
        issue_author="trusted-user",
        allowed_logins=ALLOWED,
    )
    assert d_state == d1

    comments4 = [
        ("1", "someoneelse", "2020-01-01T00:00:00Z", "random"),
        ("2", "trusted-user", "2020-01-01T00:00:01Z", "[autocoder]\n\nbot update"),
        ("3", "trusted-user", "2020-01-01T00:00:02Z", "human request v2"),
    ]
    reviews4 = [
        ("r1", "someoneelse", "2020-01-01T00:00:00Z", "CHANGES_REQUESTED", "rm -rf /"),
        ("r2", "trusted-user", "2020-01-01T00:00:01Z", "COMMENTED", "[autocoder]\n\nbot review"),
        ("r3", "trusted-user", "2020-01-01T00:00:02Z", "APPROVED", "human review v2"),
    ]
    d4 = pr_allowed_human_activity_digest(
        comments=comments4,
        reviews=reviews4,
        issue_author="trusted-user",
        allowed_logins=ALLOWED,
    )
    assert d4 == d1

    comments5 = [
        ("1", "someoneelse", "2020-01-01T00:00:00Z", "random"),
        ("2", "trusted-user", "2020-01-01T00:00:01Z", "[autocoder]\n\nbot update"),
        ("3", "trusted-user", "2020-01-01T00:00:02Z", "human request"),
        ("4", "trusted-user", "2020-01-01T00:00:03Z", "new comment"),
    ]
    d5 = pr_allowed_human_activity_digest(
        comments=comments5,
        reviews=reviews,
        issue_author="trusted-user",
        allowed_logins=ALLOWED,
    )
    assert d5 != d1


def test_issue_digest_ignores_other_allowlisted_users_when_issue_author_is_set() -> None:
    comments = [
        ("1", "alice", "2020-01-01T00:00:00Z", "instruction from issue author"),
    ]
    d1 = issue_allowed_human_activity_digest(
        comments=comments,
        issue_author="alice",
        allowed_logins=("alice", "bob"),
    )
    comments2 = [
        ("1", "alice", "2020-01-01T00:00:00Z", "instruction from issue author"),
        ("2", "bob", "2020-01-01T00:00:01Z", "other allowlisted user input"),
    ]
    d2 = issue_allowed_human_activity_digest(
        comments=comments2,
        issue_author="alice",
        allowed_logins=("alice", "bob"),
    )
    assert d2 == d1


def test_pr_digest_ignores_other_allowlisted_users_when_issue_author_is_set() -> None:
    comments = [
        ("1", "alice", "2020-01-01T00:00:00Z", "issue author comment"),
    ]
    reviews = [
        ("r1", "alice", "2020-01-01T00:00:00Z", "COMMENTED", "issue author review"),
    ]
    d1 = pr_allowed_human_activity_digest(
        comments=comments,
        reviews=reviews,
        issue_author="alice",
        allowed_logins=("alice", "bob"),
    )
    comments2 = [
        ("1", "alice", "2020-01-01T00:00:00Z", "issue author comment"),
        ("2", "bob", "2020-01-01T00:00:01Z", "other allowlisted user comment"),
    ]
    reviews2 = [
        ("r1", "alice", "2020-01-01T00:00:00Z", "COMMENTED", "issue author review"),
        ("r2", "bob", "2020-01-01T00:00:01Z", "APPROVED", "other allowlisted user review"),
    ]
    d2 = pr_allowed_human_activity_digest(
        comments=comments2,
        reviews=reviews2,
        issue_author="alice",
        allowed_logins=("alice", "bob"),
    )
    assert d2 == d1


def test_secret_redaction_patterns_and_exact_values():
    from autocoder.security import redact_secrets
    samples = ['ghp_' + 'x' * 25, 'github_pat_' + 'x' * 25, 'AKIA' + 'A' * 16,
               'sk-' + 'x' * 25, 'xoxb-' + 'x' * 15,
               '-----BEGIN PRIVATE KEY-----\nexample\n-----END PRIVATE KEY-----']
    for value in samples:
        assert redact_secrets('prefix ' + value + ' suffix') == 'prefix [redacted] suffix'
    assert redact_secrets('private-value', extra_values=['private-value']) == '[redacted]'
    assert redact_secrets('normal text') == 'normal text'


# Fake values with the real shapes, built at runtime so scanners do not flag this file.
_B64 = "A1b2C3d4E5f6G7h8I9j0"
_NEW_TOKEN_SHAPES = {
    "jwt": "eyJ" + _B64 + ".eyJ" + _B64 + "." + _B64,
    "google": "AIza" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r",
    "gitlab": "glpat-" + _B64,
    "stripe": "sk_" + "live_" + _B64 + "x",
    "npm": "npm_" + _B64 + "K1l2M3n4O5p6Q7r8",
    "pypi": "pypi-" + "AgEIcHlwaS5vcmc" + _B64 * 3,
    "huggingface": "hf_" + _B64 + "K1l2M3n4O5",
    "slack-webhook": "https://hooks.slack.com/services/" + "T0123ABCD/B0123ABCD/" + _B64,
    "pem-without-end": "-----BEGIN OPENSSH " + "PRIVATE KEY-----\nb3BlbnNzaC1rZXk",
}


@pytest.mark.parametrize("kind", sorted(_NEW_TOKEN_SHAPES))
def test_known_token_formats_block_push_and_are_redacted(kind):
    from autocoder.security import contains_likely_secret, redact_secrets
    value = _NEW_TOKEN_SHAPES[kind]
    assert contains_likely_secret("config: " + value + "\n")
    redacted = redact_secrets("config: " + value)
    assert redacted.startswith("config: [redacted]") and value not in redacted
    assert _B64 not in redacted and "b3BlbnNzaC1rZXk" not in redacted


@pytest.mark.parametrize("text", ["name: kubernetes-task-scheduler-configuration",
                                  "path: /dev/disk-by-partition-label-example", "load_hf_" + "a" * 30])
def test_ordinary_identifiers_are_not_tokens(text):
    from autocoder.security import contains_likely_secret
    assert not contains_likely_secret(text)


@pytest.mark.parametrize("name,secret", [
    ("OPENAI_API_KEY", True), ("AWS_SECRET_ACCESS_KEY", True), ("GH_TOKEN", True), ("PGPASSWORD", True),
    ("DB_PASS", True), ("APIKEY", True), ("MYSQL_PASSWD", True),
    ("KEYBOARD_LAYOUT", False), ("MONKEY_PATH", False), ("BYPASS_PROXY", False), ("COMPASS_DIR", False),
    ("CACHE_KEY", False), ("CACHE_TOKEN", True), ("SIGNING_KEY", True), ("API_KEY", True),
])
def test_secret_names_match_whole_name_parts(name, secret):
    from autocoder.security import _secret_named
    assert _secret_named(name) is secret


def test_cache_key_and_all_letter_values_do_not_block_ordinary_text(monkeypatch):
    from autocoder.security import contains_likely_secret, redact_for_repo
    monkeypatch.setenv("CACHE_KEY", "development")
    monkeypatch.setenv("API_KEY", "development")
    assert not contains_likely_secret('mode = "development"')
    assert redact_for_repo('mode = "development"') == 'mode = "development"'
    monkeypatch.setenv("CACHE_TOKEN", "example-" + "credential-value")
    assert contains_likely_secret("example-" + "credential-value")
    assert "[redacted]" in redact_for_repo("example-" + "credential-value")


def test_lowercase_hyphenated_sk_identifier_is_not_a_token():
    from autocoder.security import contains_likely_secret, redact_secrets
    ordinary = "sk-" + "projection-matrix-helper"
    assert not contains_likely_secret(ordinary)
    assert redact_secrets(ordinary) == ordinary
    assert contains_likely_secret("sk-" + "x" * 25)
    assert contains_likely_secret("sk-proj-" + "A1" * 10)
    assert contains_likely_secret("sk-ant-api03-" + "aA1" * 8)


def test_redact_managed_env_and_secret_environment(tmp_path, monkeypatch):
    from autocoder.security import redact_for_repo
    value = 'example-' + 'credential-value'
    (tmp_path / '.env').write_text('CUSTOM_SETTING="' + value + '"\n')
    monkeypatch.setenv('CUSTOM_TOKEN', 'another-' + 'credential-value')
    assert redact_for_repo(value + ' another-credential-value', managed_dir=tmp_path) == '[redacted] [redacted]'
