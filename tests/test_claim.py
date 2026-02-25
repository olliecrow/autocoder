from __future__ import annotations

from types import SimpleNamespace

from autocoder.claim import parse_claim_comment
from autocoder.gh import IssueComment, IssueDetail
from autocoder.run import _issue_claimed_by_this_instance


def test_parse_claim_comment() -> None:
    body = "\n".join(
        [
            "[autocoder]",
            "",
            "claimed by autocoder.",
            "instance: 123e4567-e89b-12d3-a456-426614174000",
            "branch: autocoder/issue-1-test",
            "next: doing things",
            "",
        ]
    )
    info = parse_claim_comment(body)
    assert info is not None
    assert info.instance_id == "123e4567-e89b-12d3-a456-426614174000"
    assert info.branch == "autocoder/issue-1-test"


def test_parse_claim_comment_rejects_non_autocoder_prefix() -> None:
    assert parse_claim_comment("hello") is None


def test_issue_claimed_by_this_instance_ignores_non_allowlisted_comment_author() -> None:
    rt = SimpleNamespace(instance_id="123e4567-e89b-12d3-a456-426614174000")
    body = "\n".join(
        [
            "[autocoder]",
            "",
            "claimed by autocoder.",
            f"instance: {rt.instance_id}",
            "branch: autocoder/issue-1-test",
            "next: doing things",
            "",
        ]
    )
    issue = IssueDetail(
        number=1,
        title="t",
        url="https://example.test/issues/1",
        state="OPEN",
        updated_at="2026-02-13T00:00:00Z",
        author="olliecrow",
        body="",
        labels=("autocoder", "autocoder:claimed"),
        comments=(
            IssueComment(
                id="c1",
                author="someoneelse",
                body=body,
                created_at="2026-02-13T00:00:01Z",
                updated_at="2026-02-13T00:00:01Z",
                url="https://example.test/issues/1#issuecomment-c1",
            ),
        ),
    )
    assert _issue_claimed_by_this_instance(rt=rt, issue=issue) is None


def test_issue_claimed_by_this_instance_accepts_allowlisted_comment_author() -> None:
    rt = SimpleNamespace(instance_id="123e4567-e89b-12d3-a456-426614174000")
    body = "\n".join(
        [
            "[autocoder]",
            "",
            "claimed by autocoder.",
            f"instance: {rt.instance_id}",
            "branch: autocoder/issue-1-test",
            "next: doing things",
            "",
        ]
    )
    issue = IssueDetail(
        number=1,
        title="t",
        url="https://example.test/issues/1",
        state="OPEN",
        updated_at="2026-02-13T00:00:00Z",
        author="olliecrow",
        body="",
        labels=("autocoder", "autocoder:claimed"),
        comments=(
            IssueComment(
                id="c1",
                author="olliecrow",
                body=body,
                created_at="2026-02-13T00:00:01Z",
                updated_at="2026-02-13T00:00:01Z",
                url="https://example.test/issues/1#issuecomment-c1",
            ),
        ),
    )
    assert _issue_claimed_by_this_instance(rt=rt, issue=issue) == "autocoder/issue-1-test"


def test_issue_claimed_by_this_instance_uses_latest_claim_comment() -> None:
    rt = SimpleNamespace(instance_id="11111111-1111-1111-1111-111111111111")
    body_old = "\n".join(
        [
            "[autocoder]",
            "",
            "claimed by autocoder.",
            f"instance: {rt.instance_id}",
            "branch: autocoder/issue-1-old",
            "",
        ]
    )
    body_new_other = "\n".join(
        [
            "[autocoder]",
            "",
            "claimed by autocoder.",
            "instance: 22222222-2222-2222-2222-222222222222",
            "branch: autocoder/issue-1-new",
            "",
        ]
    )
    issue = IssueDetail(
        number=1,
        title="t",
        url="https://example.test/issues/1",
        state="OPEN",
        updated_at="2026-02-13T00:00:00Z",
        author="olliecrow",
        body="",
        labels=("autocoder", "autocoder:claimed"),
        comments=(
            IssueComment(
                id="c-old",
                author="olliecrow",
                body=body_old,
                created_at="2026-02-13T00:00:01Z",
                updated_at="2026-02-13T00:00:01Z",
                url="https://example.test/issues/1#issuecomment-c-old",
            ),
            IssueComment(
                id="c-new",
                author="olliecrow",
                body=body_new_other,
                created_at="2026-02-13T00:01:01Z",
                updated_at="2026-02-13T00:01:01Z",
                url="https://example.test/issues/1#issuecomment-c-new",
            ),
        ),
    )
    assert _issue_claimed_by_this_instance(rt=rt, issue=issue) is None


def test_issue_claimed_by_this_instance_accepts_latest_matching_claim() -> None:
    rt = SimpleNamespace(instance_id="11111111-1111-1111-1111-111111111111")
    body_old_other = "\n".join(
        [
            "[autocoder]",
            "",
            "claimed by autocoder.",
            "instance: 22222222-2222-2222-2222-222222222222",
            "branch: autocoder/issue-1-old",
            "",
        ]
    )
    body_new = "\n".join(
        [
            "[autocoder]",
            "",
            "claimed by autocoder.",
            f"instance: {rt.instance_id}",
            "branch: autocoder/issue-1-new",
            "",
        ]
    )
    issue = IssueDetail(
        number=1,
        title="t",
        url="https://example.test/issues/1",
        state="OPEN",
        updated_at="2026-02-13T00:00:00Z",
        author="olliecrow",
        body="",
        labels=("autocoder", "autocoder:claimed"),
        comments=(
            IssueComment(
                id="c-old",
                author="olliecrow",
                body=body_old_other,
                created_at="2026-02-13T00:00:01Z",
                updated_at="2026-02-13T00:00:01Z",
                url="https://example.test/issues/1#issuecomment-c-old",
            ),
            IssueComment(
                id="c-new",
                author="olliecrow",
                body=body_new,
                created_at="2026-02-13T00:01:01Z",
                updated_at="2026-02-13T00:01:01Z",
                url="https://example.test/issues/1#issuecomment-c-new",
            ),
        ),
    )
    assert _issue_claimed_by_this_instance(rt=rt, issue=issue) == "autocoder/issue-1-new"
