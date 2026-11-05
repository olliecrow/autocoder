from __future__ import annotations

import re
from dataclasses import dataclass

AUTOCODER_COMMENT_PREFIX = "[autocoder]\n\n"

_CLAIM_INSTANCE_RE = re.compile(r"(?mi)^instance:\s*(?P<id>[0-9a-fA-F-]{16,})\s*$")
_CLAIM_BRANCH_RE = re.compile(r"(?mi)^branch:\s*(?P<branch>\S+)\s*$")


@dataclass(frozen=True)
class ClaimInfo:
    instance_id: str
    branch: str


def parse_claim_comment(body: str) -> ClaimInfo | None:
    """
    Parse a standard autocoder claim comment.

    This is intentionally simple and tolerant; the claim comment is expected to be
    human-readable with minimal machine-readable lines.
    """
    text = body or ""
    if not text.startswith(AUTOCODER_COMMENT_PREFIX):
        return None

    m_id = _CLAIM_INSTANCE_RE.search(text)
    m_branch = _CLAIM_BRANCH_RE.search(text)
    if not m_id or not m_branch:
        return None

    branch = m_branch.group("branch").strip()
    if not re.fullmatch(r"autocoder/issue-[1-9][0-9]*-[a-z0-9-]+", branch):
        return None
    return ClaimInfo(
        instance_id=m_id.group("id").strip(),
        branch=branch,
    )

