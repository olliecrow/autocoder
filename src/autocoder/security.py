from __future__ import annotations

import hashlib
import json
from typing import Iterable


# Safety measure: only accept instructions from these GitHub logins.
# Keep this committed and intentionally small; we can generalize later.
ALLOWED_GITHUB_LOGINS: frozenset[str] = frozenset(
    {
        "olliecrow",
    }
)


def normalize_login(login: str) -> str:
    return (login or "").strip().lstrip("@").lower()


def is_allowed_login(login: str) -> bool:
    return normalize_login(login) in ALLOWED_GITHUB_LOGINS


def filter_allowed_logins(logins: Iterable[str]) -> tuple[str, ...]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in logins:
        n = normalize_login(raw)
        if not n or n in seen:
            continue
        if n in ALLOWED_GITHUB_LOGINS:
            seen.add(n)
            out.append(n)
    return tuple(out)


# Because autocoder posts GitHub comments as the locally-authenticated user (same as the human),
# we treat comments prefixed with this marker as bot-authored, and ignore them as *triggers*.
_AUTOCODER_COMMENT_PREFIX_LINE = "[autocoder]"


def is_autocoder_comment(body: str) -> bool:
    return (body or "").lstrip().lower().startswith(_AUTOCODER_COMMENT_PREFIX_LINE)


def is_allowed_human_comment(*, author: str, body: str) -> bool:
    return is_allowed_login(author) and not is_autocoder_comment(body)


def _sha256_hexdigest(obj: object) -> str:
    data = json.dumps(obj, sort_keys=True, ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def issue_allowed_human_activity_digest(
    *,
    comments: Iterable[tuple[str, str, str, str]],
    issue_author: str | None = None,
) -> str:
    """
    Digest of allowlisted *human* issue activity.

    Inputs:
    - comments: iterable of (comment_id, author_login, updated_at, body)
    - issue_author: issue author login (optional)

    Excludes:
    - comments by non-allowlisted logins
    - bot-authored comments (identified by `[autocoder]` prefix)

    Notes:
    - Ignores edits: digest is based on stable comment IDs only.
    - When `issue_author` is provided, only comment IDs from that same login are included.
    """
    issue_actor = normalize_login(issue_author or "")
    kept_ids: list[str] = []
    for cid, author, _updated_at, body in comments:
        if not is_allowed_human_comment(author=author, body=body):
            continue
        if issue_actor and normalize_login(author) != issue_actor:
            continue
        kept_ids.append(cid or "")

    kept_ids.sort()

    payload = {
        "comments": kept_ids,
    }
    return _sha256_hexdigest(payload)


def pr_allowed_human_activity_digest(
    *,
    comments: Iterable[tuple[str, str, str, str]],
    reviews: Iterable[tuple[str, str, str, str, str]] | None = None,
    issue_author: str | None = None,
) -> str:
    """
    Digest of allowlisted *human* PR activity (excludes bot comments).

    Inputs:
    - comments: iterable of (comment_id, author_login, updated_at, body)
    - reviews: iterable of (review_id, author_login, submitted_at, state, body)
    - issue_author: when provided, include only activity authored by this login

    Notes:
    - Ignores edits: digest is based on stable PR comment/review IDs only.
    """
    issue_actor = normalize_login(issue_author or "")
    kept_comment_ids: list[str] = []
    for cid, author, _updated_at, body in comments:
        if not is_allowed_human_comment(author=author, body=body):
            continue
        if issue_actor and normalize_login(author) != issue_actor:
            continue
        kept_comment_ids.append(cid or "")

    kept_review_ids: list[str] = []
    if reviews is not None:
        for rid, author, _submitted_at, _state, body in reviews:
            if not is_allowed_human_comment(author=author, body=body):
                continue
            if issue_actor and normalize_login(author) != issue_actor:
                continue
            kept_review_ids.append(rid or "")

    kept_comment_ids.sort()
    kept_review_ids.sort()
    payload = {"comments": kept_comment_ids, "reviews": kept_review_ids}
    return _sha256_hexdigest(payload)
